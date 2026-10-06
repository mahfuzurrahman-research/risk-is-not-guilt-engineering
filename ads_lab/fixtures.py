from __future__ import annotations

from html import escape

from .contracts import CONTEXTS, digest, json_bytes

SCENARIOS = (
    "benign_static", "benign_localization", "benign_ab", "benign_consent",
    "benign_tracking", "benign_geo", "benign_sso", "benign_shared_template",
    "benign_repaired_stale", "abuse_topic_cloaking", "abuse_credential_cloaking",
    "abuse_download_cloaking", "abuse_known_phishing", "abuse_js_reference",
    "abuse_delayed_feed",
)


def html_page(topic="clothing", variant="", *, form=None, download=None, js=None):
    texts = {
        "clothing": "Shop clothing and shirts. View the clothing collection.",
        "finance": "Bank finance and investment services. View your banking account.",
        "software": "Software application for productivity. View application details.",
        "toys": "Shop toys and games. View the toy collection.",
    }
    text = texts[topic]
    if variant == "spanish":
        text = "Comprar ropa y camisas. Ver nuestra ropa."
    elif variant == "ab":
        text += " Explore today's featured offers."
    elif variant == "geo":
        text += " Local delivery and regional prices available."
    elif variant == "consent":
        text = "Cookie preferences required before viewing this page."
    pieces = ["<!doctype html><html><head><title>Controlled destination fixture</title></head><body>",
              "<main><h1>" + escape(text) + "</h1>"]
    if form:
        pieces.append('<form action="' + escape(form, quote=True) + '"><label>Test account</label>'
                      '<input name="username"><input type="password" name="password">'
                      '<button>Continue</button></form>')
    if download:
        pieces.append('<a href="' + escape(download, quote=True) + '">Download test file</a>')
    if js:
        # Reference-only evidence. The lab never executes this script or visits its target.
        pieces.append('<script>window.location.assign("' + escape(js, quote=True) + '");</script>')
    pieces.append("<p>Controlled research fixture. No real advertiser or credential collection.</p></main></body></html>")
    return "".join(pieces)


def page_for(scenario: str, context: str, campaign: str) -> str:
    if scenario not in SCENARIOS or context not in CONTEXTS:
        raise ValueError("unknown fixture scenario or context")
    user = context != "reviewer"
    host = campaign + ".test"
    cohort = campaign.split("-")[0]
    if scenario == "abuse_topic_cloaking":
        return html_page("finance" if user else "clothing")
    if scenario == "abuse_credential_cloaking":
        return html_page("finance", form=f"https://collector-{cohort}.test/submit" if user else None)
    if scenario == "abuse_download_cloaking":
        return html_page("software", download=f"https://files-{host}/test.exe" if user else None)
    if scenario == "abuse_js_reference":
        return html_page("clothing", js=f"https://jump-{cohort}.test/unknown" if user else None)
    if scenario in {"abuse_known_phishing", "abuse_delayed_feed", "benign_repaired_stale"}:
        return html_page("finance")
    if scenario == "benign_localization":
        return html_page(variant="spanish" if context == "mobile" else "")
    if scenario == "benign_ab":
        return html_page(variant="ab" if context == "desktop" else "")
    if scenario == "benign_consent":
        return html_page(variant="consent" if context == "mobile" else "")
    if scenario == "benign_geo":
        return html_page(variant="geo" if context == "mobile" else "")
    if scenario == "benign_sso":
        return html_page("finance", form=f"https://identity-{cohort}.test/login")
    return html_page()


def make_snapshot(request_url: str, final_url: str, body: str, context: str, at: str,
                  intermediates=()) -> dict:
    urls = [request_url, *intermediates, final_url] if request_url != final_url else [request_url]
    hops = []
    for index, url in enumerate(urls):
        terminal = index == len(urls) - 1
        response_body = body if terminal else ""
        hops.append({"url": url, "status": 200 if terminal else 302,
                     "location": None if terminal else urls[index + 1],
                     "body": response_body, "body_sha256": digest(response_body)})
    return {"context": context, "captured_at": at, "request_url": request_url,
            "final_url": final_url, "hops": hops}


def generate_corpus(replicas=4) -> tuple[list[dict], list[dict], dict]:
    if type(replicas) is not int or not 1 <= replicas <= 20:
        raise ValueError("replicas must be a small positive integer")
    records, labels, indicators = [], [], []
    for split, prefix, at, label_at in (
        ("validation", "val", "2026-01-20T12:00:00Z", "2026-01-25T00:00:00Z"),
        ("holdout", "test", "2026-02-10T12:00:00Z", "2026-02-14T00:00:00Z"),
    ):
        for scenario_index, scenario in enumerate(SCENARIOS):
            for replica in range(replicas):
                campaign = f"{prefix}-campaign-{chr(97 + scenario_index)}-{chr(97 + replica)}"
                key = "observation-" + campaign
                request_url = f"https://{campaign}.test/landing"
                snapshots = []
                for context in CONTEXTS:
                    final_url = request_url
                    intermediates = ()
                    if scenario == "benign_tracking" and context != "reviewer":
                        intermediates = (f"https://tracker-{campaign}.test/first",
                                         f"https://tracker-{campaign}.test/second")
                        final_url = f"https://shop-{campaign}.test/landing"
                    body = page_for(scenario, context, campaign)
                    snapshots.append(make_snapshot(request_url, final_url, body, context, at, intermediates))
                topic = "finance" if scenario in {"abuse_credential_cloaking", "abuse_known_phishing",
                                                  "abuse_delayed_feed", "benign_repaired_stale", "benign_sso"} else "clothing"
                if scenario == "abuse_download_cloaking":
                    topic = "software"
                records.append({"observation_id": key, "campaign_id": campaign, "split": split,
                                "decision_at": at, "ad_claim": "Discover our " + topic + " services",
                                "ad_url": request_url, "snapshots": snapshots})
                available_at = label_at
                if scenario == "abuse_delayed_feed" and split == "holdout":
                    available_at = "2026-02-25T00:00:00Z"
                labels.append({"observation_id": key, "is_abuse": scenario.startswith("abuse_"),
                               "available_at": available_at, "scenario": scenario,
                               "label_source": "CONTROLLED_FIXTURE_GROUND_TRUTH"})
                if scenario in {"abuse_known_phishing", "abuse_delayed_feed", "benign_repaired_stale"}:
                    verified = "2026-01-01T00:00:00Z"
                    available = verified
                    expires = "2026-03-01T00:00:00Z"
                    if scenario == "abuse_delayed_feed":
                        verified = available = "2026-01-21T00:00:00Z" if split == "validation" else "2026-02-13T00:00:00Z"
                    elif scenario == "benign_repaired_stale":
                        expires = "2026-01-10T00:00:00Z"
                    indicators.append({"url": request_url, "threat_type": "PHISHING", "source_recorded_at": verified,
                                       "available_at": available, "expires_at": expires})
    indicators.sort(key=lambda row: row["url"])
    threat_snapshot = {"schema_version": 1, "source": "CONTROLLED_THREAT_FIXTURE",
                       "input_sha256": digest(json_bytes(indicators)),
                       "retrieved_at": "2026-01-01T00:00:00Z", "synthetic": True, "indicators": indicators}
    return records, labels, threat_snapshot
