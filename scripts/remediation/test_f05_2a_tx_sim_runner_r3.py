"""Public-boundary regressions for immutable F05.2a simulator snapshots."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("f05_2a_tx_sim_runner_r3.py")
SPEC = importlib.util.spec_from_file_location("f05_2a_tx_sim_runner_r3", SCRIPT)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

FIXTURE_ROOT = RUNNER.ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1"
POSITIVE_HASHES = {
    "transaction": "765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
    "raw_inputs": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
    "raw_outputs": "9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a",
}
POSITIVE_BODY_ID = "695e8caab89a518b36885cb8377a8e8d472acd1090f55389a4a49cd65131f34b"
POLICY_ID = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"


class SnapshotRunnerPublicBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="f05-r3-test-")
        self.root = Path(self.temp.name)
        self.tx = self.root / "transaction.cbor"
        self.inputs = self.root / "raw-inputs.cbor"
        self.outputs = self.root / "raw-outputs.cbor"
        self.tx.write_bytes((FIXTURE_ROOT / "valid.tx.cbor").read_bytes())
        self.inputs.write_bytes((FIXTURE_ROOT / "raw_inputs.cbor").read_bytes())
        self.outputs.write_bytes((FIXTURE_ROOT / "raw_outputs.cbor").read_bytes())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _fake_aiken(self, action: str = "", *, ambiguous: bool = False,
                    rejection: bool = False, sleep_seconds: float = 0) -> Path:
        executable = self.root / "fake-aiken"
        extra = ""
        if sleep_seconds:
            extra += f"time.sleep({sleep_seconds!r})\n"
        extra += action
        if ambiguous:
            body = (
                "sys.stdout.write(json.dumps([{'mem':424440,'cpu':431999255,'traces':[]}]))\n"
                "sys.stderr.write('Parsing script context\\nSimulating " + POSITIVE_BODY_ID +
                "\\nEvaluating Mint[0]\\nEvaluating Mint[0]\\n')\n"
                "sys.exit(0)\n"
            )
        elif rejection:
            body = (
                "sys.stderr.write('Parsing script context\\nSimulating " + POSITIVE_BODY_ID +
                "\\nEvaluating Mint[0]\\nError failed script execution\\nMint[0] the validator crashed / exited prematurely\\n')\n"
                "sys.exit(1)\n"
            )
        else:
            body = (
                "expected = " + repr(list(POSITIVE_HASHES.values())) + "\n"
                "observed = [hashlib.sha256(open(p,'rb').read()).hexdigest() for p in sys.argv[4:7]]\n"
                "if observed != expected:\n"
                "  sys.stderr.write('unknown or substituted fixture bytes\\n')\n"
                "  sys.exit(0)\n"
                "sys.stdout.write(json.dumps([{'mem':424440,'cpu':431999255,'traces':[]}]))\n"
                "sys.stderr.write('Parsing script context\\nSimulating " + POSITIVE_BODY_ID +
                "\\nEvaluating Mint[0]\\n')\n"
                "sys.exit(0)\n"
            )
        script = (f"#!{sys.executable}\nimport hashlib,json,os,subprocess,sys,time\n"
                  "args=sys.argv\n" + extra + body)
        executable.write_text(script, encoding="utf-8")
        executable.chmod(0o700)
        return executable

    def _run(self, action: str = "", *, policy_id: str = POLICY_ID, **kwargs):
        fake = self._fake_aiken(action, **kwargs)
        return RUNNER.run_snapshot_simulation(fake, self.tx, self.inputs,
                                               self.outputs, policy_id,
                                               timeout_seconds=2.0)

    def _assert_positive_snapshot(self, result: dict) -> None:
        self.assertEqual(result["schema_version"], "f05-2a-tx-sim-run-result-r3")
        self.assertEqual(result["submitted_sha256"], POSITIVE_HASHES)
        self.assertEqual(result["simulator_result"],
                         {"stage": "script_accepted", "target_script_invoked": True})
        self.assertEqual(result["simulator_child_exit"], 0)
        self.assertEqual(result["target_mint_binding"]["expected_policy_id"], POLICY_ID)
        self.assertEqual(result["target_mint_binding"]["policy_ids"], [POLICY_ID])
        self.assertEqual(result["target_mint_binding"]["compiled_script_hash"], POLICY_ID)
        self.assertEqual(result["wrapper_exit_code"], 0)
        self.assertEqual(result["cleanup"]["status"], "clean")
        self.assertTrue(result["cleanup"]["child_reaped"])
        self.assertTrue(result["cleanup"]["process_group_empty"])

    def test_pathname_replacement_after_snapshot_cannot_change_submitted_transaction(self) -> None:
        source = repr(str(self.tx))
        action = (f"os.rename({source}, {source}+'.old')\n"
                  f"open({source},'wb').write(b'tampered')\n")
        self._assert_positive_snapshot(self._run(action))

    def test_pathname_replacement_after_snapshot_for_each_source_role(self) -> None:
        for role, path in (("transaction", self.tx), ("raw_inputs", self.inputs),
                           ("raw_outputs", self.outputs)):
            with self.subTest(role=role):
                self.tx.write_bytes((FIXTURE_ROOT / "valid.tx.cbor").read_bytes())
                self.inputs.write_bytes((FIXTURE_ROOT / "raw_inputs.cbor").read_bytes())
                self.outputs.write_bytes((FIXTURE_ROOT / "raw_outputs.cbor").read_bytes())
                source = repr(str(path))
                action = (f"os.rename({source}, {source}+'.old')\n"
                          f"open({source},'wb').write(b'tampered')\n")
                self._assert_positive_snapshot(self._run(action))

    def test_in_place_source_modification_after_snapshot_cannot_change_submission(self) -> None:
        source = repr(str(self.tx))
        action = (f"with open({source},'r+b') as f:\n"
                  "  f.seek(0); f.write(b'tampered')\n")
        self._assert_positive_snapshot(self._run(action))

    def test_swap_and_restore_race_cannot_change_child_read_bytes(self) -> None:
        source = repr(str(self.tx))
        action = (f"saved=open({source},'rb').read()\n"
                  f"open({source},'wb').write(b'tampered')\n"
                  "raced=open(args[4],'rb').read()\n"
                  f"open({source},'wb').write(saved)\n"
                  "if hashlib.sha256(raced).hexdigest() != " +
                  repr(POSITIVE_HASHES["transaction"]) +
                  ":\n  sys.stderr.write('swap observed by child\\n'); sys.exit(0)\n")
        self._assert_positive_snapshot(self._run(action))

    def test_swap_and_restore_race_for_each_source_role_cannot_change_child_bytes(self) -> None:
        source_roles = (("transaction", self.tx, 4),
                        ("raw_inputs", self.inputs, 5),
                        ("raw_outputs", self.outputs, 6))
        for role, path, arg_index in source_roles:
            with self.subTest(role=role):
                source = repr(str(path))
                expected = repr(POSITIVE_HASHES[role])
                action = (f"saved=open({source},'rb').read()\n"
                          f"open({source},'wb').write(b'tampered')\n"
                          f"raced=open(args[{arg_index}],'rb').read()\n"
                          f"open({source},'wb').write(saved)\n"
                          f"if hashlib.sha256(raced).hexdigest() != {expected}:\n"
                          "  sys.stderr.write('swap observed by child\\n'); sys.exit(0)\n")
                self._assert_positive_snapshot(self._run(action))

    def test_input_output_substitution_and_write_attempt_cannot_change_snapshots(self) -> None:
        raw_inputs, raw_outputs = repr(str(self.inputs)), repr(str(self.outputs))
        action = (f"open({raw_inputs},'wb').write(b'changed input')\n"
                  f"open({raw_outputs},'wb').write(b'changed output')\n"
                  "write_succeeded=False\n"
                  "for p in args[5:7]:\n"
                  "  try:\n"
                  "    with open(p,'wb') as f: f.write(b'substituted snapshot')\n"
                  "    write_succeeded=True\n"
                  "  except OSError: pass\n"
                  "if write_succeeded:\n"
                  "  sys.stderr.write('snapshot write unexpectedly succeeded\\n'); sys.exit(0)\n")
        self._assert_positive_snapshot(self._run(action))

    def test_ambiguous_output_is_indeterminate_and_wrapper_fails_closed(self) -> None:
        result = self._run(ambiguous=True)
        self.assertEqual(result["simulator_child_exit"], 0)
        self.assertEqual(result["simulator_result"],
                         {"stage": "indeterminate", "target_script_invoked": False})
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertNotIn("stdout", result)
        self.assertNotIn("stderr", result)
        self.assertNotIn("raw_transaction", result)

    def test_simulator_and_wrapper_exit_codes_are_distinct(self) -> None:
        # Synthetic parser canary only; this does not promote registry case #33.
        result = self._run(rejection=True)
        self.assertEqual(result["simulator_child_exit"], 1)
        self.assertEqual(result["simulator_result"],
                         {"stage": "compiled_evaluation", "target_script_invoked": True})
        self.assertEqual(result["wrapper_exit_code"], 0)

    def test_timeout_kills_and_reaps_the_isolated_child_group(self) -> None:
        fake = self._fake_aiken(sleep_seconds=20)
        result = RUNNER.run_snapshot_simulation(fake, self.tx, self.inputs,
                                                self.outputs, POLICY_ID,
                                                timeout_seconds=0.15)
        self.assertEqual(result["error_code"], "simulator_deadline")
        self.assertNotEqual(result["simulator_child_exit"], 0)
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertTrue(result["cleanup"]["child_reaped"])
        self.assertTrue(result["cleanup"]["process_group_empty"])
        self.assertEqual(result["cleanup"]["status"], "clean")

    def test_timeout_kills_grandchild_that_holds_capture_pipes_open(self) -> None:
        marker = repr(str(self.root / "grandchild.pid"))
        action = ("grandchild=subprocess.Popen([sys.executable,'-c',"
                  "'import time; time.sleep(20)'])\n"
                  f"open({marker},'w').write(str(grandchild.pid))\n")
        fake = self._fake_aiken(action, sleep_seconds=0.02)
        result = RUNNER.run_snapshot_simulation(fake, self.tx, self.inputs,
                                                self.outputs, POLICY_ID,
                                                timeout_seconds=0.15)
        marker_path = self.root / "grandchild.pid"
        self.assertTrue(marker_path.exists())
        grandchild_pid = int(marker_path.read_text(encoding="ascii"))
        self.assertEqual(result["error_code"], "simulator_deadline")
        self.assertTrue(result["cleanup"]["child_reaped"])
        self.assertTrue(result["cleanup"]["process_group_empty"])
        self.assertEqual(result["wrapper_exit_code"], 2)
        deadline = time.monotonic() + 1.0
        while True:
            try:
                os.kill(grandchild_pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                self.fail("grandchild process survived bounded group cleanup")
            time.sleep(0.025)

    def test_tampered_snapshot_has_targeted_integrity_failure_before_spawn(self) -> None:
        fake = self._fake_aiken()
        original_snapshot = RUNNER._sealed_snapshot
        first = {"done": False}

        def mutate_transaction_snapshot(name: str, content: bytes) -> int:
            if name == "f05-r3-transaction" and not first["done"]:
                first["done"] = True
                content = b"X" + content[1:]
            return original_snapshot(name, content)

        with mock.patch.object(RUNNER, "_sealed_snapshot", mutate_transaction_snapshot):
            result = RUNNER.run_snapshot_simulation(
                fake, self.tx, self.inputs, self.outputs, POLICY_ID,
                timeout_seconds=2.0)
        self.assertEqual(result["error_code"], "snapshot_integrity_failure")
        self.assertEqual(result["simulator_child_exit"], None)
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertEqual(result["cleanup"]["status"], "clean")

    def test_raw_input_output_descriptor_swap_is_targeted_before_spawn(self) -> None:
        fake = self._fake_aiken()
        original_builder = RUNNER._build_simulator_command

        def swap_vectors(aiken: Path, descriptors: dict[str, int]) -> list[str]:
            command = original_builder(aiken, descriptors)
            command[-2], command[-1] = command[-1], command[-2]
            return command

        with mock.patch.object(RUNNER, "_build_simulator_command", swap_vectors):
            result = RUNNER.run_snapshot_simulation(
                fake, self.tx, self.inputs, self.outputs, POLICY_ID,
                timeout_seconds=2.0)
        self.assertEqual(result["error_code"], "snapshot_binding_mismatch")
        self.assertEqual(result["simulator_child_exit"], None)
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertEqual(result["cleanup"]["status"], "clean")

    def test_wrong_expected_policy_binding_is_rejected_before_child_execution(self) -> None:
        result = self._run(policy_id="00" * 28)
        self.assertEqual(result["error_code"], "target_policy_binding_mismatch")
        self.assertIsNone(result["simulator_child_exit"])
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertEqual(result["simulator_result"]["stage"], "indeterminate")
        self.assertFalse(result["simulator_result"]["target_script_invoked"])
        self.assertEqual(result["cleanup"]["status"], "clean")

    def test_cleanup_failure_is_not_a_success_and_retry_closes_descriptor(self) -> None:
        fake = self._fake_aiken()
        original_close = RUNNER._close_snapshot_fd
        fail_once = {"done": False}

        def injected_close_failure(fd: int) -> None:
            original_close(fd)
            if not fail_once["done"]:
                fail_once["done"] = True
                raise OSError("injected close failure")

        with mock.patch.object(RUNNER, "_close_snapshot_fd", injected_close_failure):
            result = RUNNER.run_snapshot_simulation(
                fake, self.tx, self.inputs, self.outputs, POLICY_ID,
                timeout_seconds=2.0)
        self.assertEqual(result["simulator_result"]["stage"], "script_accepted")
        self.assertEqual(result["error_code"], "cleanup_failed")
        self.assertEqual(result["cleanup"]["status"], "failed")
        self.assertEqual(result["wrapper_exit_code"], 2)

    def test_exception_before_child_still_closes_all_snapshot_descriptors(self) -> None:
        fake = self._fake_aiken()
        original_snapshot = RUNNER._sealed_snapshot
        created: list[int] = []

        def fail_second_snapshot(name: str, content: bytes) -> int:
            if created:
                raise RUNNER.SnapshotError("injected_snapshot_failure")
            fd = original_snapshot(name, content)
            created.append(fd)
            return fd

        with mock.patch.object(RUNNER, "_sealed_snapshot", fail_second_snapshot):
            result = RUNNER.run_snapshot_simulation(
                fake, self.tx, self.inputs, self.outputs, POLICY_ID,
                timeout_seconds=2.0)
        self.assertEqual(result["error_code"], "injected_snapshot_failure")
        self.assertEqual(result["simulator_child_exit"], None)
        self.assertEqual(result["wrapper_exit_code"], 2)
        self.assertEqual(result["cleanup"]["status"], "clean")
        with self.assertRaises(OSError):
            os.fstat(created[0])

    def test_r3_contract_binds_r2_without_promoting_any_case(self) -> None:
        contract_path = (Path(__file__).resolve().parents[2] /
                         "docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r3.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"],
                         "f05-2a-tx-simulator-evidence-contract-r3")
        self.assertEqual(contract["extends"]["r2"]["sha256"],
                         "3510e127d369e9eab24a7ebe5a5dea10daaf55fd9589a297d78776bda940f6e9")
        self.assertEqual(contract["accepted_registry"]["sha256"],
                         "98a05d24d476b1aee2754768322dc4b794e5afb5fabec28ade17a2888285467d")
        r2 = json.loads((RUNNER.ROOT /
                         "docs/remediation/m3_f05_2a/tx_sim_evidence_contract_r2.json").read_text())
        self.assertEqual(len(r2["negative_cases"]), 55)
        self.assertEqual(len(r2["compiled_mutations"]), 21)
        self.assertTrue(all(row["status"] == "PENDING"
                            for row in r2["negative_cases"] + r2["compiled_mutations"]))
        case33 = next(row for row in r2["negative_cases"]
                      if row["id"] == "authority_value_minus_one")
        self.assertEqual(case33["status"], "PENDING")
        self.assertTrue(contract["case_status_policy"]["pending_is_not_pass"])
        self.assertEqual(contract["cleanup_contract"]["persistent_temporary_paths"], 0)


if __name__ == "__main__":
    unittest.main()
