from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parents[1]
con=sqlite3.connect(ROOT/"outputs/public_demo.sqlite")
try:
    for row in con.execute("SELECT * FROM mart_ingestion_health"): print(row)
finally: con.close()
