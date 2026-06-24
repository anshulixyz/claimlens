"""Integration module — event mapping, signed webhook (dry-run), named scaffolds."""

from evidence_review.integrations import (
    ClaimReviewResult,
    WebhookConnector,
    ZendeskConnector,
    default_connectors,
    result_from_output_row,
    sign_body,
    verify_signature,
)

REQUIRED_MANIFEST_KEYS = {
    "name",
    "target_system",
    "category",
    "supports_inbound",
    "supports_outbound",
    "auth",
    "docs_url",
    "status",
}


def test_result_from_output_row():
    row = {
        "user_id": "u1",
        "claim_status": "supported",
        "severity": "medium",
        "risk_flags": "user_history_risk;none",
        "supporting_image_ids": "img_1;none",
        "issue_type": "dent",
        "object_part": "rear_bumper",
        "claim_status_justification": "visible dent",
        "evidence_standard_met": "true",
    }
    r = result_from_output_row(row, claim_id="CLM-1", reviewed_at="2026-06-19T00:00:00Z")
    assert r.verdict == "supported" and r.risk_flags == ["user_history_risk"]
    assert r.image_ids == ["img_1"] and r.evidence_requirements_met is True
    # idempotency key is stable across re-reviews (independent of reviewed_at),
    # so retries/redeliveries of the same claim+evidence dedupe.
    r_retry = result_from_output_row(row, claim_id="CLM-1", reviewed_at="2026-06-20T09:00:00Z")
    assert r.idempotency_key() == r_retry.idempotency_key()
    # different claim id -> different key; different evidence -> different key
    r_other = result_from_output_row(row, claim_id="CLM-2", reviewed_at="2026-06-19T00:00:00Z")
    assert r.idempotency_key() != r_other.idempotency_key()


def test_webhook_dry_run_signed():
    ev = ClaimReviewResult(claim_id="CLM-1", verdict="contradicted", reviewed_at="t")
    res = WebhookConnector().dispatch(ev, {"dry_run": True, "secret": "s"})
    assert res.ok and res.status == "dry_run"


def test_sign_body_stable():
    assert sign_body(b"hello", "k") == sign_body(b"hello", "k")
    assert sign_body(b"hello", "k") != sign_body(b"hello2", "k")


def test_named_adapters_report_not_implemented():
    reg = default_connectors()
    assert "webhook_generic" in reg.names()
    ev = ClaimReviewResult(claim_id="CLM-1", verdict="supported")
    assert reg.dispatch("zendesk", ev).status == "not_implemented"
    assert reg.dispatch("unknown_xyz", ev).ok is False


def test_new_named_adapters_report_not_implemented():
    reg = default_connectors()
    ev = ClaimReviewResult(claim_id="CLM-1", verdict="supported")
    for name in ("zoho_desk", "freshdesk", "intercom_fin", "decagon"):
        assert name in reg.names()
        res = reg.dispatch(name, ev)
        assert res.status == "not_implemented" and res.ok is False


def test_registry_manifests():
    reg = default_connectors()
    manifests = reg.manifests()
    # one manifest per registered connector
    assert len(manifests) == len(reg.names())
    by_name = {m["name"]: m for m in manifests}
    # every manifest carries the required keys
    for m in manifests:
        assert REQUIRED_MANIFEST_KEYS <= set(m)
        assert m["status"] in ("live", "scaffold")
        assert m["category"] in ("helpdesk", "crm", "ai_agent", "claims_core", "generic")
    # honesty discipline: only the generic webhook is live
    assert by_name["webhook_generic"]["status"] == "live"
    live = [m["name"] for m in manifests if m["status"] == "live"]
    assert live == ["webhook_generic"]
    # named adapters are scaffolds
    for name in ("zendesk", "salesforce", "zoho_desk", "freshdesk", "intercom_fin", "decagon"):
        assert by_name[name]["status"] == "scaffold"
    # zendesk is the inbound reference
    assert by_name["zendesk"]["supports_inbound"] is True


def test_zendesk_parse_inbound_maps_claim_job():
    payload = {
        "ticket": {
            "id": 12345,
            "description": "My rear bumper has a deep dent after the accident.",
            "requester_id": 778,
            "comments": [
                {
                    "body": "Photos attached.",
                    "attachments": [
                        {"content_url": "https://files.zendesk.com/a/img_1.jpg"},
                        {"content_url": "https://files.zendesk.com/a/img_2.jpg"},
                    ],
                }
            ],
        }
    }
    job = ZendeskConnector().parse_inbound(payload, {})
    assert job["claim_id"] == "12345"
    assert job["user_id"] == "778"
    assert "rear bumper" in job["user_claim"]
    assert job["image_refs"] == [
        "https://files.zendesk.com/a/img_1.jpg",
        "https://files.zendesk.com/a/img_2.jpg",
    ]
    assert job["source"] == "zendesk"


def test_zendesk_parse_inbound_defensive_defaults():
    # empty / malformed payloads must not crash and yield sensible defaults
    job = ZendeskConnector().parse_inbound({}, {})
    assert job["claim_id"] == "" and job["user_claim"] == ""
    assert job["image_refs"] == [] and job["user_id"] == ""
    # flat ticket (no nested "ticket" key) + first-comment fallback for claim text
    flat = {
        "id": 9,
        "comments": [{"body": "windshield cracked", "attachments": ["https://x/y.png"]}],
    }
    job2 = ZendeskConnector().parse_inbound(flat, {})
    assert job2["claim_id"] == "9"
    assert job2["user_claim"] == "windshield cracked"
    assert job2["image_refs"] == ["https://x/y.png"]


def test_verify_signature_accepts_and_rejects():
    body = b'{"ticket":{"id":1}}'
    secret = "shhh"
    good = sign_body(body, secret)
    assert verify_signature(body, good, secret) is True
    # tampered body
    assert verify_signature(b'{"ticket":{"id":2}}', good, secret) is False
    # wrong secret
    assert verify_signature(body, good, "other") is False
    # empty signature / secret
    assert verify_signature(body, "", secret) is False
    assert verify_signature(body, good, "") is False


def test_connector_verify_inbound_signature_delegates():
    body = b"abc"
    secret = "k"
    sig = sign_body(body, secret)
    assert ZendeskConnector().verify_inbound_signature(body, sig, secret) is True
    assert ZendeskConnector().verify_inbound_signature(body, sig, "nope") is False
