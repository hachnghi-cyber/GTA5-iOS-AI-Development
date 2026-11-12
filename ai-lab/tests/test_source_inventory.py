import importlib.util
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "source_inventory.py"
spec = importlib.util.spec_from_file_location("source_inventory", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SourceInventoryTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(mod.classify(Path("v1.4/P2P/prp_p2p.c")), "source")
        self.assertEqual(mod.classify(Path("v1.4/Tests/test_p2p.c")), "test")
        self.assertEqual(mod.classify(Path("v1.4/README.md")), "documentation")
        self.assertEqual(mod.classify(Path("v1.4/source.zip")), "archive-not-inspected")
    def test_collect_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / "police-rp" / "v1.4"
            folder.mkdir(parents=True)
            (folder / "hello.c").write_bytes(b"int main(void) {return 0;}\n")
            (folder / "README.md").write_text("SOURCE + PROBE", encoding="utf-8")
            report = mod.inventory(root)
            self.assertEqual(report["summary"]["files"], 2)
            self.assertEqual(report["summary"]["categories"]["source"], 1)
            self.assertEqual(report["summary"]["categories"]["documentation"], 1)
            self.assertEqual(len([f for f in report["files"] if f["sha256"]]), 2)
    def test_no_recursion_into_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            folder = root / "police-rp"
            folder.mkdir()
            (folder / "v1").mkdir()
            (folder / "v1" / "readme.md").write_text("hello", encoding="utf-8")
            (folder / "outside").symlink_to(root, target_is_directory=True)
            report = mod.inventory(root)
            self.assertEqual(report["summary"]["files"], 1)
    def test_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                mod.inventory(d)

if __name__ == "__main__":
    unittest.main()
