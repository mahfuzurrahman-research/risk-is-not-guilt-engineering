# Ads Landing-Page Abuse Investigation Lab

## Purpose and evidence

This extension adds domain-specific investigation work to the existing ML companion: collect destination evidence, identify interpretable signals, organize associations, prioritize verification, and replay a controlled incident. It is a standard-library Python/SQLite application. It supplies no real Google Ads records, advertiser identity, payment/account information, production incident history or enforcement authority.

Policy references reviewed on 6 October 2026:

- [Google Ads: Circumventing systems](https://support.google.com/adspolicy/answer/15938075?hl=en). Content variation and redirects alone do not establish cloaking; legitimate localization and appropriate tracking are allowed.
- [PhishTank developer documentation](https://phishtank.org/developer_info.php). The downloadable JSON supplies online, community-verified phishing metadata. Automated downloads require observing its key/rate requirements.
- [URLhaus community API](https://urlhaus.abuse.ch/api/). CSV malware-URL exports require an Auth-Key. Date added is a source recording time, not a Google policy determination.

These references inform the lab's scenarios and interpretation. Its scores are not Google's policy rules or calibrated fraud probabilities.

## Architecture

`ads_lab/fixtures.py` creates raw ad claims and three context captures per observation. Outcomes and scenario names are stored separately in `labels.json`; the detector and queue never receive them.

`capture.py` also performs real bounded HTTP requests against a temporary owned loopback server. It records each status/Location/body hash and checks each redirect before following it. The context header is a local test control; it does not impersonate a Google crawler. It rejects off-origin redirects, loops, unsupported encodings/content types, oversize bodies and unsuccessful terminal responses. No external destination or executable is fetched.

`features.py` parses recorded HTML text, topic tokens, forms, password inputs, download links, DOM skeletons and literal JavaScript redirect references. It excludes script/style/noscript text. This is static parsing: it does not compute CSS visibility, execute JavaScript, render a browser or establish the runtime behavior of obfuscated code. Unresolved content is recorded rather than certified safe.

`feeds.py` matches exact canonical URLs against dated indicator snapshots. Scheme/host/default-port/fragment normalization preserves path case, query values and order. An indicator must be locally available at the decision and unexpired. A missing, future or expired match remains unknown.

`detection.py` derives signals without accessing outcomes. The following fixed, inspectable weights are a review heuristic:

| Signal | Weight | Interpretation |
|---|---:|---|
| Product-topic divergence between reviewer/user contexts | 4 | Investigate comparable product evidence |
| Ad-topic/user-content mismatch | 3 | Check that the promoted product remains the same |
| Context-specific external password form | 3 | Verify who receives credentials; benign SSO is a control |
| Context-specific executable download link | 3 | Verify destination behavior; file type is not a malware verdict |
| Current known threat indicator | 6 | Record source and availability; it is not an Ads label |
| Different destination host | 1 | Weak evidence; legitimate tracking can change the host |
| Longer redirect chain | 1 | Weak evidence; benign tracking is included |
| External static JavaScript redirect reference | 1 | Reference only; execution is unobserved |
| External form | 1 | Weak evidence; legitimate identity providers are included |

Weights are fixed before evaluation. Only mature validation labels select a threshold under a minimum validation precision constraint. Failure to meet that constraint disables review flags. The policy is frozen before held-out decisions. All simulation dates are fixture clock values, not evidence that this software or a policy existed on those historical dates.

`investigation.py` builds a capacity-bounded queue of held-out flags with deterministic score/ID ties. Each entry includes evidence hashes, reasons, a pending-review status and no automatic adverse action. Case reports include context comparisons, an applicable policy reference, benign alternative explanations and verification steps.

Campaign links use shared final URLs, form endpoints, static redirect references and DOM skeletons. A shared template or identity service is compatible with unrelated legitimate businesses. All links are evidence associations; none establishes actor identity, an organized fraud ring or wrongdoing. Graph structure does not add to the score.

Incident replay selects a topic-divergent controlled case, records a root-cause hypothesis, constructs a consistent-product repair and re-scores its exact patched evidence. It is a counterfactual fixture exercise; no actual incident, deployment, measured response latency or remediation outcome is claimed.

## Evaluation and independent reconstruction

There are 15 scenario designs and four ID/domain replicas per split. Repetition exercises indexing, ties and shared-resource links; it is not 120 independent attack examples. Validation and holdout use separate campaign IDs and destination domains. The same scenario families and topic lexicon appear in both splits, so generalization remains within the designed fixtures.

Labels mature separately from detection. Pending labels are excluded from confusion metrics and never treated as benign. The report compares the frozen policy with an any-content/destination-change baseline and a current-indicator-only baseline. It reports false positives, false negatives, review capacity loss and scenario results without extrapolating to production traffic.

`sql/ads_abuse_validation.sql` independently reconstructs every signal, score, flag, ordered queue and matured-label confusion table from parsed capture primitives and dated indicators. It does not consume the Python signal values to calculate its expected values. Thirty-five reconciliation gates check the complete inventories, temporal admission, split separation, queue capacity/order/status and both initial/follow-up metric counts.

The label-maturity follow-up evaluates the same original decisions after delayed labels arrive. It does not re-score observations with later indicators, reselect thresholds or change the original queue. In the default fixture run, flag recall falls from 0.80 on initially mature outcomes to two-thirds when all labels mature; queue recall falls from 0.60 to 0.50. This exposes the limitation of a maturity-conditioned headline metric.

Replay re-parses raw HTML and recomputes the threshold, scores, links, queue, cases, incident exercise and evaluation. It rebuilds a fresh warehouse and compares all schema objects and table rows with the saved database. SHA-256 receipts detect changed artifacts and source; replay also rejects corrupted decisions even if their artifact hashes were rewritten. Hashes prove consistency, not the authenticity of self-supplied evidence.

Builds use a writer lock and staging directory. A failed build preserves the last completed run; a failed publication restores it. This rollback is not a claim that directory replacement is continuously available during the brief publication transition. Generated receipts are written after all required outputs and verified before publication. Extra files, symlinks and output directories belonging to other workflows are rejected.

## Commands

Python 3.12 is required. The lab needs no third-party dependencies:

```bash
./run_ads_lab.sh
python3 -m ads_lab run --capacity 12 --output outputs/ads_lab
python3 -m ads_lab verify --output outputs/ads_lab
python3 -m ads_lab capture-demo --output outputs/ads_capture.json
python3 -m ads_lab inspect --capture outputs/ads_capture.json
python3 -m ads_lab verify-inspection --input outputs/ads_inspection.json
```

The last two commands inspect real HTTP captures of owned synthetic pages. They store no ground-truth performance metrics. A captured package and its frozen policy are included in the saved inspection so decisions can be independently replayed.

For optional public metadata, download an export according to its provider's instructions and retain the actual retrieval time. `data/threat_feeds/` is ignored by Git. Replace the timestamp below with that retrieval time:

```bash
python3 -m ads_lab import-feed --format phishtank \
  --input data/threat_feeds/online-valid.json \
  --retrieved-at 2026-10-06T12:00:00Z \
  --output outputs/phishtank_snapshot.json
python3 -m ads_lab import-feed --format urlhaus \
  --input data/threat_feeds/recent.csv \
  --retrieved-at 2026-10-06T12:00:00Z \
  --output outputs/urlhaus_snapshot.json
python3 -m ads_lab inspect --capture outputs/ads_capture.json \
  --threat-snapshot outputs/phishtank_snapshot.json \
  --output outputs/ads_public_metadata_inspection.json
```

Imported indicators cannot be backdated to their source verification/date-added times: local availability begins at retrieval. The default import TTL is 24 hours, with an explicit one-hour to one-week option. This is a lab freshness rule, not a provider guarantee. PhishTank and URLhaus adapters are tested with marked fixture inputs; this validation record does not claim a public feed was downloaded or evaluated.

## Output inventory

`outputs/ads_lab/` contains raw label-free captures, separate labels, the indicator snapshot, frozen policy, scored observations, campaign links, queue, Markdown cases, JSON evaluation, counterfactual incident, SQLite warehouse, SQL check results, HTML report, source manifest and success receipt. Owned HTTP captures and replayable inspections are adjacent JSON files. All generated outputs are ignored by Git and may be retained as CI artifacts.

## Claim boundary

Supported: implemented and tested controlled ad-destination investigations, time-aware indicator handling, evidence-based review, static HTML analysis, campaign association analysis and replayable simulated incident investigation.

Unsupported: production anti-abuse effectiveness, real Google Ads enforcement, actor attribution, malware reverse-engineering expertise, live incident response experience, general multilingual cloaking detection or independent scientific findings from the private study.
