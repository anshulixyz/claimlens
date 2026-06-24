/* ClaimLens UI, editorial landing on the light enterprise surface.
 * Sections (dot-railed): hero · problem · how · why-different · who-it's-for ·
 * embed/open-API · trust · proof · integrations · faq · cta.
 * Copy is grounded in the docs (HLD, MODEL_ROUTING, BENCHMARKING) and stays honest
 * about limits. Depends on ui-base.js (Icon, art, setupScrollFx). */

/* ============================== FAQ ============================== */
function Faq({ q, a }) {
  const [open, setOpen] = useState(false);
  return html`
    <div class="faq ${open ? "open" : ""}">
      <button class="faqq" aria-expanded=${open} onClick=${() => setOpen(!open)}>
        <span>${q}</span><${Icon} name="chevron" size=${18} cls=${open ? "rot" : ""} /></button>
      ${open ? html`<div class="faqa">${a}</div>` : null}
    </div>`;
}

/* ───────── content ───────── */

/* who it's for, one verticals grid */
const VERTICALS = [
  ["shield", "Insurance & FNOL", "Triage first-notice-of-loss photos the moment a motor or property claim opens, auto-clear the obvious, escalate the ambiguous, and cut loss-adjustment time.", "FNOL → decision → adjuster acts"],
  ["cart", "E-commerce returns", "Settle “arrived damaged” and “wrong item” on the evidence, not the description, before a refund or replacement ever ships.", "return → decision → refund / RMA"],
  ["laptop", "Device & warranty", "Confirm a cracked screen, dent or liquid mark before an RMA is approved, with a reason the customer can see.", "warranty → decision → approve / decline"],
  ["message", "Support chat", "Embed Lens in any messenger so the conversation itself captures and verifies the evidence inline, no email ping-pong.", "chat → decision → bot / agent replies"],
  ["headset", "Helpdesk at scale", "Run verification across Zendesk, Salesforce, HubSpot, Zoho Desk and Freshdesk queues, one signed decision event per ticket.", "ticket → decision → automation acts"],
];

/* why it's different, the wide positioning band */
const DIFF = [
  ["It adjudicates, it doesn’t just detect.", "The output is a claim decision: supported, contradicted or needs-info, with a reason grounded in the image. Not a bounding box or a label, an answer your team can act on and defend."],
  ["It abstains instead of guessing.", "When the relevant part isn’t visible, it returns needs-info and routes to a human. For a decision that moves money, a confident wrong answer is the expensive one."],
  ["It’s hard to game by construction.", "Live capture signed at the source, perceptual-hash reuse detection, an independent object check, and in-image-text / prompt-injection defence. The image is the source of truth, the words can’t talk it into “approved.”"],
];

/* illustrative provider-agnostic intake envelope (mirrors embed.intake_from_job) */
const ENVELOPE = `{
  "schema_version": "1.0",
  "claims": {
    "claim_object": "car",
    "user_claim": "rear bumper dented in a parking lot",
    "conversation": [ { "role": "user", "text": "it happened yesterday" } ]
  },
  "evidence": {
    "images":         [ { "kind": "data_url", "value": "data:image/jpeg;…" } ],
    "capture_tokens": [ "<signed capture token, integrity>" ]
  },
  "protocols": {
    "scenario_pack": "motor_fnol",
    "evidence_requirements": { "min_images": 1 }
  }
}`;

const TRUST = [
  ["camera", "Camera-first capture", "Evidence is captured live in the assistant, uploads are off, so a downloaded or recycled image can’t walk in the front door."],
  ["lock", "Signed at the source", "Each capture is bound to a hash of the image bytes with an HMAC token the server re-checks. Today that proves integrity; device attestation is the next step."],
  ["shield", "Prompt-injection defence", "The conversation and any text inside the image are treated as data, never instructions. An injected “approve this claim” is flagged, never obeyed."],
  ["key", "Auth you control", "API key, OAuth / OIDC or HMAC, pick a provider to gate the chat per user or tenant. Off by default, so the demo and tests run with zero config."],
];

const FAQS = [
  ["How is it hard to game?", "The image is the source of truth, not the customer’s words. Capture is live (no uploads) and signed at the source; we run perceptual-hash reuse detection, an independent object check, in-image-text / prompt-injection detection and forensic provenance. A photo that isn’t the claimed object is flagged and held, never auto-approved."],
  ["What models does it run?", "It’s model-agnostic. A capability router picks the cheapest model that qualifies for each step, a vision model for perception, a stronger reasoning model for the decision, and fails over automatically if one is unavailable. Free deterministic computer-vision does the first pass, so the expensive model runs once per claim. Bring your own, including a local open-source model."],
  ["Does it auto-approve or auto-decline?", "It returns a decision with a confidence band and routes low-confidence or flagged cases to a human. It assists adjudication, it doesn’t replace the reviewer."],
  ["How accurate is it?", "On the 20 labelled sample claims it reaches about 0.75 claim-status accuracy. That’s directional given the small set; the evaluation reports the full confusion matrix and per-field accuracy rather than one headline number."],
  ["What about data & privacy?", "Images go only to the model providers you configure, nothing else. It runs in your environment and reads API keys from environment variables; nothing is committed."],
  ["Is the chat the same as the batch system?", "Yes. The assistant calls the exact pipeline that scores the evaluation set and produces output.csv, there’s no separate demo path."],
  ["How do we integrate it?", "It emits a signed, versioned decision event (ClaimReviewResult). The generic webhook is live, Zapier, Make, n8n, any endpoint, and named adapters for Zendesk, Salesforce and Guidewire are documented and pluggable."],
];

/* Integrations, rendered from the backend connector manifest (GET /api/connectors)
 * so the UI stays in sync with the registry; falls back to a static list when
 * served without a backend. */
const INTEG_FALLBACK = ["Zendesk", "Salesforce / Agentforce", "HubSpot", "Zoho Desk",
  "Freshdesk", "Intercom / Fin", "Guidewire ClaimCenter", "Decagon", "Zapier · Make · n8n", "Any webhook"];

function Integrations() {
  const [items, setItems] = useState(null);
  useEffect(() => {
    let ok = true;
    fetch("/api/connectors")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (ok && d && Array.isArray(d.connectors) && d.connectors.length)
          setItems(d.connectors.map((c) => ({ name: c.target_system || c.name, live: c.status === "live" })));
      })
      .catch(() => {});
    return () => { ok = false; };
  }, []);
  const pills = items || INTEG_FALLBACK.map((n) => ({ name: n, live: false }));
  return html`
    <section class="sec integ" id="integ">
      <div class="eye mono reveal">integrations</div>
      <h2 class="reveal d1">Sends a <em>signed decision</em> into your stack.</h2>
      <p class="bsub reveal d2">ClaimLens emits a versioned, signed <span class="mono">ClaimReviewResult</span> event. The generic
        webhook is live; named adapters are documented and pluggable.${items ? html` <span class="dim">(live from the connector registry)</span>` : ""}</p>
      <div class="ilist reveal d2">
        ${pills.map((p) => html`<span class="ipill ${p.live ? "live" : ""}" key=${p.name}>
          <${Icon} name="blocks" size=${13} /> ${p.name}${p.live ? html` · <b>live</b>` : ""}</span>`)}
        <span class="ipill open" key="open"><${Icon} name="plug" size=${13} /> + open to integrations</span>
      </div>
    </section>`;
}

/* ============================== Landing ============================== */
function Landing() {
  const openLens = (e) => { e && e.preventDefault(); window.__openLens && window.__openLens(); };
  useEffect(() => {
    const raf = requestAnimationFrame(() => setupScrollFx());
    return () => cancelAnimationFrame(raf);
  }, []);

  return html`
    <div class="page">
      <nav class="nav">
        <div class="nav-in">
          <a href="#top" class="brand"><${Icon} name="aperture" size=${20} cls="logo" /> Claim<b>Lens</b><span class="dot"></span></a>
          <div class="navr">
            <a class="lnk" href="#problem">the problem</a>
            <a class="lnk" href="#how">how it works</a>
            <a class="lnk" href="#who">who it’s for</a>
            <a class="lnk" href="#trust">trust</a>
            <a class="lnk" href="#faq">faq</a>
            <a class="btn accent sm" href="#" onClick=${openLens}><${Icon} name="message" size=${15} /> Try Lens</a>
          </div>
        </div>
      </nav>

      <div class="rail" aria-hidden="true">
        ${["top", "problem", "how", "different", "who", "embed", "trust", "proof", "faq", "start"]
          .map((s) => html`<a href="#${s}" data-s=${s} key=${s}></a>`)}
      </div>

      <!-- 0 · HERO -->
      <header class="hero sec" id="top">
        <div class="hero-l">
          <div class="badge-line reveal"><span>multi-modal</span><span>camera-first</span><span><b>audit-ready</b></span></div>
          <h1 class="reveal d1">Decide damage claims on the <em>evidence</em>, in seconds.</h1>
          <p class="lead reveal d2">ClaimLens is a multi-modal review agent. It reads the photo, the claim conversation and the customer’s
            history, then returns an auditable <b>accept · decline · needs-info</b> decision, grounded in the pixels and routed
            into your support stack. It clears the clean claims instantly and surfaces the rest for a human.</p>
          <div class="hero-cta reveal d3">
            <a class="btn accent" href="#" onClick=${openLens}>See it review a live claim <${Icon} name="arrow" size=${16} /></a>
            <a class="btn ghost" href="#how">How it works</a>
          </div>
          <div class="cmd reveal d3">
            <span class="g mono">$</span> <code class="mono">python code/server.py</code>
            <span class="dim mono">runs the UI on the real review pipeline</span>
          </div>
        </div>
        <div class="hero-r reveal d2">
          <div class="exhibit verdict-ex">
            <div class="ex-head"><span class="ex-ic ok"><${Icon} name="check" size=${15} /></span>
              <b>Accepted</b><span class="ex-sev mono">medium</span></div>
            <div class="ex-grid">
              <div><span class="mono">issue</span><b>dent</b></div>
              <div><span class="mono">part</span><b>rear bumper</b></div>
            </div>
            <div class="ex-foot">grounded in img_1 · confidence 1.0</div>
          </div>
          <div class="exhibit thin">
            <div class="ex-line"><span class="ex-dot blue"></span><span class="mono">evidence</span> <b>object present · image clear</b></div>
            <div class="ex-line"><span class="ex-dot green"></span><span class="mono">risk checks</span> <b>no reuse · no tampering · no injected text</b></div>
          </div>
          <div class="exhibit thin warn-ex">
            <div class="ex-line"><span class="ex-dot coral"></span><span class="mono">wrong photo?</span> <b>flagged and held, never auto-approved</b></div>
          </div>
        </div>
      </header>

      <!-- stats band -->
      <section class="stats sec">
        <div class="stat reveal"><span class="n">Seconds</span><span class="l">a decision while the customer is still in chat<i>live & batch, one pipeline</i></span></div>
        <div class="stat reveal d1"><span class="n">1 call</span><span class="l">the reasoning model runs once per claim, free CV does the rest<i>cost-aware cascade</i></span></div>
        <div class="stat reveal d2"><span class="n">~0.75</span><span class="l">claim-status accuracy on the labelled sample set<i>directional · n=20 · full matrix in eval</i></span></div>
      </section>

      <!-- 1 · PROBLEM -->
      <section class="sec" id="problem">
        <div class="eye mono reveal">the problem · <b>it’s still done by eye</b></div>
        <h2 class="reveal d1">Photo claims still get <em>eyeballed</em> in a ticket queue.</h2>
        <p class="bsub reveal d2">A support agent opens an attachment, guesses whether it matches the story, and has no real defence
          against a recycled, edited or AI-generated image. Slow, inconsistent, and easy to game.</p>
        <div class="grid-3">
          ${[["search", "Manual, one at a time", "Every claim waits on a person to open, interpret and judge an image. Volume turns straight into backlog."],
             ["fileCheck", "Two reviewers, two answers", "Decisions drift between agents, and there’s no audit trail when a customer disputes the call."],
             ["shield", "Built to be gamed", "Stock, old, screenshotted, edited or AI-generated photos pass a queue that only eyeballs the pixels."]]
            .map(([ic, t, d], i) => html`<div class="card reveal d${i} pain" key=${t}>
              <span class="card-ic coral"><${Icon} name=${ic} size=${18} /></span><h3>${t}</h3><p>${d}</p></div>`)}
        </div>
      </section>

      <!-- 2 · HOW IT WORKS -->
      <section class="sec" id="how">
        <div class="eye mono reveal">how it works · <b>evidence in, decision out</b></div>
        <h2 class="reveal d1">A photo becomes a <em>defensible verdict</em>, in three stages.</h2>
        <div class="art flow reveal d2" dangerouslySetInnerHTML=${{ __html: FLOW_ART }}></div>
        <div class="grid-3 steps">
          ${[["01", "Capture & forensics", "A live photo (no uploads) is signed at capture, then free on-device checks read quality and EXIF, test for perceptual-hash reuse, and confirm the object, before a single model call."],
             ["02", "Perception", "A vision model reads every image and reports what’s actually there, object, part, damage, image quality, one image at a time, cached so re-runs are nearly free."],
             ["03", "Adjudication", "A reasoning model weighs that evidence against the claim, the history and your rules, abstains when it can’t see enough, and returns the decision with a grounded reason."]]
            .map(([n, t, d]) => html`<div class="card reveal step" key=${n}><div class="sn mono">${n}</div><h3>${t}</h3><p>${d}</p></div>`)}
        </div>
      </section>

      <!-- 3 · WHY IT'S DIFFERENT -->
      <section class="sec why" id="different">
        <div class="eye mono reveal">why it’s different · <b>not an image classifier</b></div>
        <h2 class="reveal d1">Three things off-the-shelf detection <em>doesn’t do.</em></h2>
        <div class="whypanel reveal d2">
          ${DIFF.map(([t, d], i) => html`<div class="whycol" key=${i}>
            <div class="wn mono">0${i + 1}</div><h3>${t}</h3><p>${d}</p></div>`)}
        </div>
      </section>

      <!-- 4 · WHO IT'S FOR -->
      <section class="sec" id="who">
        <div class="eye mono reveal">who it’s for · <b>one decision, many front doors</b></div>
        <h2 class="reveal d1">An evidence agent that <em>drops into how you already work.</em></h2>
        <p class="bsub reveal d2">ClaimLens isn’t one app. It’s an embeddable, multi-modal review agent for insurance, e-commerce, device
          warranty, support chat and high-volume helpdesks, one decision contract behind every channel.</p>
        <div class="grid-3 verticals">
          ${VERTICALS.map(([ic, t, d, flow], i) => html`<div class="card reveal vcard" key=${i}>
            <span class="card-ic"><${Icon} name=${ic} size=${18} /></span>
            <h3>${t}</h3><p>${d}</p>
            <div class="vflow"><${Icon} name="arrow" size=${12} /> ${flow}</div></div>`)}
        </div>
      </section>

      <!-- 5 · EMBED / OPEN API -->
      <section class="sec" id="embed">
        <div class="eye mono reveal">embed · open api · <b>one envelope in</b></div>
        <h2 class="reveal d1">One contract in. One <em>signed decision</em> out.</h2>
        <p class="bsub reveal d2">Drop ClaimLens behind any channel. It takes a single versioned intake envelope 
          <b>claims</b> (the conversation), <b>evidence</b> (images + capture token) and <b>protocols</b> (which rules to apply) 
          and returns the same auditable decision your batch pipeline produces.</p>
        <div class="embed-grid">
          <div class="envwrap reveal d1">
            <div class="envhead mono"><span class="g">●</span> POST /api/intake · ClaimLens intake envelope</div>
            <pre class="env mono">${ENVELOPE}</pre>
          </div>
          <div class="embed-notes reveal d2">
            ${[["plug", "Works with what you run", "A signed generic webhook and a programmatic intake API are live today, so it connects through Zapier, Make, n8n or any endpoint, no custom glue."],
               ["blocks", "No lock-in", "Named adapters (Zendesk, Salesforce, Guidewire…) sit on the same envelope, one small adapter per vendor, no change to the core."],
               ["fileCheck", "Honest by design", "The envelope and webhook are real and tested; named adapters are documented scaffolds you switch on when you need them."]]
              .map(([ic, t, d], i) => html`<div class="enote" key=${i}>
                <span class="card-ic sm"><${Icon} name=${ic} size=${15} /></span>
                <div><b>${t}</b><p>${d}</p></div></div>`)}
          </div>
        </div>
      </section>

      <!-- 6 · TRUST -->
      <section class="sec" id="trust">
        <div class="eye mono reveal">trust & security · <b>verify, don’t take our word</b></div>
        <h2 class="reveal d1">Hard to game, and <em>auditable</em> by default.</h2>
        <p class="bsub reveal d2">Evidence integrity, prompt-injection defence and a pluggable auth layer, so a host can turn on
          the chat per user or per tenant.</p>
        <div class="grid-2">
          ${TRUST.map(([ic, t, d], i) => html`<div class="card reveal trust-c" key=${i}>
            <span class="card-ic"><${Icon} name=${ic} size=${18} /></span>
            <h3>${t}</h3><p>${d}</p></div>`)}
        </div>
      </section>

      <!-- 7 · PROOF -->
      <section class="sec" id="proof">
        <div class="eye mono reveal">what you get back · <b>every claim</b></div>
        <h2 class="reveal d1">An <em>auditable decision</em>, never a black box.</h2>
        <div class="proof-grid">
          <div class="plist reveal d1">
            ${["A decision: supported, contradicted, or needs-info",
               "Issue type, object part and a severity estimate",
               "Risk flags, reuse, mismatch, wrong object, in-image text, history",
               "The exact image IDs behind the call, with a confidence band",
               "A short reason grounded in the pixels, plus a full per-run trace"]
              .map((t, i) => html`<div class="pitem" key=${i}><span class="pcheck"><${Icon} name="check" size=${13} /></span> ${t}</div>`)}
          </div>
          <div class="art detail-art reveal d2" dangerouslySetInnerHTML=${{ __html: DETAIL_ART }}></div>
        </div>
      </section>

      <${Integrations} />

      <!-- 8 · FAQ -->
      <section class="sec faqs" id="faq">
        <div class="eye mono reveal">faq · <b>the honest answers</b></div>
        <h2 class="reveal d1">Questions, <em>answered.</em></h2>
        <div class="reveal d2">${FAQS.map(([q, a], i) => html`<${Faq} key=${i} q=${q} a=${a} />`)}</div>
      </section>

      <!-- 9 · FINAL CTA -->
      <section class="sec endcta" id="start">
        <div class="endcta-in reveal">
          <h2>See it <em>decide a live claim.</em></h2>
          <p class="bsub">Open the assistant, capture a photo, and watch it reach a verdict in seconds, with the full reasoning one click away.</p>
          <a class="btn accent lg" href="#" onClick=${openLens}><${Icon} name="message" size=${17} /> Try the live assistant</a>
        </div>
      </section>

      <footer class="foot">
        <div class="foot-in">
          <span class="brand"><${Icon} name="aperture" size=${18} cls="logo" /> Claim<b>Lens</b></span>
          <span class="mono">multi-modal evidence review · chat with Lens, bottom-right →</span>
        </div>
      </footer>
    </div>`;
}
