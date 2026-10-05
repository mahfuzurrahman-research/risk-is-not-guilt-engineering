from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .config import RANDOM_SEED, LABEL_DELAY_DAYS


@dataclass(frozen=True)
class SyntheticDatasetSpec:
    rows: int = 6000
    start_date: str = "2025-01-01"
    days: int = 180
    seed: int = RANDOM_SEED


def generate(spec: SyntheticDatasetSpec = SyntheticDatasetSpec()) -> pd.DataFrame:
    if type(spec.rows) is not int or not 500 <= spec.rows <= 1_000_000:
        raise ValueError("rows must be an integer between 500 and 1,000,000")
    if type(spec.days) is not int or spec.days < 30:
        raise ValueError("days must be at least 30")

    rng = np.random.default_rng(spec.seed)
    day_index = rng.integers(0, spec.days, size=spec.rows)

    drift = day_index >= int(spec.days * 0.80)
    latent_prob = 0.07 + 0.06 * drift.astype(float)
    latent_abuse = rng.random(spec.rows) < latent_prob

    def pois(base, risky):
        lam = np.where(latent_abuse, risky, base)
        return rng.poisson(lam).astype(float)

    account_age_days = np.where(
        latent_abuse,
        rng.gamma(shape=1.4, scale=18.0, size=spec.rows),
        rng.gamma(shape=2.6, scale=90.0, size=spec.rows),
    )
    ctr = np.where(
        latent_abuse,
        rng.beta(4.5, 3.0, size=spec.rows),
        rng.beta(1.8, 8.0, size=spec.rows),
    )
    conversion = np.where(
        latent_abuse,
        rng.beta(0.9, 12.0, size=spec.rows),
        rng.beta(2.0, 10.0, size=spec.rows),
    )
    device_count = pois(2.2, 8.5)
    ip_count = pois(3.0, 11.0)
    geo_velocity = np.where(
        latent_abuse,
        rng.lognormal(mean=5.7, sigma=0.55, size=spec.rows),
        rng.lognormal(mean=3.8, sigma=0.55, size=spec.rows),
    )
    repeat_ratio = np.where(
        latent_abuse,
        rng.beta(5.0, 2.0, size=spec.rows),
        rng.beta(1.3, 7.0, size=spec.rows),
    )
    night_share = np.where(
        latent_abuse,
        rng.beta(3.5, 2.0, size=spec.rows),
        rng.beta(1.4, 4.5, size=spec.rows),
    )
    payment_failures = pois(0.08, 1.2)
    burst_index = np.where(
        latent_abuse,
        rng.gamma(shape=3.0, scale=0.9, size=spec.rows),
        rng.gamma(shape=1.3, scale=0.45, size=spec.rows),
    )

    # Noisy synthetic outcome: positive examples are not perfectly separable.
    label_prob = np.where(latent_abuse, 0.88, 0.012)
    abuse_label = (rng.random(spec.rows) < label_prob).astype(int)

    start = date.fromisoformat(spec.start_date)
    event_dates = [
        (start + timedelta(days=int(x))).isoformat()
        for x in day_index
    ]

    df = pd.DataFrame({
        "event_id": [f"EVT{i:06d}" for i in range(spec.rows)],
        "event_date": event_dates,
        "account_id": [f"ACC{x:05d}" for x in rng.integers(1, 1800, size=spec.rows)],
        "account_age_days": np.round(account_age_days, 3),
        "click_through_rate": np.round(ctr, 6),
        "conversion_rate": np.round(conversion, 6),
        "device_count_24h": device_count.astype(int),
        "ip_count_24h": ip_count.astype(int),
        "geo_velocity_kmh": np.round(geo_velocity, 3),
        "repeat_click_ratio": np.round(repeat_ratio, 6),
        "night_activity_share": np.round(night_share, 6),
        "payment_failures_30d": payment_failures.astype(int),
        "burst_index": np.round(burst_index, 6),
        "abuse_label": abuse_label,
        "decision_at": [d + "T23:59:59Z" for d in event_dates],
        "feature_available_at": [d + "T00:00:00Z" for d in event_dates],
        "label_available_at": [
            (date.fromisoformat(d) + timedelta(days=LABEL_DELAY_DAYS)).isoformat()
            + "T00:00:00Z" for d in event_dates
        ],
        "synthetic_record": True,
    })

    return df.sort_values(
        ["event_date", "event_id"],
        kind="stable",
    ).reset_index(drop=True)
