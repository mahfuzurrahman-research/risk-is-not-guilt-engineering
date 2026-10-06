#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
mkdir -p outputs
python3 scripts/verify_public_boundary.py
python3 -m ads_lab run > outputs/ads_lab_summary.json
python3 -m ads_lab verify
python3 -m ads_lab capture-demo
python3 -m ads_lab inspect --capture outputs/ads_capture.json
python3 -m ads_lab verify-inspection
python3 -m unittest discover -s tests_ads -v
printf '\nADS_DESTINATION_INVESTIGATION_LAB=PASS\n'
