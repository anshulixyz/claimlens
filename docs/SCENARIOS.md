# Scenario Packs — Behavior as Data

Per-object behavior lives in **declarative YAML packs**
(`evidence_review/scenario_packs/*.yaml`), not in hardcoded `if claim_object ==`
branches (Principle P6). A pack describes the object's parts, issue families,
required evidence, risk focus, decision hints, and which tools to run. Adding a
new object type or issue family is a config change — no code edit.

## Pack schema

```yaml
object: car                 # the claim_object this pack applies to
description: >              # human summary
  ...
parts: [front_bumper, ...]  # allowed object_part values (self-describing)
issue_families:             # group issue_types + their evidence requirement
  - name: dent_or_scratch
    issues: [dent, scratch]
    severity_default: medium
    evidence: "Panel visible at an angle where marks/deformation can be assessed."
risk_focus: [wrong_object, claim_mismatch, non_original_image]   # advisory
decision_hints: |           # object-specific guidance injected into the judge
  - Cracked windshields are 'crack' unless glass is in pieces ('glass_shatter').
  - Identity mismatch between two car images -> not_enough_information + wrong_object.
tools: null                 # null = all registered tools; or a name subset
```

## How a pack is used
- `scenarios.get_scenario(claim_object)` loads the pack (cached).
- `scenarios.scenario_hint_block()` renders it into a compact text block that is
  injected into the judge prompt under "SCENARIO PACK" — this is where domain
  knowledge for handling each scenario lives.
- `ToolRegistry.active()` consults `tools:` to optionally restrict which
  detectors run for that object.

## Shipped packs
- [`car.yaml`](../evidence_review/scenario_packs/car.yaml) — panels, glass, lights, mirrors; vehicle identity/orientation.
- [`laptop.yaml`](../evidence_review/scenario_packs/laptop.yaml) — screen/keyboard/trackpad; hinge/lid/port structural.
- [`package.yaml`](../evidence_review/scenario_packs/package.yaml) — exterior crush/tear/seal; label/stain; contents.

## Adding a scenario
1. Drop a new `<object>.yaml` in `scenario_packs/`.
2. (If it introduces new parts/issues, also extend `schema.py` enums.)
3. Done — the loader auto-discovers it; the judge gets its hints; tools honor its `tools:` list.

Graceful degradation: if PyYAML is missing, packs load empty and the judge falls
back to the global rubric in `prompts.py` (P12).
