"""Scenario-pack loader (Principle P6 — behavior as data).

Loads declarative per-object scenario packs from scenario_packs/*.yaml. Falls
back to a no-op pack if PyYAML is unavailable, so the pipeline never hard-fails.
Adding a new object type = drop a new YAML file here; no code change.
"""

from __future__ import annotations

from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent / "scenario_packs"

_CACHE: dict | None = None


def _load_all() -> dict:
    packs = {}
    try:
        import yaml
    except Exception:
        return packs  # graceful: no packs -> empty hints
    for f in sorted(PACK_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if data and data.get("object"):
                packs[data["object"].lower()] = data
        except Exception:
            continue
    return packs


def get_scenario(claim_object: str) -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_all()
    return _CACHE.get((claim_object or "").lower(), {})


def scenario_hint_block(scenario: dict) -> str:
    """Render the scenario pack into a compact text block for the judge prompt."""
    if not scenario:
        return "(no scenario pack loaded)"
    lines = [f"Scenario: {scenario.get('object')}"]
    fams = scenario.get("issue_families", [])
    if fams:
        lines.append("Issue families & required evidence:")
        for fam in fams:
            lines.append(
                f"  - {fam.get('name')}: issues={fam.get('issues')}; "
                f"evidence: {fam.get('evidence')}"
            )
    if scenario.get("risk_focus"):
        lines.append(f"Risk focus: {scenario['risk_focus']}")
    if scenario.get("decision_hints"):
        lines.append("Decision hints:\n" + scenario["decision_hints"].rstrip())
    return "\n".join(lines)
