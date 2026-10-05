import tempfile,unittest
from pathlib import Path
from src.risk_engineering.warehouse import build_warehouse,quality_summary
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_wh(self):
  with tempfile.TemporaryDirectory() as td:
   obj=build_warehouse(ROOT/"data/synthetic/linkage_records.csv",Path(td)/"d.sqlite");con=obj["connection"]
   try:q=quality_summary(con);self.assertEqual(q["status"],"PASS");self.assertEqual(q["failures"],0);self.assertGreaterEqual(q["checks"],9)
   finally:con.close()
if __name__=="__main__":unittest.main()
