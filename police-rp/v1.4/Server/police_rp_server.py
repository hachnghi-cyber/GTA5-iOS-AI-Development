#!/usr/bin/env python3
"""GTA V iOS Police RP Only v0.4: native job aware opt-in companion server.

Does not change the GTA Online UDP relay. Positions and room names are reported
by RP clients, so this is NOT an anti-cheat/authoritative game server.
Never expose raw HTTP with tokens on the public Internet.
"""
import argparse
import hashlib
import json
import math
import secrets
import sqlite3
import sys
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_JAIL = (1691.0, 2565.0, 45.5)  # Exterior estimate; verify in game.
ONLINE_AGE = 20.0
MAX_BODY = 4096


class RPError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def fail(code, message):
    raise RPError(code, message)


def open_db(path):
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA busy_timeout=5000')
    return db


def make_db(path):
    db = open_db(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE, room TEXT NOT NULL DEFAULT '',
            x REAL NOT NULL DEFAULT 0, y REAL NOT NULL DEFAULT 0,
            z REAL NOT NULL DEFAULT 0, last_seen REAL NOT NULL DEFAULT 0,
            on_duty INTEGER NOT NULL DEFAULT 0, native_job INTEGER NOT NULL DEFAULT -1,
            consent INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'free', officer TEXT NOT NULL DEFAULT '',
            jail_until REAL NOT NULL DEFAULT 0, changed REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL,
            officer_id TEXT NOT NULL, target_id TEXT NOT NULL,
            action TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_players_room ON players(room);
        CREATE INDEX IF NOT EXISTS ix_players_officer ON players(officer);
    ''')
    # Preserve registered players when upgrading an existing v0.2 sqlite DB.
    columns = {row['name'] for row in db.execute('PRAGMA table_info(players)')}
    if 'on_duty' not in columns:
        db.execute('ALTER TABLE players ADD COLUMN on_duty INTEGER NOT NULL DEFAULT 0')
    if 'native_job' not in columns:
        db.execute('ALTER TABLE players ADD COLUMN native_job INTEGER NOT NULL DEFAULT -1')
    if 'consent' not in columns:
        db.execute('ALTER TABLE players ADD COLUMN consent INTEGER NOT NULL DEFAULT 0')
    return db


@contextmanager
def db_session(path):
    # Initialize once at startup; avoid DDL on every heartbeat from 32 devices.
    db = open_db(path)
    try:
        yield db
    finally:
        db.close()


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_player(db, name, role='citizen'):
    if role not in ('police', 'citizen'):
        fail(400, 'Unknown role')
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 32):
        fail(400, 'Name length must be 1-32')
    key, pid = secrets.token_urlsafe(32), secrets.token_hex(6)
    db.execute('INSERT INTO players(id,name,role,token_hash) VALUES(?,?,?,?)',
               (pid, name.strip(), role, token_hash(key)))
    return pid, key


def auth(db, token):
    if not token or len(token) > 128:
        fail(401, 'Missing player token')
    p = db.execute('SELECT * FROM players WHERE token_hash=?', (token_hash(token),)).fetchone()
    if p is None:
        fail(401, 'Unknown player token')
    return p


def sanitize_room(value):
    if not isinstance(value, str) or not 4 <= len(value) <= 48 or not all(
            c.isascii() and (c.isalnum() or c in '-_') for c in value):
        fail(400, 'Room must be 4-48 ASCII letters/digits/-/_')
    return value


def sanitize_pos(pos):
    if not isinstance(pos, dict):
        fail(400, 'Position must be an object')
    try:
        xyz = tuple(float(pos[k]) for k in ('x', 'y', 'z'))
    except (KeyError, ValueError, TypeError, OverflowError):
        fail(400, 'Missing or invalid position')
    if not all(math.isfinite(v) and abs(v) <= 100000 for v in xyz):
        fail(400, 'Position out of range')
    return xyz


def distance(a, b):
    return math.dist(tuple(float(a[k]) for k in ('x', 'y', 'z')),
                     tuple(float(b[k]) for k in ('x', 'y', 'z')))


def jail_distance(p, jail):
    return math.dist((p['x'], p['y'], p['z']), jail)


def online(p, now):
    return p['room'] != '' and 0 <= now - p['last_seen'] <= ONLINE_AGE


def auto_release(db, now):
    # Players who explicitly revoked consent are never kept restrained.
    db.execute("""UPDATE players SET status='free',officer='',jail_until=0,changed=?
                  WHERE consent=0 AND status!='free'""", (now,))
    # Expired sentences release even when nobody else is connected.
    db.execute('''UPDATE players SET status='free',officer='',jail_until=0,changed=?
                  WHERE status='jailed' AND jail_until>0 AND jail_until<=?''', (now, now))
    # Fail-open for cuffs/escort if the prisoner or the responsible officer left,
    # switched rooms or has not heartbeated recently. Does not shorten sentences.
    db.execute('''UPDATE players SET status='free',officer='',changed=?
                  WHERE status IN ('cuffed','escorted') AND
                  (consent=0 OR last_seen<? OR room='' OR NOT EXISTS (
                      SELECT 1 FROM players AS p WHERE p.id=players.officer
                      AND p.room=players.room AND p.room!='' AND p.role='police'
                      AND p.on_duty=1 AND p.consent=1 AND p.last_seen>=?
                  ))''', (now, now-ONLINE_AGE, now-ONLINE_AGE))


def snapshot(db, player_id, jail, now):
    auto_release(db, now)
    player = db.execute('SELECT * FROM players WHERE id=?', (player_id,)).fetchone()
    if player['room'] == '':
        members = []
    else:
        members = db.execute('SELECT * FROM players WHERE room=? ORDER BY name COLLATE NOCASE',
                             (player['room'],)).fetchall()
    return {
        'you': {'id': player['id'], 'name': player['name'], 'role': player['role'],
                'status': player['status'], 'officer': player['officer'],
                'native_duty': bool(player['on_duty']), 'native_job': player['native_job'],
                'consent': bool(player['consent']),
                'jail_seconds': max(0, int(player['jail_until'] - now)),
                'changed': player['changed']},
        'players': [{'id':p['id'], 'name':p['name'], 'role':p['role'],
                     'status':p['status'], 'online':True, 'native_duty':bool(p['on_duty']),
                     'x':p['x'], 'y':p['y'], 'z':p['z']}
                    for p in members if online(p, now) and p['consent']],
        'jail': {'x':jail[0], 'y':jail[1], 'z':jail[2]},
        'room':player['room'], 'server_time':now,
    }


def heartbeat(db, actor, data, jail):
    room = sanitize_room(data.get('room'))
    x, y, z = sanitize_pos(data.get('pos'))
    consent = data.get('consent', False)
    if type(consent) is not bool:
        fail(400, 'Consent must be true or false')
    native_job = data.get('native_job', -1)
    native_duty = data.get('on_duty', False)
    if type(native_duty) is not bool or type(native_job) is not int:
        fail(400, 'Native job / duty data types invalid')
    if native_duty and native_job not in (0, 1, 2):
        fail(400, 'Native duty only valid for cop job 0/1/2')
    if actor['role'] != 'police' and native_duty:
        fail(403, 'Citizen cannot claim police duty')
    duty = int(actor['role'] == 'police' and native_duty)
    now = time.time()
    db.execute('BEGIN IMMEDIATE')
    try:
        if (actor['room'] and actor['room'] != room) or not consent:
            # Revoking RP consent immediately releases temporary cuffs and sentences.
            db.execute('''UPDATE players SET status='free',officer='',jail_until=0,changed=?
                          WHERE officer=? AND status IN ('cuffed','escorted')''',
                       (now, actor['id']))
            db.execute("UPDATE players SET status='free',officer='',jail_until=0,changed=? WHERE id=?",
                       (now, actor['id']))
        if actor['room'] and actor['room'] != room:
            # Leaving an RP room cancels any temporary cuffs by this officer.
            db.execute('''UPDATE players SET status='free',officer='',changed=?
                          WHERE officer=? AND status IN ('cuffed','escorted')''',
                       (now, actor['id']))
            if actor['status'] in ('cuffed', 'escorted'):
                db.execute("UPDATE players SET status='free',officer='',changed=? WHERE id=?",
                           (now, actor['id']))
        db.execute('UPDATE players SET room=?,x=?,y=?,z=?,last_seen=?,on_duty=?,native_job=?,consent=? WHERE id=?',
                   (room, x, y, z, now, duty, native_job if duty else -1, int(consent), actor['id']))
        result = snapshot(db, actor['id'], jail, now)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def leave(db, actor, jail):
    now = time.time()
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('''UPDATE players SET status='free',officer='',changed=?
                      WHERE officer=? AND status IN ('cuffed','escorted')''',
                   (now, actor['id']))
        db.execute('''UPDATE players SET room='',last_seen=0,on_duty=0,native_job=-1,consent=0,
                      status='free',officer='',jail_until=0,
                      changed=? WHERE id=?''', (now, actor['id']))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'ok':True, 'left':True}


def action(db, actor, data, jail):
    kind = data.get('action')
    if kind not in ('cuff', 'uncuff', 'escort', 'jail', 'release'):
        fail(400, 'Invalid action')
    target_id = data.get('target')
    # Explicit selection prevents arresting the wrong player in a crowded room.
    if not isinstance(target_id, str) or not (1 <= len(target_id) <= 64):
        fail(400, 'Select a target id first')
    now = time.time()
    db.execute('BEGIN IMMEDIATE')
    try:
        auto_release(db, now)
        actor = db.execute('SELECT * FROM players WHERE id=?', (actor['id'],)).fetchone()
        if actor['role'] != 'police':
            fail(403, 'Police role required')
        if not online(actor, now) or not actor['consent']:
            fail(409, 'Officer not active in this room')
        if not actor['on_duty'] or actor['native_job'] not in (0, 1, 2):
            fail(409, 'Take an actual native police shift before arresting a player')
        target = db.execute('SELECT * FROM players WHERE id=?', (target_id,)).fetchone()
        if not target or target['id'] == actor['id'] or target['room'] != actor['room'] or not online(target, now) or not target['consent']:
            fail(404, 'Target not active in same RP room')
        if target['role'] != 'citizen':
            fail(409, 'Only citizen targets are allowed')
        status, officer, until = target['status'], target['officer'], target['jail_until']
        near = distance(actor, target)
        if kind == 'cuff':
            if near > 4: fail(409, 'Target farther than 4m')
            if status != 'free': fail(409, 'Target is not free')
            status, officer = 'cuffed', actor['id']
        elif kind == 'uncuff':
            if near > 4: fail(409, 'Target farther than 4m')
            if status not in ('cuffed','escorted'): fail(409, 'Target not restrained')
            if officer != actor['id']: fail(403, 'Only arresting officer can uncuff')
            status, officer = 'free', ''
        elif kind == 'escort':
            if near > 5: fail(409, 'Target farther than 5m')
            if status != 'cuffed': fail(409, 'Cuff target first')
            if officer != actor['id']: fail(403, 'Only arresting officer can escort')
            status = 'escorted'
        elif kind == 'jail':
            if status not in ('cuffed','escorted'): fail(409, 'Cuff target first')
            if officer != actor['id']: fail(403, 'Only arresting officer can jail')
            if near > 12: fail(409, 'Prisoner farther than 12m')
            if jail_distance(actor,jail) > 60: fail(409, 'Officer must reach prison gate')
            minutes = data.get('minutes', 5)
            if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 60:
                fail(400, 'Sentence must be integer 1-60 minutes')
            status, until = 'jailed', now + 60*minutes
        else:  # release
            if status != 'jailed': fail(409, 'Target not jailed')
            if jail_distance(actor, jail) > 60: fail(409, 'Officer must reach prison gate')
            status, officer, until = 'free', '', 0
        db.execute('UPDATE players SET status=?,officer=?,jail_until=?,changed=? WHERE id=?',
                   (status, officer, until, now, target_id))
        db.execute('INSERT INTO events(ts,officer_id,target_id,action,note) VALUES (?,?,?,?,?)',
                   (now, actor['id'], target_id, kind, str(data.get('minutes', ''))[:12]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'ok':True, 'action':kind, 'target':target['name'], 'target_id':target_id,
            'new_status':status, 'jail_seconds':max(0,int(until-now))}


class Handler(BaseHTTPRequestHandler):
    db_path = ''
    jail = DEFAULT_JAIL

    def log_message(self, fmt, *args):
        print('%s %s' % (self.log_date_time_string(), fmt % args), flush=True)

    def answer(self, status, body):
        raw = json.dumps(body, ensure_ascii=False, separators=(',',':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def route(self, method):
        if self.path == '/health' and method == 'GET':
            return self.answer(200, {'ok':True,'service':'Police RP','version':'0.4-police-only-alpha'})
        if self.path not in ('/v1/state','/v1/heartbeat','/v1/action','/v1/leave'):
            fail(404, 'Unknown endpoint')
        if (self.path == '/v1/state' and method != 'GET') or (self.path != '/v1/state' and method != 'POST'):
            fail(405, 'Wrong HTTP method')
        bearer = self.headers.get('Authorization', '')
        if not bearer.startswith('Bearer '):
            fail(401, 'Bearer token required')
        data = {}
        if method == 'POST':
            try:
                length = int(self.headers.get('Content-Length','0'))
            except ValueError:
                fail(400, 'Invalid Content-Length')
            if not 0 < length <= MAX_BODY:
                fail(413, 'Invalid body size')
            try:
                data = json.loads(self.rfile.read(length).decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                fail(400, 'Invalid JSON')
            if not isinstance(data, dict):
                fail(400, 'Expected JSON object')
        with db_session(self.db_path) as db:
            actor = auth(db, bearer[7:].strip())
            if self.path == '/v1/heartbeat':
                result = heartbeat(db, actor, data, self.jail)
            elif self.path == '/v1/action':
                result = action(db, actor, data, self.jail)
            elif self.path == '/v1/leave':
                result = leave(db, actor, self.jail)
            else:
                if not online(actor, time.time()):
                    fail(409, 'Send heartbeat first')
                result = snapshot(db, actor['id'], self.jail, time.time())
        self.answer(200, result)

    def do_GET(self):
        try: self.route('GET')
        except RPError as e: self.answer(e.code, {'ok':False,'error':e.message})
        except Exception as e:
            print('Internal error:', repr(e),file=sys.stderr,flush=True)
            self.answer(500, {'ok':False,'error':'Server error'})

    def do_POST(self):
        try: self.route('POST')
        except RPError as e: self.answer(e.code, {'ok':False,'error':e.message})
        except Exception as e:
            print('Internal error:', repr(e),file=sys.stderr,flush=True)
            self.answer(500, {'ok':False,'error':'Server error'})


def main():
    ap = argparse.ArgumentParser(description='Police RP ONLY v0.4: opt-in companion server (test rooms only)')
    ap.add_argument('--db', default='police_rp.sqlite3')
    sub = ap.add_subparsers(dest='cmd',required=True)
    run = sub.add_parser('serve')
    run.add_argument('--bind',default='127.0.0.1')
    run.add_argument('--port',type=int,default=7789)
    run.add_argument('--jail',nargs=3,type=float,default=DEFAULT_JAIL,
                     metavar=('X','Y','Z'))
    add = sub.add_parser('add-player')
    add.add_argument('name');add.add_argument('--role',choices=['police','citizen'],default='citizen')
    sub.add_parser('players')
    role = sub.add_parser('set-role')
    role.add_argument('id');role.add_argument('role',choices=['police','citizen'])
    reset = sub.add_parser('reset');reset.add_argument('id')
    args = ap.parse_args()
    db = make_db(args.db)
    try:
        if args.cmd == 'add-player':
            pid, token = create_player(db, args.name, args.role)
            print('Player ID:',pid,'\nRole:',args.role,'\nTOKEN (keep secret):',token)
        elif args.cmd == 'players':
            for p in db.execute('SELECT * FROM players'):
                print(p['id'],p['role'],p['status'],p['name'],p['room'],
                      'online' if online(p,time.time()) else 'offline')
        elif args.cmd == 'set-role':
            cur = db.execute('UPDATE players SET role=? WHERE id=?',(args.role,args.id))
            if cur.rowcount != 1: raise SystemExit('Player ID not found')
            print('Role updated')
        elif args.cmd == 'reset':
            cur = db.execute("UPDATE players SET status='free',officer='',jail_until=0,changed=? WHERE id=?",
                             (time.time(),args.id))
            if cur.rowcount != 1: raise SystemExit('Player ID not found')
            print('Player released')
        else:
            class Bound(Handler): pass
            Bound.db_path,Bound.jail = args.db,tuple(args.jail)
            server = ThreadingHTTPServer((args.bind,args.port),Bound)
            print('Police RP listening %s:%d; keep behind HTTPS/VPN' % server.server_address)
            print('Jail exterior:',args.jail)
            try: server.serve_forever()
            except KeyboardInterrupt: pass
            finally: server.server_close()
    finally:
        db.close()


if __name__ == '__main__': main()
