# ML Validation Record

Recorded on 6 October 2026 with Python 3.12 and the exact versions in requirements-ml.txt.

## Scope

The previous public baseline demonstrated linkage QA and readiness gates, with 10 tests. This upgrade adds a separate fabricated-data ML and review-prioritization module. It does not change the private study's scientific findings.

## Local validation

The combined runner passes the 10 original tests and 32 ML tests. Checks include invalid input domains, future availability, delayed-label purging, target exclusion, feature ordering, persistence replay, queue capacity/ties, unmet precision targets, ID-aligned evaluation, build failure, writer locking, and artifact corruption.

The source-only public boundary scan and complete artifact receipt verification pass. The ML CI workflow runs both modules and builds/runs the ML Docker image; actual container execution must be checked against the corresponding Actions run.

## Default synthetic run

| Observation | Result |
|---|---:|
| Fabricated events | 6,000 |
| Training events after availability purge | 3,380 |
| Validation events after availability purge | 991 |
| Future held-out events | 1,227 |
| Removed unavailable outcomes | 402 |
| Selected classifier | Logistic regression |
| Test average precision | 0.839207 |
| Test train-prior baseline average precision | 0.126324 |
| Test ROC AUC | 0.940948 |
| Test threshold precision | 0.893082 |
| Test threshold recall | 0.916129 |
| Queue capacity | 123 |
| Combined queue precision at capacity | 0.902439 |
| Classifier-only queue precision at capacity | 0.902439 |
| Anomaly-only queue precision at capacity | 0.894309 |
| Fixed-seed random queue precision at capacity | 0.121951 |

The combined ranking has the same precision at capacity as classifier-only ranking. No incremental detection improvement is demonstrated by adding the anomaly layer in this run.

These values describe the default simulator and pinned environment. They do not estimate real-world advertising-fraud performance or establish calibration, production readiness, scientific identification, or employer-specific experience.
