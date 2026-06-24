"""Claim Intake Envelope — the provider-agnostic INBOUND surface (Task 1).

This is what makes ClaimLens "an agent embeddable in a bigger system": any chat
provider or host (Intercom, a custom messenger, a workflow engine, another agent)
can POST a single, versioned envelope describing {claims, evidence, protocols}
and get back the SAME 14-field verdict the batch path produces, plus a normalized
`ClaimReviewResult` payload for downstream systems.

Design notes
------------
* Provider-agnostic: the envelope carries no vendor fields. Connectors map their
  native job shape onto it via `intake_from_job`.
* Defensive: input is untrusted. `from_payload` validates required fields and the
  claim_object enum, raising `ValueError` with a clear message.
* Safe by construction: base64 images are decoded to a private tempdir; dataset-
  relative paths go through `dataio.resolve_image` so the path-traversal guard
  still applies; `url`-kind evidence is NOT fetched here (out of scope for this
  reference — that belongs to the host) and is recorded as a risk note instead.
* Import-light: this module imports cleanly WITHOUT fastapi. The HTTP wiring
  (POST /api/intake) lives in server.py and merely calls `handle_intake`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

INTAKE_SCHEMA_VERSION = "1.0"

_VALID_CLAIM_OBJECTS = {"car", "laptop", "package"}


# --- JSON Schema (plain dict, no external deps; usable for docs/validation) ----
INTAKE_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ClaimLens Intake Envelope",
    "description": (
        "Provider-agnostic inbound envelope: a host/chat provider submits "
        "{claims, evidence, protocols, metadata} and receives a ClaimLens verdict."
    ),
    "version": INTAKE_SCHEMA_VERSION,
    "type": "object",
    "required": ["claims", "evidence"],
    "additionalProperties": True,
    "properties": {
        "schema_version": {"type": "string", "default": INTAKE_SCHEMA_VERSION},
        "claims": {
            "type": "object",
            "required": ["claim_object", "user_claim"],
            "properties": {
                "claim_object": {"type": "string", "enum": sorted(_VALID_CLAIM_OBJECTS)},
                "user_claim": {"type": "string"},
                "conversation": {
                    "type": "array",
                    "description": "Optional prior turns: [{role, text}, ...] (passthrough).",
                    "items": {"type": "object"},
                },
            },
        },
        "evidence": {
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "description": (
                        "Each item is a base64 data URL, a dataset-relative path, "
                        'or {"kind": "data_url|path|url", "value": "..."}.'
                    ),
                    "items": {"type": ["string", "object"]},
                },
                "capture_tokens": {
                    "type": "array",
                    "description": "Optional capture/provenance tokens (passthrough).",
                    "items": {"type": "string"},
                },
            },
        },
        "protocols": {
            "type": "object",
            "description": "Optional host-supplied hints (passthrough; not authoritative).",
            "properties": {
                "evidence_requirements": {"type": "object"},
                "scenario_pack": {"type": "string"},
                "escalation": {"type": "object"},
            },
        },
        "metadata": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string"},
                "tenant": {"type": "string"},
                "source": {"type": "string"},
                "user_id": {"type": "string"},
            },
        },
    },
}


@dataclass
class ClaimIntake:
    """Parsed, validated intake envelope (the in-process representation)."""

    # claims
    claim_object: str
    user_claim: str
    conversation: list = field(default_factory=list)
    # evidence
    images: list = field(default_factory=list)  # raw item specs (str | dict)
    capture_tokens: list = field(default_factory=list)
    # protocols (passthrough hints)
    protocols: dict = field(default_factory=dict)
    # metadata
    claim_id: str = ""
    tenant: str = ""
    source: str = ""
    user_id: str = ""

    @classmethod
    def from_payload(cls, payload: dict) -> ClaimIntake:
        """Validate an untrusted intake payload and build a ClaimIntake.

        Raises ValueError with a clear message on malformed/invalid input.
        """
        if not isinstance(payload, dict):
            raise ValueError("intake payload must be a JSON object")

        claims = payload.get("claims")
        if not isinstance(claims, dict):
            raise ValueError("intake payload missing 'claims' object")

        claim_object = str(claims.get("claim_object", "")).strip().lower()
        if not claim_object:
            raise ValueError("claims.claim_object is required")
        if claim_object not in _VALID_CLAIM_OBJECTS:
            raise ValueError(
                f"claims.claim_object must be one of {sorted(_VALID_CLAIM_OBJECTS)}; "
                f"got {claim_object!r}"
            )

        user_claim = claims.get("user_claim")
        if not isinstance(user_claim, str) or not user_claim.strip():
            raise ValueError("claims.user_claim is required and must be a non-empty string")

        conversation = claims.get("conversation") or []
        if not isinstance(conversation, list):
            raise ValueError("claims.conversation must be a list when provided")

        evidence = payload.get("evidence") or {}
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be an object when provided")
        images = evidence.get("images") or []
        if not isinstance(images, list):
            raise ValueError("evidence.images must be a list when provided")
        capture_tokens = evidence.get("capture_tokens") or []
        if not isinstance(capture_tokens, list):
            raise ValueError("evidence.capture_tokens must be a list when provided")

        protocols = payload.get("protocols") or {}
        if not isinstance(protocols, dict):
            raise ValueError("protocols must be an object when provided")

        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object when provided")

        return cls(
            claim_object=claim_object,
            user_claim=user_claim,
            conversation=conversation,
            images=images,
            capture_tokens=capture_tokens,
            protocols=protocols,
            claim_id=str(metadata.get("claim_id", "")),
            tenant=str(metadata.get("tenant", "")),
            source=str(metadata.get("source", "")),
            user_id=str(metadata.get("user_id", "")),
        )
