#!/usr/bin/env python3
"""Entry point: run the evidence-review pipeline on a claims CSV -> output.csv.

Usage:
    python code/main.py                       # dataset/claims.csv -> output.csv
    python code/main.py --input dataset/sample_claims.csv --output sample_out.csv
    python code/main.py --no-cache            # ignore the perception cache

Models & keys come from code/.env (see code/.env.example). With no keys the
pipeline runs in deterministic 'mock' mode so it always completes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence_review import Config, Pipeline
from evidence_review import config as cfgmod
from evidence_review.dataio import read_csv
from evidence_review.schema import OUTPUT_COLUMNS


def main():
    ap = argparse.ArgumentParser(description="Multi-modal evidence review")
    ap.add_argument("--input", default=str(cfgmod.CLAIMS_CSV))
    ap.add_argument("--output", default=str(cfgmod.REPO_ROOT / "output.csv"))
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="process only first N rows (debug)")
    args = ap.parse_args()

    cfg = Config()
    print(f"[config] {cfg.summary()}")
    if cfg.perception_provider == "mock" or cfg.judge_provider == "mock":
        print(
            "[note] running with a MOCK tier (no API key for that tier). "
            "Add keys to code/.env for real model output."
        )

    rows = read_csv(args.input)
    if args.limit:
        rows = rows[: args.limit]
    print(f"[run] {len(rows)} claims from {args.input}")

    pipe = Pipeline(cfg, use_cache=not args.no_cache)
    t0 = time.time()
    results = pipe.process_rows(rows)
    dt = time.time() - t0

    out_path = Path(args.output)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in results:
            w.writerow(r)

    print(f"[done] wrote {len(results)} rows -> {out_path} in {dt:.1f}s")
    print("[usage] " + json.dumps(pipe.usage.report(), indent=2))


if __name__ == "__main__":
    main()
