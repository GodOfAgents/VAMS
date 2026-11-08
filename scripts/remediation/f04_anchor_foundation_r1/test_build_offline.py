"""Public-boundary regressions for the offline F04 runner."""
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

RUNNER = Path(__file__).with_name("build_offline.py")
spec = importlib.util.spec_from_file_location("f04_offline_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class OfflineRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="f04-runner-test-")
        self.ev = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_check_only_plan_contains_no_build_command(self):
        plan = runner.command_plan(Path(sys.executable), self.ev, self.ev / "out.json", "check-only")
        self.assertEqual(set(plan), {"version", "check"})
        self.assertTrue(runner.validate_plan("check-only", plan))

    def test_build_command_requires_explicit_build_mode(self):
        with self.assertRaises(runner.Blocked):
            runner.command_plan(Path(sys.executable), self.ev, self.ev / "out.json", "implicit")
        plan = runner.command_plan(Path(sys.executable), self.ev, self.ev / "out.json", "build")
        self.assertEqual(set(plan), {"version", "check", "build"})

    def test_check_only_plan_validator_detects_build_mutation(self):
        plan = runner.command_plan(Path(sys.executable), self.ev, self.ev / "out.json", "check-only")
        mutated = dict(plan, build=["aiken", "build"])
        with self.assertRaises(runner.Blocked):
            runner.validate_plan("check-only", mutated)

    def test_child_exit_and_stream_hashes_are_retained(self):
        code = "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"
        record = runner.run([sys.executable, "-c", code], self.ev, {}, self.ev, "child", 5)
        self.assertEqual(record["child_exit"], 7)
        self.assertTrue(record["started"])
        self.assertTrue(record["capture_complete"])
        self.assertEqual(record["stdout_sha256"], hashlib.sha256((self.ev / "child.stdout").read_bytes()).hexdigest())
        self.assertEqual(record["stderr_sha256"], hashlib.sha256((self.ev / "child.stderr").read_bytes()).hexdigest())
        self.assertFalse(runner.command_ok(record))

    def test_launcher_failure_has_no_child_exit(self):
        record = runner.run([str(self.ev / "missing-executable")], self.ev, {}, self.ev, "missing", 1)
        self.assertIsNone(record["child_exit"])
        self.assertEqual(record["launcher_error_class"], "FileNotFoundError")
        self.assertFalse(record["started"])
        self.assertFalse(runner.command_ok(record))

    def test_timeout_is_not_success_even_if_process_is_killed(self):
        record = runner.run([sys.executable, "-c", "import time; time.sleep(5)"], self.ev, {}, self.ev, "timeout", 0.05)
        self.assertTrue(record["timed_out"])
        self.assertIsNotNone(record["child_exit"])
        self.assertFalse(runner.command_ok(record))

    def test_missing_capture_hash_is_not_success(self):
        self.assertFalse(runner.command_ok({"started": True, "launcher_error_class": None,
            "capture_complete": False, "child_exit": 0, "timed_out": False,
            "stdout_sha256": None, "stderr_sha256": None}))


    @staticmethod
    def good_record(exit_code=0):
        return {"started": True, "launcher_error_class": None, "capture_error_class": None,
                "capture_complete": True, "child_exit": exit_code,
                "child_signal": None, "terminal_outcome": "EXITED_ZERO" if exit_code == 0 else "EXITED_NONZERO",
                "timed_out": False, "stdout_sha256": "a" * 64, "stderr_sha256": "b" * 64}

    def test_check_only_success_never_calls_build(self):
        plan = runner.command_plan("aiken", self.ev, self.ev / "out.json", "check-only")
        calls, records = [], {}
        def invoke(name, argv):
            calls.append(name)
            return self.good_record()
        runner.check_then_optional_build(plan, "check-only", invoke, lambda _: None, lambda _: None, records)
        self.assertEqual(calls, ["check"])
        self.assertNotIn("build", records)

    def test_check_only_compiler_failure_is_retained_and_never_calls_build(self):
        plan = runner.command_plan("aiken", self.ev, self.ev / "out.json", "check-only")
        calls, records = [], {}
        failed = self.good_record(1)
        def invoke(name, argv):
            calls.append(name)
            return failed
        with self.assertRaises(runner.Blocked):
            runner.check_then_optional_build(plan, "check-only", invoke, lambda _: None, lambda _: None, records)
        self.assertEqual(calls, ["check"])
        self.assertEqual(records["check"]["child_exit"], 1)
        self.assertEqual(records["check"]["terminal_outcome"], "EXITED_NONZERO")
        self.assertNotIn("build", records)

    def test_explicit_build_mode_runs_build_only_after_accepted_check(self):
        plan = runner.command_plan("aiken", self.ev, self.ev / "out.json", "build")
        calls, records = [], {}
        def invoke(name, argv):
            calls.append(name)
            return self.good_record()
        runner.check_then_optional_build(plan, "build", invoke, lambda _: None, lambda _: None, records)
        self.assertEqual(calls, ["check", "build"])

    def test_wrapper_success_cannot_erase_child_failure(self):
        inner = {"mode": "check-only", "wrapper_exit": 0, "status": "PASS_CHECK_ONLY",
                 "commands": {"check": self.good_record(1)}}
        self.assertFalse(runner.outer_accepted("check-only", 0, inner, True, False, None, None))
        self.assertEqual(inner["commands"]["check"]["child_exit"], 1)

    def test_signal_exit_is_distinct_from_compiler_rejection(self):
        record = runner.run([sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"],
                            self.ev, {}, self.ev, "signaled", 5)
        self.assertEqual(record["terminal_outcome"], "SIGNAL_TERMINATED")
        self.assertEqual(record["child_signal"], 15)
        self.assertLess(record["child_exit"], 0)
        self.assertFalse(record["timed_out"])
        self.assertFalse(runner.command_ok(record))

    def test_capture_open_failure_is_incomplete_and_not_success(self):
        original_open = Path.open
        def selective_open(path, *args, **kwargs):
            if path.name == "capture.stdout":
                raise PermissionError("synthetic capture failure")
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", selective_open):
            record = runner.run([sys.executable, "-c", "pass"], self.ev, {}, self.ev, "capture", 5)
        self.assertEqual(record["capture_error_class"], "PermissionError")
        self.assertFalse(record["capture_complete"])
        self.assertFalse(runner.command_ok(record))

if __name__ == "__main__":
    unittest.main()
