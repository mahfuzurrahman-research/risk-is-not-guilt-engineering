import threading
import unittest
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ads_lab.capture import capture, capture_demo, fixture_server
from ads_lab.contracts import digest, validate_labels
from ads_lab.detection import choose_policy, score_record
from ads_lab.fixtures import generate_corpus
from ads_lab.inspection import inspect_captures, verify_inspection


@contextmanager
def error_server(mode):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if mode in {"external", "loop", "missing_location"}:
                self.send_response(302)
                if mode != "missing_location":
                    self.send_header("Location", "http://outside.test/" if mode == "external" else self.path)
                self.end_headers()
            else:
                self.send_response(200 if mode != "server_error" else 500)
                self.send_header("Content-Type", "application/octet-stream" if mode == "non_html" else "text/html")
                self.end_headers()
                body = b"x" * (129 * 1024) if mode == "oversize" else b"\xff" if mode == "non_utf8" else b"<p>fixture</p>"
                self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TestOwnedCapture(unittest.TestCase):
    def test_http_capture_records_real_redirect_hops_and_hashes(self):
        with fixture_server() as origin:
            result = capture(origin + "/visit/benign_tracking", "mobile", origin)
        self.assertEqual([h["status"] for h in result["hops"]], [302, 302, 200])
        self.assertEqual(result["hops"][-1]["body_sha256"], digest(result["hops"][-1]["body"]))

    def test_distinct_contexts_capture_distinct_topic_evidence(self):
        with fixture_server() as origin:
            url = origin + "/visit/abuse_topic_cloaking"
            reviewer = capture(url, "reviewer", origin)
            desktop = capture(url, "desktop", origin)
        self.assertIn("clothing", reviewer["hops"][-1]["body"])
        self.assertIn("finance", desktop["hops"][-1]["body"])

    def test_external_redirect_is_rejected_before_external_request(self):
        with error_server("external") as origin:
            with self.assertRaisesRegex(ValueError, "owned loopback"):
                capture(origin + "/", "desktop", origin)

    def test_loop_and_missing_location_rejected(self):
        for mode, pattern in (("loop", "redirect loop"), ("missing_location", "missing Location")):
            with self.subTest(mode=mode), error_server(mode) as origin:
                with self.assertRaisesRegex(ValueError, pattern):
                    capture(origin + "/", "desktop", origin)

    def test_bad_status_encoding_content_type_and_size_rejected(self):
        for mode in ("server_error", "non_utf8", "non_html", "oversize"):
            with self.subTest(mode=mode), error_server(mode) as origin:
                with self.assertRaises(ValueError):
                    capture(origin + "/", "desktop", origin)

    def test_unowned_origins_and_unknown_contexts_rejected(self):
        for url in ("http://outside.test/", "http://127.0.0.2:1234/", "file:///tmp/page"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                capture(url, "desktop", "http://127.0.0.1:1234")
        with self.assertRaises(ValueError):
            capture("http://127.0.0.1:1234/", "unknown", "http://127.0.0.1:1234")

    def test_live_capture_inspection_and_replay(self):
        package = capture_demo()
        records, labels, threats = generate_corpus(1)
        policy = choose_policy([score_record(r, threats) for r in records], validate_labels(labels, records))
        inspection = inspect_captures(package, threats, policy)
        self.assertEqual(len(inspection["scored_observations"]), 5)
        self.assertEqual(len(inspection["investigation_queue"]), 2)
        self.assertEqual(verify_inspection(inspection)["status"], "PASS")
        changed = deepcopy(inspection)
        changed["investigation_queue"][0]["risk_score"] += 1
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            verify_inspection(changed)

    def test_browser_execution_claim_is_rejected(self):
        package = {"source": "OWNED_LOOPBACK_HTTP_SERVER", "synthetic_content": True,
                   "javascript_executed": True, "observations": []}
        with self.assertRaisesRegex(ValueError, "browser execution"):
            inspect_captures(package, {}, {})
