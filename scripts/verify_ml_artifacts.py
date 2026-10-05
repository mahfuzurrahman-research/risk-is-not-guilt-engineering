from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_demo.integrity import verify_artifacts


if __name__ == "__main__":
    verify_artifacts(ROOT / "outputs/ml_demo")
    print("ML_ARTIFACT_INTEGRITY=PASS")
