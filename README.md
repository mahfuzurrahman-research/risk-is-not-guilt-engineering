# Risk Is Not Guilt - Research Engineering Demonstration

**Public engineering companion for _Risk Is Not Guilt: Predictive Anti-Corruption and the Constitutional Governance of Algorithmic Risk_.**

Two executable modules demonstrate data engineering and ML risk analysis using fabricated records. The original linkage module validates a SQLite warehouse and fails closed when prediction readiness is unresolved. The additive ML module compares classifiers, scores anomalies, and builds a human-review queue on an independent advertising-integrity simulator.

This repository contains no real procurement/sanction records, manuscript, private provenance, historical scientific outputs, or Google Ads data. It demonstrates engineering capability; it does not establish wrongdoing, predictive validity on real fraud, or findings from the private paper.

## Run both modules

Requires Python 3.12. The linkage module uses the standard library. The ML dependencies are pinned to the recorded environment.

```bash
python3 -m pip install -r requirements-ml.txt
./run_all_demos.sh
```

Run either module separately with `./run_public_demo.sh` or `./run_ml_demo.sh`.

| Module | Implemented behavior | Evidence |
|---|---|---|
| Linkage engineering | Machine-readable contracts; SQLite schema, marts and QA; Python/SQL parity; readiness and temporal gates; JSON/Markdown/HTML reporting | [Original architecture](docs/architecture.md), `tests/` |
| Synthetic ML risk | Logistic-regression baseline and random-forest comparison; Isolation Forest; validation-selected threshold; historical label availability; label-free review queue | [ML design](docs/ml_risk_demo.md), `tests_ml/` |
| Reproducibility | Complete model/policy serialization; dependency/source/artifact hashes; success receipt; replay and failure checks | [Reproducibility](docs/reproducibility.md) |
| Automation | Two GitHub Actions workflows and separate Docker images | `.github/workflows/`, `Dockerfile`, `Dockerfile.ml` |

## ML risk and review controls

- Only the ten allowed numeric features enter the models; identifiers, timestamps, and labels are excluded.
- Missing values, non-finite values, out-of-domain rates/counts, duplicate keys, and unavailable features are rejected.
- Complete dates separate training, validation, and test. Outcomes not available before the next origin are purged.
- Validation selects the classifier and threshold. An unmet precision target disables classifier flags.
- The saved scoring policy must be available before each held-out decision.
- The queue admits the ceiling of 10% of test events, with deterministic event-ID ties, descriptive reasons, and `PENDING_REVIEW` status.
- Outcomes are excluded from scored events and queues. Retrospective evaluation is stored separately.
- Queue inclusion recommends human review and never authorizes an adverse action.

The classifier score is uncalibrated. The fixed classifier/anomaly mixture is a prioritization heuristic. Strong synthetic performance is not evidence of generalization to real actors, traffic, or commercial systems.

## Outputs and validation

`outputs/ml_demo/` contains generated data, label-free scored events and review queue, retrospective metrics, a saved model bundle, model card, manifest, and a success receipt. Generated artifacts are ignored by Git.

```bash
python3 scripts/verify_ml_artifacts.py
```

See the [validation record](docs/ml_validation_record.md) for the observed synthetic results and the [CV evidence guide](docs/cv_evidence.md) for supported wording.

The existing readiness and temporal gates retain `NOT_READY` / `BLOCKED_UNRESOLVED` as valid outcomes when evidence is insufficient. The full scientific repository remains private.

## Author

**Mahfuzur Rahman**

Copyright © Mahfuzur Rahman. All rights reserved.
