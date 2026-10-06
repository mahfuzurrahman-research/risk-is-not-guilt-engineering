from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .contracts import CONTEXTS, MAX_BODY_BYTES, MAX_HOPS, canonical_url, digest, utc_string
from .fixtures import SCENARIOS, page_for


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _allow_local(url: str, allowed_origin: str) -> str:
    url = canonical_url(url)
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if parts.scheme != "http" or parts.hostname != "127.0.0.1" or origin != allowed_origin:
        raise ValueError("capture is restricted to the explicitly owned loopback server")
    return url


def capture(url: str, context: str, allowed_origin: str, *, at: str | None = None) -> dict:
    if context not in CONTEXTS:
        raise ValueError("unknown capture context")
    request_url = _allow_local(url, allowed_origin)
    current, seen, hops = request_url, set(), []
    # Ignore environment proxies and never follow an unchecked redirect.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    for _ in range(MAX_HOPS):
        if current in seen:
            raise ValueError("redirect loop")
        seen.add(current)
        request = Request(current, headers={"User-Agent": "AdsInvestigationLab/1.0 (controlled fixture)",
                                           "X-Lab-Context": context, "Accept-Encoding": "identity"})
        try:
            response = opener.open(request, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.status
            raw = response.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                raise ValueError("body exceeds capture limit")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("compressed capture is not supported")
            try:
                body = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("capture requires UTF-8") from exc
            location = response.headers.get("Location")
            if status in {301, 302, 303, 307, 308}:
                if not location:
                    raise ValueError("redirect is missing Location")
                location = _allow_local(urljoin(current, location), allowed_origin)
            elif status == 200:
                if response.headers.get_content_type() != "text/html":
                    raise ValueError("terminal response is not HTML")
                location = None
            else:
                raise ValueError(f"capture failed with HTTP status {status}")
            hops.append({"url": current, "status": status, "location": location,
                         "body": body, "body_sha256": digest(raw)})
        if status == 200:
            return {"context": context, "captured_at": at or utc_string(datetime.now(timezone.utc)),
                    "request_url": request_url, "final_url": current, "hops": hops}
        current = location
    raise ValueError("redirect chain exceeds capture limit")


@contextmanager
def fixture_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parts = urlsplit(self.path).path.strip("/").split("/")
            context = self.headers.get("X-Lab-Context", "desktop")
            if len(parts) != 2 or parts[0] not in {"visit", "track", "destination"} or parts[1] not in SCENARIOS or context not in CONTEXTS:
                self.send_error(404)
                return
            stage, scenario = parts
            if scenario == "benign_tracking" and stage in {"visit", "track"} and context != "reviewer":
                self.send_response(302)
                next_stage = "track" if stage == "visit" else "destination"
                self.send_header("Location", f"/{next_stage}/{scenario}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            body = page_for(scenario, context, "owned-capture").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
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


def capture_demo() -> dict:
    records = []
    with fixture_server() as origin:
        for index, scenario in enumerate(("abuse_topic_cloaking", "abuse_credential_cloaking",
                                          "benign_localization", "benign_tracking", "abuse_js_reference")):
            url = f"{origin}/visit/{scenario}"
            snapshots = [capture(url, context, origin) for context in CONTEXTS]
            records.append({"observation_id": f"owned-capture-{index}", "campaign_id": f"owned-campaign-{index}",
                            "split": "holdout", "decision_at": utc_string(datetime.now(timezone.utc)),
                            "ad_claim": "Bank finance services" if "credential" in scenario else "Shop clothing and shirts",
                            "ad_url": url, "snapshots": snapshots})
    return {"source": "OWNED_LOOPBACK_HTTP_SERVER", "synthetic_content": True,
            "javascript_executed": False, "observations": records}
