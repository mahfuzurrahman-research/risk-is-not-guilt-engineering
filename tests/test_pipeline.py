import unittest
from pathlib import Path
from src.risk_engineering.pipeline import run_pipeline
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_e2e(self):
  o=run_pipeline(ROOT);self.assertEqual(o["quality"]["status"],"PASS");self.assertEqual(o["python_sql_parity"]["status"],"PASS");self.assertEqual(o["readiness"]["gate_result"],"NOT_READY");self.assertEqual(o["temporal"]["gate_result"],"BLOCKED_UNRESOLVED")
if __name__=="__main__":unittest.main()
