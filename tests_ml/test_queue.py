import json
import math
import unittest

import numpy as np
import pandas as pd

from fixtures import fitted_demo
from ml_demo.config import QUEUE_FRACTION
from ml_demo.queue import build_queue, reason_codes


class TestQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, _, cls.bundle, cls.scored, _ = fitted_demo()

    def test_queue_capacity_order_and_review_only_status(self):
        queue = build_queue(self.scored, self.bundle.reason_thresholds)
        self.assertEqual(len(queue), math.ceil(len(self.scored) * QUEUE_FRACTION))
        self.assertTrue(queue["combined_risk_score"].is_monotonic_decreasing)
        self.assertEqual(queue["queue_rank"].tolist(), list(range(1, len(queue)+1)))
        self.assertNotIn("abuse_label", queue)
        self.assertNotIn("label_available_at", queue)
        self.assertTrue(queue["review_status"].eq("PENDING_REVIEW").all())
        self.assertTrue(queue["recommended_action"].eq("HUMAN_REVIEW").all())
        self.assertFalse(queue["adverse_action_authorized"].any())
        self.assertTrue(all(json.loads(s) for s in queue["reason_codes"]))

    def test_equal_scores_use_id_tiebreak_independent_of_input_order(self):
        tied = self.scored.assign(combined_risk_score=0.5)
        a = build_queue(tied, self.bundle.reason_thresholds, capacity=7)
        b = build_queue(tied.sample(frac=1, random_state=3), self.bundle.reason_thresholds, capacity=7)
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(a["event_id"].tolist(), sorted(tied["event_id"])[:7])

    def test_labels_cannot_change_queue(self):
        a = build_queue(self.scored, self.bundle.reason_thresholds)
        b = build_queue(self.scored.assign(abuse_label=1, label_available_at="2030-01-01"), self.bundle.reason_thresholds)
        pd.testing.assert_frame_equal(a, b)

    def test_zero_empty_and_oversized_capacity(self):
        self.assertTrue(build_queue(self.scored, self.bundle.reason_thresholds, capacity=0).empty)
        self.assertTrue(build_queue(self.scored.iloc[:0], self.bundle.reason_thresholds).empty)
        self.assertEqual(len(build_queue(self.scored, self.bundle.reason_thresholds, capacity=len(self.scored)+9)), len(self.scored))

    def test_invalid_capacity_and_scores_rejected(self):
        for capacity in [-1, 2.5, True]:
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                build_queue(self.scored, self.bundle.reason_thresholds, capacity=capacity)
        for value in [np.nan, np.inf, -0.1, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_queue(self.scored.assign(combined_risk_score=value), self.bundle.reason_thresholds)

    def test_equal_tail_thresholds_do_not_create_false_reason(self):
        row = pd.Series({**self.bundle.reason_thresholds, "classifier_flag":0, "anomaly_score":0})
        self.assertEqual(reason_codes(row, self.bundle.reason_thresholds), ["CAPACITY_PRIORITY_ONLY"])

    def test_string_scores_cannot_change_numeric_order(self):
        with self.assertRaisesRegex(ValueError, "numeric queue scores"):
            build_queue(self.scored.assign(combined_risk_score="0.8"), self.bundle.reason_thresholds)
