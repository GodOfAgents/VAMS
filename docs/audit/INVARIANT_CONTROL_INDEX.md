# VAMS Core Invariant Control Index

The canonical machine-readable index is `invariant-controls.json`. It binds all
ten invariants to source and regression anchors and is checked by
`validate_traceability.py` in CI.

| ID | Testnet enforcement | Residual requirement |
| --- | --- | --- |
| INV-1 | Immutable 30% regional ceiling | Live allocation monitoring |
| INV-2 | 30% insurance yield ceiling | Real vault review; yield remains disabled |
| INV-3 | Session validity restricted to 1-24 hours | Live bundler integration evidence |
| INV-4 | Non-empty subset of configured core contracts | Signed deployment address allowlist |
| INV-5 | OMS institutional route fails closed | Live OMS outage test |
| INV-6 | Explicit root EOA required for TEE encoding | Real quote verifier evidence |
| INV-7 | Permissionless fixed fallback after oracle expiry | Keeper/monitoring drill |
| INV-8 | Absolute supply ceiling of $1 \times 10^9$ | Explorer supply record |
| INV-9 | Testnet reward rate zero and no staking minter | Separate reward solvency design before activation |
| INV-10 | Proof/payload separation and strict nonce ordering | Real bridge/Mithril verification evidence |

An anchor passing does not change an audit track to `verified`; runtime evidence,
reviewer approval, zero blocking findings, and matching artifact hashes are also
required by the assurance index.
