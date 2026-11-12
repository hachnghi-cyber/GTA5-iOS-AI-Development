#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CC="${CC:-clang}"
mkdir -p /tmp/prp-v11
"$CC" -std=c11 -O1 -g -Wall -Wextra -Werror \
 -fsanitize=address,undefined -fno-omit-frame-pointer \
 -I./NativeBridge -I./P2P -I./Integration \
 NativeBridge/police_rp_only.c NativeBridge/police_rp_adapter.c \
 P2P/prp_p2p.c P2P/prp_runtime.c \
 Integration/prp_mailbox.c Integration/prp_engine_binding.c \
 Integration/prp_candidate_carrier.c Integration/prp_event_isolation.c \
 Integration/test_event_isolation.c -lm -o /tmp/prp-v11/test_event
/tmp/prp-v11/test_event
python3 Tools/test_v11_receiver.py
