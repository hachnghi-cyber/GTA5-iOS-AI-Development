#!/usr/bin/env python3
"""Reconstruct pinned v1.6 duplex core and safely overlay it onto GTA5Port source.
Reads only code from a SHA-256 pinned tar.xz bundle, never game data.
"""
import argparse,base64,hashlib,io,json,lzma,os,shutil,tarfile,tempfile
from pathlib import Path

BUNDLE_SHA='a88c9463e183eba4f09455cdaf43d0fe80bebabc40c3e57717b37cb441c95c65'
BASE_C_SHA='1baf7a796fc09e8477e43f38c2b213e0fd96e7a6492552dbf3a442c63e17b904'
NEW_C_SHA='80c1e6e42b43617570e07a55548be6f98400f4163a7fc00d9b0dd99802b5e7af'
BACKUP='.rp-source-bridge-v17-backup'
SWIFT='app/App/NativePortViewController.swift'
HEADER='app/Source/Native-Bridging-Header.h'
WORLD='        if line == "WORLD_READY" { PGSetTargetingMode(Int32(GameSettings.shared.targetingMode)); PGSetSelfRadioMode(Int32(GameSettings.shared.selfRadioMode)); if worldReadyAt == nil { worldReadyAt = CACurrentMediaTime() } }\n'
LEAVE='        leftAppHandled = true\n        RunEnd.playing(false)\n'


def sha(data):return hashlib.sha256(data).hexdigest()


def materialize(payload):
    raw=lzma.decompress(base64.b64decode(Path(payload).read_text().strip(),validate=True))
    if sha(raw)!=BUNDLE_SHA:raise ValueError('v1.6 source tar SHA256 mismatch')
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        files={}
        for key in ('src/RPBridgeDuplexV16.c','src/rp16_json.c','src/rp16_json.h'):
            member=tar.getmember(key)
            if not member.isfile() or member.name!=key:raise ValueError('unsafe tar member')
            files[key]=tar.extractfile(member).read()
    c=files['src/RPBridgeDuplexV16.c'].decode()
    if sha(c.encode())!=BASE_C_SHA:raise ValueError('unexpected v1.6 C source')
    old='(void)ignore;g_home=getenv("HOME");'
    c=c.replace(old,'(void)ignore;if(!g_home)g_home=getenv("HOME");')
    start=c.index('#ifndef RP_BRIDGE_NO_CONSTRUCTOR\n__attribute__((constructor))')
    end=c.index('#ifdef RP_BRIDGE_TEST_API',start)
    c=c[:start]+'''/* Explicit lifecycle managed by Swift after WORLD_READY, not a dylib constructor.
   Compile this source as part of the port's native host target. */
static atomic_int bridge_started=0;
static char bridge_home[PATH_MAX];
void PGRPBridgeStart(const char *home){
    if(!home||home[0]!='/')return;
    size_t len=strnlen(home,PATH_MAX);
    if(!len||len>PATH_MAX-64)return;
    int expected=0;
    if(!atomic_compare_exchange_strong(&bridge_started,&expected,1))return;
    memcpy(bridge_home,home,len+1);
    g_home=bridge_home;
    atomic_store(&stop_requested,0);
    pthread_t thread;
    if(pthread_create(&thread,NULL,worker,NULL)!=0){
        g_home=NULL;
        atomic_store(&bridge_started,0);
        return;
    }
    pthread_detach(thread);
}
void PGRPBridgeStop(void){atomic_store(&stop_requested,1);}
'''+c[end:]
    if sha(c.encode())!=NEW_C_SHA:raise ValueError('source v1.7 reconstructed checksum mismatch')
    return {
        'app/Source/NativeRPBridge.c':c.encode(),
        'app/Source/NativeRPBridge.h':b'#pragma once\n/* Opt-in LAN pose diagnostics (no RAGE hooks, no gameplay commands).\n   Called only after the native port reports WORLD_READY in Story Mode. */\n#ifdef __cplusplus\nextern "C" {\n#endif\nvoid PGRPBridgeStart(const char *sandbox_home);\nvoid PGRPBridgeStop(void);\n#ifdef __cplusplus\n}\n#endif\n',
        'app/Source/rp16_json.c':files['src/rp16_json.c'],
        'app/Source/rp16_json.h':files['src/rp16_json.h']}


def install(root,payload,check=False):
    root=Path(root).resolve()
    if not (root/'app/project.yml').is_file() or 'name: PlayGTA5Native' not in (root/'app/project.yml').read_text():
        raise ValueError('not a GTA5Port iOS source tree')
    native=materialize(payload)
    swift=(root/SWIFT).read_text()
    header=(root/HEADER).read_text()
    if 'GTA5PORT_RP_SOURCE_V17' in swift or 'NativeRPBridge.h' in header:
        if (swift.count('PGRPBridgeStart(')==1 and swift.count('PGRPBridgeStop()')==1 and
            'NativeRPBridge.h' in header and all((root/k).is_file() and (root/k).read_bytes()==v for k,v in native.items())):
            return []
        raise ValueError('partial or modified RP source overlay detected')
    if swift.count(WORLD)!=1 or swift.count(LEAVE)!=1 or header.count('#include "EngineHost.h"')!=1:
        raise ValueError('upstream Swift/header anchor changed; refusing unsafe edits')
    if any((root/k).exists() for k in native):raise ValueError('existing native files conflict')
    swift=swift.replace(WORLD,WORLD+'''        // GTA5PORT_RP_SOURCE_V17: explicit opt-in, Story Mode only, after WORLD_READY.
        if line == "WORLD_READY", bootedMode == .story, !ModGuard.startsWithoutMods {
            NSHomeDirectory().withCString { PGRPBridgeStart($0) }
        }
''')
    swift=swift.replace(LEAVE,'''        leftAppHandled = true
        // GTA5PORT_RP_SOURCE_V17: do not send pose in the background.
        PGRPBridgeStop()
        RunEnd.playing(false)
''')
    changes={SWIFT:swift.encode(),HEADER:(header.rstrip()+'\n\n#include "NativeRPBridge.h"\n').encode(),**native}
    if check:return list(changes)
    backup=root/BACKUP
    if backup.exists():raise ValueError('existing backup; refusing to overwrite')
    backup.mkdir(mode=0o700)
    manifest={}
    try:
        for name,new in changes.items():
            old=(root/name).read_bytes() if (root/name).exists() else None
            manifest[name]={'old':sha(old) if old is not None else None,'new':sha(new)}
            if old is not None:
                out=backup/name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(old)
        (backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
        for name,new in changes.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(new)
    except BaseException:
        for name in changes:
            path=root/name;old=backup/name
            if old.exists():path.write_bytes(old.read_bytes())
            elif path.exists():path.unlink()
        shutil.rmtree(backup,ignore_errors=True)
        raise
    return list(changes)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('upstream',type=Path)
    p.add_argument('--payload',type=Path,required=True,help='Checked-in native-bridge-v16/source_bundle.tar.xz.b64')
    p.add_argument('--check',action='store_true')
    args=p.parse_args()
    try:
        files=install(args.upstream,args.payload,check=args.check)
        print(json.dumps({'mode':'check' if args.check else 'apply','files':files,'already_integrated':not files},indent=2))
    except (ValueError,OSError,tarfile.TarError,EOFError) as exc:
        p.error(str(exc))

if __name__=='__main__':main()
