"""OcrInjectionTool — in-image instruction / prompt-injection detection (LIVE).

Defense in depth for `text_instruction_present`:
  - PRIMARY (free): the perception tier already reports `text_in_image` /
    `instruction_text_present` per image — we always have this signal.
  - SECONDARY (optional, deterministic): if EasyOCR (Apache) or pytesseract
    (Apache) is installed, OCR each image and scan for instruction-like phrases.
    This is an independent, model-free cross-check that is harder to game.

Self-disables the OCR pass gracefully if neither OCR lib is present; the
perception-backed signal still works. See docs/SCENARIO_COVERAGE.md.
"""

from __future__ import annotations

import re

from ..harness.tool import Tool, ToolResult

# instruction-like phrases an attacker might paint into an image
_INJECTION_PATTERNS = re.compile(
    r"\b(ignore|disregard|approve|accept|mark|override|system\s*prompt|"
    r"you\s+must|as\s+an?\s+ai|reimburse|pay\s+out|authoriz|valid\s+claim|"
    r"damaged|pre[- ]?existing)\b",
    re.IGNORECASE,
)


# --- optional OCR backends (lazy) ---
def _get_ocr():
    try:
        import easyocr  # Apache-2.0

        return ("easyocr", easyocr)
    except Exception:
        pass
    try:
        import pytesseract  # Apache-2.0 (needs tesseract binary)

        return ("pytesseract", pytesseract)
    except Exception:
        pass
    return (None, None)


class OcrInjectionTool(Tool):
    name = "ocr_injection"
    tier = "forensic"
    produces_flags = ("text_instruction_present",)
    optional = False  # perception-backed path always available

    def __init__(self):
        self._backend, self._mod = _get_ocr()
        self._reader = None

    def _ocr_text(self, path):
        if self._backend == "easyocr":
            if self._reader is None:
                self._reader = self._mod.Reader(["en"], gpu=False, verbose=False)
            return " ".join(self._reader.readtext(str(path), detail=0))
        if self._backend == "pytesseract":
            from PIL import Image

            return self._mod.image_to_string(Image.open(path))
        return ""

    def run(self, ctx) -> ToolResult:
        flags, detected = set(), []

        # PRIMARY: perception signals (free)
        for p in ctx.perceptions:
            if p.get("instruction_text_present") or p.get("text_in_image"):
                detected.append(
                    {
                        "image_id": p.get("_image_id"),
                        "source": "perception",
                        "instruction": bool(p.get("instruction_text_present")),
                    }
                )
                if p.get("instruction_text_present"):
                    flags.add("text_instruction_present")

        # SECONDARY: deterministic OCR cross-check (optional)
        if self._backend:
            for p in ctx.abs_paths:
                if not p.exists():
                    continue
                try:
                    text = self._ocr_text(p)
                except Exception:
                    continue
                if text and _INJECTION_PATTERNS.search(text):
                    flags.add("text_instruction_present")
                    detected.append(
                        {
                            "image_id": p.stem,
                            "source": self._backend,
                            "snippet": " ".join(text.split())[:120],
                        }
                    )

        note = (
            f"ocr_backend={self._backend or 'none(perception-only)'}; "
            f"instruction_text={'yes' if 'text_instruction_present' in flags else 'no'}"
        )
        return ToolResult(
            name=self.name,
            available=True,
            signals={"ocr_backend": self._backend, "detections": detected},
            risk_flags=sorted(flags),
            evidence={"in_image_text": detected},
            note=note,
        )
