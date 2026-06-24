"""Presentation helpers for the ClaimLens server.

Pure, framework-free functions split out of `server.py` so the server module is
just wiring (routes + app assembly). These shape a pipeline decision into the
conversational reply and the per-run "decision detail" the UI renders, decode
live-capture data URLs, and stamp timestamps.
"""

import base64
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_images(data_urls: list[str], tmpdir: Path) -> list[Path]:
    paths = []
    for i, durl in enumerate(data_urls or [], start=1):
        b64 = durl.split(",", 1)[1] if "," in durl else durl
        try:
            raw = base64.b64decode(b64)
        except Exception:
            continue
        p = tmpdir / f"img_{i}.jpg"
        p.write_bytes(raw)
        paths.append(p)
    return paths


def _assistant_message(d: dict, claim_object: str) -> str:
    """A grounded, conversational reply derived from the REAL verdict + justification."""
    status, flags = d["claim_status"], d["risk_flags"]
    just = d.get("claim_status_justification", "").strip()
    sev = d.get("severity", "unknown")
    if "wrong_object" in flags:
        return (
            f"Hmm — that photo doesn’t look like a {claim_object}. {just} "
            f"Could you point the camera at the {claim_object} and recapture the affected area?"
        )
    if "text_instruction_present" in flags:
        return f"I noticed text overlaid on the image, so I judged it from the actual condition only. {just}"
    if status == "supported":
        return f"Thanks — I can confirm it from your photo. {just} Logged as accepted (severity: {sev})."
    if status == "contradicted":
        return (
            f"I looked closely and couldn’t see the damage described. {just} "
            f"I can’t approve this as it stands — want to add another angle?"
        )
    return (
        f"I can’t verify this yet. {just} "
        f"Could you retake a clearer, closer photo of the affected area?"
    )


def _detail(extra: dict) -> dict:
    """Per-run observability payload: the tiered chain the verdict came from."""
    jr = extra.get("judge_raw", {}) or {}
    esc = extra.get("escalation", {}) or {}
    perceptions = []
    for p in extra.get("perceptions", []) or []:
        perceptions.append(
            {
                "image_id": p.get("_image_id"),
                "object_present": p.get("object_present"),
                "issue_type": p.get("issue_type"),
                "object_part": p.get("object_part"),
                "image_quality": p.get("image_quality"),
                "notes": p.get("notes"),
            }
        )
    tools = []
    for t in extra.get("tool_results", []) or []:
        tools.append(
            {
                "name": t.name,
                "available": t.available,
                "risk_flags": list(t.risk_flags),
                "note": t.note,
            }
        )
    return {
        "claim_summary": jr.get("claim_summary"),
        "reasoning": jr.get("reasoning"),
        "confidence": esc.get("confidence"),
        "confidence_band": esc.get("confidence_band"),
        "escalation_reasons": esc.get("reasons", []),
        "perception": perceptions,
        "tools": tools,
    }
