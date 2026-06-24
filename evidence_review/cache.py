"""Content-addressed JSON cache.

Perception is keyed by (image content hash + model + prompt version), so
re-running the pipeline costs $0 for unchanged images. This is both a cost
lever and a reproducibility guarantee.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import config


def file_sha1(path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


class JsonCache:
    def __init__(self, namespace: str, enabled: bool = True):
        self.dir = config.CACHE_DIR / namespace
        self.enabled = enabled
        if enabled:
            self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str):
        if not self.enabled:
            return None
        p = self._path(key)
        if p.exists():
            self.hits += 1
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        self.misses += 1
        return None

    def set(self, key: str, value):
        if not self.enabled:
            return
        self._path(key).write_text(json.dumps(value, ensure_ascii=False, indent=2))
