"""Hermetic tests for the Claim Intake Envelope (embed.py).

Mock-tier only — no API keys. Builds a real Pipeline in mock mode (keyless mock
backstop) and exercises the provider-agnostic inbound surface end to end.
"""

import base64
import io

import pytest

from evidence_review import Config, Pipeline
from evidence_review.embed import (
    INTAKE_SCHEMA,
    INTAKE_SCHEMA_VERSION,
    ClaimIntake,
    handle_intake,
    intake_from_job,
)
from evidence_review.schema import CLAIM_STATUS


def _mock_pipeline():
    cfg = Config(
        perception_provider="mock",
        perception_model="mock",
        judge_provider="mock",
        judge_model="mock",
    )
    return Pipeline(cfg, use_cache=False, verbose=False)


def _jpeg_data_url() -> str:
    """A tiny but valid JPEG, encoded as a data URL."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (120, 120, 120)).save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


# --- (a) from_payload validation -------------------------------------------------


def test_from_payload_rejects_missing_claim_object():
    with pytest.raises(ValueError):
        ClaimIntake.from_payload({"claims": {"user_claim": "dent"}, "evidence": {}})


def test_from_payload_rejects_invalid_claim_object():
    with pytest.raises(ValueError):
        ClaimIntake.from_payload(
            {"claims": {"claim_object": "spaceship", "user_claim": "broken"}, "evidence": {}}
        )


def test_from_payload_rejects_missing_user_claim():
    with pytest.raises(ValueError):
        ClaimIntake.from_payload({"claims": {"claim_object": "car"}, "evidence": {}})


def test_from_payload_accepts_valid_envelope():
    intake = ClaimIntake.from_payload(
        {
            "claims": {"claim_object": "Car", "user_claim": "dent on rear bumper"},
            "evidence": {"images": ["images/test/c1/img_1.jpg"]},
            "metadata": {"claim_id": "C-1", "user_id": "u1"},
        }
    )
    assert intake.claim_object == "car"  # normalized
    assert intake.claim_id == "C-1"
    assert intake.images == ["images/test/c1/img_1.jpg"]


def test_intake_schema_exposed():
    assert INTAKE_SCHEMA["version"] == INTAKE_SCHEMA_VERSION
    assert "claims" in INTAKE_SCHEMA["properties"]


# --- (b) data-URL image envelope -> handle_intake -------------------------------


def test_handle_intake_data_url_returns_legal_verdict():
    payload = {
        "claims": {"claim_object": "car", "user_claim": "There is a dent on the rear bumper."},
        "evidence": {"images": [_jpeg_data_url()]},
        "metadata": {"claim_id": "C-100", "user_id": "u1"},
    }
    resp = handle_intake(payload, _mock_pipeline(), reviewed_at="2026-06-19T00:00:00Z")

    assert resp["claim_status"] in CLAIM_STATUS
    assert "claim_review_result" in resp
    crr = resp["claim_review_result"]
    assert crr["schema_version"]  # ClaimReviewResult schema_version present
    assert crr["claim_id"] == "C-100"
    assert crr["verdict"] in CLAIM_STATUS
    assert "intake_risk_flags" in resp
    assert "image_notes" in resp
    assert resp["intake_schema_version"] == INTAKE_SCHEMA_VERSION


# --- (c) intake_from_job mapping ------------------------------------------------


def test_intake_from_job_maps_fields():
    job = {
        "claim_id": "JOB-7",
        "user_claim": "cracked screen",
        "claim_object": "laptop",
        "image_paths": "images/a/img_1.jpg;images/a/img_2.jpg",
        "user_id": "user-9",
        "tenant": "acme",
        "source": "zendesk",
    }
    payload = intake_from_job(job)
    assert payload["claims"]["claim_object"] == "laptop"
    assert payload["claims"]["user_claim"] == "cracked screen"
    assert payload["evidence"]["images"] == ["images/a/img_1.jpg", "images/a/img_2.jpg"]
    assert payload["metadata"]["claim_id"] == "JOB-7"
    assert payload["metadata"]["user_id"] == "user-9"
    assert payload["metadata"]["tenant"] == "acme"
    # round-trips through validation
    intake = ClaimIntake.from_payload(payload)
    assert intake.claim_object == "laptop"


# --- (d) empty / garbage images -> not_enough_information, no exception ----------


def test_handle_intake_empty_images_not_enough_information():
    payload = {
        "claims": {"claim_object": "package", "user_claim": "box was crushed"},
        "evidence": {"images": []},
        "metadata": {"claim_id": "C-empty"},
    }
    resp = handle_intake(payload, _mock_pipeline())
    assert resp["claim_status"] == "not_enough_information"
    assert resp["claim_review_result"]["verdict"] == "not_enough_information"


def test_handle_intake_garbage_images_not_enough_information():
    payload = {
        "claims": {"claim_object": "package", "user_claim": "box was crushed"},
        "evidence": {
            "images": [
                "data:image/jpeg;base64,!!!notbase64!!!",
                {"kind": "url", "value": "https://example.com/photo.jpg"},
            ]
        },
        "metadata": {"claim_id": "C-garbage"},
    }
    resp = handle_intake(payload, _mock_pipeline())
    assert resp["claim_status"] == "not_enough_information"
    # url-kind evidence is recorded as a skip note, not fetched
    assert any("url" in n for n in resp["image_notes"])
