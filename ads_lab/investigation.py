from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from itertools import combinations

from .contracts import POLICY_URL, digest, json_bytes
from .detection import apply_policy, score_record


def campaign_links(scored: list[dict]) -> list[dict]:
    indexes = defaultdict(set)
    for row in scored:
        for page in row["pages"].values():
            indexes[(row["split"], "SHARED_FINAL_URL", page["final_url"])].add(row["campaign_id"])
            indexes[(row["split"], "SHARED_DOM_SKELETON", page["template_sha256"])].add(row["campaign_id"])
            for url in page["form_actions"]:
                indexes[(row["split"], "SHARED_FORM_ENDPOINT", url)].add(row["campaign_id"])
            for url in page["static_js_redirect_references"]:
                indexes[(row["split"], "SHARED_STATIC_REDIRECT_REFERENCE", url)].add(row["campaign_id"])
    links = []
    for (split, reason, value), campaigns in sorted(indexes.items()):
        for left, right in combinations(sorted(campaigns), 2):
            links.append({"split": split, "left_campaign": left, "right_campaign": right,
                          "link_reason": reason, "evidence_value": value,
                          "strength": "WEAK_TEMPLATE_ASSOCIATION" if reason == "SHARED_DOM_SKELETON" else "RESOURCE_ASSOCIATION",
                          "actor_identity_established": False, "review_only": True})
    return links


def build_queue(scored: list[dict], capacity: int) -> list[dict]:
    if type(capacity) is not int or capacity < 0:
        raise ValueError("capacity must be a non-negative integer")
    candidates = sorted((r for r in scored if r["split"] == "holdout" and r["review_flag"]),
                        key=lambda r: (-r["risk_score"], r["observation_id"]))
    queue = []
    for rank, row in enumerate(candidates[:capacity], start=1):
        queue.append({"rank": rank, "observation_id": row["observation_id"],
                      "campaign_id": row["campaign_id"], "decision_at": row["decision_at"],
                      "risk_score": row["risk_score"], "reason_codes": row["reason_codes"],
                      "evidence_sha256": digest(json_bytes(row["pages"])),
                      "review_status": "PENDING_REVIEW", "recommended_action": "VERIFY_EVIDENCE",
                      "actor_attribution": "UNRESOLVED", "automatic_enforcement": False})
    return queue


def case_reports(scored: list[dict], queue: list[dict], links: list[dict]) -> str:
    by_id = {r["observation_id"]: r for r in scored}
    lines = ["# Controlled ad-destination investigation cases", "",
             "All cases use fabricated ads and destinations. Queue entry requests verification; it is not a finding of wrongdoing.",
             "", "Policy reference: " + POLICY_URL, ""]
    for item in queue:
        row = by_id[item["observation_id"]]
        lines += ["## " + item["observation_id"], "",
                  f"Decision: {item['decision_at']} | Score: {item['risk_score']} | Status: PENDING_REVIEW", "",
                  "Evidence reasons: " + ", ".join(item["reason_codes"]), "",
                  "| Context | Final destination | Topic tags | Body SHA-256 |",
                  "|---|---|---|---|"]
        for context, page in sorted(row["pages"].items()):
            lines.append(f"| {context} | {page['final_url']} | {', '.join(page['topic_tags']) or 'UNRESOLVED'} | {page['body_sha256']} |")
        relevant_links = [link for link in links if link["split"] == "holdout" and
                          item["campaign_id"] in {link["left_campaign"], link["right_campaign"]}]
        lines += ["", "Current threat lookup: " + row["threat_lookup"]["status"],
                  f"Campaign associations: {len(relevant_links)}; shared templates alone do not establish a common actor.", "",
                  "Alternative explanations: legitimate localization, A/B testing, consent interstitials, SSO, tracking or a compromised destination.",
                  "Next verification: repeat comparable captures, inspect the recorded HTTP/HTML evidence, confirm the advertised product and the indicator's time/source.",
                  "Static JavaScript references are not executed redirect traces. Attribution and policy violation remain unresolved.", ""]
    return "\n".join(lines) + "\n"


def incident_replay(records: list[dict], scored: list[dict], threat_snapshot: dict, policy: dict) -> dict:
    candidate = next(r for r in scored if r["split"] == "holdout" and r["signals"]["topic_divergence"])
    original = next(r for r in records if r["observation_id"] == candidate["observation_id"])
    patched = deepcopy(original)
    reviewer_body = next(s["hops"][-1]["body"] for s in patched["snapshots"] if s["context"] == "reviewer")
    for snapshot in patched["snapshots"]:
        snapshot["hops"][-1]["body"] = reviewer_body
        snapshot["hops"][-1]["body_sha256"] = digest(reviewer_body)
    after = apply_policy([score_record(patched, threat_snapshot)], policy)[0]
    return {"source": "CONTROLLED_COUNTERFACTUAL_REPLAY", "real_incident": False,
            "observation_id": original["observation_id"], "decision_at": original["decision_at"],
            "timeline": [{"stage": "CONTEXT_CAPTURES", "evidence": "corpus.json"},
                         {"stage": "DETECTION", "evidence": "observations.json"},
                         {"stage": "HUMAN_VERIFICATION_REQUIRED", "evidence": "case_reports.md"},
                         {"stage": "SIMULATED_CONTENT_REPAIR", "evidence": "patched_record"}],
            "root_cause_hypothesis": "Context-dependent delivery changes the advertised product topic.",
            "simulated_mitigation": "Serve the same advertised product in all controlled contexts.",
            "before_score": candidate["risk_score"], "after_score": after["risk_score"],
            "before_review_flag": candidate["review_flag"], "after_review_flag": after["review_flag"],
            "patched_record": patched, "patched_evidence_sha256": digest(json_bytes(patched)),
            "automatic_enforcement": False}
