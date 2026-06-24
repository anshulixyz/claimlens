"""Configuration: paths, model backends, env loading.

Secrets come from env / code/.env ONLY (never hardcoded). If python-dotenv is
installed we load code/.env automatically so `python code/main.py` just works.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo layout ---------------------------------------------------------------
# The package lives at the repo root, so CODE_DIR == REPO_ROOT.
CODE_DIR = Path(__file__).resolve().parent.parent  # repo root
REPO_ROOT = CODE_DIR
DATASET_DIR = REPO_ROOT / "dataset"  # ships a tiny SYNTHETIC sample; point at your own
CACHE_DIR = CODE_DIR / ".cache"

CLAIMS_CSV = DATASET_DIR / "claims.csv"
SAMPLE_CSV = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQ_CSV = DATASET_DIR / "evidence_requirements.csv"


# Load code/.env if present (no hard dependency) ----------------------------
def _load_env():
    try:
        from dotenv import load_dotenv

        load_dotenv(CODE_DIR / ".env")
    except Exception:
        # minimal fallback parser so the project still works without dotenv
        envf = CODE_DIR / ".env"
        if envf.exists():
            for line in envf.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _env(key, default=None):
    v = os.environ.get(key)
    return v if v not in (None, "") else default


class Config:
    """Resolved runtime config. Provider falls back to 'mock' when no key."""

    def __init__(
        self, perception_provider=None, perception_model=None, judge_provider=None, judge_model=None
    ):
        self.gemini_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
        self.anthropic_key = _env("ANTHROPIC_API_KEY")
        self.openai_key = _env("OPENAI_API_KEY")

        self.perception_provider = perception_provider or _env("PERCEPTION_PROVIDER", "gemini")
        self.perception_model = perception_model or _env(
            "PERCEPTION_MODEL", "gemini-2.5-flash-lite"
        )
        self.judge_provider = judge_provider or _env("JUDGE_PROVIDER", "claude")
        self.judge_model = judge_model or _env("JUDGE_MODEL", "claude-sonnet-4-6")

        self.max_concurrency = int(_env("MAX_CONCURRENCY", "4"))

        # Auto-downgrade to mock when the required key is missing, so the
        # pipeline + evaluation always run end-to-end (offline reproducible).
        self.perception_provider = self._resolve(self.perception_provider)
        self.judge_provider = self._resolve(self.judge_provider)

    def _resolve(self, provider):
        provider = (provider or "mock").lower()
        if provider == "gemini" and not self.gemini_key:
            return "mock"
        if provider == "claude" and not self.anthropic_key:
            return "mock"
        if provider == "openai" and not self.openai_key:
            return "mock"
        return provider

    def key_for(self, provider):
        return {
            "gemini": self.gemini_key,
            "claude": self.anthropic_key,
            "openai": self.openai_key,
        }.get(provider)

    def summary(self):
        return (
            f"perception={self.perception_provider}:{self.perception_model} | "
            f"judge={self.judge_provider}:{self.judge_model} | "
            f"concurrency={self.max_concurrency}"
        )
