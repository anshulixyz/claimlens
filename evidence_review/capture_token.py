"""Capture-token verification — backend counterpart to the capture PWA.

The PWA (code/pwa/) binds every live-camera capture to a signed token:
    token = {payload, alg:"HMAC-SHA256", sig}
    payload.image_sha256 = SHA-256(image bytes)
    sig = HMAC-SHA256(canonical(payload), secret)
where canonical() == json.dumps(payload, sort_keys=True, separators=(",",":")),
exactly matching the PWA's canonical() in app.js.

This module re-verifies a token server-side. A swapped, edited, re-saved, or
uploaded (non-camera) image fails verification — which is what makes the
camera-only capture path hard to game. The ProvenanceTool uses this to turn a
valid token into a strong authenticity signal, and a missing/invalid token on a
claimed live capture into `non_original_image`.

SECURITY NOTE: the demo secret matches the PWA's DEMO_SECRET for end-to-end
testing. In production the secret is server-side only, the server issues a
one-time `nonce`, and capture is backed by platform attestation
(Play Integrity / App Attest) — the token format stays the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass


def _secret() -> str:
    return os.environ.get("CAPTURE_TOKEN_SECRET", "evidence-capture-demo-key-v1")


def canonical(payload: dict) -> str:
    """Must match the PWA's canonical(): sorted keys, compact separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign(payload: dict, secret: str | None = None) -> str:
    msg = canonical(payload).encode("utf-8")
    return hmac.new((secret or _secret()).encode("utf-8"), msg, hashlib.sha256).hexdigest()


@dataclass
class TokenVerdict:
    valid: bool
    reasons: list
    live_capture: bool = False

    def as_dict(self):
        return {"valid": self.valid, "live_capture": self.live_capture, "reasons": self.reasons}


def verify_token(
    token: dict,
    image_bytes: bytes | None = None,
    secret: str | None = None,
    max_age_days: int | None = None,
) -> TokenVerdict:
    """Verify a capture token. If image_bytes is given, also bind the hash."""
    reasons = []
    if not isinstance(token, dict) or "payload" not in token or "sig" not in token:
        return TokenVerdict(False, ["malformed token"])

    payload = token["payload"]

    # 1. signature over canonical payload
    expected = sign(payload, secret)
    if not hmac.compare_digest(expected, str(token.get("sig", ""))):
        reasons.append("signature mismatch")

    # 2. provenance assertion
    live = payload.get("capture_source") == "live_camera"
    if not live:
        reasons.append("capture_source != live_camera")

    # 3. bind the actual image bytes (the anti-swap check)
    if image_bytes is not None:
        actual = hashlib.sha256(image_bytes).hexdigest()
        if actual != payload.get("image_sha256"):
            reasons.append("image hash mismatch (image altered or swapped)")

    # 4. optional freshness
    if max_age_days is not None:
        from datetime import datetime, timezone

        try:
            ts = datetime.fromisoformat(payload["captured_at"].replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).days
            if age > max_age_days:
                reasons.append(f"token older than {max_age_days} days")
        except Exception:
            reasons.append("unparseable captured_at")

    return TokenVerdict(valid=not reasons, reasons=reasons, live_capture=live)


def sidecar_token_path(image_path):
    """Convention: an image's token lives next to it as <name>.token.json."""
    from pathlib import Path

    p = Path(image_path)
    return p.with_suffix(p.suffix + ".token.json")
