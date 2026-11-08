# F05.2a Python 3.12 sealed-snapshot compatibility — 2026-10-02

Independently accepted bounded compatibility repair. Changed files:
`scripts/remediation/f05_2a_tx_sim_runner_r3.py`, new
`scripts/remediation/test_f05_2a_sealing_compatibility.py`, changelog and these records.

The existing Python 3.12.14 build exposes memfd but omits six fcntl sealing
symbols. The runner now uses fixed Linux UAPI values only where symbols are
absent, on Linux only, during creation and pre-spawn readback. Runtime kernel
enforcement, seal readback, content/hash binding and descriptor cleanup remain
mandatory. Sealing syscall errors produce `snapshot_sealing_failed` after
descriptor closure. This changes test infrastructure, not Cardano policy.

Exact commands/results are in `/home/GodOfAgents/vams-evidence/m3-f05-2a-sealing-compatibility-20261002-r1/TEST-RESULTS.json`:
both `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python` (3.12.14)
and `/usr/bin/python3` (3.14.4), with `PYTHONDONTWRITEBYTECODE=1`, ran
`scripts/remediation/test_f05_2a_sealing_compatibility.py` (4/4) and
`scripts/remediation/test_f05_2a_tx_sim_runner_r3.py` (16/16), all exit 0.
New kernel tests reject write/grow/shrink/additional seals, check readback,
simulate absent Python symbols, reject missing seals, and close descriptors.
Independent ENOSYS/EINVAL/EPERM, missing-bit and content/hash probes pass on both.

`python -m bandit scripts/remediation/f05_2a_tx_sim_runner_r3.py -ll -ii`:
exit 0, 0 medium/high, 3 low/high-confidence findings below this gate threshold,
0 skipped files, no nosec suppressions. Raw evidence: `/home/GodOfAgents/vams-evidence/m3-f05-2a-sealing-compatibility-20261002-r1/BANDIT.json`.
`git diff --check`: exit 0. Pinned Aiken 1.1.21 negative control on repaired
Python 3.12 reaches original Mint[0], child exit 1, wrapper exit 0, cleanup clean.

Independent review: `/home/GodOfAgents/vams-evidence/m3-f05-2a-sealing-independent-review-20261002-r1/REVIEW-RESULT.json`;
manifest digest `7f63656b726675f9a23a579f6059546bce9485c85b3f4f1dde4722897ce78dd6`.
Integrated source hashes: `{"scripts/remediation/f05_2a_tx_sim_runner_r3.py": "3088ade0a316f6af59c04fe3e1675733100b58be826fa22af3c25e40a086ea5c", "scripts/remediation/test_f05_2a_sealing_compatibility.py": "66bec1a0307ef4ea99e28390b7369931d19a75ab46d1494a0e0d27a93af61d2a"}`.
No tool install/fetch, live keys, submission, credentials, vendors, production
Cardano source/blueprint/lock, Git history or unrelated dirty work changed.

INV-1–INV-10 and mock behavior unchanged. Original identity remains accepted
only for the synthetic fixture. Counts remain 13/55 negatives PASS,
42 pending, 0/21 mutations PASS, 21 pending. F05/M3 remain open;
Pre-Prod INCONCLUSIVE; promotion NOT READY. Deployment, Deposit, Slash
activation and ExecuteIntent remain disabled.

Next single slice: compiled `remove_exact_lovelace_guard` three-leg mutation
with exact one-line disposable-source deletion, derived mutant identity,
rebound signed fixture, false-positive controls and independent review.
