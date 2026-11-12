#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CC="${CC:-clang}"
mkdir -p /tmp/prp-v12
"$CC" -std=c11 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c \
  P2P/prp_p2p.c P2P/prp_runtime.c \
  Integration/prp_mailbox.c Integration/prp_engine_binding.c \
  Integration/prp_candidate_carrier.c Integration/prp_event_isolation.c \
  Integration/prp_transport_port.c Integration/test_transport_port.c \
  -lm -o /tmp/prp-v12/test_transport
/tmp/prp-v12/test_transport
