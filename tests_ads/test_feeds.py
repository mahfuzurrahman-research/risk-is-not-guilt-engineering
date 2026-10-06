import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from ads_lab.contracts import write_json
from ads_lab.feeds import import_feed, lookup_urls, validate_threat_snapshot
from ads_lab.fixtures import generate_corpus


class TestDatedThreatMetadata(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "feed.json"

    def tearDown(self):
        self.temporary.cleanup()

    def phish(self, **changes):
        row = {"url": "https://example.test/login", "verified": "yes", "online": "yes",
               "verification_time": "2026-01-02T00:00:00+00:00"}
        row.update(changes)
        return row

    def test_phishtank_filters_unverified_and_offline_records(self):
        write_json(self.path, [self.phish(), self.phish(url="https://unverified.test/", verified="no"),
                               self.phish(url="https://offline.test/", online="no")])
        result = import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
        self.assertEqual(len(result["indicators"]), 1)
        self.assertFalse(result["synthetic"])
        self.assertEqual(result["indicators"][0]["available_at"], "2026-01-03T00:00:00Z")

    def test_retrieval_time_prevents_historical_backdating(self):
        write_json(self.path, [self.phish()])
        result = import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
        url = result["indicators"][0]["url"]
        before = lookup_urls([url], "2026-01-02T12:00:00Z", result)
        self.assertEqual(before["status"], "UNKNOWN_NO_CURRENT_MATCH")
        self.assertEqual(before["excluded"][0]["reason"], "NOT_YET_AVAILABLE")

    def test_exact_availability_and_expiry_boundaries(self):
        write_json(self.path, [self.phish()])
        result = import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
        url = result["indicators"][0]["url"]
        self.assertEqual(len(lookup_urls([url], "2026-01-03T00:00:00Z", result)["matches"]), 1)
        self.assertEqual(lookup_urls([url], "2026-01-04T00:00:00Z", result)["excluded"][0]["reason"], "EXPIRED_INDICATOR")

    def test_unknown_url_is_not_benign_ground_truth(self):
        _, _, result = generate_corpus(1)
        lookup = lookup_urls(["https://unlisted.test/"], "2026-02-10T12:00:00Z", result)
        self.assertEqual(lookup["status"], "UNKNOWN_NO_CURRENT_MATCH")
        self.assertNotIn("is_safe", lookup)

    def test_urlhaus_comment_header_and_offline_filter(self):
        self.path.write_text('# generated metadata\n# id,dateadded,url,url_status,threat,tags\n'
                             '1,2026-01-02 00:00:00,https://example.test/test.exe,online,malware_download,test\n'
                             '2,2026-01-02 00:00:00,https://offline.test/test.exe,offline,malware_download,test\n')
        result = import_feed(self.path, "urlhaus", "2026-01-03T00:00:00Z")
        self.assertEqual(len(result["indicators"]), 1)
        self.assertEqual(result["indicators"][0]["threat_type"], "MALWARE_URL")
        self.assertEqual(result["indicators"][0]["source_recorded_at"], "2026-01-02T00:00:00Z")

    def test_future_source_times_and_invalid_ttl_rejected(self):
        write_json(self.path, [self.phish(verification_time="2026-01-05T00:00:00+00:00")])
        with self.assertRaisesRegex(ValueError, "after retrieval"):
            import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
        for ttl in (0, -1, True, 200):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z", ttl)

    def test_duplicate_indicator_and_false_source_claim_rejected(self):
        _, _, snapshot = generate_corpus(1)
        changed = deepcopy(snapshot)
        changed["indicators"].append(deepcopy(changed["indicators"][0]))
        from ads_lab.contracts import digest, json_bytes
        changed["input_sha256"] = digest(json_bytes(changed["indicators"]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_threat_snapshot(changed)
        changed = deepcopy(snapshot)
        changed["source"] = "PHISHTANK_PUBLIC_METADATA"
        with self.assertRaisesRegex(ValueError, "synthetic declaration"):
            validate_threat_snapshot(changed)

    def test_path_query_and_case_are_not_collapsed_by_feed_matching(self):
        write_json(self.path, [self.phish(url="https://example.test/Path?token=a")])
        result = import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
        for url in ("https://example.test/path?token=a", "https://example.test/Path?token=b"):
                self.assertFalse(lookup_urls([url], "2026-01-03T12:00:00Z", result)["matches"])

    def test_malformed_csv_and_json_headers_rejected(self):
        self.path.write_text('url,status\nhttps://example.test/,online\n')
        with self.assertRaisesRegex(ValueError, "CSV header"):
            import_feed(self.path, "urlhaus", "2026-01-03T00:00:00Z")
        self.path.write_text('[{"url":"https://a.test/","url":"https://b.test/"}]')
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            import_feed(self.path, "phishtank", "2026-01-03T00:00:00Z")
