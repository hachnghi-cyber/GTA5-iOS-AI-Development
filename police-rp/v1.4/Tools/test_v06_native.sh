#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CC:=clang}"
CFLAGS='-std=c11 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer'
TMPDIR_P6=$(mktemp -d)
trap 'rm -rf "$TMPDIR_P6"' EXIT
for kind in p2p runtime; do
  "$CC" $CFLAGS NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c P2P/prp_p2p.c P2P/prp_runtime.c "P2P/test_${kind}.c" -lm -o "$TMPDIR_P6/test_${kind}"
  "$TMPDIR_P6/test_${kind}"
done
