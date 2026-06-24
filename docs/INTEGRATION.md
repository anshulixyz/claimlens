# Integration — Open Ends

The system is designed so another system can **impose its own rules and plug into
ours** without forking. Every layer is an explicit extension point with a typed
contract. Nothing here requires editing core files.

## The five extension points

### 1. Public entry — review claims programmatically
```python
from evidence_review import Pipeline, Config

pipe = Pipeline(Config())                 # or inject custom components (below)
rows = [{"user_id": "u1", "image_paths": "images/test/c1/img_1.jpg",
         "user_claim": "dent on rear bumper", "claim_object": "car"}]
results = pipe.process_rows(rows)          # -> list of schema-conformant dict rows
```
The output contract is fixed and validated (`schema.OUTPUT_COLUMNS` + `coerce_row`),
so any consumer gets legal, ordered fields regardless of model behavior.

### 2. Inject a custom tool registry (your own detectors / rules)
```python
from evidence_review.tools import default_registry
from evidence_review.harness.tool import Tool, ToolResult

class MyRule(Tool):
    name = "my_rule"; tier = "consistency"; produces_flags = ("claim_mismatch",)
    def run(self, ctx):
        ...
        return ToolResult(name=self.name, risk_flags=[...], evidence={...}, note="...")

reg = default_registry().register(MyRule())
pipe = Pipeline(Config(), registry=reg)     # injected — no core change
```
Tool-asserted risk flags are deterministically unioned into the decision (fusion),
so your rule cannot be silently dropped by the model. See [TOOLS.md](./TOOLS.md).

### 3. Inject a custom escalation / autonomy policy
```python
from evidence_review.harness.escalation import EscalationPolicy
class StrictPolicy(EscalationPolicy):
    def decide(self, status, risk_flags, history):
        d = super().decide(status, risk_flags, history)
        if status == "supported" and history and int(history.get("rejected_claim",0)) > 0:
            d["flags_to_add"].add("manual_review_required")
        return d
pipe = Pipeline(Config(), escalation=StrictPolicy())
```
This is the autonomy slider (P4): tune what auto-passes vs routes to a human.

### 4. Declarative scenario packs (behavior as data)
Drop a YAML in `evidence_review/scenario_packs/` to add an object type, issue
family, evidence requirement, decision hint, or restrict which tools run. No code
change. See [SCENARIOS.md](./SCENARIOS.md).

### 5. Image-admissibility checks (intake rules)
Register a custom intake rule (format policy, NSFW gate, regulatory rule) — see
[IMAGE_PROTOCOL.md](./IMAGE_PROTOCOL.md):
```python
from evidence_review.intake import register_check, Status
register_check(lambda path, raw, cv: (Status.BLOCKED, "policy") if banned(path) else None)
```

## Provider abstraction
Perception and judge are pluggable per tier (`gemini | claude | openai | mock`,
or a local OSS VLM) via `providers/` — set in `code/.env` or `Config(...)`. A new
backend is one file implementing `complete_json(system, parts, model, ...)`.

## Capture / provenance interop
The capture-token format (`capture_token.py`) is documented and language-neutral
(canonical JSON + HMAC; round-trip verified JS⇄Python). An external capture app
that emits the same token format integrates with the `provenance` tool directly.
Production path: server-issued nonce + platform attestation + C2PA (see
[../pwa/README.md](../pwa/README.md), BENCHMARKING.md).

## Stable contracts (what integrators can rely on)
- **Output schema** — `schema.OUTPUT_COLUMNS` (order) + allowed-value enums.
- **ToolResult** — `{name, available, signals, risk_flags, evidence, note, error}`.
- **Admissibility** — `{image_id, status, valid_image, send_to_model, risk_flags, reason}`.
- **Trace** — per-claim JSON (`harness/trace.py`) for downstream audit/eval ingestion.
