"""Connector adapters — translate the normalized event into target systems.

Pluggable `Connector` adapters translate the `ClaimReviewResult` into each
target system's native shape. The generic, HMAC-signed `WebhookConnector` alone
makes ClaimLens reachable from Zapier / Make / n8n / Workato / Segment and any
custom endpoint; named adapters (Zendesk, Salesforce, Guidewire, …) are
documented scaffolds enabled on demand.

This is intentionally an EXTENSIBLE SCAFFOLD, not a set of live integrations:
the generic webhook connector is real; named adapters declare their mapping and
report `not_implemented` until wired. Adding a vendor = one Connector subclass +
`register`. See docs/INTEGRATIONS.md for the full ecosystem survey & design.
"""

from __future__ import annotations

import json
import os

from .events import ClaimReviewResult, DispatchResult, sign_body, verify_signature


class Connector:
    """Adapter interface. Outbound: push a verdict; inbound: parse a foreign payload.

    Every connector also exposes a `manifest()` capability descriptor so the
    registry, server, and UI can render the connector catalog data-drivenly.
    """

    name: str = "base"
    target_system: str = ""
    category: str = "generic"  # helpdesk | crm | ai_agent | claims_core | generic
    auth: str = "hmac_webhook"  # hmac_webhook | oauth2 | api_token
    docs_url: str = ""
    status: str = "scaffold"  # live | scaffold
    mapping: str = ""

    def supports_outbound(self) -> bool:
        return True

    def supports_inbound(self) -> bool:
        return False

    def dispatch(self, event: ClaimReviewResult, config: dict | None = None) -> DispatchResult:
        raise NotImplementedError

    def parse_inbound(self, raw_payload: dict, headers: dict) -> dict:
        raise NotImplementedError

    def verify_inbound_signature(self, body: bytes, signature: str, secret: str) -> bool:
        """Authenticate an inbound request body before parsing it."""
        return verify_signature(body, signature, secret)

    def manifest(self) -> dict:
        """Capability descriptor — the per-connector catalog entry."""
        return {
            "name": self.name,
            "target_system": self.target_system or self.name,
            "category": self.category,
            "supports_inbound": self.supports_inbound(),
            "supports_outbound": self.supports_outbound(),
            "auth": self.auth,
            "docs_url": self.docs_url,
            "status": self.status,
            "mapping": self.mapping,
        }


class WebhookConnector(Connector):
    """Generic, signed webhook — the baseline that reaches Zapier/Make/n8n/etc.

    POSTs the ClaimReviewResult JSON with an `X-ClaimLens-Signature` HMAC header.
    Network send is optional: without `requests` (or in dry_run) it returns the
    exact signed request it WOULD send, so it is testable offline.
    """

    name = "webhook_generic"
    target_system = "Generic webhook (Zapier / Make / n8n / Workato / Segment / any URL)"
    category = "generic"
    auth = "hmac_webhook"
    docs_url = "https://github.com/anthropics/claimlens/blob/main/code/docs/INTEGRATIONS.md"
    status = "live"
    mapping = "POST the signed ClaimReviewResult JSON to a configured URL"

    def dispatch(self, event, config=None) -> DispatchResult:
        cfg = config or {}
        url = cfg.get("url") or os.environ.get("CLAIMLENS_WEBHOOK_URL")
        secret = cfg.get("secret") or os.environ.get("CLAIMLENS_WEBHOOK_SECRET", "")
        body = json.dumps(event.to_payload(), separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-ClaimLens-Event": event.event,
            "X-ClaimLens-Idempotency-Key": event.idempotency_key(),
        }
        if secret:
            headers["X-ClaimLens-Signature"] = sign_body(body, secret)

        if not url or cfg.get("dry_run"):
            return DispatchResult(
                self.name,
                ok=True,
                status="dry_run",
                detail=f"prepared signed POST ({len(body)} bytes)"
                + (f" -> {url}" if url else " (no url configured)"),
            )
        try:
            import requests  # optional

            r = requests.post(url, data=body, headers=headers, timeout=10)
            return DispatchResult(
                self.name,
                ok=r.ok,
                status="delivered" if r.ok else "error",
                detail=f"HTTP {r.status_code}",
            )
        except Exception as e:
            return DispatchResult(self.name, ok=False, status="error", detail=str(e))


class _NamedAdapter(Connector):
    """A named target whose field mapping is documented but not yet wired live.

    Status stays "scaffold" and outbound `dispatch` reports `not_implemented` —
    this is the honesty discipline: only the generic webhook is LIVE.
    """

    status = "scaffold"
    mapping = ""

    def dispatch(self, event, config=None) -> DispatchResult:
        return DispatchResult(
            self.name,
            ok=False,
            status="not_implemented",
            detail=f"{self.target_system}: would {self.mapping}",
        )


class ZendeskConnector(_NamedAdapter):
    """Reference inbound adapter (the one parse wired end-to-end).

    Inbound is LIVE for parsing: a Zendesk ticket/webhook → normalized claim job.
    Outbound write-back is still a scaffold (reports `not_implemented`).
    """

    name = "zendesk"
    target_system = "Zendesk"
    category = "helpdesk"
    auth = "oauth2"
    docs_url = "https://developer.zendesk.com/"
    mapping = "add an internal note + set a tag/custom field on the ticket (REST + webhooks)"

    def supports_inbound(self) -> bool:
        return True

    def parse_inbound(self, raw_payload: dict, headers: dict | None = None) -> dict:
        """Map a Zendesk ticket/webhook payload → normalized claim job.

        Accepts the common Zendesk webhook shapes defensively. Recognised keys:
          - `ticket` object (webhook target / trigger placeholder body), OR a
            flat ticket dict at the top level.
          - ticket.id, ticket.description (or first comment body),
            ticket.requester_id / requester.id, and attachment urls from
            ticket.comments[].attachments[].content_url (or ticket.attachments).

        Missing fields fall back to sensible defaults and never raise. The
        returned shape feeds `embed.intake_from_job` directly (note `image_refs`).
        """
        payload = raw_payload or {}
        ticket = payload.get("ticket")
        if not isinstance(ticket, dict):
            # Some webhook bodies put fields at the top level.
            ticket = payload if isinstance(payload, dict) else {}

        ticket_id = ticket.get("id") or ticket.get("ticket_id") or payload.get("id") or ""

        # Claim text: prefer description, else the first comment body.
        comments = ticket.get("comments")
        if not isinstance(comments, list):
            comments = []
        user_claim = ticket.get("description") or ""
        if not user_claim:
            for c in comments:
                if isinstance(c, dict) and c.get("body"):
                    user_claim = c.get("body")
                    break
        user_claim = (user_claim or "").strip()

        # Requester / user id.
        requester = ticket.get("requester")
        requester_id = ""
        if isinstance(requester, dict):
            requester_id = requester.get("id") or requester.get("email") or ""
        user_id = ticket.get("requester_id") or requester_id or ticket.get("submitter_id") or ""

        # Attachment image urls — from comment attachments and/or a flat list.
        image_refs: list = []

        def _collect(attachments):
            if not isinstance(attachments, list):
                return
            for a in attachments:
                if isinstance(a, dict):
                    url = a.get("content_url") or a.get("url") or a.get("mapped_content_url")
                    if url:
                        image_refs.append(url)
                elif isinstance(a, str):
                    image_refs.append(a)

        for c in comments:
            if isinstance(c, dict):
                _collect(c.get("attachments"))
        _collect(ticket.get("attachments"))

        return {
            "claim_id": str(ticket_id) if ticket_id != "" else "",
            "claim_object": ticket.get("claim_object", ""),
            "user_claim": user_claim,
            "image_refs": image_refs,
            "user_id": str(user_id) if user_id != "" else "",
            "source": "zendesk",
        }


class SalesforceConnector(_NamedAdapter):
    name = "salesforce"
    target_system = "Salesforce Service Cloud / Agentforce"
    category = "crm"
    auth = "oauth2"
    docs_url = "https://appexchange.salesforce.com/"
    mapping = "publish a Platform Event or create a Case comment (Pub/Sub API)"


class HubSpotConnector(_NamedAdapter):
    name = "hubspot"
    target_system = "HubSpot Service Hub / CRM"
    category = "helpdesk"
    auth = "oauth2"
    docs_url = "https://developers.hubspot.com/"
    mapping = "log to the ticket/CRM timeline (Webhooks + CRM API)"


class GuidewireConnector(_NamedAdapter):
    name = "guidewire"
    target_system = "Guidewire ClaimCenter"
    category = "claims_core"
    auth = "oauth2"
    docs_url = "https://www.guidewire.com/developers/apis"
    mapping = "attach a note/activity to the claim (InsuranceSuite Cloud API)"


class ZohoDeskConnector(_NamedAdapter):
    name = "zoho_desk"
    target_system = "Zoho Desk"
    category = "helpdesk"
    auth = "oauth2"
    docs_url = "https://desk.zoho.com/DeskAPIDocument"
    mapping = "add a private comment + tag the ticket (Tickets API + webhooks)"


class FreshdeskConnector(_NamedAdapter):
    name = "freshdesk"
    target_system = "Freshdesk (Freshworks)"
    category = "helpdesk"
    auth = "api_token"
    docs_url = "https://developers.freshworks.com/"
    mapping = "add a private note + set a custom field on the ticket (REST + webhooks)"


class IntercomFinConnector(_NamedAdapter):
    name = "intercom_fin"
    target_system = "Intercom / Fin (acquired by Salesforce, ~$3.6B, Jun 2026)"
    category = "ai_agent"
    auth = "oauth2"
    docs_url = "https://developers.intercom.com/"
    mapping = "post an internal note / conversation reply (Conversations API + webhooks)"


class DecagonConnector(_NamedAdapter):
    name = "decagon"
    target_system = "Decagon (frontier AI support agent)"
    category = "ai_agent"
    auth = "api_token"
    docs_url = "https://decagon.ai/"
    mapping = "hand the verdict to the AI agent as a tool result / knowledge signal"
