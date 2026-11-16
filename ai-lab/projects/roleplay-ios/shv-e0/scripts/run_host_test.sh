#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
clang -std=c11 -Wall -Wextra -Werror -fPIC -shared -DRBP_E0_HOST_TEST \
  "$ROOT/src/rbp_e0_probe.c" -o "$OUT/RBPProbeE0.so" -pthread -ldl
clang -std=c11 -Wall -Wextra -Werror -rdynamic \
  "$ROOT/tests/test_e0_host.c" -o "$OUT/test_e0_host" -ldl
"$OUT/test_e0_host" "$OUT/RBPProbeE0.so" normal
"$OUT/test_e0_host" "$OUT/RBPProbeE0.so" fast
