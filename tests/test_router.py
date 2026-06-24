"""ModelRouter — qualification gate, ranking, fallback, circuit-breaker."""

from evidence_review.router import ModelRouter
from evidence_review.usage import UsageTracker


class _Cfg:
    """Stub config: declares which provider keys are 'present' (no real keys)."""

    def __init__(
        self,
        pp="gemini",
        pm="gemini-2.5-flash-lite",
        jp="claude",
        jm="claude-sonnet-4-6",
        keys=("gemini", "claude", "openai"),
    ):
        self.perception_provider, self.perception_model = pp, pm
        self.judge_provider, self.judge_model = jp, jm
        self._keys = set(keys)

    def key_for(self, p):
        return "k" if p in self._keys else None


def _names(router, role):
    return [m.model for m in router.candidates(role)]


def test_judge_requires_reasoning_capability():
    r = ModelRouter(_Cfg(), UsageTracker())
    js = _names(r, "judge")
    assert "gemini-2.5-flash-lite" not in js  # lacks 'reasoning' -> unqualified
    assert js[-1] == "mock"  # mock is always the final backstop


def test_perception_cheapest_qualified_first_mock_last():
    r = ModelRouter(_Cfg(), UsageTracker())
    ps = _names(r, "perception")
    assert ps[0] == "gemini-2.5-flash-lite"  # cheapest qualified (preference) first
    assert ps[-1] == "mock"


def test_circuit_breaker_excludes_downed_model():
    r = ModelRouter(_Cfg(jp="gemini", jm="gemini-2.5-flash"), UsageTracker())
    assert "gemini-2.5-flash" in _names(r, "judge")
    r._down.add("gemini-2.5-flash")  # simulate a permanent failure this run
    assert "gemini-2.5-flash" not in _names(r, "judge")  # fell out -> fallback to next


def test_missing_key_excludes_provider():
    r = ModelRouter(_Cfg(keys=("gemini",)), UsageTracker())  # only Gemini key present
    js = _names(r, "judge")
    assert all("claude" not in m and "gpt" not in m for m in js if m != "mock")
    assert "gemini-2.5-flash" in js  # Gemini still qualifies for judge


def test_explicit_mock_forces_mock_only():
    r = ModelRouter(_Cfg(jp="mock"), UsageTracker())
    assert _names(r, "judge") == ["mock"]  # keeps tests/offline hermetic
