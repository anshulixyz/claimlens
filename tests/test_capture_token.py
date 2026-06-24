"""Capture-token sign/verify round-trip + tamper detection (PWA <-> backend)."""

from evidence_review.capture_token import sign, verify_token


def _token(image_bytes):
    payload = {
        "v": 1,
        "capture_id": "abc",
        "image_id": "img_1",
        "claim_object": "car",
        "captured_at": "2026-06-19T12:00:00.000Z",
        "nonce": "deadbeef",
        "device": {"platform": "iPhone", "ua": "demo"},
        "image_sha256": __import__("hashlib").sha256(image_bytes).hexdigest(),
        "capture_source": "live_camera",
        "width": 640,
        "height": 480,
    }
    return {"payload": payload, "alg": "HMAC-SHA256", "sig": sign(payload)}


def test_valid_token_round_trip():
    img = b"pretend-jpeg-bytes"
    v = verify_token(_token(img), image_bytes=img)
    assert v.valid and v.live_capture and v.reasons == []


def test_tampered_image_rejected():
    img = b"pretend-jpeg-bytes"
    tok = _token(img)
    v = verify_token(tok, image_bytes=img + b"x")  # bytes changed
    assert not v.valid and any("hash mismatch" in r for r in v.reasons)


def test_tampered_payload_rejected():
    img = b"pretend-jpeg-bytes"
    tok = _token(img)
    tok["payload"]["claim_object"] = "laptop"  # signed field changed
    v = verify_token(tok, image_bytes=img)
    assert not v.valid and any("signature" in r for r in v.reasons)


def test_malformed_token():
    assert not verify_token({"nope": 1}).valid
