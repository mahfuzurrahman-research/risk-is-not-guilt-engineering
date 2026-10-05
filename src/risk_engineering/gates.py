from __future__ import annotations
import csv, json
from datetime import date
from pathlib import Path

def evaluate_readiness(contract_path:Path)->dict:
    obj=json.loads(Path(contract_path).read_text(encoding="utf-8"))
    ready=all(bool(v) for v in obj["required_conditions"].values())
    result="READY" if ready else "NOT_READY"
    if result!=obj["expected_gate_result"]: raise RuntimeError("Readiness gate contract mismatch")
    if obj.get("release_authorized") and result!="READY": raise RuntimeError("Release cannot be authorized while not ready")
    return {"gate_result":result,"release_authorized":bool(obj.get("release_authorized")),"conditions":obj["required_conditions"]}

def evaluate_temporal_gate(input_csv:Path,contract_path:Path)->dict:
    obj=json.loads(Path(contract_path).read_text(encoding="utf-8"))
    future=0; unknown=0
    with Path(input_csv).open("r",encoding="utf-8",newline="") as h:
        for row in csv.DictReader(h):
            a=(row.get("available_date") or "").strip(); e=(row.get("event_date") or "").strip()
            if not a or not e: unknown+=1; continue
            if date.fromisoformat(a)>date.fromisoformat(e): future+=1
    result="BLOCKED_UNRESOLVED" if (unknown or future) else "PASS"
    if result!=obj["expected_gate_result"]: raise RuntimeError("Temporal gate contract mismatch")
    return {"gate_result":result,"unknown_dates":unknown,"future_available_records":future}
