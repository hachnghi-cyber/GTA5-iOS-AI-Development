#!/usr/bin/env python3
"""Stage-gate evaluator. Never infers visible gameplay from native call logs.
Input must be files EXTRACTED FROM THE APP SANDBOX on physical iPhones.
A plaintext 'platform=iphoneos-target' marker is diagnostic, not attestation.
"""
import argparse
import json
import re
from pathlib import Path

def latest_run(content):
    anchor='[RBP_PROBE] RUN_BEGIN phase=4'
    pos=content.rfind(anchor)
    return '' if pos<0 else content[pos:]

def check_e0(run,stage):
    needed=[f'RUN_BEGIN phase=4 stage={stage} platform=iphoneos-target',
            f'DLLMAIN_ATTACH stage={stage}',
            'SCRIPT_HOOK_UUID_MATCH=1',
            'SCRIPT_REGISTER_ATTEMPTED',
            f'SCRIPT_CALLBACK_ENTER stage={stage}',
            'SCRIPT_TICK tick=1']
    result={x:(x in run) for x in needed}
    # A successful earlier callback marker cannot override a subsequent failure.
    fail_closed=('FAIL_CLOSED', 'SCRIPT_WAIT_FAST_RETURN=1',
                 'SHV_SYMBOL_RESOLUTION_FAILED', 'SCRIPT_HOOK_UUID_MATCH=0')
    result['no_script_fail_closed']=not any(marker in run for marker in fail_closed)
    return result

def assess(stage,b_log,a_log=None,visual_observed=False):
    b=latest_run(b_log)
    reasons=[]
    checks={'B_E0':check_e0(b,stage)}
    if not all(checks['B_E0'].values()):
        reasons.append('E0 device log prerequisites not met')
    if stage>=1:
        checks['B_local_native_invoked']='LOCAL_E1_GAME_ACTION_INVOKED=1' in b
        if not checks['B_local_native_invoked']:reasons.append('E1 native invocation missing')
    if stage==3:
        a=latest_run(a_log or '')
        checks['A_E0']=check_e0(a,3)
        def sequences(contents, expression):
            return {int(m.group(1)) for m in re.finditer(expression,contents)}
        transmitted=sequences(a,r'(?m)^\[RBP_NET\] PACKET_TRANSMITTED seq=(\d+) attempt=\d+\s*$')
        acked=sequences(a,r'(?m)^\[RBP_NET\] ACK_VERIFIED seq=(\d+) \(queue receipt ONLY\)\s*$')
        received=sequences(b,r'(?m)^\[RBP_NET\] PACKET_ACCEPTED seq=(\d+) ack_sent=1\s*$')
        invoked=sequences(b,r'(?m)^\[RBP_PROBE\] REMOTE_E3_GAME_ACTION_INVOKED=1 seq=(\d+) tick=\d+ thread=\S+\s*$')
        queued=sequences(b,r'(?m)^\[RBP_PROBE\] NATIVE_INVOCATION_REPORT_QUEUED=1 seq=(\d+) \(NOT visual proof\)\s*$')
        reported=sequences(b,r'(?m)^\[RBP_NET\] NATIVE_INVOCATION_REPORT_SENT=1 seq=(\d+) \(API call only\)\s*$')
        verified=sequences(a,r'(?m)^\[RBP_NET\] NATIVE_INVOCATION_REPORT_VERIFIED seq=(\d+) \(native API invoked, NOT HUD observed\)\s*$')
        # All seven phases must match the SAME sequence in this latest run.
        # This checks log consistency, not device provenance or RAGE replication.
        common=transmitted & acked & received & invoked & queued & reported & verified
        checks['A_udp_transmitted']=bool(transmitted)
        checks['A_queue_ack_verified']=bool(acked)
        checks['B_udp_accepted']=bool(received)
        checks['B_remote_native_invoked']=bool(invoked)
        checks['B_native_report_queued']=bool(queued)
        checks['B_native_report_sent']=bool(reported)
        checks['A_native_report_verified']=bool(verified)
        checks['same_sequence_correlated_A_B']=bool(common)
        matched_sequences=sorted(common)
        if not all(checks['A_E0'].values()) or not all(checks[k] for k in (
            'A_udp_transmitted','A_queue_ack_verified','B_udp_accepted',
            'B_remote_native_invoked','B_native_report_queued','B_native_report_sent',
            'A_native_report_verified','same_sequence_correlated_A_B')):
            reasons.append('E3 two-device event/ACK/native-report pipeline not established with matching sequence')
    if stage>=1 and not visual_observed:
        reasons.append('visual gameplay observation not provided; native log alone is not gameplay proof')
    def all_pass(obj):
        return all(all_pass(x) for x in obj.values()) if isinstance(obj,dict) else obj is True
    result={
        'stage':stage,
        'observations':checks,
        'matched_sequence_ids':matched_sequences if stage==3 else [],
        'all_log_preconditions_met':all_pass(checks),
        'visual_observed_user_assertion':visual_observed,
        'evidence_level':'LOGS_PLUS_MANUAL_VISUAL' if stage>=1 and visual_observed and all_pass(checks)
            else 'DEVICE_LOG_ONLY' if all_pass(checks) else 'INCOMPLETE',
        'not_a_cryptographic_device_attestation':True,
        'rage_multiplayer_replication_verified':False,
        'blockers':reasons
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--stage',type=int,choices=(0,1,3),required=True)
    p.add_argument('--b-log',type=Path,required=True)
    p.add_argument('--a-log',type=Path)
    p.add_argument('--visual-observed',action='store_true',
                   help='Manual assertion after capturing B screen; never inferred from log')
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    if a.stage==3 and not a.a_log:p.error('E3 needs both sender and receiver logs')
    report=assess(a.stage,a.b_log.read_text(errors='replace'),
                  a.a_log.read_text(errors='replace') if a.a_log else None,
                  a.visual_observed)
    encoded=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.out:a.out.write_text(encoded)
    print(encoded,end='')
    return 0 if report['all_log_preconditions_met'] and (a.stage==0 or a.visual_observed) else 2
if __name__=='__main__':raise SystemExit(main())
