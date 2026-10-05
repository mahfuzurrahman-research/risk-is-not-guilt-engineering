from __future__ import annotations

FEATURES = [
    "account_age_days",
    "click_through_rate",
    "conversion_rate",
    "device_count_24h",
    "ip_count_24h",
    "geo_velocity_kmh",
    "repeat_click_ratio",
    "night_activity_share",
    "payment_failures_30d",
    "burst_index",
]

LABEL = "abuse_label"
DATE = "event_date"
ID = "event_id"

RANDOM_SEED = 20261006
TRAIN_FRACTION = 0.60
VALIDATION_FRACTION = 0.20
QUEUE_FRACTION = 0.10

SCHEMA_VERSION = "2.0"
POLICY_VERSION = "synthetic-review-v2"
MIN_PRECISION = 0.55
CLASSIFIER_WEIGHT = 0.80
ANOMALY_WEIGHT = 0.20
ANOMALY_REASON_THRESHOLD = 0.80
LABEL_DELAY_DAYS = 7

RATE_FEATURES = {
    "click_through_rate", "conversion_rate", "repeat_click_ratio",
    "night_activity_share",
}
COUNT_FEATURES = {"device_count_24h", "ip_count_24h", "payment_failures_30d"}
