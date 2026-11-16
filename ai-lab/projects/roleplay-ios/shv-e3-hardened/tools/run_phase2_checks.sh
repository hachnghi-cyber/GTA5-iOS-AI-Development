#!/usr/bin/env bash
# Host-only reproduction. Does NOT load iPhone modules or assert RAGE effects.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build evidence
CC="${CC:-clang}"
: "${ASAN_OPTIONS:=detect_leaks=0:halt_on_error=1}"
: "${UBSAN_OPTIONS:=halt_on_error=1}"
export ASAN_OPTIONS UBSAN_OPTIONS
python3 -m unittest discover -s tests -p 'test_*.py' -v \
  > evidence/phase2_python_tests.log 2>&1
CFLAGS=( -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer -Iinclude )
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_wire_c.c src/rbp_crypto.c \
  tests/test_rbp_wire_c.c -lcrypto -o build/test_rbp_wire_c
./build/test_rbp_wire_c > evidence/wire_c_asan_ubsan.log 2>&1
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_native_adapter.c \
  tests/test_native_adapter.c -o build/test_native_adapter_v2
./build/test_native_adapter_v2 > evidence/native_adapter_v2_asan.log 2>&1
"$CC" "${CFLAGS[@]}" src/rbp_handoff.c src/rbp_wire_c.c src/rbp_crypto.c \
  src/rbp_native_adapter.c src/rbp_device_network.c \
  tests/test_device_network.c -lcrypto -pthread -o build/test_device_network
./build/test_device_network > evidence/udp_native_asan_ubsan.log 2>&1
for stage in 0 1 3; do
 "$CC" -std=c11 -O1 -Wall -Wextra -Werror -pedantic \
   -DRBP_PROBE_STAGE="$stage" -Iinclude -c ios/rbp_shv_plugin.c \
   -o "build/rbp_shv_plugin_host_e${stage}.o"
done
bash -n ios/build_probe_macos.sh ios/package_probe_macos.sh
for source in src/rbp_handoff.c src/rbp_native_adapter.c src/rbp_wire_c.c; do
 name="$(basename "${source%.c}")"
 "$CC" -target arm64-apple-ios16.3 -ffreestanding -fno-builtin \
   -std=c11 -Wall -Wextra -Werror -DRBP_FREESTANDING_ARM64 -Iinclude -c \
   "$source" -o "build/${name}_ios_arm64_v2.o"
done
file build/*_ios_arm64_v2.o > evidence/arm64_v2_objects.log
printf 'PASS: host Python/C tests, sanitizer, mock stage 0/1/3 compile, freestanding Mach-O ARM64 objects, shell syntax.\n'
printf 'Not a signed iOS dylib / not a device test / not RAGE gameplay.\n'
