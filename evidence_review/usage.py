"""Token / call / cost tracking for the operational analysis.

Prices are public list prices per 1M tokens (approximate, documented in the
evaluation report). Override or extend PRICING as providers change.
"""

from __future__ import annotations

import threading
from collections import defaultdict

# USD per 1M tokens (input, output). Matched by substring of the model id.
# NOTE: order matters — more specific keys (…flash-lite) must precede their
# prefixes (…flash) so substring matching picks the right price.
PRICING = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-flash-lite": (0.10, 0.40),
    "gemini-flash": (0.30, 2.50),
    "claude-haiku": (0.80, 4.00),
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "mock": (0.0, 0.0),
}


def price_for(model: str):
    for key, p in PRICING.items():
        if key in (model or "").lower():
            return p
    return (0.0, 0.0)  # unknown -> 0, noted in report


class UsageTracker:
    def __init__(self):
        self.calls = 0
        self.images = 0
        self.cache_hits = 0
        self.short_circuits = 0  # claims resolved before the judge (token saver)
        self.by_tier = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "images": 0})
        self.models = {}
        self._lock = threading.Lock()  # the pipeline updates this from N worker threads

    def add(self, in_tok, out_tok, images=0, calls=1, tier="?", model=None):
        with self._lock:
            self.calls += calls
            self.images += images
            t = self.by_tier[tier]
            t["calls"] += calls
            t["in"] += in_tok or 0
            t["out"] += out_tok or 0
            t["images"] += images
            if model:
                self.models[tier] = model

    def note_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def note_short_circuit(self):
        with self._lock:
            self.short_circuits += 1

    def set_model(self, tier, model):
        self.models[tier] = model

    def cost(self):
        total = 0.0
        breakdown = {}
        for tier, t in self.by_tier.items():
            pin, pout = price_for(self.models.get(tier, ""))
            c = t["in"] / 1e6 * pin + t["out"] / 1e6 * pout
            breakdown[tier] = round(c, 6)
            total += c
        return round(total, 6), breakdown

    def report(self):
        total, breakdown = self.cost()
        return {
            "total_model_calls": self.calls,
            "images_processed": self.images,
            "cache_hits": self.cache_hits,
            "short_circuits": self.short_circuits,
            "by_tier": {k: dict(v) for k, v in self.by_tier.items()},
            "models": self.models,
            "estimated_cost_usd": total,
            "cost_by_tier_usd": breakdown,
        }
