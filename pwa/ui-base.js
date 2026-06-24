/* ClaimLens UI — shared base: React/htm globals, icons, brand SVG art, scroll FX.
 * Loaded FIRST; later classic scripts (ui-messenger, ui-landing, app) reuse these
 * top-level const bindings via the shared global lexical scope.
 *
 * ── light enterprise design language ─────────────────────────────────────────
 *  surface  clean near-white canvas with a faint indigo/emerald wash
 *  cards    white, hairline borders, soft shadows — the exhibit primitive
 *  palette  a confident indigo brand for actions; the verdict spectrum
 *           (emerald=accept, rose=decline, amber=needs-info) is reserved for state
 *  type     Plus Jakarta Sans (display) · Inter (body) · JetBrains Mono (labels)
 *  motion   reveal-on-scroll + dot-rail scroll-spy — reduced-motion aware
 */
const { useState, useRef, useEffect, useCallback } = React;
const createRoot = ReactDOM.createRoot;
const html = htm.bind(React.createElement);

/* ----------------------------- icons (inline Lucide-style SVG) ----------------------------- */
const ICONS = {
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  fileCheck: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="m9 15 2 2 4-4"/>',
  blocks: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  layers: '<path d="m12 2 9 5-9 5-9-5 9-5z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
  lock: '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  send: '<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>',
  car: '<path d="M19 17h2l-1.5-5.5a2 2 0 0 0-1.9-1.5H7.4a2 2 0 0 0-1.9 1.5L4 17h2"/><circle cx="7.5" cy="17" r="2"/><circle cx="16.5" cy="17" r="2"/>',
  laptop: '<rect x="3" y="5" width="18" height="11" rx="2"/><path d="M2 20h20"/>',
  package: '<path d="m7.5 4.3 9 5.2M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  aperture: '<circle cx="12" cy="12" r="10"/><path d="m14.3 16 3.7 0M9.7 8H6M12 2v5M12 22v-5"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/>',
  building: '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M16 6h.01M8 10h.01M16 10h.01M8 14h.01M16 14h.01"/>',
  cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
  plug: '<path d="M12 22v-5M9 8V2M15 8V2M6 12V8h12v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4z"/>',
  key: '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
  code: '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/>',
  headset: '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H4a1 1 0 0 1-1-1v-4a9 9 0 0 1 18 0v4a1 1 0 0 1-1 1h-2a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
};
function Icon({ name, size = 18, cls = "" }) {
  return html`<svg class="ic ${cls}" width=${size} height=${size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" dangerouslySetInnerHTML=${{ __html: ICONS[name] || "" }}></svg>`;
}

/* ----------------------------- brand SVG art (drawn for the light surface) ----------------------------- */
const FONT = "Plus Jakarta Sans, Inter, sans-serif";
const MONO = "JetBrains Mono, monospace";
const INK = "#0B0F19";
const MUT = "#777F8C";

/* the cascade rail: stages named by what they do (not by vendor) */
const FLOW_ART = `<svg viewBox="0 0 960 168" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="How a photo becomes a verdict: capture, forensics, perception, adjudication">
  ${[["photo", "captured live", "#15924E"], ["forensics", "free · deterministic", "#777F8C"], ["perception", "reads every image", "#2E6BE6"], ["adjudication", "weighs the claim", "#4F46E5"], ["verdict", "auditable", "#15924E"]]
    .map((s, i) => {
      const x = 8 + i * 192;
      const arrow = i < 4 ? `<path d="M${x + 164} 76 h26" stroke="#CBD0DB" stroke-width="2"/><path d="M${x + 184} 70 l7 6 -7 6" fill="none" stroke="#CBD0DB" stroke-width="2"/>` : "";
      return `<rect x="${x}" y="46" width="164" height="60" rx="14" fill="#FBFBFD" stroke="#E6E9EF"/>
        <circle cx="${x + 22}" cy="76" r="4.5" fill="${s[2]}"/>
        <text x="${x + 38}" y="72" font-family="${FONT}" font-size="15" font-weight="700" fill="${INK}">${s[0]}</text>
        <text x="${x + 38}" y="90" font-family="${MONO}" font-size="9.5" fill="${MUT}">${s[1]}</text>${arrow}`;
    }).join("")}
  <text x="480" y="142" text-anchor="middle" font-family="${MONO}" font-size="11" letter-spacing="0.03em" fill="${MUT}">cost-aware · model-agnostic · routed by capability, with automatic fallback</text>
</svg>`;

/* per-run decision ledger — what every verdict ships with */
const DETAIL_ART = `<svg viewBox="0 0 440 280" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Per-run decision detail ledger">
  <rect x="6" y="6" width="428" height="268" rx="18" fill="#FFFFFF" stroke="#E6E9EF"/>
  <rect x="6" y="6" width="428" height="44" rx="18" fill="#FAFBFD"/>
  <line x1="6" y1="50" x2="434" y2="50" stroke="#EFF1F6"/>
  <circle cx="34" cy="28" r="6" fill="#15924E"/><path d="M31 28l2.4 2.4 4-4.6" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <text x="50" y="32" font-family="${MONO}" font-size="10" letter-spacing="1.2" fill="${MUT}">DECISION DETAIL · PER RUN</text>
  <text x="372" y="32" font-family="${MONO}" font-size="9.5" fill="#15924E">conf 1.0</text>
  ${[["extracted claim", "dent · rear bumper", INK], ["evidence check", "img_1 · object present ✓", "#2E6BE6"], ["risk signals", "reuse · quality · in-image text, clear", "#15924E"], ["confidence", "1.0 · high", INK], ["model route", "cheapest qualified · auto-fallback", "#4F46E5"]]
    .map(([k, v, c], i) => {
      const y = 80 + i * 38;
      return `<text x="28" y="${y}" font-family="${MONO}" font-size="10" fill="${MUT}">${k}</text>
        <text x="186" y="${y}" font-family="${FONT}" font-size="12.5" font-weight="600" fill="${c}">${v}</text>
        <line x1="28" y1="${y + 13}" x2="412" y2="${y + 13}" stroke="#EFF1F6"/>`;
    }).join("")}
</svg>`;

/* ----------------------------- scroll FX (reveal + dot-rail spy) ----------------------------- */
/* React renders .reveal / .rail nodes, so wire the observers after mount. Both
 * are reduced-motion aware (the .reveal CSS resets transforms under the query). */
function setupScrollFx() {
  const io = new IntersectionObserver(
    (es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }),
    { threshold: 0.14 }
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

  const dots = {};
  document.querySelectorAll(".rail a").forEach((a) => { dots[a.dataset.s] = a; });
  const sio = new IntersectionObserver(
    (es) => es.forEach((e) => {
      const d = dots[e.target.id];
      if (!d || !e.isIntersecting) return;
      document.querySelectorAll(".rail a").forEach((x) => x.classList.remove("on"));
      d.classList.add("on");
    }),
    { rootMargin: "-30% 0px -55% 0px", threshold: 0 }
  );
  document.querySelectorAll("section[id]").forEach((s) => sio.observe(s));
  return () => { io.disconnect(); sio.disconnect(); };
}
