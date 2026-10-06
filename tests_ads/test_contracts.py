import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from ads_lab.contracts import canonical_url, digest, read_json, timestamp, validate_corpus, validate_labels
from ads_lab.fixtures import generate_corpus


class TestEvidenceContracts(unittest.TestCase):
    def setUp(self):
        self.records, self.labels, _ = generate_corpus(1)

    def rejects(self, mutate, pattern):
        changed = deepcopy(self.records)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, pattern):
            validate_corpus(changed)

    def test_default_corpus_and_label_alignment(self):
        validate_corpus(self.records)
        self.assertEqual(len(validate_labels(self.labels, self.records)), len(self.records))

    def test_labels_cannot_enter_capture_contract(self):
        self.rejects(lambda rows: rows[0].update(is_abuse=True), "label-free")

    def test_duplicate_observations_rejected(self):
        self.rejects(lambda rows: rows.append(deepcopy(rows[0])), "duplicate observation")

    def test_missing_and_duplicate_context_rejected(self):
        self.rejects(lambda rows: rows[0]["snapshots"].pop(), "per required context")
        self.rejects(lambda rows: rows[0]["snapshots"][0].update(context="mobile"), "per required context")

    def test_corrupt_body_hash_rejected(self):
        self.rejects(lambda rows: rows[0]["snapshots"][0]["hops"][-1].update(body="changed"), "body hash")

    def test_future_or_old_capture_rejected(self):
        self.rejects(lambda rows: rows[0]["snapshots"][0].update(captured_at="2026-01-20T12:01:00Z"), "unavailable")
        self.rejects(lambda rows: rows[0]["snapshots"][0].update(captured_at="2026-01-20T11:40:00Z"), "comparison window")

    def test_contexts_must_share_entry_url(self):
        self.rejects(lambda rows: rows[0]["snapshots"][0].update(request_url="https://other.test/"), "same ad URL")

    def test_redirect_chain_and_terminal_status_rejected(self):
        index = next(i for i, row in enumerate(self.records) if len(row["snapshots"][1]["hops"]) > 1)
        self.rejects(lambda rows: rows[index]["snapshots"][1]["hops"][0].update(location="https://unrelated.test/"), "discontinuous")
        self.rejects(lambda rows: rows[0]["snapshots"][0]["hops"][-1].update(status=404), "successful HTML")

    def test_campaign_and_domain_split_leakage_rejected(self):
        holdout = next(i for i, row in enumerate(self.records) if row["split"] == "holdout")
        self.rejects(lambda rows: rows[holdout].update(campaign_id=rows[0]["campaign_id"]), "campaign leakage")
        def share_domain(rows):
            url = rows[0]["ad_url"]
            row = rows[holdout]
            row["ad_url"] = url
            for snapshot in row["snapshots"]:
                snapshot.update(request_url=url, final_url=url)
                snapshot["hops"][0]["url"] = url
        self.rejects(share_domain, "domain leakage")

    def test_timestamps_are_sql_comparable_whole_seconds(self):
        for value in ("2026-01-20", "2026-01-20T12:00:00", "2026-01-20T12:00:00.5Z", "20260120T120000Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                timestamp(value)

    def test_url_normalization_preserves_evidence_distinctions(self):
        self.assertEqual(canonical_url("HTTPS://Example.TEST:443/Path?b=2&a=1#fragment"), "https://example.test/Path?b=2&a=1")
        self.assertNotEqual(canonical_url("https://x.test/a?b=1"), canonical_url("https://x.test/a?b=2"))
        for url in ("file:///etc/passwd", "https://user:password@x.test/", "https://x.test/ bad", "https://x.test:bad/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url)

    def test_labels_require_exact_ids_and_boolean_ground_truth(self):
        for mutate in (lambda rows: rows.pop(), lambda rows: rows.append(deepcopy(rows[0])),
                       lambda rows: rows[0].update(is_abuse=1)):
            labels = deepcopy(self.labels)
            mutate(labels)
            with self.assertRaises(ValueError):
                validate_labels(labels, self.records)

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    read_json(path)

    def test_oversize_evidence_rejected(self):
        def oversize(rows):
            hop = rows[0]["snapshots"][0]["hops"][0]
            hop["body"] = "x" * (129 * 1024)
            hop["body_sha256"] = digest(hop["body"])
        self.rejects(oversize, "body exceeds")
