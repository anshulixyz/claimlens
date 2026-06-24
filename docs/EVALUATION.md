# Evaluation

`evaluation/main.py` runs the pipeline on the labeled `dataset/sample_claims.csv`,
compares multiple strategies, and generates `evaluation/evaluation_report.md`
with metrics + the operational (cost/latency/RPM) analysis.

## Strategies compared (P9)
- `heuristic_mock` — no-model keyword baseline (the floor every model must beat).
- `gemini_only` — Gemini Flash-Lite perception → Gemini Flash judge.
- `gemini+claude` — Gemini Flash-Lite perception → Claude Sonnet judge (**final**).

Available strategies are auto-selected from the keys present (`config.Config`);
the recommended final strategy is the highest claim_status macro-F1 among
model-backed runs.

## Metrics (`evaluation/metrics.py`)
- Per-field **accuracy**: claim_status, evidence_standard_met, valid_image,
  issue_type, object_part, severity.
- **claim_status macro-F1** (primary decision metric).
- **risk_flags**: set-based micro precision / recall / F1 (multi-label).
- claim_status confusion matrix (for error analysis).

## Honesty about variance
The judge is not perfectly deterministic at `temperature=0`; repeated runs of the
final strategy vary by a few points (claim_status accuracy ≈ 0.75 ± 0.04). We
therefore:
- tuned only **general, domain-justified rules** (calibration rubrics, crack/
  shatter convention, abstention gate, evidence-based flagging) — **no fitting to
  individual samples** (the brief forbids hardcoded test labels);
- report `contradicted` as the hardest minority class (few examples) rather than
  over-tuning to it on 20 samples.

**Selection-on-test caveat:** the harness currently picks the "best" strategy by
score on the same 20 labeled rows. With `contradicted` n=5, one row swings
macro-F1 by ~0.07, so the selected score is **directional, not the system's true
accuracy**. With more data the right method is k-fold or repeated-run averaging
before selection. We report the metric as directional and lead with the per-class
confusion matrix, not the headline number. (Flagged in [REVIEW.md](./REVIEW.md).)

## Run
```bash
python code/evaluation/main.py                       # all available strategies
python code/evaluation/main.py --strategies gemini+claude
```
Outputs: `evaluation/evaluation_report.md`, `evaluation/preds_<strategy>.csv`,
`evaluation/metrics.json`, and `evaluation/dashboard.html`.

## Visual dashboard
`evaluation/main.py` also emits a **self-contained** `evaluation/dashboard.html`
(ClaimLens-branded) — open it directly in a browser, no server needed. It shows
the KPI cards, the strategy comparison, the `claim_status` confusion matrix, and a
per-claim audit (gold vs predicted per field, risk flags, justification). Regenerate
standalone with `python code/evaluation/dashboard.py`.

## Per-claim traces (observability, P10)
Run the pipeline with tracing to emit a full decision record per claim
(inputs → tool signals → perceptions → judge raw → escalation → final) under
`code/.cache/traces/`:
```python
Pipeline(cfg, trace=True)
```
