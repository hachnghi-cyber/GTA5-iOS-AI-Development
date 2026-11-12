"""Police-only isolation + opt-in regression tests for GTA V iOS v12.
This verifies server state. It does NOT validate native game integration.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import test_police_rp_v2 as base
from unittest import TestCase
import time
from concurrent.futures import ThreadPoolExecutor

class PoliceOnlyV04(TestCase):
    setUp=base.PoliceRPV2.setUp
    tearDown=base.PoliceRPV2.tearDown
    req=base.PoliceRPV2.req
    beat=base.PoliceRPV2.beat
    act=base.PoliceRPV2.act
    setup_arrest=base.PoliceRPV2.setup_arrest

    def test_no_consent_never_visible_or_arrestable(self):
        self.beat(self.cop_token)
        self.assertEqual(self.beat(self.a_token,2, consent=False)[0],200)
        members=self.req('/v1/state',self.cop_token)[1]['players']
        self.assertFalse(any(p['id']==self.a for p in members))
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],404)
    def test_officer_opt_out_blocks_all_actions(self):
        self.beat(self.cop_token,consent=False)
        self.beat(self.a_token,2)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],409)
        self.assertEqual(self.beat(self.cop_token, consent=True)[0],200)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
    def test_victim_withdraw_consent_releases_cuffs(self):
        self.setup_arrest()
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
        self.assertEqual(self.beat(self.a_token,2,consent=False)[0],200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],404)
    def test_victim_withdraw_consent_releases_sentence(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.assertEqual(self.act(self.cop_token,'jail',self.a)[0],200)
        self.assertEqual(self.beat(self.a_token,101,100,10,consent=False)[0],200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
    def test_invalid_consent_types_rejected(self):
        for val in ('true',1,0,None,[],{}):
            res=self.req('/v1/heartbeat',self.a_token,{'room':'POLICE_TEST',
                'pos':{'x':0,'y':0,'z':0},'consent':val})
            self.assertEqual(res[0],400)
    def test_old_heartbeat_does_not_opt_in(self):
        self.beat(self.cop_token)
        self.req('/v1/heartbeat',self.a_token,{'room':'POLICE_TEST',
             'pos':{'x':1,'y':0,'z':0}, 'native_job':-1,'on_duty':False})
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],404)
    def test_police_leaves_releases_temporary_cuffs(self):
        self.setup_arrest()
        self.act(self.cop_token,'cuff',self.a)
        self.beat(self.cop_token,consent=False)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
    def test_prisoner_disconnect_releases_sentence(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.act(self.cop_token,'jail',self.a)
        self.req('/v1/leave',self.a_token,{'reason':'disconnect'})
        self.beat(self.a_token,101,100,10)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
    def test_cross_room_with_consent_still_denied(self):
        self.beat(self.cop_token)
        self.beat(self.a_token,2,room='ROOM_OTHER')
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],404)
    def test_status_is_only_a_state_not_game_control(self):
        self.setup_arrest()
        self.act(self.cop_token,'cuff',self.a)
        state=self.req('/v1/state',self.a_token)[1]
        self.assertEqual(state['you']['status'],'cuffed')
        self.assertEqual(set(state['you'])-set(('id','name','role','status','officer',
            'native_duty','native_job','consent','jail_seconds','changed')), set())
    def test_original_game_server_unmodified(self):
        import hashlib
        deployed=Path(__file__).parents[1]/'Server/gtav_online_server.py'
        expected='2b1e69da0e3b92cbabbd8479d28e229105b5734144eef0ab1c2f510cf5067592'
        self.assertEqual(hashlib.sha256(deployed.read_bytes()).hexdigest(),expected)
