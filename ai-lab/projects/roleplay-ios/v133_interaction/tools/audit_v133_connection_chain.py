#!/usr/bin/env python3
"""Exact GTA V iOS v13.3 connection-handle / decrypt-boundary static audit.
READ ONLY: no network hook, gameplay calls, source authentication or IPA patch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile

BASE=0x100000000
SHA256="f4b5e98efa44227dba8fb357dce02d3a42faac3328a7ce867edafba5916cddfc"
UUID="eb122c3596f4307f91c3a2255dd9c685"
PINS={
    0x101cd0794:0xb949e728, # CreateConnection counter read
    0x101cd0798:0x11000508, # increment
    0x101cd079c:0xb909e728, # counter store
    0x101cd07c4:0x53103d08, # move allocation marker to upper 16
    0x101cd0854:0x2a0801b8, # combine with slot
    0x101cd0938:0x290252d8, # store connection id at Cxn+0x10
    0x101cd131c:0x12003ea8, # CloseConnection low16 slot lookup
    0x101cd134c:0xb9401028, # read complete live 32-bit id
    0x101cd1350:0x6b15011f, # compare complete id
    0x101cd1354:0x540000c1, # reject mismatch
    0x102007b54:0xb9401800, # netPlayer connection id +0x18
    0x102024914:0xb9403c48, # OnNetEvent connection id +0x3c
    0x10202496c:0xb940192b, # remote peer connection id +0x18
    0x102024970:0x6b0a017f, # compare ids
    0x102024974:0x54000080, # equal branch
    0x101cd5f34:0x940097da, # GetP2pKey
    0x101cd5f98:0x940027d3, # P2P decrypt path
    0x101cd6110:0x94002775, # tunnel decrypt path
    0x101cd6124:0x36000160, # tunnel packet predicate
    0x101cd6128:0x52800008, # successful tunnel out flag=0
    0x101cd612c:0x390002c8, # write out flag
    0x101cd6130:0x52800020, # successful return=1
    0x101cd770c:0x97fff9e6, # HandleReceivedPacket -> P2pDecrypt
    0x101cd7710:0x34000500, # return==0 => reject
    0x101cd7794:0x39406fe4, # pass out flag in w4 to Unpack
    0x101cd77a8:0x97fffaa2, # Unpack call
    0x1019d255c:0x9102a000, # snSession::GetSessionId adds rlSession +0xa8
    0x1019d2560:0x140e6356, # tail branch into rlSession::GetId
    0x101d6b2b8:0xf9429000, # rlSession::GetId loads 64-bit ID at +0x520
    0x1019d62f0:0x91312000, # GetPeerCxn accesses rlPeerInfo member
    0x1019d62f8:0xeb00029f, # GetPeerCxn compares peer ID
    0x1019d6300:0x91310268, # GetPeerCxn selects local connection field
    0x1019d6304:0xb9400100, # GetPeerCxn reads 32-bit connection
    0x1019d6310:0xb8756a68, # GetPeerCxn remote peer list count
    0x1019d632c:0x91002100, # GetPeerCxn remote peer info
    0x1019d6330:0x940e3a1b, # GetPeerCxn remote peer ID getter
    0x1019d6334:0xeb14001f, # GetPeerCxn peer ID compare
    0x1019d6358:0x12800000, # GetPeerCxn missing peer returns -1
    0x1019d30f0:0x91312000, # GetPeerEndpointId peer info
    0x1019d30f8:0xeb00029f, # GetPeerEndpointId ID compare
    0x1019d3100:0x91310268, # GetPeerEndpointId select field
    0x1019d3104:0xb941e100, # GetPeerEndpointId endpoint field DIFFERENT from connection
    0x1019d3110:0xb8756a68, # GetPeerEndpointId remote peer count
    0x1019d312c:0x91002100, # GetPeerEndpointId remote peer info
    0x1019d3130:0x940e469b, # GetPeerEndpointId remote peer getter
    0x1019d3134:0xeb14001f, # GetPeerEndpointId remote peer compare
    0x1019d3158:0x12800000, # GetPeerEndpointId missing returns -1
    0x1020249a8:0xa9012be9, # OnNetEvent copies sender + local pointers
    0x1020249b8:0x940005d7, # remote OnNetEvent dispatch
    0x101ffeecc:0x94009c92, # LOCAL SendBuffer dispatch same delegate
    0x1019d2ee8:0x940e3fb5, # snSession::IsMember compares gamer IDs
}
class AuditError(ValueError):pass

def macho_uuid(binary):
    if len(binary)<32:raise AuditError("truncated Mach-O")
    magic,cpu,_,kind,ncmds,sizeofcmds,_,_=struct.unpack_from("<8I",binary)
    if (magic,cpu,kind)!=(0xfeedfacf,0x0100000c,2):
        raise AuditError("wrong Mach-O CPU/type")
    if not 1<=ncmds<=1024 or not 24<=sizeofcmds<=1048576 or sizeofcmds+32>len(binary):
        raise AuditError("bad load command bounds")
    off=32; uuids=[]
    for _ in range(ncmds):
        if off+8>sizeofcmds+32:raise AuditError("truncated command")
        op,size=struct.unpack_from("<II",binary,off)
        if size<8 or size%8 or off+size>sizeofcmds+32:
            raise AuditError("invalid command")
        if op==0x1b:
            if size!=24:raise AuditError("invalid UUID command")
            uuids.append(binary[off+8:off+24].hex())
        off+=size
    if len(uuids)!=1:raise AuditError("missing/duplicate UUID")
    return uuids[0]

def verify_pins(word_at):
    for address,opcode in PINS.items():
        if word_at(address)!=opcode:
            raise AuditError("opcode mismatch at "+hex(address))

def audit(binary):
    if hashlib.sha256(binary).hexdigest()!=SHA256:
        raise AuditError("wrong GTA5 SHA256")
    if macho_uuid(binary)!=UUID:
        raise AuditError("wrong GTA5 UUID")
    def word(address):
        offset=address-BASE
        if offset<0 or offset+4>len(binary):raise AuditError("offset out of bounds")
        return struct.unpack_from("<I",binary,offset)[0]
    verify_pins(word)
    return {
        "status":"STATIC_CONNECTION_HANDLE_CHAIN_ONLY",
        "sha256":SHA256,
        "macho_uuid":"EB122C35-96F4-307F-91C3-A2255DD9C685",
        "pinned_instructions":len(PINS),
        "connection_id":"32-bit local allocation marker + slot; NOT an auth token",
        "close_connection_compares_full_id":True,
        "on_net_event_compares_event_and_peer_full_id":True,
        "decrypt_success_may_have_zero_out_flag":True,
        "authenticated_sender_verified":False,
        "session_id_read_is_64bit_static":True,
        "peer_connection_and_endpoint_are_distinct_fields":True,
        "peer_lookup_not_found_returns_minus_one":True,
        "local_send_buffer_reaches_same_delegate":True,
        "connection_session_identity_is_static_candidate_only":True,
        "connection_lifetime_on_iphone_verified":False,
        "session_incarnation_verified":False,
        "remote_gameplay_verified":False,
        "safe_to_enable_roleplay":False,
    }

def load(path):
    if path.suffix.lower()==".ipa":
        with zipfile.ZipFile(path) as z:
            info=z.getinfo("Payload/GTAV.app/GTA5")
            if info.file_size>128*1024*1024:raise AuditError("oversized binary")
            return z.read(info)
    if path.stat().st_size>128*1024*1024:raise AuditError("oversized binary")
    return path.read_bytes()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("file",type=Path,help="Locally-owned ORIGINAL GTA v13.3 IPA or extracted GTA5; never upload")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    try:
        report=audit(load(args.file));code=0
    except (AuditError,OSError,KeyError,zipfile.BadZipFile) as ex:
        report={"status":"REJECTED","error":str(ex)};code=1
    result=json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.out:args.out.write_text(result,encoding="utf8")
    print(result,end="")
    return code
if __name__=="__main__":raise SystemExit(main())
