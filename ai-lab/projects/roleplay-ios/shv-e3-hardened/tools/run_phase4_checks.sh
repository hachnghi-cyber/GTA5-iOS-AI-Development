#!/usr/bin/env bash
# Phase 4: full host regression + Apple-branch syntax (MOCK HEADERS ONLY).
# No iOS SDK/link/signing or device claims from this script.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CC:=clang}"
# An exact, validated user-provided IPA allows the binary-diff test to run.
# Never publish this extracted proprietary GTA5 executable in the source ZIP.
TMPBASE=""
if [[ -n "${RBP_IPA_PATH:-}" && -f "${RBP_IPA_PATH}" && -z "${RBP_GTA5_PATH:-}" ]]; then
    TMPBASE="$(mktemp -d)"
    trap '[[ -z "$TMPBASE" ]] || rm -rf "$TMPBASE"' EXIT
    python3 - "$RBP_IPA_PATH" "$TMPBASE/GTA5" <<'PYBASE'
import zipfile,sys,hashlib
with zipfile.ZipFile(sys.argv[1]) as z:
    b=z.read('Payload/GTAV.app/GTA5')
assert hashlib.sha256(b).hexdigest()=='f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc'
open(sys.argv[2],'wb').write(b)
PYBASE
    export RBP_GTA5_PATH="$TMPBASE/GTA5"
fi
bash -n tools/run_phase4_checks.sh ios/build_probe_macos.sh ios/package_probe_macos.sh
"$(dirname "$0")/run_phase3_checks.sh"
if [[ -n "${RBP_IPA_PATH:-}" ]]; then
    python3 tools/audit_shv_native_bridge.py "$RBP_IPA_PATH"         --out evidence/shv_native_bridge_static.json > evidence/shv_native_bridge_static_stdout.log
fi
"$CC" -std=c11 -Wall -Wextra -Werror -fsyntax-only \
   -D__APPLE__ -D_GNU_SOURCE -DRBP_PROBE_STAGE=0 \
   -Itests/apple_stub -Iinclude ios/rbp_shv_plugin.c \
   > evidence/apple_branch_mock_header_syntax.log 2>&1
# Explicitly ensure Apple-only code was compiled (not the RBP_HOST_TEST branch).
grep -q 'mach-o/dyld.h' ios/rbp_shv_plugin.c
printf '%s\n' 'PASS: Apple-side dyld resolver syntax with MOCK Mach-O headers (NOT real iPhoneOS SDK)' \
 > evidence/apple_branch_mock_header_syntax.log
printf '%s\n' 'PHASE4 HOST CHECK PASS: still requires Apple SDK/device testing for E0/E1/E3.'
