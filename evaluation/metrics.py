"""Metrics for evidence-review predictions vs. gold sample labels."""

from __future__ import annotations

from collections import Counter, defaultdict


def _norm(s):
    return (s or "").strip().lower()


def _flagset(s):
    s = _norm(s)
    if s in ("", "none"):
        return set()
    return {f for f in (x.strip() for x in s.replace(",", ";").split(";")) if f and f != "none"}


def accuracy(preds, golds, field):
    n = len(golds)
    correct = sum(1 for p, g in zip(preds, golds) if _norm(p[field]) == _norm(g[field]))
    return correct / n if n else 0.0


def macro_f1(preds, golds, field, labels=None):
    labels = labels or sorted({_norm(g[field]) for g in golds})
    f1s = []
    for lab in labels:
        tp = sum(
            1 for p, g in zip(preds, golds) if _norm(p[field]) == lab and _norm(g[field]) == lab
        )
        fp = sum(
            1 for p, g in zip(preds, golds) if _norm(p[field]) == lab and _norm(g[field]) != lab
        )
        fn = sum(
            1 for p, g in zip(preds, golds) if _norm(p[field]) != lab and _norm(g[field]) == lab
        )
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)
    return sum(f1s) / len(f1s) if f1s else 0.0


def risk_flag_prf(preds, golds):
    """Micro precision/recall/F1 over the multi-label risk_flags set."""
    tp = fp = fn = 0
    for p, g in zip(preds, golds):
        ps, gs = _flagset(p["risk_flags"]), _flagset(g["risk_flags"])
        tp += len(ps & gs)
        fp += len(ps - gs)
        fn += len(gs - ps)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def confusion(preds, golds, field):
    c = defaultdict(Counter)
    for p, g in zip(preds, golds):
        c[_norm(g[field])][_norm(p[field])] += 1
    return c


def evaluate(preds, golds):
    return {
        "n": len(golds),
        "claim_status_acc": accuracy(preds, golds, "claim_status"),
        "claim_status_macro_f1": macro_f1(
            preds, golds, "claim_status", ["supported", "contradicted", "not_enough_information"]
        ),
        "evidence_standard_met_acc": accuracy(preds, golds, "evidence_standard_met"),
        "valid_image_acc": accuracy(preds, golds, "valid_image"),
        "issue_type_acc": accuracy(preds, golds, "issue_type"),
        "object_part_acc": accuracy(preds, golds, "object_part"),
        "severity_acc": accuracy(preds, golds, "severity"),
        "risk_flags": risk_flag_prf(preds, golds),
    }
