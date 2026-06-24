"""Tier 1 — per-image perception (cheap VLM), cached by image content hash."""

from __future__ import annotations

import json
from pathlib import Path

from . import prompts
from .cache import JsonCache, file_sha1, text_sha1


class Perception:
    def __init__(self, router, cache: JsonCache, usage):
        self.router = router  # ModelRouter (capability-based selection + fallback)
        self.cache = cache
        self.usage = usage
        # cache key uses the preferred perception model (stable per config)
        self.model = getattr(router.cfg, "perception_model", None) or "perception"

    def perceive(self, image_path: Path, claim_object: str, cv_signals: dict) -> dict:
        image_path = Path(image_path)
        if not image_path.exists():
            return {
                "object_present": False,
                "notes": "image file missing",
                "image_quality": "missing",
                "_image_id": image_path.stem,
            }

        # cache key: image bytes + model + prompt version + the CV signals that
        # are actually interpolated into the prompt (so changing Tier-0 thresholds
        # invalidates stale perceptions instead of silently serving them).
        sig_keys = (
            "blur_var",
            "mean_luma",
            "glare_frac",
            "small_side",
            "has_camera_exif",
            "risk_hints",
        )
        sig_fingerprint = json.dumps({k: cv_signals.get(k) for k in sig_keys}, sort_keys=True)
        key = text_sha1(
            f"{file_sha1(image_path)}|{self.model}|{prompts.PROMPT_VERSION}|{sig_fingerprint}"
        )
        cached = self.cache.get(key)
        if cached is not None:
            self.usage.note_cache_hit()
            cached["_image_id"] = image_path.stem
            return cached

        user = prompts.PERCEPTION_USER.format(
            claim_object=claim_object,
            image_id=image_path.stem,
            cv_signals=json.dumps(
                {
                    k: cv_signals.get(k)
                    for k in (
                        "blur_var",
                        "mean_luma",
                        "glare_frac",
                        "small_side",
                        "has_camera_exif",
                        "risk_hints",
                    )
                }
            ),
        )
        try:
            # router selects the cheapest qualified perception model + falls back
            resp, _used = self.router.run(
                "perception",
                system=prompts.PERCEPTION_SYSTEM,
                parts=[user, image_path],
                max_tokens=600,
                images=1,
            )
            data = resp.json()
        except Exception as e:
            data = {
                "object_present": True,
                "notes": f"perception error: {e}",
                "image_quality": "unknown",
                "issue_type": "unknown",
                "object_part": "unknown",
                "damage_observed": False,
                "text_in_image": False,
            }

        data["_image_id"] = image_path.stem
        self.cache.set(key, data)
        return data
