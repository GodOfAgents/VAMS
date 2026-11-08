# M7 pytest collection split independent review - 2026-10-03

## Result

PASS for the exact pytest workflow hunk and its collection partition. The root invocation adds only `--ignore=docs/remediation/m3_f05_design_r2/test_design.py`; the following invocation targets that exact file. Both retain the default pytest import mode and use the same `VAMS_ENVOY_BIN` setting. Fresh pinned-interpreter collection reports 1,575 root node IDs and 10 F05-file node IDs, which are disjoint and cover 1,585 node IDs with no omitted file.

## Count correction

My earlier aggregate was incorrect. Correct arithmetic is:

- Root execution: 1,569 passed + 6 failed = 1,575 outcomes.
- Separate F05 execution: 10 passed.
- Combined: 1,579 passed + 6 failed = 1,585 collected node IDs.
- The 441 passing subtests are nested and do not add pytest node IDs.

The Python gate remains FAIL due to six executed failures. The F05 split file itself passed 10/10.

## Review limits

I inspected the exact workflow hunk and checked the arithmetic against the supplied test/collection results. I did not rerun the suite. The workflow has unrelated pre-existing dirty changes; this review covers only the pytest split lines. No behavior or invariant claim is made.
