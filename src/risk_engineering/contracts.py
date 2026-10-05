from __future__ import annotations
import csv, json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ContractValidationResult:
    rows_checked: int
    contract_name: str
    contract_version: str

def load_contract(path: Path) -> dict:
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    required={"contract_name","contract_version","required_columns","allowed_link_basis","allowed_publication_flags","rules"}
    missing=required-set(obj)
    if missing: raise ValueError(f"Malformed contract; missing: {sorted(missing)}")
    return obj

def validate_csv(input_csv: Path, contract_path: Path) -> ContractValidationResult:
    contract=load_contract(contract_path)
    with Path(input_csv).open("r",encoding="utf-8",newline="") as h:
        reader=csv.DictReader(h); fields=set(reader.fieldnames or [])
        missing=set(contract["required_columns"])-fields
        if missing: raise ValueError(f"Missing required columns: {sorted(missing)}")
        seen=set(); n=0
        for line,row in enumerate(reader,start=2):
            n+=1
            rid=(row.get("record_id") or "").strip()
            alias=(row.get("entity_alias") or "").strip()
            basis=(row.get("link_basis") or "").strip()
            flag=(row.get("publication_flag") or "").strip()
            status=(row.get("workflow_status") or "").strip()
            if not rid: raise ValueError(f"Row {line}: blank record_id")
            if rid in seen: raise ValueError(f"Row {line}: duplicate record_id")
            seen.add(rid)
            if basis not in contract["allowed_link_basis"]: raise ValueError(f"Row {line}: invalid link_basis")
            if flag not in contract["allowed_publication_flags"]: raise ValueError(f"Row {line}: invalid publication_flag")
            if not status: raise ValueError(f"Row {line}: blank workflow_status")
            if basis=="DIRECT_KEY" and not alias: raise ValueError(f"Row {line}: DIRECT_KEY requires entity_alias")
    return ContractValidationResult(n,contract["contract_name"],contract["contract_version"])
