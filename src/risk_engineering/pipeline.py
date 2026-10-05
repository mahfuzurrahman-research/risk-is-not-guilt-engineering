from pathlib import Path
from .contracts import validate_csv
from .profiling import compute_profile
from .warehouse import build_warehouse,quality_summary,sql_profile
from .gates import evaluate_readiness,evaluate_temporal_gate
from .reporting import write_reports

def run_pipeline(root:Path)->dict:
    root=Path(root); csvp=root/"data/synthetic/linkage_records.csv"
    validation=validate_csv(csvp,root/"contracts/linkage_contract.json")
    profile=compute_profile(csvp).to_dict()
    wh=build_warehouse(csvp,root/"outputs/public_demo.sqlite"); con=wh["connection"]
    try: qa=quality_summary(con); sql=sql_profile(con)
    finally: con.close()
    if qa["status"]!="PASS": raise RuntimeError("Relational QA failed")
    fields=list(profile)
    mismatch={k:(profile[k],sql[k]) for k in fields if int(profile[k])!=int(sql[k])}
    if mismatch: raise RuntimeError(f"Python/SQL parity failed: {mismatch}")
    ready=evaluate_readiness(root/"contracts/prediction_readiness_demo.json")
    temporal=evaluate_temporal_gate(csvp,root/"contracts/temporal_integrity_demo.json")
    payload={"contract_validation":{"rows_checked":validation.rows_checked,"contract_name":validation.contract_name,"contract_version":validation.contract_version},
             "profile":profile,"quality":qa,"python_sql_parity":{"status":"PASS","mismatches":{}},
             "readiness":ready,"temporal":temporal}
    write_reports(payload,root/"outputs")
    return payload
