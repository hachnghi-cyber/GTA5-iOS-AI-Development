#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash Tools/test_v09_full.sh
bash Tools/test_v10_carrier.sh
bash Tools/test_v11_event.sh
bash Tools/test_v12_transport.sh
bash Tools/build_v08_arm64_objects.sh
if [ -f /mnt/data/GTAV-v12\(1\).ipa ]; then
  python3 Tools/verify_v12_base.py '/mnt/data/GTAV-v12(1).ipa'
fi
