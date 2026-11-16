#!/usr/bin/env bash
# Source-only tests. No GTA binary, iPhone, or live network is accessed.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
compiler="${CC:-cc}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
flags=(-std=c11 -Wall -Wextra -Wpedantic -Werror -pthread -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -I include)
sources=(src/rp_v133_interact_gate.c src/rp_v133_wire.c src/rp_v133_mailbox.c src/rp_v133_carrier.c src/rp_v133_police.c src/rp_v133_police_tx.c src/rp_v133_police_bridge.c)
for target in test_v133_interact_gate test_v133_wire test_v133_two_peers test_v133_mailbox test_v133_mailbox_threads test_v133_carrier test_v133_police test_v133_police_tx test_v133_police_bridge; do
  "$compiler" "${flags[@]}" "${sources[@]}" "tests/$target.c" -o "$work/$target"
  ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$work/$target"
done
"$compiler" "${flags[@]}" -DRP_TEST_CARRIER "${sources[@]}" tests/test_v133_two_peers.c -o "$work/test_carrier_two_peers"
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$work/test_carrier_two_peers"
echo "P9 host tests: PASS (10 source test binaries; no game or device)"
