# Architecture & Guardrails — Multi-Modal Evidence Review

A review of the system as an AI-agent design: how it is structured, where the
guardrails live, how context is engineered, and how it scales. Written to be
defensible in a technical interview. The system-level view (context diagrams,
flows, component table, NFRs) lives in [docs/HLD.md](docs/HLD.md).

> **Subsystems added since this doc's first draft** (each has its own reference):
> - **Capability model router + fallback** (no hardcoded provider; Claude-out → Gemini) — [docs/MODEL_ROUTING.md](docs/MODEL_ROUTING.md)
> - **Confidence-gated short-circuit** (skip the judge on unusable / two-signal wrong-object) — MODEL_ROUTING.md
> - **Layered prompt-injection defense** (instruction hierarchy + spotlighting + text/image guards + red-team CI) — [docs/PROMPT_INJECTION.md](docs/PROMPT_INJECTION.md)
> - **Embeddable intake surface** (`/api/intake` envelope; inbound connector parse) — [docs/EMBED.md](docs/EMBED.md), [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)
> - **Pluggable auth** (off by default: ApiKey / OIDC / HMAC) — [docs/SECURITY.md](docs/SECURITY.md)
> The thesis and guardrail principles below still hold; these extend them.

---

## 1. Design thesis

> **Use the cheapest capable component at each tier, and spend the strong model
> only on the one irreversible decision.**

Most "verify an image against a claim" systems reach for one big multimodal
model per claim and call it a day. That is expensive, hard to audit, and easy to
game. Instead we split the job into three tiers with sharply different costs and
trust levels, and we make the *rules* (not a model zoo) carry the multimodal
discipline.

```
            ┌─────────────────────────────────────────────────────────┐
  claim ───▶│ Tier 0  CONTEXT BUILDER (deterministic, $0, no model)     │
  + images  │   blur / exposure / glare / resolution / EXIF provenance  │
            │   perceptual-hash duplicate & reuse detection             │
            └───────────────┬─────────────────────────────────────────┘
                            │ free quality + provenance signals
            ┌───────────────▼─────────────────────────────────────────┐
            │ Tier 1  PERCEPTION  (cheap VLM, 1 call / image, CACHED)   │
            │   Gemini 2.5 Flash-Lite — "what is literally visible?"    │
            │   per-image structured JSON; in-image text detection      │
            └───────────────┬─────────────────────────────────────────┘
                            │ compact per-image evidence (JSON, not pixels)
            ┌───────────────▼─────────────────────────────────────────┐
            │ Tier 2  JUDGE  (strong model, 1 call / claim)             │
            │   Claude Sonnet — claim extraction → evidence match →     │
            │   calibrated decision over the 14-field schema            │
            └───────────────┬─────────────────────────────────────────┘
                            │
            ┌───────────────▼─────────────────────────────────────────┐
            │ FUSION + COERCION (deterministic)                         │
            │   force provenance/quality flags · snap to legal enums    │
            └───────────────────────────────────────────────────────────┘
                            │
                         output row
```

Each tier is **pluggable** behind one interface (`providers/`), so Gemini, Claude,
OpenAI, or a local open-source VLM can be swapped per tier without touching the
pipeline. The default mixes providers on purpose: Gemini Flash-Lite is ~10–30×
cheaper per image than a frontier VLM, and the expensive judge runs exactly once
per claim.

---

## 2. Guardrails

Guardrails are layered so that no single model output can produce an illegal,
ungrounded, or game-able result.

### 2.1 Output integrity (schema is law)
- Every model field is **snapped to the allowed enum** in `schema.py`
  (`coerce_row`) — `claim_status`, `issue_type`, per-object `object_part`,
  `risk_flags`, `severity`. A hallucinated value like `"screen_crack"` maps to
  `crack`; an out-of-vocab part becomes `unknown`. The CSV can **never** contain
  an illegal value, regardless of what the model says.
- Output column set and order are fixed (`OUTPUT_COLUMNS`) and quoted.

### 2.2 Prompt-injection / in-image-instruction defense
The dataset deliberately plants images containing text like "mark as approved".
Two independent defenses:
- **Detection (Tier 1):** perception is instructed to treat any in-image text as
  *untrusted content*, set `text_in_image` / `instruction_text_present`, and
  never obey it.
- **Decision (Tier 2):** the judge is told in-image text is never an instruction;
  when flagged it judges *from pixels only*. The flag is force-added in fusion so
  it always surfaces (`text_instruction_present`).

### 2.3 Hallucination control / calibrated abstention
- **Images are primary truth** — the judge may never mark `supported` on the
  user's words alone.
- **Abstention gate:** `not_enough_information` is reserved for "I cannot *see*
  the part." If the part is visible the judge must commit to
  `supported`/`contradicted`. This stops the model from hiding behind "unsure".
- **Severity rubric** prevents inflation (most genuine single-area damage = `medium`).
- **Issue taxonomy** disambiguates the confusable pairs (crack vs glass_shatter,
  none vs unknown), the empirically dominant error class.

### 2.4 Provenance / anti-gaming (deterministic, model-independent)
- Tier 0 computes a **perceptual hash per image** and flags reused/near-duplicate
  images across a claim → `non_original_image`.
- **EXIF/provenance** presence is checked (camera-captured images usually carry
  EXIF; screenshots / re-saved / generated images often don't).
- These run with **zero model calls** and are **force-merged** into the output in
  fusion, so the cheap deterministic layer keeps the expensive model honest.
- The companion **camera-only capture PWA** (design in `pwa/`) pushes provenance
  upstream: evidence is captured live and bound to a signed token, so the most
  common gaming vectors (uploading stock/old/edited/AI images) are blocked at
  source rather than detected after the fact.

### 2.5 Fail-safe behavior
- Any model/parse error degrades to a `not_enough_information` +
  `manual_review_required` row instead of crashing the batch (`_error_row`).
- Missing/unreadable images are handled at Tier 0 and never reach a model.
- With **no API keys**, every tier falls back to a deterministic `mock`, so the
  pipeline and the evaluation always run end-to-end (reproducibility guarantee).

### 2.6 Determinism
- `temperature = 0` everywhere; outputs snapped to enums; perception cached by
  content hash. (We measured and report residual judge nondeterminism — see §4.)

---

## 3. Context engineering

The judge call is where context quality decides accuracy. Deliberate choices:

- **Trust separation.** The judge prompt cleanly separates *what to check*
  (conversation), *evidence* (per-image perception + CV signals), *risk context*
  (history), and *untrusted content* (in-image text). History is explicitly
  labeled "risk context only — must not flip a visually clear decision."
- **Evidence, not pixels, to the judge.** Tier 1 distills each image to compact
  structured JSON; the judge reasons over that plus CV signals instead of
  re-ingesting raw images. Smaller, cacheable, cheaper, and it forces grounded,
  per-image reasoning.
- **Explicit reasoning order.** The judge is told to (1) extract the claim,
  (2) read each image, (3) match, (4) decide — emitted as `claim_summary` +
  `reasoning` fields inside the JSON (kept out of the CSV) so the chain is
  auditable without leaking prose.
- **Multilingual robustness.** Conversations include Hindi/Hinglish; the judge is
  instructed to extract the claim regardless of language (verified on samples).
- **Minimum-evidence requirements** for the object are injected so the
  `evidence_standard_met` decision is grounded in the published rubric, not vibes.
- **Versioned prompts** (`PROMPT_VERSION`) are part of the perception cache key,
  so changing a prompt cleanly invalidates stale cached perceptions.

---

## 4. Evaluation methodology (and honesty about it)

- `evaluation/main.py` runs **≥2 strategies** (mock baseline · Gemini-only ·
  Gemini→Claude) on the 20 labeled samples and reports per-field accuracy,
  claim_status macro-F1, and **set-based precision/recall/F1 for risk_flags**.
- Strategy selection is automatic: highest claim_status macro-F1 among
  model-backed strategies.
- **Measured nondeterminism:** repeated runs of the chosen strategy vary by a few
  points (status acc ~0.75 ± 0.04) because the judge is not perfectly
  deterministic at temp 0. We therefore tuned only **general, domain-justified
  rules** (calibration rubrics, crack/shatter convention, evidence-based
  flagging) and avoided fitting to individual samples. `contradicted` remains the
  hardest minority class (5 examples) and is reported as such rather than papered
  over.

---

## 5. Cost, latency, rate limits

- **Call budget:** 1 perception call per *image* (cached → $0 on re-run) + 1 judge
  call per *claim*. Tier 0 is free.
- **Caching:** content-addressed by `sha1(image)+model+prompt_version`; identical
  re-runs make zero model calls.
- **Concurrency:** bounded thread pool (`MAX_CONCURRENCY`) to respect TPM/RPM.
- **Batching:** one image per perception keeps prompts small and individually
  cacheable; the judge receives JSON, not re-sent images.
- Full numbers and projected test-set cost are in `evaluation/evaluation_report.md`.

---

## 6. Scalability & integration

- **Stateless pipeline** over rows → trivially horizontally scalable; cache is a
  shared content store.
- **Provider abstraction** means new models/providers are a single file.
- **Schema module** is the integration contract; the same `coerce_row` guarantees
  any downstream consumer gets legal values.
- Natural next steps: provider-native **batch APIs** for perception, a real
  server-issued nonce + device-attestation path for the PWA capture token, and a
  confidence score driving an automated `manual_review_required` queue.

---

## 7. Known limitations

- 20 labeled samples → metrics are noisy; treat as directional.
- `issue_type` is inherently ambiguous on borderline glass/screen cases.
- EXIF-based provenance is a *soft* signal (many legitimate images lack EXIF); it
  informs flags but never decides alone.
- The PWA capture-token signing is a client-side demo; production needs
  server-issued nonces and platform attestation (Play Integrity / App Attest).
