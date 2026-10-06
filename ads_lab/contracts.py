from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CONTEXTS = ("reviewer", "desktop", "mobile")
MAX_BODY_BYTES = 128 * 1024
MAX_HOPS = 6
MAX_CAPTURE_SECONDS = 300
POLICY_URL = "https://support.google.com/adspolicy/answer/15938075?hl=en"
POLICY_AVAILABLE_AT = "2026-01-31T00:00:00Z"
EVALUATION_AT = "2026-02-20T00:00:00Z"
FOLLOW_UP_AT = "2026-02-26T00:00:00Z"
REQUIRED_OUTPUTS = {
    "corpus.json", "labels.json", "threat_snapshot.json", "policy.json",
    "observations.json", "campaign_links.json", "investigation_queue.json",
    "case_reports.md", "evaluation.json", "incident_replay.json",
    "warehouse.sqlite", "sql_checks.json", "report.html", "manifest.json",
}


def timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise ValueError("timestamps must be UTC whole-second YYYY-MM-DDTHH:MM:SSZ")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise ValueError("timestamp must use UTC")
    return parsed


def utc_string(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timezone is required")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 for c in value):
        raise ValueError("invalid URL")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("URL requires HTTP(S), a host and no credentials")
    try:
        port = parts.port
        host = parts.hostname.encode("idna").decode("ascii").lower()
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid host or port") from exc
    if ":" in host:
        host = "[" + host + "]"
    default_port = 80 if parts.scheme == "http" else 443
    netloc = host if port in {None, default_port} else f"{host}:{port}"
    # Keep path case, escapes, query values and ordering; remove only the fragment.
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


def host_of(value: str) -> str:
    return urlsplit(canonical_url(value)).hostname


def digest(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.write_bytes(json_bytes(value))


def read_json(path: Path):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON value: {value}")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant,
                      object_pairs_hook=unique_pairs)


def finite_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def validate_corpus(records: list[dict], *, benchmark=True) -> None:
    if not isinstance(records, list) or not records:
        raise ValueError("non-empty corpus required")
    ids = set()
    expected_fields = {"observation_id", "campaign_id", "split", "decision_at", "ad_claim", "ad_url", "snapshots"}
    for record in records:
        if set(record) != expected_fields:
            raise ValueError("corpus fields must be label-free and match the contract")
        key = record["observation_id"]
        if not isinstance(key, str) or not key or key in ids:
            raise ValueError("invalid or duplicate observation ID")
        ids.add(key)
        if not isinstance(record["campaign_id"], str) or not record["campaign_id"]:
            raise ValueError("campaign ID required")
        if record["split"] not in {"validation", "holdout"}:
            raise ValueError("unknown evaluation split")
        if not isinstance(record["ad_claim"], str) or not record["ad_claim"].strip():
            raise ValueError("ad claim required")
        canonical_url(record["ad_url"])
        decision = timestamp(record["decision_at"])
        snapshots = record["snapshots"]
        if not isinstance(snapshots, list) or sorted(s["context"] for s in snapshots) != sorted(CONTEXTS):
            raise ValueError("exactly one capture per required context is required")
        capture_times = []
        for snapshot in snapshots:
            if set(snapshot) != {"context", "captured_at", "request_url", "final_url", "hops"}:
                raise ValueError("snapshot schema mismatch")
            captured = timestamp(snapshot["captured_at"])
            capture_times.append(captured)
            if captured > decision:
                raise ValueError("capture unavailable at decision")
            if canonical_url(snapshot["request_url"]) != canonical_url(record["ad_url"]):
                raise ValueError("all contexts must start at the same ad URL")
            hops = snapshot["hops"]
            if not isinstance(hops, list) or not 1 <= len(hops) <= MAX_HOPS:
                raise ValueError("invalid redirect chain length")
            if canonical_url(hops[0]["url"]) != canonical_url(snapshot["request_url"]):
                raise ValueError("chain does not start at the requested URL")
            seen_urls = set()
            for index, hop in enumerate(hops):
                if set(hop) != {"url", "status", "location", "body", "body_sha256"}:
                    raise ValueError("hop schema mismatch")
                url = canonical_url(hop["url"])
                if url in seen_urls:
                    raise ValueError("redirect loop in captured evidence")
                seen_urls.add(url)
                body = hop["body"]
                if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_BODY_BYTES:
                    raise ValueError("body exceeds capture limit")
                if digest(body) != hop["body_sha256"]:
                    raise ValueError("capture body hash mismatch")
                if index < len(hops) - 1:
                    if hop["status"] not in {301, 302, 303, 307, 308}:
                        raise ValueError("intermediate hop is not an HTTP redirect")
                    if canonical_url(hop["location"]) != canonical_url(hops[index + 1]["url"]):
                        raise ValueError("redirect chain is discontinuous")
                elif hop["status"] != 200 or hop["location"] is not None:
                    raise ValueError("terminal response must be a successful HTML capture")
            if canonical_url(snapshot["final_url"]) != canonical_url(hops[-1]["url"]):
                raise ValueError("final URL does not match the capture chain")
        if (max(capture_times) - min(capture_times)).total_seconds() > MAX_CAPTURE_SECONDS:
            raise ValueError("context captures exceed the comparison window")
        if (decision - min(capture_times)).total_seconds() > MAX_CAPTURE_SECONDS:
            raise ValueError("evidence is too old for this decision")
    validation = [r for r in records if r["split"] == "validation"]
    holdout = [r for r in records if r["split"] == "holdout"]
    if not benchmark:
        if validation:
            raise ValueError("inspection inputs must contain holdout decisions only")
        return
    if not validation or not holdout:
        raise ValueError("both validation and holdout records required")
    if max(timestamp(r["decision_at"]) for r in validation) >= timestamp(POLICY_AVAILABLE_AT):
        raise ValueError("validation observations must precede policy availability")
    if min(timestamp(r["decision_at"]) for r in holdout) < timestamp(POLICY_AVAILABLE_AT):
        raise ValueError("policy unavailable for a held-out decision")
    if {r["campaign_id"] for r in validation} & {r["campaign_id"] for r in holdout}:
        raise ValueError("campaign leakage across splits")
    def domains(rows):
        return {host_of(s["final_url"]) for r in rows for s in r["snapshots"]}
    if domains(validation) & domains(holdout):
        raise ValueError("destination domain leakage across splits")


def validate_labels(labels: list[dict], records: list[dict]) -> dict[str, dict]:
    expected = {r["observation_id"] for r in records}
    result = {}
    for label in labels:
        if set(label) != {"observation_id", "is_abuse", "available_at", "scenario", "label_source"}:
            raise ValueError("label schema mismatch")
        key = label["observation_id"]
        if key in result or key not in expected or type(label["is_abuse"]) is not bool:
            raise ValueError("invalid, duplicate or unaligned label")
        timestamp(label["available_at"])
        if label["label_source"] != "CONTROLLED_FIXTURE_GROUND_TRUTH":
            raise ValueError("this benchmark requires controlled ground truth")
        result[key] = label
    if set(result) != expected:
        raise ValueError("labels must cover the complete corpus")
    return result
