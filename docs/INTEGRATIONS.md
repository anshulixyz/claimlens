# Integrations — Ecosystem & Connector Module

ClaimLens emits a normalized verdict event and routes it into the customer-support,
CRM, helpdesk, and claims-core tools enterprises actually use. This documents the
ecosystem (verified June 2026) and the extensible connector module
(`evidence_review/integrations.py`). **The generic signed-webhook connector is
live; named adapters are documented scaffolds enabled on demand.**

> 2026 market context (verified — affects naming): **Salesforce signed a
> definitive agreement to acquire Intercom/Fin (~$3.6B, 15 Jun 2026)**;
> **Zendesk acquired Forethought (Mar 2026)**; **Kustomer is independent again**
> (Meta sold it back in 2023); **Sapiens↔FRISS is a partnership, not ownership**.

## The ecosystem (all expose inbound REST + webhooks)

**Helpdesk / support:** [Zendesk](https://developer.zendesk.com/) · [Freshdesk](https://developers.freshworks.com/) · [Intercom/Fin](https://developers.intercom.com/) · [HubSpot Service Hub](https://developers.hubspot.com/) · [Zoho Desk](https://desk.zoho.com/DeskAPIDocument) · [Salesforce Service Cloud](https://appexchange.salesforce.com/) · Help Scout · Front · Gorgias · Kustomer.
**CRM:** Salesforce · HubSpot · Zoho CRM · Microsoft Dynamics 365 (Dataverse) · Pipedrive.
**AI support agents:** Intercom Fin (→ Salesforce) · Decagon ($4.5B, 2026) · Sierra ($15.8B, 2026) · Forethought (→ Zendesk) · Ada · Gladly · Cresta · Sendbird · Salesforce Agentforce.
**Insurance / claims core:** [Guidewire ClaimCenter](https://www.guidewire.com/developers/apis) (InsuranceSuite Cloud API) · Duck Creek (Anywhere, 2,600+ APIs) · Sapiens · FRISS (fraud scoring) · Shift Technology ("Shift Claims", agentic, 2025) — the closest peer to our explainable-verdict output.
**Generic glue (broadest reach, least effort):** Zapier · Make · n8n · Workato · Segment · raw webhooks.

## Connector design (`integrations.py`)

### Normalized outbound event — `ClaimReviewResult`
```jsonc
{ "event": "claim_review.completed", "schema_version": "1.0",
  "claim_id": "...", "verdict": "supported|contradicted|not_enough_information",
  "severity": "...", "confidence": 0.87, "risk_flags": [...], "image_ids": [...],
  "issue_type": "...", "object_part": "...", "justification": "...",
  "evidence_requirements_met": true, "reviewed_at": "<ISO>", "source": "claimlens" }
```
Design rules: **versioned schema**; **closed verdict vocabulary** (maps to ticket
states / case dispositions); **HMAC-SHA256 signed** delivery via
`X-ClaimLens-Signature` (mirrors Segment/Help Scout/Stripe); **at-least-once with
retries + idempotency key** (`claim_id:reviewed_at`) — several platforms (e.g.
Gorgias) disable endpoints after repeated failures.

### Pluggable `Connector`
```python
class Connector:
    name: str
    def supports_outbound(self) -> bool
    def supports_inbound(self) -> bool
    def dispatch(self, event: ClaimReviewResult, config) -> DispatchResult   # push verdict
    def parse_inbound(self, raw_payload, headers) -> dict                     # ticket -> claim job
    def verify_inbound_signature(self, body, signature, secret) -> bool       # authenticate
    def manifest(self) -> dict                                                # capability descriptor
```
- `WebhookConnector` (**live**): POSTs the signed event; works with Zapier/Make/n8n/
  Workato/Segment/any URL. Offline-testable (returns the signed request in `dry_run`).
- Named adapters (`ZendeskConnector`, `SalesforceConnector`, `HubSpotConnector`,
  `GuidewireConnector`, plus `ZohoDeskConnector`, `FreshdeskConnector`,
  `IntercomFinConnector`, `DecagonConnector`): declare their native mapping, report
  `not_implemented` until wired. A `ConnectorRegistry` loads them by name; adding a
  vendor = one subclass + `register` — no core change.

### Connector manifest — the capability descriptor
Every connector exposes `manifest()` so the registry, server, and UI can render
the connector catalog data-drivenly (no hard-coded lists). `ConnectorRegistry.manifests()`
returns one descriptor per registered connector:
```jsonc
{ "name": "zendesk",
  "target_system": "Zendesk",
  "category": "helpdesk",            // helpdesk | crm | ai_agent | claims_core | generic
  "supports_inbound": true,
  "supports_outbound": true,
  "auth": "oauth2",                  // hmac_webhook | oauth2 | api_token
  "docs_url": "https://developer.zendesk.com/",
  "status": "scaffold",              // live | scaffold
  "mapping": "add an internal note + set a tag/custom field on the ticket" }
```
Only `webhook_generic` reports `status: "live"`; every named adapter reports
`status: "scaffold"`. The UI mirrors this list; the server can expose it as a
catalog endpoint.

#### Connector catalog
| name | target_system | category | auth | inbound | outbound | status |
|------|---------------|----------|------|---------|----------|--------|
| `webhook_generic` | Zapier/Make/n8n/Workato/Segment/any URL | generic | hmac_webhook | no | yes | **live** |
| `zendesk` | Zendesk | helpdesk | oauth2 | **yes** (reference parse) | yes | scaffold |
| `salesforce` | Salesforce Service Cloud / Agentforce | crm | oauth2 | no | yes | scaffold |
| `hubspot` | HubSpot Service Hub / CRM | helpdesk | oauth2 | no | yes | scaffold |
| `guidewire` | Guidewire ClaimCenter | claims_core | oauth2 | no | yes | scaffold |
| `zoho_desk` | Zoho Desk | helpdesk | oauth2 | no | yes | scaffold |
| `freshdesk` | Freshdesk (Freshworks) | helpdesk | api_token | no | yes | scaffold |
| `intercom_fin` | Intercom / Fin (→ Salesforce, ~$3.6B, Jun 2026) | ai_agent | oauth2 | no | yes | scaffold |
| `decagon` | Decagon (frontier AI support agent) | ai_agent | api_token | no | yes | scaffold |

> **Reading the catalog:** `outbound: yes` means the connector *declares* an
> outbound mapping — it does **not** mean outbound is wired. Except
> `webhook_generic` (**live**), every named adapter's `dispatch()` returns
> `not_implemented` (`status: scaffold`). `auth` is the *outbound* write auth;
> inbound webhook verification uses a signing secret, which for real vendors is
> their own scheme (see below).

### Inbound (close the loop) — Zendesk reference
A single endpoint `POST /integrations/inbound/{connector}`: (1) **if** a signing
secret is configured (`CLAIMLENS_WEBHOOK_SECRET`), it requires a valid
`X-ClaimLens-Signature` via `verify_inbound_signature(body, signature, secret)`
(`verify_signature()` = `sign_body` + `hmac.compare_digest`) and rejects otherwise;
with **no** secret set, inbound is unauthenticated (demo default). A real Zendesk
webhook signs with its own header/scheme (`X-Zendesk-Webhook-Signature`, base64
HMAC over timestamp+body), wired per-connector at integration time. Then (2)
`parse_inbound()` builds a normalized **claim job**, (3) ClaimLens reviews, and
(4) the matching outbound adapter (scaffold) replies on the same ticket.

`ZendeskConnector.parse_inbound(raw_payload, headers)` is the one inbound reference
(`supports_inbound() == True`): the **ticket → claim-job mapping** is wired and
tested. Two things a real deployment still supplies for a *full verdict*: (a) a
`claim_object` (car/laptop/package) — a raw ticket rarely carries one, so triage/UI
or a custom field must set it, else intake returns 422 `incomplete claim`; and
(b) image **bytes** — attachments arrive as URLs, which this reference does not
fetch (see the embed `url`-evidence note), so the host fetches them and resubmits
as `data_url`. It maps a realistic Zendesk ticket/webhook (nested `ticket` object or
flat body) defensively — missing fields → sensible defaults, never crashes — into:
```jsonc
{ "claim_id": "<ticket.id>",
  "claim_object": "",                  // optional; filled by triage/UI
  "user_claim": "<ticket.description or first comment body>",
  "image_refs": ["<attachment content_url>", ...],
  "user_id": "<ticket.requester_id / requester.id / submitter_id>",
  "source": "zendesk" }
```
This claim-job shape feeds **`embed.intake_from_job`** directly (note the
`image_refs` key, which `intake_from_job` accepts alongside `images`/`image_paths`),
so the connector never has to know the nested intake-envelope shape. From there the
normal pipeline runs and the verdict can be written back to the same Zendesk ticket
by the (scaffold) outbound adapter.

## Roll-out order ("supported soon")
1. **Generic webhook + Zapier/Make** — ship first; broadest reach, least effort.
2. **Zendesk** — highest-leverage single helpdesk (and owns Forethought).
3. **Salesforce / Agentforce** — top enterprise target; absorbs Fin/Intercom.
4. **Guidewire ClaimCenter** — domain-credibility play for P&C insurers.
Fast-follow: Freshdesk, HubSpot (one connector covers Service Hub + CRM).

## Messaging
> "ClaimLens connects to your stack. Out of the box it speaks generic signed
> webhooks — so it drops into Zapier, Make, n8n, Workato, or any endpoint today —
> with native adapters for Zendesk, Salesforce/Agentforce, and Guidewire
> ClaimCenter on the way."

## Status & honesty
- **Live:** `WebhookConnector` (signed POST / dry-run), the event schema, the
  registry + `manifests()` catalog, the signature verifier (`verify_signature`),
  and the **`ZendeskConnector.parse_inbound` reference** (ticket → claim job).
- **Scaffold (documented, not live):** all named adapters' **outbound** write —
  Zendesk, Salesforce/Agentforce, HubSpot, Guidewire, Zoho Desk, Freshdesk,
  Intercom/Fin (→ Salesforce), Decagon — every one reports `not_implemented` and
  carries `status: "scaffold"` in its manifest. Per-vendor outbound write mechanics
  for the newer AI agents (Decagon/Sierra/Gladly/Cresta) are gated behind sales/docs
  — confirm at integration time.
- This is a **basic, extensible module** meant to prove the design and the
  openness, not a production integration suite. See [INTEGRATION.md](./INTEGRATION.md)
  for the harness-level injection points.
