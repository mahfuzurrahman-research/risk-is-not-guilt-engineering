from __future__ import annotations
import csv, hashlib, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def _apply(con, rel): con.executescript((ROOT/rel).read_text(encoding="utf-8"))

def build_warehouse(input_csv:Path, db_path:Path)->dict:
    input_csv=Path(input_csv); db_path=Path(db_path); db_path.parent.mkdir(parents=True,exist_ok=True)
    if db_path.exists(): db_path.unlink()
    con=sqlite3.connect(db_path); con.row_factory=sqlite3.Row; con.execute("PRAGMA foreign_keys=ON")
    _apply(con,"sql/schema.sql")
    with input_csv.open("r",encoding="utf-8",newline="") as h: rows=list(csv.DictReader(h))
    aliases=sorted({r["entity_alias"] for r in rows if r["link_basis"]=="DIRECT_KEY" and r["entity_alias"]})
    with con:
        con.executemany("INSERT INTO entities(entity_alias) VALUES (?)",[(x,) for x in aliases])
        con.executemany("""INSERT INTO linkage_records(record_id,entity_alias,link_basis,publication_flag,workflow_status,available_date,event_date)
        VALUES (?,?,?,?,?,?,?)""",[(r["record_id"],r["entity_alias"] or None,r["link_basis"],int(r["publication_flag"]),r["workflow_status"],r["available_date"],r["event_date"]) for r in rows])
        con.execute("""INSERT INTO ingestion_runs(source_file,source_sha256,input_rows,loaded_entities,loaded_records)
        VALUES (?,?,?,?,?)""",(input_csv.name,hashlib.sha256(input_csv.read_bytes()).hexdigest(),len(rows),len(aliases),len(rows)))
    _apply(con,"sql/marts.sql"); _apply(con,"sql/quality_checks.sql")
    if con.execute("PRAGMA integrity_check").fetchone()[0]!="ok" or con.execute("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("SQLite integrity verification failed")
    return {"connection":con,"input_rows":len(rows),"loaded_entities":len(aliases)}

def quality_summary(con):
    rows=con.execute("SELECT check_name,violations FROM quality_results ORDER BY check_name").fetchall()
    failures=sum(int(r["violations"]) for r in rows)
    return {"checks":len(rows),"failures":failures,"status":"PASS" if failures==0 else "FAIL"}

def sql_profile(con): return dict(con.execute("SELECT * FROM mart_linkage_summary").fetchone())
