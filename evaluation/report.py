"""Generate evaluation/evaluation_report.md (metrics + operational analysis)."""

from __future__ import annotations

from pathlib import Path

from evidence_review import config as cfgmod
from evidence_review.usage import price_for

HERE = Path(__file__).resolve().parent


# Test-set facts (dataset/claims.csv) used to project full-run cost — computed
# from the actual file so they never drift from the dataset.
def _test_set_facts() -> tuple[int, int]:
    import csv

    path = cfgmod.DATASET_DIR / "claims.csv"
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except OSError:
        return 44, 82  # known dataset facts if the file isn't present
    claims = len(rows)
    images = sum(
        len([p for p in (r.get("image_paths") or "").split(";") if p.strip()]) for r in rows
    )
    return claims, images


TEST_CLAIMS, TEST_IMAGES = _test_set_facts()


def _scale_costs(best):
    """Project sample usage to the full test set (linear, per-claim/per-image)."""
    u = best["usage"]
    tiers = u["by_tier"]
    proj = {}
    # perception scales by images, judge scales by claims
    for tier, t in tiers.items():
        if t["calls"] == 0:
            continue
        if tier == "perception":
            factor = TEST_IMAGES / max(1, t["images"]) if t["images"] else 0
        else:
            factor = TEST_CLAIMS / max(1, t["calls"])
        pin, pout = price_for(u["models"].get(tier, ""))
        in_tok = t["in"] * factor
        out_tok = t["out"] * factor
        cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout
        proj[tier] = {
            "calls": round(t["calls"] * factor),
            "in_tok": round(in_tok),
            "out_tok": round(out_tok),
            "cost_usd": round(cost, 5),
            "model": u["models"].get(tier, ""),
        }
    return proj


def write_report(results, best, n_sample):
    proj = _scale_costs(best)
    total_proj_cost = round(sum(p["cost_usd"] for p in proj.values()), 5)

    lines = []
    A = lines.append
    A("# Evaluation Report — Multi-Modal Evidence Review\n")
    A(
        "Evidence-review system over **car / laptop / package** damage claims. "
        "Tiered architecture: free deterministic CV (Tier 0) → cheap VLM perception "
        "(Tier 1) → strong judge (Tier 2). Models are pluggable per tier.\n"
    )

    # --- Strategy comparison ---
    A("## 1. Strategy comparison (on `dataset/sample_claims.csv`)\n")
    A(
        f"Evaluated on **{n_sample}** labeled sample claims. `heuristic_mock` is a "
        "no-model keyword baseline; the model strategies must beat it.\n"
    )
    A(
        "| strategy | config | claim_status acc | status macroF1 | evidence acc | issue acc | part acc | severity acc | risk_flag F1 | est. cost $ | runtime s |"
    )
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        s = r["scores"]
        A(
            f"| `{r['name']}` | {r['config']} | {s['claim_status_acc']:.3f} | "
            f"{s['claim_status_macro_f1']:.3f} | {s['evidence_standard_met_acc']:.3f} | "
            f"{s['issue_type_acc']:.3f} | {s['object_part_acc']:.3f} | {s['severity_acc']:.3f} | "
            f"{s['risk_flags']['f1']:.3f} | {r['usage']['estimated_cost_usd']:.4f} | {r['runtime_s']:.1f} |"
        )
    A("")
    A(
        f"**Final strategy chosen for `output.csv`: `{best['name']}` ({best['config']}).** "
        "Selected by highest claim_status macro-F1 among model-backed strategies "
        "(the primary decision metric), with risk-flag F1 as a tiebreaker.\n"
    )

    # --- Per-strategy predictions ---
    A(
        "Per-strategy predictions are saved next to this report "
        "(`preds_<strategy>.csv`) for inspection and error analysis.\n"
    )

    # --- Operational analysis ---
    A("## 2. Operational analysis\n")
    A("### Architecture & call budget\n")
    A(
        "Per claim the system makes **1 judge call**; per image it makes **1 perception "
        "call** (cached by image content hash, so re-runs are free). Tier 0 (CV: blur, "
        "exposure/glare, EXIF/provenance, perceptual-hash duplicate detection) is "
        "**deterministic and costs zero model calls**.\n"
    )
    bu = best["usage"]
    A(
        f"- Sample run: **{bu['total_model_calls']} model calls**, "
        f"**{bu['images_processed']} images**, **{bu['cache_hits']} cache hits**."
    )
    A(
        f"- Sample input tokens: {sum(t['in'] for t in bu['by_tier'].values()):,}; "
        f"output tokens: {sum(t['out'] for t in bu['by_tier'].values()):,}."
    )
    A(
        f"- Sample estimated cost: **${bu['estimated_cost_usd']:.4f}**, "
        f"runtime **{best['runtime_s']:.1f}s**.\n"
    )

    A(f"### Projected full test set (`claims.csv`: {TEST_CLAIMS} claims, {TEST_IMAGES} images)\n")
    A("| tier | model | calls | input tok | output tok | cost $ |")
    A("|---|---|---|---|---|---|")
    for tier, p in proj.items():
        A(
            f"| {tier} | `{p['model']}` | {p['calls']} | {p['in_tok']:,} | {p['out_tok']:,} | {p['cost_usd']:.5f} |"
        )
    A(f"| **total** | | | | | **{total_proj_cost:.5f}** |")
    A("")
    A(
        f"**Approx. full-test cost: ${total_proj_cost:.4f}** (list prices; see "
        "`evidence_review/usage.py`). Perception scales with image count, judge with "
        "claim count. Using Gemini Flash for perception keeps the per-image cost ~10–30× "
        "below a frontier VLM while reserving the strong judge for the single decision.\n"
    )

    A("### Pricing assumptions (USD / 1M tokens)\n")
    A("| model | input | output |")
    A("|---|---|---|")
    for _tier, p in proj.items():
        pin, pout = price_for(p["model"])
        A(f"| `{p['model']}` | {pin} | {pout} |")
    A("")

    A("### Latency, rate limits, batching, caching, retries\n")
    A(
        "- **Concurrency:** claims processed with a bounded thread pool "
        "(`MAX_CONCURRENCY`, default 4) to stay under provider TPM/RPM."
    )
    A(
        "- **Caching:** perception is content-addressed (`code/.cache/`) by "
        "`sha1(image) + model + prompt_version`; identical re-runs make **zero** calls."
    )
    A(
        "- **Batching:** one image per perception call keeps prompts small and cacheable; "
        "the judge receives compact JSON evidence rather than re-sending images."
    )
    A(
        "- **Retries:** model errors degrade gracefully to a `manual_review_required` "
        "row instead of crashing the batch."
    )
    A(
        "- **Cost control:** the cheapest capable model runs per tier; the expensive "
        "judge is called exactly once per claim.\n"
    )

    A("## 3. Reproducibility\n")
    A("- Keys read from env / `code/.env` only (never committed).")
    A(
        "- With **no keys**, every tier falls back to a deterministic `mock`, so the "
        "pipeline and this evaluation always run end-to-end."
    )
    A(
        "- All model outputs are snapped to the allowed enums in `evidence_review/schema.py`; "
        "deterministic rules (Tier 0) guarantee provenance/quality risk flags regardless of model.\n"
    )

    out = HERE / "evaluation_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out.relative_to(cfgmod.REPO_ROOT))
