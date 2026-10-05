import unittest
from pathlib import Path
from src.risk_engineering.gates import evaluate_readiness,evaluate_temporal_gate
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_ready(self):
  o=evaluate_readiness(ROOT/"contracts/prediction_readiness_demo.json");self.assertEqual(o["gate_result"],"NOT_READY");self.assertFalse(o["release_authorized"])
 def test_temporal(self):
  o=evaluate_temporal_gate(ROOT/"data/synthetic/linkage_records.csv",ROOT/"contracts/temporal_integrity_demo.json");self.assertEqual(o["gate_result"],"BLOCKED_UNRESOLVED");self.assertGreater(o["future_available_records"],0)
if __name__=="__main__":unittest.main()
