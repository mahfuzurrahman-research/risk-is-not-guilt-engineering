from __future__ import annotations

import json
from pathlib import Path


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_model_card(path: Path, manifest: dict, validation: dict, test: dict, queue: dict) -> None:
    metrics = test["selected_classifier"]
    prior = test["train_prior_baseline"]
    def number(value):
        return "undefined (single-class sample)" if value is None else f"{value:.6f}"
    text = f"""# Synthetic Advertising-Integrity ML Model Card

## Intended use

Engineering demonstration of fabricated risk classification, anomaly detection,
temporal validation, and a capacity-bounded human-review queue. Every event and
outcome comes from the simulator. The target is not observed fraud or legal guilt.

## Model and timing

- Selected classifier: {manifest['selected_classifier']}
- Model ID: {manifest['model_id']}
- Training / tuning / held-out rows: {manifest['train_rows']} / {manifest['validation_rows']} / {manifest['test_rows']}
- Earliest policy release: {manifest['released_at']}
- Threshold: {manifest['threshold']:.6f}; status: {manifest['threshold_status']}
- Features must be available by event decision time.
- Training and validation outcomes unavailable at the next origin are purged.
- Model and threshold selection use validation only; validation scores are tuning results.
- Future test decisions occur after policy release; test outcomes are used retrospectively.

## Held-out synthetic evaluation

- Average precision: {number(metrics['average_precision'])}
- Training-prior baseline average precision: {number(prior['average_precision'])}
- ROC AUC: {number(metrics['roc_auc'])}
- Precision / recall / F1: {metrics['precision']:.6f} / {metrics['recall']:.6f} / {metrics['f1']:.6f}
- Brier score: {metrics['brier']:.6f}
- Combined queue precision at capacity {queue['capacity']}: {queue['combined']['precision_at_capacity']:.6f}
- Classifier-only queue precision at the same capacity: {queue['classifier_only']['precision_at_capacity']:.6f}
- Anomaly-only queue precision at the same capacity: {queue['anomaly_only']['precision_at_capacity']:.6f}

## Scoring and review policy

The class-weighted classifier's predict_proba output is called a classifier score.
No probability calibration is fitted. The score is not an established fraud
probability. The training-only Isolation Forest score is normalized by training
quantiles; an anomaly is not proof of abuse.

The review priority is 0.80 times classifier score plus 0.20 times anomaly score.
These are fixed demonstration weights, not optimized or certified weights.
Capacity is the ceiling of 10% of held-out events. Equal scores use ascending
event IDs. The classifier threshold tunes F1 subject to a 0.55 validation
precision target; if infeasible, classifier flags are disabled.

The queue contains no outcome labels. Every case is PENDING_REVIEW, recommends
HUMAN_REVIEW, and carries adverse_action_authorized=false. Feature reason codes
describe training-tail signals; they are not model attribution or legal findings.

## Reproducibility and limits

The saved bundle contains estimators, thresholds, feature order, training reason
cutoffs, release time, and model ID. A persistence roundtrip is checked. The
manifest records dependency versions, source hashes, and artifact hashes.
A success receipt is published last; consumers must verify its hashes.

The simulator builds strong feature/outcome associations and a late prevalence
shift. Its performance measures show that the code executes; they provide no
evidence of generalization to real advertising fraud, new accounts, or countries.
Account IDs are randomly reused and excluded from features; this is a temporal
event holdout, not an unseen-account evaluation. Source-specific measurement,
label noise, deployment monitoring, fairness, and production inference remain
outside this demonstration.

There is no Google Ads data, real fraud labeling, commercial deployment, or
extension of the private paper's scientific claims.
"""
    path.write_text(text, encoding="utf-8")
