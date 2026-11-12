#!/usr/bin/env python3
"""Read-only source and documentation inventory for GTA V iOS Roleplay.

It does not build, import, decompile or execute any game/mod binary.
"""
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

SOURCE_EXT = {".c", ".h", ".cc", ".cpp", ".hpp", ".mm", ".m", ".cs", ".swift"}
TEST_PREFIXES = ("test_", "tests/")
DOC_EXT = {".md", ".txt"}
CONFIG_EXT = {".json", ".yaml", ".yml", ".ini", ".plist"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".ipa"}
EXCLUDE_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
MAX_HASH_SIZE = 32 * 1024 * 1024

def classify(relative):
    name = relative.name.lower()
    parts = {p.lower() for p in relative.parts}
    if name.startswith("test_") or "tests" in parts:
        return "test"
    if relative.suffix.lower() in SOURCE_EXT:
        return "source"
    if relative.suffix.lower() in DOC_EXT:
        return "documentation"
    if relative.suffix.lower() in CONFIG_EXT:
        return "config-or-evidence"
    if relative.suffix.lower() in ARCHIVE_EXT:
        return "archive-not-inspected"
    return "other"

def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def inventory(root):
    root = Path(root).resolve()
    subtree = root / "police-rp"
    if not subtree.is_dir():
        raise FileNotFoundError("Missing police-rp directory under " + str(root))
    files = []
    for current, dirs, names in os.walk(subtree, followlinks=False):
        dirs[:] = sorted(d for d in dirs
                         if d not in EXCLUDE_DIRS
                         and not (Path(current) / d).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if not path.is_file() or path.is_symlink() or path.suffix.lower() == ".pyc":
                continue
            relative = path.relative_to(root)
            role_relative = relative.relative_to("police-rp")
            size = path.stat().st_size
            category = classify(role_relative)
            item = {"path": relative.as_posix(), "size_bytes": size,
                    "category": category,
                    "version_directory": role_relative.parts[0] if len(role_relative.parts) > 1 else "(root)"}
            if size <= MAX_HASH_SIZE:
                item["sha256"] = hash_file(path)
            else:
                item["sha256"] = None
                item["note"] = "not hashed: larger than 32MiB"
            files.append(item)
    totals = Counter(x["category"] for x in files)
    versions = Counter(x["version_directory"] for x in files)
    return {
        "schema_version": 1,
        "scope": "police-rp/",
        "status": "source-inventory-only-not-executed-or-device-tested",
        "summary": {"files": len(files),
                    "total_bytes": sum(x["size_bytes"] for x in files),
                    "categories": dict(sorted(totals.items())),
                    "version_directories": dict(sorted(versions.items()))},
        "cautions": [
            "Source-file existence does not establish feature completeness or engine integration.",
            "This inventory never decompiles IPA or inspects archived mod contents.",
            "A successful Python CI result is not evidence of an iPhone game build."
        ],
        "files": files
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--output")
    args = p.parse_args()
    report = inventory(args.root)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
