from __future__ import annotations

from copy import deepcopy

from .contracts import POLICY_AVAILABLE_AT, finite_number, timestamp
from .features import primitive_features
from .feeds import lookup_urls

WEIGHTS = {
    "topic_divergence": 4, "ad_topic_mismatch": 3, "credential_change": 3,
    "download_change": 3, "known_threat": 6, "destination_change": 1,
    "long_redirect": 1, "static_js_external": 1, "external_form": 1,
}


def score_record(record: dict, threat_snapshot: dict) -> dict:
    features = primitive_features(record)
    pages = features["pages"]
    reviewer, users = pages["reviewer"], [pages[c] for c in ("desktop", "mobile")]
    ad_topics = set(features["ad_topics"])
    def disjoint(left, right):
        return bool(left and right and not (set(left) & set(right)))
    lookup = lookup_urls(features["candidate_urls"], record["decision_at"], threat_snapshot)
    signals = {
        "topic_divergence": any(disjoint(reviewer["topic_tags"], p["topic_tags"]) for p in users),
        "ad_topic_mismatch": any(disjoint(ad_topics, p["topic_tags"]) for p in users),
        "credential_change": any(p["password_input"] and p["external_form"] and not reviewer["password_input"] for p in users),
        "download_change": any(p["download_links"] and not reviewer["download_links"] for p in users),
        "known_threat": bool(lookup["matches"]),
        "destination_change": any(p["final_host"] != reviewer["final_host"] for p in users),
        "long_redirect": any(p["hop_count"] > 2 for p in users),
        "static_js_external": any(p["static_js_reference_external"] for p in users),
        "external_form": any(p["external_form"] for p in users),
    }
    signals = {name: bool(value) for name, value in signals.items()}
    features.update({"signals": signals,
                     "risk_score": sum(WEIGHTS[name] for name, present in signals.items() if present),
                     "reason_codes": sorted(name.upper() for name, present in signals.items() if present),
                     "threat_lookup": lookup,
                     "content_change_baseline": any(p["body_sha256"] != reviewer["body_sha256"] or
                                                    p["final_url"] != reviewer["final_url"] for p in users),
                     "content_unresolved": not ad_topics or any(not p["topic_tags"] for p in users),
                     "probability_calibrated": False,
                     "actor_attribution": "UNRESOLVED"})
    return features


def choose_policy(scored: list[dict], labels: dict[str, dict], minimum_precision=0.9) -> dict:
    minimum_precision = finite_number(minimum_precision, "minimum precision")
    if not 0 < minimum_precision <= 1:
        raise ValueError("minimum precision must be in (0, 1]")
    validation = [r for r in scored if r["split"] == "validation"]
    matured = [r for r in validation if timestamp(labels[r["observation_id"]]["available_at"]) < timestamp(POLICY_AVAILABLE_AT)]
    if len(matured) != len(validation):
        raise ValueError("validation labels must be available before policy freeze")
    positives = sum(labels[r["observation_id"]]["is_abuse"] for r in matured)
    if not positives or positives == len(matured):
        raise ValueError("validation requires positive and negative labels")
    candidates = []
    for threshold in sorted({r["risk_score"] for r in matured if r["risk_score"] > 0}):
        selected = [r for r in matured if r["risk_score"] >= threshold]
        tp = sum(labels[r["observation_id"]]["is_abuse"] for r in selected)
        precision = tp / len(selected)
        candidates.append({"threshold": threshold, "precision": precision, "recall": tp / positives,
                           "flagged": len(selected)})
    feasible = [c for c in candidates if c["precision"] >= minimum_precision]
    best = max(feasible, key=lambda c: (c["recall"], c["precision"], -c["threshold"])) if feasible else None
    return {"schema_version": 1, "available_at": POLICY_AVAILABLE_AT,
            "weights": deepcopy(WEIGHTS), "minimum_validation_precision": minimum_precision,
            "enabled": best is not None, "threshold": best["threshold"] if best else None,
            "selection_scope": "MATURE_VALIDATION_LABELS_ONLY", "validation_candidates": candidates,
            "score_meaning": "REVIEW_PRIORITIZATION_HEURISTIC_NOT_FRAUD_PROBABILITY"}


def apply_policy(scored: list[dict], policy: dict) -> list[dict]:
    if policy.get("weights") != WEIGHTS or type(policy.get("enabled")) is not bool:
        raise ValueError("invalid scoring policy")
    if policy["enabled"] and (type(policy.get("threshold")) is not int or policy["threshold"] <= 0):
        raise ValueError("invalid review threshold")
    if policy.get("available_at") != POLICY_AVAILABLE_AT or policy.get("selection_scope") != "MATURE_VALIDATION_LABELS_ONLY":
        raise ValueError("invalid policy availability or selection scope")
    if not policy["enabled"] and policy.get("threshold") is not None:
        raise ValueError("disabled policy cannot have a threshold")
    for row in scored:
        if row["split"] == "holdout" and timestamp(row["decision_at"]) < timestamp(policy["available_at"]):
            raise ValueError("review policy unavailable at decision")
        row["review_flag"] = bool(policy["enabled"] and row["risk_score"] >= policy["threshold"])
        row["decision_status"] = "REVIEW_CANDIDATE" if row["review_flag"] else "INSUFFICIENT_EVIDENCE_FOR_FLAG"
        row["automatic_enforcement"] = False
    return scored
