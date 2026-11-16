#!/usr/bin/env python3
"""Read-only correlation of stock loader and E0 callback logs.

TEXT CONSISTENCY ONLY: matching logs do not authenticate their device origin.
Do not upload raw game payloads, identifiers, secrets, or user account data.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from evaluate_e0_log import BEGIN, evaluate

STOCK_LOADED=re.compile(r'\[shv\] loaded plugin (.*?) \((\d+) scripts\)',re.I)
STOCK_FAILED=re.compile(r"\[shv\] couldn't load plugin (.*?):",re.I)
STOCK_TIME=re.compile(r'(?m)^\s*(\d\d):(\d\d):(\d\d)\s')
PLUGIN='RBPProbeE0.shv.dylib'

def basename(path: str) -> str:
    return path.replace('\\', '/').rsplit('/',1)[-1]

def compare(probe_log: str,posthook_log: str,tz_offset_minutes: int | None=None) -> dict:
    out={'status':'INCOMPLETE','stock_registration':False,
         'callback_log_consistent':False,'device_verified':False,
         'online_verified':False,'notes':[]}
    result=evaluate(probe_log)
    out['callback_log_consistent']=bool(result.get('pass'))
    if re.search(r'Script Hook is OFF|\[shv\] off by setting',posthook_log,re.I):
        out['status']='SHV_DISABLED'; return out
    if any(basename(m.group(1).strip())==PLUGIN for m in STOCK_FAILED.finditer(posthook_log)):
        out['status']='PLUGIN_DLOPEN_FAILURE'; return out
    entries=[m for m in STOCK_LOADED.finditer(posthook_log)
             if basename(m.group(1).strip())==PLUGIN]
    if not entries:
        out['status']='STOCK_LOADER_ENTRY_MISSING'; return out
    if len(entries)!=1:
        out['status']='AMBIGUOUS_STOCK_LOAD_ENTRIES'; return out
    entry=entries[0]
    delta=int(entry.group(2))
    out['script_registration_delta']=delta
    if delta!=1:
        out['status']='REGISTRATION_DELTA_NOT_ONE'; return out
    out['stock_registration']=True
    if not out['callback_log_consistent']:
        out['status']='STOCK_REGISTERED_BUT_E0_CALLBACK_UNVERIFIED'
        out['notes'].append(result.get('status','UNKNOWN'))
        return out
    if tz_offset_minutes is None:
        out['status']='LOG_CONSISTENT_UNCORRELATED_TIME';return out
    if not -840 <= tz_offset_minutes <= 840:
        out['status']='INVALID_TIMEZONE_OFFSET';return out
    run=list(BEGIN.finditer(probe_log))[-1]
    start_ms=int(run.group(2))
    line=posthook_log[posthook_log.rfind('\n',0,entry.start())+1:entry.start()]
    m=STOCK_TIME.match(line)
    if not m:
        out['status']='STOCK_LOG_TIME_UNAVAILABLE';return out
    try:
        local=datetime.fromtimestamp(start_ms/1000,
                  tz=timezone(timedelta(minutes=tz_offset_minutes)))
    except (ValueError,OverflowError,OSError):
        out['status']='INVALID_E0_TIMESTAMP';return out
    if not (int(m[1])<24 and int(m[2])<60 and int(m[3])<60):
        out['status']='INVALID_STOCK_LOG_CLOCK';return out
    a=local.hour*3600+local.minute*60+local.second
    b=int(m[1])*3600+int(m[2])*60+int(m[3])
    elapsed=(b-a+43200)%86400-43200
    if not -2 <= elapsed <= 30:
        out['status']='TIME_MISMATCH';return out
    out['status']='STOCK_AND_E0_LOGS_CONSISTENT_NOT_DEVICE_PROOF'
    out['notes'].append('Confirm source files came from the same fresh device run; text alone is forgeable')
    return out

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--probe',required=True,type=Path)
    ap.add_argument('--posthook',required=True,type=Path)
    ap.add_argument('--timezone-offset-minutes',type=int)
    args=ap.parse_args()
    try:
        r=compare(args.probe.read_text(encoding='utf8',errors='replace'),
                  args.posthook.read_text(encoding='utf8',errors='replace'),
                  args.timezone_offset_minutes)
    except OSError as exc:
        print(json.dumps({'status':'FILE_UNREADABLE','error':type(exc).__name__}))
        return 2
    print(json.dumps(r,sort_keys=True,indent=2))
    return 0 if r['status']=='STOCK_AND_E0_LOGS_CONSISTENT_NOT_DEVICE_PROOF' else 1

if __name__=='__main__':
    raise SystemExit(main())
