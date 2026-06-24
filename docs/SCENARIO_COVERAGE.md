# Scenario Coverage — Open-Source Detectors

How we extend scenario coverage with open-source projects so the VLM judge is
**cross-checked by independent signals** and the system is hard to game (P8).
Every project below was verified to exist (mid-2026) with its license read off
the source. Legend: 🟢 permissive (MIT/Apache/BSD) · 🟡 non-commercial weights/data ·
🔴 copyleft (GPL/AGPL) — do not link into the pipeline.

> Selection rule: **license is the filter, not capability.** The strongest
> drop-in models (YOLO-World, Ultralytics damage models, pyiqa) are non-permissive,
> so the LIVE tier deliberately leans on classical forensics + provenance +
> robust hashing + zero-shot CLIP, and documents the heavy/encumbered models as
> opt-in adapters.

---

## What we run LIVE (CPU, permissive, dependency-light)

| Tool (this repo) | OSS basis | License | Serves | Status |
|---|---|---|---|---|
| `quality` | OpenCV / NumPy Laplacian + luminance/glare | 🟢 Apache/BSD | `blurry_image`, `low_light_or_glare`, `cropped_or_obstructed` | **live** |
| `provenance` | imagehash (pHash) + Pillow EXIF + **c2pa-python** (optional) | 🟢 BSD / MIT-Apache | `non_original_image`, authenticity | **live** (C2PA optional) |
| `forgery` | DIY **Error Level Analysis** (numpy/PIL); algorithm ref: Sherloq | 🟢 our code (Sherloq 🔴 GPL = ref only) | `possible_manipulation` (evidence-only; off by default) | **live** |
| `ocr_injection` | perception signal + **EasyOCR**/**pytesseract** (optional) | 🟢 Apache | `text_instruction_present` | **live** (perception-backed; OCR optional) |
| `object_consistency` | **open_clip** ViT-B-32 (OpenAI weights) | 🟢 MIT/Apache | `wrong_object` (+ drives the pre-judge **short-circuit**) | **live** (CPU, free; `pip install torch open_clip_torch`) |

The genuinely load-bearing OSS today: **imagehash** (reuse → `non_original_image`),
**OpenCV** (quality gating), and **open_clip** (independent wrong-object check that
also lets the pipeline skip the expensive judge on junk/gaming — see the
short-circuit in [MODEL_ROUTING.md](./MODEL_ROUTING.md)). ELA is a deliberately weak,
evidence-only prior; OCR/C2PA are optional cross-checks (perception already covers
in-image text for free).

## Adapter-ready (documented contract; self-disable unless deps/weights present)

| Tool | OSS basis | License | Serves | Enable |
|---|---|---|---|---|
| `aigen` | **UniversalFakeDetect** (MIT) / **Corvi2023 ClipBased** (Apache) | 🟢 MIT/Apache | `non_original_image`, `possible_manipulation` | set `AIGEN_WEIGHTS=...` + torch/open_clip |

---

## Full survey by scenario family

### 1. Manipulation / forgery localization → `possible_manipulation`
- **DIY ELA / JPEG-ghost / double-JPEG / noise-variance** — 🟢 our numpy/PIL code, CPU-ms, no weights → **LIVE**. (Sherloq 🔴 GPL-3.0 used as *algorithm reference only*.)
- **TruFor** (grip-unina) — strong splice/copy-move localization, 🟡 **non-commercial** + GPU → adapter, license-gated.
- **CAT-Net**, **MVSS-Net**, **ManTraNet** — GPU/stale-stack and/or non-commercial/unknown license → avoid or adapter only.
- **IMDL-BenCo** (scu-zjz) — 🟢 unifies CAT-Net/IML-ViT/PSCC-Net behind one interface; the cleanest path if a neural localizer is ever added (GPU).

### 2. AI-generated / synthetic detection → `non_original_image`, `possible_manipulation`
- **UniversalFakeDetect** (WisconsinAIVision) — 🟢 **MIT**, frozen CLIP ViT-L + linear head, **CPU-feasible** → best-licensed adapter (`aigen`).
- **Corvi2023 / ClipBased-SyntheticImageDetection** (grip-unina) — 🟢 **Apache-2.0**, CLIP-feature LLR, generalizes across generators → adapter.
- **AIDE** (ICLR'25) — 🟢 MIT but **GPU-required** → adapter.
- **Organika/sdxl-detector** (HF) — 🟡 **CC-BY-NC**; CPU-fine and popular but non-commercial → demo only, not shipped.

### 3. Zero-shot object / part presence → `wrong_object`, `wrong_object_part`, `claim_mismatch`
- **open_clip ViT-B-32** — 🟢 MIT, ~350 MB (OpenAI weights), CPU sub-second → **LIVE** in `object_consistency`; conservatively thresholded (gap > 0.05; 0/20 false positives on valid samples) and wired into the pre-judge short-circuit.
- **OWL-ViT / OWLv2** — 🟢 Apache, text-conditioned box detection of a *part* → adapter.
- **GroundingDINO** — 🟢 Apache, stronger open-vocab detection (`--cpu-only`) → adapter for box-level part checks.
- **Grounded-SAM** — 🟢 Apache, adds masks (damage-area %) → heavy adapter.
- **YOLO-World / Ultralytics** — 🔴 **GPL/AGPL** → **avoid** (copyleft).

### 4. Damage / defect corroboration → `issue_type`, `claim_mismatch`
- No fully-permissive CPU-light model covers car+laptop+package. Treat as adapter.
- **Anomalib** (openvinotoolkit) — 🟢 Apache, generic surface-anomaly (PatchCore/PADIM); needs "normal" references → most license-safe damage adapter.
- **CarDD** dataset — 🟡 non-commercial (Flickr/Shutterstock); research fine-tune only.
- **Roboflow car/parcel damage YOLO** — ⚠️ often AGPL backbone; per-model license check.
- **LCFC-Laptop** dataset (Sensors 2025) — academic; verify before commercial use.

### 5. OCR / in-image text (prompt-injection defense) → `text_instruction_present`
- **EasyOCR** — 🟢 Apache, pip-only, CPU (~80–100 MB) → primary OCR for `ocr_injection`.
- **pytesseract + Tesseract** — 🟢 Apache, tiny, CPU-native → secondary cross-check.
- **PaddleOCR** — 🟢 Apache, highest accuracy, heavier dep → adapter.
- **docTR** — 🟢 Apache, MobileNet backbones → adapter.
- *(none of the forensics models detect overlaid instruction text — OCR is the right tool.)*

### 6. Provenance & robust hashing → `non_original_image`, authenticity
- **c2pa-python** (contentauth) — 🟢 MIT/Apache, pure CPU, prebuilt macOS wheels → **the only cryptographically hard provenance signal**; LIVE-optional in `provenance`.
- **piexif** — 🟢 MIT, EXIF anomaly / editor-software / timestamp checks → LIVE.
- **imagehash** — 🟢 BSD, pHash/aHash/dHash (already used) → LIVE.
- **pdqhash** (Meta PDQ) — 🟢 MIT, 256-bit DCT hash + quality, more robust to resize/recompress than pHash → recommended LIVE upgrade alongside imagehash.

### 7. Image quality (no-reference) → `blurry_image`, `low_light_or_glare`
- **OpenCV** Laplacian + luminance/saturation heuristics — 🟢 Apache → LIVE (in `quality`).
- **OpenCV-contrib `cv2.quality.QualityBRISQUE`** — 🟢 Apache, license-clean BRISQUE → optional LIVE upgrade.
- **pyiqa (IQA-PyTorch)** — 🔴/🟡 **PolyForm Noncommercial** → avoid in shipped pipeline (reimplement BRISQUE/NIQE instead).

---

## Explicitly avoided in the shipped pipeline
- 🔴 **YOLO-World / Ultralytics YOLO** damage models (GPL/AGPL copyleft).
- 🟡 **pyiqa** (PolyForm Noncommercial) — use OpenCV-contrib BRISQUE.
- 🟡 **CarDD / MVTec / Organika sdxl-detector** (non-commercial weights/data) — research/demo only.

## How to add a new detector (extensibility)
1. Subclass `harness.Tool`, implement `available(ctx)` and `run(ctx) -> ToolResult`.
2. Assert any deterministic `risk_flags` it is confident about; put soft signals in `evidence`.
3. Register it in `tools/__init__.py::default_registry()`.
4. (Optional) restrict it to scenarios via a pack's `tools:` list.
No pipeline or judge changes needed — see [TOOLS.md](./TOOLS.md).
