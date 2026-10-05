from __future__ import annotations
import json
from pathlib import Path

def write_reports(payload:dict,out_dir:Path):
    out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"audit_summary.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    p=payload["profile"]; q=payload["quality"]; r=payload["readiness"]; t=payload["temporal"]
    md=f"""# Public Engineering Audit

## Synthetic input
- Rows: {p['total_rows']}
- Direct-key rows: {p['direct_rows']}
- Process-only rows: {p['process_only_rows']}
- Unique direct entities: {p['unique_direct_entities']}

## Relational QA
- Checks: {q['checks']}
- Failures: {q['failures']}
- Status: **{q['status']}**

## Readiness gate
- Status: **{r['gate_result']}**
- Release authorized: **{str(r['release_authorized']).lower()}**

## Temporal gate
- Status: **{t['gate_result']}**
- Future-available records: {t['future_available_records']}

## Boundary
All records are synthetic. This report is engineering evidence only and contains no private study result.
"""
    (out_dir/"audit_report.md").write_text(md,encoding="utf-8")
