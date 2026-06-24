"""Connector registry + default catalog wiring."""

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
from .events import ClaimReviewResult, DispatchResult


class ConnectorRegistry:
    def __init__(self):
        self._by_name: dict[str, Connector] = {}

    def register(self, connector: Connector):
        self._by_name[connector.name] = connector
        return self

    def get(self, name: str) -> Connector | None:
        return self._by_name.get(name)

    def names(self) -> list:
        return list(self._by_name)

    def manifests(self) -> list:
        """Capability descriptors for every registered connector (catalog)."""
        return [c.manifest() for c in self._by_name.values()]

    def dispatch(self, name: str, event: ClaimReviewResult, config=None) -> DispatchResult:
        c = self.get(name)
        if not c:
            return DispatchResult(name, ok=False, status="error", detail="unknown connector")
        return c.dispatch(event, config)


def default_connectors() -> ConnectorRegistry:
    reg = ConnectorRegistry()
    reg.register(WebhookConnector())  # the one that's actually live
    reg.register(ZendeskConnector())  # inbound parse live; outbound scaffold
    reg.register(SalesforceConnector())
    reg.register(HubSpotConnector())
    reg.register(GuidewireConnector())
    reg.register(ZohoDeskConnector())
    reg.register(FreshdeskConnector())
    reg.register(IntercomFinConnector())
    reg.register(DecagonConnector())
    return reg
