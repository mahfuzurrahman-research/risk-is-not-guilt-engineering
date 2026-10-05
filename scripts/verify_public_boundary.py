from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
for rel in ["manuscript","supplement","future-study","provenance","framework","results/tables"]:
    if (ROOT/rel).exists(): raise SystemExit(f"PRIVATE_PATH_PRESENT={rel}")
# Exact private-study counts and private asset names must not appear in this companion.
patterns=[r"\b460\b",r"\b406\b",r"\b126\b",r"\b112\b",r"\b280\b",r"manuscript\.pdf",r"methods_supplement"]
ignored_dirs={".git", ".venv", "__pycache__", "outputs"}
for p in ROOT.rglob("*"):
    if not p.is_file() or ignored_dirs.intersection(p.relative_to(ROOT).parts) or p == Path(__file__).resolve() or p.suffix.lower() in {".sqlite",".zip",".png",".jpg",".jpeg",".joblib"}: continue
    txt=p.read_text(encoding="utf-8",errors="ignore")
    for pat in patterns:
        if re.search(pat,txt,flags=re.I): raise SystemExit(f"PRIVATE_PATTERN_FOUND={pat}::{p.relative_to(ROOT)}")
print("PUBLIC_BOUNDARY_SCAN=PASS")
