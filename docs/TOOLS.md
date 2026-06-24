# Tools — Pluggable Scenario Detectors

A **Tool** is an independent capability that inspects a `ClaimContext` and returns
a `ToolResult` (signals + deterministic `risk_flags` + evidence). Tools are the
unit of extensibility (Principle P5) and the basis for defense-in-depth (P8):
several independent detectors cross-check the VLM judge, so gaming one layer is
not enough.

## Interface (`harness/tool.py`)

```python
class Tool:
    name: str            # unique id, used in registry + scenario `tools:` lists
    tier: str            # context | forensic | consistency | perception
    produces_flags: tuple # risk flags this tool may assert (documented)
    optional: bool       # optional tools may be unavailable without breaking a run

    def available(self, ctx) -> bool   # capability detection (deps/weights present?)
    def run(self, ctx) -> ToolResult   # produce signals + risk_flags + evidence
```

`ToolResult`: `{ name, available, signals, risk_flags, evidence, note, error }`.

## Registered tools (`tools/`)

| Tool | Tier | Asserts | Backend | Default |
|---|---|---|---|---|
| `quality` | context | `blurry_image`, `low_light_or_glare`, `cropped_or_obstructed` | OpenCV/NumPy (Tier-0) | LIVE |
| `provenance` | forensic | `non_original_image` | imagehash + EXIF + c2pa(opt) | LIVE |
| `forgery` | forensic | `possible_manipulation` (conservative) | ELA (numpy/PIL) | LIVE |
| `ocr_injection` | forensic | `text_instruction_present` | perception + EasyOCR/Tesseract(opt) | LIVE |
| `object_consistency` | consistency | `wrong_object` | open_clip ViT-B-32 | adapter (opt) |
| `aigen` | forensic | `non_original_image`, `possible_manipulation` | UniversalFakeDetect/Corvi2023 | adapter (opt) |

LIVE tools run with the core dependencies. Adapter tools call `available()` and
**self-disable** cleanly when their optional deps/weights are absent (P12); the
run still completes and the trace records that coverage was reduced.

## Execution & fusion
1. The `ToolRegistry` runs every `active()` tool (allowed by the scenario pack
   and available). A tool exception is caught and recorded — it never breaks the claim.
2. Tool-asserted `risk_flags` are **unioned** into the final decision in
   `pipeline._fuse()` — deterministic signals always surface regardless of the model.
3. Tool `note`/`risk_flags` are also passed to the judge as *corroborating
   evidence* so the model reasons with them (it should not silently discard them).

## Adding a tool (no core changes)
```python
# tools/my_detector.py
from ..harness.tool import Tool, ToolResult
class MyDetector(Tool):
    name = "my_detector"; tier = "forensic"; produces_flags = ("possible_manipulation",)
    optional = True
    def available(self, ctx):  # check imports / weights
        ...
    def run(self, ctx):
        return ToolResult(name=self.name, risk_flags=[...], evidence={...}, note="...")
```
Then add it to `tools/__init__.py::default_registry()`. Optionally restrict it to
specific objects via a scenario pack's `tools:` list. See [SCENARIOS.md](./SCENARIOS.md).
