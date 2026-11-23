#!/usr/bin/env bash
# Experimental, unsigned output. Requires Xcode + iPhoneOS SDK on macOS.
set -euo pipefail
if [[ "$#" -ne 3 ]]; then
  echo "Usage: bash build_on_macos.sh <base.ipa> <VietnameseAccented.nvp> <output.ipa>" >&2
  exit 2
fi
[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS/Xcode required" >&2; exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
xcrun --sdk iphoneos clang++ \
  -arch arm64 -isysroot "$SDK" -miphoneos-version-min=16.0 \
  -std=c++17 -O2 -fobjc-arc -fvisibility=hidden -dynamiclib \
  -Wl,-install_name,@executable_path/Frameworks/libVietHoaBoot.dylib \
  -framework Foundation -lc++ \
  "$ROOT/src/NovaVietnameseInstaller.cpp" "$ROOT/src/VietnameseBoot.mm" \
  -o "$TMP/libVietHoaBoot.dylib"
python3 "$ROOT/tools/inject_ipa.py" --ipa "$1" --nvp "$2" \
  --dylib "$TMP/libVietHoaBoot.dylib" --output "$3"
