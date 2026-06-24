"""ToolRegistry — registration, capability detection, ordered execution (P5).

Tools register themselves; the registry runs the available ones and collects
their results. Adding a scenario detector = add a Tool subclass + register it.
A scenario pack can also restrict which tools run via `scenario['tools']`.
"""

from __future__ import annotations

from .tool import Tool, ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: list[Tool] = []

    def register(self, tool: Tool):
        self._tools.append(tool)
        return self

    def register_all(self, tools):
        for t in tools:
            self.register(t)
        return self

    @property
    def tools(self):
        return list(self._tools)

    def active(self, ctx) -> list[Tool]:
        """Tools that are (a) allowed by the scenario pack and (b) available."""
        allow = None
        if ctx.scenario:
            allow = ctx.scenario.get("tools")  # None => all
        out = []
        for t in self._tools:
            if allow is not None and t.name not in allow:
                continue
            try:
                if t.available(ctx):
                    out.append(t)
            except Exception:
                continue
        return out

    def run_all(self, ctx) -> list[ToolResult]:
        results = []
        for t in self.active(ctx):
            try:
                res = t.run(ctx)
            except Exception as e:  # a tool failure never breaks the claim (P12)
                res = ToolResult(
                    name=t.name, available=False, error=str(e), note=f"tool error: {e}"
                )
            results.append(res)
        return results

    def manifest(self) -> list[dict]:
        """Static description of registered tools (for docs / introspection)."""
        return [
            {
                "name": t.name,
                "tier": t.tier,
                "optional": t.optional,
                "produces_flags": list(t.produces_flags),
            }
            for t in self._tools
        ]
