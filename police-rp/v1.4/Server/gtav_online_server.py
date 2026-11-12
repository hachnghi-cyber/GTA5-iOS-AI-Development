#!/usr/bin/env python3
"""GTA V Online server: a community server for the iOS/macOS port's GTA Online sandbox, for a spare PC.

The sandbox's sessions run on players' own devices (one hosts, the others join it with the host's session code). Without
a server, players find the host through the BitTorrent DHT and connect straight to it, or through the host when two
players can't reach each other. A server run by a group adds three things for everyone who points the game at it
(launcher > Settings > GTA Online > Community Server):

  - joining by code at once: the host registers its session here, so a joiner gets the host's addresses in one round
    trip instead of a DHT search;
  - a relay: players whose networks can't reach each other (mobile data, strict routers, a player and the host alike)
    play through this server; players who can reach each other still connect directly;
  - a list of sessions their hosts chose to make public (launcher > GTA Online > Join);
  - the server's own session (2026-11-01), always at the top of that list: the first player to join it hosts it, and
    when the host leaves, the game hands the session to another player in it (or, when the game can't, the server
    names the next player who joined as the new host and the others join that player).

The server never sees the players' own sessions: it passes on packets sealed with a key made from the session's code,
which it doesn't know. It sees players' IP addresses, a public session's code, its host's name and its player count,
and (games from 3 Nov 2026 on) each player's id on this server, and the names of the players in its own session.
The server's own session has a code the server makes (and lists), so that one is only as private as the server.

Moderation (2026-11-03): the operator lists the server's session, kicks players out of it (10 minutes, or as long as
told) and bans players from the server, by the id each game gives the server (made from a secret only that device
has: the same after restarts and reinstalls of the server, another on every other server) or, for older games, by IP
address. Commands are signed with the operator key (server_operator_key.txt, made at the first start), from this PC or
any other; bans are kept in server_bans.json:

    python3 gtav_online_server.py admin list
    python3 gtav_online_server.py admin --server our.server.org --key KEY kick Bob 30 griefing
    python3 gtav_online_server.py admin ban 7f3a91c20b4d 7d
    python3 gtav_online_server.py admin unban 7f3a91c20b4d

Run it with Python 3.7 or newer, nothing else to install:

    python3 gtav_online_server.py [--port 7788] [--name "Our server"] [--no-server-session]

Players on the same network use this PC's address; players elsewhere need UDP port 7788 forwarded to this PC on its
router (or the server on a VPS). See README.txt.
"""
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import select
import socket
import struct
import sys
import time

VERSION = 1
MAGIC = 0xA8
HELLO, WELCOME, LOOKUP, FOUND, PEER, RELAY, RELAYED, LIST, LISTED, BYE = range(1, 11)
REMOVED, ADMIN, ADMIN_REPLY = 11, 12, 13           # 2026-11-03: the operator's moderation
W_COOKIE, W_REGISTERED, W_REFUSED, W_BANNED, W_KICKED = 0, 1, 2, 3, 4   # WELCOME's status (3, 4: 2026-11-03)
F_HOSTING, F_PUBLIC, F_ID = 1, 2, 4               # HELLO's flags (F_ID, 2026-11-03: the player's id and name follow)
C_SEEN = 5                                        # p2p.cpp's address kinds: "where its packets come from"
MIN_HELLO = 160          # a HELLO is padded to this: an answer to an unproven address is never bigger than what came in
NAME_CHARS, NAME_BYTES = 40, 96   # the server's name: 40 letters or 32 Chinese characters (2026-11-09; its WELCOME stays within MIN_HELLO)
CLIENT_TIMEOUT = 45.0    # seconds without a HELLO (players send one every 10 s)
CODE_DIGITS = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # p2p.cpp's session codes: Crockford's base 32
ROOM_GRACE = 10.0        # the server's session: seconds the game has to hand it to a player itself after the host left
ROOM_CLAIM = 25.0        # seconds a player the server named has to start hosting before the next one is named
ROOM_STALE_HOST = 15.0   # a host this long silent (its game crashed) gives way to the player the game made host
ROOM_REMEMBER = 120.0    # seconds a player who left the server's session keeps its place in the join order
MAX_PACKET = 1500
KICK_MINUTES = 10        # 2026-11-03: a kick keeps the player out of the server's session this long (unless told otherwise)
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = HERE             # where the server keeps its session code, operator key and bans (--state-dir)


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


class Client:
    __slots__ = ("addr", "key", "node", "secret", "net", "flags", "host_hash", "cands", "listing", "listed_at",
                 "seen_at", "first_at", "tokens", "bytes", "refill_at", "relayed", "dropped", "pid", "pname", "room_since")

    def __init__(self, addr, key, now):
        self.addr, self.key = addr, key
        self.node, self.secret, self.net, self.flags = 0, b"", 0, 0
        self.host_hash, self.cands, self.listing, self.listed_at = b"", b"\0", None, 0.0
        self.seen_at = self.first_at = self.refill_at = now
        self.tokens = self.bytes = 0.0
        self.relayed = self.dropped = 0
        self.pid, self.pname, self.room_since = None, "", 0.0   # 2026-11-03: its id (8 bytes; None: an older game), name


def addr_key(addr):
    """(ip text, port) with IPv4-mapped IPv6 addresses as plain IPv4"""
    ip = ipaddress.ip_address(addr[0].split("%")[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (str(ip), addr[1])


def cand(key, kind=C_SEEN):
    """An address as p2p.cpp's PutCand writes it: kind << 1 | v6, the IP, the port"""
    ip = ipaddress.ip_address(key[0])
    return bytes([kind << 1 | (ip.version == 6)]) + ip.packed + struct.pack(">H", key[1])


def read_cands(data, pos, limit=10):
    """A count, then that many addresses (PutCand); the raw bytes back (passed on as they came) and where they end"""
    if pos >= len(data):
        raise ValueError
    count, start, pos = data[pos], pos, pos + 1
    for _ in range(count):
        if pos >= len(data):
            raise ValueError
        pos += 1 + (16 if data[pos] & 1 else 4) + 2
    if pos > len(data) or count > limit:
        raise ValueError
    return data[start:pos], pos


def read_text(data, pos, limit):
    if pos >= len(data):
        raise ValueError
    n = data[pos]
    raw = data[pos + 1:pos + 1 + n]
    if len(raw) != n:
        raise ValueError
    text = "".join(c for c in raw.decode("utf-8", "replace") if c.isprintable())
    return text[:limit], pos + 1 + n


def text(s, limit):
    # 2026-11-09 (a server host: a longer Chinese room name showed as "å¬çæ¡¡..."): whole characters only. Cut inside a
    # character the name wasn't UTF-8 any more, and the games read it as another encoding.
    raw = s.encode("utf-8")[:limit].decode("utf-8", "ignore").encode("utf-8")
    return bytes([len(raw)]) + raw


def session_names(code):
    """p2p.cpp's StartSession: the key, the network id and the DHT's (and this server's) host name of a session code"""
    key = hashlib.sha256(("gtavmp-p2p-1|" + code).encode()).digest()
    net = struct.unpack(">I", hashlib.sha256(b"net|" + key).digest()[:4])[0]
    return net, hashlib.sha1(b"host|" + key).digest()


def room_code(fixed):
    """The server's own session's code: --session-code, or a random one made at the first start and kept in a file
    beside this script (the same code after a restart)"""
    if fixed:
        code = "".join(c for c in fixed.upper() if c in CODE_DIGITS)
        if len(code) != 12:
            raise SystemExit("--session-code: 12 characters of %s" % CODE_DIGITS)
        return code
    path = os.path.join(STATE, "server_session_code.txt")
    try:
        with open(path) as f:
            code = f.read().strip()
        if len(code) == 12 and all(c in CODE_DIGITS for c in code):
            return code
    except OSError:
        pass
    code = "".join(CODE_DIGITS[b % 32] for b in os.urandom(12))
    try:
        with open(path, "w") as f:
            f.write(code + "\n")
    except OSError:
        pass
    return code


def operator_key(fixed):
    """2026-11-03: the key the operator's commands are signed with (python3 gtav_online_server.py admin ...):
    --operator-key, or a random one made at the first start and kept in server_operator_key.txt beside this script"""
    if fixed:
        return fixed.strip()
    path = os.path.join(STATE, "server_operator_key.txt")
    try:
        with open(path) as f:
            key = f.read().strip()
        if len(key) >= 16:
            return key
    except OSError:
        pass
    key = "".join(CODE_DIGITS[b % 32] for b in os.urandom(26))
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)   # the owner's only
        with os.fdopen(fd, "w") as f:
            f.write(key + "\n")
    except OSError:
        log("can't keep the operator key in %s: it's %s for this run" % (path, key))
    return key


def admin_mac(key, body):
    """An operator command's signature: HMAC-SHA256 with the operator key over everything before it, 16 bytes"""
    return hmac.new(key.encode(), b"gtavmp-admin|" + body, hashlib.sha256).digest()[:16]


def pid_text(pid):
    """A player's id as the operator sees and types it (12 hex digits; a game before 3 Nov 2026 sends none)"""
    return pid.hex()[:12] if pid else "-"


def span_text(minutes):
    if not minutes:
        return "for good"
    if minutes < 120:
        return "for %d min" % minutes
    if minutes < 2880:
        return "for %d h" % ((minutes + 59) // 60)
    return "for %d days" % ((minutes + 1439) // 1440)


def parse_span(word):
    """'30m', '2h', '7d', 'forever' (or 'perm'): minutes (0 for good); None if it isn't a span"""
    w = word.lower()
    if w in ("forever", "perm", "permanent", "0"):
        return 0
    unit = {"m": 1, "h": 60, "d": 1440}.get(w[-1:], None)
    num = w[:-1] if unit else w
    if not num.isdigit():
        return None
    return max(1, int(num) * (unit or 1))


class Server:
    def __init__(self, args):
        self.args = args
        self.secret = os.urandom(32)
        self.clients = {}       # addr_key -> Client
        self.by_node = {}       # (net, node) -> Client
        self.hosts = {}         # host hash -> Client
        self.per_ip = {}        # ip -> registrations
        self.relayed = self.relay_dropped = self.joins = 0
        self.sock = self.open_socket(args.bind, args.port)
        self.started = time.monotonic()
        # the server's own session (2026-11-01): its code, network id and host name; who's in it, in join order
        self.room = None if args.no_server_session else room_code(args.session_code)
        self.room_net, self.room_hash = session_names(self.room) if self.room else (0, b"")
        self.room_order = {}        # node -> (when it first came into the session, last seen in it)
        self.room_named = None      # (node, when): the player the server named to host, while nobody hosts
        self.room_lost_at = 0.0     # when the session's host went (the game's own handover gets ROOM_GRACE)
        self.room_had_host = False
        # 2026-11-03: the operator's moderation: the key its commands are signed with, bans and kicks (bans kept in
        # server_bans.json beside this script), removals being told again, commands already done (no replays)
        self.op_key = operator_key(args.operator_key)
        self.bans_path = os.path.join(STATE, "server_bans.json")
        self.bans = []
        self.load_bans()
        self.removals = []          # (net, node, kind, minutes, why, until)
        self.admin_seen = {}        # nonce -> when
        self.admin_fails = {}       # ip -> (count, since)

    def open_socket(self, bind, port):
        family = socket.AF_INET if bind and ":" not in bind else socket.AF_INET6
        try:
            s = socket.socket(family, socket.SOCK_DGRAM)
        except OSError:
            family, s = socket.AF_INET, socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if family == socket.AF_INET6:
            try:
                s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)   # IPv4 and IPv6 on one socket
            except (OSError, AttributeError):
                pass
        for opt in (socket.SO_RCVBUF, socket.SO_SNDBUF):
            try:
                s.setsockopt(socket.SOL_SOCKET, opt, 4 << 20)
            except OSError:
                pass
        if sys.platform == "win32" and hasattr(socket, "SIO_UDP_CONNRESET"):
            try:
                s.ioctl(socket.SIO_UDP_CONNRESET, False)   # a player gone away isn't an error on this socket
            except (OSError, ValueError):
                pass   # recvfrom's ConnectionResetError is skipped instead
        s.bind((bind or ("::" if family == socket.AF_INET6 else "0.0.0.0"), port))
        s.setblocking(False)
        return s

    # ---- cookies: an address proves it gets this server's answers before anything is kept for it or listed to it

    def cookie(self, key, epoch):
        return hmac.new(self.secret, ("%s|%d|%d" % (key[0], key[1], epoch)).encode(), hashlib.sha256).digest()[:16]

    def cookie_ok(self, key, got, now):
        epoch = int(now // 60)
        return hmac.compare_digest(got, self.cookie(key, epoch)) or hmac.compare_digest(got, self.cookie(key, epoch - 1))

    def send(self, client_or_addr, payload):
        addr = client_or_addr.addr if isinstance(client_or_addr, Client) else client_or_addr
        try:
            self.sock.sendto(payload, addr)
        except OSError:
            pass

    # ---- packets

    def handle(self, data, addr, now):
        if len(data) < 3 or data[0] != MAGIC or data[2] != VERSION:
            return
        try:
            key = addr_key(addr)
        except ValueError:
            return
        kind = data[1]
        try:
            if kind == RELAY:
                self.on_relay(data, key, now)
            elif kind == HELLO:
                self.on_hello(data, addr, key, now)
            elif kind == LOOKUP:
                self.on_lookup(data, key, now)
            elif kind == LIST:
                self.on_list(data, addr, key, now)
            elif kind == ADMIN:
                self.on_admin(data, addr, key, now)
            elif kind == BYE:
                c = self.clients.get(key)
                if c and len(data) >= 11 and struct.unpack_from(">Q", data, 3)[0] == c.node:
                    self.forget(c, "left")
        except (ValueError, struct.error, IndexError):
            pass

    def welcome(self, addr, key, status, ts, now, extra=b""):
        out = bytes([MAGIC, WELCOME, VERSION, status]) + struct.pack(">I", ts) + self.cookie(key, int(now // 60))
        out += cand(key) + struct.pack(">HH", min(65535, sum(1 for c in self.hosts.values() if c.listing)),
                                       min(65535, len(self.clients)))
        out += text(self.args.name[:NAME_CHARS], NAME_BYTES)
        out += text(self.room or "", 12)   # 2026-11-01: the server's own session's code ("" none)
        self.send(addr, out + extra)       # 2026-11-03: W_BANNED / W_KICKED: minutes left (0 for good), why

    def on_hello(self, data, addr, key, now):
        if len(data) < MIN_HELLO:
            return
        pos = 3
        got = data[pos:pos + 16]; pos += 16
        node, = struct.unpack_from(">Q", data, pos); pos += 8
        secret = data[pos:pos + 16]; pos += 16
        net, ts = struct.unpack_from(">II", data, pos); pos += 8
        flags = data[pos]; pos += 1
        host_hash = data[pos:pos + 20]; pos += 20
        cands, pos = read_cands(data, pos)
        listing = None
        if flags & F_PUBLIC:
            code, pos = read_text(data, pos, 12)
            name, pos = read_text(data, pos, 31)
            players, max_players = data[pos], data[pos + 1]; pos += 2
            build, pos = read_text(data, pos, 16)
            mods, pos = read_text(data, pos, 24)
            note, pos = read_text(data, pos, 60)
            if len(code) == 12 and code.isalnum():
                listing = (code, name or "Player", players, max_players, build, mods, note)
        pid, pname = None, ""
        if flags & F_ID:   # 2026-11-03: the player's id on this server (from its device's own secret), its name in ours
            pid = bytes(data[pos:pos + 8]); pos += 8
            pname, pos = read_text(data, pos, 31)
            if len(pid) != 8 or not any(pid):
                pid = None
        if not self.cookie_ok(key, got, now):
            self.welcome(addr, key, W_COOKIE, ts, now)     # no state for an address that hasn't shown it gets answers
            return
        if not node:
            return
        ban = self.ban_for(pid, key[0], net)
        if ban:
            # turned away: a ban from the whole server, a kick from its own session (for a while); its game is told
            # again to leave the server's session while it's still in it (the first word may have gone missing)
            left = 0 if not ban.get("until") else max(1, int((ban["until"] - time.time() + 59) // 60))
            why = ban.get("reason", "")
            kind = 2 if ban.get("kind") == "ban" else 1
            old = self.clients.get(key)
            if old is not None:
                self.forget(old, "turned away (%s)" % ("banned" if kind == 2 else "kicked"))
            if self.room and net == self.room_net:
                self.send(addr, self.removed_packet(key, node, kind, left, why, now))
            self.welcome(addr, key, W_BANNED if kind == 2 else W_KICKED, ts, now, struct.pack(">H", min(left, 65535)) + text(why, 60))
            return
        c = self.clients.get(key)
        if c is None:
            other = self.by_node.get((net, node)) if net else None
            if other is not None and other.key != key:
                # the same player from another address (its phone changed networks): its secret says it's the same
                if other.secret != secret and now - other.seen_at < CLIENT_TIMEOUT:
                    self.welcome(addr, key, W_REFUSED, ts, now)
                    return
                self.forget(other, "moved to %s:%d" % key)
            if len(self.clients) >= self.args.max_players or self.per_ip.get(key[0], 0) >= self.args.max_per_ip:
                self.welcome(addr, key, W_REFUSED, ts, now)
                log("refused %s:%d: %s" % (key[0], key[1], "the server is full" if len(self.clients) >= self.args.max_players else "too many from one address"))
                return
            c = Client(addr, key, now)
            c.tokens, c.bytes = 2.0 * self.args.relay_packets, 2048.0 * self.args.relay_kbytes   # a full share to begin with
            self.clients[key] = c
            self.per_ip[key[0]] = self.per_ip.get(key[0], 0) + 1
        elif c.node != node or c.secret != secret:
            self.unindex(c)                                 # another game on the same address and port: starts over
        if (c.net, c.node) != (net, node):
            self.unindex(c)
        c.node, c.secret, c.net, c.flags, c.cands, c.seen_at = node, secret, net, flags, cands, now
        c.pid, c.pname = pid, pname or c.pname
        if net:
            self.by_node[(net, node)] = c
        hosting = bool(flags & F_HOSTING and net and any(host_hash))
        if c.host_hash and (not hosting or c.host_hash != host_hash):
            if self.hosts.get(c.host_hash) is c:
                del self.hosts[c.host_hash]
                if c.host_hash == self.room_hash and self.room:
                    self.room_host_gone(c, now)
                else:
                    log("session closed by %s:%d" % key)
            c.host_hash = b""
        if hosting and self.hosts.get(host_hash) is not c:
            # one host a code: another device still hosting under it (the same profile copied) keeps it
            holder = self.hosts.get(host_hash)
            stale = CLIENT_TIMEOUT if host_hash != self.room_hash else ROOM_STALE_HOST
            if holder is None or now - holder.seen_at >= stale or holder.secret == secret:
                if holder is not None:
                    holder.host_hash, holder.listing = b"", None
                self.hosts[host_hash] = c
                if host_hash == self.room_hash and self.room:
                    self.room_named, self.room_had_host = None, True
                    log("the server's session: %s:%d hosts it now" % key)
                else:
                    log("session opened by %s:%d%s" % (key[0], key[1], " (public: %s)" % listing[1] if listing else ""))
        c.host_hash = host_hash if hosting and self.hosts.get(host_hash) is c else b""
        if self.room and net == self.room_net:
            first = self.room_order.get(node, (now, now))[0]
            self.room_order[node] = (first, now)
            if not c.room_since:   # 2026-11-03: who comes into the server's session (the operator's log)
                c.room_since = now
                log("the server's session: %s (id %s) came in from %s:%d" % (c.pname or "a player (an older game)", pid_text(c.pid), key[0], key[1]))
        elif c.room_since:
            self.room_left(c, "left it")
        if listing and not c.listing:
            c.listed_at = now
        c.listing = listing if c.host_hash else None
        self.welcome(addr, key, W_REGISTERED, ts, now)

    def on_lookup(self, data, key, now):
        c = self.clients.get(key)
        if c is None or not c.net or len(data) < 3 + 16 + 20 or not self.cookie_ok(key, data[3:19], now):
            return
        host_hash = data[19:39]
        h = self.hosts.get(host_hash)
        if h is None or h is c or h.net != c.net or now - h.seen_at >= CLIENT_TIMEOUT:
            # the server's session with nobody hosting it: 1 after the node = "host it yourself" (older games stop reading)
            yours = self.room and host_hash == self.room_hash and self.room_name_host(c, now)
            self.send(c, bytes([MAGIC, FOUND, VERSION]) + host_hash + struct.pack(">Q", 0) + bytes([1 if yours else 0]))
            return
        # both learn the other's addresses: the joiner tries the host's, the host's packets open its router to the joiner
        self.send(c, bytes([MAGIC, FOUND, VERSION]) + host_hash + struct.pack(">Q", h.node) + cand(h.key) + h.cands)
        self.send(h, bytes([MAGIC, PEER, VERSION]) + struct.pack(">Q", c.node) + cand(c.key) + c.cands)
        self.joins += 1

    def room_name_host(self, c, now):
        """Nobody hosts the server's session and c asks where its host is: whether c should host it. The player who came
        in first of those still looking (the order kept while they rejoin), after the game had its chance to hand the
        session over itself; one named who doesn't start hosting in time goes to the back."""
        if self.room_had_host and now - self.room_lost_at < ROOM_GRACE:
            return False
        if self.room_named:
            node, at = self.room_named
            named = self.by_node.get((self.room_net, node))   # None while its game switches from joining to hosting
            if now - at < ROOM_CLAIM and (named is None or now - named.seen_at < 12):
                return named is c
            if node in self.room_order:
                self.room_order[node] = (now, self.room_order[node][1])   # to the back of the line
            log("the server's session: the player named to host didn't start it, naming the next one")
            self.room_named = None
        waiting = [x for x in self.clients.values() if x.net == self.room_net and now - x.seen_at < 12 and x.node in self.room_order]
        if not waiting:
            return False
        first = min(waiting, key=lambda x: self.room_order[x.node][0])
        self.room_named = (first.node, now)
        log("the server's session: nobody hosts it, %s:%d is the next player in line: it hosts now" % first.key)
        return first is c

    def room_host_gone(self, c, now):
        """The server's session's host stopped hosting (left, timed out, moved): the clock for the game's own handover"""
        self.room_lost_at = now
        log("the server's session: its host %s:%d left" % c.key)

    def on_relay(self, data, key, now):
        c = self.clients.get(key)
        if c is None or not c.net or len(data) < 11 or len(data) > MAX_PACKET:
            return
        dst = self.by_node.get((c.net, struct.unpack_from(">Q", data, 3)[0]))
        if dst is None or dst is c or now - dst.seen_at >= CLIENT_TIMEOUT:
            return
        # each player's own share: packets and bytes a second, with a burst of two seconds' worth
        elapsed, c.refill_at = now - c.refill_at, now
        rate, byte_rate = self.args.relay_packets, self.args.relay_kbytes * 1024
        c.tokens = min(2 * rate, c.tokens + elapsed * rate)
        c.bytes = min(2 * byte_rate, c.bytes + elapsed * byte_rate)
        if c.tokens < 1 or c.bytes < len(data):
            c.dropped += 1
            self.relay_dropped += 1
            return
        c.tokens -= 1
        c.bytes -= len(data)
        c.relayed += 1
        self.relayed += 1
        self.send(dst, bytes([MAGIC, RELAYED, VERSION]) + struct.pack(">Q", c.node) + data[11:])

    def on_list(self, data, addr, key, now):
        if len(data) < 3 + 16 + 2 or not self.cookie_ok(key, data[3:19], now):
            return
        offset, = struct.unpack_from(">H", data, 19)
        hosts = sorted((h for h in self.hosts.values() if h.listing and now - h.seen_at < CLIENT_TIMEOUT and h.host_hash != self.room_hash),
                       key=lambda h: (-h.listing[2], h.listing[1].lower()))
        listed = [h.listing + (h.listed_at,) for h in hosts]
        if self.room:
            # the server's own session first: its players (those in it lately), any build ("dev"), no mods named
            players = sum(1 for c in self.clients.values() if c.net == self.room_net and now - c.seen_at < 25)
            listed.insert(0, (self.room, self.args.name[:NAME_CHARS], min(players, 255), 32, "dev", "",
                              "The server's session: the first player in hosts it", self.started))
        entries = []
        size = 0
        for code, name, players, max_players, build, mods, note, since in listed[offset:]:
            e = text(code, 12) + text(name, NAME_BYTES) + bytes([players, max_players]) + text(build, 16) + text(mods, 24) + \
                text(note, 60) + struct.pack(">H", min(65535, int((now - since) // 60)))
            if size + len(e) > 1100 or len(entries) == 255:
                break
            entries.append(e)
            size += len(e)
        self.send(addr, bytes([MAGIC, LISTED, VERSION]) + struct.pack(">HHB", min(65535, len(listed)), offset, len(entries)) + b"".join(entries))

    # ---- the operator's moderation (2026-11-03, a server operator: "remotely list lobby members, kick disruptive players,
    # and cross-session ban users by stable client IDs"). A player's id is the one its game gives this server (made
    # from a secret only that device has and this server's session code: the same after restarts, another on every
    # other server); games before 3 Nov 2026 give none, and only their IP address tells them apart.

    def load_bans(self):
        try:
            with open(self.bans_path) as f:
                bans = json.load(f).get("bans", [])
            self.bans = [b for b in bans if isinstance(b, dict) and (b.get("id") or b.get("ip"))]
        except (OSError, ValueError, AttributeError):
            self.bans = []

    def save_bans(self):
        """The bans (not the kicks: minutes long) in server_bans.json, for the next start"""
        try:
            tmp = self.bans_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"bans": [b for b in self.bans if b.get("kind") == "ban"]}, f, indent=1)
            os.replace(tmp, self.bans_path)
        except OSError as e:
            log("can't write %s: %s" % (self.bans_path, e))

    def ban_for(self, pid, ip, net):
        """What turns this player away now: a ban (from the whole server), or a kick (from its own session); None if
        nothing. A ban by IP address (an older game, no id) is anyone's from it."""
        wall = time.time()
        if any(b.get("until") and b["until"] <= wall for b in self.bans):
            ended = [b for b in self.bans if b.get("until") and b["until"] <= wall]
            self.bans = [b for b in self.bans if b not in ended]
            for b in ended:
                log("operator: %s of %s ended" % (b.get("kind", "ban"), b.get("name") or b.get("id") or b.get("ip")))
            if any(b.get("kind") == "ban" for b in ended):
                self.save_bans()
        hexid = pid.hex() if pid else None
        for b in self.bans:
            if not ((hexid and b.get("id") and hexid.startswith(b["id"])) or (not b.get("id") and b.get("ip") == ip)):
                continue
            if b.get("kind") == "ban" or (self.room and net == self.room_net):
                return b
        return None

    def removed_packet(self, key, node, kind, minutes, why, now):
        """REMOVED for the player at key: player node was taken out (kind 1 kicked, 2 banned; minutes 0 for good). It
        carries that player's cookies (this minute's and the last): its game takes the word only from this server."""
        epoch = int(now // 60)
        return (bytes([MAGIC, REMOVED, VERSION]) + self.cookie(key, epoch) + self.cookie(key, epoch - 1) +
                struct.pack(">QBH", node, kind, min(minutes, 65535)) + text(why, 60))

    def tell_removal(self, net, node, kind, minutes, why, now):
        """Every game in that session: nothing more to or from that player (their games drop it 8 s on)"""
        for c in list(self.clients.values()):
            if c.net == net and c.node != node:
                self.send(c, self.removed_packet(c.key, node, kind, minutes, why, now))

    def take_out(self, c, kind, minutes, why, now):
        """A player out of the server's session: its game leaves and tells the player why, the others stop talking
        to it (said again for 3 s), and this server forgets it"""
        self.send(c, self.removed_packet(c.key, c.node, kind, minutes, why, now))
        if c.net:
            self.tell_removal(c.net, c.node, kind, minutes, why, now)
            self.removals.append((c.net, c.node, kind, minutes, why, now + 3.5))
        self.forget(c, "taken out by the operator (%s %s)" % ("kicked" if kind == 1 else "banned", span_text(minutes)))

    def find_players(self, who, room_only):
        """The players an operator's word names: an id or its first 4+ digits, a name (any case), an IP address"""
        w = who.strip().lower()
        players = [c for c in self.clients.values() if not room_only or (self.room and c.net == self.room_net)]
        if len(w) >= 4 and all(ch in "0123456789abcdef" for ch in w):
            found = [c for c in players if c.pid and c.pid.hex().startswith(w)]
            if found:
                return found
        found = [c for c in players if c.pname and c.pname.lower() == w]
        if found:
            return found
        try:
            ip = str(ipaddress.ip_address(w))
            return [c for c in players if c.key[0] == ip]
        except ValueError:
            pass
        # 2026-11-07: the start of a name. Games before 7 Nov send the server up to 31 bytes of the name but show 16 in the
        # game (a long Chinese name: its first 5 characters), so the name players report is the start of the one here.
        # Two players whose names start so: the command says it's ambiguous, as for two of the same name.
        if len(w) >= 2:
            return [c for c in players if c.pname and c.pname.lower().startswith(w)]
        return []

    def player_line(self, c, now):
        host = self.hosts.get(c.host_hash) is c if c.host_hash else False
        name = (c.pname or "-") + (" (host)" if host else "")
        since = c.room_since or c.first_at
        return "  %-13s %-24s %-24s %d min" % (pid_text(c.pid), name[:24], "%s:%d" % c.key, int((now - since) // 60))

    def command(self, words, now):
        """An operator command (signed with the operator key); what it did, as lines of text"""
        if not words or words[0] in ("help", "?"):
            return ("Commands: list | list all | kick <who> [minutes] [why] | ban <who> [30m|2h|7d|forever] [why] | "
                    "unban <who> | bans. <who>: a player's id (its first 4 digits or more), name, or IP address.")
        verb, rest = words[0].lower(), words[1:]
        if verb == "list":
            everyone = bool(rest) and rest[0].lower() == "all"
            room = [c for c in self.clients.values() if self.room and c.net == self.room_net]
            room.sort(key=lambda c: c.room_since or c.first_at)
            host = self.hosts.get(self.room_hash) if self.room else None
            out = []
            if self.room:
                out.append("The server's session %s-%s-%s: %d player%s%s" % (
                    self.room[:4], self.room[4:8], self.room[8:], len(room), "" if len(room) == 1 else "s",
                    ", host %s" % (host.pname or pid_text(host.pid)) if host else ", nobody hosting"))
                out.append("  %-13s %-24s %-24s %s" % ("ID", "NAME", "FROM", "IN FOR"))
                out += [self.player_line(c, now) for c in room]
            others = [c for c in self.clients.values() if c not in room]
            sessions = len({c.net for c in others if c.net})
            out.append("Others on this server: %d player%s in %d other session%s, %d in none (a launcher's list)%s" % (
                sum(1 for c in others if c.net), "" if len(others) == 1 else "s", sessions, "" if sessions == 1 else "s",
                sum(1 for c in others if not c.net), "" if everyone or not others else " (list all: each of them)"))
            if everyone:
                out += [self.player_line(c, now) + ("  hosts a session" if c.host_hash else "  in a session" if c.net else "")
                        for c in others]
            active = [b for b in self.bans if not b.get("until") or b["until"] > time.time()]
            out.append("Bans and kicks: %d (bans lists them)" % len(active))
            return "\n".join(out)
        if verb in ("kick", "ban"):
            if not rest:
                return "%s whom? A player's id (its first 4 digits or more), name, or IP address." % verb
            kick = verb == "kick"
            found = self.find_players(rest[0], kick)
            minutes = KICK_MINUTES if kick else 0
            reason_words = rest[1:]
            if reason_words:
                span = parse_span(reason_words[0])   # kick: minutes ("30" or "30m", "2h"); ban: "7d", "forever"...
                if span is not None and (span or not kick):
                    minutes, reason_words = span, reason_words[1:]
            why = " ".join(reason_words)[:60]
            w = rest[0].strip().lower()
            offline = None
            if not found and not kick:
                # someone not on the server now: an id from the log (12 digits at least) or an IP address
                try:
                    offline = {"id": None, "ip": str(ipaddress.ip_address(w))}
                except ValueError:
                    if len(w) >= 12 and all(ch in "0123456789abcdef" for ch in w):
                        offline = {"id": w[:16], "ip": None}
            if not found and not offline:
                return ("No one in the server's session is %s (list shows them)." if kick else
                        "No one on the server is %s now (list all shows them; an id from the log needs 12 digits).") % rest[0]
            if len({c.pid or c.key[0] for c in found}) > 1:
                return "%s is more than one player: use the id.\n" % rest[0] + "\n".join(self.player_line(c, now) for c in found)
            c = found[0] if found else None
            wall = time.time()
            entry = {"kind": verb, "id": (c.pid.hex() if c.pid else None) if c else offline["id"],
                     "ip": (None if c.pid else c.key[0]) if c else offline["ip"], "name": c.pname if c else "",
                     "reason": why, "since": int(wall), "until": int(wall + minutes * 60) if minutes else 0}
            self.bans = [b for b in self.bans if not ((entry["id"] and b.get("id") == entry["id"]) or (entry["ip"] and b.get("ip") == entry["ip"]))]
            self.bans.append(entry)
            if not kick:
                self.save_bans()
            who = "%s (id %s, %s)" % (c.pname or "a player", pid_text(c.pid), c.key[0]) if c else (entry["id"] or entry["ip"])
            for x in found:
                if (self.room and x.net == self.room_net) or not kick:
                    self.take_out(x, 1 if kick else 2, minutes, why, now)
            log("operator: %s %s %s%s" % ("kicked" if kick else "banned", who, span_text(minutes), ": " + why if why else ""))
            note = "" if entry["id"] else " (by IP address: a game from before 3 Nov 2026 sends no id, and addresses change on many networks)"
            return "%s %s %s%s.%s" % ("Kicked" if kick else "Banned", who, span_text(minutes), ": " + why if why else "", note)
        if verb == "unban":
            if not rest:
                return "unban whom? An id (as bans lists it), a name or an IP address."
            w = rest[0].lower()
            gone = [b for b in self.bans if (b.get("id") and b["id"].startswith(w) and len(w) >= 4) or
                    (b.get("name") and b["name"].lower() == w) or b.get("ip") == w]
            if not gone:
                return "No ban or kick for %s (bans lists them)." % rest[0]
            self.bans = [b for b in self.bans if b not in gone]
            self.save_bans()
            for b in gone:
                log("operator: unbanned %s" % (b.get("name") or b.get("id") or b.get("ip")))
            return "Unbanned: " + ", ".join(b.get("name") or (b.get("id") or "")[:12] or b.get("ip") for b in gone) + "."
        if verb == "bans":
            wall = time.time()
            active = [b for b in self.bans if not b.get("until") or b["until"] > wall]
            if not active:
                return "No bans or kicks."
            lines = ["  %-13s %-24s %-6s %-12s %s" % ("ID / IP", "NAME", "KIND", "LEFT", "WHY")]
            for b in active:
                left = "for good" if not b.get("until") else span_text(max(1, int((b["until"] - wall + 59) // 60)))[4:]
                lines.append("  %-13s %-24s %-6s %-12s %s" % ((b.get("id") or "")[:12] or b.get("ip"), (b.get("name") or "-")[:24],
                                                             b.get("kind", "ban"), left, b.get("reason", "")))
            return "\n".join(lines)
        return "Not a command: %s (help lists them)." % words[0]

    def on_admin(self, data, addr, key, now):
        """An operator command: cookie (the address gets this server's answers), a nonce, the command, the operator
        key's signature over them. The answer goes back in parts."""
        if len(data) < MIN_HELLO:
            return
        if not self.cookie_ok(key, data[3:19], now):
            self.welcome(addr, key, W_COOKIE, 0, now)   # the operator's tool asks again with it
            return
        nonce = bytes(data[19:27])
        n, = struct.unpack_from(">H", data, 27)
        body_end = 29 + n
        if body_end + 16 > len(data):
            return
        reply = lambda status, msg: self.admin_reply(addr, nonce, status, msg)
        if not hmac.compare_digest(admin_mac(self.op_key, bytes(data[3:body_end])), bytes(data[body_end:body_end + 16])):
            count, since = self.admin_fails.get(key[0], (0, now))
            if now - since > 60:
                count, since = 0, now
            self.admin_fails[key[0]] = (count + 1, since)
            if count < 5:
                log("operator command with a wrong key from %s" % key[0])
                reply(1, "Wrong operator key (server_operator_key.txt beside the server's script).")
            return
        if nonce in self.admin_seen:   # asked again (an answer went missing): the same answer, not done twice
            reply(0, self.admin_seen[nonce][1])
            return
        words = data[29:body_end].decode("utf-8", "replace").split()
        try:
            out = self.command(words, now)
        except Exception as e:   # an operator's typo mustn't stop the server
            out = "That didn't work: %s" % e
        self.admin_seen[nonce] = (now, out)
        reply(0, out)

    def admin_reply(self, addr, nonce, status, msg):
        raw = msg.encode("utf-8")
        parts = [raw[i:i + 1100] for i in range(0, len(raw), 1100)] or [b""]
        for i, part in enumerate(parts[:255]):
            self.send(addr, bytes([MAGIC, ADMIN_REPLY, VERSION]) + nonce + bytes([status, i, min(len(parts), 255)]) + part)

    # ---- bookkeeping

    def unindex(self, c):
        if c.net and self.by_node.get((c.net, c.node)) is c:
            del self.by_node[(c.net, c.node)]
        if c.host_hash and self.hosts.get(c.host_hash) is c:
            del self.hosts[c.host_hash]
            if c.host_hash == self.room_hash and self.room:
                self.room_host_gone(c, time.monotonic())
            else:
                log("session closed by %s:%d" % c.key)
        c.host_hash, c.listing = b"", None

    def room_left(self, c, why):
        log("the server's session: %s (id %s) %s after %d min" % (c.pname or "a player (an older game)", pid_text(c.pid), why,
                                                                 int((time.monotonic() - c.room_since) // 60)))
        c.room_since = 0.0

    def forget(self, c, why):
        if c.room_since:
            self.room_left(c, why)
        self.unindex(c)
        if self.clients.get(c.key) is c:
            del self.clients[c.key]
            n = self.per_ip.get(c.key[0], 1) - 1
            if n > 0:
                self.per_ip[c.key[0]] = n
            else:
                self.per_ip.pop(c.key[0], None)
        if self.args.verbose:
            log("player %s:%d %s (relayed %d packets, dropped %d)" % (c.key[0], c.key[1], why, c.relayed, c.dropped))

    def maintain(self, now):
        for c in [c for c in self.clients.values() if now - c.seen_at >= CLIENT_TIMEOUT]:
            self.forget(c, "timed out")
        for node in [n for n, (_, last) in self.room_order.items() if now - last >= ROOM_REMEMBER]:
            del self.room_order[node]
        # 2026-11-03: the session told again of a player the operator took out (a packet can go missing), for 3 s
        self.removals = [r for r in self.removals if now < r[5]]
        for net, node, kind, minutes, why, _ in self.removals:
            self.tell_removal(net, node, kind, minutes, why, now)
        for nonce in [n for n, (at, _) in self.admin_seen.items() if now - at > 300]:
            del self.admin_seen[nonce]

    def status(self, interval):
        log("%d player%s, %d session%s (%d public), %.0f packets/s relayed%s, %d joins" % (
            len(self.clients), "" if len(self.clients) == 1 else "s", len(self.hosts), "" if len(self.hosts) == 1 else "s",
            sum(1 for h in self.hosts.values() if h.listing), self.relayed / interval,
            " (%d over a player's share)" % self.relay_dropped if self.relay_dropped else "", self.joins))
        self.relayed = self.relay_dropped = self.joins = 0

    def run(self):
        last_maintain = last_status = time.monotonic()
        while True:
            readable, _, _ = select.select([self.sock], [], [], 1.0)
            now = time.monotonic()
            if readable:
                for _ in range(2000):
                    try:
                        data, addr = self.sock.recvfrom(2048)
                    except (BlockingIOError, InterruptedError):
                        break
                    except ConnectionResetError:
                        continue
                    except OSError:
                        break
                    self.handle(data, addr, now)
            if now - last_maintain >= 1:
                self.maintain(now)
                last_maintain = now
            if now - last_status >= self.args.status:
                self.status(now - last_status)
                last_status = now


def local_addresses():
    """This PC's addresses on its networks (for the start message)"""
    found = []
    for target in ("192.0.2.1", "10.255.255.255"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((target, 9))   # no packet is sent: only the route is looked up
            ip = s.getsockname()[0]
            s.close()
            if ip not in found and not ip.startswith("127."):
                found.append(ip)
        except OSError:
            pass
    return found


def public_address(timeout=2.0):
    """This network's public IPv4 address, from a STUN server (as the game asks it); None when there's no answer"""
    for host in ("stun.l.google.com", "stun.cloudflare.com"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout)
            tx = os.urandom(12)
            s.sendto(b"\x00\x01\x00\x00\x21\x12\xa4\x42" + tx, (host, 19302 if "google" in host else 3478))
            data, _ = s.recvfrom(512)
            s.close()
            pos = 20
            while pos + 4 <= len(data):
                kind, length = struct.unpack_from(">HH", data, pos)
                if kind == 0x0020 and length >= 8 and data[pos + 5] == 1:
                    raw = bytes(b ^ m for b, m in zip(data[pos + 8:pos + 12], b"\x21\x12\xa4\x42"))
                    return socket.inet_ntoa(raw)
                pos += 4 + ((length + 3) & ~3)
        except OSError:
            continue
    return None


def admin_main(argv):
    """2026-11-03: an operator command for a running server, from its own PC or anywhere: python3 gtav_online_server.py
    admin [--server ADDRESS] [--key KEY] list | kick ... | ban ... | unban ... | bans"""
    ap = argparse.ArgumentParser(prog="gtav_online_server.py admin",
                                 description="A command for a running GTA V Online server, signed with its operator key")
    ap.add_argument("--server", default="127.0.0.1", help="the server: host or host:port (default 127.0.0.1, this PC)")
    ap.add_argument("--key", default="", help="the operator key (default: server_operator_key.txt beside this script)")
    ap.add_argument("--state-dir", default="", help="where the server keeps server_operator_key.txt (its --state-dir)")
    ap.add_argument("words", nargs=argparse.REMAINDER, help="list | list all | kick <who> [minutes] [why] | "
                    "ban <who> [30m|2h|7d|forever] [why] | unban <who> | bans | help")
    a = ap.parse_args(argv)
    key = a.key.strip()
    if not key:
        try:
            with open(os.path.join(a.state_dir or HERE, "server_operator_key.txt")) as f:
                key = f.read().strip()
        except OSError:
            print("No operator key: give --key, or run this beside the server's script (server_operator_key.txt).")
            return 2
    host, port = a.server, 7788
    if host.startswith("[") and "]" in host:                       # [IPv6]:port
        host, _, rest = host[1:].partition("]")
        port = int(rest[1:]) if rest.startswith(":") else port
    elif host.count(":") == 1:
        host, _, p = host.partition(":")
        port = int(p)
    try:
        family, _, _, _, addr = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)[0]
    except (socket.gaierror, IndexError):
        print("No such address: %s" % a.server)
        return 2
    s = socket.socket(family, socket.SOCK_DGRAM)
    s.settimeout(0.5)
    words = " ".join(a.words or ["help"]).encode("utf-8")[:1000]
    nonce, cookie = os.urandom(8), bytes(16)
    for _ in range(8):   # the same nonce each time: the server does a command once and answers it again
        body = cookie + nonce + struct.pack(">H", len(words)) + words
        packet = bytes([MAGIC, ADMIN, VERSION]) + body + admin_mac(key, body)
        s.sendto(packet + bytes(max(0, MIN_HELLO - len(packet))), addr)
        parts, deadline = {}, time.monotonic() + 1.5
        while time.monotonic() < deadline:
            try:
                data = s.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if len(data) < 4 or data[0] != MAGIC or data[2] != VERSION:
                continue
            if data[1] == WELCOME and data[3] == W_COOKIE and len(data) >= 24:
                cookie = data[8:24]   # this address's cookie: the command again with it
                break
            if data[1] == ADMIN_REPLY and len(data) >= 14 and data[3:11] == nonce:
                status, part, count = data[11], data[12], data[13]
                parts[part] = data[14:]
                if len(parts) >= count:
                    print(b"".join(parts[i] for i in sorted(parts)).decode("utf-8", "replace"))
                    return 0 if status == 0 else 1
    print("No answer from %s:%d (is the server running, and its UDP port open?)" % (host, port))
    return 2


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "admin":
        return admin_main(sys.argv[2:])
    ap = argparse.ArgumentParser(description="GTA V Online server for the iOS/macOS port's GTA Online sandbox")
    ap.add_argument("--port", type=int, default=7788, help="UDP port (default 7788)")
    ap.add_argument("--bind", default="", help="address to listen on (default: every address, IPv4 and IPv6)")
    ap.add_argument("--name", default="", help="the server's name in the players' launchers (40 letters or 32 Chinese characters at most)")
    ap.add_argument("--max-players", type=int, default=512, help="players at once (default 512)")
    ap.add_argument("--max-per-ip", type=int, default=32, help="players from one IP address (default 32)")
    ap.add_argument("--relay-packets", type=int, default=2000, help="a player's relayed packets a second (default 2000)")
    ap.add_argument("--relay-kbytes", type=int, default=2048, help="a player's relayed kilobytes a second (default 2048)")
    ap.add_argument("--status", type=float, default=300, help="seconds between status lines (default 300)")
    ap.add_argument("--no-stun", action="store_true", help="don't ask a STUN server for this network's public address")
    ap.add_argument("--verbose", action="store_true", help="a line for every player that leaves")
    ap.add_argument("--no-server-session", action="store_true", help="no session of the server's own in the list")
    ap.add_argument("--session-code", default="", help="the server's session's code (12 characters; default: made once, "
                    "kept in server_session_code.txt beside this script)")
    ap.add_argument("--operator-key", default="", help="the key operator commands are signed with (default: made once, "
                    "kept in server_operator_key.txt beside this script)")
    ap.add_argument("--state-dir", default="", help="where the server keeps server_session_code.txt, server_operator_key.txt "
                    "and server_bans.json (default: beside this script; a service that can't write there: a folder it can)")
    args = ap.parse_args()
    global STATE
    STATE = os.path.abspath(args.state_dir) if args.state_dir else HERE
    if args.state_dir:
        os.makedirs(STATE, exist_ok=True)
    if not args.name:
        args.name = (socket.gethostname().split(".")[0] or "GTA V") + "'s server"
    try:
        server = Server(args)
    except OSError as e:
        log("can't listen on UDP port %d: %s (is another server running?)" % (args.port, e))
        return 1
    log("GTA V Online server \"%s\" on UDP port %d" % (args.name, args.port))
    for ip in local_addresses():
        log("  players on this network:  %s:%d" % (ip, args.port))
    public = None if args.no_stun else public_address()
    if public:
        log("  players elsewhere:        %s:%d  (forward UDP port %d on the router to this PC first)" % (public, args.port, args.port))
    if server.room:
        log("The server's own session: code %s-%s-%s, at the top of the launcher's Join list (the first player in hosts it)" % (
            server.room[:4], server.room[4:8], server.room[8:]))
    log("In the game: launcher > Settings > GTA Online > Community Server, that address. Ctrl+C stops the server.")
    log("Moderation: python3 gtav_online_server.py admin list (kick, ban, unban, bans; help) on this PC; from another, "
        "add --server <this server's address> --key <the key in server_operator_key.txt>.%s" % (
            " %d ban%s kept from before." % (len(server.bans), "" if len(server.bans) == 1 else "s") if server.bans else ""))
    try:
        server.run()
    except KeyboardInterrupt:
        log("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
