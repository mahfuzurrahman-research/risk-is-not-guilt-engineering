# Ads Lab Validation Record

Recorded on 6 October 2026. This is an additive engineering extension to the synthetic ML companion; it does not modify the private study.

## Assessment baseline

The preceding repository demonstrated fitted classification, anomaly ranking and a synthetic review queue. It did not capture ad destinations, distinguish legitimate page variation from contextual product changes, construct destination investigation cases or replay a simulated incident. Those specific engineering behaviors are now implemented. Real advertiser data, production effectiveness and incident-response employment remain unproven.

## Controlled benchmark

| Observation | Result |
|---|---:|
| Scenario designs | 15 |
| ID/domain replicas per design per split | 4 |
| Observations across both splits | 120 |
| Context snapshots | 360 |
| Held-out observations | 60 |
| Mature held-out outcomes | 56 |
| Pending held-out outcomes | 4 |
| Validation-selected threshold | 3 |
| Held-out true-positive flags | 16 |
| Held-out false-positive flags | 0 |
| Held-out true negatives | 36 |
| Held-out false negatives | 4 |
| Recall on mature labels | 0.80 |
| Review queue capacity / selected | 12 / 12 |
| Review queue recall on mature labels | 0.60 |
| Flagged cases deferred by capacity | 4 |
| Independent SQLite gates | 35 |
| Follow-up mature outcomes | 60 |
| Follow-up positive cases / flagged | 24 / 16 |
| Follow-up false negatives | 8 |
| Follow-up flag recall | Two-thirds |
| Follow-up queue recall | 0.50 |

All replicas reuse a finite set of scenario designs. These are deterministic test results, not sampling estimates or evidence of commercial fraud-detection accuracy. New domain/campaign IDs do not establish generalization to new attack techniques.

The any-content/destination-change baseline has 20 benign false positives and four false negatives on the same mature holdout subset. Indicator-only matching detects four positive cases and misses sixteen. The frozen lab policy avoids the baseline's benign flags on these fixtures while retaining four static-JavaScript-reference misses. It does not execute the scripts or manufacture evidence of their runtime destinations.

Four delayed-feed cases have neither an available indicator at the original decision nor a mature outcome at the initial evaluation cutoff. They remain unknown/pending at that cutoff. After their labels mature, replay of the same original decisions reveals eight total false negatives and flag recall of two-thirds. Later indicators are not inserted into earlier decisions. The smaller review capacity defers four download-change candidates; they are reported rather than silently counted as handled. Follow-up queue recall is one-half.

## Capture, replay and failure checks

The owned HTTP capture exercise records five observations in three contexts, including a real local redirect chain. Inspection queues the two controlled topic/credential-change cases and reconstructs their saved evidence. It provides no unlabeled-traffic precision or recall estimate.

Automated checks cover benign variation, signal extraction, off-origin redirects, loops, bad statuses/encoding/content types, body limits, malformed feeds, future/expired indicators, unavailable labels, holdout independence in threshold selection, queue capacity/ties, unresolved attribution, simulated repair, repeated artifact hashes, source/raw-evidence replay, independent SQL corruption detection, writer locking, staged publication rollback and output ownership.

Local validation passes 10 original linkage tests, 32 existing ML tests and 62 Ads lab tests: 104 total. The combined `./run_all_demos.sh` command passes all three modules. Source-only public-boundary scans, raw-capture inspection replay, full benchmark replay and all 35 SQL gates pass.

Hosted CI results are recorded separately against the tested commit. Docker definitions and Actions checks are executable paths; successful container execution is claimed only when observed on the corresponding hosted run.
