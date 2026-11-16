#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -fPIC -shared -DRBP_E0_HOST_TEST \
  "$ROOT/src/rbp_e0_probe.c" -o "$OUT/RBPProbeE0.so" -pthread -ldl
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -rdynamic \
  "$ROOT/tests/test_e0_host.c" -o "$OUT/test_e0_host" -ldl
"$OUT/test_e0_host" "$OUT/RBPProbeE0.so" normal
"$OUT/test_e0_host" "$OUT/RBPProbeE0.so" fast

# Same dyld+UUID+dlsym code path as iOS, fed only by host-only fixtures.
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -fPIC -shared \
  "$ROOT/tests/shv_fixture.c" -o "$OUT/ScriptHookV.dylib"
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -fPIC -shared -DRBP_E0_TEST_DYLD \
  "$ROOT/src/rbp_e0_probe.c" -o "$OUT/RBPProbeE0Dyld.so" -pthread -ldl
"${CC:-clang}" -std=c11 -Wall -Wextra -Werror -rdynamic \
  "$ROOT/tests/test_e0_dyld.c" -o "$OUT/test_e0_dyld" -ldl
"$OUT/test_e0_dyld" "$OUT/RBPProbeE0Dyld.so" "$OUT/ScriptHookV.dylib"
printf 'PASS compiler=%s E0 host tests (mock + dyld-contract)\n' "${CC:-clang}"
