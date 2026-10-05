import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from fixtures import fitted_demo
from ml_demo.modeling import fit, score, evaluate_scored, choose_threshold


class TestModeling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train, cls.validation, cls.test, cls.bundle, cls.scored, cls.info = fitted_demo()

    def test_classifier_and_anomaly_layer(self):
        metrics = evaluate_scored(self.scored, self.test, self.bundle.threshold)
        self.assertIn(self.bundle.classifier_name, {"logistic_regression", "random_forest"})
        self.assertTrue(self.scored["classifier_score"].between(0, 1).all())
        self.assertTrue(self.scored["anomaly_score"].between(0, 1).all())
        self.assertEqual(sum(metrics["confusion_matrix"].values()), len(self.test))
        self.assertIn("prior_baseline", self.info)

    def test_label_free_inference_and_no_target_leakage(self):
        unlabeled = self.test.drop(columns=["abuse_label", "label_available_at"])
        changed = self.test.assign(abuse_label=1-self.test["abuse_label"])
        pd.testing.assert_frame_equal(score(self.bundle, unlabeled), self.scored)
        pd.testing.assert_frame_equal(score(self.bundle, changed), self.scored)
        self.assertNotIn("abuse_label", self.scored)

    def test_feature_order_and_account_id_do_not_change_scores(self):
        altered = self.test[list(reversed(self.test.columns))].assign(account_id="ACC99999")
        result = score(self.bundle, altered)
        np.testing.assert_array_equal(result["classifier_score"], self.scored["classifier_score"])
        np.testing.assert_array_equal(result["anomaly_score"], self.scored["anomaly_score"])

    def test_training_events_refused_for_held_out_scoring(self):
        with self.assertRaisesRegex(ValueError, "training events"):
            score(self.bundle, self.train)

    def test_model_release_must_precede_decisions(self):
        bundle = replace(self.bundle, released_at="2030-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "model not available"):
            score(bundle, self.test)

    def test_future_training_outcomes_block_fit(self):
        bad = self.train.assign(label_available_at="2030-01-01T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "outcome unavailable"):
            fit(bad, self.validation)

    def test_model_persistence_preserves_scoring_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bundle.joblib"
            joblib.dump(self.bundle, path)
            restored = joblib.load(path)
        pd.testing.assert_frame_equal(score(restored, self.test), self.scored)
        self.assertEqual(restored.reason_thresholds, self.bundle.reason_thresholds)

    def test_precision_target_failure_disables_classifier_flags(self):
        policy = choose_threshold([0, 1], [0.9, 0.1], min_precision=0.9)
        self.assertEqual(policy["status"], "PRECISION_TARGET_UNMET")
        self.assertGreater(policy["threshold"], 1)
        with self.assertRaisesRegex(ValueError, "both classes"):
            choose_threshold([0, 0], [0.2, 0.8])

    def test_evaluation_aligns_by_id_and_handles_one_class(self):
        expected = evaluate_scored(self.scored, self.test, self.bundle.threshold)
        shuffled = self.test.sample(frac=1, random_state=8)
        self.assertEqual(evaluate_scored(self.scored, shuffled, self.bundle.threshold), expected)
        metric = evaluate_scored(self.scored, self.test.assign(abuse_label=0), self.bundle.threshold)
        self.assertIsNone(metric["roc_auc"])
        self.assertIsNone(metric["average_precision"])
        self.assertEqual(metric["discrimination_status"], "SINGLE_CLASS")

    def test_evaluation_key_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "identifier mismatch"):
            evaluate_scored(self.scored, self.test.iloc[:-1], self.bundle.threshold)
