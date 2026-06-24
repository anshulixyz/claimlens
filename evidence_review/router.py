"""ModelRouter — capability-based model selection, qualification & fallback.

The blog "anatomy of an agent harness" enumerates 11 harness components but
explicitly does NOT cover model routing/fallback. This is that missing layer —
the industry-standard model-gateway pattern (cf. LiteLLM / OpenRouter):

- A **catalog** declares each model's capabilities + cost/quality tiers.
- A **role spec** declares the capabilities a role REQUIRES. A model may only
  serve a role if it MEETS those expectations (qualification gate) — "if a model
  meets the bar, it can be the reviewer," not a hardcoded choice.
- **Ordered fallback + circuit-breaker:** the router tries the best qualified,
  available model; on a permanent failure (credit/auth) or exhausted transient
  retries it marks that model down for the run and falls back to the next
  qualified model — so e.g. Claude running out of credits auto-falls to Gemini
  with no config edit. `mock` is always the final, always-available backstop.

The pipeline is a fixed DAG (perceive → tools → judge → fuse), not a ReAct loop,
so we don't need LangGraph; but each step is a discrete node (see pipeline.py),
so a future LangGraph port is mechanical. Selection is data-driven here, not
hardcoded in the call sites.
"""

from __future__ import annotations

from dataclasses import dataclass

from .providers import get_provider
from .providers.base import ProviderResponse

# permanent failures: don't retry, don't keep this model this run
_PERMANENT = (
    "credit",
    "billing",
    "quota",
    "invalid api key",
    "authentication",
    "permission",
    "not found",
    "does not exist",
    "401",
    "403",
    "404",
)


@dataclass(frozen=True)
class ModelSpec:
    model: str
    provider: str
    caps: frozenset  # e.g. {"vision","json","reasoning","strong"}
    cost: int  # 0 cheapest .. 5 priciest
    quality: int  # 0 weakest .. 5 strongest


# Declared capability catalog (extend as providers change).
CATALOG = [
    ModelSpec("gemini-2.5-flash-lite", "gemini", frozenset({"vision", "json"}), 1, 2),
    ModelSpec("gemini-2.5-flash", "gemini", frozenset({"vision", "json", "reasoning"}), 2, 3),
    ModelSpec(
        "claude-haiku-4-5-20251001", "claude", frozenset({"vision", "json", "reasoning"}), 2, 3
    ),
    ModelSpec(
        "claude-sonnet-4-6", "claude", frozenset({"vision", "json", "reasoning", "strong"}), 4, 5
    ),
    ModelSpec("gpt-4o", "openai", frozenset({"vision", "json", "reasoning", "strong"}), 4, 5),
    ModelSpec("mock", "mock", frozenset({"vision", "json", "reasoning", "strong"}), 0, 0),
]

# Role -> required capabilities + how to rank qualified candidates.
ROLES = {
    # perception: must see images + emit json; pick the CHEAPEST that qualifies.
    "perception": {
        "requires": frozenset({"vision", "json"}),
        "rank": lambda m: (m.cost, -m.quality),
    },
    # judge: must reason + emit json; pick the STRONGEST that qualifies.
    "judge": {"requires": frozenset({"json", "reasoning"}), "rank": lambda m: (-m.quality, m.cost)},
}


def _is_permanent(err: Exception) -> bool:
    return any(t in str(err).lower() for t in _PERMANENT)


class ModelRouter:
    def __init__(self, config, usage):
        self.cfg = config
        self.usage = usage
        self._providers = {}  # provider name -> instance (lazy)
        self._down = set()  # circuit-breaker: model ids down this run
        self._catalog = {m.model: m for m in CATALOG}

    # --- availability + qualification ---
    def _key_present(self, provider: str) -> bool:
        return provider == "mock" or bool(self.cfg.key_for(provider))

    def _override(self, role: str):
        """Explicit Config preference for a role (provider+model), if any."""
        if role == "perception":
            return self.cfg.perception_provider, self.cfg.perception_model
        return self.cfg.judge_provider, self.cfg.judge_model

    def candidates(self, role: str) -> list[ModelSpec]:
        spec = ROLES[role]
        prov_pref, model_pref = self._override(role)

        # Explicit mock => force mock only (keeps tests/offline hermetic).
        if prov_pref == "mock":
            return [self._catalog["mock"]]

        # real (non-mock) qualified models, ranked; mock is handled separately so
        # it is ALWAYS the final backstop, never a mid-list fallback.
        qualified = [
            m
            for m in CATALOG
            if m.provider != "mock"
            and spec["requires"] <= m.caps
            and self._key_present(m.provider)
            and m.model not in self._down
        ]
        qualified.sort(key=spec["rank"])

        # Move the explicit preference to the front if it qualifies.
        pref = next(
            (
                m
                for m in qualified
                if m.provider == prov_pref and (m.model == model_pref or model_pref is None)
            ),
            None,
        )
        if pref:
            qualified.remove(pref)
            qualified.insert(0, pref)

        qualified.append(self._catalog["mock"])  # deterministic last-resort backstop
        return qualified

    def _provider(self, name: str):
        if name not in self._providers:
            self._providers[name] = get_provider(name, self.cfg)
        return self._providers[name]

    # --- execute with fallback ---
    def run(
        self, role: str, system: str, parts: list, max_tokens: int = 900, images: int = 0
    ) -> tuple[ProviderResponse, str]:
        last_err = None
        for spec in self.candidates(role):
            try:
                resp = self._provider(spec.provider).complete_json(
                    system=system, parts=parts, model=spec.model, max_tokens=max_tokens
                )
                self.usage.add(
                    resp.input_tokens,
                    resp.output_tokens,
                    images=images,
                    calls=1,
                    tier=role,
                    model=(spec.model if spec.provider != "mock" else "mock"),
                )
                self.usage.set_model(role, spec.model if spec.provider != "mock" else "mock")
                return resp, spec.model
            except Exception as e:  # noqa: BLE001
                last_err = e
                if _is_permanent(e):
                    self._down.add(spec.model)  # don't try this model again this run
                import sys

                print(
                    f"[router] {role} model '{spec.model}' failed ({type(e).__name__}); "
                    f"{'circuit-open, ' if _is_permanent(e) else ''}falling back",
                    file=sys.stderr,
                )
                continue
        raise RuntimeError(f"no model could serve role '{role}': {last_err}")

    def plan(self) -> dict:
        """Introspection: which models qualify for each role right now."""
        return {
            role: [{"model": m.model, "provider": m.provider} for m in self.candidates(role)]
            for role in ROLES
        }
