from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

root = Path("/home/GodOfAgents/code/VAMS-testnet")
out = root / "docs/remediation/m7_f05_address_option_r1"
source = root / "scripts/remediation/test_f05_2a_authority_bootstrap_public.py"
aiken = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
spec = importlib.util.spec_from_file_location("f05_public", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class Captured(Exception): pass
def stop(observed):
    (out / "POSITIVE_OBSERVED.json").write_text(json.dumps(observed, indent=2) + "\n")
    raise Captured()
module._require_positive_acceptance = stop
try:
    module._run_suite(aiken)
except Captured:
    pass
else:
    raise AssertionError("positive capture boundary not reached")
observed = json.loads((out / "POSITIVE_OBSERVED.json").read_text())
print(json.dumps(observed, indent=2))
if not observed["accepted"] or observed["exit"] != 0 or observed["verify_signature_alias_count"] != 5:
    raise SystemExit(2)
