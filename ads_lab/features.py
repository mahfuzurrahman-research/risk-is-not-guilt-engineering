from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .contracts import canonical_url, digest, host_of

# Small, inspectable lexicon. This is a controlled-fixture extractor, not a
# multilingual semantic model or an authoritative Ads policy classifier.
TOPICS = {
    "clothing": {"clothing", "shirts", "shirt", "ropa", "camisas", "fashion"},
    "finance": {"bank", "banking", "finance", "investment", "investments", "banco"},
    "software": {"software", "application", "productivity", "aplicacion"},
    "toys": {"toys", "toy", "juguetes"},
}
EXECUTABLE_SUFFIXES = (".exe", ".msi", ".ps1", ".sh", ".apk")
JS_REFERENCE = re.compile(
    r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]|"
    r"(?:window\.)?location\.(?:assign|replace)\s*\(\s*['\"]([^'\"]+)['\"]", re.I)


def topic_tags(text: str) -> list[str]:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    return sorted(name for name, words in TOPICS.items() if tokens & words)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.text = []
        self.tags = []
        self.form_actions = []
        self.password = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
        if self.hidden_depth:
            return
        self.tags.append(tag)
        if tag == "form":
            self.form_actions.append(attrs.get("action", ""))
        elif tag == "input" and attrs.get("type", "").lower() == "password":
            self.password = True
        elif tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            self.text.append(data)


def extract_page(body: str, final_url: str) -> dict:
    parser = PageParser()
    parser.feed(body)
    text = " ".join(" ".join(parser.text).split())
    def resolve(values):
        result = set()
        for value in values:
            try:
                result.add(canonical_url(urljoin(final_url, value)))
            except ValueError:
                # Non-network links such as mailto: are not URL threat evidence.
                continue
        return sorted(result)
    actions = resolve(parser.form_actions)
    links = resolve(parser.links)
    js_refs = resolve([a or b for a, b in JS_REFERENCE.findall(body)])
    from urllib.parse import urlsplit
    downloads = [url for url in links if urlsplit(url).path.lower().endswith(EXECUTABLE_SUFFIXES)]
    return {
        "topic_tags": topic_tags(text),
        "extracted_text": text,
        "extracted_text_sha256": digest(text.lower()),
        "template_sha256": digest("|".join(parser.tags)),
        "form_actions": actions,
        "password_input": parser.password,
        "external_form": any(host_of(url) != host_of(final_url) for url in actions),
        "download_links": downloads,
        "static_js_redirect_references": js_refs,
        "static_js_reference_external": any(host_of(url) != host_of(final_url) for url in js_refs),
        "javascript_executed": False,
    }


def primitive_features(record: dict) -> dict:
    pages = {}
    candidates = set()
    for snapshot in record["snapshots"]:
        page = extract_page(snapshot["hops"][-1]["body"], snapshot["final_url"])
        page.update({"final_url": canonical_url(snapshot["final_url"]),
                     "final_host": host_of(snapshot["final_url"]),
                     "hop_count": len(snapshot["hops"]),
                     "body_sha256": snapshot["hops"][-1]["body_sha256"]})
        pages[snapshot["context"]] = page
        candidates.update(canonical_url(hop["url"]) for hop in snapshot["hops"])
        candidates.update(page["form_actions"] + page["download_links"] + page["static_js_redirect_references"])
    return {"observation_id": record["observation_id"], "campaign_id": record["campaign_id"],
            "split": record["split"], "decision_at": record["decision_at"],
            "ad_topics": topic_tags(record["ad_claim"]), "pages": pages,
            "candidate_urls": sorted(candidates)}
