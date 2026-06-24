# Guardrails

Layered controls so that no single model output can produce an illegal,
ungrounded, or game-able result. Each layer is independent (defense in depth, P8).

## 1. Output integrity — schema is law (`schema.py`)
- Every model field is **snapped to the allowed enum** (`coerce_row`). A
  hallucinated `issue_type` becomes `unknown`; an out-of-vocab `object_part`
  becomes `unknown`; statuses/severities/flags are normalized. The CSV can
  **never** contain an illegal value.
- Column set + order are fixed (`OUTPUT_COLUMNS`), output is fully quoted.
- Risk flags are de-duplicated and default to `none`.

## 2. Prompt-injection / in-image-instruction defense
- **Detect (perception):** in-image text → `text_in_image` / `instruction_text_present`.
- **Detect (independent):** `ocr_injection` tool re-scans with EasyOCR/Tesseract
  for instruction-like phrases (model-free cross-check).
- **Decide (judge):** in-image text is declared untrusted; the judge weighs pixels only.
- **Force-surface (fusion):** `text_instruction_present` is unioned in deterministically.

## 3. Calibrated abstention / hallucination control (`prompts.py`)
- Images are primary truth; never `supported` on the user's words alone.
- **Abstention gate:** `not_enough_information` is reserved for "can't *see* the part."
  If the part is visible, the judge must commit (supported/contradicted).
- Severity rubric prevents inflation; issue taxonomy disambiguates crack vs glass_shatter.

## 4. Provenance & forensics (deterministic, model-independent)
- `provenance`: perceptual-hash reuse → `non_original_image`; EXIF presence (soft);
  C2PA cryptographic credentials (hard) when available.
- `forgery`: Error Level Analysis → `possible_manipulation` (conservative threshold).
- `object_consistency` (adapter): CLIP zero-shot → `wrong_object` independent of the VLM.

## 5. Human-in-the-loop escalation (`harness/escalation.py`, P4)
- Deterministic policy routes to `manual_review_required` when: any integrity
  flag is present (manipulation / non-original / wrong-object / mismatch /
  in-image-instruction), or the system abstains (`not_enough_information`).
- Emits a **confidence band** (high/medium/low) for transparency.
- It adds the escalation flag and confidence; it does **not** silently override
  the judge's visual decision — the autonomy boundary stays explicit.

## 6. Fail-safe & degradation (`pipeline.py`, `config.py`)
- Any model/parse/tool error → a valid `not_enough_information` +
  `manual_review_required` row; the batch never crashes.
- Missing/unreadable images handled at Tier 0; never reach a model.
- No API key → deterministic `mock` tier; missing optional dep → tool self-disables.
- The system always emits a schema-conformant row.

## 7. Determinism & secrets
- `temperature = 0`; content-hash perception cache; enum coercion.
- Secrets read from env / `code/.env` only; `.env` is gitignored and never logged
  (redacted in the build transcript).

## Risk-flag → guardrail map
| risk flag | produced by |
|---|---|
| `blurry_image`, `low_light_or_glare`, `cropped_or_obstructed` | `quality` (CV) |
| `non_original_image` | `provenance` (dup/EXIF/C2PA), `aigen` (adapter) |
| `possible_manipulation` | `forgery` (ELA), `aigen` (adapter) |
| `text_instruction_present` | perception + `ocr_injection` |
| `wrong_object` | `object_consistency` (adapter), judge |
| `wrong_object_part`, `claim_mismatch`, `damage_not_visible`, `wrong_angle` | judge (visual) |
| `user_history_risk` | fusion (history flags) + judge |
| `manual_review_required` | escalation policy |
