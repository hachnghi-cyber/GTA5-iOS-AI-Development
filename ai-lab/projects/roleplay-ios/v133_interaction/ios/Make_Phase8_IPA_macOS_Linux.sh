#!/bin/sh
# Local-only source packaging. Input IPA never leaves this computer.
set -eu
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  printf '%s\n' 'Usage: sh Make_Phase8_IPA_macOS_Linux.sh /path/to/GTAV-v13.3.ipa' >&2
  exit 2
fi
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
IPA=$1
PY="$DIR/patch_exact_v133_probe.py"
BRIDGE="$DIR/PoliceRPV133Probe.dylib"
[ -f "$PY" ] && [ -f "$BRIDGE" ] || { echo "Missing packer or iPhone arm64 dylib in $DIR" >&2; exit 2; }
case "$IPA" in
  *.ipa) OUT="${IPA%.ipa}-Phase8-Probe-UNSIGNED.ipa" ;;
  *) echo 'Input must have .ipa extension' >&2; exit 2 ;;
esac
[ ! -e "$OUT" ] || { echo "Output already exists: $OUT" >&2; exit 2; }
python3 "$PY" --ipa "$IPA" --bridge "$BRIDGE" --out "$OUT" --enable-file-sharing
printf '%s\n' "Created unsigned IPA: $OUT" 'Re-sign app + embedded dylib with the same Apple developer identity before iPhone install.' 'This is only a startup diagnostic; it DOES NOT enable online Police RP.'
