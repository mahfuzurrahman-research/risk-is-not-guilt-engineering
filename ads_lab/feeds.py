from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import canonical_url, digest, json_bytes, read_json, timestamp, utc_string

SOURCES = {"CONTROLLED_THREAT_FIXTURE", "PHISHTANK_PUBLIC_METADATA", "URLHAUS_PUBLIC_METADATA"}


def validate_threat_snapshot(snapshot: dict) -> None:
    if set(snapshot) != {"schema_version", "source", "input_sha256", "retrieved_at", "synthetic", "indicators"}:
        raise ValueError("threat snapshot schema mismatch")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1 or snapshot["source"] not in SOURCES:
        raise ValueError("unsupported threat source")
    if type(snapshot["synthetic"]) is not bool or snapshot["synthetic"] != (snapshot["source"] == "CONTROLLED_THREAT_FIXTURE"):
        raise ValueError("source and synthetic declaration disagree")
    timestamp(snapshot["retrieved_at"])
    if not isinstance(snapshot["input_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot["input_sha256"]):
        raise ValueError("threat input hash required")
    if not isinstance(snapshot["indicators"], list):
        raise ValueError("indicator list required")
    if snapshot["synthetic"] and snapshot["input_sha256"] != digest(json_bytes(snapshot["indicators"])):
        raise ValueError("controlled indicator input hash mismatch")
    seen = set()
    for row in snapshot["indicators"]:
        if set(row) != {"url", "threat_type", "source_recorded_at", "available_at", "expires_at"}:
            raise ValueError("indicator schema mismatch")
        url = canonical_url(row["url"])
        if url != row["url"] or url in seen:
            raise ValueError("non-canonical or duplicate threat URL")
        seen.add(url)
        if row["threat_type"] not in {"PHISHING", "MALWARE_URL"}:
            raise ValueError("unknown threat type")
        verified, available, expires = (timestamp(row[key]) for key in ("source_recorded_at", "available_at", "expires_at"))
        if available < verified or expires <= available:
            raise ValueError("invalid threat availability or expiry")
        if available < timestamp(snapshot["retrieved_at"]):
            raise ValueError("imported indicator cannot predate local retrieval")


def lookup_urls(urls: list[str], decision_at: str, snapshot: dict) -> dict:
    decision = timestamp(decision_at)
    by_url = {r["url"]: r for r in snapshot["indicators"]}
    matches, excluded = [], []
    for url in sorted(set(urls)):
        row = by_url.get(canonical_url(url))
        if row is None:
            continue
        if timestamp(row["available_at"]) > decision:
            excluded.append({"url": url, "reason": "NOT_YET_AVAILABLE"})
        elif timestamp(row["expires_at"]) <= decision:
            excluded.append({"url": url, "reason": "EXPIRED_INDICATOR"})
        else:
            matches.append({"url": url, "threat_type": row["threat_type"],
                            "available_at": row["available_at"], "source": snapshot["source"]})
    return {"status": "KNOWN_THREAT_INDICATOR" if matches else "UNKNOWN_NO_CURRENT_MATCH",
            "matches": matches, "excluded": excluded}


def _source_time(value: str, allow_naive: bool = False) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid source timestamp") from exc
    if parsed.tzinfo is None:
        if not allow_naive:
            raise ValueError("source timestamp requires timezone")
        parsed = parsed.replace(tzinfo=timezone.utc)  # URLhaus dateadded is documented UTC.
    return parsed.astimezone(timezone.utc)


def import_feed(path: Path, feed_format: str, retrieved_at: str, ttl_hours: int = 24) -> dict:
    retrieved = timestamp(retrieved_at)
    if type(ttl_hours) is not int or not 1 <= ttl_hours <= 168:
        raise ValueError("TTL must be between one hour and one week")
    raw = Path(path).read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("feed exceeds import size limit")
    rows = []
    if feed_format == "phishtank":
        entries = read_json(path)
        if not isinstance(entries, list):
            raise ValueError("PhishTank JSON must be a list")
        for item in entries:
            if item.get("verified") not in {True, "yes"} or item.get("online") not in {True, "yes"}:
                continue
            rows.append((item["url"], "PHISHING", _source_time(item["verification_time"])))
        source = "PHISHTANK_PUBLIC_METADATA"
    elif feed_format == "urlhaus":
        lines = []
        for line in raw.decode("utf-8-sig").splitlines():
            if line.lstrip().startswith("#"):
                header = line.lstrip()[1:].lstrip()
                if "dateadded" in header and "url_status" in header:
                    lines.append(header)
            elif line.strip():
                lines.append(line)
        reader = csv.DictReader(io.StringIO("\n".join(lines)))
        if not reader.fieldnames or not {"url", "url_status", "dateadded"} <= set(reader.fieldnames) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("URLhaus CSV header is missing or ambiguous")
        for item in reader:
            if item.get("url_status") != "online":
                continue
            rows.append((item["url"], "MALWARE_URL", _source_time(item["dateadded"], allow_naive=True)))
        source = "URLHAUS_PUBLIC_METADATA"
    else:
        raise ValueError("unsupported feed format")
    indicators = {}
    for url, threat_type, verified in rows:
        if verified > retrieved:
            raise ValueError("feed claims a verification after retrieval")
        url = canonical_url(url)
        row = {"url": url, "threat_type": threat_type, "source_recorded_at": utc_string(verified),
               "available_at": retrieved_at, "expires_at": utc_string(retrieved + timedelta(hours=ttl_hours))}
        if url in indicators and indicators[url] != row:
            raise ValueError("conflicting duplicate feed URL")
        indicators[url] = row
    result = {"schema_version": 1, "source": source, "input_sha256": digest(raw),
              "retrieved_at": retrieved_at, "synthetic": False,
              "indicators": [indicators[url] for url in sorted(indicators)]}
    validate_threat_snapshot(result)
    return result
