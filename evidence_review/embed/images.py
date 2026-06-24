"""Evidence-image materialization for the intake envelope.

Decodes/resolves the untrusted `evidence.images` item specs into local files:
* data_url -> base64-decode into a private tempdir,
* path     -> resolved via `dataio.resolve_image` (path-traversal guard kept),
* url      -> skipped with a risk note (remote fetch is out of scope here).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .. import dataio
from .envelope import ClaimIntake


def _classify_item(item: Any) -> tuple[str, str]:
    """Normalize an evidence item to (kind, value).

    kind in {"data_url", "path", "url", "unknown"}.
    """
    if isinstance(item, dict):
        kind = str(item.get("kind", "")).strip().lower()
        value = str(item.get("value", ""))
        if kind in ("data_url", "path", "url"):
            return kind, value
        # infer from value if kind missing/unknown
        item = value
    if not isinstance(item, str):
        return "unknown", ""
    s = item.strip()
    if not s:
        return "unknown", ""
    # A bare base64 blob can't be reliably told apart from a path (base64's
    # alphabet includes "/"), so base64 evidence must be an explicit `data:` URL
    # or carry kind="data_url" (handled above). Everything else is a url or path.
    if s.startswith("data:"):
        return "data_url", s
    if s.lower().startswith(("http://", "https://")):
        return "url", s
    return "path", s


_MIME_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/bmp": ".bmp",
}


def _data_url_ext(value: str) -> str:
    """Best-effort file extension from a data-URL mime (intake re-sniffs bytes)."""
    if value.startswith("data:") and "," in value:
        mime = value[5:].split(",", 1)[0].split(";", 1)[0].strip().lower()
        return _MIME_EXT.get(mime, ".img")
    return ".img"


def materialize_images(intake: ClaimIntake, tmpdir: Path) -> tuple[list, list]:
    """Decode/resolve evidence images to local files. Returns (paths, notes).

    * data_url  -> base64-decode into `tmpdir` (mirrors server.py `_decode_images`).
    * path      -> resolved via `dataio.resolve_image` (path-traversal guard kept).
    * url       -> SKIPPED with a risk note; remote fetch is out of scope for this
                   reference and belongs to the host system.
    """
    paths: list = []
    notes: list = []
    n = 0
    for item in intake.images or []:
        kind, value = _classify_item(item)
        if kind == "data_url":
            if value.startswith("data:") and "," not in value:
                notes.append("skipped an image: malformed data URL (no base64 payload)")
                continue
            b64 = value.split(",", 1)[1] if "," in value else value
            b64 = "".join(b64.split())  # tolerate wrapped/whitespaced payloads
            try:
                # validate=True rejects non-base64 garbage (fail closed, no junk file)
                raw = base64.b64decode(b64, validate=True)
            except Exception:
                notes.append("skipped an image: invalid base64 data URL")
                continue
            if not raw:
                notes.append("skipped an image: empty data URL")
                continue
            n += 1
            p = tmpdir / f"img_{n}{_data_url_ext(value)}"
            p.write_bytes(raw)
            paths.append(p)
        elif kind == "path":
            resolved = dataio.resolve_image(value)
            if resolved.exists():
                paths.append(resolved)
            else:
                notes.append(
                    f"skipped a path image: {value!r} did not resolve inside the dataset "
                    "(missing or path-traversal rejected)"
                )
        elif kind == "url":
            notes.append(
                f"skipped a url image: remote fetch is out of scope for this reference "
                f"(host must fetch and resubmit as data_url) — {value!r}"
            )
        else:
            notes.append("skipped an unrecognized evidence item")
    return paths, notes
