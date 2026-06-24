"""Tier 2 — the judge: one structured decision per claim.

Consumes the assembled ClaimContext (scenario pack, requirements, history,
per-image perception + CV) plus the independent tool signals, and emits the
14-field decision (coerced to the schema). Context assembly here is the core
context-engineering surface (Principle P2).
"""

from __future__ import annotations

import json
import secrets

from . import prompts
from .scenarios import scenario_hint_block
from .schema import coerce_row


def _fence(label: str, text: str, token: str) -> str:
    """Spotlight untrusted input: wrap it in a per-run token fence so the model
    knows it is DATA, not instructions, and a forged closing fence can't escape."""
    return f"[UNTRUSTED {label} · token {token}]\n{text}\n[/UNTRUSTED {label} · token {token}]"


def _fmt_requirements(reqs):
    return (
        "\n".join(f"- [{r['applies_to']}] {r['minimum_image_evidence']}" for r in reqs)
        or "- (none)"
    )


def _fmt_history(hist):
    if not hist:
        return "No history on file for this user."
    return (
        f"past_claims={hist.get('past_claim_count')}, accepted={hist.get('accept_claim')}, "
        f"manual_review={hist.get('manual_review_claim')}, rejected={hist.get('rejected_claim')}, "
        f"last_90d={hist.get('last_90_days_claim_count')}, flags={hist.get('history_flags')}. "
        f"Summary: {hist.get('history_summary')}"
    )


def _fmt_image_evidence(perceptions, cv_images):
    cv_by_id = {c["image_id"]: c for c in cv_images}
    lines = []
    for p in perceptions:
        iid = p.get("_image_id", "?")
        cv = cv_by_id.get(iid, {})
        lines.append(
            json.dumps(
                {
                    "image_id": iid,
                    "perception": {
                        k: p.get(k)
                        for k in (
                            "object_present",
                            "object_guess",
                            "visible_parts",
                            "damage_observed",
                            "issue_type",
                            "object_part",
                            "image_quality",
                            "text_in_image",
                            "instruction_text_present",
                            "notes",
                        )
                    },
                    "cv": {
                        k: cv.get(k)
                        for k in (
                            "blur_var",
                            "mean_luma",
                            "glare_frac",
                            "small_side",
                            "has_camera_exif",
                            "usable",
                            "risk_hints",
                        )
                    },
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _fmt_tool_signals(tool_results):
    lines = []
    for r in tool_results:
        if not r.available:
            continue
        lines.append(
            json.dumps(
                {
                    "tool": r.name,
                    "asserts_risk_flags": list(r.risk_flags),
                    "summary": r.note,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) or "(no tool signals)"


class Judge:
    def __init__(self, router, usage):
        self.router = router  # ModelRouter: picks the strongest qualified judge + fallback
        self.usage = usage

    def decide(self, ctx, tool_results) -> dict:
        # Spotlighting / data-marking: fence untrusted free-text inputs (the
        # conversation + user history) with a per-call token so injected text
        # can't pose as instructions or forge a closing delimiter (L2).
        token = secrets.token_hex(3)
        user = prompts.JUDGE_USER.format(
            claim_object=ctx.claim_object,
            user_claim=_fence("CLAIM", ctx.user_claim, token),
            scenario=scenario_hint_block(ctx.scenario),
            requirements=_fmt_requirements(ctx.requirements),
            user_history=_fence("HISTORY", _fmt_history(ctx.user_history), token),
            image_evidence=_fmt_image_evidence(ctx.perceptions, ctx.cv_result.get("images", [])),
            tool_signals=_fmt_tool_signals(tool_results),
        )
        try:
            resp, _used = self.router.run(
                "judge", system=prompts.JUDGE_SYSTEM, parts=[user], max_tokens=900
            )
            raw = resp.json()
        except Exception as e:
            # log full error internally; keep the CSV reason generic (no raw
            # exception text / paths / URLs leaking into the deliverable).
            import sys

            print(f"[judge error] {type(e).__name__}: {e}", file=sys.stderr)
            raw = {
                "claim_status": "not_enough_information",
                "evidence_standard_met": False,
                "valid_image": False,
                "risk_flags": ["manual_review_required"],
                "claim_status_justification": "Automated review could not be completed; routed to manual review.",
                "evidence_standard_met_reason": "automated review unavailable",
                "severity": "unknown",
            }
        coerced = coerce_row(raw, ctx.claim_object)
        coerced["_raw"] = {k: raw.get(k) for k in ("claim_summary", "reasoning")}
        return coerced
