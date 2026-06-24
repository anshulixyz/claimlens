"""Pluggable scenario-detector Tools (Principle P5 / P8 defense in depth).

Each Tool is an independent capability that produces evidence + deterministic
risk flags. `default_registry()` wires the LIVE (CPU, permissive-license) tools;
adapter tools self-disable unless their optional deps/weights are present.

Open-source coverage and license notes: see docs/SCENARIO_COVERAGE.md.
"""

from __future__ import annotations

from ..harness.registry import ToolRegistry
from .aigen import AiGenAdapterTool
from .forgery import ForgeryTool
from .object_consistency import ObjectConsistencyTool
from .ocr_injection import OcrInjectionTool
from .provenance import ProvenanceTool
from .quality import QualityTool


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register_all(
        [
            # --- LIVE deterministic / free ---
            QualityTool(),  # blur / exposure / glare  (Tier-0 CV)
            ProvenanceTool(),  # EXIF + C2PA + perceptual-hash reuse
            ForgeryTool(),  # ELA / double-JPEG manipulation evidence
            OcrInjectionTool(),  # in-image instruction text (perception-backed + optional OCR)
            # --- ADAPTER-READY (self-disable unless deps/weights present) ---
            AiGenAdapterTool(),  # UniversalFakeDetect / Corvi2023 (optional)
            ObjectConsistencyTool(),  # CLIP zero-shot object check (optional)
        ]
    )
    return reg
