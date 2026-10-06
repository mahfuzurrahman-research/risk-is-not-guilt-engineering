import fcntl
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ads_lab.contracts import digest, read_json, write_json
from ads_lab.pipeline import run, verify
from ads_lab.warehouse import validate_warehouse


class TestSavedEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_temporary = tempfile.TemporaryDirectory()
        cls.base = Path(cls.base_temporary.name) / "ads_lab"
        cls.result = run(cls.base, replicas=1, capacity=3)

    @classmethod
    def tearDownClass(cls):
        cls.base_temporary.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.output = Path(self.temporary.name) / "ads_lab"
        shutil.copytree(self.base, self.output)

    def tearDown(self):
        self.temporary.cleanup()

    def rehash(self, name):
        receipt = read_json(self.output / "run_receipt.json")
        receipt["artifact_sha256"][name] = digest((self.output / name).read_bytes())
        write_json(self.output / "run_receipt.json", receipt)

    def test_all_artifacts_and_sql_replay(self):
        result = verify(self.output)
        self.assertEqual(result["status"], "PASS")
        self.assertGreaterEqual(result["independent_sql_gates"], 25)

    def test_identical_runs_preserve_artifact_hashes(self):
        before = (self.output / "run_receipt.json").read_bytes()
        run(self.output, replicas=1, capacity=3)
        self.assertEqual(before, (self.output / "run_receipt.json").read_bytes())

    def test_failed_build_keeps_last_completed_run(self):
        before = (self.output / "run_receipt.json").read_bytes()
        with patch("ads_lab.pipeline._build", side_effect=RuntimeError("injected build failure")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                run(self.output, replicas=1, capacity=3)
        self.assertEqual(before, (self.output / "run_receipt.json").read_bytes())
        verify(self.output)

    def test_failed_publication_restores_previous_run(self):
        before = (self.output / "run_receipt.json").read_bytes()
        replace = os.replace
        def fail_staging(source, destination):
            if "-stage-" in Path(source).name and Path(destination) == self.output:
                raise RuntimeError("injected publication failure")
            return replace(source, destination)
        with patch("ads_lab.pipeline.os.replace", side_effect=fail_staging):
            with self.assertRaisesRegex(RuntimeError, "publication failure"):
                run(self.output, replicas=2, capacity=4)
        self.assertEqual(before, (self.output / "run_receipt.json").read_bytes())
        verify(self.output)

    def test_writer_lock_blocks_concurrent_publication(self):
        lock = self.output.parent / ".ads_lab.lock"
        with lock.open("a+b") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "another Ads lab run"):
                run(self.output)

    def test_raw_corruption_fails_artifact_hash(self):
        path = self.output / "corpus.json"
        path.write_bytes(path.read_bytes() + b"corrupt")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            verify(self.output)

    def test_rehashed_queue_corruption_fails_reconstruction(self):
        path = self.output / "investigation_queue.json"
        data = read_json(path)
        data[0]["risk_score"] += 1
        write_json(path, data)
        self.rehash(path.name)
        with self.assertRaisesRegex(ValueError, "raw-evidence replay"):
            verify(self.output)

    def test_rehashed_policy_corruption_fails_validation_replay(self):
        path = self.output / "policy.json"
        data = read_json(path)
        data["threshold"] += 1
        write_json(path, data)
        self.rehash(path.name)
        with self.assertRaisesRegex(ValueError, "raw-evidence replay"):
            verify(self.output)

    def test_changed_sql_score_is_independently_detected(self):
        path = self.output / "warehouse.sqlite"
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE reported_scores SET risk_score=risk_score+1")
        with self.assertRaisesRegex(ValueError, "score_values"):
            validate_warehouse(path, read_json(self.output / "evaluation.json"))

    def test_missing_validation_capture_is_independently_detected(self):
        path = self.output / "warehouse.sqlite"
        with sqlite3.connect(path) as connection:
            connection.execute("DELETE FROM captures WHERE observation_id=(SELECT observation_id FROM observation_base WHERE split='validation' LIMIT 1)")
        with self.assertRaisesRegex(ValueError, "complete_contexts"):
            validate_warehouse(path, read_json(self.output / "evaluation.json"))

    def test_rehashed_warehouse_primitive_corruption_fails_raw_replay(self):
        path = self.output / "warehouse.sqlite"
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE captures SET template_sha256='modified'")
        self.rehash(path.name)
        with self.assertRaisesRegex(ValueError, "warehouse raw-input replay"):
            verify(self.output)

    def test_unknown_directory_and_symlink_outputs_rejected(self):
        unknown = self.output.parent / "personal"
        unknown.mkdir()
        (unknown / "notes.txt").write_text("keep")
        with self.assertRaisesRegex(ValueError, "without a lab receipt"):
            run(unknown)
        link = self.output.parent / "linked"
        link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            run(link)

    def test_extra_artifact_is_rejected(self):
        (self.output / "extra.txt").write_text("unexpected")
        with self.assertRaisesRegex(ValueError, "unexpected artifact"):
            verify(self.output)

    def test_reports_escape_markup(self):
        from ads_lab.reporting import build_report
        queue = read_json(self.output / "investigation_queue.json")
        queue[0]["observation_id"] = '<img src=x onerror="alert(1)">'
        report = build_report(read_json(self.output / "evaluation.json"), queue,
                              read_json(self.output / "sql_checks.json"), read_json(self.output / "policy.json"))
        self.assertIn("&lt;img", report)
        self.assertNotIn("<img", report)
        self.assertIn("Content-Security-Policy", report)
        self.assertIn("default-src 'none'", report)
        self.assertNotIn("<script>", report)
