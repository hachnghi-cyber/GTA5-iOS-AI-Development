#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash Tools/test_v08_bridge.sh
bash Tools/build_v08_arm64_objects.sh
if [[ $# -ge 1 ]]; then
    python3 Tools/verify_v12_base.py "$1"
    python3 Tools/inspect_v12_calls.py "$1" --output ARM64_CALL_XREF_V12.json
fi
