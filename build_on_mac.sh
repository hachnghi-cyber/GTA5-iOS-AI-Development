#!/bin/bash
set -euo pipefail

# Build on a real macOS host with Xcode and the iPhoneOS SDK.
# No input IPA is required to produce the plugin dylib.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out_dir="${1:-$script_dir/dist}"
mkdir -p "$out_dir"

sdk_path="$(xcrun --sdk iphoneos --show-sdk-path)"
clang_path="$(xcrun --find clang)"

"$clang_path" -arch arm64 -fobjc-arc -fobjc-exceptions -std=gnu++17 \
  -miphoneos-version-min=16.3 -isysroot "$sdk_path" \
  -dynamiclib -O2 -fvisibility=hidden \
  -framework Foundation -framework UIKit -framework GameController \
  -Wl,-install_name,@rpath/libCustomTouch.dylib \
  -o "$out_dir/libCustomTouch.dylib" "$script_dir/CustomTouch.mm"

codesign --force --sign - --timestamp=none "$out_dir/libCustomTouch.dylib"
file "$out_dir/libCustomTouch.dylib"
codesign --verify --verbose=2 "$out_dir/libCustomTouch.dylib"
