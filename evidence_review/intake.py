"""Image Admissibility Protocol — the standard intake contract.

Every image entering the system is classified into ONE admissibility status with
a defined, documented response BEFORE any paid model call. This gives a single,
predictable protocol for "what do we do with this image?" — usable, unsupported,
too low-quality ("cheap"), oversized (decompression-bomb), unreadable, missing,
or blocked/censored (safety-filtered). It is also a security boundary for
untrusted image input (format allowlist + size/pixel caps).

Open end (Principle P5): the protocol is a *registry of checks*. Any integrating
system can register its own check (e.g. a stricter format policy, an NSFW gate,
a regulatory rule) without editing this file:

    from evidence_review.intake import register_check, Status
    register_check(my_check)   # (path, raw_bytes, cv) -> Status | None

The first check that returns a non-OK Status decides; otherwise the image is OK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image


# --- the canonical status set (a string enum kept simple for serialization) ---
class Status:
    OK = "ok"  # usable for automated review
    MISSING = "missing"  # file not found
    UNREADABLE = "unreadable"  # cannot decode
    UNSUPPORTED_FORMAT = "unsupported_format"
    OVERSIZED = "oversized"  # exceeds byte/pixel caps (DoS / bomb guard)
    TOO_LOW_QUALITY = "too_low_quality"  # "cheap": tiny / severely blurred
    BLOCKED = "blocked"  # safety-filtered / censored by a downstream check


# statuses that are still worth sending to the perception model
SEND_TO_MODEL = {Status.OK, Status.TOO_LOW_QUALITY}

# how each status maps onto the output contract
_RESPONSE = {
    Status.OK: {"valid_image": True, "risk_flags": []},
    Status.MISSING: {"valid_image": False, "risk_flags": ["damage_not_visible"]},
    Status.UNREADABLE: {"valid_image": False, "risk_flags": ["damage_not_visible"]},
    Status.UNSUPPORTED_FORMAT: {"valid_image": False, "risk_flags": ["manual_review_required"]},
    Status.OVERSIZED: {"valid_image": False, "risk_flags": ["manual_review_required"]},
    Status.TOO_LOW_QUALITY: {"valid_image": True, "risk_flags": ["blurry_image"]},
    Status.BLOCKED: {"valid_image": False, "risk_flags": ["manual_review_required"]},
}

# --- security / quality limits (documented; tune per deployment) ---
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC", "BMP"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_PIXELS = 50_000_000  # 50 MP (decompression-bomb guard)
MIN_SIDE = 64  # below this we cannot inspect anything

# guard Pillow against decompression bombs globally
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass
class Admissibility:
    image_id: str
    status: str
    valid_image: bool
    send_to_model: bool
    risk_flags: list = field(default_factory=list)
    reason: str = ""

    def as_dict(self):
        return {
            "image_id": self.image_id,
            "status": self.status,
            "valid_image": self.valid_image,
            "send_to_model": self.send_to_model,
            "risk_flags": self.risk_flags,
            "reason": self.reason,
        }


# ---- built-in checks (run in order; first non-OK wins) ----
def _check_exists(path: Path, raw, cv):
    if not path.exists():
        return Status.MISSING, "file not found"
    return None


def _check_size(path: Path, raw, cv):
    try:
        if path.stat().st_size > MAX_BYTES:
            return Status.OVERSIZED, f">{MAX_BYTES // (1024 * 1024)}MB"
    except OSError:
        return Status.UNREADABLE, "stat failed"
    return None


def _check_decodes(path: Path, raw, cv):
    try:
        with Image.open(path) as im:
            fmt = (im.format or "").upper()
            im.verify()  # detect truncation / bombs without full decode
    except Exception as e:
        return Status.UNREADABLE, f"decode failed: {type(e).__name__}"
    if fmt and fmt not in ALLOWED_FORMATS:
        return Status.UNSUPPORTED_FORMAT, f"format={fmt}"
    return None


def _check_quality(path: Path, raw, cv):
    # cv is the per-image Tier-0 signal dict (may be empty)
    side = cv.get("small_side")
    if side is not None and side < MIN_SIDE:
        return Status.TOO_LOW_QUALITY, f"min side {side}px"
    if not cv.get("usable", True):
        return Status.TOO_LOW_QUALITY, "below usability threshold"
    return None


_CHECKS = [_check_exists, _check_size, _check_decodes, _check_quality]


def register_check(fn):
    """Register an external admissibility check: (path, raw_bytes, cv) -> (Status, reason) | None."""
    _CHECKS.append(fn)
    return fn


def assess(path, cv_signals: dict | None = None) -> Admissibility:
    path = Path(path)
    cv = cv_signals or {}
    image_id = path.stem
    for check in _CHECKS:
        try:
            result = check(path, None, cv)
        except Exception as e:
            result = (Status.UNREADABLE, f"check error: {e}")
        if result:
            status, reason = result
            resp = _RESPONSE.get(status, _RESPONSE[Status.UNREADABLE])
            return Admissibility(
                image_id,
                status,
                resp["valid_image"],
                status in SEND_TO_MODEL,
                list(resp["risk_flags"]),
                reason,
            )
    resp = _RESPONSE[Status.OK]
    return Admissibility(image_id, Status.OK, True, True, list(resp["risk_flags"]), "usable")
