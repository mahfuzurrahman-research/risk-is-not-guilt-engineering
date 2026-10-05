import unittest

from ml_demo.synthetic_data import SyntheticDatasetSpec, generate
from ml_demo.split import temporal_split
from ml_demo.contracts import timestamps


class TestTemporalSplit(unittest.TestCase):
    def test_strict_time_order_and_label_purge(self):
        df = generate(SyntheticDatasetSpec(rows=1000))
        train, validation, test = temporal_split(df)
        self.assertLess(train["event_date"].max(), validation["event_date"].min())
        self.assertLess(validation["event_date"].max(), test["event_date"].min())
        self.assertLess(timestamps(train, "label_available_at").max(), timestamps(validation, "decision_at").min())
        self.assertLess(timestamps(validation, "label_available_at").max(), timestamps(test, "decision_at").min())
        self.assertLess(len(train)+len(validation)+len(test), len(df))
        self.assertFalse(set(train["event_id"]) & set(test["event_id"]))

    def test_unavailable_outcomes_leave_no_train_sample(self):
        df = generate(SyntheticDatasetSpec(rows=1000)).assign(label_available_at="2030-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "no usable observations"):
            temporal_split(df)

    def test_too_few_dates_rejected(self):
        df = generate(SyntheticDatasetSpec(rows=1000))
        df = df[df["event_date"].isin(sorted(df["event_date"].unique())[:2])]
        with self.assertRaisesRegex(ValueError, "insufficient dates"):
            temporal_split(df)
