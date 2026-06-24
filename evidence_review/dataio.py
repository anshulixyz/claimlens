"""Loading claims / history / requirements, and image path resolution."""

from __future__ import annotations

import csv
from pathlib import Path

from . import config


def read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_user_history() -> dict[str, dict]:
    rows = read_csv(config.USER_HISTORY_CSV)
    return {r["user_id"]: r for r in rows}


def load_evidence_requirements() -> list[dict]:
    return read_csv(config.EVIDENCE_REQ_CSV)


def requirements_for_object(reqs: list[dict], claim_object: str) -> list[dict]:
    co = (claim_object or "").lower()
    return [r for r in reqs if r["claim_object"] in (co, "all")]


def image_id(path: str) -> str:
    """filename without extension, e.g. images/.../img_1.jpg -> img_1"""
    return Path(path).stem


def split_image_paths(image_paths: str) -> list[str]:
    return [p.strip() for p in (image_paths or "").split(";") if p.strip()]


def resolve_image(rel_path: str) -> Path:
    """Resolve a CSV image path against the dataset dir, with a path-traversal guard.

    Image paths come from an untrusted CSV. We resolve them inside DATASET_DIR and
    reject anything that escapes it (e.g. '../../etc/passwd'), so a malicious row
    cannot make the pipeline read arbitrary files. Returns a sentinel
    non-existent path on violation; the intake protocol then marks it MISSING.
    """
    rel = (rel_path or "").strip().lstrip("/")
    base = config.DATASET_DIR.resolve()
    candidate = (config.DATASET_DIR / rel).resolve()
    try:
        candidate.relative_to(base)  # raises if candidate escapes the dataset dir
    except ValueError:
        return config.DATASET_DIR / "__rejected_path__"
    return candidate
