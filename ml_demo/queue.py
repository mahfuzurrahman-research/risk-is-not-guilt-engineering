from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype

from .config import QUEUE_FRACTION, ID, ANOMALY_REASON_THRESHOLD
from .contracts import validate_frame, META
from .config import FEATURES

REASON_MAP = {
    "account_age_days": ("LOW_ACCOUNT_AGE", "low"),
    "click_through_rate": ("HIGH_CTR", "high"),
    "conversion_rate": ("LOW_CONVERSION_RATE", "low"),
    "device_count_24h": ("DEVICE_FANOUT", "high"),
    "ip_count_24h": ("IP_FANOUT", "high"),
    "geo_velocity_kmh": ("HIGH_GEO_VELOCITY", "high"),
    "repeat_click_ratio": ("HIGH_REPEAT_CLICK_RATIO", "high"),
    "night_activity_share": ("HIGH_NIGHT_ACTIVITY", "high"),
    "payment_failures_30d": ("PAYMENT_FAILURES", "high"),
    "burst_index": ("CLICK_BURST", "high"),
}
QUEUE_COLUMNS = [
    "queue_rank", "case_id", ID, "event_date", "account_id",
    "combined_risk_score", "classifier_score", "anomaly_score", "classifier_flag",
    "model_id", "policy_version", "reason_codes", "review_status",
    "recommended_action", "adverse_action_authorized",
]


def thresholds(train: pd.DataFrame) -> dict:
    validate_frame(train)
    return {
        feature: float(train[feature].quantile(0.05 if direction == "low" else 0.95))
        for feature, (_, direction) in REASON_MAP.items()
    }


def reason_codes(row: pd.Series, cutoffs: dict) -> list[str]:
    reasons = []
    if int(row["classifier_flag"]) == 1:
        reasons.append("CLASSIFIER_THRESHOLD_EXCEEDED")
    if float(row["anomaly_score"]) >= ANOMALY_REASON_THRESHOLD:
        reasons.append("ANOMALOUS_MULTIVARIATE_PATTERN")
    for feature, (code, direction) in REASON_MAP.items():
        value, cutoff = float(row[feature]), float(cutoffs[feature])
        if (direction == "high" and value > cutoff) or (direction == "low" and value < cutoff):
            reasons.append(code)
    return reasons or ["CAPACITY_PRIORITY_ONLY"]


def build_queue(scored: pd.DataFrame, cutoffs: dict, capacity: int | None = None) -> pd.DataFrame:
    if capacity is not None and (type(capacity) is not int or capacity < 0):
        raise ValueError("capacity must be a non-negative integer")
    if set(cutoffs) != set(REASON_MAP) or not all(np.isfinite(v) for v in cutoffs.values()):
        raise ValueError("invalid training reason thresholds")
    required = set(META) | set(FEATURES) | {
        "classifier_score", "anomaly_score", "combined_risk_score", "classifier_flag",
        "model_id", "policy_version",
    }
    if not required.issubset(scored.columns):
        raise ValueError("missing scored columns")
    if scored.empty:
        return pd.DataFrame(columns=QUEUE_COLUMNS)
    validate_frame(scored[list(META) + FEATURES])
    for col in ["classifier_score", "anomaly_score", "combined_risk_score"]:
        if not is_numeric_dtype(scored[col]) or is_bool_dtype(scored[col]):
            raise ValueError("numeric queue scores required")
        a = scored[col].to_numpy(dtype=float)
        if not np.isfinite(a).all() or ((a < 0) | (a > 1)).any():
            raise ValueError("invalid queue score")
    if not is_numeric_dtype(scored["classifier_flag"]) or is_bool_dtype(scored["classifier_flag"]) or not scored["classifier_flag"].isin([0, 1]).all():
        raise ValueError("invalid classifier_flag")
    n = math.ceil(len(scored) * QUEUE_FRACTION) if capacity is None else capacity
    queue = scored.sort_values(["combined_risk_score", ID], ascending=[False, True], kind="stable").head(n).copy()
    queue["reason_codes"] = [
        json.dumps(reason_codes(row, cutoffs), separators=(",", ":"))
        for _, row in queue.iterrows()
    ]
    queue.insert(0, "queue_rank", range(1, len(queue) + 1))
    queue["case_id"] = "CASE-" + queue[ID]
    queue["review_status"] = "PENDING_REVIEW"
    queue["recommended_action"] = "HUMAN_REVIEW"
    queue["adverse_action_authorized"] = False
    return queue[QUEUE_COLUMNS].reset_index(drop=True)
