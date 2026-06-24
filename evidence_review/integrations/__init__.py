"""Integration package — emit ClaimLens verdicts into the customer's stack.

ClaimLens finishes a review and emits ONE normalized, versioned event
(`ClaimReviewResult`). Pluggable `Connector` adapters translate it into each
target system's native shape. The generic, HMAC-signed `WebhookConnector` alone
makes ClaimLens reachable from Zapier / Make / n8n / Workato / Segment and any
custom endpoint; named adapters (Zendesk, Salesforce, Guidewire, …) are
documented scaffolds enabled on demand.

This is intentionally an EXTENSIBLE SCAFFOLD, not a set of live integrations:
the generic webhook connector is real; named adapters declare their mapping and
report `not_implemented` until wired. Adding a vendor = one Connector subclass +
`register`. See docs/INTEGRATIONS.md for the full ecosystem survey & design.

This module is split into `events` (the event model + signing), `connectors`
(the adapters), and `registry` (the catalog); the public import surface is
unchanged — everything is re-exported here.
"""

from __future__ import annotations

from .connectors import (
    Connector,
    DecagonConnector,
    FreshdeskConnector,
    GuidewireConnector,
    HubSpotConnector,
    IntercomFinConnector,
    SalesforceConnector,
    WebhookConnector,
    ZendeskConnector,
    ZohoDeskConnector,
)
from .events import (
    SCHEMA_VERSION,
    ClaimReviewResult,
    DispatchResult,
    result_from_output_row,
    sign_body,
    verify_signature,
)
from .registry import ConnectorRegistry, default_connectors

__all__ = [
    "SCHEMA_VERSION",
    "ClaimReviewResult",
    "DispatchResult",
    "sign_body",
    "verify_signature",
    "result_from_output_row",
    "Connector",
    "WebhookConnector",
    "ZendeskConnector",
    "SalesforceConnector",
    "HubSpotConnector",
    "GuidewireConnector",
    "ZohoDeskConnector",
    "FreshdeskConnector",
    "IntercomFinConnector",
    "DecagonConnector",
    "ConnectorRegistry",
    "default_connectors",
]
