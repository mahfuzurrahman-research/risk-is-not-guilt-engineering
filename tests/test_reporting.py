import tempfile,unittest
from pathlib import Path
from src.risk_engineering.reporting import write_reports
class T(unittest.TestCase):
 def test_reports(self):
  p={"profile":{"total_rows":1,"direct_rows":1,"process_only_rows":0,"unique_direct_entities":1},"quality":{"checks":10,"failures":0,"status":"PASS"},"readiness":{"gate_result":"NOT_READY","release_authorized":False},"temporal":{"gate_result":"BLOCKED_UNRESOLVED","future_available_records":1}}
  with tempfile.TemporaryDirectory() as td:
   out=Path(td);write_reports(p,out);self.assertTrue((out/"audit_summary.json").is_file());self.assertTrue((out/"audit_report.md").is_file())
if __name__=="__main__":unittest.main()
