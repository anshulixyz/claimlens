# ClaimLens PWA — chat-first claim capture & review

A Progressive Web App where a user files a damage claim in a **conversation** with
a bot ("Lens"): pick the object → describe what happened → **capture evidence live
on camera** → get an **accept / decline / needs-info** verdict. Evidence can only
come from the live camera (no upload path), and each capture is bound to a
tamper-evident, cryptographically signed **capture token**.

Built with **React + htm, vendored locally** (`vendor/`) — no build step and no
CDN, so it boots offline / on locked-down networks.

## Why chat + camera-only
- **Chat UX** matches how people expect to interact (Zomato/Uber-style), keeps a
  **history** of claims (localStorage), and lets the bot guide capture and explain
  the decision in plain language.
- **Camera-only** kills the cheapest gaming vectors — uploading old/stock/edited/
  AI-generated/screenshot images — because there is no `<input type="file">`
  anywhere. Each frame is hashed + signed at capture.

## The capture token
```jsonc
{ "payload": { "v":1, "capture_id":"…", "image_id":"img_1", "claim_object":"car",
    "captured_at":"<ISO>", "nonce":"<random>", "device":{…},
    "image_sha256":"<sha256 of JPEG bytes>", "capture_source":"live_camera", "width":…, "height":… },
  "alg":"HMAC-SHA256", "sig":"HMAC-SHA256(canonical(payload), key)" }
```
`image_sha256` binds the exact bytes; `sig` binds the payload. The backend verifier
`evidence_review/capture_token.py` re-hashes the bytes and re-checks the signature
using the **same canonical JSON** as `app.js` (verified end-to-end JS⇄Python,
including tamper rejection — see `tests/test_capture_token.py`).

## Honest limitations (these are basic; production needs more)
- **The accept/decline verdict is a client-side DEMO** mirroring the real pipeline
  schema (labelled in the UI). Wiring it to the real Python pipeline needs a small
  hosted endpoint.
- **Notifications** use the local Notification API when the tab is hidden — real
  delivery needs Web Push (VAPID + push service + server).
- **The capture token is integrity-only**: the demo HMAC key is client-side, so it
  proves the bytes/payload weren't altered, **not** that they're authentic.
  Production hardens this without changing the format: server-issued one-time
  `nonce` + platform attestation (Play Integrity / App Attest / WebAuthn), and
  optionally **C2PA** Content Credentials.
- **Integrations** in the panel are illustrative; only a generic signed webhook is
  live in `integrations.py` (named adapters are scaffolds).

## Run it
```bash
cd code/pwa && python3 -m http.server 8000      # open http://localhost:8000
```
Camera + service worker need a secure context (localhost or HTTPS). On a phone,
serve over HTTPS and "Add to Home Screen". Works offline after first load (the
service worker caches the shell + vendored React).

## Files
| File | Purpose |
|---|---|
| `index.html` | shell; loads vendored React + the app |
| `app.js` | chat flow, camera capture, SHA-256 + HMAC token, simulated verdict, integrations |
| `styles.css` | ClaimLens brand theme (chat, verdict cards, integrations) |
| `sw.js` | offline app-shell + vendor cache |
| `vendor/` | React, ReactDOM, htm (UMD, local — no CDN) |
| `manifest.json`, `icon*.png/svg` | installable PWA metadata |
| `serve.py` | tiny static server for local preview |
