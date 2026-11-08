# F05.2a original applied-policy identity gate — 2026-10-02

Accepted for synthetic-fixture source identity only following independent reproduction.
Branch `testnet/remediation-20260907`, HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`.

Two isolated Aiken 1.1.21 builds of current canonical source reproduce the original
applied policy with exact public genesis reference and ordered committee keys
recovered from the frozen fixture datum. Both blueprint digests are
`c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008`.
The 3467-byte CBOR-encoded compiledCode equals both the original artifact and
the exact transaction witness; its inner program is 3464 bytes. The script hash
uses `BLAKE2b-224(03 || compiledCode)` and is
`9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`.
Applied artifact SHA256 is
`fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59`.
The nullary state hash remains
`b4a7b5de32fa88554a4eb44d8e8235e24e738a1c1d1fe1764a0a3e66`.

Exact application commands, parameter CBOR, stdout, stderr, exits, canonical
before/after hashes and isolated lock hashes: `/home/GodOfAgents/vams-evidence/m3-f05-2a-identity-gate-20261002-r1/RESULT.json`.
Evidence manifest SHA256: `a42e8b5f77026ecc66b4bafd062849104bf7d34279ac483fb43be619502a4e5b`.
Canonical Cardano source, blueprint, dependency manifest and lock bytes remained
identical; isolated locks differ only in permitted etag timestamps.

Commands and results:

- `PYTHONDONTWRITEBYTECODE=1 python3 identity_probe.py --evidence /home/GodOfAgents/vams-evidence/m3-f05-2a-identity-gate-20261002-r1`:
  exit 0; two build/apply reproductions PASS. Script saved inside this evidence pack.
- `PYTHONDONTWRITEBYTECODE=1 python3 reverify_f05_baseline.py`:
  exit 0; 28/28 rows PASS across pinned Aiken 1.1.21/1.1.23:
  13 distinct negative cases plus positive control on each runtime.
  Results: `/home/GodOfAgents/vams-evidence/m3-f05-2a-baseline-reverify-20261002-r1/RESULT.json`.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/remediation/test_f05_2a_tx_sim_runner_r3.py`:
  exit 0, 16/16 on Python 3.14.4.
- Same test command using `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python`:
  exit 1, 16 tests, 18 subtest failures; not PASS on Python 3.12.14.
  Direct `_sealed_snapshot` probe identifies absent `fcntl.F_SEAL_WRITE`.
  This is a separate environment-compatibility blocker, not a changed policy result.
- `sha256sum -c SHA256SUMS` in historical R4 evidence: every entry OK.
- `git diff --check`: exit 0 before record update.

Independent reviewer manually re-encoded the parameter CBOR and ran direct
`aiken blueprint apply`, without importing the writer's `_compile` path.
Independent result: `/home/GodOfAgents/vams-evidence/m3-f05-2a-identity-independent-review-20261002-r1/REVIEW-RESULT.json`.
This closes the original applied-policy identity question for the current
synthetic fixture; it does not establish approved operator credentials or a
deployment policy instance. No new negative or mutation receives PASS:
13/55 negative PASS, 42 pending, 0/21 mutation PASS, 21 pending.

INV-1–INV-10 and mock behavior are unchanged. F05 remains REVALIDATED_OPEN,
F01–F03 open, F04 REMEDIATED, M3 OPEN, Pre-Prod INCONCLUSIVE, promotion NOT READY.
Deployment, Deposit, Slash activation and ExecuteIntent remain disabled.
Ledger script-data-hash/collateral, provenance-bound Pre-Prod parameters,
minimum ADA, live network evidence and T06/history remain unresolved.

Next single slice: repair and independently review sealed-snapshot compatibility
with the required Python 3.12 toolchain, then resume remaining F05.2a cases and
compiled mutations in dependency order. No tool installation or deployment is authorized.
