"""Orchestration (the harness scheduler, Principle P1).

Per claim:
  Tier 0  context_builder      → deterministic CV signals (shared)
  Tier 1  perception           → per-image VLM evidence (cached)
  Tools   registry.run_all     → independent detectors (provenance/forensics/
                                  quality/in-image-text/object-consistency)
  Tier 2  judge                → calibrated 14-field decision
  Policy  escalation           → human-in-the-loop routing + confidence
  Fusion  deterministic union of tool flags + judge flags + escalation flags
  Trace   structured per-claim record (observability)

Deterministic fusion guarantees tool-asserted risk flags always surface,
regardless of what the model said — rules keep the model honest (P8).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from . import context_builder, dataio, intake, scenarios
from .cache import JsonCache
from .config import CACHE_DIR, Config
from .harness import ClaimContext, ClaimTrace, EscalationPolicy
from .harness.sanitize import sanitize_claim_text
from .judge import Judge
from .perception import Perception
from .router import ModelRouter
from .schema import OUTPUT_COLUMNS, normalize_image_ids, normalize_risk_flags
from .tools import default_registry
from .usage import UsageTracker


class Pipeline:
    def __init__(
        self,
        config: Config = None,
        use_cache: bool = True,
        verbose: bool = True,
        trace: bool = False,
        registry=None,
        escalation=None,
    ):
        """Integration hook (Principle P5): an external system can inject its own
        tool `registry` (custom detectors / scenario rules) and `escalation`
        policy without subclassing — see docs/INTEGRATION.md. Both default to the
        built-ins when not provided.
        """
        self.cfg = config or Config()
        self.verbose = verbose
        self.trace_enabled = trace
        self.usage = UsageTracker()

        # Capability-based model router: qualifies + ranks + falls back per role
        # (no hardcoded provider; Claude-credit-out auto-falls to Gemini, etc.).
        self.router = ModelRouter(self.cfg, self.usage)
        self.perception = Perception(
            self.router, JsonCache("perception", enabled=use_cache), self.usage
        )
        self.judge = Judge(self.router, self.usage)

        self.registry = registry or default_registry()
        self.escalation = escalation or EscalationPolicy()
        self.history = dataio.load_user_history()
        self.requirements = dataio.load_evidence_requirements()

    # --- single claim ---
    def process_claim(self, row: dict, idx: int = 0) -> dict:
        claim_object = (row.get("claim_object") or "").strip().lower()
        rel_paths = dataio.split_image_paths(row.get("image_paths", ""))
        abs_paths = [dataio.resolve_image(p) for p in rel_paths]

        ctx = ClaimContext(
            user_id=row.get("user_id", ""),
            claim_object=claim_object,
            user_claim=row.get("user_claim", ""),
            image_paths_raw=row.get("image_paths", ""),
            abs_paths=abs_paths,
            cv_result=context_builder.analyze_claim_images(abs_paths),
            user_history=self.history.get(row.get("user_id", "")),
            requirements=dataio.requirements_for_object(self.requirements, claim_object),
            scenario=scenarios.get_scenario(claim_object),
            config=self.cfg,
            usage=self.usage,
        )

        decision, _extra = self._run_context(ctx, idx)
        out = {
            "user_id": row.get("user_id", ""),
            "image_paths": row.get("image_paths", ""),
            "user_claim": row.get("user_claim", ""),
            "claim_object": row.get("claim_object", ""),
        }
        out.update(decision)
        return {k: out.get(k, "") for k in OUTPUT_COLUMNS}

    # --- core review over a fully-built ClaimContext (shared by batch + API) ---
    def _run_context(self, ctx, idx=0):
        claim_object = ctx.claim_object
        # Intake / admissibility: classify each image BEFORE any paid model call.
        cv_by_id = {c["image_id"]: c for c in ctx.cv_result["images"]}
        ctx.admissibility = [intake.assess(ap, cv_by_id.get(ap.stem, {})) for ap in ctx.abs_paths]
        adm_by_id = {a.image_id: a for a in ctx.admissibility}

        # Tier 1: perception per image (only for model-admissible images)
        ctx.perceptions = []
        for ap in ctx.abs_paths:
            adm = adm_by_id.get(ap.stem)
            if adm is not None and not adm.send_to_model:
                ctx.perceptions.append(
                    {
                        "_image_id": ap.stem,
                        "object_present": False,
                        "image_quality": adm.status,
                        "issue_type": "unknown",
                        "object_part": "unknown",
                        "damage_observed": False,
                        "text_in_image": False,
                        "notes": f"inadmissible: {adm.reason}",
                    }
                )
                continue
            ctx.perceptions.append(
                self.perception.perceive(ap, claim_object, cv_by_id.get(ap.stem, {}))
            )

        tool_results = self.registry.run_all(ctx)  # independent detectors

        # Confidence-gated short-circuit: when the free/cheap layer already settles
        # the claim (no usable image, or two independent signals agree it's the
        # WRONG object), skip the expensive judge call — saving the priciest tokens
        # on exactly the junk/gaming claims, without touching genuine ones.
        sc = self._short_circuit(ctx, tool_results)
        if sc is not None:
            self.usage.note_short_circuit()
            decision, judge_raw = sc, {"claim_summary": "(resolved before judge)", "reasoning": ""}
        else:
            decision = self.judge.decide(ctx, tool_results)  # strong judge
            judge_raw = decision.pop("_raw", {})
        decision = self._fuse(decision, ctx, tool_results)  # fusion + escalation
        esc = decision.pop("_escalation", {})

        if self.trace_enabled:
            tr = ClaimTrace(
                user_id=ctx.user_id,
                claim_object=claim_object,
                scenario=ctx.scenario.get("object", ""),
            )
            for r in tool_results:
                tr.add_tool(r)
            tr.perceptions = ctx.perceptions
            tr.judge_raw = judge_raw
            tr.escalation = esc
            tr.final = decision
            tr.save(CACHE_DIR, idx)

        return decision, {
            "judge_raw": judge_raw,
            "escalation": esc,
            "perceptions": ctx.perceptions,
            "tool_results": tool_results,
        }

    # --- review uploaded images directly (API / chat path; not dataset-bound) ---
    def review_uploaded(self, claim_object, user_claim, abs_paths, user_id=""):
        claim_object = (claim_object or "").strip().lower()
        abs_paths = list(abs_paths)
        ctx = ClaimContext(
            user_id=user_id or "",
            claim_object=claim_object,
            user_claim=user_claim or "",
            image_paths_raw=";".join(str(p) for p in abs_paths),
            abs_paths=abs_paths,
            cv_result=context_builder.analyze_claim_images(abs_paths),
            user_history=self.history.get(user_id) if user_id else None,
            requirements=dataio.requirements_for_object(self.requirements, claim_object),
            scenario=scenarios.get_scenario(claim_object),
            config=self.cfg,
            usage=self.usage,
        )
        return self._run_context(ctx)

    # --- pre-judge short-circuit (token saver; conservative by construction) ---
    def _short_circuit(self, ctx, tool_results):
        """Return a coerced decision (skipping the judge) ONLY when the cheap layer
        is confident the judge would agree; else None. Designed to NOT fire on
        genuine claims, so review accuracy is preserved."""
        from .schema import coerce_row

        # Rule A — nothing usable to review: the judge can't add anything.
        if ctx.admissibility and not any(a.send_to_model for a in ctx.admissibility):
            return coerce_row(
                {
                    "claim_status": "not_enough_information",
                    "evidence_standard_met": False,
                    "valid_image": False,
                    "issue_type": "unknown",
                    "object_part": "unknown",
                    "severity": "unknown",
                    "risk_flags": ["manual_review_required"],
                    "claim_status_justification": "No usable image was available to review; routed to manual review.",
                    "evidence_standard_met_reason": "no admissible image",
                },
                ctx.claim_object,
            )

        # Rule B — two INDEPENDENT signals agree it's the wrong object:
        #   (1) the CLIP object-consistency tool asserted wrong_object, AND
        #   (2) every image's perception guessed a different, known object.
        clip_wrong = any(
            "wrong_object" in (t.risk_flags or [])
            for t in tool_results
            if t.name == "object_consistency"
        )
        guesses = [str(p.get("object_guess", "")).strip().lower() for p in (ctx.perceptions or [])]
        perc_wrong = bool(guesses) and all(
            g not in ("", "unknown", ctx.claim_object) for g in guesses
        )
        if clip_wrong and perc_wrong:
            return coerce_row(
                {
                    "claim_status": "not_enough_information",
                    "evidence_standard_met": False,
                    "valid_image": True,
                    "issue_type": "unknown",
                    "object_part": "unknown",
                    "severity": "unknown",
                    "risk_flags": ["wrong_object", "claim_mismatch", "manual_review_required"],
                    "claim_status_justification": (
                        f"The submitted image does not appear to be the claimed {ctx.claim_object} "
                        "(an independent CLIP check and the perception model agree); the claim cannot be evaluated."
                    ),
                    "evidence_standard_met_reason": "image is not the claimed object",
                },
                ctx.claim_object,
            )
        return None

    # --- deterministic fusion of tool flags + escalation on top of the judge ---
    def _fuse(self, decision, ctx, tool_results):
        flags = {f for f in decision["risk_flags"].split(";") if f != "none"}

        # union deterministic tool-asserted flags
        for r in tool_results:
            flags.update(r.risk_flags)

        # union intake/admissibility flags (e.g. blurry_image, manual_review)
        for a in ctx.admissibility:
            flags.update(a.risk_flags)
        # if NO image was admissible for review, the set is not usable
        if ctx.admissibility and not any(a.valid_image for a in ctx.admissibility):
            decision["valid_image"] = False

        # text-channel prompt-injection guard on the conversation (L3): the
        # claimant's words are untrusted — a directive in them is flagged, never
        # obeyed (the judge decides from pixels). Same flag as the image side.
        try:
            _, text_flags = sanitize_claim_text(ctx.user_claim)
            flags.update(text_flags)
        except Exception:
            pass

        # history risk (explicit flag column only — judge handles summary-based risk)
        hist = ctx.user_history or {}
        hflags = (hist.get("history_flags") or "none").strip().lower()
        if hflags not in ("none", "", "0"):
            flags.add("user_history_risk")

        # Normalize ONCE to the canonical set, THEN run escalation on that exact
        # set, so the trace's confidence and the row's flags never disagree.
        canon = {
            f
            for f in normalize_risk_flags(sorted(flags), ctx.claim_object).split(";")
            if f != "none"
        }
        esc = self.escalation.decide(decision["claim_status"], canon, hist)
        canon |= esc["flags_to_add"]
        decision["_escalation"] = esc
        decision["risk_flags"] = normalize_risk_flags(sorted(canon), ctx.claim_object)

        # backfill a supporting image only if supported-but-empty, and only cite a
        # genuinely usable, non-duplicate image (never a borderline/reused one).
        if decision["claim_status"] == "supported" and decision["supporting_image_ids"] == "none":
            dups = set(ctx.cv_result.get("duplicate_image_ids", []))
            good = [
                c["image_id"]
                for c in ctx.cv_result.get("images", [])
                if c.get("usable")
                and (c.get("small_side") or 0) >= 256
                and c["image_id"] not in dups
            ]
            if good:
                decision["supporting_image_ids"] = normalize_image_ids(good[:1])

        decision["evidence_standard_met"] = "true" if decision["evidence_standard_met"] else "false"
        decision["valid_image"] = "true" if decision["valid_image"] else "false"
        return decision

    # --- batch (bounded concurrency for TPM/RPM safety) ---
    def process_rows(self, rows: list[dict]) -> list[dict]:
        results = [None] * len(rows)
        workers = max(1, self.cfg.max_concurrency)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self.process_claim, r, i): i for i, r in enumerate(rows)}
            done = 0
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    results[i] = fut.result()
                except Exception as e:
                    results[i] = self._error_row(rows[i], e)
                done += 1
                if self.verbose:
                    print(
                        f"  [{done}/{len(rows)}] {rows[i].get('user_id', '?')} "
                        f"{rows[i].get('claim_object', '?')}",
                        flush=True,
                    )
        return results

    def _error_row(self, row, err):
        base = {k: row.get(k, "") for k in OUTPUT_COLUMNS}
        base.update(
            {
                "evidence_standard_met": "false",
                "evidence_standard_met_reason": f"pipeline error: {err}",
                "risk_flags": "manual_review_required",
                "issue_type": "unknown",
                "object_part": "unknown",
                "claim_status": "not_enough_information",
                "claim_status_justification": "processing error",
                "supporting_image_ids": "none",
                "valid_image": "false",
                "severity": "unknown",
            }
        )
        return base
