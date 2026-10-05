from pathlib import Path
import json, html
ROOT=Path(__file__).resolve().parents[1]
obj=json.loads((ROOT/"outputs/audit_summary.json").read_text(encoding="utf-8"))
p=obj["profile"];q=obj["quality"];r=obj["readiness"];t=obj["temporal"]
doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>Risk Is Not Guilt — Engineering Demo</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:980px;margin:40px auto;padding:0 20px;line-height:1.5}}.card{{border:1px solid #ddd;border-radius:12px;padding:18px;margin:14px 0}}</style>
</head><body><h1>Risk Is Not Guilt — Research Engineering Demonstration</h1>
<p>All records shown here are synthetic.</p>
<div class="card"><h2>Pipeline health</h2><p>Relational QA: <strong>{html.escape(q['status'])}</strong></p><p>Checks: {q['checks']} · Failures: {q['failures']}</p></div>
<div class="card"><h2>Synthetic linkage profile</h2><p>Rows: {p['total_rows']} · Direct rows: {p['direct_rows']} · Process-only rows: {p['process_only_rows']}</p><p>Unique direct entities: {p['unique_direct_entities']}</p></div>
<div class="card"><h2>Fail-closed gates</h2><p>Readiness: <strong>{html.escape(r['gate_result'])}</strong></p><p>Temporal: <strong>{html.escape(t['gate_result'])}</strong></p></div>
<div class="card"><h2>Boundary</h2><p>This dashboard demonstrates validation, relational QA, parity and gate behavior. It contains no private study result.</p></div>
</body></html>"""
(ROOT/"outputs/dashboard.html").write_text(doc,encoding="utf-8")
print("DASHBOARD=PASS")
