"""Operator-provisioned accounts; persistent password hashes, ephemeral login grants.

All state methods run on the authority event loop. Only scrypt runs in a worker.
No GTA identity, consent or police role is accepted from a browser.
"""
import argparse
import asyncio
from dataclasses import dataclass
import getpass
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=1 << 17,
                          r=8, p=1, dklen=32, maxmem=256 * 1024 * 1024)


def username(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_]{3,32}', value):
        raise ValueError('Tên tài khoản cần 3–32 ký tự chữ, số hoặc dấu gạch dưới.')
    return value.lower()


def open_database(path):
    path = Path(path).resolve()
    if any((parent / '.git').exists() for parent in (path.parent, *path.parents)):
        raise ValueError('Account database must be outside Git working trees')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.exists():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    db = sqlite3.connect(path, timeout=0.1)
    db.execute('''CREATE TABLE IF NOT EXISTS accounts (
        name TEXT PRIMARY KEY, rp_id TEXT UNIQUE NOT NULL,
        salt BLOB NOT NULL, verifier BLOB NOT NULL,
        version INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 1)''')
    db.commit()
    return db


def provision(db, name, rp_id, password, *, reset=False):
    name = username(name)
    if type(rp_id) is not int or not 0 < rp_id < 1 << 64:
        raise ValueError('Invalid RP identity')
    if not isinstance(password, str) or not 15 <= len(password) <= 128:
        raise ValueError('Mật khẩu cần 15–128 ký tự.')
    salt = secrets.token_bytes(16)
    verifier = password_hash(password, salt)
    with db:
        if reset:
            result = db.execute('UPDATE accounts SET salt=?, verifier=?, version=version+1 '
                                'WHERE name=? AND rp_id=?', (salt, verifier, name, str(rp_id)))
            if result.rowcount != 1:
                raise ValueError('Account or RP identity does not match')
        else:
            db.execute('INSERT INTO accounts(name,rp_id,salt,verifier) VALUES (?,?,?,?)',
                       (name, str(rp_id), salt, verifier))


@dataclass
class Grant:
    name: str
    rp_id: int
    version: int
    created: float
    touched: float


class Accounts:
    def __init__(self, db, *, idle=1800, lifetime=28800, clock=time.monotonic):
        if not 0 < idle <= lifetime:
            raise ValueError('Invalid login lifetime')
        self.db, self.idle, self.lifetime, self.clock = db, idle, lifetime, clock
        self.grants, self.identities, self.generations, self.attempts = {}, {}, {}, {}
        self.hashing = False
        self.dummy_salt = secrets.token_bytes(16)

    def _row(self, name):
        return self.db.execute('SELECT rp_id,salt,verifier,version,enabled FROM accounts '
                               'WHERE name=?', (name,)).fetchone()

    @staticmethod
    def token_key(token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return None
        return hashlib.sha256(token.encode('ascii')).digest()

    def _attempt(self, name, remote):
        now = self.clock()
        self.attempts = {k: v for k, v in self.attempts.items() if now - v[0] < 60}
        # Global bound also prevents bypass by cycling usernames and addresses.
        keys = (('user', name), ('ip', remote), ('global', ''))
        if len(self.attempts) >= 4096:
            return False
        counts = [self.attempts.get(k, (now, 0)) for k in keys]
        if any(v[1] >= limit for v, limit in zip(counts, (5, 20, 60))):
            return False
        for k, (start, count) in zip(keys, counts):
            self.attempts[k] = (start, count + 1)
        return True

    async def login(self, name, password, remote):
        try:
            name = username(name)
        except ValueError:
            return None
        if (not isinstance(password, str) or not 1 <= len(password) <= 128 or
                not self._attempt(name, remote) or self.hashing):
            return None
        row = self._row(name)
        generation = self.generations.get(name, 0)
        self.hashing = True  # At most one 128 MiB password operation, no unbounded queue.
        try:
            value = await asyncio.to_thread(password_hash, password, row[1] if row else self.dummy_salt)
        finally:
            self.hashing = False
        if (not row or not hmac.compare_digest(value, row[2]) or not row[4] or
                row != self._row(name) or generation != self.generations.get(name, 0)):
            return None
        identity = int(row[0])
        self.revoke_identity(identity)
        token = secrets.token_urlsafe(32)
        key = self.token_key(token)
        now = self.clock()
        self.grants[key] = Grant(name, identity, row[3], now, now)
        self.identities[identity] = key
        return token

    def validate(self, key, identity=None, *, touch=False):
        grant = self.grants.get(key)
        if grant is None or (identity is not None and grant.rp_id != identity):
            return None
        try:
            row = self._row(grant.name)
        except sqlite3.OperationalError:
            row = None
        now = self.clock()
        if (not row or not row[4] or row[3] != grant.version or int(row[0]) != grant.rp_id or
                self.identities.get(grant.rp_id) != key or
                now - grant.created >= self.lifetime or now - grant.touched >= self.idle):
            self.revoke_identity(grant.rp_id)
            return None
        if touch:
            grant.touched = now
        return grant

    def admission(self, identity):
        key = self.identities.get(identity)
        return key if self.validate(key, identity) else None

    def revoke_identity(self, identity):
        key = self.identities.pop(identity, None)
        grant = self.grants.pop(key, None)
        if grant:
            self.generations[grant.name] = self.generations.get(grant.name, 0) + 1

    def logout(self, token):
        grant = self.grants.get(self.token_key(token))
        if grant:
            self.revoke_identity(grant.rp_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('action', choices=('add', 'reset', 'disable'))
    parser.add_argument('username')
    parser.add_argument('--rp-id', type=int)
    args = parser.parse_args()
    db = open_database(args.database)
    try:
        name = username(args.username)
        if args.action == 'disable':
            with db:
                if db.execute('UPDATE accounts SET enabled=0, version=version+1 WHERE name=?',
                              (name,)).rowcount != 1:
                    raise ValueError('Unknown account')
        else:
            password = getpass.getpass('Mật khẩu mới (ít nhất 15 ký tự): ')
            if password != getpass.getpass('Nhập lại mật khẩu: '):
                raise ValueError('Mật khẩu không khớp')
            provision(db, name, args.rp_id, password, reset=args.action == 'reset')
        print('Đã lưu tài khoản. Không có mật khẩu mặc định.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
