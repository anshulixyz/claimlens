# Model Routing & Fallback

The blog *"The Anatomy of an Agent Harness"* lists 11 harness components but
**explicitly does not cover model routing/fallback**. This is that missing layer —
the industry-standard model-gateway pattern (cf. **LiteLLM**, **OpenRouter**),
implemented in `evidence_review/router.py`. No tier is hardcoded; selection is
capability-driven, with qualification and automatic fallback.

## Why not LangGraph
LangGraph models *stateful ReAct / multi-agent loops with conditional routing*.
Our pipeline is a **fixed DAG** — `perceive → tools → judge → fuse` — with no
agentic loop to manage. The blog's own guidance ("the harness is where the hard
engineering lives", "maximize a single agent first", "complexity should decrease
as models improve") says don't add a framework for its own sake. Each pipeline
step is a discrete node, so a LangGraph port is mechanical *if* real multi-agent
loops are ever added — but today it would add ceremony for no behavioural gain.

## How it works

### 1. Capability catalog (`CATALOG`)
Each model declares capabilities + cost/quality tiers:
```
gemini-2.5-flash-lite : {vision, json}                cost 1 / quality 2
gemini-2.5-flash      : {vision, json, reasoning}     cost 2 / quality 3
claude-haiku-4-5-20251001 : {vision, json, reasoning} cost 2 / quality 3
claude-sonnet-4-6     : {vision, json, reasoning, strong}  cost 4 / quality 5
gpt-4o                : {vision, json, reasoning, strong}  cost 4 / quality 5
mock                  : {all}                          cost 0 / quality 0
```

### 2. Role requirements + ranking (`ROLES`) — the qualification gate
- **perception** requires `{vision, json}`; ranks **cheapest-qualified first**.
- **judge** requires `{json, reasoning}`; ranks **strongest-qualified first**.

A model may serve a role **only if its capabilities ⊇ the role's requirements**
*and* its provider key is present. "If a model meets the bar, it can be the
reviewer" — not a hardcoded pick. (So `gemini-2.5-flash-lite` can perceive but is
**not** allowed to judge — it lacks `reasoning`.)

### 3. Ordered fallback + circuit-breaker
`router.run(role, …)` tries candidates best-first:
- **Permanent error** (credit/billing/quota/auth/404) → mark the model **down for
  the run** (circuit-open) and fall to the next qualified model.
- **Transient error** (503/429/5xx) → the provider already retried with backoff;
  the router then falls to the next model.
- **`mock` is always the final backstop**, so a claim never hard-fails.

Concrete payoff: when **Claude runs out of credits**, the judge auto-falls to
Gemini with **no `.env` edit** — the fragility we hit in testing is now handled
by the router. Usage/cost tracking records the model *actually used*, including
fallbacks.

### 4. Preferences vs hardcoding
`PERCEPTION_PROVIDER/MODEL` and `JUDGE_PROVIDER/MODEL` in `.env` are **preferences**
(moved to the front of the qualified list if they qualify), not hard choices — the
router still falls back if the preferred model is unavailable. Setting a provider
to `mock` forces mock only (keeps tests/offline hermetic).

### Introspection
`ModelRouter(cfg, usage).plan()` returns the qualified, ranked candidate list per
role — useful for debugging "who can serve as judge right now?".

Covered by `tests/test_router.py` (qualification, ranking, circuit-breaker,
missing-key exclusion, explicit-mock).

## Confidence-gated short-circuit (token saver)
Beyond routing, the pipeline skips the expensive judge entirely when the free/cheap
layer already settles the claim — realising the original "cheap tools gate, strong
model only for real judgment" goal:
- **Rule A** — no admissible/usable image → `not_enough_information` (the judge
  couldn't add anything).
- **Rule B** — two INDEPENDENT signals agree the image is the wrong object: the
  **CLIP object-consistency tool** *and* the perception model both say it's a
  different, known object → `not_enough_information` + `wrong_object`.

It is conservative by construction: on the 20 labelled samples it fires **0 times**
(all 20 still go to the judge), so review accuracy is unchanged; it fires only on
junk/gaming submissions, where it skips the priciest call. Demonstrated: a "laptop"
claim with a car photo → judge calls **0**, short-circuited; a real car claim →
judge calls **1**. Counted as `short_circuits` in the usage report.

`open_clip` (CLIP ViT-B-32, OpenAI weights, MIT/Apache) runs locally on CPU — free,
no tokens — and is conservatively thresholded (0/20 false positives on valid samples).
