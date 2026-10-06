# Capability Matrix

| Capability | Public evidence |
|---|---|
| Python | contracts, profiling, pipeline, gates, reporting |
| SQL / SQLite | normalized schema, marts, quality checks |
| ETL | CSV → relational warehouse |
| Data quality | executable QA gates |
| Relational modeling | entities, linkage records, ingestion runs |
| Python/SQL parity | independent profile comparison |
| Failure handling | fail-fast contracts and fail-closed gates |
| Temporal validation | synthetic availability/event-date gate |
| Reporting | deterministic JSON + Markdown |
| Dashboard | generated static HTML |
| Testing | unit, integration, negative/failure-mode tests |
| CI | GitHub Actions |
| Containerization | Docker |

| ML capability | Public evidence |
|---|---|
| Supervised classification | Logistic baseline and random-forest comparison on fabricated outcomes |
| Anomaly detection | Training-only Isolation Forest with frozen normalization |
| Temporal validity | Feature availability, delayed-outcome purge, release-time admission |
| Model selection | Validation-only classifier and threshold selection; separate future test |
| Review prioritization | Label-free capacity-bounded queue, stable ties, reasons, human-review status |
| Retrospective evaluation | ID-aligned metrics, prior baseline, fixed-capacity queue comparisons |
| Model persistence | Complete model/policy bundle and exact replay check |
| Artifact integrity | Dependency/source hashes, success receipt, SHA-256 verifier |
| Failure handling | Invalid features/keys, future availability, unmet threshold target, interrupted build, writer lock |

| Ads investigation capability | Public evidence |
|---|---|
| HTTP evidence capture | Owned server, bounded responses, explicit redirect chains, body hashes, three contexts |
| Destination signals | Product mismatch, contextual forms/downloads, legitimate variation controls |
| Threat metadata | PhishTank/URLhaus local import, retrieval-time admission, expiry, unknown status |
| Campaign association | Shared endpoints/references/templates with unresolved actor identity |
| Investigation cases | Capacity limits, evidence reasons, policy references and alternative explanations |
| Incident exercise | Controlled root-cause hypothesis, patched evidence and exact score replay |
| Independent validation | Thirty-five SQLite gates plus raw-input/schema/table reconstruction |
| Reports and automation | JSON/Markdown/HTML evidence, dedicated CI and standard-library Docker image |
