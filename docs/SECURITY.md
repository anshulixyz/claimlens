# Security — Data Input

We don't host the system, but the inputs (CSV rows, image files, claim text,
capture tokens) are **untrusted**, and we apply standard input-security practices
so the pipeline is safe to point at real submissions.

## Threats & controls

| Threat | Control | Where |
|---|---|---|
| **Path traversal** via CSV `image_paths` (`../../etc/passwd`) | Paths are resolved inside `DATASET_DIR` and rejected if they escape; a violation becomes a `MISSING` image, never a file read. | `dataio.resolve_image` |
| **Decompression bomb** (tiny file, billions of pixels) | `Image.MAX_IMAGE_PIXELS` cap (50 MP) + byte cap (25 MB) + `Image.verify()` before decode. | `intake.py` |
| **Unsupported / malformed format** | Format allowlist (JPEG/PNG/WEBP/HEIF/BMP); decode failures → `UNREADABLE`, never a crash. | `intake.py` |
| **Prompt injection via text inside images** | In-image text is declared untrusted to the model; detected by perception + the `ocr_injection` tool; force-flagged `text_instruction_present`; the judge decides from pixels only. | `prompts.py`, `tools/ocr_injection.py` |
| **Prompt injection via the claim conversation** | The conversation is framed as data ("the user's claim to verify"), not instructions; the judge is told images are the source of truth and never to act on embedded directives. | `prompts.py` (judge system) |
| **Untrusted inbound conversation (external chat)** | Claim text arriving from external chat providers (Slack/WhatsApp/CRM webhooks) is scanned for instruction-injection / role-hijack / exfiltration phrasing; on a hit we force-flag `text_instruction_present` (the same flag the in-image guard raises). The text is kept verbatim — the judge decides from pixels and ignores embedded directives. | `harness/sanitize.py` |
| **Model output injection** (model emits illegal/oversized fields) | Every field snapped to allowed enums; `claim_status` fails **closed** to `not_enough_information` (never fuzzy-matches toward approval); text fields length-capped. | `schema.coerce_row`, `_snap(fuzzy=False)` |
| **Secret leakage** | Keys read from env / `code/.env` only; `.env` gitignored; never logged (redacted in the build transcript); error rows write a **generic** reason, not raw exceptions/paths. | `config.py`, `judge.py`, `.gitignore` |
| **Capture-token forgery / image swap** | Token binds `sha256(image)` + payload via HMAC; verifier re-hashes the bytes and re-checks the signature. **Note:** the demo key is client-side, so the token proves *integrity*, not *provenance*, until server-issued nonce + platform attestation (Play Integrity / App Attest) is added. | `capture_token.py`, `pwa/README.md` |
| **Unbounded cost / DoS via huge batches** | Bounded concurrency (`MAX_CONCURRENCY`); content-hash caching; inadmissible images skip model calls; per-claim failures isolated to one row. | `pipeline.py`, `cache.py`, `intake.py` |

## Authentication & authorization (pluggable)

Auth is a **pluggable layer, OFF by default**, so the grader / CI / local demo run
with zero configuration (`NoAuth` — every request is an anonymous principal). A host
that wants to *enable the chat for a given user / tenant* selects a provider and
applies it to the FastAPI `/api/*` routes. Providers live in
[`../evidence_review/harness/auth.py`](../evidence_review/harness/auth.py) and are
plain objects (`authenticate(headers) -> AuthContext`, raising `AuthError`), unit-
testable without a web framework.

| Provider | Selector (`CLAIMLENS_AUTH`) | How it authenticates | Per-user / per-tenant |
|---|---|---|---|
| `NoAuth` (default) | `none` | always allows; anonymous principal | n/a |
| `ApiKeyAuth` | `apikey` | `X-API-Key` header vs `CLAIMLENS_API_KEYS` (comma-separated; `key=tenant` maps a key to a tenant) | per-key → `AuthContext.tenant` |
| `HMACAuth` | `hmac` | `X-ClaimLens-Signature` HMAC over the **raw body** (`integrations.sign_body` + `hmac.compare_digest`); `CLAIMLENS_HMAC_SECRET` | per-call (`X-ClaimLens-Tenant`) |
| `OIDCAuth` | `oidc` | Bearer JWT — HS256 shared secret (`CLAIMLENS_OIDC_SECRET`) for the testable path, RS256 + JWKS (`CLAIMLENS_OIDC_JWKS`) for production; validates `aud`/`iss` (`CLAIMLENS_OIDC_AUDIENCE`/`_ISSUER`). PyJWT is an optional dep. | `sub`/`tenant`/`scope` from the token |

A host builds the provider with `auth_from_env()` and wires it with
`make_fastapi_dependency(provider)` (a FastAPI `Depends` callable that imports
FastAPI lazily, maps `AuthError → HTTP 401`, and yields the `AuthContext`). The
`AuthContext` (subject + tenant + scopes) is what a host keys per-user / per-tenant
chat enablement on. PyJWT and FastAPI are **optional** — `auth.py` imports cleanly
without either; the web framework is touched only inside the dependency callable,
and PyJWT only inside `OIDCAuth`.

> **OIDC production note.** `aud`/`iss` are only enforced when
> `CLAIMLENS_OIDC_AUDIENCE`/`CLAIMLENS_OIDC_ISSUER` are set. The HS256
> shared-secret path is a *testing convenience*: a shared symmetric secret means
> any holder can mint tokens, and with no `aud`/`iss` set a token is replayable
> across services sharing the secret. For production, set **both** `aud` and
> `iss` and use **RS256 + JWKS** (asymmetric) so verifiers never hold signing
> material. Treat HS256-without-aud/iss as non-production.

## PII / data handling
- The claim conversation and history may contain PII. We do not transmit it
  anywhere except the configured model providers, and only the minimum needed
  (distilled evidence, not raw images, to the judge).
- Traces (`code/.cache/traces/`) contain claim content — treat the cache dir as
  sensitive; it is gitignored.

## What we explicitly do NOT claim
- We are not a hosted service. Authn/z is now a **pluggable layer (off by
  default)** — see *Authentication & authorization* above — but TLS, rate-limiting,
  and the hosting itself still belong to the deployment. This document covers the
  **input safety** of the library plus the auth provider interface it ships.
- EXIF-based provenance is a *soft* signal (forgeable); only C2PA is
  cryptographically hard, and most real-world images have no C2PA manifest (it is
  stripped on upload by major platforms). See BENCHMARKING.md §Group B.
