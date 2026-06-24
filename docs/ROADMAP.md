# ClaimLens — Roadmap & Open Items (WIP)

**Status: work in progress.** ClaimLens is an embeddable, multi-modal
claim-verification agent. The core (batch pipeline → `output.csv`, the tiered
harness, the live chat assistant, the embeddable intake surface, pluggable auth,
and the connector module) is built and tested; this file tracks what is *not* yet
done, categorized by product feature, so adopters know exactly where the edges
are. It is intentionally honest — see [CURRENT.md](../README.md) for the
"explicitly basic" list and [REVIEW.md](./REVIEW.md) for review findings.

**Priority legend:** `P0` blocker · `P1` important (do before "production") ·
`P2` nice-to-have · `P3` future / exploratory.

---

## ✅ Shipped in the current WIP cycle
- **Basic modularization**: split the 548-line `pwa/app.js` into feature files (`ui-base.js` assets/globals · `ui-messenger.js` · `ui-landing.js` · slim `app.js` entry); CI parses all four.
- **Python modularization**: `embed.py` → `embed/{envelope,images,service}.py` and `integrations.py` → `integrations/{events,connectors,registry}.py` (import-stable packages, public API unchanged); `server.py` presentation helpers → `server_helpers.py` (252→176 LOC). 63 tests green throughout.
- Embeddable **Claim Intake Envelope** (`{claims, evidence, protocols}`) + `POST /api/intake` — [EMBED.md](./EMBED.md)
- **Pluggable auth** (NoAuth default / ApiKey / OIDC / HMAC) + inbound prompt-injection sanitizer — [SECURITY.md](./SECURITY.md)
- **Connector manifest** + Zendesk inbound parse reference; UI integrations render from `GET /api/connectors` — [INTEGRATIONS.md](./INTEGRATIONS.md)
- Product-thesis landing (verticals · embed/open-API · trust)
- **Idempotency key** made stable across retries (claim identity + evidence, not wall-clock)
- Fixed P0: FastAPI auth-dependency annotation (routes were 422-ing) + HTTP-level regression tests

---

## 1 · Embeddable agent surface (intake)
| Pri | Item | Notes |
|---|---|---|
| **P2** | **Remote evidence fetch** — `url`-kind evidence in the envelope is not fetched (host must supply bytes); inbound tickets with URL attachments → `not_enough_information`. | Add an **opt-in, SSRF-safe** fetcher (host allowlist + size/type caps + timeout). Unblocks the Zendesk inbound verdict (see §3). |
| **P3** | Use the full `conversation` array (today only `user_claim` reaches the judge). | Multi-turn claim context. |
| **P3** | Async intake + callback for large/slow batches (job id → webhook on completion). | Server is currently synchronous per request. |

## 2 · Security & auth
| Pri | Item | Notes |
|---|---|---|
| **P1** | **OIDC production hardening** — enforce `aud`/`iss` by default and prefer **RS256 + JWKS**; HS256 shared-secret is a testing path only. | See the OIDC note in [SECURITY.md](./SECURITY.md). |
| **P2** | Rate limiting + request-size caps on `/api/*` (DoS guard). | Belongs partly to the deployment; ship a simple middleware option. |
| **P2** | Enforce per-tenant scoping *inside* the pipeline/trace (auth tenant now threads into intake; not yet used for data isolation). | |
| **P3** | **Capture-token provenance** — server-issued nonce + platform attestation (Play Integrity / App Attest) + C2PA. Currently integrity-only. | From CURRENT.md honesty list. |

## 3 · Integrations (the connector module)
| Pri | Item | Notes |
|---|---|---|
| **P1** | Wire **one real outbound adapter** end-to-end (e.g. Zendesk internal note via REST) behind a flag — all named outbound adapters currently report `not_implemented`. | Proves the round-trip; manifest already declares the mapping. |
| **P2** | Per-vendor **native inbound signature** schemes (e.g. `X-Zendesk-Webhook-Signature`) instead of the generic `X-ClaimLens-Signature`. | Per-connector `verify_inbound_signature` override. |
| **P2** | Zendesk inbound can't infer `claim_object` from a raw ticket → 422; add a triage classifier or map a ticket custom field. | |
| **P3** | Wire more connectors on demand: Salesforce/Agentforce (Pub/Sub), HubSpot, Guidewire, Freshdesk, Intercom/Fin, Decagon/Sierra. | Manifests exist; scaffolds documented. |

## 4 · UI / product thesis
| Pri | Item | Notes |
|---|---|---|
| **P2** | **Notifications** — replace the local Notification API with real Web Push (VAPID + push service + server). | From CURRENT.md honesty list. |
| **P2** | Richer integration catalog UI — render inbound/outbound + auth + status from the manifest (today: name + `live` pill). | Endpoint already exposes the full manifest. |
| **P3** | Per-vertical landing variants (insurance / e-commerce / CMS) + an embed-snippet generator. | |
| **P3** | Live ops dashboard: intake traffic + verdict distribution. | |

## 5 · Pipeline / accuracy / evaluation
| Pri | Item | Notes |
|---|---|---|
| **P1** | Expand the labeled eval set — currently **n=20** → metrics are directional; selection-on-test acknowledged. | See [EVALUATION.md](./EVALUATION.md). |
| **P2** | ELA forensics is a weak, off-by-default prior → learned forgery detector. | See [BENCHMARKING.md](./BENCHMARKING.md) §Group B. |
| **P3** | Confidence calibration + per-object-part accuracy targets. | |

## 6 · Observability / ops / reliability
| Pri | Item | Notes |
|---|---|---|
| **P2** | Dead-letter + retry/backoff for failed outbound webhook deliveries (delivery is at-least-once; no DLQ yet). | |
| **P2** | Structured request logging + per-tenant usage/cost metering on the server. | `usage.py` tracks per-run cost; not yet per-tenant. |
| **P3** | Hosted deployment topology: TLS, job queue, autoscale (today: localhost / single process). | From [HLD.md](./HLD.md) §9. |

## 7 · Developer docs & DX (integration + agent usage)
| Pri | Item | Notes |
|---|---|---|
| **P1** | **Integrator guide** — one end-to-end "connect ClaimLens to your stack" doc: auth setup (`CLAIMLENS_AUTH` + keys/secrets), `POST /api/intake`, `GET /api/connectors`, the inbound webhook flow, signed-webhook verification, and per-connector setup. Today this is split across [EMBED.md](./EMBED.md) / [INTEGRATIONS.md](./INTEGRATIONS.md) / [SECURITY.md](./SECURITY.md). | Single front door for adopters. |
| **P1** | **Agent usage guide** — how to embed/run the agent: the `{claims, evidence, protocols}` envelope reference, the stable response contract, risk-flag/verdict semantics, error cases (422/NEI), and **runnable client examples** (curl + Python + JS). | Reduce "how do I call it" friction. |
| **P2** | Publish the **OpenAPI/Swagger** spec — FastAPI already serves it at `/docs`; pin a versioned export + link it from the docs index. | Machine-readable contract. |
| **P3** | Versioning & compatibility policy for the intake envelope + `ClaimReviewResult` event (schema_version bumps, deprecation window). | |

## 8 · Engineering, codebase health & process
> Context: this started as a fast prototype to test the idea, so structure
> followed the build. Now hardening it into a maintainable product.

| Pri | Item | Notes |
|---|---|---|
| **P2** | **Remaining modularization** — `embed.py`, `integrations.py` (→ packages) and `server.py` helpers are now split (see Shipped). Left: break `server.py` routes into FastAPI `APIRouter` groups (kept as one file for now — it's demo-critical and only ~176 LOC). | Test-guarded by the server HTTP suite. |
| **P2** | **Adopt coding-guideline skills** from [mattpocock/skills](https://github.com/mattpocock/skills) — pull in the relevant coding-standard / best-practice skills to standardize contributions (style, structure, review checklists). | Establishes consistent engineering conventions as the codebase grows. |
| **P2** | **Coordinate further development with the Multi-Agent Loop Kit** ([anshulixyz/multi-agent-loop-kit](https://github.com/anshulixyz/multi-agent-loop-kit), our own OSS) — use its ownership map, task briefs, approval gates, and journals to run multi-agent work on this repo safely. | The structured multi-agent loop for scaling the build beyond a single session. |
| **P3** | Add type hints coverage + `mypy`/`pyright` gate; expand ruff rule set as the code stabilizes. | |

---

_Add new items under the matching feature with a priority. When an item ships,
move it to "Shipped" with a one-line note and update [CURRENT.md](../README.md)._
