from __future__ import annotations

import pandas as pd

from .config import DATE, ID, TRAIN_FRACTION, VALIDATION_FRACTION
from .contracts import validate_frame, timestamps


def temporal_split(df: pd.DataFrame):
    """Split by complete days; purge labels unavailable at the next origin."""
    validate_frame(df, require_labels=True)
    ordered = df.sort_values([DATE, ID], kind="stable").reset_index(drop=True)
    dates = sorted(ordered[DATE].unique())
    train_end = max(1, int(len(dates) * TRAIN_FRACTION))
    val_end = max(train_end + 1, int(len(dates) * (TRAIN_FRACTION + VALIDATION_FRACTION)))
    if val_end >= len(dates):
        raise ValueError("insufficient dates for temporal split")
    train = ordered[ordered[DATE].isin(dates[:train_end])].copy()
    validation = ordered[ordered[DATE].isin(dates[train_end:val_end])].copy()
    test = ordered[ordered[DATE].isin(dates[val_end:])].copy()
    validation_origin = timestamps(validation, "decision_at").min()
    test_origin = timestamps(test, "decision_at").min()
    train = train[timestamps(train, "label_available_at") < validation_origin].copy()
    validation = validation[timestamps(validation, "label_available_at") < test_origin].copy()
    if train.empty or validation.empty or test.empty:
        raise ValueError("no usable observations after label-availability purge")
    if train[DATE].max() >= validation[DATE].min() or validation[DATE].max() >= test[DATE].min():
        raise ValueError("temporal overlap")
    return train, validation, test
