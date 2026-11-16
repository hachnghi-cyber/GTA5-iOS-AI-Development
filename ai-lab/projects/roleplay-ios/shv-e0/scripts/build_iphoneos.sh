#!/usr/bin/env bash
# Unsigned ARM64 iPhoneOS diagnostic dylib; NOT a playable/signed IPA.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"
command -v xcrun >/dev/null || { echo 'BLOCKED: macOS/Xcode/xcrun required' >&2; exit 2; }
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
mkdir -p "$OUT"
xcrun clang -arch arm64 -isysroot "$SDK" -miphoneos-version-min=16.3 \
  -std=c11 -Os -Wall -Wextra -Werror -fvisibility=hidden \
  -dynamiclib "$ROOT/src/rbp_e0_probe.c" \
  -Wl,-install_name,@rpath/RBPProbeE0.shv.dylib \
  -o "$OUT/RBPProbeE0.shv.dylib"
xcrun nm -gU "$OUT/RBPProbeE0.shv.dylib" > "$OUT/exports.txt"
grep -Eq '[[:space:]]_DllMain$' "$OUT/exports.txt" || { echo 'FAIL: DllMain not exported' >&2; exit 1; }
xcrun otool -L "$OUT/RBPProbeE0.shv.dylib" > "$OUT/dependencies.txt"
if grep -q ScriptHookV.dylib "$OUT/dependencies.txt"; then
  echo 'FAIL: ScriptHookV must be dynamically discovered; no strong linkage' >&2; exit 1
fi
xcrun otool -l "$OUT/RBPProbeE0.shv.dylib" > "$OUT/loadcommands.txt"
xcrun lipo -info "$OUT/RBPProbeE0.shv.dylib" > "$OUT/arch.txt"
xcrun vtool -show-build "$OUT/RBPProbeE0.shv.dylib" > "$OUT/platform.txt"
shasum -a 256 "$OUT/RBPProbeE0.shv.dylib" > "$OUT/SHA256SUMS.txt"
cat > "$OUT/README.txt" <<'EOT'
BUILD ONLY: unsigned diagnostic Mach-O dylib for iPhoneOS ARM64.
No GTA game, IPA, profile, entitlements or certificates are included.
No evidence of loading on iPhone or multiplayer game action is implied.
Installer must sign code legitimately with matching app/team provisioning.
EOT
printf 'PASS: iPhoneOS ARM64 E0 dylib linked; hardware validation outstanding.\n'
