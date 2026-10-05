#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="$PWD:${PYTHONPATH:-}"

python3 scripts/verify_public_boundary.py
python3 scripts_run_ml_demo.py
python3 -m unittest discover -s tests_ml -v
python3 scripts/verify_ml_artifacts.py

printf '\nML_RISK_ENGINEERING_DEMO=PASS\n'
