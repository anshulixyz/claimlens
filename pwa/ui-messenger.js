/* ClaimLens UI — live messenger feature: camera capture, verdict card, per-run
 * decision detail; calls /api/review. Depends on ui-base.js. */
/* ----------------------------- API ----------------------------- */
async function reviewClaim(claim_object, user_claim, dataUrls) {
  const res = await fetch("/api/review", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_object, user_claim, images: dataUrls }),
  });
  if (!res.ok) throw new Error("review failed (" + res.status + ")");
  return res.json();
}

const STATUS_META = {
  supported: { label: "Accepted", cls: "ok", icon: "check" },
  contradicted: { label: "Declined", cls: "bad", icon: "x" },
  not_enough_information: { label: "Needs more info", cls: "warn", icon: "alert" },
};
const OBJECTS = [["car", "car"], ["laptop", "laptop"], ["package", "package"]];

/* ============================ Camera capture ============================ */
function CameraSheet({ claimObject, onCapture, onClose }) {
  const videoRef = useRef(null);
  const [err, setErr] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let stream, cancelled = false;
    // Camera APIs only exist in a secure context (HTTPS or localhost). On a phone
    // hitting a plain http://LAN-IP, navigator.mediaDevices is undefined — so fail
    // loud with an actionable message instead of hanging on "Starting camera…".
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setErr("Camera needs a secure (HTTPS) connection. On your phone, open the https:// link for this demo — a plain http:// address can't access the camera.");
      return () => {};
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then(async (s) => {
        stream = s; const v = videoRef.current; if (!v || cancelled) return;
        v.srcObject = s; v.muted = true; v.playsInline = true; v.setAttribute("playsinline", "");
        try { await v.play(); } catch (_) {}
      })
      .catch((e) => setErr(e.message + " — allow camera access (localhost/HTTPS)."));
    return () => { cancelled = true; if (stream) stream.getTracks().forEach((t) => t.stop()); };
  }, []);
  const onReady = useCallback(() => { const v = videoRef.current; if (v && v.videoWidth > 0) setReady(true); }, []);
  const snap = useCallback(() => {
    const v = videoRef.current;
    if (!v || v.readyState < 2 || !v.videoWidth) { setReady(false); return; }
    const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    onCapture(c.toDataURL("image/jpeg", 0.85));
  }, [onCapture]);
  return html`
    <div class="sheet-bg" onClick=${onClose}>
      <div class="sheet" onClick=${(e) => e.stopPropagation()}>
        <div class="sheet-head"><b>Capture your ${claimObject}</b>
          <button class="iconbtn" onClick=${onClose} aria-label="Close"><${Icon} name="x" /></button></div>
        <p class="upl"><${Icon} name="lock" size=${14} /> Live capture only — uploads are disabled</p>
        <div class="cam">
          ${err ? html`<div class="cam-msg">${err}</div>`
                : html`<video ref=${videoRef} aria-label="Live camera preview" autoPlay muted playsInline
                    onLoadedMetadata=${onReady} onCanPlay=${onReady} onPlaying=${onReady}></video>`}
          ${!err && !ready ? html`<div class="cam-msg">Starting camera…</div>` : null}
        </div>
        <button class="btn accent block" onClick=${snap} disabled=${!!err || !ready}>
          <${Icon} name="camera" /> ${ready ? "Capture" : "Starting camera…"}</button>
      </div>
    </div>`;
}

/* ============================ Verdict + per-run detail ============================ */
function DecisionDetail({ d }) {
  const det = d.detail || {};
  return html`
    <div class="detail">
      ${det.claim_summary ? html`<div class="drow"><span>extracted claim</span><b>${det.claim_summary}</b></div>` : null}
      ${det.confidence != null ? html`<div class="drow"><span>confidence</span><b>${det.confidence} · ${det.confidence_band || ""}</b></div>` : null}
      ${(det.perception || []).length ? html`
        <div class="dsec">perception (what the model saw)</div>
        ${det.perception.map((p) => html`<div class="dline" key=${p.image_id}>
          <b>${p.image_id}</b> · object_present=${String(p.object_present)} · ${p.issue_type}/${p.object_part} · ${p.image_quality}
          ${p.notes ? html`<div class="dnote">${p.notes}</div>` : null}</div>`)}` : null}
      ${(det.tools || []).length ? html`
        <div class="dsec">tool signals (independent detectors)</div>
        ${det.tools.map((t) => html`<div class="dline" key=${t.name}>
          <b>${t.name}</b>${t.risk_flags.length ? html` · <span class="dflag">${t.risk_flags.join(", ")}</span>` : " · clear"}
          ${t.note ? html`<div class="dnote">${t.note}</div>` : null}</div>`)}` : null}
      ${(det.escalation_reasons || []).length ? html`
        <div class="dsec">human-in-the-loop</div>
        ${det.escalation_reasons.map((r, i) => html`<div class="dline" key=${i}>${r}</div>`)}` : null}
    </div>`;
}

function Verdict({ d }) {
  const m = STATUS_META[d.claim_status] || STATUS_META.not_enough_information;
  const flags = (d.risk_flags || "none").split(";").filter((f) => f && f !== "none");
  const [open, setOpen] = useState(false);
  return html`
    <div class="verdict ${m.cls}">
      <div class="vh"><span class="vi"><${Icon} name=${m.icon} size=${15} /></span>
        <b>${m.label}</b><span class="vsev">${d.severity}</span></div>
      <div class="vrow"><span>issue</span><b>${(d.issue_type || "—").replace(/_/g, " ")}</b>
        <span>part</span><b>${(d.object_part || "—").replace(/_/g, " ")}</b></div>
      ${flags.length ? html`<div class="vflags">${flags.map((f) =>
        html`<span class="vflag" key=${f}>${f.replace(/_/g, " ")}</span>`)}</div>` : null}
      <button class="dtoggle" onClick=${() => setOpen(!open)}>
        <${Icon} name="chevron" size=${14} cls=${open ? "rot" : ""} /> ${open ? "Hide" : "View"} decision detail</button>
      ${open ? html`<${DecisionDetail} d=${d} />` : null}
    </div>`;
}

/* ============================== Messenger ============================== */
function bubble(from, text, extra) { return { from, text, extra: extra || {}, t: Date.now() + Math.random() }; }

/* Common issues per object — chip-first (Zomato/Uber style) so the user taps
   instead of typing; "Something else" falls back to free text. Each entry is
   [chip label, the claim sentence sent to the pipeline as user_claim]. */
const ISSUES = {
  car: [["Dented panel", "My car has a dented panel."], ["Scratched paint", "My car's paint is scratched."], ["Cracked windshield", "My car's windshield is cracked."], ["Broken light", "A light on my car is broken."]],
  laptop: [["Cracked screen", "My laptop's screen is cracked."], ["Broken hinge", "My laptop's hinge is broken."], ["Dented body", "My laptop's body is dented."], ["Liquid damage", "My laptop has liquid damage."]],
  package: [["Crushed box", "My package box is crushed."], ["Torn packaging", "My package's packaging is torn."], ["Water damage", "My package got water damage."], ["Item broken inside", "The item inside my package is broken."]],
};

function Messenger() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [step, setStep] = useState("name");
  const [claim, setClaim] = useState({ object: "", text: "" });
  const [name, setName] = useState("");
  const [draft, setDraft] = useState("");
  const [cam, setCam] = useState(false);
  const [busy, setBusy] = useState(false);
  const body = useRef(null);

  useEffect(() => { if (open && !msgs.length) greet(); }, [open]);
  useEffect(() => { body.current?.scrollTo(0, body.current.scrollHeight); }, [msgs, busy]);
  useEffect(() => { window.__openLens = () => setOpen(true); }, []);

  const push = (m) => setMsgs((p) => [...p, m]);

  function greet() {
    setMsgs([bubble("bot", "Hi — I’m Lens, your claims assistant. Before we start, what’s your name?")]);
    setStep("name");
  }
  function reset() { setClaim({ object: "", text: "" }); setDraft(""); greet(); }

  function submitName() {
    const n = draft.trim(); setDraft("");
    if (n) { setName(n); push(bubble("user", n)); }
    push(bubble("bot", `Thanks${n ? ", " + n : ""}! What are you claiming for?`, { chips: OBJECTS }));
    setStep("object");
  }
  function skipName() {
    setDraft("");
    push(bubble("bot", "No problem. What are you claiming for?", { chips: OBJECTS }));
    setStep("object");
  }

  function pickObject(o) {
    setClaim((c) => ({ ...c, object: o })); push(bubble("user", o));
    push(bubble("bot", `Got it — a ${o}. What’s the issue? Pick the closest one.`, { issues: ISSUES[o] || [] }));
    setStep("issue");
  }
  function pickIssue(label, text, object) {
    setClaim((c) => ({ ...c, text })); push(bubble("user", label));
    push(bubble("bot", `Thanks. Now capture a live photo of the ${object} so I can check it against your claim.`, { capture: true }));
    setStep("capture");
  }
  function otherIssue() {
    push(bubble("user", "Something else")); push(bubble("bot", "Sure — in a sentence, what happened?")); setStep("describe");
  }
  function send() {
    const t = draft.trim(); if (!t) return; setDraft(""); push(bubble("user", t));
    setClaim((c) => ({ ...c, text: t }));
    push(bubble("bot", `Thanks. Now capture a live photo of the ${claim.object} so I can check it against your claim.`, { capture: true }));
    setStep("capture");
  }
  async function onCapture(dataUrl) {
    setCam(false); push(bubble("user", "", { image: dataUrl })); setBusy(true);
    try {
      const d = await reviewClaim(claim.object, claim.text, [dataUrl]);
      push(bubble("bot", d.assistant_message || "Here’s my decision.", { verdict: d }));
      push(bubble("bot", "Was this decision helpful?", { feedback: true }));
      setStep("feedback");
    } catch (e) {
      push(bubble("bot", "Sorry — I couldn’t reach the review service. Make sure the local server (python code/server.py) is running."));
    } finally { setBusy(false); }
  }
  function rate(up) {
    push(bubble("user", up ? "👍 Looks right" : "👎 I disagree"));
    if (up) { push(bubble("bot", "Great — thanks for confirming. You’re all set.")); setStep("done"); }
    else { push(bubble("bot", "Sorry to hear that. I can send this to our claims team for a human review — add a note if you’d like, or just tap send.")); setStep("escalate"); }
  }
  function escalate() {
    const note = draft.trim(); setDraft("");
    if (note) push(bubble("user", note));
    const ref = "CL-" + String(Date.now()).slice(-6);
    push(bubble("bot", `Thanks${name ? ", " + name : ""}. I’ve escalated this to our claims team for human review (ref ${ref}). They’ll get back to you within 48–72 hours.`));
    setStep("done");
  }
  function composerSubmit() {
    if (step === "name") return submitName();
    if (step === "describe") return send();
    if (step === "escalate") return escalate();
  }

  const typing = step === "name" || step === "describe" || step === "escalate";
  const placeholder = step === "name" ? "Your name…" : step === "escalate" ? "Add a note (optional)…" : "Describe what happened…";

  return html`
    <div class="msgr">
      ${open && html`
        <div class="panel">
          <div class="phead">
            <div class="pavatar"><${Icon} name="aperture" size=${20} /></div>
            <div><div class="pname">Lens</div><div class="pstatus"><span class="online"></span> Claims assistant · online</div></div>
            <button class="iconbtn light" onClick=${() => setOpen(false)} aria-label="Close"><${Icon} name="x" /></button>
          </div>
          <div class="pbody" ref=${body}>
            ${msgs.map((m) => html`<${Msg} key=${m.t} m=${m} step=${step} onChip=${pickObject} onCam=${() => setCam(true)}
              onIssue=${pickIssue} onOther=${otherIssue} onRate=${rate} object=${claim.object} />`)}
            ${busy && html`<div class="b bot"><div class="bav">L</div><div class="btext"><div class="typing"><span></span><span></span><span></span></div></div></div>`}
          </div>
          <div class="pcomposer">
            ${typing ? html`
              <input value=${draft} placeholder=${placeholder}
                onInput=${(e) => setDraft(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && composerSubmit()} />
              <button class="iconbtn accent" onClick=${composerSubmit} aria-label="Send"><${Icon} name="send" /></button>
              ${step === "name" ? html`<button class="btn ghost sm" onClick=${skipName}>Skip</button>` : null}` : null}
            ${step === "capture" ? html`<button class="btn accent block" onClick=${() => setCam(true)}><${Icon} name="camera" /> Open camera</button>` : null}
            ${step === "done" ? html`<button class="btn ghost block" onClick=${reset}><${Icon} name="refresh" /> Start another claim</button>` : null}
            ${step === "object" || step === "issue" || step === "feedback" ? html`<div class="hint">Pick an option above to continue.</div>` : null}
          </div>
        </div>`}
      <button class="launcher ${open ? "x-open" : ""}" onClick=${() => setOpen(!open)} aria-label=${open ? "Close chat" : "Open chat"}>
        <${Icon} name=${open ? "x" : "message"} size=${24} /></button>
      ${cam && html`<${CameraSheet} claimObject=${claim.object} onCapture=${onCapture} onClose=${() => setCam(false)} />`}
    </div>`;
}

function Msg({ m, step, onChip, onCam, onIssue, onOther, onRate, object }) {
  if (m.from === "user")
    return html`<div class="b user">${m.image ? html`<img class="bimg" src=${m.image} alt="your capture"/>` : m.text}</div>`;
  const objIcon = { car: "car", laptop: "laptop", package: "package" };
  return html`
    <div class="b bot">
      <div class="bav">L</div>
      <div class="btext">
        <span>${m.text}</span>
        ${m.extra.chips && step === "object" ? html`<div class="chips">${m.extra.chips.map(([o]) =>
          html`<button class="chip" key=${o} onClick=${() => onChip(o)}><${Icon} name=${objIcon[o]} size=${16} /> ${o}</button>`)}</div>` : null}
        ${m.extra.issues && step === "issue" ? html`<div class="chips">${m.extra.issues.map(([label, text]) =>
          html`<button class="chip" key=${label} onClick=${() => onIssue(label, text, object)}>${label}</button>`)}
          <button class="chip" onClick=${onOther}>Something else</button></div>` : null}
        ${m.extra.capture && step === "capture" ? html`<div class="chips"><button class="chip" onClick=${onCam}><${Icon} name="camera" size=${16} /> Open camera</button></div>` : null}
        ${m.extra.verdict ? html`<${Verdict} d=${m.extra.verdict} />` : null}
        ${m.extra.feedback && step === "feedback" ? html`<div class="chips">
          <button class="chip" onClick=${() => onRate(true)}>👍 Looks right</button>
          <button class="chip" onClick=${() => onRate(false)}>👎 I disagree</button></div>` : null}
      </div>
    </div>`;
}
