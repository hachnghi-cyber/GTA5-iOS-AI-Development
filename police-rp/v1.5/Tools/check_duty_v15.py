#!/usr/bin/env python3
"""Analyze on-device Police RP v1.5 duty probe; no network and no gameplay."""
from pathlib import Path
import argparse
import json
import re

HEADER = re.compile(r'^\[PRP_DIAG_V15\] dylib_loaded=1 gta5_uuid_verified=(?P<uuid>[01]) hooks=0 network_events=0 police_gameplay=0 timer=main_queue_1s$')
SAMPLE = re.compile(r'^\[PRP_DUTY_V15\] tick=(\d+) job=(-?\d+) shift=([01]) police_active=([01]) label=(\w+)$')
LABELS = {-1:'none',0:'cop_ls',1:'cop_sandy',2:'cop_paleto'}

def analyse(text: str) -> dict:
    lines=[s.strip() for s in text.splitlines()]
    headers=[m for s in lines if (m:=HEADER.fullmatch(s))]
    if not headers or headers[-1]['uuid']!='1':
        return {'status':'LOAD_NOT_VERIFIED','police_transition_seen':False,'samples':0}
    samples=[]
    for line in lines:
        m=SAMPLE.fullmatch(line)
        if not m: continue
        tick, job, shift, active=map(int,m.groups()[:4]); label=m.group(5)
        if active != int(job in (0,1,2) and shift==1):
            return {'status':'BAD_SAMPLE','police_transition_seen':False,'samples':len(samples)}
        if LABELS.get(job,'other') != label:
            return {'status':'BAD_SAMPLE','police_transition_seen':False,'samples':len(samples)}
        samples.append({'tick':tick,'job':job,'shift':shift,'police_active':active,'label':label})
    if not samples:
        return {'status':'TIMER_NO_SAMPLES','police_transition_seen':False,'samples':0}
    transitioned=any(a['police_active'] != b['police_active'] for a,b in zip(samples,samples[1:]))
    return {'status':'DUTY_TRANSITION_OBSERVED' if transitioned else 'SAMPLES_OK_NO_TRANSITION',
            'police_transition_seen':transitioned,'samples':len(samples),
            'first':samples[0],'last':samples[-1]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('file',type=Path)
    args=p.parse_args()
    print(json.dumps(analyse(args.file.read_text(encoding='utf-8',errors='replace')),ensure_ascii=False,indent=2))
if __name__ == '__main__': main()
