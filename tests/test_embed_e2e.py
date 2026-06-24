"""End-to-end smoke for the embeddable surface (hermetic, mock tier, no keys).

Exercises the whole new loop a chat provider / host would use:
  intake envelope -> handle_intake (same pipeline as batch) -> verdict
  -> normalized ClaimReviewResult -> connector dispatch (dry-run)
and the inbound direction: Zendesk webhook -> claim job -> envelope.

The pure-library loop needs no web deps; the HTTP-level tests below use FastAPI's
TestClient (httpx) — both ship in code/requirements.txt — and `importorskip` so the
suite still runs if they're absent.
"""

import base64
import io

import pytest

from evidence_review import Config, Pipeline, embed, integrations
from evidence_review.schema import CLAIM_STATUS


def _mock_pipeline():
    cfg = Config(
        perception_provider="mock",
        perception_model="mock",
        judge_provider="mock",
        judge_model="mock",
    )
    return Pipeline(cfg, use_cache=False, verbose=False)


def _data_url():
    """A tiny in-memory JPEG as a base64 data URL (live-capture style evidence)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (180, 30, 30)).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_intake_envelope_to_verdict_to_connector():
    pipe = _mock_pipeline()
    envelope = {
        "claims": {"claim_object": "car", "user_claim": "dent on the rear bumper"},
        "evidence": {"images": [_data_url()]},
        "metadata": {"claim_id": "C-1", "tenant": "acme", "source": "test"},
    }
    resp = embed.handle_intake(envelope, pipe, reviewed_at="2026-06-19T00:00:00Z")

    # the live path returns the verdict fields (not the batch input-echo columns);
    # the value is always a legal claim_status, and the key risk/severity fields ride along
    assert resp["claim_status"] in CLAIM_STATUS
    for col in ("risk_flags", "severity", "issue_type", "object_part"):
        assert col in resp
    # the normalized integration event rides along, versioned
    crr = resp["claim_review_result"]
    assert crr["schema_version"] == integrations.SCHEMA_VERSION
    assert crr["verdict"] in CLAIM_STATUS
    assert crr["claim_id"] == "C-1"
    assert resp["intake_schema_version"] == embed.INTAKE_SCHEMA_VERSION

    # that event dispatches through the live generic connector (offline dry-run)
    event = integrations.ClaimReviewResult(**{k: crr[k] for k in ("claim_id", "verdict")})
    out = integrations.WebhookConnector().dispatch(event, {"dry_run": True})
    assert out.ok and out.status == "dry_run"


def test_intake_rejects_bad_envelope():
    pipe = _mock_pipeline()
    with pytest.raises(ValueError):
        embed.handle_intake(
            {
                "claims": {"claim_object": "spaceship", "user_claim": "x"},
                "evidence": {"images": []},
            },
            pipe,
        )


def test_inbound_zendesk_ticket_to_envelope():
    conn = integrations.ZendeskConnector()
    assert conn.supports_inbound()
    payload = {
        "ticket": {
            "id": 4242,
            "claim_object": "car",  # mapped from a ticket custom field
            "description": "my bumper is dented",
            "requester_id": "user_99",
            "comments": [
                {"body": "see photo", "attachments": [{"content_url": "https://z/att/1.jpg"}]}
            ],
        }
    }
    job = conn.parse_inbound(payload, {})
    assert job["claim_id"] == "4242"
    assert job["claim_object"] == "car"
    assert job["user_id"] == "user_99"
    assert job["image_refs"] == ["https://z/att/1.jpg"]

    # the job maps cleanly onto the provider-agnostic envelope
    envelope = embed.intake_from_job(job)
    intake = embed.ClaimIntake.from_payload(envelope)
    assert intake.claim_object == "car"
    # url-kind evidence is intentionally NOT fetched in this reference
    pipe = _mock_pipeline()
    resp = embed.handle_intake(envelope, pipe, reviewed_at="2026-06-19T00:00:00Z")
    assert resp["claim_status"] == "not_enough_information"
    assert any("url" in note.lower() for note in resp.get("image_notes", []))


def test_server_wires_the_new_routes():
    pytest.importorskip("fastapi")
    import server  # noqa: PLC0415 — imported here so the suite runs without fastapi

    paths = {r.path for r in server.app.routes}
    assert {
        "/api/review",
        "/api/intake",
        "/api/connectors",
        "/integrations/inbound/{connector}",
    } <= paths


def test_server_routes_respond_over_http():
    """Regression guard: exercise the routes through the real ASGI app, not just
    by path string. Catches the auth-dependency/annotation class of bug where a
    route silently 422s because a dependency param isn't injected."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import server  # noqa: PLC0415

    client = TestClient(server.app)
    assert client.get("/api/health").status_code == 200
    # under the default NoAuth, /api/review and /api/intake must accept the body
    # (NOT 422 on a phantom query param)
    r = client.post(
        "/api/review",
        json={"claim_object": "car", "user_claim": "dent", "images": [_data_url()]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["claim_status"] in CLAIM_STATUS
    r2 = client.post(
        "/api/intake",
        json={
            "claims": {"claim_object": "car", "user_claim": "dent"},
            "evidence": {"images": [_data_url()]},
            "metadata": {"claim_id": "C-http"},
        },
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["claim_status"] in CLAIM_STATUS
    # the manifest-backed catalog the UI renders from
    cons = client.get("/api/connectors")
    assert cons.status_code == 200
    names = {c["name"] for c in cons.json()["connectors"]}
    assert "webhook_generic" in names


def test_auth_dependency_enforced_over_http():
    """The pluggable dependency must actually gate a route: 401 without a key,
    200 with the right key — proving make_fastapi_dependency injects Request and
    runs the provider (not treated as a query param)."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi import Depends, FastAPI  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from evidence_review.harness.auth import (  # noqa: PLC0415
        ApiKeyAuth,
        NoAuth,
        make_fastapi_dependency,
    )

    app = FastAPI()

    @app.get("/open")
    def open_route(ctx=Depends(make_fastapi_dependency(NoAuth()))):
        return {"subject": ctx.subject}

    @app.get("/guarded")
    def guarded(ctx=Depends(make_fastapi_dependency(ApiKeyAuth(keys=["k1=acme"])))):
        return {"tenant": ctx.tenant}

    c = TestClient(app)
    assert c.get("/open").status_code == 200  # NoAuth admits anonymous
    assert c.get("/guarded").status_code == 401  # missing key
    assert c.get("/guarded", headers={"X-API-Key": "nope"}).status_code == 401
    ok = c.get("/guarded", headers={"X-API-Key": "k1"})
    assert ok.status_code == 200 and ok.json()["tenant"] == "acme"
