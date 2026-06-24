"""ForgeryTool — lightweight manipulation forensics (LIVE, free).

Error Level Analysis (ELA): re-encode the JPEG at a known quality and measure
the per-pixel residual. Uniformly-compressed authentic photos show low, even
residual; spliced / pasted / locally-edited regions light up. We compute global
ELA statistics and a localized-spike ratio.

ELA is a documented-WEAK prior — it degrades badly on already-recompressed /
re-saved JPEGs and is meaningless on PNGs (single-JPEG ELA needs a JPEG source).
So by default this tool is EVIDENCE-ONLY: it surfaces ELA statistics to the
judge but does NOT assert `possible_manipulation` on its own (set
`FORGERY_ASSERT=1` to enable assertion if you have validated the threshold on
your data). It only runs on JPEG inputs. A learned manipulation / AI-gen
detector (UniversalFakeDetect adapter, or a Hive/Reality-Defender-style API) is
the right upgrade — see docs/SCENARIO_COVERAGE.md and BENCHMARKING.md.
Algorithm reference: Sherloq (GPL — reference only; clean numpy/PIL reimpl).
"""

from __future__ import annotations

import os
from io import BytesIO

import numpy as np
from PIL import Image

from ..harness.tool import Tool, ToolResult

# strong, localized signal required before asserting manipulation (avoid FPs)
ELA_SPIKE_RATIO = 0.020  # fraction of pixels far above the mean residual
ELA_MEAN_MIN = 12.0  # mean residual floor to even consider flagging


def _ela_stats(path, quality=90):
    img = Image.open(path).convert("RGB")
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    recompressed = Image.open(buf).convert("RGB")
    a = np.asarray(img, dtype=np.int16)
    b = np.asarray(recompressed, dtype=np.int16)
    diff = np.abs(a - b).max(axis=2).astype(np.float64)  # per-pixel max channel residual
    mean = float(diff.mean())
    std = float(diff.std())
    thresh = mean + 3 * std
    spike_ratio = float((diff > thresh).mean()) if std > 0 else 0.0
    return {
        "ela_mean": round(mean, 2),
        "ela_std": round(std, 2),
        "ela_spike_ratio": round(spike_ratio, 4),
    }


class ForgeryTool(Tool):
    name = "forgery"
    tier = "forensic"
    produces_flags = ("possible_manipulation",)

    def run(self, ctx) -> ToolResult:
        assert_flag = os.environ.get("FORGERY_ASSERT") == "1"
        per_image, flags = [], set()
        for p in ctx.abs_paths:
            if not p.exists():
                continue
            if p.suffix.lower() not in (".jpg", ".jpeg"):
                per_image.append({"image_id": p.stem, "skipped": "non-JPEG (ELA n/a)"})
                continue
            try:
                s = _ela_stats(p)
            except Exception as e:
                per_image.append({"image_id": p.stem, "error": str(e)})
                continue
            s["image_id"] = p.stem
            # weak prior: note a strong localized residual spike, but only ASSERT
            # the risk flag when explicitly enabled (validated threshold).
            s["suspicious"] = bool(
                s["ela_spike_ratio"] >= ELA_SPIKE_RATIO and s["ela_mean"] >= ELA_MEAN_MIN
            )
            if s["suspicious"] and assert_flag:
                flags.add("possible_manipulation")
            per_image.append(s)

        susp = sum(1 for s in per_image if s.get("suspicious"))
        note = (
            f"ELA on {len(per_image)} image(s); suspicious={susp}; "
            f"assert={'on' if assert_flag else 'evidence-only'}"
        )
        return ToolResult(
            name=self.name,
            available=True,
            signals={"per_image": per_image},
            risk_flags=sorted(flags),
            evidence={"ela": per_image},
            note=note,
        )
