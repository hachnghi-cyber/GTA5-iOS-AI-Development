#!/usr/bin/env python3
"""Resolve one valid Apple Development identity; never sign by an ambiguous name.

Input: stdout from 'security find-identity -v -p codesigning' on macOS.
Output: a single uppercase SHA-1 certificate fingerprint for codesign --sign.
A second check must match that fingerprint to provisioning DeveloperCertificates.
"""
import argparse
import re
import sys
from pathlib import Path

LINE=re.compile(r'^\s*\d+\)\s+([0-9a-fA-F]{40})\s+"([^"]+)"\s*$')
HEX=re.compile(r'^[0-9a-fA-F]{40}$')
class IdentityError(ValueError):pass

def resolve(content,selector):
    if not isinstance(selector,str) or not selector.strip() or selector!=selector.strip():
        raise IdentityError("empty or whitespace-padded identity selector")
    matches=[]
    for line in content.splitlines():
        m=LINE.fullmatch(line)
        if m:matches.append((m[1].upper(),m[2]))
    if HEX.fullmatch(selector):
        matches=[x for x in matches if x[0]==selector.upper()]
    else:
        if not selector.startswith("Apple Development: "):
            raise IdentityError("require exact Apple Development label or 40-hex SHA1")
        matches=[x for x in matches if x[1]==selector]
    if len(matches)!=1:
        raise IdentityError("identity must match exactly one VALID Keychain entry")
    return matches[0][0]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--identity-list",type=Path,required=True)
    ap.add_argument("--identity",required=True)
    a=ap.parse_args()
    try:
        result=resolve(a.identity_list.read_text(encoding="utf-8"),a.identity)
    except (IdentityError,OSError) as exc:
        print("REJECTED: "+str(exc),file=sys.stderr)
        return 2
    print(result)
    return 0
if __name__=="__main__":sys.exit(main())
