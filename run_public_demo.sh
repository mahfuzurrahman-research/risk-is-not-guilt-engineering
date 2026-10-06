#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD:${PYTHONPATH:-}"
mkdir -p outputs
# Regenerate this module's files without deleting other completed demo runs.
rm -f outputs/public_demo.sqlite outputs/audit_summary.json outputs/audit_report.md outputs/dashboard.html
python3 scripts/verify_public_boundary.py
python3 scripts/run_pipeline.py
python3 dashboards/build_demo_dashboard.py
python3 -m unittest discover -s tests -v
printf '\nPUBLIC_ENGINEERING_DEMO=PASS\n'
