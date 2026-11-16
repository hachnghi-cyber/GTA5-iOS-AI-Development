#!/usr/bin/env python3
"""Classify E0 bootstrap failures using actual ScriptHook posthook + RBP logs.
Static evidence from the v13.3 ScriptHookV binary identifies loader message strings.
Plain text is diagnostic evidence, NOT cryptographic proof it came from iPhone.
"""
import argparse
import json
from pathlib import Path
if __package__:
    from .evaluate_device_logs import latest_run
else:
    from evaluate_device_logs import latest_run


def analyze_loader(posthook_log: str, probe_log: str):
    probe=latest_run(probe_log)
    # A posthook file can contain old boot messages. Prefer the most recent
    # loader-related record instead of treating an old OFF/failure as current.
    lines=posthook_log.splitlines()
    off_at=max((i for i,line in enumerate(lines) if
                '[shv] off by setting: no plugins, no tick' in line or
                'Script Hook is OFF' in line),default=-1)
    ready_at=max((i for i,line in enumerate(lines) if
                  'Script Hook ready:' in line or
                  'loaded plugin RBPProbe.shv.dylib' in line),default=-1)
    failed_at=max((i for i,line in enumerate(lines) if
                   "couldn't load plugin" in line and 'RBPProbe.shv.dylib' in line),default=-1)
    shv_load_at=max((i for i,line in enumerate(lines) if
                     'loaded plugin RBPProbe.shv.dylib' in line),default=-1)
    disabled=off_at>=0 and off_at>ready_at
    fail_load=failed_at>=0 and failed_at>shv_load_at
    shv_load=shv_load_at>=0 and shv_load_at>failed_at
    start='RUN_BEGIN phase=4 stage=0 platform=iphoneos-target' in probe
    uuid_match='SCRIPT_HOOK_UUID_MATCH=1' in probe
    attempted='SCRIPT_REGISTER_ATTEMPTED' in probe
    callback='SCRIPT_CALLBACK_ENTER stage=0' in probe
    tick='SCRIPT_TICK tick=1' in probe
    if disabled:
        classification='SHV_DISABLED_BY_SETTING'
        suggestion='Enable ScriptHook using the port UI and restart. Do not patch the game.'
    elif fail_load:
        classification='DYLD_OR_LOADER_PLUGIN_LOAD_FAILED'
        suggestion='Read the exact posthook dlopen error: signature, dependency, path or architecture.'
    elif not shv_load and not start:
        classification='LOADER_NOT_OBSERVED'
        suggestion='Check whether ScriptHookV initialized, scan path and whether posthook log is current.'
    elif shv_load and not start:
        classification='PLUGIN_LOADED_BUT_DLLMAIN_NOT_OBSERVED'
        suggestion='Inspect DllMain symbol/calling convention, logging path and loader output.'
    elif start and not uuid_match:
        classification='SCRIPT_HOOK_UUID_OR_SYMBOL_CHECK_FAILED'
        suggestion='Check SHV runtime image UUID and path; do not reuse offsets from another build.'
    elif attempted and not callback:
        classification='SCRIPT_REGISTRATION_ATTEMPTED_NO_CALLBACK'
        suggestion='Inspect actual ScriptHook tick logs, 64-slot capacity and scheduler/Story versus Online state.'
    elif callback and not tick:
        classification='CALLBACK_ENTERED_BUT_FIRST_TICK_NOT_OBSERVED'
        suggestion='Inspect scriptWait/ScriptHook scheduler and crash/stall logs.'
    elif callback and tick:
        classification='E0_LOG_PREREQUISITES_OBSERVED'
        suggestion='Still requires provenance and device validation; proceed to E1 only if from verified device logs.'
    else:
        classification='INCOMPLETE_UNCLASSIFIED'
        suggestion='Collect current posthook.log, RBPProbe.log and crash reports.'
    return {
        'classification':classification,
        'checks':{'shv_disabled_log':disabled,'plugin_load_failed_log':fail_load,
                  'shv_loader_reported_plugin':shv_load,'probe_run_begin':start,
                  'uuid_match':uuid_match,'registration_attempted':attempted,
                  'callback_entered':callback,'first_script_tick':tick},
        'next_experiment':suggestion,
        'status':'LOG_CLASSIFICATION_ONLY',
        'not_proof_of_iphone_or_gameplay':True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--posthook-log',type=Path,required=True)
    ap.add_argument('--probe-log',type=Path,required=True)
    ap.add_argument('--out',type=Path)
    ns=ap.parse_args()
    res=analyze_loader(ns.posthook_log.read_text(errors='replace'),ns.probe_log.read_text(errors='replace'))
    payload=json.dumps(res,indent=2,ensure_ascii=False)+'\n'
    if ns.out:ns.out.write_text(payload)
    print(payload,end='')
    return 0

if __name__=='__main__':raise SystemExit(main())
