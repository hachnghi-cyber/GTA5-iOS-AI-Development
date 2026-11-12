#!/usr/bin/env python3
"""Heuristic crash triage; no dSYM symbolication or proof of root cause."""
import argparse
import json
import re
import zipfile
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024

def triage_text(text, source=""):
    return {"source": source,
            "signals": sorted(set(s.upper() for s in re.findall(
                r"\bSIG(?:SEGV|ABRT|TRAP|BUS|ILL)\b", text, re.I))),
            "devices": sorted(set(re.findall(r"\bi(?:Phone|Pad)\d{1,3},\d+\b", text))),
            "evidence_lines": [s[:400] for s in text.splitlines() if re.search(
                r"SIGSEGV|SIGABRT|SIGTRAP|pc=|lr=|thread|uuid|exception", s, re.I)][:75],
            "status": "heuristic-not-symbolicated"}

def triage(path):
    path = Path(path)
    if zipfile.is_zipfile(path):
        result = []
        with zipfile.ZipFile(path) as z:
            for item in z.infolist():
                if item.is_dir() or item.file_size > MAX_BYTES:
                    continue
                if not item.filename.lower().endswith((".log", ".txt", ".ips", ".crash")):
                    continue
                with z.open(item) as f:
                    result.append(triage_text(f.read(MAX_BYTES).decode("utf8", "replace"), item.filename))
                if len(result) == 30:
                    break
        return {"reports": result}
    with path.open("rb") as f:
        return triage_text(f.read(MAX_BYTES).decode("utf8", "replace"), str(path))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("log")
    p.add_argument("--output")
    a = p.parse_args()
    text = json.dumps(triage(a.log), ensure_ascii=False, indent=2) + "\n"
    if a.output:
        dest = Path(a.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf8")
    print(text)

if __name__ == "__main__":
    main()
