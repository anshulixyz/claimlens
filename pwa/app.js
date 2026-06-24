/* ClaimLens UI — app entry: compose Landing + Messenger, register the service
 * worker, mount. Loaded LAST; depends on ui-base.js, ui-messenger.js, ui-landing.js. */
function App() { return html`<${React.Fragment}><${Landing} /><${Messenger} /></${React.Fragment}>`; }

if ("serviceWorker" in navigator)
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));

const rootEl = document.getElementById("root");
rootEl.classList.remove("booting"); // drop the loading shell (mono font + grid centering)
createRoot(rootEl).render(html`<${App} />`);
