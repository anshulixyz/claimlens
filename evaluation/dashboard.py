#!/usr/bin/env python3
"""Generate a self-contained ClaimLens evaluation dashboard (dashboard.html).

Reads the evaluation artifacts already produced by evaluation/main.py
(metrics.json, preds_<strategy>.csv) plus the gold sample labels, and emits ONE
static HTML file with the data inlined — so it opens directly (file://), no
server, no external fetch. It is an observability/eval surface, not new plumbing:
it just visualizes the trace/metrics artifacts the pipeline already emits.

Usage:  python code/evaluation/dashboard.py   ->  code/evaluation/dashboard.html
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE_DIR = HERE.parent
sys.path.insert(0, str(CODE_DIR))

from evidence_review import config as cfgmod

FIELDS = [
    "claim_status",
    "evidence_standard_met",
    "issue_type",
    "object_part",
    "severity",
    "valid_image",
]


def _read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_data():
    metrics_path = HERE / "metrics.json"
    results = json.loads(metrics_path.read_text()) if metrics_path.exists() else []

    gold = _read_csv(cfgmod.SAMPLE_CSV)
    gkey = {g["user_id"] + g["image_paths"]: g for g in gold}

    # find the recommended (best non-mock) strategy's predictions
    real = [r for r in results if "mock" not in r["config"]] or results
    best = max(real, key=lambda r: r["scores"]["claim_status_macro_f1"]) if real else None
    per_claim, confusion = [], {}
    if best:
        preds = _read_csv(cfgmod.REPO_ROOT / best["preds_path"])
        labels = ["supported", "contradicted", "not_enough_information"]
        confusion = {a: dict.fromkeys(labels, 0) for a in labels}
        for p in preds:
            g = gkey.get(p["user_id"] + p["image_paths"])
            if not g:
                continue
            gs, ps = g["claim_status"], p["claim_status"]
            if gs in confusion and ps in confusion[gs]:
                confusion[gs][ps] += 1
            per_claim.append(
                {
                    "user_id": g["user_id"],
                    "claim_object": g["claim_object"],
                    "claim": g["user_claim"][:140],
                    "fields": {
                        f: {
                            "gold": g.get(f, ""),
                            "pred": p.get(f, ""),
                            "ok": (g.get(f, "").strip().lower() == p.get(f, "").strip().lower()),
                        }
                        for f in FIELDS
                    },
                    "risk_gold": g.get("risk_flags", ""),
                    "risk_pred": p.get("risk_flags", ""),
                    "justification": p.get("claim_status_justification", ""),
                }
            )

    return {
        "results": results,
        "best": best,
        "confusion": confusion,
        "per_claim": per_claim,
        "fields": FIELDS,
    }


def render(data) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return _TEMPLATE.replace("/*__DATA__*/", payload)


_TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ClaimLens — Evaluation Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
:root{--brand:#4F46E5;--brand-tint:#EEEDFE;--ink:#0B0F19;--ink2:#434A56;--muted:#777F8C;--bg:#F6F7FA;
--soft:#FAFBFD;--line:#E6E9EF;--line2:#EFF1F6;--good:#15924E;--goodbg:#E8F6EE;--bad:#DC4B4F;--badbg:#FCEDED;
--disp:"Plus Jakarta Sans",system-ui,sans-serif;--mono:"JetBrains Mono",ui-monospace,monospace;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);background-image:linear-gradient(180deg,#fff 0%,#F6F7FA 62%);color:var(--ink);
font-family:Inter,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5}
.wrap{max-width:1040px;margin:0 auto;padding:24px 18px 60px}
.top{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.mark{width:28px;height:28px}.brand{font-family:var(--disp);font-weight:800;font-size:1.32rem;letter-spacing:-.02em}
.brand b{color:var(--brand)}.sub{color:var(--ink2);margin:0 0 24px;font-size:.95rem;max-width:74ch}
h2{font-family:var(--disp);font-size:1.08rem;font-weight:700;margin:28px 0 12px;letter-spacing:-.01em}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:0 4px 16px rgba(16,24,40,.05)}
.card .lbl{color:var(--muted);font-family:var(--mono);font-size:.7rem;font-weight:500;text-transform:uppercase;letter-spacing:.06em}
.card .val{font-family:var(--disp);font-size:1.7rem;font-weight:800;margin-top:5px;color:var(--brand)}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 4px 16px rgba(16,24,40,.05)}
th,td{padding:10px 13px;text-align:left;font-size:.85rem;border-bottom:1px solid var(--line2)}
th{background:var(--soft);color:var(--ink2);font-family:var(--mono);font-weight:500;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono)}
tr:last-child td{border-bottom:0}
.best{background:var(--brand-tint)}
.cm{display:inline-grid;gap:4px;margin-top:6px}
.cm .cell{padding:9px 13px;border-radius:9px;font-size:.82rem;text-align:center;font-weight:600}
.cm .hd{background:var(--soft);color:var(--ink2);font-family:var(--mono);font-weight:500;font-size:.74rem}
.cm .diag{background:var(--goodbg);color:var(--good)}
.cm .off{background:#fff;border:1px solid var(--line);color:var(--muted)}
.cm .miss{background:var(--badbg);color:var(--bad)}
.claim{background:#fff;border:1px solid var(--line);border-radius:16px;padding:15px 17px;margin-bottom:10px;box-shadow:0 4px 16px rgba(16,24,40,.05)}
.claim .h{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:6px}
.claim .id{font-family:var(--disp);font-weight:800}.tag{font-family:var(--mono);font-size:.68rem;font-weight:500;padding:3px 10px;border-radius:999px;background:var(--brand-tint);color:var(--brand);text-transform:uppercase;letter-spacing:.04em}
.claim .txt{color:var(--ink2);font-size:.84rem;margin:0 0 10px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-family:var(--mono);font-size:.72rem;padding:4px 9px;border-radius:8px;font-weight:500}
.chip.ok{background:var(--goodbg);color:var(--good)}.chip.no{background:var(--badbg);color:var(--bad)}
.just{color:var(--muted);font-size:.8rem;margin-top:8px;font-style:italic}
.note{color:var(--muted);font-size:.78rem;margin-top:10px}
</style></head><body><div class="wrap">
<div class="top"><svg class="mark" viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" fill="none" stroke="#4F46E5" stroke-width="3.5"/><circle cx="20" cy="20" r="6.5" fill="#4F46E5"/><path d="M20 4 a16 16 0 0 1 13.8 8" fill="none" stroke="#15924E" stroke-width="3.5" stroke-linecap="round"/></svg>
<span class="brand">Claim<b>Lens</b> · Evaluation</span></div>
<p class="sub">Sample-set evaluation &amp; per-claim decision audit. Metrics on 20 labeled rows are <b>directional</b> (small n, judge nondeterminism) — read the confusion matrix, not just the headline.</p>
<div id="kpis" class="cards"></div>
<h2>Strategy comparison</h2><div id="strat"></div>
<h2>claim_status confusion (gold → predicted)</h2><div id="cm"></div>
<h2>Per-claim audit</h2><div id="claims"></div>
<p class="note">Generated by <code>evaluation/dashboard.py</code> from <code>metrics.json</code> + predictions. Per-claim runtime traces (full tool→judge→escalation chain) are emitted to <code>code/.cache/traces/</code> when the pipeline runs with <code>trace=True</code>.</p>
</div><script>
const DATA=/*__DATA__*/;
const $=(s)=>document.querySelector(s);
function pct(x){return (x*100).toFixed(0)+"%";}
(function(){
 const b=DATA.best;
 if(b){const s=b.scores,u=b.usage;
  $("#kpis").innerHTML=[
   ["Final strategy",b.name],
   ["claim_status acc",pct(s.claim_status_acc)],
   ["macro-F1",s.claim_status_macro_f1.toFixed(2)],
   ["issue_type acc",pct(s.issue_type_acc)],
   ["object_part acc",pct(s.object_part_acc)],
   ["risk-flag F1",s.risk_flags.f1.toFixed(2)],
   ["sample cost",("$"+u.estimated_cost_usd.toFixed(3))],
  ].map(([l,v])=>`<div class="card"><div class="lbl">${l}</div><div class="val" style="font-size:${String(v).length>9?'1.1rem':'1.7rem'}">${v}</div></div>`).join("");
 }
 // strategy table
 let rows=DATA.results.map(r=>{const s=r.scores;const cls=(DATA.best&&r.name===DATA.best.name)?'best':'';
  return `<tr class="${cls}"><td>${r.name}</td><td class="num">${pct(s.claim_status_acc)}</td>
  <td class="num">${s.claim_status_macro_f1.toFixed(2)}</td><td class="num">${pct(s.evidence_standard_met_acc)}</td>
  <td class="num">${pct(s.issue_type_acc)}</td><td class="num">${pct(s.object_part_acc)}</td>
  <td class="num">${s.risk_flags.f1.toFixed(2)}</td><td class="num">$${r.usage.estimated_cost_usd.toFixed(3)}</td>
  <td class="num">${r.runtime_s.toFixed(0)}s</td></tr>`;}).join("");
 $("#strat").innerHTML=`<table><tr><th>strategy</th><th class="num">status acc</th><th class="num">macroF1</th>
  <th class="num">evid</th><th class="num">issue</th><th class="num">part</th><th class="num">risk F1</th>
  <th class="num">cost</th><th class="num">time</th></tr>${rows}</table>`;
 // confusion matrix
 const cm=DATA.confusion,labs=["supported","contradicted","not_enough_information"];
 if(cm&&Object.keys(cm).length){
  let g=`<div class="cm" style="grid-template-columns:repeat(${labs.length+1},auto)">`;
  g+=`<div class="cell hd">gold ＼ pred</div>`+labs.map(l=>`<div class="cell hd">${l.replace(/_/g,' ')}</div>`).join("");
  labs.forEach(gl=>{g+=`<div class="cell hd">${gl.replace(/_/g,' ')}</div>`;
   labs.forEach(pl=>{const v=cm[gl][pl];const c=gl===pl?'diag':(v>0?'miss':'off');g+=`<div class="cell ${c}">${v}</div>`;});});
  g+="</div>";$("#cm").innerHTML=g;
 }
 // per-claim
 $("#claims").innerHTML=DATA.per_claim.map(c=>{
  const chips=DATA.fields.map(f=>{const x=c.fields[f];return `<span class="chip ${x.ok?'ok':'no'}">${f}: ${x.pred||'∅'}${x.ok?'':' ✗('+x.gold+')'}</span>`;}).join("");
  return `<div class="claim"><div class="h"><span class="id">${c.user_id}</span><span class="tag">${c.claim_object}</span></div>
   <p class="txt">${c.claim}…</p><div class="chips">${chips}</div>
   <div class="just">“${c.justification}”</div></div>`;}).join("");
})();
</script></body></html>"""


def main():
    data = build_data()
    out = HERE / "dashboard.html"
    out.write_text(render(data), encoding="utf-8")
    n = len(data["per_claim"])
    print(
        f"[dashboard] wrote {out.relative_to(cfgmod.REPO_ROOT)} ({n} claims, "
        f"{len(data['results'])} strategies)"
    )


if __name__ == "__main__":
    main()
