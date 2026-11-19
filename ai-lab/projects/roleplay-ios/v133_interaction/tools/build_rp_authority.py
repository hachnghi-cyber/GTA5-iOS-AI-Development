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
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-Wpedantic', '-O2', '-shared']
    if sys.platform != 'win32':
        flags += ['-fPIC']
    subprocess.run([args.compiler, *args.compiler_arg, *flags, '-I', str(root / 'include'),
                    str(root / 'src/rp_v133_police.c'), str(root / 'src/rp_v133_police_tx.c'),
                    str(root / 'server/rp_authority_ffi.c'), '-o', str(args.output.resolve())], check=True)
    print(args.output.resolve())


if __name__ == '__main__':
    main()
