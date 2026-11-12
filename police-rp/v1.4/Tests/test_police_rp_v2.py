"""Police RP V2 HTTP integration/regression tests; no GTA client required."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Server')))
import police_rp_server as rp


class PoliceRPV2(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'test.db')
        rp.make_db(self.path).close()
        with rp.db_session(self.path) as db:
            self.cop, self.cop_token = rp.create_player(db, 'Cop', 'police')
            self.cop2, self.cop2_token = rp.create_player(db, 'Cop2', 'police')
            self.a, self.a_token = rp.create_player(db, 'Alice')
            self.b, self.b_token = rp.create_player(db, 'Bob')
            self.c, self.c_token = rp.create_player(db, 'Other room')
            self.cop_tokens = {self.cop_token,self.cop2_token}
        class Handler(rp.Handler): pass
        Handler.db_path = self.path
        Handler.jail = (100.0, 100.0, 10.0)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.timeout = 0.1
        self.url = 'http://127.0.0.1:' + str(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True,
                                       kwargs={'poll_interval':0.01})
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def req(self, path, token='', data=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        body = None if data is None else json.dumps(data).encode('utf-8')
        if body is not None: headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.url + path, headers=headers, data=body)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def beat(self, token, x=0, y=0, z=0, room='POLICE_TEST', on_duty=None, consent=True):
        duty = (token in self.cop_tokens) if on_duty is None else on_duty
        return self.req('/v1/heartbeat',token,{'room':room,'pos':{'x':x,'y':y,'z':z},
                        'on_duty':duty,'native_job':0 if duty else -1, 'consent':consent})

    def act(self, token, kind, target, minutes=5):
        return self.req('/v1/action', token,
                        {'action':kind,'target':target,'minutes':minutes})

    def setup_arrest(self):
        self.assertEqual(self.beat(self.cop_token)[0],200)
        self.assertEqual(self.beat(self.a_token,2)[0],200)

    def test_authentication_and_health(self):
        status, doc = self.req('/health')
        self.assertEqual((status,doc['version']), (200,'0.4-police-only-alpha'))
        self.assertEqual(self.req('/v1/state')[0],401)
        self.assertEqual(self.req('/v1/state','bad-token')[0],401)
        self.assertEqual(self.req('/v1/state',self.a_token)[0],409) # needs heartbeat

    def test_arrest_and_release(self):
        self.setup_arrest()
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'cuffed')
        self.assertEqual(self.act(self.cop_token,'escort',self.a)[0],200)
        self.assertEqual(self.act(self.cop_token,'uncuff',self.a)[0],200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')

    def test_role_and_explicit_target_required(self):
        self.setup_arrest()
        self.assertEqual(self.act(self.a_token,'cuff',self.cop)[0],403)
        self.assertEqual(self.req('/v1/action',self.cop_token,{'action':'cuff'})[0],400)
        self.assertEqual(self.beat(self.cop2_token,1)[0],200)
        self.assertEqual(self.act(self.cop_token,'cuff',self.cop2)[0],409)
        self.assertEqual(self.act(self.cop_token,'cuff','made-up-id')[0],404)

    def test_distance_and_room_separation(self):
        self.setup_arrest()
        self.assertEqual(self.beat(self.b_token,60)[0],200)
        self.assertEqual(self.beat(self.c_token,1,room='DIFFERENT')[0],200)
        self.assertEqual(self.act(self.cop_token,'cuff',self.b)[0],409)
        self.assertEqual(self.act(self.cop_token,'cuff',self.c)[0],404)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)

    def test_officer_ownership_prevents_hijack(self):
        self.setup_arrest()
        self.beat(self.cop2_token,1)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
        self.assertEqual(self.act(self.cop2_token,'uncuff',self.a)[0],403)
        self.assertEqual(self.act(self.cop2_token,'escort',self.a)[0],403)
        self.assertEqual(self.act(self.cop_token,'escort',self.a)[0],200)

    def test_prison_sentence_and_expiry(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
        self.assertEqual(self.act(self.cop_token,'jail',self.a, 0)[0],400)
        self.assertEqual(self.act(self.cop_token,'jail',self.a, 61)[0],400)
        self.assertEqual(self.act(self.cop_token,'jail',self.a, 1.5)[0],400)
        self.assertEqual(self.act(self.cop_token,'jail',self.a, True)[0],400)
        self.assertEqual(self.act(self.cop_token,'jail',self.a, 1)[0],200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'jailed')
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],409)
        with rp.db_session(self.path) as db:
            db.execute('UPDATE players SET jail_until=? WHERE id=?',(time.time()-1,self.a))
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')

    def test_release_needs_prison_gate(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.assertEqual(self.act(self.cop_token,'jail',self.a)[0],200)
        self.beat(self.cop_token,0,0,0)
        self.assertEqual(self.act(self.cop_token,'release',self.a)[0],409)
        self.beat(self.cop_token,100,100,10)
        self.assertEqual(self.act(self.cop_token,'release',self.a)[0],200)

    def test_leave_releases_temporary_cuffs(self):
        self.setup_arrest()
        self.act(self.cop_token,'cuff',self.a)
        status, _ = self.req('/v1/leave',self.cop_token,{'reason':'disabled'})
        self.assertEqual(status,200)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],409)

    def test_room_switch_clears_cuffs(self):
        self.setup_arrest()
        self.act(self.cop_token,'cuff',self.a)
        self.beat(self.cop_token,0,0,0,room='OTHER')
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')

    def test_disconnect_expiry_releases_cuffs_not_jail(self):
        self.setup_arrest()
        self.act(self.cop_token,'cuff',self.a)
        with rp.db_session(self.path) as db:
            db.execute('UPDATE players SET last_seen=? WHERE id=?',
                       (time.time() - rp.ONLINE_AGE - 1, self.cop))
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.act(self.cop_token,'jail',self.a)
        with rp.db_session(self.path) as db:
            db.execute('UPDATE players SET last_seen=? WHERE id=?',
                       (time.time() - rp.ONLINE_AGE - 1, self.cop))
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'jailed')

    def test_opt_out_removes_prison_sentence(self):
        self.beat(self.cop_token,100,100,10)
        self.beat(self.a_token,101,100,10)
        self.act(self.cop_token,'cuff',self.a)
        self.act(self.cop_token,'jail',self.a)
        self.req('/v1/leave',self.a_token,{'reason':'disconnect'})
        self.beat(self.a_token,101,100,10)
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')

    def test_invalid_payloads_and_input_bounds(self):
        self.assertEqual(self.beat(self.cop_token,float('nan'))[0],400)
        self.assertEqual(self.beat(self.cop_token,room='chữ_việt')[0],400)
        self.assertEqual(self.beat(self.cop_token,room='!')[0],400)
        self.assertEqual(self.beat(self.cop_token,float('inf'))[0],400)
        self.assertEqual(self.req('/v1/action',self.cop_token,{'action':'bad','target':self.a})[0],400)
        self.assertEqual(self.req('/v1/heartbeat',self.cop_token,{'room':'FOO1','pos':[]})[0],400)

    def test_two_officers_concurrent_one_winner(self):
        self.setup_arrest()
        self.beat(self.cop2_token,0)
        codes = []
        jobs = [threading.Thread(target=lambda tok=token: codes.append(self.act(tok,'cuff',self.a)[0]))
                for token in (self.cop_token,self.cop2_token)]
        for t in jobs: t.start()
        for t in jobs: t.join()
        self.assertEqual(sorted(codes),[200,409])
        with rp.db_session(self.path) as db:
            n = db.execute("SELECT COUNT(*) AS n FROM events WHERE action='cuff'").fetchone()['n']
        self.assertEqual(n,1)

    def test_role_revoked_releases_prisoner(self):
        self.setup_arrest()
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],200)
        with rp.db_session(self.path) as db:
            db.execute("UPDATE players SET role='citizen' WHERE id=?",(self.cop,))
        self.assertEqual(self.req('/v1/state',self.a_token)[1]['you']['status'],'free')
        self.assertEqual(self.act(self.cop_token,'cuff',self.a)[0],403)

    def test_thirty_two_player_heartbeat_batch(self):
        from concurrent.futures import ThreadPoolExecutor
        actors = [(self.cop,self.cop_token),(self.cop2,self.cop2_token),
                  (self.a,self.a_token),(self.b,self.b_token),(self.c,self.c_token)]
        with rp.db_session(self.path) as db:
            for i in range(27):
                actors.append(rp.create_player(db,'Player%02d'%i))
        with ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(lambda item:self.beat(item[1],1,2,3),actors))
        self.assertEqual(len(responses),32)
        self.assertTrue(all(code==200 for code,_ in responses))
        state = self.req('/v1/state',self.cop_token)[1]
        self.assertEqual(len(state['players']),32)

    def test_snapshot_keeps_only_active_room_players(self):
        self.setup_arrest()
        self.beat(self.b_token,1,room='ANOTHER')
        self.beat(self.c_token,2,room='POLICE_TEST')
        code, snap = self.req('/v1/state',self.cop_token)
        self.assertEqual(code,200)
        ids = {p['id'] for p in snap['players']}
        self.assertIn(self.a,ids)
        self.assertIn(self.c,ids)
        self.assertNotIn(self.b,ids)


if __name__ == '__main__':
    unittest.main(verbosity=2)
