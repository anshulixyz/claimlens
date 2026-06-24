"""QualityTool — image quality assessment (LIVE, free).

Wraps the Tier-0 OpenCV/PIL signals (blur via Laplacian variance, luminance,
glare/saturation, resolution) already computed in context_builder and turns
them into deterministic risk flags. License-clean (OpenCV Apache-2.0).
Optional upgrade path: OpenCV-contrib BRISQUE (see docs/SCENARIO_COVERAGE.md).
"""

from __future__ import annotations

from ..harness.tool import Tool, ToolResult


class QualityTool(Tool):
    name = "quality"
    tier = "context"
    produces_flags = ("blurry_image", "low_light_or_glare", "cropped_or_obstructed")

    def run(self, ctx) -> ToolResult:
        images = ctx.cv_result.get("images", [])
        flags, per_image = set(), []
        usable_any = False
        for im in images:
            hints = im.get("risk_hints", []) or []
            flags.update(h for h in hints if h in self.produces_flags)
            usable_any = usable_any or im.get("usable", False)
            per_image.append(
                {
                    "image_id": im.get("image_id"),
                    "blur_var": im.get("blur_var"),
                    "mean_luma": im.get("mean_luma"),
                    "glare_frac": im.get("glare_frac"),
                    "small_side": im.get("small_side"),
                    "usable": im.get("usable"),
                }
            )
        note = f"{len(images)} image(s); usable={usable_any}; flags={sorted(flags) or 'none'}"
        return ToolResult(
            name=self.name,
            available=True,
            signals={
                "per_image": per_image,
                "usable_any": usable_any,
                "cv_backend": ctx.cv_result.get("cv_backend"),
            },
            risk_flags=sorted(flags),
            evidence={"quality_per_image": per_image},
            note=note,
        )
