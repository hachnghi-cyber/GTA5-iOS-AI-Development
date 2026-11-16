#!/bin/bash
# macOS/Xcode + installed iPhoneOS SDK only. Does NOT modify/sign any IPA.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="${1:-0}"
case "$STAGE" in 0|1|3) ;; *) echo 'Usage: build_probe_macos.sh [0|1|3]' >&2; exit 2;; esac
if ! command -v xcrun >/dev/null || ! command -v codesign >/dev/null; then
  echo 'BLOCKED BY ENVIRONMENT: macOS Xcode/iPhoneOS SDK required' >&2; exit 2
fi
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
OUT="$ROOT/build/ios-e${STAGE}"
mkdir -p "$OUT"
CFLAGS=( -arch arm64 -isysroot "$SDK" -miphoneos-version-min=16.3 \
 -std=c11 -Os -Wall -Wextra -Werror -fvisibility=hidden \
 "-DRBP_PROBE_STAGE=$STAGE" -I"$ROOT/include" )
# Minimal dependencies for each gate: E0 must NOT require any UDP or
# CommonCrypto network code. E1 adds only native HUD adapter; E3 adds transport.
SOURCES=("$ROOT/ios/rbp_shv_plugin.c" \
 "$ROOT/src/rbp_handoff.c" "$ROOT/src/rbp_device_log.c")
if [[ "$STAGE" != 0 ]]; then SOURCES+=("$ROOT/src/rbp_native_adapter.c"); fi
if [[ "$STAGE" == 3 ]]; then
 SOURCES+=("$ROOT/src/rbp_wire_c.c" "$ROOT/src/rbp_crypto.c" \
           "$ROOT/src/rbp_device_network.c")
fi
xcrun clang "${CFLAGS[@]}" -dynamiclib "${SOURCES[@]}" \
 -Wl,-install_name,@rpath/RBPProbe.shv.dylib -Wl,-rpath,@loader_path \
 -o "$OUT/RBPProbe.shv.dylib"
# Loader-visible export and per-plugin rpath are required for this build.
xcrun nm -gU "$OUT/RBPProbe.shv.dylib" > "$OUT/exported_symbols.txt"
grep -Eq '[[:space:]]_DllMain$' "$OUT/exported_symbols.txt" || {
 echo 'DllMain export missing from linked plugin' >&2; exit 1;
}
xcrun otool -l "$OUT/RBPProbe.shv.dylib" > "$OUT/loadcommands.txt"
# Parse the LC_RPATH command itself; a stray @loader_path string in an
# unrelated load command is NOT sufficient evidence.
awk '/cmd LC_RPATH/{rpath=1;next} rpath && /path @loader_path /{found=1;rpath=0} END{exit !found}' \
  "$OUT/loadcommands.txt" || { echo 'LC_RPATH @loader_path missing' >&2; exit 1; }
xcrun lipo -verify_arch arm64 "$OUT/RBPProbe.shv.dylib" || {
 echo 'Missing arm64 slice' >&2; exit 1;
}
xcrun lipo -info "$OUT/RBPProbe.shv.dylib" | tee "$OUT/architecture.txt"
xcrun otool -L "$OUT/RBPProbe.shv.dylib" | tee "$OUT/dependencies.txt"
if grep -E '^[[:space:]]+.*(ScriptHookV|libgtacompat)\.dylib' "$OUT/dependencies.txt"; then
 echo 'Unexpected strong link to optional game libraries' >&2; exit 1;
fi
xcrun vtool -show-build "$OUT/RBPProbe.shv.dylib" | tee "$OUT/platform.txt"
grep -Eq 'platform[[:space:]]+IOS([[:space:]]|$)' "$OUT/platform.txt" || {
 echo 'LC_BUILD_VERSION is not iPhoneOS platform IOS' >&2; exit 1;
}
shasum -a 256 "$OUT/RBPProbe.shv.dylib" | tee "$OUT/SHA256.txt"
printf '%s\n' "E${STAGE} dylib built only; NOT signed, NOT loaded, NOT tested in game." > "$OUT/README.txt"
