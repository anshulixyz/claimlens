# Embed ClaimLens in any chat / host system

ClaimLens is designed to be **embeddable**: any chat provider, workflow engine,
or upstream agent can hand it a single, versioned **Claim Intake Envelope** —
`{claims, evidence, protocols, metadata}` — and get back the exact same 14-field
verdict the batch path produces, plus a normalized event other systems consume.

This is the **inbound, provider-agnostic** surface. It carries no vendor fields,
so it works the same whether the caller is Intercom, a custom messenger, n8n, or
another LLM agent. (The **outbound** side — pushing verdicts into Zendesk /
Salesforce / a webhook — lives in [INTEGRATION.md](./INTEGRATION.md).)

Module: `code/evidence_review/embed.py` · Schema version: `INTAKE_SCHEMA_VERSION = "1.0"`.

## The envelope

| Section | Field | Notes |
|---|---|---|
| `claims` | `claim_object` | **required**, one of `car` \| `laptop` \| `package` |
| `claims` | `user_claim` | **required**, the natural-language claim |
| `claims` | `conversation` | optional `[{role, text}, …]` (passthrough) |
| `evidence` | `images` | list; each item is a base64 **data URL**, a **dataset-relative path**, or `{"kind","value"}` with kind `data_url`\|`path`\|`url` |
| `evidence` | `capture_tokens` | optional provenance tokens (passthrough) |
| `protocols` | `evidence_requirements` / `scenario_pack` / `escalation` | optional host hints (passthrough; not authoritative) |
| `metadata` | `claim_id` / `tenant` / `source` / `user_id` | identifiers for the verdict + downstream event |

## Example (~20 lines)

```python
from evidence_review import Config, Pipeline
from evidence_review.embed import handle_intake

pipeline = Pipeline(Config())  # real models if keys present; mock fallback otherwise

payload = {
    "claims": {
        "claim_object": "car",
        "user_claim": "There is a dent on the rear bumper.",
    },
    "evidence": {
        "images": ["data:image/jpeg;base64,<...>"],  # data URL, path, or {kind,value}
    },
    "metadata": {"claim_id": "CASE-42", "user_id": "u1", "source": "intercom"},
}

resp = handle_intake(payload, pipeline, reviewed_at="2026-06-19T12:00:00Z")
print(resp["claim_status"])              # supported | contradicted | not_enough_information
print(resp["claim_review_result"])       # normalized event for downstream systems
```

Connectors that already have a flat "claim job" can map it with
`intake_from_job(job)` (claim_id, user_claim, claim_object, image refs, user_id, …)
to produce the envelope dict, then call `handle_intake`.

## Response contract (stable)

`handle_intake` returns the full 14-field decision (the same fields as
`schema.OUTPUT_COLUMNS`, minus the input columns) **plus**:

| Key | Meaning |
|---|---|
| `claim_review_result` | normalized `ClaimReviewResult` payload (carries its own `schema_version`) for outbound connectors |
| `intake_risk_flags` | flags raised by the inbound text sanitizer (e.g. prompt-injection in `user_claim`) |
| `image_notes` | per-image materialization notes (skips, traversal rejections, url skips) |
| `intake_schema_version` | `"1.0"` |

If no usable image is present (empty list, all-garbage, or only `url`-kind items),
`handle_intake` does **not** crash — it returns a `not_enough_information`
decision with `manual_review_required` and an `assistant_message`, mirroring the
chat server's empty-images branch.

## JSON Schema

`embed.INTAKE_SCHEMA` is a plain dict (no external deps) describing the envelope,
usable for docs or lightweight validation. `ClaimIntake.from_payload(payload)` is
the authoritative validator: it raises `ValueError` with a clear message on a
missing/invalid `claim_object` (must be `car`\|`laptop`\|`package`), a missing
`user_claim`, or malformed sections.

## Honesty notes

- **`url`-kind evidence is NOT fetched** in this reference. Fetching arbitrary
  remote URLs is a security and egress concern that belongs to the **host**:
  the host should fetch, validate, and resubmit the bytes as a `data_url`. A
  skipped `url` item is recorded in `image_notes` (never silently dropped).
- **Path-traversal guard preserved**: dataset-relative `path` items are resolved
  through `dataio.resolve_image`, so a malicious `../../etc/passwd` is rejected
  exactly as on the batch path.
- **`protocols` is passthrough** today (recorded, not authoritative). Authoritative
  per-tenant rules are configured via scenario packs / injected registries /
  escalation policy — see [INTEGRATION.md](./INTEGRATION.md).

## HTTP endpoint

The parent wires this behind **`POST /api/intake`** on `code/server.py`: the
endpoint decodes the JSON body, calls `handle_intake(body, pipeline, reviewed_at=…)`,
and returns the response dict. `/api/intake` sits behind the pluggable auth layer
(`NoAuth` by default; API key / OAuth-OIDC / HMAC) — see the "Authentication &
authorization" section of [SECURITY.md](./SECURITY.md). The request body is exactly
the envelope described above.
