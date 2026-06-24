# Image Admissibility Protocol

A single, documented contract for **what the system does with every image before
it spends a model call**. Implemented in `evidence_review/intake.py`; runs as the
first per-image stage in the pipeline.

## Why
Real submissions include images we shouldn't or can't review: unsupported
formats, unreadable/truncated files, oversized (decompression-bomb) payloads,
too-low-quality ("cheap") shots, and safety-blocked / censored content. Without a
protocol these either crash, waste model spend, or silently produce garbage. The
protocol makes the behavior **predictable, cheap, and safe**.

## Statuses & responses

| Status | Meaning | valid_image | sent to model? | risk flags |
|---|---|---|---|---|
| `ok` | usable for automated review | true | yes | — |
| `too_low_quality` | tiny / severely blurred ("cheap") | true | yes (best-effort) | `blurry_image` |
| `missing` | file not found | false | no | `damage_not_visible` |
| `unreadable` | cannot decode / truncated | false | no | `damage_not_visible` |
| `unsupported_format` | not in the format allowlist | false | no | `manual_review_required` |
| `oversized` | exceeds byte/pixel caps (DoS / bomb) | false | no | `manual_review_required` |
| `blocked` | safety-filtered / censored downstream | false | no | `manual_review_required` |

Only `ok` and `too_low_quality` are sent to the perception model; everything else
**skips the paid call** and is handled deterministically. The image's status is
also surfaced to the judge (as its per-image note) and its risk flags are unioned
into the final decision via fusion.

## Security limits (tunable per deployment)
- Format allowlist: JPEG, PNG, WEBP, HEIF/HEIC, BMP.
- Max bytes: 25 MB. Max pixels: 50 MP (`Image.MAX_IMAGE_PIXELS` guard against
  decompression bombs). Min usable side: 64 px.
- Decoding uses `Image.verify()` to detect truncation/bombs without a full decode.

## "Censored" / safety-blocked images
When a downstream model or moderation layer refuses an image, register a check
that returns `Status.BLOCKED`. The protocol then marks it `valid_image=false`,
routes the claim to `manual_review_required`, and never treats the refusal as
evidence for or against the claim. (Model-side safety refusals are caught in the
perception/judge error paths and degrade to manual review — fail safe, P12.)

## Extensibility (open end)
The protocol is a **registry of checks**. Any integrating system adds its own
rule without editing the module:

```python
from evidence_review.intake import register_check, Status

def block_nsfw(path, raw, cv):
    if my_nsfw_model(path) > 0.9:
        return Status.BLOCKED, "nsfw"
    return None

register_check(block_nsfw)
```
The first check to return a non-OK status decides; otherwise the image is `ok`.
See [INTEGRATION.md](./INTEGRATION.md) for all extension points.
