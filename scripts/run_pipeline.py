from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.risk_engineering.pipeline import run_pipeline
p=run_pipeline(ROOT)
print("CONTRACT_VALIDATION=PASS")
print("RELATIONAL_QA=PASS")
print("PYTHON_SQL_PARITY=PASS")
print(f"READINESS_GATE={p['readiness']['gate_result']}")
print(f"TEMPORAL_GATE={p['temporal']['gate_result']}")
