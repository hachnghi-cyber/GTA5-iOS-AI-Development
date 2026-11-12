#!/usr/bin/env python3
"""Fail-closed review gate for autonomous text-only Roleplay patches."""
import argparse
import subprocess
from pathlib import Path

ALLOWED = ("police-rp/", "ai-lab/tests/", "ai-lab/projects/roleplay-ios/")
FORBIDDEN = ("ai-lab/projects/roleplay-ios/baselines/",)
EXTS = {".c", ".h", ".cpp", ".hpp", ".mm", ".m", ".py", ".md", ".json", ".ini", ".cs"}
MAX_FILES = 12
MAX_BYTES = 131072

def check_paths(paths, diff_size, modes=None):
    if not paths or len(paths) > MAX_FILES:
        raise ValueError("Empty or oversized file selection")
    if diff_size > MAX_BYTES:
        raise ValueError("Patch exceeds 128 KiB")
    for name in paths:
        if (not name.startswith(ALLOWED) or name.startswith(FORBIDDEN)
                or ".." in name.split("/") or "\\" in name
                or Path(name).suffix.lower() not in EXTS):
            raise ValueError("Forbidden changed file: " + name)
        if modes and modes.get(name) not in (None, "100644"):
            raise ValueError("Forbidden file mode: " + name)
    return True

def inspect_checkout():
    def git(*args):
        return subprocess.check_output(["git", *args], text=True)
    status = git("diff", "--cached", "--name-status", "--no-renames")
    paths = []
    for entry in status.splitlines():
        operation, name = entry.split("\t", 1)
        if operation not in ("A", "M"):
            raise ValueError("Deletion or unsafe change blocked: " + entry)
        paths.append(name)
    patch = subprocess.check_output(["git", "diff", "--cached", "--binary"])
    modes = {}
    for row in git("ls-files", "--stage").splitlines():
        cols = row.split(None, 3)
        if len(cols) == 4:
            modes[cols[3]] = cols[0]
    check_paths(paths, len(patch), modes)
    if b"GIT binary patch" in patch or b"Binary files" in patch:
        raise ValueError("Binary patches not allowed")
    print("PASS:", len(paths), "text files, patch bytes:", len(patch))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check-staged", action="store_true")
    args = p.parse_args()
    if not args.check_staged:
        p.error("Use --check-staged")
    inspect_checkout()
