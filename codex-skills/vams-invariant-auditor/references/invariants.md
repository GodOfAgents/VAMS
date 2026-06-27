# VAMS Invariants

Use this map when reviewing diffs, designs, deployments, or PRs.

| ID | Rule | Primary Files |
| --- | --- | --- |
| INV-1 | Regional emissions per region must be <= 30%. | `contracts/src/economic/RegionAwareDEC.sol`, `neuron/economics/dec_regional.py` |
| INV-2 | Insurance idle capital deployed to yield must be <= 30%. | `contracts/src/economic/VAMSInsuranceFund.sol`, `neuron/economics/yield_manager.py` |
| INV-3 | ERC-4337 session keys must expire within <= 24 hours. | `neuron/sdk/sequence_wallet.py` |
| INV-4 | Session keys must be restricted to whitelisted VAMS contracts. | `neuron/sdk/sequence_wallet.py` |
| INV-5 | Institutional P3 compliance must fail closed on OMS identity failure. | `neuron/clr_router.py`, `neuron/sdk/oms_identity.py` |
| INV-6 | TEE attestations must bind to root EOA, not session keys. | `neuron/trust_plugins/tee_plugin.py`, `neuron/sdk/phala_tee.py` |
| INV-7 | Stale oracle data must trigger fallback and never be used silently. | `contracts/src/oracle/CommitRevealOracle.sol`, `neuron/chain_oracle.py` |
| INV-8 | Max $VAMS supply is fixed at 1e9. | `contracts/src/token/VAMSToken.sol` |
| INV-9 | Reward pools must cover pending rewards. | `contracts/src/staking/VAMSStaking.sol`, `contracts/src/economic/RewardDistributor.sol` |
| INV-10 | Cross-chain `bridge_proof` must remain separate from `payload_hash`. | `neuron/bridge_executor.py` |

Review rules:

- Treat math constants as security boundaries.
- Require tests for every affected invariant.
- Do not accept documentation-only proof for executable behavior.
- If deployment is involved, require chain ID, addresses, tx hashes, role owners, and verification evidence.
