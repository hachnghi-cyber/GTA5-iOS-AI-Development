#!/usr/bin/env python3
"""Compile and execute existing Police RP v1.4 C tests on a HOST runner.

No GTA executable, IPA, iOS SDK, network socket or device is involved.
The result establishes host-side C contract coverage only.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2P = Path("police-rp/v1.4/P2P")
BRIDGE = Path("police-rp/v1.4/NativeBridge")
SOURCES = (
    P2P / "prp_p2p.c",
    P2P / "prp_runtime.c",
    BRIDGE / "police_rp_adapter.c",
    BRIDGE / "police_rp_only.c",
)
CASES = (
    ("p2p_packet_host_authority", P2P / "test_p2p.c"),
    ("runtime_session_and_consent", P2P / "test_runtime.c"),
    ("off_duty_releases_restraints", P2P / "test_duty_exit.c"),
    ("versioned_native_api_contract", P2P / "test_abi_contract.c"),
)
FLAGS = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_suite(root=ROOT, compiler=None):
    root = Path(root).resolve()
    if compiler is None:
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        raise RuntimeError("No host C compiler found (cc/clang/gcc)")
    required = SOURCES + tuple(path for _, path in CASES)
    missing = [str(p) for p in required if not (root / p).is_file()]
    if missing:
        raise FileNotFoundError("Missing required C sources: " + ", ".join(missing))
    evidence = [{"path":path.as_posix(), "sha256":_hash(root/path)} for path in required]
    report = {
        "schema_version": 1,
        "status": "host-tests-failed",
        "scope": "Police RP C host tests ONLY; not GTA engine, authenticated transport, iOS build or device",
        "compiler": compiler,
        "compiler_flags": list(FLAGS),
        "source_fingerprints": evidence,
        "cases": [],
        "gameplay_verified": False,
        "iphone_tested": False,
    }
    with tempfile.TemporaryDirectory(prefix="rp-host-tests-") as temp:
        for index, (name, test) in enumerate(CASES):
            binary = Path(temp) / ("test_" + str(index))
            command = [compiler, *FLAGS, *map(str, (root / s for s in SOURCES)),
                       str(root / test), "-lm", "-o", str(binary)]
            case = {"name":name, "source":test.as_posix(),
                    "compiled": False, "passed": False}
            report["cases"].append(case)
            try:
                built = subprocess.run(command, capture_output=True, text=True,
                                       timeout=60, check=False)
                case["compiled"] = built.returncode == 0
                if not case["compiled"]:
                    case["error"] = (built.stdout + built.stderr)[-4000:]
                    continue
                executed = subprocess.run([str(binary)], capture_output=True,
                                          text=True, timeout=30, check=False)
                case["passed"] = executed.returncode == 0
                case["output"] = (executed.stdout + executed.stderr)[-4000:]
                if not case["passed"]:
                    case["exit_code"] = executed.returncode
            except subprocess.TimeoutExpired:
                case["error"] = "compiler or test process timeout"
            except OSError as exc:
                case["error"] = type(exc).__name__ + ": " + str(exc)
    report["status"] = ("host-tests-passed" if all(c["passed"] for c in report["cases"])
                        else "host-tests-failed")
    report["passed_count"] = sum(c["passed"] for c in report["cases"])
    report["total_count"] = len(report["cases"])
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--compiler")
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    report = run_suite(root=args.root, compiler=args.compiler)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    return 0 if report["status"] == "host-tests-passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
