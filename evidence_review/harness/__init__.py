"""Agentic harness core: tools, registry, trace, escalation.

The harness is the "OS" around the model (see docs/HARNESS_PRINCIPLES.md):
pluggable Tools behind a Registry, a structured Trace for observability, and an
Escalation policy for human-in-the-loop routing.
"""

from .context import ClaimContext
from .escalation import EscalationPolicy
from .registry import ToolRegistry
from .tool import Tool, ToolResult
from .trace import ClaimTrace

__all__ = ["Tool", "ToolResult", "ClaimContext", "ToolRegistry", "ClaimTrace", "EscalationPolicy"]
