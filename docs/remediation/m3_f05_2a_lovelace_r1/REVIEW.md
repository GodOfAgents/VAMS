# F05.2a exact-lovelace mutation acceptance — 2026-10-02

Registered `remove_exact_lovelace_guard`: PASS after separate integrated independent
acceptance at `/home/GodOfAgents/vams-evidence/m3-f05-2a-lovelace-combined-independent-acceptance-20261002-r1/ACCEPTANCE.json`; manifest digest
`69a922a6b1a6a71cec17622e7a4264d14827d487aea53571f107069afdd8c491`.
Only this mutation is accepted. Negative counts remain 13/55 PASS, 42 pending;
mutation counts are now 1/21 PASS, 20 pending. The historical R4 ledger is unchanged.

Changed canonical files: this review, CASE-STATUS.json, STATUS.md and SESSION_HANDOFF.md.
No production code, accepted fixture, registry assertion, policy/blueprint/lock,
credential, vendor, history, or activation changed. Current HEAD remains
`829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`.

Exact command: `PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python run_lovelace_mutation.py`:
exit 0, three triad legs PASS and two routing controls PASS. Script, full build/apply
argv/stdout/stderr/exits, exact applied parameters, source hashes, artifacts and
snapshot results are preserved in
`/home/GodOfAgents/vams-evidence/m3-f05-2a-lovelace-mutation-20261002-r1/`;
manifest digest `3aa8b74d6826fa7b5ca7d4498f2798175bddca78d92dc9735273f8e4474bba71`.
The disposable source deletes exactly one guard line. Original valid accepts,
original invalid rejects, and rebound-mutant invalid accepts at the actual
intended compiled Mint[0]. Mutant ID
`92f0e06de7ec071b919fba18e74f7dd3623579685eea59c9414df2ac`;
program SHA256 `b609c404942482186fbe7c35ae8089b4bd2713b88ec41452604b30df62eaaacc`.
All funding witnesses use ephemeral TEST keys only, never persisted or emitted.

Independent review separately verifies one-line source deletion, compiled
identity, two serialized-body signatures, unique ordered input/raw-UTxO linkage,
unchanged datum and 17,000,000-lovelace conservation, and replays all five rows
on the SHA-pinned Aiken 1.1.21 runtime. Evidence:
`/home/GodOfAgents/vams-evidence/m3-f05-2a-lovelace-independent-review-20261002-r1/`.

The initial candidate lacked the required constant-success/classifier-only
control; core triad PASS was not accepted as registered mutation PASS. A separate
bounded closed admission verifier then rejected wrong runtime, declaration-only,
executed constant-success, stale hashes, malformed rows, cleanup/type and extra-field
adversaries. Exact command: same Python runtime with `lovelace_admission_controls.py`,
exit 0; separately independently reviewed final script SHA
`a0b60f395f6cc0d0e3c97f2779fadb694c641df62fb5bed0e22f8c3692e920cd`.
Evidence: `/home/GodOfAgents/vams-evidence/m3-f05-2a-admission-independent-review-20261002-r1/`.
Structural declarations alone remain insufficient: separate observed pinned
execution is a mandatory acceptance condition and was independently completed.

`git diff --check`: exit 0. Canonical policy SHA remains
`5c01f9556d922a719a7dac348d8b7175d660ef387fdf2005979c27fb2e833b05`,
blueprint `c145a18c235a9e7586ec10b70076899ddf0fe74a4b17ae3e4f5c1a636222a7d2`,
lock `6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`.

INV-1–INV-10 and mock behavior unchanged. This is synthetic simulator evidence,
not ledger admission, live evidence or deployment authorization. F05/M3 remain
open; Pre-Prod INCONCLUSIVE; promotion NOT READY. Deployment, Deposit, Slash
activation and ExecuteIntent remain disabled. Other mandatory roadmap and
T06/history exit criteria remain required.

Next single slice: the remaining authority-datum semantic negative family,
with unchanged original policy identity, byte-reviewed single-field mutations,
valid synthetic funding signatures, actual compiled rejection and independent review.
