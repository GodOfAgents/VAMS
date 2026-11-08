# F05.2a applied-policy identity revalidation - 2026-10-03

Status: PASS for current synthetic fixture identity only.

Two fresh, separate disposable builds with pinned Aiken 1.1.21 reproduce the applied policy. Each serialized 3,467-byte compiled program matches both the checked-in `tx_sim_r1/applied-policy.cbor` and the witness in the frozen valid transaction. BLAKE2b-224(`0x03 || compiledCode`) independently matches the fixture Mint[0] policy ID `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`. Both blueprint digests are `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008`; normalized locks equal the canonical lock. All 21 protected canonical Cardano input hashes are unchanged before/after.

Durable result: `/home/GodOfAgents/vams-evidence/m3-f05-2a-identity-reverify-20261003-r1/RESULT.json` (SHA-256 `546c9f52bbc5e4eb0debe6b08f9eb81b472c2f211632c68f5482c02bc903abdf`). Package manifest SHA-256 `14a5335a77fe9fd70820b65017b6e01cc01d94a214df4375f4472735dc8bf53c`; every listed file verified. Package includes the probe source and both build outputs.

Independent review PASS for this narrow assertion: all 21 input hashes, fixture transaction, compiled code/artifact/witness, policy hash, blueprint and lock were independently checked. Limitations: the run does not demonstrate process/network isolation; Aiken resolved two dependencies from its existing cache. The pinned binary version/hash were checked but are not embedded in RESULT.json.

Synthetic fixture identity only; no ledger admission, Cardano Pre-Prod, live-network or deployment evidence. No negative or mutation credit. Current accepted overlay remains 45/55 negative cases (10 pending) and 18/21 mutations (3 pending), recorded in `docs/remediation/m3_f05_2a_evidence_classification_r1/CASE-STATUS.json` (SHA-256 `8a571af3c92957ced0dc4d1c17c03776ac6a774d19a8ac20fce10c0fff1e5cc2`). The older 13/55 and 0/21 values are historical.

No canonical source, fixture, lock, key, credential, vendor, or deployment behavior changed. INV-1 through INV-10 are not touched. Readiness remains NOT READY; deployment, Deposit, Slash activation and ExecuteIntent remain disabled.

Full-plan reassessment: six applied-parameter variants and four signature-domain cases still await their documented decisions; the F04 normative path and T06 provider/history evidence remain unresolved. Separately, root pytest fails collection because two archived evidence modules share `test_design.py`; importlib mode then fails four sibling imports. Next single slice: repair root pytest collection without changing frozen evidence packages, then independently review and run the full suite.
