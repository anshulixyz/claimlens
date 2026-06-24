"""Tier 0 — deterministic context builders (FREE, no model calls).

This is the cheap anti-gaming / quality layer. For each image it computes
blur, exposure/glare, resolution, EXIF/provenance presence and a perceptual
hash. Across a claim's images it detects reused / duplicate images. These
signals become risk hints for the judge and keep the expensive model honest.

Everything degrades gracefully: cv2 and imagehash are optional; PIL+numpy
are sufficient. No signal here ever costs an API call.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2  # optional, sharper Laplacian

    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False

try:
    import imagehash  # optional, robust perceptual hash

    _HAS_IMAGEHASH = True
except Exception:
    _HAS_IMAGEHASH = False


# --- thresholds (documented, tunable) ---
BLUR_VAR_MIN = 80.0  # variance of Laplacian below this => likely blurry
DARK_MEAN_MAX = 45.0  # mean luma below this => low light
BRIGHT_MEAN_MIN = 215.0  # mean luma above this => washed out
GLARE_FRAC_MAX = 0.18  # fraction of near-saturated pixels => glare
SMALL_SIDE_MIN = 256  # min shorter side for "usable" detail
DUP_HAMMING_MAX = 5  # perceptual-hash distance => near-duplicate


def _laplacian_var(gray: np.ndarray) -> float:
    if _HAS_CV2:
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # numpy 3x3 Laplacian fallback
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
    g = gray.astype(np.float64)
    p = np.pad(g, 1, mode="edge")
    out = (
        k[0, 1] * p[:-2, 1:-1]
        + k[1, 0] * p[1:-1, :-2]
        + k[1, 1] * p[1:-1, 1:-1]
        + k[1, 2] * p[1:-1, 2:]
        + k[2, 1] * p[2:, 1:-1]
    )
    return float(out.var())


def _phash(img: Image.Image):
    if _HAS_IMAGEHASH:
        return imagehash.phash(img)
    # average-hash fallback -> int
    g = np.asarray(img.convert("L").resize((8, 8)), dtype=np.float64)
    bits = (g > g.mean()).flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return val


def _hamming(a, b) -> int:
    if _HAS_IMAGEHASH:
        return int(a - b)
    return bin(int(a) ^ int(b)).count("1")


def analyze_image(path: Path) -> dict:
    """Per-image deterministic signals + derived quality risk hints."""
    info = {
        "image_id": path.stem,
        "exists": path.exists(),
        "risk_hints": [],
    }
    if not path.exists():
        info["risk_hints"] = ["damage_not_visible"]
        info["usable"] = False
        info["note"] = "file missing"
        return info

    try:
        img = Image.open(path)
        img.load()
    except Exception as e:
        info["usable"] = False
        info["note"] = f"unreadable image: {e}"
        info["risk_hints"] = ["damage_not_visible"]
        return info

    rgb = img.convert("RGB")
    w, h = rgb.size
    arr = np.asarray(rgb, dtype=np.float64)
    luma = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]

    blur_var = _laplacian_var(luma)
    mean_luma = float(luma.mean())
    glare_frac = float((luma > 245).mean())
    dark_frac = float((luma < 15).mean())
    small_side = min(w, h)

    # EXIF / provenance presence (camera-captured images usually carry EXIF;
    # screenshots / re-saved / generated images often have none).
    exif = {}
    try:
        raw = rgb.getexif()
        exif = {k: str(v)[:60] for k, v in raw.items()} if raw else {}
    except Exception:
        exif = {}
    has_camera_exif = any(
        t in exif for t in (271, 272, 306, 36867)
    )  # Make/Model/DateTime/DateTimeOriginal

    hints = []
    if blur_var < BLUR_VAR_MIN:
        hints.append("blurry_image")
    if mean_luma < DARK_MEAN_MAX or mean_luma > BRIGHT_MEAN_MIN or glare_frac > GLARE_FRAC_MAX:
        hints.append("low_light_or_glare")
    if small_side < SMALL_SIDE_MIN:
        hints.append("cropped_or_obstructed")

    usable = (blur_var >= BLUR_VAR_MIN * 0.5) and small_side >= 64

    info.update(
        {
            "width": w,
            "height": h,
            "small_side": small_side,
            "aspect": round(w / h, 3) if h else None,
            "blur_var": round(blur_var, 1),
            "mean_luma": round(mean_luma, 1),
            "glare_frac": round(glare_frac, 3),
            "dark_frac": round(dark_frac, 3),
            "has_exif": bool(exif),
            "has_camera_exif": has_camera_exif,
            "_phash": _phash(rgb),
            "usable": usable,
            "risk_hints": hints,
        }
    )
    return info


def analyze_claim_images(paths: list[Path]) -> dict:
    """Per-image analysis + cross-image provenance (duplicate detection)."""
    per_image = [analyze_image(p) for p in paths]

    # cross-image near-duplicate / reuse detection
    dup_flags = set()
    valid = [m for m in per_image if m.get("_phash") is not None]
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            try:
                d = _hamming(valid[i]["_phash"], valid[j]["_phash"])
            except Exception:
                continue
            if d <= DUP_HAMMING_MAX:
                dup_flags.add(valid[i]["image_id"])
                dup_flags.add(valid[j]["image_id"])

    # provenance: no image carries camera EXIF at all -> reuse/non-original hint
    any_camera_exif = any(m.get("has_camera_exif") for m in per_image)

    claim_hints = []
    if dup_flags:
        claim_hints.append("non_original_image")
    if len(per_image) >= 1 and not any_camera_exif:
        # soft signal only — many valid web images also lack EXIF
        claim_hints.append("provenance_unverified")

    # strip non-serializable phash before returning
    for m in per_image:
        m.pop("_phash", None)

    return {
        "images": per_image,
        "duplicate_image_ids": sorted(dup_flags),
        "any_camera_exif": any_camera_exif,
        "claim_level_hints": claim_hints,
        "cv_backend": "opencv" if _HAS_CV2 else "numpy",
        "phash_backend": "imagehash" if _HAS_IMAGEHASH else "ahash-fallback",
    }
