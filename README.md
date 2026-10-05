# Risk Is Not Guilt — Research Engineering Demonstration

**Public engineering companion for _Risk Is Not Guilt: Predictive Anti-Corruption and the Constitutional Governance of Algorithmic Risk_.**

This repository demonstrates research/data-engineering techniques with **fully synthetic records**. It does **not** contain the manuscript, real procurement/sanction records, empirical results, private provenance, historical model outputs, or the complete scientific workflow.

## What this repository demonstrates

- Python data contracts and fail-fast validation
- SQLite relational warehouse construction
- normalized relational modeling and analytical marts
- Python/SQL parity checks
- relational and data-quality gates
- linkage-integrity checks
- prediction-readiness gates that **fail closed**
- temporal-integrity checks that **fail closed**
- deterministic JSON and Markdown reporting
- synthetic failure-path testing
- Docker-based reproducibility
- GitHub Actions continuous integration
- static public-safe dashboard generation

## Engineering flow

```text
Synthetic linkage records
          │
          ▼
Machine-readable input contract
          │
          ▼
Schema / domain validation
          │
          ▼
SQLite relational warehouse
          │
          ▼
Relational quality gates
          │
          ▼
Python / SQL parity
          │
          ▼
Analytics marts
          │
          ├───────────────┐
          ▼               ▼
Readiness gate      Temporal gate
          │               │
          └───────┬───────┘
                  ▼
        Deterministic audit report
                  │
                  ▼
           Static dashboard
                  │
                  ▼
          CI + Docker validation
```

## Public-safe design

The schema and records in this companion are independently fabricated. The repository demonstrates engineering patterns without exposing the private study's exact record semantics, identifiers, empirical counts, scientific results, or manuscript logic.

The readiness and temporal gates are demonstration controls. A `BLOCKED` or `NOT_READY` status is treated as a successful engineering outcome when required evidence is missing.

## Quick start

```bash
./run_public_demo.sh
```

Expected markers:

```text
PUBLIC_BOUNDARY_SCAN=PASS
CONTRACT_VALIDATION=PASS
RELATIONAL_QA=PASS
PYTHON_SQL_PARITY=PASS
READINESS_GATE=NOT_READY
TEMPORAL_GATE=BLOCKED_UNRESOLVED
DASHBOARD=PASS
PUBLIC_ENGINEERING_DEMO=PASS
```

## Repository map

```text
contracts/        machine-readable public-safe contracts
data/synthetic/   fabricated linkage records only
src/              Python validation, warehouse, gates and reporting
sql/              SQLite schema, marts and quality checks
tests/            unit, integration and failure-mode tests
dashboards/       static public-safe dashboard builder
docs/             architecture, reproducibility and capability notes
.github/          continuous-integration workflow
```

## Scientific boundary

This repository demonstrates **engineering capability only**. It does **not** establish corruption or wrongdoing, guilt or innocence, predictive validity, legal finality, causal effects, or any empirical finding from the private paper.

The full scientific repository remains private.

## Author

**Mahfuzur Rahman**

Copyright © Mahfuzur Rahman. All rights reserved.
