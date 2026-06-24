"""Intake orchestration: run a full claim review from an intake envelope.

`handle_intake` is the embeddable entrypoint the HTTP layer calls; `intake_from_job`
maps a generic connector job shape onto the envelope payload.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .. import integrations
from .envelope import INTAKE_SCHEMA_VERSION, ClaimIntake
from .images import materialize_images


def _not_enough_information(intake: ClaimIntake, reviewed_at: str, image_notes: list) -> dict:
    """Build a graceful not_enough_information response (mirrors server.py's
    empty-images branch) without invoking the pipeline."""
    from ..schema import coerce_row

    decision = coerce_row(
        {
            "claim_status": "not_enough_information",
            "evidence_standard_met": False,
            "valid_image": False,
            "issue_type": "unknown",
            "object_part": "unknown",
            "severity": "unknown",
            "risk_flags": ["manual_review_required"],
            "claim_status_justification": (
                "No usable image was submitted with the claim; routed to manual review."
            ),
            "evidence_standard_met_reason": "no usable image in the intake envelope",
        },
        intake.claim_object,
    )
    decision["evidence_standard_met"] = "true" if decision["evidence_standard_met"] else "false"
    decision["valid_image"] = "true" if decision["valid_image"] else "false"
    return _build_response(
        decision,
        intake,
        reviewed_at=reviewed_at,
        intake_risk_flags=[],
        image_notes=image_notes,
        assistant_message=(
            "I didn't receive a usable photo with this claim. Please capture the "
            f"{intake.claim_object} live and resubmit."
        ),
    )


def _build_response(
    decision: dict,
    intake: ClaimIntake,
    *,
    reviewed_at: str,
    intake_risk_flags: list,
    image_notes: list,
    assistant_message: str | None = None,
) -> dict:
    """Assemble the stable intake response contract."""
    claim_id = intake.claim_id or intake.user_id or ""
    result = integrations.result_from_output_row(
        decision, claim_id=claim_id, reviewed_at=reviewed_at
    )
    resp = dict(decision)
    resp["claim_review_result"] = result.to_payload()
    resp["intake_risk_flags"] = list(intake_risk_flags or [])
    resp["image_notes"] = list(image_notes or [])
    resp["intake_schema_version"] = INTAKE_SCHEMA_VERSION
    if assistant_message is not None:
        resp["assistant_message"] = assistant_message
    return resp


def handle_intake(
    payload: dict,
    pipeline,
    *,
    reviewed_at: str = "",
    tmp_root=None,
) -> dict:
    """Run a full claim review from a provider-agnostic intake envelope.

    Parameters
    ----------
    payload : dict
        The intake envelope (see INTAKE_SCHEMA). Untrusted; validated here.
    pipeline : Pipeline
        A `Pipeline` instance (or anything exposing `review_uploaded`).
    reviewed_at : str
        ISO-8601 timestamp the caller stamps onto the emitted event.
    tmp_root : path-like, optional
        Parent dir for the scratch tempdir (defaults to the system temp).

    Returns
    -------
    dict
        The full 14-field decision plus:
          * "claim_review_result"  — normalized ClaimReviewResult payload,
          * "intake_risk_flags"    — flags from inbound sanitization,
          * "image_notes"          — per-image materialization notes,
          * "intake_schema_version".

    Raises
    ------
    ValueError
        On a malformed/invalid envelope (from `ClaimIntake.from_payload`).
    """
    intake = ClaimIntake.from_payload(payload)

    # Sanitize the user-supplied claim text via the inbound sanitizer if present.
    # Lazy import so embed.py stays usable even before that module lands.
    try:
        from evidence_review.harness.sanitize import sanitize_claim_text
    except ImportError:

        def sanitize_claim_text(t):
            return (t, [])

    clean_claim, intake_risk_flags = sanitize_claim_text(intake.user_claim)

    tmpdir = Path(tempfile.mkdtemp(prefix="claimlens_intake_", dir=tmp_root))
    try:
        paths, image_notes = materialize_images(intake, tmpdir)
        if not paths:
            return _not_enough_information(intake, reviewed_at, image_notes)

        decision, _extra = pipeline.review_uploaded(
            intake.claim_object,
            clean_claim,
            paths,
            user_id=intake.user_id,
        )
        decision = dict(decision)
        return _build_response(
            decision,
            intake,
            reviewed_at=reviewed_at,
            intake_risk_flags=list(intake_risk_flags or []),
            image_notes=image_notes,
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def intake_from_job(job: dict) -> dict:
    """Map a generic inbound "claim job" to an intake-envelope payload dict.

    Lets connectors reuse the envelope without knowing its nested shape. Accepts
    a flat job like:
        {"claim_id", "user_claim", "claim_object", "images" | "image_paths" |
         "image_refs", "user_id", "tenant", "source", "conversation",
         "capture_tokens", "protocols"}
    and returns a dict suitable for `handle_intake` / `ClaimIntake.from_payload`.
    """
    job = job or {}
    images = job.get("images") or job.get("image_refs") or job.get("image_paths") or []
    if isinstance(images, str):
        # accept a ';'-joined path string like the batch path uses
        images = [p.strip() for p in images.split(";") if p.strip()]
    return {
        "schema_version": INTAKE_SCHEMA_VERSION,
        "claims": {
            "claim_object": job.get("claim_object", ""),
            "user_claim": job.get("user_claim", ""),
            "conversation": job.get("conversation") or [],
        },
        "evidence": {
            "images": list(images),
            "capture_tokens": job.get("capture_tokens") or [],
        },
        "protocols": job.get("protocols") or {},
        "metadata": {
            "claim_id": job.get("claim_id", ""),
            "tenant": job.get("tenant", ""),
            "source": job.get("source", ""),
            "user_id": job.get("user_id", ""),
        },
    }
