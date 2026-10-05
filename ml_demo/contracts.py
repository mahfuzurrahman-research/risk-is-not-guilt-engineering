"""Enforce the fabricated-data contract before fitting or scoring."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from .config import FEATURES, RATE_FEATURES, COUNT_FEATURES, LABEL, ID, DATE, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
META = {ID, DATE, "account_id", "decision_at", "feature_available_at", "synthetic_record"}
TARGET_META = {LABEL, "label_available_at"}


def load_contract(path: Path | None = None) -> dict:
    obj = json.loads((path or ROOT / "contracts/ml_demo_contract.json").read_text())
    expected_flags = {
        "synthetic_only": True, "uses_google_ads_data": False,
        "uses_real_fraud_labels": False, "commercial_production_deployment": False,
        "scientific_claims_extended": False,
    }
    if any(obj.get(k) is not v for k, v in expected_flags.items()):
        raise ValueError("synthetic claim contract violated")
    if obj.get("contract_version") != SCHEMA_VERSION or obj.get("features") != FEATURES:
        raise ValueError("schema/feature contract mismatch")
    if obj.get("target") != LABEL:
        raise ValueError("target contract mismatch")
    return obj


def timestamps(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column]
    if not values.map(lambda v: isinstance(v, str)).all():
        raise ValueError(f"{column}: timestamps must be UTC strings")
    if not values.str.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z").all():
        raise ValueError(f"{column}: invalid UTC timestamp format")
    try:
        return pd.to_datetime(values, format="%Y-%m-%dT%H:%M:%SZ", utc=True, errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{column}: invalid timestamp") from exc


def validate_frame(df: pd.DataFrame, *, require_labels: bool = False) -> None:
    load_contract()
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("non-empty DataFrame required")
    if not df.columns.is_unique or not df.index.is_unique:
        raise ValueError("duplicate columns or index")
    required = META | set(FEATURES) | (TARGET_META if require_labels else set())
    if not required.issubset(df.columns):
        raise ValueError(f"missing columns: {sorted(required - set(df.columns))}")
    unknown = set(df.columns) - META - set(FEATURES) - TARGET_META
    if unknown:
        raise ValueError(f"unexpected columns: {sorted(unknown)}")
    if df[list(required)].isna().any().any():
        raise ValueError("missing input values")
    for col, pattern in [(ID, r"EVT\d{6}"), ("account_id", r"ACC\d{5}")]:
        if not df[col].map(lambda v: isinstance(v, str)).all() or not df[col].str.fullmatch(pattern).all():
            raise ValueError(f"{col}: invalid fabricated identifier")
    if df[ID].duplicated().any():
        raise ValueError("duplicate event_id")
    if not is_bool_dtype(df["synthetic_record"]) or not df["synthetic_record"].all():
        raise ValueError("synthetic_record must be boolean true")
    for feature in FEATURES:
        s = df[feature]
        if not is_numeric_dtype(s) or is_bool_dtype(s):
            raise ValueError(f"{feature}: numeric values required")
        a = s.to_numpy(dtype=float)
        if not np.isfinite(a).all() or (a < 0).any():
            raise ValueError(f"{feature}: finite non-negative values required")
        if feature in RATE_FEATURES and (a > 1).any():
            raise ValueError(f"{feature}: rate outside [0,1]")
        if feature in COUNT_FEATURES and not np.equal(a, np.floor(a)).all():
            raise ValueError(f"{feature}: integer counts required")
    decisions = timestamps(df, "decision_at")
    available = timestamps(df, "feature_available_at")
    if (available > decisions).any():
        raise ValueError("feature available after decision")
    if not df[DATE].map(lambda v: isinstance(v, str)).all() or not df[DATE].eq(decisions.dt.strftime("%Y-%m-%d")).all():
        raise ValueError("event_date inconsistent with decision_at")
    if require_labels:
        s = df[LABEL]
        if not is_numeric_dtype(s) or is_bool_dtype(s) or not s.isin([0, 1]).all():
            raise ValueError("label must be numeric 0/1")
        if (timestamps(df, "label_available_at") <= decisions).any():
            raise ValueError("synthetic outcome must arrive after decision")
