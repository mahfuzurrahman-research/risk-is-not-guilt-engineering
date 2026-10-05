import tempfile,unittest
from pathlib import Path
from src.risk_engineering.profiling import compute_profile
from src.risk_engineering.warehouse import build_warehouse,sql_profile
ROOT=Path(__file__).resolve().parents[1]
class T(unittest.TestCase):
 def test_parity(self):
  py=compute_profile(ROOT/"data/synthetic/linkage_records.csv").to_dict()
  with tempfile.TemporaryDirectory() as td:
   obj=build_warehouse(ROOT/"data/synthetic/linkage_records.csv",Path(td)/"d.sqlite");con=obj["connection"]
   try:sql=sql_profile(con)
   finally:con.close()
  for k,v in py.items():self.assertEqual(int(v),int(sql[k]))
if __name__=="__main__":unittest.main()
