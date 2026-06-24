"""Deterministic offline provider.

No network, no key, no cost. Produces structured JSON for both the perception
and judge tiers using simple keyword + signal heuristics. This guarantees the
full pipeline and the evaluation harness run end-to-end with zero secrets —
critical for reproducibility on the evaluator's machine. It is NOT meant to be
accurate; it is the floor that real VLM backends improve upon.
"""

from __future__ import annotations

import json

from .base import ProviderResponse

_ISSUE_KEYWORDS = [
    ("glass_shatter", ["shatter", "smash"]),
    ("crack", ["crack", "cracked"]),
    ("dent", ["dent", "dented", "ding"]),
    ("scratch", ["scratch", "scrape", "scuff", "mark"]),
    ("missing_part", ["missing", "fell off", "gone"]),
    ("broken_part", ["broke", "broken", "snapped"]),
    ("torn_packaging", ["torn", "ripped", "tear"]),
    ("crushed_packaging", ["crush", "crushed", "dented box"]),
    ("water_damage", ["water", "wet", "soaked", "moist"]),
    ("stain", ["stain", "spill", "discolor"]),
]

_PART_KEYWORDS = [
    "front_bumper",
    "rear_bumper",
    "windshield",
    "side_mirror",
    "headlight",
    "taillight",
    "fender",
    "quarter_panel",
    "hood",
    "door",
    "screen",
    "keyboard",
    "trackpad",
    "hinge",
    "lid",
    "corner",
    "port",
    "seal",
    "label",
    "contents",
    "package_corner",
    "package_side",
    "box",
    "item",
    "body",
    "base",
]


def _text_of(parts):
    return " ".join(p for p in parts if isinstance(p, str)).lower()


def _guess_issue(text):
    for issue, kws in _ISSUE_KEYWORDS:
        if any(k in text for k in kws):
            return issue
    return "unknown"


def _guess_part(text):
    for part in _PART_KEYWORDS:
        if part.replace("_", " ") in text or part in text:
            return part
    return "unknown"


class MockProvider:
    def complete_json(
        self,
        system: str,
        parts: list,
        model: str = "mock",
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        text = _text_of(parts)
        n_images = sum(1 for p in parts if not isinstance(p, str))

        if "PERCEPTION" in system.upper():
            payload = {
                "object_present": True,
                "object_guess": "unknown",
                "visible_parts": [_guess_part(text)] if _guess_part(text) != "unknown" else [],
                "damage_observed": _guess_issue(text) != "unknown",
                "issue_type": _guess_issue(text),
                "object_part": _guess_part(text),
                "image_quality": "ok",
                "text_in_image": False,
                "notes": "mock perception (no model key configured)",
            }
        else:  # JUDGE
            issue = _guess_issue(text)
            part = _guess_part(text)
            has_signal = issue != "unknown" and n_images >= 0
            status = "supported" if has_signal else "not_enough_information"
            payload = {
                "evidence_standard_met": has_signal,
                "evidence_standard_met_reason": "Mock heuristic based on claim keywords and image presence.",
                "risk_flags": ["manual_review_required"] if not has_signal else [],
                "issue_type": issue,
                "object_part": part,
                "claim_status": status,
                "claim_status_justification": f"Mock decision: keyword issue='{issue}', part='{part}'.",
                "supporting_image_ids": [],
                "valid_image": True,
                "severity": "medium" if has_signal else "unknown",
            }

        body = json.dumps(payload)
        return ProviderResponse(text=body, input_tokens=0, output_tokens=0, model="mock")
