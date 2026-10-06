from __future__ import annotations

from copy import deepcopy

from .contracts import digest, json_bytes, validate_corpus
from .detection import apply_policy, score_record
from .feeds import validate_threat_snapshot
from .investigation import build_queue, campaign_links, case_reports
from .pipeline import source_hashes


def inspect_captures(capture_package: dict, threat_snapshot: dict, policy: dict, capacity=12) -> dict:
    if set(capture_package) != {"source", "synthetic_content", "javascript_executed", "observations"}:
        raise ValueError("capture package schema mismatch")
    if capture_package["source"] != "OWNED_LOOPBACK_HTTP_SERVER" or capture_package["synthetic_content"] is not True:
        raise ValueError("this entry point accepts owned controlled captures")
    if capture_package["javascript_executed"] is not False:
        raise ValueError("unsupported browser execution claim")
    records = capture_package["observations"]
    validate_corpus(records, benchmark=False)
    validate_threat_snapshot(threat_snapshot)
    scored = apply_policy([score_record(record, threat_snapshot) for record in records], policy)
    links = campaign_links(scored)
    queue = build_queue(scored, capacity)
    return {"module": "ADS_CONTROLLED_CAPTURE_INSPECTION", "schema_version": 1,
            "source_sha256": source_hashes(), "capacity": capacity,
            "input_sha256": {"capture": digest(json_bytes(capture_package)),
                             "threat_snapshot": digest(json_bytes(threat_snapshot)), "policy": digest(json_bytes(policy))},
            "inputs": {"capture": deepcopy(capture_package), "threat_snapshot": deepcopy(threat_snapshot),
                       "policy": deepcopy(policy)}, "scored_observations": scored,
            "campaign_links": links, "investigation_queue": queue,
            "case_reports_markdown": case_reports(scored, queue, links),
            "no_ground_truth_metrics": True, "real_google_ads_data": False,
            "automatic_enforcement": False}


def verify_inspection(package: dict) -> dict:
    inputs = package["inputs"]
    expected = inspect_captures(inputs["capture"], inputs["threat_snapshot"], inputs["policy"], package["capacity"])
    if package != expected:
        raise ValueError("controlled capture inspection replay mismatch")
    return {"status": "PASS", "raw_capture_replay": "PASS", "ground_truth_metrics": "NOT_AVAILABLE"}
