import unittest
from src.loopback_demo import run
class TwoPeerLoopbackTest(unittest.TestCase):
    def test_local_udp_two_endpoint_roundtrip(self):
        states = run()
        self.assertEqual(len(states),4)
