# Documentation Index

System documentation for the Multi-Modal Evidence Review harness. Start with the
principles, then the architecture, then per-subsystem docs.

| Doc | What it covers |
|---|---|
| [HARNESS_PRINCIPLES.md](./HARNESS_PRINCIPLES.md) | The 12 principles of the extensible agentic harness (LLM-as-OS / Software-3.0) and how they map to code |
| [HLD.md](./HLD.md) | High-level design: system context, component view, request flows, contracts, NFRs, deployment, key decisions |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | System design: the three tiers, guardrails, context engineering, cost/scale |
| [TOOLS.md](./TOOLS.md) | The pluggable Tool interface, registered detectors, and how to add one |
| [SCENARIOS.md](./SCENARIOS.md) | Declarative scenario packs (behavior as data) |
| [SCENARIO_COVERAGE.md](./SCENARIO_COVERAGE.md) | Open-source detectors per scenario, with licenses & integration tiers |
| [GUARDRAILS.md](./GUARDRAILS.md) | Layered controls; risk-flag → guardrail map |
| [MODEL_ROUTING.md](./MODEL_ROUTING.md) | Capability-based model router: qualification + fallback (LiteLLM/OpenRouter pattern) |
| [IMAGE_PROTOCOL.md](./IMAGE_PROTOCOL.md) | Image admissibility protocol (unsupported/cheap/censored) |
| [SECURITY.md](./SECURITY.md) | Untrusted-input security: traversal, bombs, injection, secrets; pluggable auth (NoAuth/ApiKey/OIDC/HMAC) |
| [PROMPT_INJECTION.md](./PROMPT_INJECTION.md) | Prompt-injection threat model & layered-defense plan (design; sanitizer is wired) |
| [INTEGRATION.md](./INTEGRATION.md) | The five open extension points for other systems |
| [EMBED.md](./EMBED.md) | The inbound Claim Intake Envelope — embed ClaimLens in any chat/host (POST /api/intake) |
| [INTEGRATIONS.md](./INTEGRATIONS.md) | CS/CRM/helpdesk/claims ecosystem + the connector module |
| [EVALUATION.md](./EVALUATION.md) | How evaluation works; metrics; variance honesty |
| [BENCHMARKING.md](./BENCHMARKING.md) | Vs live products (Tractable/CCC/Truepic/...) + roadmap to supreme |
| [REVIEW.md](./REVIEW.md) | Senior engineering review findings & resolutions |
| [ROADMAP.md](./ROADMAP.md) | **Open items / WIP backlog** — pending work by product feature, prioritized |
| [PRESENTATION.md](./PRESENTATION.md) | **Project presentation** — requirements met, advancements, perf/cost benchmark, security, SOC 2 plan, business case |
| [deck.html](./deck.html) | **Slide deck** (self-contained HTML) — the visual walkthrough of the presentation; open in a browser |

Code entry points: [`../main.py`](../main.py) (predictions),
[`../evaluation/main.py`](../evaluation/main.py) (evaluation),
[`../README.md`](../README.md) (quickstart).

## Subsystem map
```
evidence_review/
  schema.py            spec/contract (enums + coercion)        [P3]
  config.py            env + provider resolution               [P12]
  context_builder.py   Tier-0 deterministic CV                 [P7,P8]
  perception.py        Tier-1 per-image VLM (cached)           [P1,P11]
  judge.py             Tier-2 decision + context assembly      [P2]
  prompts.py           versioned perception/judge prompts      [P2,P3]
  scenarios.py         scenario-pack loader                    [P6]
  scenario_packs/*.yaml declarative per-object behavior        [P6]
  harness/
    tool.py registry.py  pluggable tools + capability detect   [P5]
    trace.py             structured per-claim trace            [P10]
    escalation.py        human-in-the-loop policy              [P4]
  tools/*.py           scenario detectors (provenance/forgery/ [P5,P8]
                       quality/ocr/clip/aigen)
  cache.py usage.py    content cache + cost/usage tracking     [P7,P10,P11]
  providers/*.py       gemini | claude | openai | mock         [P5,P12]
```
