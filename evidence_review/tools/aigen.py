"""AiGenAdapterTool — AI-generated / synthetic image detection (ADAPTER-READY).

Detecting diffusion/GAN-generated "evidence" is a strong anti-gaming signal
(-> non_original_image / possible_manipulation). The best-licensed detectors are
UniversalFakeDetect (MIT, frozen CLIP + linear head, CPU-feasible) and
Corvi2023/ClipBased-SyntheticImageDetection (Apache). Both need torch + a CLIP
backbone download, so this is wired as an OPTIONAL adapter that self-disables
unless the weights are provided via env var AIGEN_WEIGHTS.

Enable: pip install torch open_clip_torch ; set AIGEN_WEIGHTS=/path/to/fc_weights.pth
See docs/SCENARIO_COVERAGE.md for the integration contract.
"""

from __future__ import annotations

import os

from ..harness.tool import Tool, ToolResult


class AiGenAdapterTool(Tool):
    name = "aigen"
    tier = "forensic"
    produces_flags = ("non_original_image", "possible_manipulation")
    optional = True

    # Inference is not implemented yet, so this adapter reports UNAVAILABLE — we
    # do not advertise a capability we don't run. The integration contract below
    # documents exactly what to implement to turn it on.
    _IMPLEMENTED = False

    def available(self, ctx) -> bool:
        if not self._IMPLEMENTED or not os.environ.get("AIGEN_WEIGHTS"):
            return False
        try:
            import open_clip  # noqa: F401
            import torch  # noqa: F401

            return True
        except Exception:
            return False

    def run(self, ctx) -> ToolResult:
        # Contract for enabling (UniversalFakeDetect, MIT): load the frozen CLIP
        # ViT-L backbone + the linear head from AIGEN_WEIGHTS, score each image's
        # synthetic-probability, and assert non_original_image above a validated
        # threshold. Until _IMPLEMENTED is True this is never reached.
        return self._skip("aigen adapter not implemented in this build")
