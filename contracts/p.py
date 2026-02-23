import json

with open('test_output.json', 'r', encoding='utf-8-sig', errors='ignore') as f:
    content = f.read()

try:
    for line in content.split('\n'):
        if not line.strip(): continue
        try:
            data = json.loads(line)
            # Forge test --json outputs one JSON object per contract
            for testName, result in data.items():
                if isinstance(result, dict) and result.get('status') == 'Failure':
                    print(f"{testName} -> {result.get('reason')}")
        except:
            # If it's a single big JSON object with files
            pass

    data = json.loads(content)
    # Check structure
    for key, val in data.items():
        if isinstance(val, dict):
            for contract, results in val.items():
                if isinstance(results, dict) and 'test_results' in results:
                    for testName, result in results['test_results'].items():
                        if result.get('status') == 'Failure':
                            print(f"{contract}::{testName} -> {result.get('reason')}")
except Exception as e:
    pass
