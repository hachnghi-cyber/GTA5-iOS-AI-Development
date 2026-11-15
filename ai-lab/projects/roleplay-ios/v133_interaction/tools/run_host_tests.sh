#!/usr/bin/env bash
# Source-only tests. No GTA binary, iPhone, or live network is accessed.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
compiler="${CC:-cc}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
flags=(-std=c11 -Wall -Wextra -Wpedantic -Werror -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -I include)
sources=(src/rp_v133_interact_gate.c src/rp_v133_wire.c)
for target in test_v133_interact_gate test_v133_wire test_v133_two_peers; do
  "$compiler" "${flags[@]}" "${sources[@]}" "tests/$target.c" -o "$work/$target"
  ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$work/$target"
done
echo "P5 host tests: PASS (source-only)"
