#!/usr/bin/env bash
set -euo pipefail

# Build on a Mac with Xcode; this script does NOT modify or sign an IPA.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build_dir="${script_dir}/build-ios"
mkdir -p "${build_dir}"

xcrun --sdk iphoneos clang -arch arm64 -miphoneos-version-min=16.0 \
  -std=c11 -O2 -fvisibility=hidden \
  -c "${script_dir}/GojoTouchQueue.c" -o "${build_dir}/GojoTouchQueue.o"

xcrun --sdk iphoneos clang++ -arch arm64 -miphoneos-version-min=16.0 \
  -std=c++17 -O2 -fobjc-arc -fblocks -fvisibility=hidden \
  -c "${script_dir}/GojoTouchOverlay.mm" -o "${build_dir}/GojoTouchOverlay.o"

xcrun --sdk iphoneos clang++ -arch arm64 -miphoneos-version-min=16.0 \
  -dynamiclib -install_name '@rpath/GojoTouchBridge.dylib' \
  -Wl,-exported_symbol,_gojo_touch_consume \
  -Wl,-exported_symbol,_gojo_touch_set_enabled \
  -framework Foundation -framework UIKit -framework CoreGraphics \
  "${build_dir}/GojoTouchQueue.o" "${build_dir}/GojoTouchOverlay.o" \
  -o "${build_dir}/GojoTouchBridge.dylib"

file "${build_dir}/GojoTouchBridge.dylib"
