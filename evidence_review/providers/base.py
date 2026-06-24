"""Shared provider plumbing: response container, image encoding, JSON parsing."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# transient errors worth retrying (NOT 400/credit/auth — those fail fast)
_TRANSIENT = (
    "503",
    "502",
    "500",
    "504",
    "429",
    "overloaded",
    "unavailable",
    "timeout",
    "timed out",
    "rate limit",
    "deadline",
    "temporarily",
)


def with_retries(fn, tries=3, base_delay=1.0):
    """Call fn(); retry transient API errors (503/429/5xx/overload) with backoff.

    Permanent errors (400 invalid_request, credit-too-low, auth) re-raise
    immediately so the pipeline degrades to a manual-review row fast.
    """
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if not any(t in str(e).lower() for t in _TRANSIENT) or i == tries - 1:
                raise
            time.sleep(base_delay * (2**i))
    raise last


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    raw: dict = field(default_factory=dict)

    def json(self) -> dict:
        return parse_json(self.text)


def encode_image(path: Path):
    """Return (base64_str, mime_type) for an image file."""
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/jpeg"
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii"), mime


def parse_json(text: str) -> dict:
    """Best-effort JSON extraction from a model response."""
    if not text:
        return {}
    text = text.strip()
    # strip ```json fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # grab the outermost {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return {}
    return {}
