from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capture import capture_demo
from .contracts import read_json, write_json
from .feeds import import_feed
from .inspection import inspect_captures, verify_inspection
from .pipeline import run, verify


def main():
    parser = argparse.ArgumentParser(description="Controlled Ads destination investigation lab")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="Build, evaluate and replay the controlled benchmark")
    run_parser.add_argument("--output", type=Path, default=Path("outputs/ads_lab"))
    run_parser.add_argument("--replicas", type=int, default=4)
    run_parser.add_argument("--capacity", type=int, default=12)
    verify_parser = commands.add_parser("verify", help="Verify artifact hashes and reconstruct all decisions")
    verify_parser.add_argument("--output", type=Path, default=Path("outputs/ads_lab"))
    capture_parser = commands.add_parser("capture-demo", help="Capture five cases from a temporary owned HTTP server")
    capture_parser.add_argument("--output", type=Path, default=Path("outputs/ads_capture.json"))
    feed_parser = commands.add_parser("import-feed", help="Import locally downloaded public indicator metadata")
    feed_parser.add_argument("--format", choices=("phishtank", "urlhaus"), required=True)
    feed_parser.add_argument("--input", type=Path, required=True)
    feed_parser.add_argument("--retrieved-at", required=True)
    feed_parser.add_argument("--ttl-hours", type=int, default=24)
    feed_parser.add_argument("--output", type=Path, required=True)
    inspect_parser = commands.add_parser("inspect", help="Score owned captures against a dated indicator snapshot")
    inspect_parser.add_argument("--capture", type=Path, required=True)
    inspect_parser.add_argument("--threat-snapshot", type=Path, default=Path("outputs/ads_lab/threat_snapshot.json"))
    inspect_parser.add_argument("--policy", type=Path, default=Path("outputs/ads_lab/policy.json"))
    inspect_parser.add_argument("--capacity", type=int, default=12)
    inspect_parser.add_argument("--output", type=Path, default=Path("outputs/ads_inspection.json"))
    replay_parser = commands.add_parser("verify-inspection", help="Reconstruct a saved controlled-capture inspection")
    replay_parser.add_argument("--input", type=Path, default=Path("outputs/ads_inspection.json"))
    args = parser.parse_args()
    if args.command == "run":
        result = run(args.output, args.replicas, args.capacity)
        summary = {"status": result["status"], "observations": result["manifest"]["observations"],
                   "policy_threshold": result["policy_threshold"], "sql_gates": result["sql_checks"]["independent_sql_gates"],
                   "evaluation": result["evaluation"]}
    elif args.command == "verify":
        summary = verify(args.output)
    elif args.command == "capture-demo":
        data = capture_demo()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, data)
        summary = {"status": "PASS", "owned_http_observations": len(data["observations"]),
                   "javascript_executed": False}
    elif args.command == "import-feed":
        data = import_feed(args.input, args.format, args.retrieved_at, args.ttl_hours)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, data)
        summary = {"status": "PASS", "source": data["source"], "indicators": len(data["indicators"]),
                   "snapshot_sha256": data["input_sha256"]}
    elif args.command == "inspect":
        data = inspect_captures(read_json(args.capture), read_json(args.threat_snapshot), read_json(args.policy), args.capacity)
        verify_inspection(data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, data)
        summary = {"status": "PASS", "observations": len(data["scored_observations"]),
                   "queued": len(data["investigation_queue"]), "ground_truth_metrics": "NOT_AVAILABLE"}
    else:
        summary = verify_inspection(read_json(args.input))
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
