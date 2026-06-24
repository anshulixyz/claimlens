"""ProvenanceTool — provenance & reuse detection (LIVE, free + optional C2PA).

Combines three independent provenance signals (defense in depth, P8):
  1. Perceptual-hash duplicate/reuse across the claim's images  -> non_original_image
  2. EXIF / camera-capture presence (soft signal; EXIF is forgeable)
  3. C2PA Content Credentials (cryptographic, HARD to fake) — optional, via
     the permissive `c2pa-python` (MIT/Apache); awards authenticity when a
     valid manifest is present. Self-disables if the lib isn't installed.

License-clean: imagehash (BSD), c2pa-python (MIT/Apache), Pillow EXIF.
Optional robustness upgrade: pdqhash (MIT) — see docs/SCENARIO_COVERAGE.md.
"""

from __future__ import annotations

import json

from ..capture_token import sidecar_token_path, verify_token
from ..harness.tool import Tool, ToolResult

try:
    import c2pa  # optional, permissive

    _HAS_C2PA = True
except Exception:
    _HAS_C2PA = False


class ProvenanceTool(Tool):
    name = "provenance"
    tier = "forensic"
    produces_flags = ("non_original_image",)

    def run(self, ctx) -> ToolResult:
        cv = ctx.cv_result
        dup = cv.get("duplicate_image_ids", []) or []
        any_exif = cv.get("any_camera_exif", False)

        flags = set()
        if dup:
            flags.add("non_original_image")

        # capture-token verification (counterpart to the camera-only PWA).
        # If an image ships a signed capture token, verify it binds the bytes +
        # asserts live-camera origin. A present-but-invalid token => tampering.
        capture = []
        for p in ctx.abs_paths:
            tok_path = sidecar_token_path(p)
            if not tok_path.exists():
                continue
            try:
                token = json.loads(tok_path.read_text())
                verdict = verify_token(token, image_bytes=p.read_bytes())
            except Exception as e:
                verdict = None
                capture.append({"image_id": p.stem, "error": str(e)})
                continue
            capture.append({"image_id": p.stem, **verdict.as_dict()})
            if not verdict.valid:
                flags.add("non_original_image")  # claimed capture but token fails

        # optional cryptographic provenance
        c2pa_results = []
        if _HAS_C2PA:
            for p in ctx.abs_paths:
                try:
                    manifest = c2pa.read_file(str(p), None)
                    c2pa_results.append({"image_id": p.stem, "has_manifest": bool(manifest)})
                except Exception:
                    c2pa_results.append({"image_id": p.stem, "has_manifest": False})

        note = (
            f"duplicates={dup or 'none'}; camera_exif={any_exif}; "
            f"c2pa={'on' if _HAS_C2PA else 'not_installed'}"
        )
        return ToolResult(
            name=self.name,
            available=True,
            signals={
                "duplicate_image_ids": dup,
                "any_camera_exif": any_exif,
                "c2pa": c2pa_results,
                "c2pa_enabled": _HAS_C2PA,
                "capture_tokens": capture,
            },
            risk_flags=sorted(flags),
            evidence={
                "provenance": {
                    "duplicate_image_ids": dup,
                    "any_camera_exif": any_exif,
                    "c2pa": c2pa_results,
                    "capture_tokens": capture,
                }
            },
            note=note,
        )
