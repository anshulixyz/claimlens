# Harness Principles — Building an Extensible Agentic Workflow

How this system is engineered as an **agent harness**, not a script with an LLM
in the middle. The framing follows the modern "LLM-as-OS / Software 3.0" outlook
(Karpathy): the model is a fallible CPU; the *harness is the operating system*
around it — memory, tools, scheduler, filesystem, and a verification/permission
layer. We build the OS; we don't dump the whole job on the model.

These principles are the contract every module in this repo is held to.

---

## P1 — LLM as the kernel, not the program
The model is one component: a powerful but unreliable reasoning unit. The harness
provides everything around it:
- **Context window = RAM** → assembled deliberately (P2).
- **Tools = syscalls** → typed capabilities behind a registry (P5).
- **Control flow = scheduler** → deterministic orchestration, not model-driven loops where we can avoid it.
- **Cache/state = filesystem** → content-addressed, idempotent.
- **Coercion/eval = verification layer** → nothing the model emits is trusted raw.

> Implication: most reliability gains come from the OS, not from a bigger model.

## P2 — Context engineering > prompt engineering
The scarce resource is the context window. We **curate** it:
- Typed, **trust-tagged** evidence blocks (claim · per-image evidence · risk-only history · *untrusted* in-image text).
- Right altitude: distilled JSON evidence to the judge, not raw pixels.
- Just-in-time: only the scenario pack and requirements relevant to *this* object.
- No stuffing — every token in context earns its place.

## P3 — Spec / schema is the program (Software 3.0)
The output schema + allowed values (`schema.py`) are the **executable spec**.
- Both code and prompts reference the same source of truth.
- Every model output is validated/coerced to it — the artifact can never be illegal.
- The spec is versioned; changing it is a deliberate, reviewable act.

## P4 — Autonomy slider + human-in-the-loop ("march of nines")
We don't chase full autonomy; we expose a **dial**.
- Reliability is earned one nine at a time; design for *partial* autonomy with verification.
- Confidence-gated **escalation to a human** (`manual_review_required`) is a
  first-class output, not a failure mode.
- The decision policy is explicit and tunable (`escalation.py`), not buried in a prompt.

## P5 — Tools / skills as composable, pluggable capabilities
Every capability — perception, OCR, forgery check, duplicate detection, object
consistency, history — is a **Tool** with a uniform interface behind a
**registry** with **capability detection**.
- Adding a scenario detector = add one file + register it. No core changes.
- Heavy/optional tools (GPU models) **degrade gracefully** when deps/weights absent.
- Tools are independently testable and independently swappable across providers.

## P6 — Declarative scenario packs, not hardcoded branches
Per `object × issue-family` behavior lives in **data** (`scenarios/*.yaml`), not in
`if claim_object == "car"` ladders.
- A scenario pack declares: required evidence, which tools/risks to run, decision hints.
- Behavior is extensible and **auditable** without touching code.
- New object types or issue families are a config change.

## P7 — Determinism & idempotence where possible
- `temperature = 0`, enum coercion, pure-function Tier-0 detectors.
- **Content-addressed caching** → identical re-runs cost zero model calls.
- Reproducibility is a feature, not an accident. (Residual model nondeterminism is *measured*, see P9.)

## P8 — Defense in depth / adversarial verification (anti-gaming)
No single pass is trusted, and no single bypass wins:
- **Provenance** at capture (camera-only PWA + signed token).
- **Forensics** on pixels (ELA / manipulation / AI-gen detectors).
- **Consistency** across images, claim, and history (perceptual hash, CLIP object check).
- **Content** checks (in-image text → injection flag).
- Independent detectors cross-check the model; gaming one layer is not enough.

## P9 — Evals as the backbone, not an afterthought
- Every change is measured on the labeled set (`evaluation/`), multi-strategy.
- Regression-tracked; **honest about variance** (we report run-to-run spread).
- "You can't improve what you don't measure" — the march of nines is eval-driven.

## P10 — Observability & traceability
- Every decision emits a **structured trace**: claim → tool signals → reasoning →
  decision → flags → escalation. (`trace.py`)
- Auditable, debuggable, and explainable to a human reviewer or auditor.
- Token/cost usage is tracked per tier for operational transparency.

## P11 — Cost & latency are design constraints
- Tiering (free → cheap → strong), bounded concurrency, batching, caching, retry/fallback.
- Spend compute **only where it changes the decision** — one strong-model call per claim.

## P12 — Graceful degradation & capability detection
- Missing key → deterministic mock tier; missing optional dep → tool disables itself
  and the harness records *why* coverage was reduced (no silent gaps).
- The system always produces a valid, schema-conformant result.

---

## How the principles map to the code

| Principle | Where it lives |
|---|---|
| P1 kernel/OS | `harness/` (registry, scheduler in `pipeline.py`, trace, escalation) |
| P2 context engineering | `judge.py` context assembly, `prompts.py` trust separation |
| P3 spec is program | `schema.py` (enums + `coerce_row`) |
| P4 autonomy/HITL | `harness/escalation.py` → `manual_review_required` |
| P5 pluggable tools | `harness/tool.py`, `harness/registry.py`, `tools/*` |
| P6 scenario packs | `scenarios/*.yaml`, loaded by the registry |
| P7 determinism | `cache.py`, `temperature=0`, `coerce_row` |
| P8 defense in depth | `tools/provenance.py`, `tools/forgery.py`, `tools/ocr_injection.py`, `tools/object_consistency.py` |
| P9 evals | `evaluation/` |
| P10 observability | `harness/trace.py`, `usage.py` |
| P11 cost/latency | tiering in `pipeline.py`, `cache.py`, `MAX_CONCURRENCY` |
| P12 degradation | `config.py` mock fallback, per-tool `available()` checks |

See also: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (system design),
[`SCENARIO_COVERAGE.md`](./SCENARIO_COVERAGE.md) (open-source detectors per scenario),
[`GUARDRAILS.md`](./GUARDRAILS.md), [`TOOLS.md`](./TOOLS.md), [`SCENARIOS.md`](./SCENARIOS.md).
