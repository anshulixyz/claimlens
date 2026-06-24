# Senior Engineering Review — Findings & Resolutions

The system was put through an adversarial senior-AI-engineer review (architecture,
prompts, guardrails, eval rigor, correctness, cost, code quality). This records
the findings and what we did about them — kept as an honest audit trail.

## Review verdict (paraphrased)
> "The architecture is the strongest part — tiering, schema-as-law, deterministic
> fusion, and graceful degradation are senior-grade and well-documented. The
> exposure is in the long tail: a dangerous coercion shortcut, a racy usage
> counter, an over-claimed anti-gaming layer, and eval methodology that's honest
> in prose but still selects on the test set."

## Findings & resolution

| Sev | Finding | Resolution |
|---|---|---|
| **P0** | `schema._snap` char-substring fallback flipped meaning: `"unsupported"→supported`, `"indoor"→door`, `"transport"→port`. | **Fixed.** Rewrote to token-sequence matching (no char-substring), and `claim_status` now uses `fuzzy=False` → fails **closed** to `not_enough_information`. Regression-tested with the exact adversarial cases. |
| **P1** | Capture token signed with a client-side key → proves integrity, not provenance; risk of over-claiming. | **Acknowledged + bounded.** Token is framed as integrity-only in code/docs; no code consumes a *valid* token as positive authenticity. Production path (server nonce + platform attestation + C2PA) documented. |
| **P1** | `UsageTracker` did non-atomic `+=` across threads → racy cost numbers. | **Fixed.** Added a `threading.Lock` around `add`/`note_cache_hit`. `JsonCache` get/set race noted as benign (idempotent content). |
| **P1** | ELA ran uncached on every image with an undefended threshold; meaningless on PNG/recompressed. | **Fixed.** ELA is now **evidence-only** by default (asserts `possible_manipulation` only if `FORGERY_ASSERT=1`), runs on JPEG only, and is documented as a weak prior; learned detector is the roadmap upgrade. |
| **P1** | Eval selects the "best" strategy on the same 20 rows it scores → selection-on-test. | **Acknowledged.** EVALUATION.md states selection is directional given n=20, reports the variance band, and describes the k-fold/repeated-run path. Lead metric is macro-F1 + per-class confusion. |
| **P1** | `_fuse` computed escalation/confidence on pre-normalized flags → trace and row could disagree. | **Fixed.** Normalize the flag set once, then run escalation on that exact canonical set; one source of truth for the row. |
| **P2** | `escalation` had a dead `supported+integrity` branch. | **Fixed.** Removed. |
| **P2** | Perception cache key ignored the CV signals interpolated into the prompt. | **Fixed.** Cache key now includes a fingerprint of the prompt-affecting CV signals. |
| **P2** | `aigen` advertised a capability whose `run()` was a stub. | **Fixed.** `available()` returns False until inference is implemented; the integration contract is documented. |
| **P2** | `supporting_image_ids` backfill could cite a borderline/duplicate image. | **Fixed.** Backfill now requires `usable` + `small_side ≥ 256` + not in `duplicate_image_ids`. |
| **P2** | Judge error path wrote the raw exception into the CSV. | **Fixed.** Logs internally; CSV gets a generic "routed to manual review" reason. |

## Praised (kept as-is)
Tiering thesis & its implementation (one judge call/claim, content-hash perception
cache); schema-as-law (`coerce_row` + fixed `OUTPUT_COLUMNS`); deterministic
fusion keeping the model honest; thorough graceful degradation; real trust
separation in the judge prompt; honest framing of limitations.

## Round 2 — chat PWA + integrations review (findings & resolution)

| Sev | Finding | Resolution |
|---|---|---|
| **P0** | PWA claimed offline but loaded React/htm from esm.sh at runtime → white screen offline / on blocked wifi. | **Fixed.** Vendored React + ReactDOM + htm (UMD) into `pwa/vendor/`, loaded locally; service worker shell-caches them. Now boots with zero network. |
| **P1** | CDN single point of failure at boot. | **Fixed** by the same vendoring (no CDN at all). |
| **P0/P1** | Stale-closure in `review()` could drop a late capture; old "Review →" chips re-fired the verdict and double-logged history. | **Fixed.** `review()` reads latest evidence via a ref; `review/manualReview` guard `step==="capture"`; `Bubble` receives `step` and makes stale capture/review/chip actions inert. |
| **P2** | Camera-denied was a UX dead-end (no upload fallback by design). | **Fixed.** Added a "Can't use the camera? Request manual review" action → routes to `not_enough_information` + `manual_review_required`. |
| **P2** | `Notification.requestPermission()` on mount (anti-pattern). | **Fixed.** Now requested lazily on the first "Review my claim". |
| **P2** | `--muted` text (incl. the "Demo verdict" disclaimer) below WCAG AA. | **Fixed.** Darkened `--muted` to `#6b7693` (≥4.5:1). |
| **P2** | Manifest had SVG-only icons (Lighthouse/Android may reject). | **Fixed.** Added 192/512 PNG icons (+ maskable). |
| **P2** | `#video` CSS rule was dead (element used `ref`, no `id`); no `aria-label`. | **Fixed.** Added `id="video"` + `aria-label`. |
| OK | XSS via htm; localStorage; Python HMAC `compare_digest`; CI hermetic. | Confirmed clean — no change. |

## Interview preempts (things a judge will poke)
1. "`unsupported`→`supported`" — fixed; coercion now fails closed.
2. "Your token uses a key you gave the attacker" — it's integrity-only by design; provenance needs attestation (documented).
3. "You picked your config on the test set" — directional at n=20; here's the ±band and the k-fold plan.
4. "What does ELA catch, and why pay for it?" — demoted to evidence-only weak prior; learned detector is the upgrade (BENCHMARKING.md).
5. "Is the ThreadPool safe?" — per-row pure, indexed writes; shared `UsageTracker` now locked.
