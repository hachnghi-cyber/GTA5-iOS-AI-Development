"""Read-only GTA v13.3 netPlayer <-> snSession connection/peer correlation.

Inputs are externally stopped-process memory snapshots, NOT wire-provided
identities. No hooks, GTA function calls, writes or police actions.
An internally consistent mapping is NOT an authenticated RAGE sender.
"""
MAX_PEERS=32
U64MAX=(1<<64)-1

def transport_peer_status(read64, player_info, session_peer):
    """Compare the embedded transport identities within their own domain."""
    try:
        player_transport = read64(player_info + 0x20)
        session_transport = read64(session_peer + 8)
        if not 0 < player_transport < U64MAX or not 0 < session_transport < U64MAX:
            return "invalid_transport_peer_metadata"
        if player_transport != session_transport:
            return "transport_peer_metadata_mismatch"
    except (KeyError, TypeError, ValueError, RuntimeError, OverflowError, IndexError):
        return "read_failed"
    return "match"

def endpoint_status(read32, player, session_peer):
    """Compare local endpoint IDs, keeping them distinct from connection IDs."""
    try:
        player_endpoint = read32(player + 0x1c)
        session_endpoint = read32(session_peer + 0x1e0)
        if not 0 < player_endpoint < 0xffffffff or not 0 < session_endpoint < 0xffffffff:
            return "invalid_endpoint_metadata"
    except (KeyError, TypeError, ValueError, RuntimeError, OverflowError, IndexError):
        return "read_failed"
    return "match" if player_endpoint == session_endpoint else "mismatch"

def check_peer_session_map(read32,read64,netplayer,session,conn,expected_getter,expected_peer_id=None,
                           *,check_transport_domain=False):
    r={"schema":"v133-peer-session-map-v1","status":"invalid_input",
       "peer_map_consistent":False,"remote_entries_seen":0,
       "transport_peer_map_consistent":False,
       "authenticated_rage_sender_verified":False,
       "session_membership_verified":False,
       "session_generation_verified":False}
    if not all(isinstance(x,int) and x>0 for x in
               (netplayer,session,expected_getter)):
        return r
    if not isinstance(conn,int) or conn<=0 or conn>0x7fffffff:
        return r
    try:
        if read32(netplayer+0x18)!=conn:
            r["status"]="netplayer_connection_mismatch";return r
        vtable=read64(netplayer)
        if not vtable or read64(vtable+0x38)!=expected_getter:
            r["status"]="unexpected_gamer_info_vtable";return r
        pinfo=read64(netplayer+0xa0)
        if not pinfo:
            r["status"]="missing_player_info";return r
        peer=read64(pinfo+0x1f0) # +0x20 rlGamerInfo, +0x1d0 rlPeerInfo
        if peer==0 or peer==U64MAX:
            r["status"]="invalid_netplayer_peer";return r
        # At verified OnConnectionEvent+0x654 x1 contains the result of
        # netPlayer::GetRlPeerId from the SAME native callback.
        if expected_peer_id is not None and peer!=expected_peer_id:
            r["status"]="same_callback_peer_register_mismatch";return r
        count=read32(session+0xba30)
        if not 1<=count<=MAX_PEERS:
            r["status"]="session_peer_count_out_of_bounds";return r
        r["session_remote_peer_count"] = count
        matched=0
        matched_entry=None
        for i in range(count):
            p=read64(session+0xb930+8*i)
            if not p:
                r["status"]="null_session_peer";return r
            cxn=read32(p)
            pid=read64(p+0x1d8)
            r["remote_entries_seen"]+=1
            if pid==0 or pid==U64MAX or cxn>0x7fffffff:
                r["status"]="invalid_session_entry";return r
            if cxn==conn:
                matched+=1
                matched_entry=p
                if pid!=peer:
                    r["status"]="connection_to_peer_mismatch";return r
            elif pid==peer:
                r["status"]="peer_alias_different_connection"
                if check_transport_domain:
                    r["alias_transport_peer_status"] = transport_peer_status(read64, pinfo, p)
                    if r["alias_transport_peer_status"] == "match":
                        r["alias_endpoint_status"] = endpoint_status(read32, netplayer, p)
                return r
        if matched!=1:
            r["status"]="no_unique_session_connection";return r
        if check_transport_domain:
            # rlGamerInfo starts at CPlayerInfo+0x20. Its embedded netPeerAddress
            # starts at offset zero; rlPeerInfo::GetPeerId instead reads +0x1d0.
            # Compare each identity within its own domain, never across them.
            transport_status = transport_peer_status(read64, pinfo, matched_entry)
            if transport_status != "match":
                r["status"] = transport_status
                return r
            r["transport_peer_map_consistent"]=True
        r["status"]="session_connection_peer_candidate_only"
        r["peer_map_consistent"]=True
    except (KeyError,TypeError,ValueError,RuntimeError,OverflowError,IndexError):
        r["status"]="read_failed"
    return r
