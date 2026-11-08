# T30 DA source revalidation — 2026-10-19

Status: **SOURCE-ONLY REVALIDATION; T30 REMAINS BLOCKED.** No provider was
called, no test was run, and no receipt or network behavior is claimed.

## Requirement and profile

The current profile is `docs/audit/testnet-profile.json`, SHA-256
`67136081adf06054b9385db7fe94987744529ed5a5f221ffb6ada0f5057153db`.
The faucet-only profile disables staking rewards, real fiat, real yield, and
VDSO, but the current T30 requirement remains applicable. `EVIDENCE_REQUIREMENTS.md`
(SHA-256 `895299ac7046d301f5c5c41163a09972741b7bca019ee403f2712cabc5b4c282`)
requires exactly one Celestia Mocha and one Near Testnet receipt, `mock_mode`
false, provider-native inclusion references, separate submitter and retrieval
observer identities, and retrieved bytes matching the submitted payload
SHA-256. The runtime-integration schema is
`docs/audit/schemas/runtime-integration.schema.json`, SHA-256
`e186a7ce1a376303caec46b6a0471c538d5be0c2c13d149629e0bfc7a66677e2`.
It requires two receipt objects and the named fields, restricts provider and
network values to Celestia/Near, and requires `retrieval_verified: true` and
`mock_mode: false`. The prose requirement's cross-identity distinction and
payload/artifact equality still need semantic review; field presence alone
does not prove those relationships.

## Current implementation evidence

All hashes below were read from the current dirty canonical checkout. They
bind the inspected bytes only and do not assert a committed release tree.

| Source | SHA-256 | Current source finding |
|---|---|---|
| `neuron/da/adapters/celestia_adapter.py` | `0498c0c4fc3d69ab72bd989efae82577917e6f1c601efb43f59957f98fef1f3e` | Lines 41–44 declare live submission and exact retrieval support but set `release_evidence_eligible = False`. Lines 73–109 submit through the Celestia Node API and return an unverified receipt. Lines 120–135 compare retrieved bytes to the receipt commitment. This path does not provide an independent observer or establish provider inclusion/finality. |
| `neuron/da/adapters/near_adapter.py` | `6d797515bbce468c3e7e0579e38ef315002798ed766505a7cc7985db97ea338b` | Lines 46–54 use mock submission only when requested; nonmock submission raises because the signed blob-store transaction and exact retrieval are unavailable. Lines 56–68 return false/no bytes for verification and retrieval. |
| `neuron/da/performance_audit.py` | `79b1dde2a6e1162bb019f13100a78d5dcc939c5c1b9a64a7f06f748a206aa474` | Lines 48–57 and 139–168 restrict live-capable protocols to Celestia; Near, Avail, and EigenDA are rejected from the nonmock route. Lines 237–270 mark audit results ineligible for release evidence even after same-adapter retrieval. |
| `neuron/da/adapters/avail_adapter.py` | `20e471706c4587feddafbb0c93c3e730fc000b0ce9da30af52edcef228c31c02` | Live construction is rejected; submission emits simulated receipts, verification is false, and retrieval is unavailable. |
| `neuron/da/adapters/eigenda_adapter.py` | `5cc57044bcff0712b0f4a1a9cf43ccaa7c54e317635af590502bc475a3c02050` | Live construction is rejected; submission emits simulated receipts, verification is false, and retrieval is unavailable. |
| `neuron/sdk/avail_substrate.py` | `5fa34167e9aaee4005b74a6453f3b31b15b2524128723b78d315d6dfecf64e56` | The signed-submission path is explicitly not implemented; only simulated output is available. |
| `neuron/sdk/eigenda_kzg.py` | `30010351a7f9ea9b98381b9c2085f3ebfb66c8db5a18a5835c2fc90bd54ebfc8` | The proxy SDK does not satisfy the T30 Celestia/Near provider set. Its presence does not qualify an excluded route. |
| `neuron/tests/test_da_adapters.py` | `e2f89bb23f92ee88254d951d93fd4fb696b672dd59ba19678a0fb97840b5a9ce` | Fixtures construct the adapters with `mock_mode=True`; tests cover simulated receipts and false/empty mock verification. This source is not live submission/retrieval evidence. Tests were not executed for this note. |

`docs/L3_CHAIN_AND_DA.md` (SHA-256
`02fc4d206cb94e112405626f7354bf2b58cf29d00b5d7dda7c3c1f5355226085`)
and `neuron/da/README.md` already describe these limits accurately. No
documentation correction or changelog entry is needed. `docs/audit/evidence/`
currently contains only `vdso-review-evidence.json`; no schema-compliant
`runtime-integration.json`, submission receipt, or independent retrieval
artifact is present.

## Disposition and next action

T30 remains **BLOCKED**. Existing code may support a Celestia submission and
same-adapter byte retrieval, but that is insufficient for the required
independent release evidence. The Near route cannot produce the required live
submission or retrieval, and Avail/EigenDA are excluded by the evidence
contract. No mock receipt is promoted.

The next design decision belongs to the DA owner: select the Near testnet
blob-store contract/client and signer/observer trust boundary, or explicitly
propose an in-profile provider change for review. Either choice requires a
separately scoped implementation and focused regression authorization before
code changes; a live testnet submission/retrieval also requires separate
operator authorization, non-secret credential handling, a distinct retrieval
observer, and retained provider-native evidence. Until then there is no
T30-eligible receipt. This source review does not alter INV-10, control-matrix
status, or overall readiness.
