"""Core event model + signing primitives for ClaimLens integrations.

ClaimLens finishes a review and emits ONE normalized, versioned event
(`ClaimReviewResult`). This module owns that event, the dispatch-result record,
the HMAC signing/verification helpers, and the output-row → event builder.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = "1.0"


@dataclass
class ClaimReviewResult:
    """The single stable event other systems consume."""

    claim_id: str
    verdict: str  # supported | contradicted | not_enough_information
    severity: str = "unknown"
    confidence: float | None = None
    risk_flags: list = field(default_factory=list)
    image_ids: list = field(default_factory=list)
    issue_type: str = "unknown"
    object_part: str = "unknown"
    justification: str = ""
    evidence_requirements_met: bool = False
    reviewed_at: str = ""  # ISO-8601 (caller stamps)
    source: str = "claimlens"
    event: str = "claim_review.completed"
    schema_version: str = SCHEMA_VERSION

    def to_payload(self) -> dict:
        return asdict(self)

    def idempotency_key(self) -> str:
        """Stable across retries / webhook re-deliveries.

        Derived from the claim identity + the evidence set (sorted image ids),
        NOT the wall-clock ``reviewed_at`` — so re-emitting a review of the same
        claim over the same images yields the SAME key and a receiver can dedupe
        (no double-acting on a ticket/refund). Re-reviewing different evidence
        produces a different key, as it should.
        """
        basis = "|".join([self.claim_id or "", ";".join(sorted(self.image_ids or []))])
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


@dataclass
class DispatchResult:
    connector: str
    ok: bool
    detail: str = ""
    status: str = ""  # "delivered" | "not_implemented" | "error" | "dry_run"


def sign_body(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Constant-time check that `signature` is the HMAC-SHA256 of `body` under `secret`.

    Defensive: empty secret/signature → False, never raises. Used to authenticate
    inbound webhooks before we trust their payload (`parse_inbound`).
    """
    if not secret or not signature:
        return False
    expected = sign_body(body or b"", secret)
    return hmac.compare_digest(expected, signature)


def result_from_output_row(
    row: dict, claim_id: str = "", reviewed_at: str = ""
) -> ClaimReviewResult:
    """Build a ClaimReviewResult from an output.csv-style row (decouples schemas)."""
    flags = [f for f in (row.get("risk_flags") or "").split(";") if f and f != "none"]
    ids = [i for i in (row.get("supporting_image_ids") or "").split(";") if i and i != "none"]
    return ClaimReviewResult(
        claim_id=claim_id or row.get("user_id", ""),
        verdict=row.get("claim_status", "not_enough_information"),
        severity=row.get("severity", "unknown"),
        risk_flags=flags,
        image_ids=ids,
        issue_type=row.get("issue_type", "unknown"),
        object_part=row.get("object_part", "unknown"),
        justification=row.get("claim_status_justification", ""),
        evidence_requirements_met=str(row.get("evidence_standard_met", "")).lower() == "true",
        reviewed_at=reviewed_at,
    )
