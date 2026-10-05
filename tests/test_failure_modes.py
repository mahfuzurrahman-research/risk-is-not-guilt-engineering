import tempfile,unittest,csv
from pathlib import Path
from src.risk_engineering.contracts import validate_csv
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def mk(self,row):
  td=tempfile.TemporaryDirectory();p=Path(td.name)/"x.csv"
  with p.open("w",newline="",encoding="utf-8") as f:
   w=csv.writer(f);w.writerow(["record_id","entity_alias","link_basis","publication_flag","workflow_status","available_date","event_date"]);w.writerow(row)
  return td,p
 def test_bad_flag(self):
  td,p=self.mk(["X","E","DIRECT_KEY","7","published","2025-01-02","2025-01-01"])
  try:
   with self.assertRaises(ValueError):validate_csv(p,ROOT/"contracts/linkage_contract.json")
  finally:td.cleanup()
 def test_blank_status(self):
  td,p=self.mk(["X","E","DIRECT_KEY","1","","2025-01-02","2025-01-01"])
  try:
   with self.assertRaises(ValueError):validate_csv(p,ROOT/"contracts/linkage_contract.json")
  finally:td.cleanup()
if __name__=="__main__":unittest.main()
