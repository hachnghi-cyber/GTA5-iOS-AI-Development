#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CC=${CC:-clang}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FLAGS=(-std=c11 -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer)
SOURCES=(NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c P2P/prp_p2p.c P2P/prp_runtime.c Integration/prp_engine_binding.c Integration/prp_mailbox.c)
"$CC" "${FLAGS[@]}" "${SOURCES[@]}" Integration/test_engine_binding.c -lm -o "$TMP/test_bridge"
"$TMP/test_bridge"
"$CC" "${FLAGS[@]}" Integration/prp_mailbox.c Integration/test_mailbox.c -pthread -lm -o "$TMP/test_mailbox"
"$TMP/test_mailbox"
"$CC" "${FLAGS[@]}" NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c \
  P2P/prp_p2p.c P2P/test_duty_exit.c -lm -o "$TMP/test_duty_exit"
"$TMP/test_duty_exit"
bash Tools/test_v06_native.sh
python3 -m unittest discover -s Tests -p 'test_*.py' -q
