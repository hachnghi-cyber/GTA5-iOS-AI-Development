#!/bin/bash
# Sign a PREPACKAGED Phase12 IPA with exactly one pinned RBPProbe.shv.dylib.
# Requires exact com.macport.gtav Apple Development profile. No ad-hoc signing.
set -euo pipefail
if [[ $# -lt 7 || $# -gt 8 ]];then
 echo 'Usage: sign_prepackaged_probe_macos.sh original.ipa diagnostic-unsigned.ipa stage:0|1|3 "Apple Development identity" entitlements.plist profile.mobileprovision signed-output.ipa [device-UDID]' >&2
 exit 2
fi
ORIGINAL="$1";UNSIGNED="$2";STAGE="$3";IDENTITY="$4";ENTS="$5";PROFILE="$6";OUT="$7"
UDID=""
if [[ $# -eq 8 ]];then UDID="$8";fi
case "$STAGE" in 0|1|3) ;; *) echo 'Unknown stage' >&2;exit 2;; esac
[[ -n "$IDENTITY" && "$IDENTITY" != '-' && "$IDENTITY" != *'ad hoc'* ]] || { echo 'Refusing ad-hoc signing' >&2;exit 2; }
for f in "$ORIGINAL" "$UNSIGNED" "$ENTS" "$PROFILE";do
 [[ -f "$f" ]] || { echo 'Missing required input' >&2;exit 2; }
done
for cmd in codesign xcrun security unzip zip shasum python3;do
 command -v "$cmd" >/dev/null || { echo "Missing macOS tool: $cmd" >&2;exit 2; }
done
if [[ "$OUT" != /* ]];then OUT="$(pwd)/$OUT";fi
[[ ! -e "$OUT" ]] || { echo 'Refusing to overwrite signed IPA' >&2;exit 2; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/tools/verify_existing_probe_ipa.py" \
 --original "$ORIGINAL" --diagnostic "$UNSIGNED" --stage "$STAGE" >/dev/null
WORK="$(mktemp -d /tmp/rbp-phase13.XXXXXXXX)"
trap 'rm -rf "$WORK"' EXIT
security cms -D -i "$PROFILE" > "$WORK/profile.plist"
if [[ -n "$UDID" ]];then
 python3 "$ROOT/tools/check_development_profile.py" \
  --decoded-profile "$WORK/profile.plist" --entitlements "$ENTS" --device-udid "$UDID" >/dev/null
else
 python3 "$ROOT/tools/check_development_profile.py" \
  --decoded-profile "$WORK/profile.plist" --entitlements "$ENTS" >/dev/null
fi
mkdir "$WORK/repack"
unzip -q "$UNSIGNED" -d "$WORK/repack"
APP="$WORK/repack/Payload/GTAV.app"
[[ -f "$APP/GTA5" && -f "$APP/Frameworks/RBPProbe.shv.dylib" ]] || exit 2
cp "$APP/GTA5" "$WORK/GTA5.before-sign"
cp "$PROFILE" "$APP/embedded.mobileprovision"
while IFS= read -r -d '' dylib;do
 codesign --force --sign "$IDENTITY" --timestamp=none "$dylib"
done < <(find "$APP/Frameworks" -name '*.dylib' -type f -print0)
codesign --force --sign "$IDENTITY" --timestamp=none --entitlements "$ENTS" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
python3 "$ROOT/tools/verify_code_preserved.py" "$WORK/GTA5.before-sign" "$APP/GTA5" >/dev/null
( cd "$WORK/repack" && zip -qr "$OUT" Payload )
unzip -tqq "$OUT" || { rm -f "$OUT";echo 'Signed IPA failed CRC' >&2;exit 1; }
shasum -a 256 "$OUT"
echo 'Development-signed diagnostic IPA. DEVICE TEST STILL REQUIRED.'
