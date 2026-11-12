"""Server permissions for the 3 police jobs built into this particular GTA5 v12."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import test_police_rp_v2 as base
from unittest import TestCase
import time
import sqlite3


class TestNativeDuty(TestCase):
    # Reuse only the HTTP test harness; avoid re-running baseline tests.
    setUp = base.PoliceRPV2.setUp
    tearDown = base.PoliceRPV2.tearDown
    req = base.PoliceRPV2.req
    beat = base.PoliceRPV2.beat
    act = base.PoliceRPV2.act
    setup_arrest = base.PoliceRPV2.setup_arrest
    def test_cannot_arrest_before_native_shift(self):
        self.beat(self.cop_token, on_duty=False)
        self.beat(self.a_token, 2)
        self.assertEqual(self.act(self.cop_token, 'cuff', self.a)[0], 409)
        state = self.req('/v1/state',self.cop_token)[1]['you']
        self.assertFalse(state['native_duty'])
        self.beat(self.cop_token, on_duty=True)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0], 200)

    def test_off_shift_releases_temporary_cuffs(self):
        self.setup_arrest()
        self.act(self.cop_token, 'cuff',self.a)
        self.beat(self.cop_token,on_duty=False)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')

    def test_off_shift_does_not_cancel_sentence(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.act(self.cop_token,'jail',self.a)
        self.beat(self.cop_token,100,100,10,on_duty=False)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'jailed')

    def test_reject_invalid_claims(self):
        self.assertEqual(self.beat(self.a_token,on_duty=True)[0],403)
        self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{
            'room':'POLICE_TEST','pos':{'x':0,'y':0,'z':0},
            'consent':True,'consent':True,'on_duty':True,'native_job':3})[0],400)
        self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{
            'room':'POLICE_TEST','pos':{'x':0,'y':0,'z':0},
            'consent':True,'on_duty':'true','native_job':0})[0],400)
        self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{
            'room':'POLICE_TEST','pos':{'x':0,'y':0,'z':0},
            'consent':True,'consent':True,'on_duty':True,'native_job':False})[0],400)
        for i in (0,1,2):
            self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{
                'room':'POLICE_TEST','pos':{'x':0,'y':0,'z':0},
                'consent':True,'consent':True,'on_duty':True,'native_job':i})[0],200)
        self.assertEqual(self.req('/v1/state', self.cop_token)[1]['you']['native_job'],2)

    def test_v02_database_migration_keeps_tokens(self):
        import tempfile
        from test_police_rp_v2 import rp
        with tempfile.TemporaryDirectory() as tmp:
            dbpath = str(Path(tmp)/'old.db')
            con = sqlite3.connect(dbpath)
            con.execute("""CREATE TABLE players (
              id TEXT PRIMARY KEY,name TEXT NOT NULL, role TEXT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,room TEXT NOT NULL DEFAULT '',
              x REAL NOT NULL DEFAULT 0,y REAL NOT NULL DEFAULT 0,
              z REAL NOT NULL DEFAULT 0,last_seen REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'free',officer TEXT NOT NULL DEFAULT '',
              jail_until REAL NOT NULL DEFAULT 0, changed REAL NOT NULL DEFAULT 0)""")
            con.execute('INSERT INTO players(id,name,role,token_hash) VALUES(?,?,?,?)',
                        ('test01','Original officer','police',rp.token_hash('old_secret_token')))
            con.commit(); con.close()
            db = rp.make_db(dbpath)
            self.assertEqual(rp.auth(db,'old_secret_token')['name'],'Original officer')
            self.assertEqual(rp.auth(db,'old_secret_token')['on_duty'],0)
            db.close()

    def test_old_client_without_duty_never_grants_police(self):
        self.beat(self.a_token,2)
        self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{
            'room':'POLICE_TEST','pos':{'x':0,'y':0,'z':0}})[0],200)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],409)
