import importlib.util
import tempfile
import unittest
from pathlib import Path

AUTOCODE = Path(__file__).resolve().parents[1] / "autocode"

def load(name):
    spec = importlib.util.spec_from_file_location(name, AUTOCODE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

select = load("select_autocode")
guard = load("guard_autocode")

class AutoCodeTests(unittest.TestCase):
    def test_queue(self):
        tasks = select.load_queue()
        self.assertEqual(len(tasks), 3)
        self.assertEqual(len({t["id"] for t in tasks}), 3)

    def test_select_skips_reserved(self):
        tasks = select.load_queue()
        choice = select.choose_task(tasks, lambda b: b == select.branch_for(tasks[0]))
        self.assertEqual(choice["id"], tasks[1]["id"])
        self.assertIsNone(select.choose_task(tasks, lambda _: True))

    def test_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "prompt.md"
            select.render_prompt("rp-003-contracts", path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("Do not execute game binaries", text)
            self.assertIn("rp-003-contracts", text)

    def test_paths(self):
        self.assertTrue(guard.check_paths(["police-rp/v1.4/P2P/test_p2p.c"], 20))
        for path in (".github/workflows/ci.yml", "AGENTS.md",
                     "ai-lab/autocode/tasks.json", "police-rp/v1.4/hack.ipa",
                     "ai-lab/projects/roleplay-ios/baselines/v12-verified.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                guard.check_paths([path], 20)

    def test_patch_limits(self):
        with self.assertRaises(ValueError):
            guard.check_paths(["police-rp/a.c"], 131073)
        with self.assertRaises(ValueError):
            guard.check_paths([], 0)

if __name__ == "__main__":
    unittest.main()
