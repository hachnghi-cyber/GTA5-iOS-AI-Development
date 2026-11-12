import importlib.util
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dispatcher", root / "dispatcher.py")
dispatcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatcher)

class RegistryTests(unittest.TestCase):
    def test_100_roles(self):
        agents = dispatcher.load_agents()
        self.assertEqual(len(agents), 100)
        self.assertEqual(len({a["id"] for a in agents}), 100)
        self.assertEqual(len({a["team"] for a in agents}), 10)
    def test_priority_for_sigsegv_menyoo(self):
        ids = [a["id"] for a in dispatcher.route("SIGSEGV crash after Menyoo vehicle spawn", 5)]
        self.assertIn("QA-01", ids)
        self.assertIn("UX-03", ids)
    def test_fallback(self):
        self.assertEqual(len(dispatcher.route("unknown-task-zz", 3)), 3)
    def test_limit(self):
        with self.assertRaises(ValueError):
            dispatcher.route("crash", 101)

if __name__ == "__main__":
    unittest.main()
