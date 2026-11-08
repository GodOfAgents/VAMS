# INV-1–INV-10 current-source revalidation — 2026-10-19

## Disposition

This is a source-only reconciliation against the current canonical working tree.
It records implementation anchors and missing acceptance evidence; it does not
record test execution, deployment state, live provider observations, or an
independent protocol audit. No source or test file was changed and no test,
build, Aiken command, host command, or network operation was run for this
crosswalk.

Repository HEAD at inspection: `829ab544571f12efe50ecb5740f129c8acb3e16f`.
The working tree is dirty. Hashes below bind the inspected working-tree bytes,
not a clean or release commit. Canonical control index:
`docs/audit/invariant-controls.json`, SHA-256
`7bc89ede59654921ed6192ef94c46752752ef0de25887798563e6f873c4f1732`.
Human-readable index SHA-256:
`315236c492566c0aa0cc14182ef8e3b35e50ff81dace57e86f8466115e0b5348`.
The current open-gate map is SHA-256
`e5a723db20f39f9ae0ba0c827bbf98a5217348f3fd98df9b8498e2a281f11055`.

## Source and evidence crosswalk

| Invariant | Current source observation | Existing regression anchors (present, not run here) | Remaining acceptance evidence |
|---|---|---|---|
| INV-1 regional emissions | `RegionAwareDEC` fixes `MAX_REGION_CAP_BPS` at 3,000, rejects a configured cap above it, and caps each calculated region allocation at `regionCapBps`. | `RegionAwareDEC.t.sol::test_setRegionCap_reverts_invalidCap`; the control index binds this anchor and the 3,001 boundary. | Fresh adversarial allocation tests and live allocation monitoring for admitted routes. Source cap does not establish live route allocation or monitoring. |
| INV-2 insurance yield | `deployToYield` caps tracked `totalDeployedBalance` at 30% of `totalFundBalance`; payout code checks the post-payout tracked ratio. `totalFundBalance` includes tracked deployed value. `withdrawFromYield` transfers tokens from `msg.sender`, so the source alone does not show a vault redemption or independent vault balance. | `VAMSInsuranceFund_Yield.t.sol::test_deployToYield_RevertsIfExceedsMax` and the boundary/payout cases in that file. | Yield remains disabled in the faucet profile. Review an actual vault’s custody, loss, redemption, and accounting semantics before any activation; local accounting is not redemption evidence. This source observation remains within the existing F01/yield review scope. |
| INV-3 session lifetime | `SequenceWallet` rejects non-integer/bool values and validity outside 1–24 hours. | `test_sequence_wallet.py::test_session_key_rejects_more_than_24_hours`. | Live bundler integration evidence and exact deployed session behavior. Source and unit-test presence do not establish bundler enforcement. |
| INV-4 session target | The wallet requires a non-empty allowlist, normalizes addresses, and rejects entries outside configured `core_contracts`. | `test_sequence_wallet.py::test_session_key_rejects_empty_or_non_core_allowlist`. | Signed deployment address allowlist and evidence that the live bundler applies it. |
| INV-5 institutional identity | `OMSVerificationResult.usable_for_compliance` requires verified status plus `live-provider` provenance. `CLRouter` and OMS signing paths reject missing, unavailable, failed, or non-qualifying verification. | `test_m1_2a_identity_tee_runtime.py` provider/provenance and fail-closed cases; `test_clr_v3.py` P3 routing cases; `test_oms_hybrid.py` P3/OMS cases. | Fresh live OMS outage and recovery observation against the admitted route, with endpoint and provider evidence. No live result is inferred from the source or test anchors. |
| INV-6 TEE identity | The TEE plugin requires an explicit nonzero 20-byte root EOA, rejects using the session key as that identity, and checks report binding. Phala client code labels provider evidence but source does not authenticate a real hardware quote by itself. | `test_trust_plugins.py::test_requires_explicit_root_eoa`, `test_rejects_session_key_as_root_identity`, and placeholder fail-closed cases. | Accepted real quote-verifier identity and authenticated quote evidence for measurement, root/workload, challenge, freshness, TCB, and revocation. TEE-dependent routes remain disabled. |
| INV-7 stale oracle | `CommitRevealOracle` stores an immutable configured fallback; `resolveStaleRequest` applies it only after the request deadline and emits resolution events. | `CommitRevealOracle.t.sol::test_staleRequestResolvesToFixedFallback`, `test_staleFallbackCannotBeReplayed`, and early-deadline case. | Keeper/monitoring and recovery drill on the actual profile. No live liveness or alerting is established by source. |
| INV-8 supply | `VAMSToken` sets `MAX_SUPPLY` equal to the 1,000,000,000-token initial supply and rejects minting above that cap. | `VAMSToken.t.sol::test_Mint_RevertsAboveFixedSupplyCap`. | Exact final deployed code/address and explorer or chain supply record. |
| INV-9 reward solvency | Testnet deployment constructs staking with reward rate zero, verifies it remains zero, and verifies staking has no minter role; the testnet profile disables staking rewards. `VAMSStaking` still contains accrual and minting paths for enabled configurations. | `scripts/audit/test_deployment_readiness.py::test_scanner_covers_reward_and_minter_disablement`. | The restricted profile must remain disabled. Any activation requires an owner-approved funded-liability/solvency design and fresh exact deployment evidence. Tokenomics decisions remain pending in `TOKENOMICS_OWNER_DECISIONS_R1_20261008.md`; no economic interpretation is inferred here. |
| INV-10 bridge proof | `cardano/lib/vams/icb.ak::verify_bridge_proof` checks minimum length and nonempty payload-hash bytes, not cryptographic verification or a binding between them. `ICBClient` similarly performs structural checks and refuses live construction; its nonce tracker is process-local. The insurance validator’s current deposit boundary rejects the proof-bearing deposit form. | `neuron/tests/test_clr_v3.py::test_icb_nonce_replay`; `cardano/lib/vams/icb.ak::prop_nonce_replay_always_rejected` is a source anchor only. | Real bridge/Mithril verification, proof-to-payload/domain/finality binding, durable replay protection, transaction-level validator evidence, and an independent observer. Bridge effects remain disabled. |

## Exact inspected source/test bindings

| Invariant | Source bindings (path — SHA-256) | Test-source bindings (path — SHA-256) |
|---|---|---|
| INV-1 | `contracts/src/economic/RegionAwareDEC.sol` — `cb8191c3782754d7774bd682e1d5799520240bb7f5d3c4cd46bafa2e7254ec86` | `contracts/test/economic/RegionAwareDEC.t.sol` — `0cbafdd8fe4c982695c20751385d3029fd6f0f3b6b649ca32055d79ff29b7800` |
| INV-2 | `contracts/src/economic/VAMSInsuranceFund.sol` — `f9e8466b6a56816af565f4a6add2348b581007fe727dc7e6fbe9d1dc1e8f775d` | `contracts/test/economic/VAMSInsuranceFund_Yield.t.sol` — `636e504ba25fc117d38ab9480aba6f89c3a8da0f2740e54e8555bf8f88151e25` |
| INV-3/4 | `neuron/sdk/sequence_wallet.py` — `a8e7f7103fc7172307036767f385fce5abb197765a18ca2aee420125ce93ffad` | `neuron/tests/test_sequence_wallet.py` — `5e9ab75099fd026a42563cb3af409b179115a226e979a7c97ddf0679de46ad87` |
| INV-5 | `neuron/sdk/oms_identity.py` — `38471dc06868c42bc0035d63683ba73038eb214005bf65c81aee0fcd626c9a09`; `neuron/clr_router.py` — `ea56a16330521bcb0250eb8ead939ca6388129590afb2ae71d574d8c47e35ace`; `neuron/sdk/signer.py` — `64bcbed98550ac084392106df46b68cba10d11698fcf0b9935c55836b6a904b3` | `neuron/tests/test_m1_2a_identity_tee_runtime.py` — `6b7ea8427713300659b3f8f9eb9f25823c094fa8eb90d316ad5c5868d8ba2cbd`; `neuron/tests/test_clr_v3.py` — `87370ffaaa6e89199319a04d372e4ce873a64dab896c0fc18d254ff1c021f680`; `neuron/tests/test_oms_hybrid.py` — `3aad88a6dc162450c9c93ffb4ce6f645680712f19bcd0b1fb71341a030da3dde` |
| INV-6 | `neuron/trust_plugins/tee_plugin.py` — `c324996897a72fc9fdc0d19a218568a7b055bc905fe44211bb3b20c6be4bc34e`; `neuron/sdk/phala_tee.py` — `a477288dbac1457dba979b679e629184f1fa82d69b2143b937f6e302aac91a86` | `neuron/tests/test_trust_plugins.py` — `889eac08c523c91bd253f9bdae00db1bb37bfbcd7118b54c9549b8cc65d3475d` |
| INV-7 | `contracts/src/oracle/CommitRevealOracle.sol` — `ef954da24ef00b372491379326ea4528d0d7ea66e78528668e718567c8c6871f` | `contracts/test/oracle/CommitRevealOracle.t.sol` — `76a53a6890e17cb876a316fc9ab3e78c11da7dbc253fb7e077be516260cfb52a` |
| INV-8 | `contracts/src/token/VAMSToken.sol` — `df9e5d7bd893a617359c68638766858fa2eb6883fe7458820d0c9d079f4ddc17` | `contracts/test/token/VAMSToken.t.sol` — `3a28b94e08bcf22a55d094a76915cd3788aae3287f16f6b12c3ecbd0a2364558` |
| INV-9 | `contracts/src/staking/VAMSStaking.sol` — `543e5183d7c0c1ca65f6b9d20063fdbb6127c248115120bc5ef41859b049f950`; `contracts/script/DeployTestnet.s.sol` — `542d6aed8e5fb1cccc08ef8ceed6361ae7aa715bb181dfa65894c203b2c15cf9`; `docs/audit/testnet-profile.json` — `67136081adf06054b9385db7fe94987744529ed5a5f221ffb6ada0f5057153db` | `scripts/audit/test_deployment_readiness.py` — `bbb26bebacc3d83ba4e0b78fc19927fb376a523891f4b90cc56318e2ebc6c9f1` |
| INV-10 | `neuron/bridge_executor.py` — `d5d6c8d7a6c18aa694b10e1714a690642f42f7815a6bf83437e34efe4b4ae0fb`; `cardano/lib/vams/icb.ak` — `6df86d4549e9289734b80d2193cc77fffedcb856b46fe41e29d3d8134a8b7917`; `cardano/validators/insurance_fund.ak` — `184d5c19c65037ee37999af0988166dca2d28a2e2772e268e1c1738a382ecf5f` | `neuron/tests/test_clr_v3.py` — `87370ffaaa6e89199319a04d372e4ce873a64dab896c0fc18d254ff1c021f680`; Aiken property source is in `cardano/lib/vams/icb.ak` (same hash; not executed) |

## Gate effect and next actions

All ten rows remain source-anchored, not verified. The existing map’s acceptance
criteria and owner/reviewer dependencies remain controlling; this crosswalk
does not alter them. No test-source presence is reported as a passing test.
There is no new independent review of this note.

The three owner tokenomics decisions remain open. F01/F05/F06/F07/F10 and the
other open findings retain their existing dispositions. For the immediate R28
path, the current handoff still records missing reviewed collector/input and
no-clobber supervisor artifacts; their source preparation and independent
static review require the specific separate authorization already identified
there. Host collection, resolver execution, runtime audit, provisioning,
boundary validation, candidate collection, qualification, Aiken, and
deployment remain unauthorized by this source review.

Readiness remains NOT READY. Deployment, Deposit, Slash activation, and
ExecuteIntent remain disabled. Amendment 06 accounting remains 2 suite
invocations granted / 1 consumed / 1 remaining; Slot 08 remains NOT RUN; Slot
07 remains unsuccessful, cleanup-incomplete, and `OWNERSHIP_UNCERTAIN`.
