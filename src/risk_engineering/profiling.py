from __future__ import annotations
import csv
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass(frozen=True)
class LinkageProfile:
    total_rows:int; direct_rows:int; process_only_rows:int; unique_direct_entities:int
    any_published_entities:int; all_published_entities:int; mixed_publication_entities:int
    def to_dict(self): return asdict(self)

def compute_profile(path:Path)->LinkageProfile:
    with Path(path).open("r",encoding="utf-8",newline="") as h: rows=list(csv.DictReader(h))
    direct=[r for r in rows if r["link_basis"]=="DIRECT_KEY"]
    process=[r for r in rows if r["link_basis"]=="PROCESS_ONLY"]
    by=defaultdict(list)
    for r in direct: by[r["entity_alias"]].append(int(r["publication_flag"]))
    return LinkageProfile(len(rows),len(direct),len(process),len(by),
        sum(any(v) for v in by.values()),sum(all(v) for v in by.values()),
        sum(any(v) and not all(v) for v in by.values()))
