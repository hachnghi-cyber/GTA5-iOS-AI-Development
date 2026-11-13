import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "host_rp_tests.py"
spec = importlib.util.spec_from_file_location("host_rp_tests", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class HostPoliceRPTestRunnerTests(unittest.TestCase):
    def make_source_tree(self, root):
        for p in mod.SOURCES + tuple(path for _, path in mod.CASES):
            f = root / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("int placeholder(void) { return 1; }\n", encoding="utf-8")

    def test_required_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                mod.run_suite(root=tmp, compiler="cc")

    def test_compile_failure_never_executes_failed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_source_tree(root)
            failure = SimpleNamespace(returncode=1, stdout="", stderr="compiler failed")
            with patch.object(mod.subprocess, "run", return_value=failure) as run:
                report = mod.run_suite(root=root, compiler="cc")
            self.assertEqual(report["status"], "host-tests-failed")
            self.assertEqual(run.call_count, len(mod.CASES))
            self.assertTrue(all(not c["compiled"] and not c["passed"]
                                for c in report["cases"]))
            self.assertFalse(report["iphone_tested"])

    def test_mocked_pass_is_never_called_iphone_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_source_tree(root)
            success = SimpleNamespace(returncode=0, stdout="host OK", stderr="")
            with patch.object(mod.subprocess, "run", return_value=success) as run:
                report = mod.run_suite(root=root, compiler="cc")
            self.assertEqual(report["status"], "host-tests-passed")
            self.assertEqual(run.call_count, 2*len(mod.CASES))
            self.assertEqual(report["passed_count"], len(mod.CASES))
            self.assertFalse(report["gameplay_verified"])
            self.assertFalse(report["iphone_tested"])
            self.assertEqual(len(report["source_fingerprints"]), len(mod.SOURCES) + len(mod.CASES))


    def test_ubsan_flags_passed_to_compiler_without_device_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_source_tree(root)
            success = SimpleNamespace(returncode=0, stdout="host OK", stderr="")
            with patch.object(mod.subprocess, "run", return_value=success) as run:
                report = mod.run_suite(root=root, compiler="clang", sanitize_undefined=True)
            self.assertEqual(report["status"], "host-tests-passed")
            self.assertEqual(report["sanitizer"], "undefined")
            first_command = run.call_args_list[0].args[0]
            self.assertIn("-fsanitize=undefined", first_command)
            self.assertIn("-fno-sanitize-recover=all", first_command)
            self.assertFalse(report["iphone_tested"])
            self.assertEqual(report["total_count"], len(mod.CASES))


if __name__ == "__main__":
    unittest.main()
