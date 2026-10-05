from __future__ import annotations

import hashlib
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

import joblib
import pandas as pd

from .config import (
    FEATURES, RANDOM_SEED, SCHEMA_VERSION, POLICY_VERSION, QUEUE_FRACTION,
    CLASSIFIER_WEIGHT, ANOMALY_WEIGHT,
)
from .contracts import ROOT, load_contract
from .synthetic_data import SyntheticDatasetSpec, generate
from .split import temporal_split
from .modeling import fit, score, evaluate_scored, _metrics
from .queue import build_queue
from .evaluation import evaluate_queue
from .reporting import write_json, write_model_card


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(stage: Path, spec: SyntheticDatasetSpec, contract: dict) -> dict:
    df = generate(spec)
    dataset_path = stage / "synthetic_ad_integrity_events.csv"
    df.to_csv(dataset_path, index=False)
    train, validation, test = temporal_split(df)
    bundle, validation_payload = fit(train, validation)
    scored = score(bundle, test)
    metrics = {
        "selected_classifier": evaluate_scored(scored, test, bundle.threshold),
        "train_prior_baseline": _metrics(
            test["abuse_label"].to_numpy(), bundle.prior_model.predict_proba(test[FEATURES])[:, 1], 0.5,
        ),
        "held_out_test": True, "test_used_for_selection": False,
        "evaluation_timing": "retrospective; simulator outcomes observed after event decisions",
    }
    queue = build_queue(scored, bundle.reason_thresholds)
    queue_evaluation = {
        "combined": evaluate_queue(queue, test),
        "classifier_only": evaluate_queue(build_queue(
            scored.assign(combined_risk_score=scored["classifier_score"]), bundle.reason_thresholds,
            capacity=len(queue),
        ), test),
        "anomaly_only": evaluate_queue(build_queue(
            scored.assign(combined_risk_score=scored["anomaly_score"]), bundle.reason_thresholds,
            capacity=len(queue),
        ), test),
        "fixed_seed_random": evaluate_queue(scored.sample(frac=1, random_state=RANDOM_SEED).head(len(queue)), test),
        "capacity": int(len(queue)), "fraction": QUEUE_FRACTION,
        "weights_selected_on_test": False,
    }
    model_path = stage / "model_bundle.joblib"
    joblib.dump(bundle, model_path)
    # The complete scoring policy must survive persistence, not just its estimator.
    pd.testing.assert_frame_equal(score(joblib.load(model_path), test), scored)
    scored.to_csv(stage / "scored_events.csv", index=False)
    queue.to_csv(stage / "investigation_queue.csv", index=False)
    partitions = {
        name: {
            "rows": int(len(part)), "event_date_min": part["event_date"].min(),
            "event_date_max": part["event_date"].max(),
            "latest_outcome_available_at": part["label_available_at"].max(),
        }
        for name, part in [("train", train), ("validation", validation), ("test", test)]
    }
    dataset_summary = {
        "rows": int(len(df)), "positive_rate": float(df["abuse_label"].mean()),
        "date_min": df["event_date"].min(), "date_max": df["event_date"].max(),
        "partitions": partitions,
        "purged_unavailable_label_rows": int(len(df) - len(train) - len(validation) - len(test)),
        "features": FEATURES, "synthetic_only": True, "random_seed": spec.seed,
        "dataset_sha256": sha256(dataset_path),
    }
    dependencies = {
        p: importlib.metadata.version(p)
        for p in ["numpy", "pandas", "scikit-learn", "joblib", "scipy", "threadpoolctl"]
    }
    source_files = sorted((ROOT / "ml_demo").glob("*.py")) + [
        ROOT / "contracts/ml_demo_contract.json", ROOT / "requirements-ml.txt",
    ]
    manifest = {
        "model_id": bundle.model_id, "selected_classifier": bundle.classifier_name,
        "threshold": bundle.threshold, "threshold_status": bundle.threshold_status,
        "released_at": bundle.released_at, "features": FEATURES,
        "schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
        "train_rows": len(train), "validation_rows": len(validation), "test_rows": len(test),
        "random_seed": RANDOM_SEED, "synthetic_dataset_seed": spec.seed,
        "anomaly_reference": "training quantiles 0.01/0.99; clipped to [0,1]",
        "anomaly_low": bundle.anomaly_low, "anomaly_high": bundle.anomaly_high,
        "reason_thresholds": bundle.reason_thresholds,
        "queue_score_weights": {"classifier": CLASSIFIER_WEIGHT, "anomaly": ANOMALY_WEIGHT},
        "queue_fraction": QUEUE_FRACTION, "queue_tiebreak": "event_id ascending",
        "score_calibration": "not performed",
        "python_version": platform.python_version(), "dependencies": dependencies,
        "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in source_files},
        "model_artifact_sha256": sha256(model_path),
        "synthetic_only": True, "uses_google_ads_data": False,
        "uses_real_fraud_labels": False, "commercial_production_deployment": False,
        "scientific_claims_extended": False, "persistence_roundtrip": "PASS",
    }
    write_json(stage / "dataset_summary.json", dataset_summary)
    write_json(stage / "validation_metrics.json", validation_payload)
    write_json(stage / "test_metrics.json", metrics)
    write_json(stage / "queue_evaluation.json", queue_evaluation)
    write_model_card(stage / "model_card.md", manifest, validation_payload, metrics, queue_evaluation)
    manifest["artifact_sha256"] = {
        p.name: sha256(p) for p in sorted(stage.iterdir()) if p.is_file()
    }
    write_json(stage / "model_manifest.json", manifest)
    missing = [name for name in contract["required_outputs"] if not (stage / name).is_file()]
    if missing:
        raise ValueError(f"missing required outputs: {missing}")
    write_json(stage / "run_receipt.json", {
        "status": "PASS", "synthetic_only": True,
        "artifact_sha256": {p.name: sha256(p) for p in sorted(stage.iterdir()) if p.is_file()},
    })
    return {
        "dataset": dataset_summary, "validation": validation_payload, "test": metrics,
        "queue_evaluation": queue_evaluation, "manifest": manifest, "queue_rows": len(queue),
    }


def run(root: Path, spec: SyntheticDatasetSpec | None = None) -> dict:
    """Build in isolation, then publish artifacts with the success receipt last."""
    contract = load_contract()
    outputs = Path(root).resolve() / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    lock = outputs / ".ml_demo.lock"
    with lock.open("a+b") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another ML run is active; no outputs changed") from exc
        with TemporaryDirectory(prefix="ml-demo-stage-", dir=outputs) as temporary:
            stage = Path(temporary)
            result = _build(stage, spec or SyntheticDatasetSpec(), contract)
            out = outputs / "ml_demo"
            out.mkdir(exist_ok=True)
            (out / "run_receipt.json").unlink(missing_ok=True)
            for p in sorted(stage.iterdir()):
                if p.name != "run_receipt.json":
                    os.replace(p, out / p.name)
            os.replace(stage / "run_receipt.json", out / "run_receipt.json")
            return result
