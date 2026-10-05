#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
./run_public_demo.sh
./run_ml_demo.sh
printf '\nALL_ENGINEERING_DEMOS=PASS\n'
