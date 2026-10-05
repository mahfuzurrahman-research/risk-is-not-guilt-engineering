from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    average_precision_score, brier_score_loss, precision_recall_curve,
    precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix,
)

from .config import (
    FEATURES, LABEL, ID, RANDOM_SEED, MIN_PRECISION, CLASSIFIER_WEIGHT,
    ANOMALY_WEIGHT, SCHEMA_VERSION, POLICY_VERSION,
)
from .contracts import validate_frame, timestamps
from .evaluation import label_vector
from .queue import thresholds


@dataclass
class ModelBundle:
    classifier_name: str
    classifier: object
    prior_model: DummyClassifier
    anomaly_model: IsolationForest
    threshold: float
    threshold_status: str
    anomaly_low: float
    anomaly_high: float
    reason_thresholds: dict
    released_at: str
    feature_names: tuple
    fit_event_ids: tuple
    validation_event_ids: tuple
    model_id: str


def _vectors(y, prob):
    y, prob = np.asarray(y), np.asarray(prob, dtype=float)
    if y.ndim != 1 or prob.ndim != 1 or len(y) != len(prob) or not len(y):
        raise ValueError("non-empty aligned metric vectors required")
    if not np.isin(y, [0, 1]).all() or not np.isfinite(prob).all() or ((prob < 0) | (prob > 1)).any():
        raise ValueError("invalid labels or classifier scores")
    return y.astype(int), prob


def _metrics(y, prob, threshold: float) -> dict:
    y, prob = _vectors(y, prob)
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("invalid threshold")
    pred = (prob >= threshold).astype(int)
    both = len(np.unique(y)) == 2
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "average_precision": float(average_precision_score(y, prob)) if both else None,
        "roc_auc": float(roc_auc_score(y, prob)) if both else None,
        "discrimination_status": "BOTH_CLASSES" if both else "SINGLE_CLASS",
        "brier": float(brier_score_loss(y, prob)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "threshold": float(threshold),
        "positives": int(y.sum()),
        "positive_rate": float(y.mean()),
        "predicted_positive_rows": int(pred.sum()),
        "rows": int(len(y)),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "score_interpretation": "uncalibrated classifier score; not an established fraud probability",
    }


def choose_threshold(y, prob, min_precision: float = MIN_PRECISION) -> dict:
    y, prob = _vectors(y, prob)
    if len(np.unique(y)) != 2:
        raise ValueError("threshold tuning requires both classes")
    if not 0 < min_precision <= 1:
        raise ValueError("min_precision outside (0,1]")
    precision, recall, cutoffs = precision_recall_curve(y, prob)
    candidates = []
    for p, r, cutoff in zip(precision[:-1], recall[:-1], cutoffs):
        if p >= min_precision and r > 0:
            candidates.append((2 * p * r / (p + r), r, p, float(cutoff)))
    if not candidates:
        return {"threshold": float(np.nextafter(1.0, 2.0)), "status": "PRECISION_TARGET_UNMET"}
    return {"threshold": max(candidates)[-1], "status": "VALIDATION_TARGET_MET"}


def fit(train: pd.DataFrame, validation: pd.DataFrame) -> tuple[ModelBundle, dict]:
    validate_frame(train, require_labels=True)
    validate_frame(validation, require_labels=True)
    train = train.sort_values(["event_date", ID], kind="stable")
    validation = validation.sort_values(["event_date", ID], kind="stable")
    if set(train[ID]) & set(validation[ID]):
        raise ValueError("training/validation event overlap")
    origin = timestamps(validation, "decision_at").min()
    if timestamps(train, "decision_at").max() >= origin:
        raise ValueError("training/validation temporal overlap")
    if (timestamps(train, "label_available_at") >= origin).any():
        raise ValueError("training outcome unavailable at validation origin")
    if train[LABEL].nunique() != 2 or validation[LABEL].nunique() != 2:
        raise ValueError("training and validation require both classes")
    X_train, y_train = train[FEATURES], train[LABEL].astype(int)
    X_val, y_val = validation[FEATURES], validation[LABEL].astype(int)
    models = {
        "logistic_regression": Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=RANDOM_SEED)),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=250, max_depth=9, min_samples_leaf=4,
            class_weight="balanced_subsample", random_state=RANDOM_SEED, n_jobs=1,
        ),
    }
    validation_results, decisions = {}, {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        scores = model.predict_proba(X_val)[:, 1]
        decisions[name] = choose_threshold(y_val, scores)
        validation_results[name] = {
            **_metrics(y_val, scores, decisions[name]["threshold"]),
            "threshold_status": decisions[name]["status"],
        }
    names = list(models)
    selected_name = max(names, key=lambda name: (
        validation_results[name]["average_precision"],
        validation_results[name]["f1"], -names.index(name),
    ))
    policy = decisions[selected_name]
    prior = DummyClassifier(strategy="prior").fit(X_train, y_train)
    anomaly = IsolationForest(
        n_estimators=250, contamination=0.08, random_state=RANDOM_SEED, n_jobs=1,
    ).fit(X_train)
    train_anomaly = -anomaly.decision_function(X_train)
    low, high = (float(np.quantile(train_anomaly, q)) for q in [0.01, 0.99])
    if high <= low:
        raise ValueError("degenerate training anomaly reference")
    fingerprint = hashlib.sha256(
        (train.to_csv(index=False) + validation.to_csv(index=False)).encode()
        + json.dumps({
            "classifier": selected_name, "threshold": policy["threshold"],
            "schema": SCHEMA_VERSION, "policy": POLICY_VERSION, "seed": RANDOM_SEED,
        }, sort_keys=True).encode()
    ).hexdigest()
    bundle = ModelBundle(
        classifier_name=selected_name, classifier=models[selected_name], prior_model=prior,
        anomaly_model=anomaly, threshold=policy["threshold"], threshold_status=policy["status"],
        anomaly_low=low, anomaly_high=high, reason_thresholds=thresholds(train),
        released_at=validation["label_available_at"].max(), feature_names=tuple(FEATURES),
        fit_event_ids=tuple(train[ID]), validation_event_ids=tuple(validation[ID]),
        model_id="synthetic-v2-" + fingerprint[:16],
    )
    return bundle, {
        "selected_classifier": selected_name,
        "selection_rule": "validation AP, then validation F1, then logistic baseline on exact ties",
        "threshold_rule": "validation F1 under minimum precision; disable classifier flags if infeasible",
        "min_validation_precision": MIN_PRECISION,
        "candidate_metrics": validation_results,
        "selected_metrics": validation_results[selected_name],
        "prior_baseline": _metrics(y_val, prior.predict_proba(X_val)[:, 1], 0.5),
        "validation_is_tuning_data": True,
    }


def score(bundle: ModelBundle, df: pd.DataFrame) -> pd.DataFrame:
    validate_frame(df)
    if tuple(FEATURES) != bundle.feature_names:
        raise ValueError("model feature schema mismatch")
    if set(df[ID]) & (set(bundle.fit_event_ids) | set(bundle.validation_event_ids)):
        raise ValueError("held-out scoring contains tuning/training events")
    if timestamps(df, "decision_at").min() <= pd.Timestamp(bundle.released_at):
        raise ValueError("model not available by scoring decision")
    X = df[FEATURES]
    scores = bundle.classifier.predict_proba(X)[:, 1]
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("invalid model scores")
    anomaly_raw = -bundle.anomaly_model.decision_function(X)
    anomaly_norm = np.clip(
        (anomaly_raw - bundle.anomaly_low) / (bundle.anomaly_high - bundle.anomaly_low), 0.0, 1.0,
    )
    if not np.isfinite(anomaly_norm).all():
        raise ValueError("invalid anomaly scores")
    out = df.drop(columns=[LABEL, "label_available_at"], errors="ignore").copy()
    out["classifier_score"] = scores
    out["anomaly_score"] = anomaly_norm
    out["combined_risk_score"] = CLASSIFIER_WEIGHT * scores + ANOMALY_WEIGHT * anomaly_norm
    out["classifier_flag"] = (scores >= bundle.threshold).astype(int)
    out["model_id"] = bundle.model_id
    out["policy_version"] = POLICY_VERSION
    return out


def evaluate_scored(scored: pd.DataFrame, labels: pd.DataFrame, threshold: float) -> dict:
    return _metrics(label_vector(scored, labels), scored["classifier_score"].to_numpy(), threshold)
