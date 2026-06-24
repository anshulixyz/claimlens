"""ClaimTrace — structured, auditable record of one decision (P10).

Captures the full chain: inputs → tool signals → perceptions → judge raw →
escalation → final row. Written to code/.cache/traces/<user>_<n>.json when
tracing is enabled, so every decision is debuggable and explainable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ClaimTrace:
    user_id: str
    claim_object: str
    tools: list = field(default_factory=list)  # [{name, available, risk_flags, note, signals}]
    perceptions: list = field(default_factory=list)
    judge_raw: dict = field(default_factory=dict)
    escalation: dict = field(default_factory=dict)
    final: dict = field(default_factory=dict)
    scenario: str = ""

    def add_tool(self, res):
        self.tools.append(
            {
                "name": res.name,
                "available": res.available,
                "risk_flags": list(res.risk_flags),
                "note": res.note,
                "error": res.error,
                "signals": res.signals,
            }
        )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "claim_object": self.claim_object,
            "scenario": self.scenario,
            "tools": self.tools,
            "perceptions": self.perceptions,
            "judge_raw": self.judge_raw,
            "escalation": self.escalation,
            "final": self.final,
        }

    def save(self, cache_dir, idx):
        d = cache_dir / "traces"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{self.user_id}_{idx}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
        return path
