"""Output schema, allowed-value enums, and strict coercion.

The evaluator checks the exact column set/order and (implicitly) the allowed
values from problem_statement.md. Models are fuzzy, so every model-produced
field is *snapped* to the nearest legal enum value here. This module is the
single source of truth for "what is a valid output row".
"""

from __future__ import annotations

# --- Exact output column order (problem_statement.md §Required output) ---
OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

# --- Allowed values (problem_statement.md §Allowed values) ---
CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}

ISSUE_TYPE = {
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
}

OBJECT_PART = {
    "car": {
        "front_bumper",
        "rear_bumper",
        "door",
        "hood",
        "windshield",
        "side_mirror",
        "headlight",
        "taillight",
        "fender",
        "quarter_panel",
        "body",
        "unknown",
    },
    "laptop": {
        "screen",
        "keyboard",
        "trackpad",
        "hinge",
        "lid",
        "corner",
        "port",
        "base",
        "body",
        "unknown",
    },
    "package": {
        "box",
        "package_corner",
        "package_side",
        "seal",
        "label",
        "contents",
        "item",
        "unknown",
    },
}

RISK_FLAGS = {
    "none",
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
}

SEVERITY = {"none", "low", "medium", "high", "unknown"}


_ALIASES = {
    "insufficient": "not_enough_information",
    "not_enough_info": "not_enough_information",
    "inconclusive": "not_enough_information",
    "supports": "supported",
    "contradicts": "contradicted",
    "shattered_glass": "glass_shatter",
    "broken": "broken_part",
    "missing": "missing_part",
    "torn": "torn_packaging",
    "crushed": "crushed_packaging",
    "water": "water_damage",
    "no_damage": "none",
    "screen_crack": "crack",
}


def _tokens(s):
    return [t for t in s.split("_") if t]


def _is_sublist(sub, seq):
    n = len(sub)
    return n > 0 and any(seq[i : i + n] == sub for i in range(len(seq) - n + 1))


def _snap(value, allowed, default, fuzzy=True):
    """Snap a model string to the nearest legal enum value.

    Matching order: exact -> curated alias -> (if fuzzy) contiguous TOKEN-sequence
    match -> default. Token matching avoids the dangerous char-substring trap
    (e.g. "unsupported" must NOT become "supported", "indoor" must NOT become
    "door"). For safety-critical fields like claim_status, pass fuzzy=False so an
    unrecognized value fails closed to the safe default rather than fuzzy-matching
    toward an approval.
    """
    if value is None:
        return default
    v = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if v in allowed:
        return v
    if v in _ALIASES and _ALIASES[v] in allowed:
        return _ALIASES[v]
    if fuzzy:
        vt = _tokens(v)
        best = None
        for a in allowed:
            if a in ("unknown", "none"):
                continue
            at = _tokens(a)
            if _is_sublist(at, vt):  # all of a's tokens appear contiguously in v
                if best is None or len(at) > len(_tokens(best)):
                    best = a
        if best:
            return best
    return default


def coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return default


def normalize_risk_flags(flags, claim_object=None):
    """Accept list or ';'-joined string; snap each; dedup; default 'none'."""
    if flags is None:
        items = []
    elif isinstance(flags, str):
        items = flags.replace(",", ";").split(";")
    else:
        items = list(flags)
    out, seen = [], set()
    for f in items:
        snapped = _snap(f, RISK_FLAGS, default=None)
        if snapped and snapped != "none" and snapped not in seen:
            seen.add(snapped)
            out.append(snapped)
    return ";".join(out) if out else "none"


def normalize_image_ids(ids):
    if ids is None:
        return "none"
    if isinstance(ids, str):
        items = [i.strip() for i in ids.replace(",", ";").split(";") if i.strip()]
    else:
        items = [str(i).strip() for i in ids if str(i).strip()]
    items = [i for i in items if i.lower() not in {"none", ""}]
    return ";".join(dict.fromkeys(items)) if items else "none"


def coerce_row(raw: dict, claim_object: str) -> dict:
    """Snap a model-produced dict to a fully legal output record (no input cols)."""
    co = (claim_object or "").strip().lower()
    part_allowed = OBJECT_PART.get(co, {"unknown"})
    return {
        "evidence_standard_met": coerce_bool(raw.get("evidence_standard_met"), False),
        "evidence_standard_met_reason": _clean_text(raw.get("evidence_standard_met_reason")),
        "risk_flags": normalize_risk_flags(raw.get("risk_flags"), co),
        "issue_type": _snap(raw.get("issue_type"), ISSUE_TYPE, "unknown"),
        "object_part": _snap(raw.get("object_part"), part_allowed, "unknown"),
        "claim_status": _snap(
            raw.get("claim_status"), CLAIM_STATUS, "not_enough_information", fuzzy=False
        ),
        "claim_status_justification": _clean_text(raw.get("claim_status_justification")),
        "supporting_image_ids": normalize_image_ids(raw.get("supporting_image_ids")),
        "valid_image": coerce_bool(raw.get("valid_image"), False),
        "severity": _snap(raw.get("severity"), SEVERITY, "unknown"),
    }


def _clean_text(s, limit=400):
    if not s:
        return ""
    s = " ".join(str(s).split())
    return s[:limit]
