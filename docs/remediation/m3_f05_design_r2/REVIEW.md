# F05.1-R2 scoped design resolution

Status: design artifacts locally validated; independent review **INCONCLUSIVE**. F05.2 is **not authorized**.

## Scope and decision

This slice freezes the testnet-only cross-chain authority, finality, replay, and wrapped-VAMS accounting design under `docs/remediation/m3_f05_design_r2/`. It changes no production source, validators, blueprint, lockfile, provenance, dependencies, credentials, deployment state, vendors, or Git history. F05 and F01-F03 remain `REVALIDATED_OPEN`; F04 remains `REMEDIATED`; Deposit, Slash activation, and ExecuteIntent remain disabled; M3 is `OPEN`; Pre-Prod is `INCONCLUSIVE`; promotion is `NOT_READY`.

## Evidence baseline

Strict F04 closure package verification passed before editing. Package: `/home/GodOfAgents/vams-evidence/m3-f04-closure-20260929T194439Z-829ab544571f`; expected and observed SHA256SUMS digest: `03698b936729927df4a1c87b24d46cc4722babc814a47599cd120da6469e70c4`.

Checkout: origin `https://github.com/GodOfAgents/VAMS.git`; branch `testnet/remediation-20260907`; HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`. Initial status recorded 122 dirty paths and 14 recursive submodule entries. Existing dirty work was preserved. Protected source hashes are included in the external design package.

## Frozen design

- No ERC20-to-lovelace conversion. Wrapped VAMS has a separate Cardano native asset and reserve state, distinct from `FundDatumV2`; F01 Deposit remains disabled.
- Source VAMS is escrow-locked before wrapped mint; wrapped burn precedes exact source release. Conversion rejects zero actions, dust, non-divisible amounts, and source-cap overflow. `10^8` source base units map to one wrapped unit; 10 wrapped decimals preserve the maximum supply within Cardano `uint64`; each action remains within signed `int64` mint/burn bounds.
- Testnet authority is five distinct ordered Ed25519 keys with exactly 3-of-5 signatures. Rotation is 3-of-5, increments epoch, has a 48-hour delay and exact pending transition without overlap. Emergency pause is 4-of-5 and immediate; delayed unpause is 4-of-5 after 48 hours. Paused authority rejects actions; consumed replay identities survive transitions.
- Per-source checkpoint cursors reject regressions, conflicting same-height checkpoints, wrong predecessor, event-after-checkpoint, replay, and nonce gaps. The committee is a centralized testnet finality assertion, not trustless verification or Mithril.
- Canonical fixed-width big-endian certificate serialization, SHA-256 domain separation, Ed25519 signatures, source/destination domains, event identity, action, payload hash, action ID, epoch and times are specified with pinned synthetic digest vectors. `bridge_proof` and `payload_hash` remain separate (INV-10).
- Four action types are closed in the contract: WRAPPED_CREDIT, WRAPPED_RELEASE, SLASH_AGENT and EXECUTE_INTENT. Existing F04/Governor controls remain prerequisites; the design does not activate currently disabled paths.

## Files and local checks

Scoped files: `ADR.md`, `CONTRACT.json`, `VECTORS.json`, `validate_design.py`, `test_design.py`, and this review. No global status/ledger file was changed.

Fresh results:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s docs/remediation/m3_f05_design_r2 -v` — PASS, 9 tests.
- `python3 -m py_compile docs/remediation/m3_f05_design_r2/validate_design.py docs/remediation/m3_f05_design_r2/test_design.py` — PASS.
- `python3 docs/remediation/m3_f05_design_r2/validate_design.py` — PASS; `actions=4`, `arithmetic_vectors=10`, `mutation_refs=23`.
- Contract and vectors JSON parsing — PASS through the validator’s duplicate-key-rejecting loader.
- F04 package SHA256SUMS verification — PASS as recorded above.
- Protected-source hashes, recursive submodules and dirty-path count — baseline captured; no protected source edits.
- Independent vector reconstruction — **not established**. The local canonical serialization test compares against fixed vectors, but is not an independent implementation.
- `git diff --check` — PASS; scoped new-file whitespace scan — PASS.

## Independent gate and remaining limits

Three parallel agents were used. Agent A supplied read-only source inventory; Agents B and C could not access the canonical WSL checkout (`Wsl/Service/E_ACCESSDENIED`) and correctly returned **INCONCLUSIVE** without relying on the Windows mirror. Neither independent design acceptance nor independent vector reconstruction is available. Accordingly, no reviewer authorizes F05.2 in this slice. The external independent-review package records this limitation and the required next review.

The design relies on the chosen centralized testnet committee and on future source escrow/mint-policy integrations. Real testnet keys, deployed addresses, exact script hashes and deployment ceremony are intentionally absent. A separate trust-minimized finality verifier and independent custodians remain required before production/mainnet promotion.

INV-1–INV-10 and mock-mode behavior are unchanged. In particular, bridge proof and payload hash remain distinct. No deployment or transaction was performed.

## Sources

- Current repository source facts are summarized above and source hashes are in the design evidence package.
- Cardano Conway quantity limits: [IntersectMBO Conway CDDL](https://github.com/IntersectMBO/cardano-ledger/blob/master/eras/conway/impl/cddl/data/conway.cddl).
- Polygon Amoy chain ID 80002: [Polygon documentation](https://docs.polygon.technology/tools/dApp-development/common-tools/remix/).
- Cardano Preprod network magic 1 and address network ID 0: [Cardano testnets](https://docs.cardano.org/cardano-testnets/getting-started), [Cardano native tokens](https://docs.cardano.org/native-tokens/getting-started/).
