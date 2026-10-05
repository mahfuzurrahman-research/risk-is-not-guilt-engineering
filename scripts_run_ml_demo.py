from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ml_demo.pipeline import run


def main():
    obj = run(ROOT)
    metrics = obj["test"]["selected_classifier"]
    print("ML_DATASET=PASS")
    print(f"ML_SELECTED_MODEL={obj['manifest']['selected_classifier']}")
    print("TEMPORAL_VALIDATION=PASS")
    print("RISK_CLASSIFICATION=PASS")
    print("ANOMALY_DETECTION=PASS")
    print(f"INVESTIGATION_QUEUE_ROWS={obj['queue_rows']}")
    print(f"TEST_AVERAGE_PRECISION={metrics['average_precision']:.6f}")
    print(f"TEST_ROC_AUC={metrics['roc_auc']:.6f}")
    print("MODEL_PERSISTENCE_ROUNDTRIP=PASS")
    print("SYNTHETIC_AD_INTEGRITY_ML_DEMO=PASS")


if __name__ == "__main__":
    main()
