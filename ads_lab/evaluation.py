from __future__ import annotations

from .contracts import EVALUATION_AT, FOLLOW_UP_AT, timestamp


def _metrics(rows: list[dict], labels: dict[str, dict], flag) -> dict:
    tp = fp = tn = fn = 0
    for row in rows:
        actual = labels[row["observation_id"]]["is_abuse"]
        predicted = bool(flag(row))
        tp += int(actual and predicted)
        fp += int(not actual and predicted)
        tn += int(not actual and not predicted)
        fn += int(actual and not predicted)
    return {"n": len(rows), "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_positive_rate": fp / (fp + tn) if fp + tn else None}


def evaluate(scored: list[dict], labels: dict[str, dict], queue: list[dict], capacity: int,
             evaluation_at=EVALUATION_AT) -> dict:
    at = timestamp(evaluation_at)
    holdout = [r for r in scored if r["split"] == "holdout" and timestamp(r["decision_at"]) <= at]
    mature = [r for r in holdout if timestamp(labels[r["observation_id"]]["available_at"]) <= at]
    pending = [r["observation_id"] for r in holdout if timestamp(labels[r["observation_id"]]["available_at"]) > at]
    queue_ids = {r["observation_id"] for r in queue}
    matured_ids = {r["observation_id"] for r in mature}
    adjudicated_queue = [key for key in queue_ids if key in matured_ids]
    tp = sum(labels[key]["is_abuse"] for key in adjudicated_queue)
    groups = {}
    for scenario in sorted({labels[r["observation_id"]]["scenario"] for r in mature}):
        rows = [r for r in mature if labels[r["observation_id"]]["scenario"] == scenario]
        groups[scenario] = _metrics(rows, labels, lambda r: r["review_flag"])
    follow_up_at = max(evaluation_at, FOLLOW_UP_AT)
    follow_up = [r for r in scored if r["split"] == "holdout" and timestamp(r["decision_at"]) <= timestamp(follow_up_at)]
    follow_up_mature = [r for r in follow_up if timestamp(labels[r["observation_id"]]["available_at"]) <= timestamp(follow_up_at)]
    return {"scope": "CONTROLLED_FIXTURE_BENCHMARK_NOT_GOOGLE_ADS_TRAFFIC", "evaluation_at": evaluation_at,
            "holdout_observations": len(holdout), "matured_labels": len(mature),
            "pending_label_count": len(pending), "pending_observation_ids": sorted(pending),
            "policy": _metrics(mature, labels, lambda r: r["review_flag"]),
            "baselines": {
                "any_content_or_destination_change": _metrics(mature, labels, lambda r: r["content_change_baseline"]),
                "known_indicator_only": _metrics(mature, labels, lambda r: r["signals"]["known_threat"]),
            },
            "queue": {"capacity": capacity, "selected": len(queue), "matured_selected": len(adjudicated_queue),
                      "pending_selected": len(queue_ids - matured_ids),
                      "precision_at_selected_capacity": tp / len(adjudicated_queue) if adjudicated_queue else None,
                      "recall": _metrics(mature, labels, lambda r: r["observation_id"] in queue_ids)["recall"],
                      "capacity_deferred_candidates": sum(r["review_flag"] for r in holdout) - len(queue)},
            "scenario_metrics": groups,
            "label_maturity_follow_up": {
                "evaluation_at": follow_up_at, "original_decisions_unchanged": True,
                "matured_labels": len(follow_up_mature), "pending_labels": len(follow_up) - len(follow_up_mature),
                "policy": _metrics(follow_up_mature, labels, lambda r: r["review_flag"]),
                "queue": _metrics(follow_up_mature, labels, lambda r: r["observation_id"] in queue_ids),
            },
            "generalization_limit": "New fixture domains/campaign IDs; known scenario designs and lexicon. No estimate of production effectiveness.",
            "pending_labels_are_not_negative": True}
