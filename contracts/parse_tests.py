import json
try:
    with open('clean_output.json', 'r', encoding='utf-8-sig', errors='ignore') as f:
        data = json.load(f)
    for file, content in data.items():
        for contract, res in content.items():
            if 'test_results' in res:
                for test, result in res['test_results'].items():
                    if result['status'] == 'Failure':
                        print(f"{contract}::{test} -> {result['reason']}")
except Exception as e:
    print(f"Error: {e}")
