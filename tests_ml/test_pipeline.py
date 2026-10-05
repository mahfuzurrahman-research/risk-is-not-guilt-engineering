import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ml_demo.integrity import verify_artifacts
from ml_demo.pipeline import run
from ml_demo.synthetic_data import SyntheticDatasetSpec


class TestMLPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.spec = SyntheticDatasetSpec(rows=800)
        cls.result = run(cls.root, cls.spec)
        cls.out = cls.root / "outputs/ml_demo"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_receipt_and_required_outputs(self):
        receipt = verify_artifacts(self.out)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(self.result["manifest"]["persistence_roundtrip"], "PASS")

    def test_identical_runs_preserve_all_artifact_hashes(self):
        before = (self.out / "run_receipt.json").read_bytes()
        run(self.root, self.spec)
        self.assertEqual((self.out / "run_receipt.json").read_bytes(), before)

    def test_failed_build_keeps_previous_completed_run(self):
        before = (self.out / "run_receipt.json").read_bytes()
        with patch("ml_demo.pipeline._build", side_effect=RuntimeError("injected failure")):
            with self.assertRaises(RuntimeError):
                run(self.root, self.spec)
        self.assertEqual((self.out / "run_receipt.json").read_bytes(), before)
        verify_artifacts(self.out)
        with (self.root / "outputs/.ml_demo.lock").open("a+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_lock_prevents_overlapping_writers(self):
        lock = self.root / "outputs/.ml_demo.lock"
        with lock.open("a+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "another ML run"):
                run(self.root, self.spec)
        verify_artifacts(self.out)

    def test_corrupted_artifact_rejected(self):
        path = self.out / "investigation_queue.csv"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"corrupt")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_artifacts(self.out)
        finally:
            path.write_bytes(original)
