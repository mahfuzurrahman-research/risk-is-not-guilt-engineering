import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ml_demo.synthetic_data import SyntheticDatasetSpec, generate
from ml_demo.contracts import validate_frame, load_contract


class TestMLContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = generate(SyntheticDatasetSpec(rows=800))

    def test_valid_and_unlabeled_frames(self):
        validate_frame(self.df, require_labels=True)
        validate_frame(self.df.drop(columns=["abuse_label", "label_available_at"]))

    def test_numeric_and_domain_failures(self):
        mutations = [
            ("burst_index", np.nan), ("burst_index", np.inf), ("burst_index", -1),
            ("burst_index", "1.5"), ("burst_index", True),
            ("click_through_rate", 1.1), ("device_count_24h", 1.5),
            ("abuse_label", 2), ("synthetic_record", False),
        ]
        for column, value in mutations:
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                validate_frame(self.df.assign(**{column:value}), require_labels=True)

    def test_key_schema_and_future_feature_failures(self):
        bad_frames = [
            self.df.assign(event_id="EVT000000"),
            self.df.assign(feature_available_at="2030-01-01T00:00:00Z"),
            self.df.assign(event_date="2020-01-01"),
            self.df.assign(decision_at="not-a-timestamp"),
            self.df.assign(secret_label_proxy=1),
            self.df.drop(columns=["burst_index"]),
        ]
        for i, frame in enumerate(bad_frames):
            with self.subTest(case=i), self.assertRaises(ValueError):
                validate_frame(frame, require_labels=True)

    def test_claim_contract_is_enforced_at_runtime(self):
        contract = load_contract()
        for key in ["synthetic_only", "uses_google_ads_data", "scientific_claims_extended"]:
            bad = {**contract, key:not contract[key]}
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "contract.json"
                path.write_text(json.dumps(bad))
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "claim contract"):
                    load_contract(path)
