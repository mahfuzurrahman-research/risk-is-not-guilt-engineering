from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .contracts import EVALUATION_AT
from .detection import WEIGHTS
from .features import primitive_features

ROOT = Path(__file__).resolve().parents[1]


def build_warehouse(path: Path, records, labels, threats, scored, queue, policy, capacity):
    with sqlite3.connect(path) as connection:
        connection.executescript((ROOT / "sql/ads_abuse_validation.sql").read_text())
        for record in records:
            features = primitive_features(record)
            connection.execute("INSERT INTO observation_base VALUES (?,?,?,?,?)",
                               (record["observation_id"], record["campaign_id"], record["split"],
                                record["decision_at"], json.dumps(features["ad_topics"])))
            for context, page in features["pages"].items():
                connection.execute("INSERT INTO captures VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (record["observation_id"], context, page["final_url"], page["final_host"],
                                    json.dumps(page["topic_tags"]), int(page["password_input"]), int(page["external_form"]),
                                    len(page["download_links"]), int(page["static_js_reference_external"]),
                                    page["hop_count"], page["body_sha256"], page["template_sha256"]))
            connection.executemany("INSERT INTO candidate_urls VALUES (?,?)",
                                   [(record["observation_id"], url) for url in features["candidate_urls"]])
        connection.executemany("INSERT INTO threat_indicators VALUES (?,?,?)",
                               [(r["url"], r["available_at"], r["expires_at"]) for r in threats["indicators"]])
        connection.executemany("INSERT INTO reported_scores VALUES (?,?,?,?,?)",
                               [(r["observation_id"], json.dumps(r["signals"]), r["risk_score"], int(r["review_flag"]),
                                 int(r["content_change_baseline"])) for r in scored])
        connection.executemany("INSERT INTO labels VALUES (?,?,?)",
                               [(r["observation_id"], int(r["is_abuse"]), r["available_at"]) for r in labels])
        connection.executemany("INSERT INTO reported_queue VALUES (?,?,?,?,?)",
                               [(r["rank"], r["observation_id"], r["risk_score"], r["review_status"],
                                 int(r["automatic_enforcement"])) for r in queue])
        connection.execute("INSERT INTO policy VALUES (?,?,?,?)",
                           (int(policy["enabled"]), policy["threshold"], policy["available_at"], capacity))
        connection.execute("INSERT INTO eval_cutoff VALUES (?)", (EVALUATION_AT,))


def validate_warehouse(path: Path, evaluation: dict) -> dict:
    gates = {}
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        def gate(name, query):
            count = connection.execute(query).fetchone()[0]
            gates[name] = {"violations": count, "status": "PASS" if count == 0 else "FAIL"}
        gate("foreign_keys", "SELECT COUNT(*) FROM pragma_foreign_key_check")
        gate("complete_contexts", "SELECT COUNT(*) FROM (SELECT b.observation_id FROM observation_base b LEFT JOIN captures c USING(observation_id) GROUP BY b.observation_id HAVING COUNT(c.context)<>3)")
        gate("derived_inventory", "SELECT ABS((SELECT COUNT(*) FROM observation_base)-(SELECT COUNT(*) FROM independently_derived_scores))")
        gate("score_inventory", "SELECT ABS((SELECT COUNT(*) FROM observation_base)-(SELECT COUNT(*) FROM reported_scores))")
        gate("score_values", "SELECT COUNT(*) FROM independently_derived_scores s JOIN reported_scores r USING(observation_id) WHERE s.risk_score<>r.risk_score")
        for name in WEIGHTS:
            gate("signal_" + name, f"SELECT COUNT(*) FROM independently_derived_signals s JOIN reported_scores r USING(observation_id) WHERE s.{name}<>json_extract(r.signals,'$.{name}') OR json_extract(r.signals,'$.{name}') IS NULL")
        gate("review_flags", "SELECT COUNT(*) FROM independently_derived_flags s JOIN reported_scores r USING(observation_id) WHERE s.review_flag<>r.review_flag")
        gate("content_change_baseline", "SELECT COUNT(*) FROM independently_derived_signals s JOIN reported_scores r USING(observation_id) WHERE s.content_change_baseline<>r.content_change_baseline")
        gate("policy_availability", "SELECT COUNT(*) FROM observation_base b CROSS JOIN policy p WHERE b.split='holdout' AND b.decision_at<p.available_at")
        gate("validation_label_availability", "SELECT COUNT(*) FROM observation_base b JOIN labels l USING(observation_id) CROSS JOIN policy p WHERE b.split='validation' AND l.available_at>=p.available_at")
        gate("campaign_split_separation", "SELECT COUNT(*) FROM (SELECT campaign_id FROM observation_base GROUP BY campaign_id HAVING COUNT(DISTINCT split)>1)")
        gate("domain_split_separation", "SELECT COUNT(*) FROM (SELECT final_host FROM captures JOIN observation_base USING(observation_id) GROUP BY final_host HAVING COUNT(DISTINCT split)>1)")
        gate("queue_capacity", "SELECT CASE WHEN (SELECT COUNT(*) FROM reported_queue)>(SELECT capacity FROM policy) THEN 1 ELSE 0 END")
        gate("review_only_status", "SELECT COUNT(*) FROM reported_queue WHERE status<>'PENDING_REVIEW' OR automatic_enforcement<>0")
        gate("queue_missing_or_modified", "SELECT COUNT(*) FROM (SELECT rank,observation_id,risk_score FROM independently_derived_queue EXCEPT SELECT rank,observation_id,risk_score FROM reported_queue)")
        gate("queue_extra_or_modified", "SELECT COUNT(*) FROM (SELECT rank,observation_id,risk_score FROM reported_queue EXCEPT SELECT rank,observation_id,risk_score FROM independently_derived_queue)")
        confusion = dict(connection.execute("SELECT * FROM independent_confusion").fetchone())
        for name, value in confusion.items():
            gates["metric_" + name] = {"violations": int(value != evaluation["policy"][name]),
                                      "status": "PASS" if value == evaluation["policy"][name] else "FAIL"}
        pending = connection.execute("SELECT COUNT(*) FROM observation_base b JOIN labels l USING(observation_id) CROSS JOIN eval_cutoff e WHERE b.split='holdout' AND b.decision_at<=e.evaluation_at AND l.available_at>e.evaluation_at").fetchone()[0]
        gates["pending_label_count"] = {"violations": int(pending != evaluation["pending_label_count"]),
                                        "status": "PASS" if pending == evaluation["pending_label_count"] else "FAIL"}
        follow_up = evaluation["label_maturity_follow_up"]
        query = """SELECT COUNT(*) AS n,
            SUM(CASE WHEN l.is_abuse=1 AND f.review_flag=1 THEN 1 ELSE 0 END) AS true_positive,
            SUM(CASE WHEN l.is_abuse=0 AND f.review_flag=1 THEN 1 ELSE 0 END) AS false_positive,
            SUM(CASE WHEN l.is_abuse=0 AND f.review_flag=0 THEN 1 ELSE 0 END) AS true_negative,
            SUM(CASE WHEN l.is_abuse=1 AND f.review_flag=0 THEN 1 ELSE 0 END) AS false_negative
            FROM independently_derived_flags f JOIN labels l USING(observation_id)
            WHERE f.split='holdout' AND f.decision_at<=? AND l.available_at<=?"""
        for name, value in dict(connection.execute(query, (follow_up["evaluation_at"], follow_up["evaluation_at"])).fetchone()).items():
            gates["follow_up_metric_" + name] = {"violations": int(value != follow_up["policy"][name]),
                                                "status": "PASS" if value == follow_up["policy"][name] else "FAIL"}
    failed = [name for name, value in gates.items() if value["status"] != "PASS"]
    if failed:
        raise ValueError("independent SQL reconciliation failed: " + ", ".join(failed))
    return {"status": "PASS", "independent_sql_gates": len(gates), "checks": gates,
            "reconstruction_scope": "Signals, scores, flags, complete queue and matured-label confusion from raw-capture primitives."}


def compare_warehouses(actual: Path, expected: Path) -> None:
    with sqlite3.connect(f"file:{actual}?mode=ro", uri=True) as left, sqlite3.connect(f"file:{expected}?mode=ro", uri=True) as right:
        schema_query = "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
        if left.execute(schema_query).fetchall() != right.execute(schema_query).fetchall():
            raise ValueError("warehouse schema replay mismatch")
        tables = [row[0] for row in right.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            # Table names come exclusively from our reconstructed, fixed schema.
            width = len(right.execute(f"PRAGMA table_info({table})").fetchall())
            query = f"SELECT * FROM {table} ORDER BY " + ",".join(str(i + 1) for i in range(width))
            if left.execute(query).fetchall() != right.execute(query).fetchall():
                raise ValueError("warehouse raw-input replay mismatch: " + table)
