#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="${1:-$script_dir/dist}"
mkdir -p "$output_dir"

sdk_path="$(xcrun --sdk iphoneos --show-sdk-path)"
clang_path="$(xcrun --find clang++)"

"$clang_path" -arch arm64 -std=c++17 -stdlib=libc++ -O2 -Wall -Wextra \
  -fobjc-arc -fobjc-exceptions -fvisibility=hidden \
  -miphoneos-version-min=16.3 -isysroot "$sdk_path" \
  -dynamiclib \
  -framework Foundation -framework UIKit -framework AVFoundation -framework CoreGraphics \
  -Wl,-install_name,@rpath/libSupermanIOS.dylib \
  -o "$output_dir/libSupermanIOS.dylib" \
  "$script_dir/GameplayCore.cpp" "$script_dir/SupermanOverlay.mm"

codesign --force --sign - --timestamp=none "$output_dir/libSupermanIOS.dylib"
codesign --verify --verbose=2 "$output_dir/libSupermanIOS.dylib"
file "$output_dir/libSupermanIOS.dylib"

