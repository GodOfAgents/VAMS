import json
from collections import Counter

with open(r'c:\Users\aseem\Desktop\VAMS-main\VAMS-main\audit\slither_report.json', 'r') as f:
    data = json.load(f)

results = data.get('results', {}).get('detectors', [])
print(f'Total detectors fired: {len(results)}')
print()

# Count by impact
impact_counts = Counter(r.get('impact', 'Unknown') for r in results)
check_counts = Counter(r.get('check', 'Unknown') for r in results)

print('=== SEVERITY BREAKDOWN ===')
for sev in ['High', 'Medium', 'Low', 'Informational', 'Optimization']:
    print(f'  {sev}: {impact_counts.get(sev, 0)}')

print()
print('=== TOP DETECTORS (by count) ===')
for check, count in check_counts.most_common(20):
    imp = next((r['impact'] for r in results if r['check'] == check), '?')
    print(f'  [{imp}] {check}: {count}')

print()
print('=== HIGH SEVERITY FINDINGS ===')
for r in results:
    if r.get('impact') == 'High':
        desc = r.get('description', '')[:300]
        chk = r.get('check', '')
        print(f'  [{chk}]')
        print(f'  {desc}')
        print()

print()
print('=== MEDIUM SEVERITY FINDINGS ===')
for r in results:
    if r.get('impact') == 'Medium':
        desc = r.get('description', '')[:300]
        chk = r.get('check', '')
        print(f'  [{chk}]')
        print(f'  {desc}')
        print()
