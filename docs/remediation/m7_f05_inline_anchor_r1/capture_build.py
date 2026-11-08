from __future__ import annotations
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
out = root / "docs/remediation/m7_f05_inline_anchor_r1"
source = root / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
aiken = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
spec = importlib.util.spec_from_file_location("f05_public", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fixture, _ = module._validate_inputs()
signers = module._ephemeral_committee()
keys = [item.public_key for item in signers]
genesis_hash = bytes.fromhex(fixture["synthetic_fixture_only"]["genesis_tx_hash"])
genesis_index = fixture["synthetic_fixture_only"]["genesis_output_index"]
params = {
    "genesis_ref": module._output_reference(genesis_hash, genesis_index),
    "initial_keys": module.list_data([module.byte_string(key) for key in keys]),
}
original_run = module._run
def capture_run(command, cwd):
    try:
        return original_run(command, cwd)
    except RuntimeError:
        if len(command) > 1 and command[1] == "build":
            observed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=120)
            (out / "MUTANT_BUILD.stdout").write_text(observed.stdout)
            (out / "MUTANT_BUILD.stderr").write_text(observed.stderr)
            (out / "MUTANT_BUILD.exit").write_text(str(observed.returncode) + "\n")
            print(json.dumps({"exit_code": observed.returncode, "stdout_tail": observed.stdout.splitlines()[-20:], "stderr_tail": observed.stderr.splitlines()[-20:]}))
        raise
module._run = capture_run
with tempfile.TemporaryDirectory(prefix="f05-inline-mutant-") as temp:
    try:
        module._compile(module.CARDANO, aiken, Path(temp) / "mutant", params, "remove_inline_datum_guard")
    except RuntimeError:
        pass
    else:
        raise AssertionError("mutant unexpectedly compiled")
