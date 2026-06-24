"""Claim Intake Envelope — the provider-agnostic INBOUND surface (Task 1).

This package preserves the public import surface of the original `embed` module:
a host/chat provider can submit a single, versioned envelope describing
{claims, evidence, protocols} and get back the same 14-field verdict the batch
path produces, plus a normalized `ClaimReviewResult` payload.

Submodules
----------
* envelope : INTAKE_SCHEMA(_VERSION), the `ClaimIntake` dataclass + validation.
* images   : evidence-image classification + materialization.
* service  : `handle_intake` orchestration and `intake_from_job` mapping.
"""

from __future__ import annotations

from .envelope import INTAKE_SCHEMA, INTAKE_SCHEMA_VERSION, ClaimIntake
from .images import materialize_images
from .service import handle_intake, intake_from_job

__all__ = [
    "INTAKE_SCHEMA",
    "INTAKE_SCHEMA_VERSION",
    "ClaimIntake",
    "materialize_images",
    "handle_intake",
    "intake_from_job",
]
