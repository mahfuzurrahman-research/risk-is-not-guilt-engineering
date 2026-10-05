import unittest

from ml_demo.synthetic_data import SyntheticDatasetSpec, generate


class TestSyntheticData(unittest.TestCase):
    def test_deterministic(self):
        a = generate(SyntheticDatasetSpec(rows=800, seed=77))
        b = generate(SyntheticDatasetSpec(rows=800, seed=77))
        self.assertTrue(a.equals(b))

    def test_domain(self):
        df = generate(SyntheticDatasetSpec(rows=800))
        self.assertTrue(df["abuse_label"].isin([0, 1]).all())
        self.assertTrue(df["click_through_rate"].between(0, 1).all())
        self.assertTrue(df["conversion_rate"].between(0, 1).all())


if __name__ == "__main__":
    unittest.main()
