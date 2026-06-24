"""EscalationPolicy — autonomy slider + human-in-the-loop (P4).

A deterministic, documented policy that decides when a claim must be routed to a
human (`manual_review_required`) and assigns a confidence band. It ADDS the
escalation flag and confidence; it deliberately does NOT silently override the
judge's claim_status (the judge owns the visual decision — P1/P2), keeping the
autonomy boundary explicit and auditable.
"""

from __future__ import annotations

# Flags that signal a possible integrity / gaming problem — auto-approving these
# without a human is unsafe.
INTEGRITY_FLAGS = {
    "possible_manipulation",
    "non_original_image",
    "wrong_object",
    "wrong_object_part",
    "claim_mismatch",
    "text_instruction_present",
}


class EscalationPolicy:
    def __init__(self, escalate_on_abstain=True):
        self.escalate_on_abstain = escalate_on_abstain

    def decide(self, status: str, risk_flags: set, history: dict | None) -> dict:
        reasons = []
        manual = False

        present_integrity = risk_flags & INTEGRITY_FLAGS
        if present_integrity:
            manual = True
            reasons.append(f"integrity_flags={sorted(present_integrity)}")

        if self.escalate_on_abstain and status == "not_enough_information":
            manual = True
            reasons.append("abstained: needs human evaluation")

        # confidence band (transparency; not used to silently flip decisions)
        score = 1.0
        score -= 0.25 * len(risk_flags & INTEGRITY_FLAGS)
        score -= 0.1 * len(risk_flags - INTEGRITY_FLAGS)
        if status == "not_enough_information":
            score -= 0.3
        score = max(0.0, min(1.0, score))
        band = "high" if score >= 0.75 else "medium" if score >= 0.45 else "low"

        flags_to_add = {"manual_review_required"} if manual else set()
        return {
            "manual_review_required": manual,
            "confidence": round(score, 2),
            "confidence_band": band,
            "reasons": reasons,
            "flags_to_add": flags_to_add,
        }
