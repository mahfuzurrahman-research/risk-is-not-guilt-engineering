import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestBoundaries(unittest.TestCase):
    def test_claim_boundaries_fail_closed(self):
        obj = json.loads(
            (ROOT / "contracts/ml_demo_contract.json").read_text(encoding="utf-8")
        )
        self.assertTrue(obj["synthetic_only"])
        self.assertFalse(obj["uses_google_ads_data"])
        self.assertFalse(obj["uses_real_fraud_labels"])
        self.assertFalse(obj["commercial_production_deployment"])
        self.assertFalse(obj["scientific_claims_extended"])


if __name__ == "__main__":
    unittest.main()
