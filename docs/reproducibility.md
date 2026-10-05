# Reproducibility

Requires Python 3.12.

```bash
python3 -m pip install -r requirements-ml.txt
./run_all_demos.sh
```

The original linkage module uses Python's standard library and SQLite. The ML module uses exact dependency versions from `requirements-ml.txt`.

## Containers

```bash
docker build -t risk-is-not-guilt-engineering .
docker run --rm risk-is-not-guilt-engineering
docker build -f Dockerfile.ml -t risk-is-not-guilt-ml-demo .
docker run --rm risk-is-not-guilt-ml-demo
```

## ML artifacts

After `./run_ml_demo.sh`, verify generated files:

```bash
python3 scripts/verify_ml_artifacts.py
```

`outputs/ml_demo/model_manifest.json` records model/threshold identity, feature order, availability/release timing, reason cutoffs, dependency versions, source hashes, and artifact hashes. `run_receipt.json` is written last. Its verifier checks the exact required inventory and every file's SHA-256.

The bundle stores all estimators and scoring-policy metadata. Persistence replay is tested against in-memory scores. Repeated-run tests compare every artifact hash on the same input and environment. Build failure preserves the last completed run; overlapping writers are refused.

Generated artifacts, environments, and caches are excluded from Git and from the source-only public boundary scan. This scan is an additional hygiene check, not proof that arbitrary external files are safe. The ML entrypoint generates its inputs internally and accepts no external data path.

Run the combined command in the order shown: the original linkage runner clears generated outputs before creating its reports.
