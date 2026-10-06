from __future__ import annotations

import fcntl
import os
import platform
import shutil
import sqlite3
import tempfile
from pathlib import Path

from .contracts import REQUIRED_OUTPUTS, digest, read_json, validate_corpus, validate_labels, write_json
from .detection import apply_policy, choose_policy, score_record
from .evaluation import evaluate
from .feeds import validate_threat_snapshot
from .fixtures import SCENARIOS, generate_corpus
from .investigation import build_queue, campaign_links, case_reports, incident_replay
from .reporting import build_report
from .warehouse import build_warehouse, compare_warehouses, validate_warehouse

ROOT = Path(__file__).resolve().parents[1]


def source_hashes() -> dict[str, str]:
    paths = sorted((ROOT / "ads_lab").glob("*.py")) + [ROOT / "sql/ads_abuse_validation.sql"]
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}


def _build(directory: Path, replicas: int, capacity: int) -> dict:
    records, labels, threats = generate_corpus(replicas)
    validate_corpus(records)
    label_map = validate_labels(labels, records)
    validate_threat_snapshot(threats)
    scored = [score_record(record, threats) for record in records]
    policy = choose_policy(scored, label_map)
    apply_policy(scored, policy)
    links = campaign_links(scored)
    queue = build_queue(scored, capacity)
    evaluation = evaluate(scored, label_map, queue, capacity)
    replay = incident_replay(records, scored, threats, policy)
    build_warehouse(directory / "warehouse.sqlite", records, labels, threats, scored, queue, policy, capacity)
    sql_checks = validate_warehouse(directory / "warehouse.sqlite", evaluation)
    outputs = {"corpus.json": records, "labels.json": labels, "threat_snapshot.json": threats,
               "policy.json": policy, "observations.json": scored, "campaign_links.json": links,
               "investigation_queue.json": queue, "evaluation.json": evaluation,
               "incident_replay.json": replay, "sql_checks.json": sql_checks}
    for name, value in outputs.items():
        write_json(directory / name, value)
    (directory / "case_reports.md").write_text(case_reports(scored, queue, links), encoding="utf-8")
    (directory / "report.html").write_text(build_report(evaluation, queue, sql_checks, policy), encoding="utf-8")
    manifest = {"module": "ADS_DESTINATION_INVESTIGATION_LAB", "schema_version": 1,
                "controlled_fixtures_only": True, "real_google_ads_data": False,
                "javascript_executed": False, "automatic_enforcement": False,
                "replicas": replicas, "queue_capacity": capacity, "observations": len(records),
                "scenario_designs": len(SCENARIOS), "replicas_are_not_independent_threat_scenarios": True,
                "capture_contexts": len(records) * 3, "python_version": platform.python_version(),
                "sqlite_version": sqlite3.sqlite_version, "source_sha256": source_hashes()}
    write_json(directory / "manifest.json", manifest)
    receipt = {"module": manifest["module"], "status": "PASS", "replay_required": True,
               "artifact_sha256": {name: digest((directory / name).read_bytes()) for name in sorted(REQUIRED_OUTPUTS)}}
    write_json(directory / "run_receipt.json", receipt)
    verify(directory)
    return {"manifest": manifest, "evaluation": evaluation, "sql_checks": sql_checks,
            "policy_threshold": policy["threshold"], "status": "PASS"}


def verify(directory: Path) -> dict:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("run directory must be a regular directory")
    receipt_path = directory / "run_receipt.json"
    if receipt_path.is_symlink():
        raise ValueError("receipt cannot be a symlink")
    receipt = read_json(receipt_path)
    if receipt.get("module") != "ADS_DESTINATION_INVESTIGATION_LAB" or receipt.get("status") != "PASS":
        raise ValueError("invalid lab success receipt")
    if set(receipt.get("artifact_sha256", {})) != REQUIRED_OUTPUTS:
        raise ValueError("artifact inventory mismatch")
    if {p.name for p in directory.iterdir()} != REQUIRED_OUTPUTS | {"run_receipt.json"}:
        raise ValueError("unexpected artifact in run directory")
    for name, expected in receipt["artifact_sha256"].items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError("artifact hash mismatch: " + name)
    manifest = read_json(directory / "manifest.json")
    if manifest["source_sha256"] != source_hashes():
        raise ValueError("source hash mismatch; rebuild with the current source")
    records, labels, threats = (read_json(directory / name) for name in ("corpus.json", "labels.json", "threat_snapshot.json"))
    validate_corpus(records)
    label_map = validate_labels(labels, records)
    validate_threat_snapshot(threats)
    scored = [score_record(record, threats) for record in records]
    policy = choose_policy(scored, label_map)
    apply_policy(scored, policy)
    links = campaign_links(scored)
    queue = build_queue(scored, manifest["queue_capacity"])
    evaluation = evaluate(scored, label_map, queue, manifest["queue_capacity"])
    replay = incident_replay(records, scored, threats, policy)
    reconstructed = {"policy.json": policy, "observations.json": scored, "campaign_links.json": links,
                     "investigation_queue.json": queue, "evaluation.json": evaluation, "incident_replay.json": replay}
    for name, expected in reconstructed.items():
        if read_json(directory / name) != expected:
            raise ValueError("raw-evidence replay mismatch: " + name)
    checks = validate_warehouse(directory / "warehouse.sqlite", evaluation)
    with tempfile.TemporaryDirectory(prefix="ads-replay-") as temporary:
        rebuilt = Path(temporary) / "reconstructed.sqlite"
        build_warehouse(rebuilt, records, labels, threats, scored, queue, policy, manifest["queue_capacity"])
        compare_warehouses(directory / "warehouse.sqlite", rebuilt)
    if checks != read_json(directory / "sql_checks.json"):
        raise ValueError("SQL replay mismatch")
    if (directory / "case_reports.md").read_text(encoding="utf-8") != case_reports(scored, queue, links):
        raise ValueError("case report replay mismatch")
    if (directory / "report.html").read_text(encoding="utf-8") != build_report(evaluation, queue, checks, policy):
        raise ValueError("HTML report replay mismatch")
    return {"status": "PASS", "artifacts_verified": len(REQUIRED_OUTPUTS), "raw_evidence_replay": "PASS",
            "independent_sql_gates": checks["independent_sql_gates"]}


def run(output: Path, replicas=4, capacity=12) -> dict:
    output = Path(output)
    if output.is_symlink():
        raise ValueError("output directory cannot be a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / ("." + output.name + ".lock")
    if lock_path.is_symlink():
        raise ValueError("writer lock cannot be a symlink")
    with lock_path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another Ads lab run is writing this output") from exc
        if output.exists() and (not output.is_dir() or not (output / "run_receipt.json").is_file()):
            raise ValueError("refusing to replace a directory without a lab receipt")
        if output.exists() and read_json(output / "run_receipt.json").get("module") != "ADS_DESTINATION_INVESTIGATION_LAB":
            raise ValueError("output belongs to another workflow")
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-stage-", dir=output.parent))
        backup = None
        try:
            result = _build(staging, replicas, capacity)
            if output.exists():
                backup = Path(tempfile.mkdtemp(prefix="." + output.name + "-previous-", dir=output.parent))
                backup.rmdir()
                os.replace(output, backup)
            try:
                os.replace(staging, output)
            except BaseException:
                if backup is not None:
                    os.replace(backup, output)
                    backup = None
                raise
            if backup is not None:
                shutil.rmtree(backup)
            return result
        finally:
            if staging.exists():
                shutil.rmtree(staging)
