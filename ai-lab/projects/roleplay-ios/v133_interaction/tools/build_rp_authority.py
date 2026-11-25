"""Build only the source-owned host authority library. No game assets required."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='cc')
    parser.add_argument('--compiler-arg', action='append', default=[])
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--with-client-test-fixture', action='store_true',
                        help='include the native client test wrapper; never for deployment')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-Wpedantic', '-O2', '-shared']
    if sys.platform != 'win32':
        flags += ['-fPIC']
    fixture = [str(root / file) for file in ('src/rp_v133_authority_client.c', 'src/rp_v133_authority_social.c',
                                            'src/rp_v133_interact_gate.c', 'src/rp_v133_wire.c',
                                            'tests/authority_client_test_ffi.c')] if args.with_client_test_fixture else []
    subprocess.run([args.compiler, *args.compiler_arg, *flags, '-I', str(root / 'include'),
                    str(root / 'src/rp_v133_police.c'), str(root / 'src/rp_v133_police_tx.c'),
                    str(root / 'server/rp_authority_ffi.c'), *fixture, '-o', str(args.output.resolve())], check=True)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
