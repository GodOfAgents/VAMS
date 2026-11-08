from pathlib import Path
root = Path("/home/GodOfAgents/code/VAMS-testnet")
files = ["neuron/sdk/trails_client.py", "neuron/tests/test_trails_client.py", "neuron/tests/test_m1_2b_da_trails_runtime.py", "neuron/tests/test_runtime_mode_contract.py", "neuron/tests/test_effect_canary.py"]
for name in files:
    source = root / name
    compile(source.read_text(encoding="utf-8"), str(source), "exec")
print("syntax check passed for 5 files")
