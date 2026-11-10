#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-${SCRIPT_DIR}/dist}"
mkdir -p "${OUT_DIR}"

SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
CXX="$(xcrun --sdk iphoneos --find clang++)"
CFLAGS=(-arch arm64 -isysroot "${SDK}" -miphoneos-version-min=16.3
        -std=c++17 -O2 -fvisibility=hidden -fno-exceptions -fno-rtti)

"${CXX}" "${CFLAGS[@]}" -I"${SCRIPT_DIR}" \
  -c "${SCRIPT_DIR}/SupermanR6.cpp" -o "${OUT_DIR}/SupermanR6.o"
"${CXX}" "${CFLAGS[@]}" -fobjc-arc -x objective-c++ \
  -c "${SCRIPT_DIR}/SupermanAudio.mm" -o "${OUT_DIR}/SupermanAudio.o"

"${CXX}" -arch arm64 -isysroot "${SDK}" -miphoneos-version-min=16.3 \
  -dynamiclib -stdlib=libc++ -Wl,-dead_strip \
  -Wl,-install_name,@rpath/SupermanR6.shv.dylib \
  -Wl,-rpath,@loader_path \
  -Wl,-rpath,@executable_path/Frameworks \
  -framework Foundation -framework AVFoundation \
  "${OUT_DIR}/SupermanR6.o" "${OUT_DIR}/SupermanAudio.o" \
  -L"${SCRIPT_DIR}" -lScriptHookV \
  -o "${OUT_DIR}/SupermanR6.shv.dylib"

codesign --force --sign - --timestamp=none "${OUT_DIR}/SupermanR6.shv.dylib"
file "${OUT_DIR}/SupermanR6.shv.dylib"
otool -L "${OUT_DIR}/SupermanR6.shv.dylib"
nm -gU "${OUT_DIR}/SupermanR6.shv.dylib" | grep -q '_DllMain'
codesign --verify --strict "${OUT_DIR}/SupermanR6.shv.dylib"

echo "Built: ${OUT_DIR}/SupermanR6.shv.dylib"
