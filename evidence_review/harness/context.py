"""ClaimContext — the shared, typed working memory passed to every tool.

Principle P2 (context engineering): tools read exactly what they need from a
typed object instead of re-deriving it. Heavy signals (Tier-0 CV, perceptions)
are computed once and shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ClaimContext:
    # --- raw inputs ---
    user_id: str
    claim_object: str
    user_claim: str
    image_paths_raw: str
    abs_paths: list[Path] = field(default_factory=list)

    # --- shared, precomputed signals ---
    cv_result: dict = field(default_factory=dict)  # Tier-0 deterministic CV
    admissibility: list = field(default_factory=list)  # intake protocol per image
    perceptions: list[dict] = field(default_factory=list)  # Tier-1 per-image VLM
    user_history: dict | None = None
    requirements: list[dict] = field(default_factory=list)
    scenario: dict = field(default_factory=dict)  # declarative scenario pack

    # --- collaborators ---
    config: Any = None
    usage: Any = None
    cache: Any = None

    def image_ids(self) -> list[str]:
        return [p.stem for p in self.abs_paths]
