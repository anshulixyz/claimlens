# ClaimLens — Project Presentation

**Multi-modal evidence review that turns one photo + a short claim into an
auditable `accept / decline / needs-info` verdict — and drops into any support
stack.**

> Honesty convention (same as [BENCHMARKING.md](./BENCHMARKING.md)):
> **[verified]** = checked against this repo or a cited source ·
> **[analysis]** = our reasoning/positioning, not a benchmark result ·
> **[target]** = a goal on the roadmap, not a measured claim.
> Every number below is traceable to a file in this repo or a linked source.

---

## 1. Standalone product — requirements met

The HackerRank brief ([`problem_statement.md`](../README.md)) asks for a
system that reads `dataset/claims.csv`, inspects the submitted images + claim
conversation + user history + minimum-evidence rules, and writes `output.csv`
with a fixed 14-field schema, plus an `evaluation/` folder with an operational
analysis. Status: **built and running** [verified].

| Requirement (brief) | What we built | Status |
|---|---|---|
| Extract the claim from the conversation | Judge distills `claim_summary` from `user_claim` | ✅ |
| Inspect one or more images | Tier-1 per-image perception (Gemini), content-hash cached | ✅ |
| Decide evidence sufficiency | `evidence_standard_met` + reason vs minimum-evidence rules | ✅ |
| Issue type / object part | Coerced to the brief's allowed enums (`schema.py`) | ✅ |
| supported / contradicted / not_enough_information | `claim_status`, **fails closed to NEI** | ✅ |
| Supporting image IDs | `supporting_image_ids` (or `none`) | ✅ |
| Risk flags (quality, mismatch, authenticity, history) | Deterministically fused tool flags + model flags | ✅ |
| Severity | `severity` enum | ✅ |
| Grounded justifications | `claim_status_justification` from the judge | ✅ |
| `output.csv` for all 44 test rows | **Generated, schema-validated, 0 illegal enum values** | ✅ [verified] |
| `evaluation/` folder + operational analysis | [`evaluation/`](../evaluation/) + [`evaluation_report.md`](../evaluation/evaluation_report.md) | ✅ |

**Run it** ([verified] — see [CURRENT.md](../README.md)):
```bash
python code/main.py            # -> output.csv (mock tier if no keys)
python code/evaluation/main.py # -> report + metrics.json + dashboard.html
python code/server.py          # PWA + REAL pipeline at /api/review
```
With **no API keys**, every tier falls back to a deterministic `mock`, so the
whole system (and CI) runs end-to-end. Keys (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`)
enable the real models.

---

## 2. Advancements — what we improved, and in what form

We went past a "single VLM call" into a **tiered, extensible agent harness**
(LLM-as-OS framing — see [HARNESS_PRINCIPLES.md](./HARNESS_PRINCIPLES.md)). Each
item is tagged **Full / Partial / Extensible** by how complete it is today.

| Advancement | Form | Notes |
|---|---|---|
| **Tiered cascade** free CV → cheap perception → strong judge | **Full** | One strong-model call per claim; cost-aware [verified] |
| **Capability model router** (qualify + fallback + circuit-breaker) | **Full** | Survived a live Claude-credit outage by falling back to Gemini [verified] |
| **Schema-as-law + fail-closed coercion** | **Full** | Model can't emit an illegal value or fuzzy-match toward "approved" |
| **CLIP object-consistency** (anti wrong-object) | **Full** | Local, free, zero-token; conservatively thresholded |
| **Confidence-gated short-circuit** (skip judge on junk/gaming) | **Full** | 0 short-circuits on the 20 labelled rows → accuracy preserved [verified] |
| **Embeddable intake** `{claims, evidence, protocols, metadata}` → `/api/intake` | **Full** | Any chat/host can submit a claim — [EMBED.md](./EMBED.md) |
| **Pluggable auth** (NoAuth default / ApiKey / OIDC / HMAC) | **Full (off by default)** | OIDC prod-hardening is Partial — see §6 |
| **Connector module** (signed `ClaimReviewResult` + manifest) | **Partial / Extensible** | Generic webhook + Zendesk inbound parse **live**; named outbound adapters are **documented scaffolds** [verified] |
| **Provenance / forensics** (capture token, ELA, EXIF) | **Partial** | Capture token is **integrity-only**; ELA is a weak prior; C2PA not issued |
| **Scenario packs** (per object × issue family, YAML) | **Extensible** | New vertical = config, not a new model |
| **Tools / detectors** behind a registry | **Extensible** | Add a detector = 1 file + register |

---

## 3. Development sanity — best practices enabled

**CI gates on every push/PR** ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) [verified]:
1. `ruff check` + `ruff format --check` — lint + format
2. `pytest` — **63 tests**, hermetic (mock tier, no keys)
3. `output.csv` contract — exact columns/order + legal enums
4. docs-sync gate — every `docs/*.md` must be indexed
5. PWA static check — all four split scripts must parse (`node --check`)

Plus: the 12 [Harness Principles](./HARNESS_PRINCIPLES.md) as a per-module
contract; **content-addressed caching** + `temperature=0` for reproducibility;
**graceful degradation** (missing key → mock; missing dep → tool self-disables,
records *why*); a **per-claim structured trace** for audit; **secrets from env
only** (`.env` gitignored); and a transcript log of every working session
([AGENTS.md](../README.md)). The codebase was just **modularized** — the PWA
split by feature (`ui-base / ui-messenger / ui-landing`) and the long Python
modules into import-stable packages (`embed/`, `integrations/`) — with the test
suite green throughout (see [ROADMAP.md](./ROADMAP.md)).

---

## 4. Performance & cost — the benchmark, and how we calculate it

**How cost is calculated** [verified — [`evidence_review/usage.py`](../evidence_review/usage.py) + [evaluation_report.md](../evaluation/evaluation_report.md)]:
per run we count input/output tokens **per tier**, multiply by each model's
list price (USD / 1M tokens), and sum. Tier-0 CV is deterministic (zero model
calls); perception scales with **image count**, the judge with **claim count**;
content-hash caching makes identical re-runs cost **zero** calls.

**Measured on the 20-row sample** [verified — [metrics.json](../evaluation/metrics.json)], with the
default **Gemini perception → Claude judge** config:

| Metric | Value |
|---|---|
| Model calls | 20 (1 judge/claim) · 29 cache hits |
| Tokens | 64,868 in / 6,121 out |
| Estimated cost | **$0.286** (sample) |
| Runtime | **56.3 s** |
| claim_status accuracy | **0.80** · macro-F1 0.669 |
| evidence acc / issue / part / severity | 0.85 / 0.55 / 0.80 / 0.65 |
| risk-flag F1 | 0.667 |

**Projected full test set** (44 claims, 82 images): **≈ $0.63** at list prices (Claude judge) [verified].

**The router is a cost/accuracy dial** [verified — both profiles measured]:

| Judge | claim-status acc (n=20) | full-test cost | when |
|---|---|---|---|
| **Claude Sonnet** (default) | **0.80** | ≈ $0.63 | accuracy-first |
| Gemini Flash | 0.60 | ≈ $0.06 | cost-first / high volume |

Same pipeline, one config line — the capability router (and its fallback) picks
the judge; that fallback is what kept the system running when Claude credits were
briefly exhausted mid-build.

> ⚠️ **Accuracy honesty** [verified — [EVALUATION.md](./EVALUATION.md)]: the headline is
> **directional**, not a production accuracy claim. **n = 20**, and `contradicted`
> has only ~5 examples, so one row swings macro-F1 by ~0.07; the harness also
> selects on the same 20 rows (**selection-on-test**). Repeated runs land
> **≈ 0.75–0.80** (≈0.75±0.04 per [EVALUATION.md](./EVALUATION.md); 0.80 this run). We lead with the
> confusion matrix, not the headline. Calibrated confidence + a larger eval set
> are the **Tier-1 roadmap** ([BENCHMARKING.md](./BENCHMARKING.md)).

---

## 5. Security posture & what's next

**Today** [verified — [SECURITY.md](./SECURITY.md)]: input-security for untrusted
CSV/images/text — **path-traversal guard**, **decompression-bomb/format caps**,
**prompt-injection handling** (in-image text + inbound conversation → declared
untrusted, judged from pixels), **fail-closed output coercion**, **secrets from
env only**, and a **pluggable auth layer** (API key / OIDC / HMAC, off by default).
Outbound integration events are **HMAC-signed** with an idempotency key.

**Known limits / next** ([ROADMAP.md](./ROADMAP.md) §2):
- Capture token is **integrity-only** → server-issued nonce + platform
  attestation (Play Integrity / App Attest) + **C2PA** for true provenance.
- OIDC enforces `aud`/`iss` only when set → make them mandatory + **RS256/JWKS**
  for production; HS256-shared-secret is a testing path.
- Add **rate-limiting / request-size caps** and per-tenant data isolation.
- We are **not a hosted service** — TLS, queueing, scale belong to the deployment.

---

## 6. SOC 2 readiness — is it extensible, and the plan

**Honest status: ClaimLens is *not* SOC 2 compliant today** — SOC 2 certifies an
*organization's* controls over time, not a library [verified]. But the
architecture is **friendly to the controls a SOC 2 audit checks.** SOC 2 has five
Trust Services Criteria — **Security** (mandatory) plus optional **Availability,
Processing Integrity, Confidentiality, Privacy** — and a **Type II** report tests
operating effectiveness over 6–12 months ([Vanta](https://www.vanta.com/collection/soc-2/soc-2-trust-principles), [CSA](https://cloudsecurityalliance.org/blog/2023/10/05/the-5-soc-2-trust-services-criteria-explained)) [verified].

| TSC | What ClaimLens already gives | Plan to close |
|---|---|---|
| **Security** | Pluggable auth, HMAC-signed events, injection/traversal guards, env-only secrets | Mandatory access controls, secret manager, audit of the deployment |
| **Processing Integrity** | Schema-as-law + fail-closed coercion; per-claim **trace**; `temperature=0` | Formalize evidence/QA of accuracy + change control |
| **Confidentiality** | Minimal data to providers; sensitive cache gitignored | Encryption at rest/in transit; data-classification policy |
| **Privacy** | No data store today; PII only to configured providers | Retention/deletion policy; DPA; consent surface |
| **Availability** | Graceful degradation + mock backstop | Hosted SLA, monitoring, incident process |

**Plan**: the **per-decision trace + structured logging** (P10) are the audit
backbone; the work is organizational (policies, a hosted deployment with access
controls + encryption + monitoring) more than architectural. [target]

---

## 7. Business case

### 7.1 Integration options [verified — [INTEGRATIONS.md](./INTEGRATIONS.md)]
- **Live today:** generic **signed webhook** (drops into Zapier / Make / n8n /
  Workato / any endpoint) + a programmatic **`/api/intake`** envelope + a
  **Zendesk inbound** parse reference.
- **Documented & pluggable (scaffold):** Zendesk · Salesforce/Agentforce ·
  HubSpot · Zoho Desk · Freshdesk · Intercom/Fin · Guidewire ClaimCenter ·
  Decagon. Adding a vendor = one connector + `register` (no core change).

### 7.2 Target segments [analysis]
- **Insurance / claims** — motor FNOL, P&C (Guidewire-adjacent).
- **E-commerce returns & damage** — "arrived damaged / wrong item" before refund.
- **Device & warranty / RMA** — cracked screen, dents, liquid marks.
- **Logistics & parcel** — crushed/torn parcels (~11% of shipments arrive damaged, per [BENCHMARKING.md](./BENCHMARKING.md)).
- **Large CMS / helpdesk ops** — verification at scale across Zendesk/Salesforce/HubSpot queues.

### 7.3 Perceptual map [analysis — positioning, not a benchmark]
```
              MULTI-VERTICAL · CONFIG-DRIVEN (one system, many objects)
                                  ▲
                                  │           ◆ ClaimLens
                                  │     (adjudication + integrated
                                  │      anti-gaming + abstention,
                                  │      general VLM reasoning)
   COST-ESTIMATION /              │                         VERIFICATION /
   REPAIR-PRICING  ◄──────────────┼──────────────────────►  ADJUDICATION
   (CCC, Tractable,               │                          (Truepic = provenance;
    Solera/Qapter)                │                           Onfido/AU10TIX = KYC)
              ● CCC  ● Tractable  │
              ● Solera            │
                                  ▼
              SINGLE-VERTICAL · FINE-TUNED ON PROPRIETARY CORPORA
                     (30M–1.5B images; deep accuracy, narrow scope)
```
**We win** on breadth, adjudication framing, integrated anti-gaming, abstention,
explainability; **incumbents lead** on fine-grained accuracy, cost estimation,
scale, distribution, regulatory maturity. Defensible niche: the **orchestration +
verification layer that consumes best-in-class detectors** [analysis — [BENCHMARKING.md](./BENCHMARKING.md)].

### 7.4 Two product shapes
**(a) B2C — "an agent that handles all your claims."** A consumer messenger
(the PWA): snap a photo, the agent verifies it live and returns a grounded
verdict, escalating cleanly when it can't see enough. Built today as the
camera-only PWA → `/api/review`.

**(b) B2B — "Uber/Zomato for customer service": automate the clear-cut reviews,
route the rest.** Drop ClaimLens into existing helpdesk/claims workflows; it
auto-clears the unambiguous cases and **escalates ambiguous ones to a human**
(`manual_review_required` is a first-class output, P4).

> The **"automate up to ~80% of human reviews"** figure is a **[target]**, framed
> against *external* 2026 benchmarks — AI now deflects ~45% of queries overall and
> **65–80% for high-structure intents with a clear system of record** (auth /
> order / refund) ([Builts](https://builts.ai/blog/ai-customer-service-trends-2026/), [Lorikeet](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics)) [verified]. Damage-claim
> triage is exactly that high-structure shape. Reaching it for *our* task requires
> the Tier-1 calibration + eval work in [BENCHMARKING.md](./BENCHMARKING.md); it is
> **not** a measured ClaimLens result today.

**Market context** [verified]: AI customer-service is **$15.1B in 2026 → $117.9B
by 2034 (25.8% CAGR)** ([digitalapplied](https://www.digitalapplied.com/blog/ai-customer-support-statistics-2026-adoption-roi-data)). Value levers: faster cycle time,
consistent auditable decisions, and fraud/leakage reduction on damage claims.

---

## 8. The honest one-slide summary
- **Works end-to-end**, schema-valid `output.csv` (44 rows, 0 illegal values), live `/api/review` + `/api/intake`, 63 tests green; runs keyless via mock. ✅ [verified]
- **Accuracy 0.80** claim-status on the 20-row sample with the default Claude judge — **directional** (n=20, selection-on-test; ≈0.75–0.80 across runs). ⚠️
- **Cost is a dial**: Claude judge ≈ $0.63/full run (0.80 acc); Gemini judge ≈ $0.06 (0.60 acc) — same pipeline, one config. ✅ [verified]
- **Secure-by-input** + pluggable auth; provenance/SOC2 are roadmapped, not done. ⚠️
- **Extensible by design**: new vertical = config; new connector/tool = one file. ✅
- **Business**: a B2C claims agent *and* a B2B verification layer for support stacks — winning on breadth + adjudication + anti-gaming, honest about where incumbents lead.

_Sources: repo files linked inline; external market/SOC2 figures cited inline._
