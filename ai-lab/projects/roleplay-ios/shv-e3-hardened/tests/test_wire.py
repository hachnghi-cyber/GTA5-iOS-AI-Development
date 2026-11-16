import os, time, unittest
from src.rbp_wire import *

class WireTest(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))
        self.a,self.b,self.session = id16('a'),id16('b'),id16('s')
        self.f = test_frame(self.a,self.b,self.session,10)
        self.p = self.f.encode(self.key)
        self.rx = Receiver(self_id=self.b,allowed_sender=self.a,session=self.session,per_peer_key=self.key)
    def test_size_and_fields(self):
        self.assertEqual(len(self.p),96)
        self.assertEqual(Frame.decode(self.p,self.key),self.f)
    def test_accept_duplicate(self):
        self.assertEqual(self.rx.accept(self.p)[0], 'ACCEPTED_DIAGNOSTIC_EVENT_ONLY')
        self.assertEqual(self.rx.accept(self.p)[0], 'DUPLICATE')
    def test_replay_previous(self):
        self.rx.accept(self.p)
        p = test_frame(self.a,self.b,self.session,9).encode(self.key)
        with self.assertRaisesRegex(InvalidFrame,'replayed'):
            self.rx.accept(p)
    def test_modified_mac(self):
        p = bytearray(self.p); p[47] ^= 2
        with self.assertRaisesRegex(InvalidFrame,'MAC'):
            self.rx.accept(bytes(p))
    def test_wrong_key(self):
        with self.assertRaises(InvalidFrame):
            Frame.decode(self.p, b'Z'*32)
    def test_wrong_sender(self):
        bad = test_frame(id16('intruder'),self.b,self.session,10).encode(self.key)
        with self.assertRaisesRegex(InvalidFrame,'binding'):
            self.rx.accept(bad)
    def test_wrong_destination(self):
        bad = test_frame(self.a,id16('other'),self.session,10).encode(self.key)
        with self.assertRaisesRegex(InvalidFrame,'binding'):
            self.rx.accept(bad)
    def test_wrong_session(self):
        bad = test_frame(self.a,self.b,id16('old-session'),10).encode(self.key)
        with self.assertRaisesRegex(InvalidFrame,'binding'):
            self.rx.accept(bad)
    def test_expired(self):
        with self.assertRaisesRegex(InvalidFrame,'expired'):
            self.rx.accept(self.p,now_ms=self.f.timestamp_ms+16000)
    def test_length(self):
        for b in [self.p[:-1],self.p+b'0',b'']:
            with self.subTest(len=len(b)),self.assertRaises(InvalidFrame):
                Frame.decode(b,self.key)
    def test_wrong_version_with_valid_mac(self):
        import hmac,hashlib
        p=bytearray(self.p);p[4]=2
        p[-16:]=hmac.new(self.key,p[:-16],hashlib.sha256).digest()[:16]
        with self.assertRaisesRegex(InvalidFrame,'magic/version'):
            Frame.decode(bytes(p),self.key)
    def test_no_unsafe_action(self):
        with self.assertRaises(ValueError):
            Frame(ACTION,1000,10,int(time.time()*1000),self.a,self.b,self.session,b'12345678')
    def test_ack_valid(self):
        ack = make_ack(self.f,self.b).encode(self.key)
        self.assertTrue(ack_matches(ack,self.f,self.key,self.b))
        self.assertFalse(ack_matches(ack,self.f,self.key,id16('fake')))
    def test_ack_wrong_sequence(self):
        ack = make_ack(self.f,self.b)
        wrong = Frame(ACK,0,ack.sequence+1,ack.timestamp_ms,ack.sender,ack.target,ack.session,ack.nonce)
        self.assertFalse(ack_matches(wrong.encode(self.key),self.f,self.key,self.b))
    def test_key_length(self):
        with self.assertRaises(ValueError):self.f.encode(b'x'*8)
    def test_sequence_limit(self):
        with self.assertRaises(ValueError):
            test_frame(self.a,self.b,self.session,2**64)
