#!/usr/bin/env bash
# Cross-compile ONLY ARM64 Mach-O object files using header SHIMS; no Apple SDK.
# Output is NOT a dylib, not an IPA, and cannot be installed on iOS as-is.
set -euo pipefail
cd "$(dirname "$0")/.."
CC=${CC:-clang}
mkdir -p BuildProof
for src in NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c \
           P2P/prp_p2p.c P2P/prp_runtime.c \
           Integration/prp_mailbox.c Integration/prp_engine_binding.c \
           Integration/prp_candidate_carrier.c Integration/prp_event_isolation.c \
           Integration/prp_transport_port.c; do
    name=$(basename "${src%.c}")
    "$CC" --target=arm64-apple-ios16.0 -std=c11 -O2 -Wall -Wextra -Werror \
      -nostdinc -I BuildProof/headers -isystem "$("$CC" -print-resource-dir)/include" \
      -c "$src" -o "BuildProof/$name.o"
done
file BuildProof/*.o
