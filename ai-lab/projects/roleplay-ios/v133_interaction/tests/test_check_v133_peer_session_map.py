"""Synthetic memory snapshots only; no actual snSession pointer supplied."""
import importlib.util
import unittest
from pathlib import Path
path=Path(__file__).resolve().parents[1]/"tools"/"check_v133_peer_session_map.py"
spec=importlib.util.spec_from_file_location("map_check",path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class PeerMappingTests(unittest.TestCase):
    def fixture(self):
        player,session,getter=0x1000,0x7000,0x5000
        ptr_a,ptr_b=0x8000,0x9000
        mem={player+0x18:77,player:0x2000,0x2000+0x38:getter,
             player+0xa0:0x3000,0x3000+0x1f0:222,
             session+0xba30:2,
             session+0xb930:ptr_a,session+0xb938:ptr_b,
             ptr_a:33,ptr_a+0x1d8:111,ptr_b:77,ptr_b+0x1d8:222}
        return mem,(player,session,77,getter)
    def probe(self,mem,params):
        read=lambda addr:mem[addr]
        return mod.check_peer_session_map(read,read,*params)
    def test_unique_consistent_is_candidate_only(self):
        mem,params=self.fixture()
        r=self.probe(mem,params)
        self.assertEqual(r["status"],"session_connection_peer_candidate_only")
        self.assertTrue(r["peer_map_consistent"])
        self.assertEqual(r["remote_entries_seen"],2)
        for flag in ("authenticated_rage_sender_verified",
                     "session_membership_verified","session_generation_verified"):
            self.assertFalse(r[flag])
        for secret in ("peer_id","connection_id","netplayer","session"):
            self.assertNotIn(secret,r)
    def test_wrong_connection_or_vtable(self):
        mem,args=self.fixture()
        self.assertEqual(self.probe(mem,(args[0],args[1],44,args[3]))["status"],
                         "netplayer_connection_mismatch")
        mem[0x2000+0x38]=0x1234
        self.assertEqual(self.probe(mem,args)["status"],
                         "unexpected_gamer_info_vtable")
    def test_peer_mapping_mismatch_and_alias(self):
        mem,args=self.fixture()
        mem[0x9000+0x1d8]=333
        self.assertEqual(self.probe(mem,args)["status"],
                         "connection_to_peer_mismatch")
        mem,args=self.fixture();mem[0x8000+0x1d8]=222
        self.assertEqual(self.probe(mem,args)["status"],
                         "peer_alias_different_connection")
    def test_duplicate_and_missing_cxn(self):
        mem,args=self.fixture()
        mem[0x8000]=77;mem[0x8000+0x1d8]=222
        self.assertEqual(self.probe(mem,args)["status"],
                         "no_unique_session_connection")
        mem,args=self.fixture();mem[0x9000]=22
        # Same peer ID moved to a different connection; reject alias explicitly.
        self.assertEqual(self.probe(mem,args)["status"],
                         "peer_alias_different_connection")
    def test_session_count_and_invalid_peer(self):
        mem,args=self.fixture()
        for count in (0,33,999,0xffffffff):
            mem[args[1]+0xba30]=count
            self.assertEqual(self.probe(mem,args)["status"],
                             "session_peer_count_out_of_bounds")
        mem,args=self.fixture();mem[0x9000+0x1d8]=0
        self.assertEqual(self.probe(mem,args)["status"],"invalid_session_entry")
        mem,args=self.fixture();mem[0x3000+0x1f0]=mod.U64MAX
        self.assertEqual(self.probe(mem,args)["status"],"invalid_netplayer_peer")
    def test_invalid_input_and_missing_memory(self):
        mem,args=self.fixture()
        for bad in (0,-1,0x80000000,0xffffffff):
            self.assertEqual(self.probe(mem,(args[0],args[1],bad,args[3]))["status"],
                             "invalid_input")
        self.assertEqual(self.probe(mem,(0,args[1],77,args[3]))["status"],
                         "invalid_input")
        del mem[0x9000+0x1d8]
        self.assertEqual(self.probe(mem,args)["status"],"read_failed")
    def test_no_false_persistent_ownership(self):
        mem,args=self.fixture()
        r=self.probe(mem,args)
        self.assertTrue(r["peer_map_consistent"])
        # Network migration creates a different mapping; stale pair fails.
        mem[0x9000]=88
        self.assertFalse(self.probe(mem,args)["peer_map_consistent"])
        self.assertFalse(self.probe(mem,args)["authenticated_rage_sender_verified"])

    def test_same_event_register_peer_must_match(self):
        mem,args=self.fixture()
        read=lambda a:mem[a]
        good=mod.check_peer_session_map(read,read,*args,expected_peer_id=222)
        self.assertTrue(good["peer_map_consistent"])
        bad=mod.check_peer_session_map(read,read,*args,expected_peer_id=123)
        self.assertEqual(bad["status"],"same_callback_peer_register_mismatch")
        self.assertFalse(bad["authenticated_rage_sender_verified"])

    def test_distinct_transport_and_rl_ids_match_only_within_their_domains(self):
        mem,args=self.fixture()
        mem[0x3020]=987654321
        mem[0x9008]=987654321
        read=lambda addr:mem[addr]
        result=mod.check_peer_session_map(read,read,*args,check_transport_domain=True)
        self.assertTrue(result['peer_map_consistent'])
        self.assertTrue(result['transport_peer_map_consistent'])
        self.assertFalse(result['authenticated_rage_sender_verified'])
        self.assertNotIn('987654321',str(result))
        # Numerically equal to the rl ID is not a transport-domain match.
        mem[0x9008]=222
        result=mod.check_peer_session_map(read,read,*args,check_transport_domain=True)
        self.assertEqual(result['status'],'transport_peer_metadata_mismatch')
        self.assertFalse(result['peer_map_consistent'])
        self.assertFalse(result['transport_peer_map_consistent'])

    def test_transport_domain_unknown_or_invalid_fails_closed(self):
        for value in (None,0,mod.U64MAX,mod.U64MAX+1):
            with self.subTest(value=value):
                mem,args=self.fixture()
                mem[0x3020]=777
                if value is not None:mem[0x9008]=value
                read=lambda addr:mem[addr]
                result=mod.check_peer_session_map(read,read,*args,check_transport_domain=True)
                self.assertEqual(result['status'], 'read_failed' if value is None
                                 else 'invalid_transport_peer_metadata')
                self.assertFalse(result['peer_map_consistent'])
                self.assertFalse(result['authenticated_rage_sender_verified'])

    def test_alias_compares_transport_metadata_but_remains_inconsistent(self):
        for value, expected in ((777, 'match'), (778, 'transport_peer_metadata_mismatch'),
                                (None, 'read_failed')):
            with self.subTest(value=value):
                mem, args = self.fixture()
                mem[0x9000] = 88
                mem[0x3020] = 777
                if value is not None:
                    mem[0x9008] = value
                read = mem.__getitem__
                result = mod.check_peer_session_map(read, read, *args, check_transport_domain=True)
                self.assertEqual(result['status'], 'peer_alias_different_connection')
                self.assertEqual(result['alias_transport_peer_status'], expected)
                self.assertEqual(result['session_remote_peer_count'], 2)
                if expected != 'match':
                    self.assertNotIn('alias_endpoint_status', result)
                for key in ('peer_map_consistent', 'transport_peer_map_consistent',
                            'session_membership_verified', 'authenticated_rage_sender_verified'):
                    self.assertFalse(result[key])

    def test_alias_endpoint_comparison_keeps_connection_and_authority_gates_closed(self):
        for endpoint, expected in ((771122, 'match'), (771123, 'mismatch'),
                                   (0, 'invalid_endpoint_metadata'), (None, 'read_failed')):
            with self.subTest(expected=expected):
                mem, args = self.fixture()
                mem[0x9000] = 88
                mem[0x3020] = mem[0x9008] = 777
                mem[args[0] + 0x1c] = 771122
                if endpoint is not None:
                    mem[0x9000 + 0x1e0] = endpoint
                read = mem.__getitem__
                observations = []
                result = mod.check_peer_session_map(
                    read, read, *args, check_transport_domain=True,
                    on_matching_alias=lambda *values: observations.append(values))
                self.assertEqual(result['status'], 'peer_alias_different_connection')
                self.assertEqual(result['alias_endpoint_status'], expected)
                self.assertEqual(observations, [(args[2], 88, 771122)] if expected == 'match' else [])
                self.assertFalse(result['peer_map_consistent'])
                self.assertFalse(result['session_membership_verified'])
                self.assertFalse(result['authenticated_rage_sender_verified'])
                self.assertNotIn('771122', str(result))

    def test_scan_can_stop_before_the_last_peer_row(self):
        mem, args = self.fixture()
        mem[0x8000 + 0x1d8] = 222
        result = self.probe(mem, args)
        self.assertEqual(result['status'], 'peer_alias_different_connection')
        self.assertEqual(result['remote_entries_seen'], 1)
        self.assertEqual(result['session_remote_peer_count'], 2)

    def test_legacy_rl_only_reader_never_claims_transport_binding(self):
        mem,args=self.fixture()
        result=self.probe(mem,args)
        self.assertTrue(result['peer_map_consistent'])
        self.assertFalse(result['transport_peer_map_consistent'])

if __name__=="__main__":unittest.main()
