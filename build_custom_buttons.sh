#!/bin/bash
# Run on macOS with Xcode Command Line Tools / iOS SDK installed.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: bash build_custom_buttons.sh /path/to/GTAV-v11.2.ipa [output.ipa]"
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_IPA="$1"
OUTPUT_IPA="${2:-$SCRIPT_DIR/GTAV-v11.2_CustomButtons_BETA_UNSIGNED.ipa}"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

SDK_PATH="$(xcrun --sdk iphoneos --show-sdk-path)"
DYLIB_PATH="$BUILD_DIR/GTA5CustomButtons.dylib"

xcrun --sdk iphoneos clang++ \
  -arch arm64 \
  -isysroot "$SDK_PATH" \
  -miphoneos-version-min=16.3 \
  -std=c++17 \
  -fobjc-arc -fblocks \
  -O2 -fvisibility=hidden \
  -dynamiclib \
  -Wl,-install_name,@executable_path/Frameworks/GTA5CustomButtons.dylib \
  -framework UIKit -framework Foundation \
  "$SCRIPT_DIR/CustomButtons.mm" \
  -o "$DYLIB_PATH"

python3 "$SCRIPT_DIR/inject_ipa.py" \
  --ipa "$INPUT_IPA" \
  --dylib "$DYLIB_PATH" \
  --output "$OUTPUT_IPA"

echo "Built unsigned test IPA: $OUTPUT_IPA"
echo "Sign with your iOS sideloading tool. Keep the original IPA as rollback."
