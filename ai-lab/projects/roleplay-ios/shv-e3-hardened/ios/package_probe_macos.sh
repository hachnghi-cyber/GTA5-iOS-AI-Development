#!/bin/bash
# macOS only. Explicit code-signing inputs required; never sign ad-hoc.
# Does not alter GTA5 executable or its Mach-O LC_LOAD_DYLIB; new SHV module
# is discovered at runtime by Frameworks/*.shv.dylib scanner if enabled.
set -euo pipefail
usage='Usage: package_probe_macos.sh <original-v13.3.ipa> <RBPProbe.shv.dylib> <Apple signing identity> <entitlements.plist> <output.ipa> [embedded.mobileprovision]'
if [[ $# -lt 5 || $# -gt 6 ]]; then echo "$usage" >&2; exit 2; fi
IPA="$1"; MODULE="$2"; IDENTITY="$3"; ENTS="$4"; OUT="$5"; PROFILE="${6:-}"
[[ "$IDENTITY" != '-' ]] || { echo 'Refusing ad-hoc signing identity' >&2; exit 2; }
if [[ "$OUT" != /* ]]; then OUT="$(pwd)/$OUT"; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for f in "$IPA" "$MODULE" "$ENTS"; do test -f "$f" || { echo "Not found: $f" >&2; exit 2; }; done
for cmd in xcrun codesign unzip zip shasum; do
 command -v "$cmd" >/dev/null || { echo "BLOCKED BY ENVIRONMENT: $cmd" >&2; exit 2; }
done
BASE_SHA='f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc'
python3 "$ROOT/tools/audit_ipa_for_probe.py" "$IPA" >/dev/null
WORK="$(mktemp -d "${TMPDIR:-/tmp}/rbp-package.XXXXXXXX")"
trap 'rm -rf "$WORK"' EXIT
unzip -q "$IPA" -d "$WORK"
APP="$WORK/Payload/GTAV.app"
BASE="$APP/GTA5"
test -f "$BASE" || { echo 'Not a GTA5 IPA' >&2; exit 2; }
ACTUAL="$(shasum -a 256 "$BASE" | awk '{print $1}')"
test "$ACTUAL" = "$BASE_SHA" || { echo "Refusing wrong binary SHA $ACTUAL" >&2; exit 2; }
cp "$BASE" "$WORK/GTA5.before-sign"
test -d "$APP/Frameworks" || exit 2
# Do not silently overwrite another plugin.
test ! -e "$APP/Frameworks/RBPProbe.shv.dylib" || { echo 'Plugin already exists' >&2; exit 2; }
cp "$MODULE" "$APP/Frameworks/RBPProbe.shv.dylib"
if [[ -n "$PROFILE" ]]; then
  test -f "$PROFILE" || exit 2
  cp "$PROFILE" "$APP/embedded.mobileprovision"
fi
# All embedded code must be signed for the target developer team. No new entitlements.
while IFS= read -r -d '' dylib; do
  codesign --force --sign "$IDENTITY" --timestamp=none "$dylib"
done < <(find "$APP/Frameworks" -name '*.dylib' -type f -print0)
codesign --force --sign "$IDENTITY" --timestamp=none --entitlements "$ENTS" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
# Re-signing necessarily changes the binary's code signature, and therefore
# often its full-file SHA256. Compare immutable UUID and __TEXT,__text bytes.
python3 "$ROOT/tools/verify_code_preserved.py" \
  "$WORK/GTA5.before-sign" "$BASE" >/dev/null
# Code bytes preserved does not imply the IPA runs; device validation required.
( cd "$WORK" && zip -qr "$OUT" Payload )
shasum -a 256 "$OUT"
echo "PACKAGED SIGNED DIAGNOSTIC IPA: $OUT. DEVICE VALIDATION STILL REQUIRED."
