"""Tool interface — every capability is a Tool (Principle P5).

A Tool inspects the ClaimContext and returns a ToolResult: structured signals,
deterministic risk_flags it is willing to assert (with evidence), and any
per-image / claim-level evidence to hand the judge. Tools self-report
availability so optional/heavy ones degrade gracefully (P12).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolResult:
    name: str
    available: bool = True
    signals: dict = field(default_factory=dict)  # arbitrary structured output
    risk_flags: list = field(default_factory=list)  # flags this tool asserts (deterministic)
    evidence: dict = field(default_factory=dict)  # extra evidence for the judge
    note: str = ""  # one-line human summary
    error: str = ""


class Tool:
    """Base class. Subclasses set `name`, `tier`, and implement `run`."""

    name: str = "base"
    tier: str = "context"  # context | forensic | consistency | perception
    # risk flags this tool can produce — documented for SCENARIO_COVERAGE/TOOLS docs
    produces_flags: tuple = ()
    optional: bool = False  # optional tools may be unavailable without breaking the run

    def available(self, ctx) -> bool:
        """Return True if this tool can run in the current environment/context."""
        return True

    def run(self, ctx) -> ToolResult:
        raise NotImplementedError

    def _skip(self, reason: str) -> ToolResult:
        return ToolResult(name=self.name, available=False, note=reason)
