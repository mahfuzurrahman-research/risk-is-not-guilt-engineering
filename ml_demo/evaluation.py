"""Retrospective evaluation; never used to rank an operational queue."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype, is_bool_dtype

from .config import ID, LABEL


def label_vector(scored: pd.DataFrame, labels: pd.DataFrame, *, exact: bool = True) -> np.ndarray:
    if not {ID, LABEL}.issubset(labels.columns) or ID not in scored.columns:
        raise ValueError("event identifiers and retrospective labels required")
    if labels[ID].isna().any() or scored[ID].isna().any() or labels[ID].duplicated().any() or scored[ID].duplicated().any():
        raise ValueError("duplicate/missing evaluation identifiers")
    y = labels[LABEL]
    if not is_numeric_dtype(y) or is_bool_dtype(y) or not y.isin([0, 1]).all():
        raise ValueError("invalid retrospective labels")
    if not set(scored[ID]).issubset(labels[ID]) or (exact and set(scored[ID]) != set(labels[ID])):
        raise ValueError("evaluation identifier mismatch")
    return labels.set_index(ID).loc[scored[ID], LABEL].to_numpy(dtype=int)


def evaluate_queue(queue: pd.DataFrame, labels: pd.DataFrame) -> dict:
    y = label_vector(queue, labels, exact=False)
    positives = int(labels[LABEL].sum())
    return {
        "reviewed_rows": int(len(queue)), "synthetic_positives_in_queue": int(y.sum()),
        "precision_at_capacity": float(y.mean()) if len(y) else None,
        "recall_at_capacity": float(y.sum() / positives) if positives else None,
        "evaluation_only": True, "labels_used_for_ranking": False,
    }
