import tempfile,unittest,csv
from pathlib import Path
from src.risk_engineering.contracts import validate_csv
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_valid(self):
  r=validate_csv(ROOT/"data/synthetic/linkage_records.csv",ROOT/"contracts/linkage_contract.json"); self.assertGreater(r.rows_checked,0)
 def test_direct_requires_entity(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"b.csv"
   with p.open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f);w.writerow(["record_id","entity_alias","link_basis","publication_flag","workflow_status","available_date","event_date"]);w.writerow(["X","","DIRECT_KEY","1","published","2025-01-02","2025-01-01"])
   with self.assertRaises(ValueError): validate_csv(p,ROOT/"contracts/linkage_contract.json")
if __name__=="__main__":unittest.main()
