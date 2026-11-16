#!/usr/bin/env bash
# Offline tests. No iPhoneOS SDK, device, GTA, or signed binary implied.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build evidence
CC="${CC:-clang}"
: "${ASAN_OPTIONS:=detect_leaks=0:halt_on_error=1}"
: "${UBSAN_OPTIONS:=halt_on_error=1}"
export ASAN_OPTIONS UBSAN_OPTIONS
python3 -m unittest discover -s tests -p 'test_*.py' -v > evidence/python_unittests.log 2>&1
if [[ -n "${RBP_IPA_PATH:-}" ]]; then
  python3 tools/audit_ipa_for_probe.py "$RBP_IPA_PATH" --out evidence/ipa_preflight.json > evidence/ipa_preflight_stdout.log 2>&1
elif [[ -f "/mnt/data/GTAV-v13.3.ipa" ]]; then
  python3 tools/audit_ipa_for_probe.py /mnt/data/GTAV-v13.3.ipa --out evidence/ipa_preflight.json > evidence/ipa_preflight_stdout.log 2>&1
else
  printf 'SKIPPED: no original IPA supplied; set RBP_IPA_PATH=/absolute/path/GTAV-v13.3.ipa\n' > evidence/ipa_preflight_stdout.log
fi
CFLAGS=(-std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -Iinclude)
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_wire_c.c src/rbp_crypto.c tests/test_rbp_wire_c.c -lcrypto -o build/test_rbp_wire_c
./build/test_rbp_wire_c > evidence/wire_c_sanitizers.log 2>&1
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_native_adapter.c tests/test_native_adapter.c -o build/test_native_adapter
./build/test_native_adapter > evidence/native_mock_sanitizers.log 2>&1
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_wire_c.c src/rbp_crypto.c src/rbp_native_adapter.c src/rbp_device_network.c src/rbp_device_log.c -DRBP_TEST_DROP_INITIAL_NATIVE_REPORT tests/test_device_network.c -lcrypto -pthread -o build/test_network
./build/test_network > evidence/network_sanitizers.log 2>&1
"$CC" "${CFLAGS[@]}" -D_POSIX_C_SOURCE=200809L -Wl,--export-dynamic tests/test_plugin_loader_host.c -ldl -o build/test_plugin_loader_host
for stage in 0 1 3; do
  # Mirror minimal source selection in the Xcode-facing build script.
  stage_sources=(ios/rbp_shv_plugin.c src/rbp_handoff.c src/rbp_device_log.c)
  if [[ "$stage" != 0 ]]; then stage_sources+=(src/rbp_native_adapter.c); fi
  if [[ "$stage" == 3 ]]; then
      stage_sources+=(src/rbp_device_network.c src/rbp_wire_c.c src/rbp_crypto.c)
  fi
  "$CC" "${CFLAGS[@]}" -fPIC -shared -DRBP_PROBE_STAGE="$stage" -DRBP_HOST_TEST \
    "${stage_sources[@]}" -lcrypto -pthread -ldl -o "build/RBPProbe-host-e${stage}.so"
  ./build/test_plugin_loader_host "$(pwd)/build/RBPProbe-host-e${stage}.so" "$stage" > "evidence/plugin_host_e${stage}.log" 2>&1
  ./build/test_plugin_loader_host "$(pwd)/build/RBPProbe-host-e${stage}.so" "$stage" fast > "evidence/plugin_host_e${stage}_fast.log" 2>&1
done
"$CC" "${CFLAGS[@]}" -Wl,--export-dynamic -D_POSIX_C_SOURCE=200809L \
  tests/test_plugin_peer_host.c -ldl -pthread -o build/test_plugin_peer_host
python3 tests/test_two_process_e3.py > evidence/two_process_e3.log 2>&1
bash -n ios/build_probe_macos.sh ios/package_probe_macos.sh
for src in src/rbp_handoff.c src/rbp_native_adapter.c src/rbp_wire_c.c; do
  name="$(basename "${src%.c}")"
  "${CROSS_CC:-clang}" -target arm64-apple-ios16.3 -ffreestanding -fno-builtin \
   -std=c11 -Wall -Wextra -Werror -DRBP_FREESTANDING_ARM64 -Iinclude \
   -c "$src" -o "build/${name}-arm64.o"
done
file build/*-arm64.o > evidence/arm64_objects.log
printf 'PASS HOST: Python / C sanitizers / shared .so plugin loader E0 E1 E3 / shell / ARM64 Mach-O objects\n'
printf 'DEVICE VALIDATION REQUIRED: no iOS link, codesign or on-device RAGE actions\n'
