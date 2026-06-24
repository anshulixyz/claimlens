#!/usr/bin/env python3
"""Evaluation harness.

- Runs the pipeline on dataset/sample_claims.csv (which has gold labels).
- Compares >=2 strategies / model configurations.
- Prints a metrics table, writes per-strategy predictions, and generates
  evaluation/evaluation_report.md with the operational analysis.

Usage:
    python code/evaluation/main.py
    python code/evaluation/main.py --strategies heuristic_mock,gemini+claude
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

from evaluation import metrics as M
from evaluation.report import write_report
from evidence_review import Config, Pipeline
from evidence_review import config as cfgmod
from evidence_review.dataio import read_csv
from evidence_review.schema import OUTPUT_COLUMNS

HERE = Path(__file__).resolve().parent


def available_strategies(cfg: Config):
    """Define candidate strategies; keep those whose keys are present.

    Each strategy = (name, perception_provider, perception_model, judge_provider, judge_model).
    'heuristic_mock' always runs (no key) and is the baseline both real tiers beat.
    """
    out = [("heuristic_mock", "mock", "mock", "mock", "mock")]
    if cfg.gemini_key:
        out.append(("gemini_only", "gemini", "gemini-2.5-flash-lite", "gemini", "gemini-2.5-flash"))
    if cfg.gemini_key and cfg.anthropic_key:
        out.append(
            ("gemini+claude", "gemini", "gemini-2.5-flash-lite", "claude", "claude-sonnet-4-6")
        )
    elif cfg.anthropic_key:
        out.append(
            ("claude_only", "claude", "claude-haiku-4-5-20251001", "claude", "claude-sonnet-4-6")
        )
    return out


def run_strategy(name, pp, pm, jp, jm, golds):
    cfg = Config(perception_provider=pp, perception_model=pm, judge_provider=jp, judge_model=jm)
    pipe = Pipeline(cfg, use_cache=True, verbose=False)
    t0 = time.time()
    preds = pipe.process_rows(
        [{k: g[k] for k in ("user_id", "image_paths", "user_claim", "claim_object")} for g in golds]
    )
    dt = time.time() - t0
    scores = M.evaluate(preds, golds)
    usage = pipe.usage.report()
    # save predictions for inspection
    pred_path = HERE / f"preds_{name}.csv"
    with open(pred_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(preds)
    return {
        "name": name,
        "config": f"{pp}:{pm} -> {jp}:{jm}",
        "scores": scores,
        "usage": usage,
        "runtime_s": round(dt, 2),
        "preds_path": str(pred_path.relative_to(cfgmod.REPO_ROOT)),
    }


def print_table(results):
    print("\n=== STRATEGY COMPARISON (sample_claims.csv) ===")
    hdr = f"{'strategy':18} {'status_acc':>10} {'status_f1':>10} {'evid_acc':>9} {'issue_acc':>10} {'part_acc':>9} {'risk_f1':>8} {'cost$':>9} {'sec':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        s = r["scores"]
        print(
            f"{r['name']:18} {s['claim_status_acc']:>10.3f} {s['claim_status_macro_f1']:>10.3f} "
            f"{s['evidence_standard_met_acc']:>9.3f} {s['issue_type_acc']:>10.3f} "
            f"{s['object_part_acc']:>9.3f} {s['risk_flags']['f1']:>8.3f} "
            f"{r['usage']['estimated_cost_usd']:>9.4f} {r['runtime_s']:>6.1f}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default="", help="comma list to restrict")
    ap.add_argument("--sample", default=str(cfgmod.SAMPLE_CSV))
    args = ap.parse_args()

    cfg = Config()
    golds = read_csv(args.sample)
    print(f"[eval] {len(golds)} labeled sample claims")

    strategies = available_strategies(cfg)
    if args.strategies:
        wanted = set(args.strategies.split(","))
        strategies = [s for s in strategies if s[0] in wanted]
    print(f"[eval] strategies: {[s[0] for s in strategies]}")

    results = []
    for name, pp, pm, jp, jm in strategies:
        print(f"[eval] running '{name}' ({pp}:{pm} -> {jp}:{jm}) ...")
        results.append(run_strategy(name, pp, pm, jp, jm, golds))

    print_table(results)

    # pick the best real strategy (highest status_f1, prefer non-mock)
    real = [r for r in results if "mock" not in r["config"]] or results
    best = max(real, key=lambda r: r["scores"]["claim_status_macro_f1"])
    print(f"\n[eval] recommended final strategy: {best['name']} ({best['config']})")

    report_path = write_report(results, best, n_sample=len(golds))
    print(f"[eval] wrote {report_path}")
    # machine-readable dump
    (HERE / "metrics.json").write_text(json.dumps(results, indent=2))

    # self-contained visual dashboard (reads the artifacts we just wrote)
    try:
        from evaluation.dashboard import main as build_dashboard

        build_dashboard()
    except Exception as e:
        print(f"[eval] dashboard skipped: {e}")


if __name__ == "__main__":
    main()
