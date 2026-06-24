"""Pluggable model backends behind one tiny interface.

Each provider implements .complete_json(system, parts, model, max_tokens) and
returns a ProviderResponse. `parts` is a list of str (text) or Path (image).
This lets us mix the cheapest capable model per tier (e.g. Gemini Flash for
perception, Claude Sonnet for judgment) or swap in a local OSS VLM later.
"""

from __future__ import annotations

from . import mock
from .base import ProviderResponse

__all__ = ["ProviderResponse", "get_provider"]


def get_provider(name: str, config):
    name = (name or "mock").lower()
    if name == "mock":
        return mock.MockProvider()
    if name == "gemini":
        from . import gemini

        return gemini.GeminiProvider(config.key_for("gemini"))
    if name == "claude":
        from . import claude

        return claude.ClaudeProvider(config.key_for("claude"))
    if name == "openai":
        from . import openai_provider

        return openai_provider.OpenAIProvider(config.key_for("openai"))
    raise ValueError(f"unknown provider: {name}")
