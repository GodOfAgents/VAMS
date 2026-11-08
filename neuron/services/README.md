# Service Block catalogue (`neuron/services/`)

`ServiceBlockClient` currently reads hardcoded local declarations, not the on-chain
ServiceBlockRegistry. Its optional `contract_client` is stored but unused; its
presence does not qualify a read. Default-false construction denies catalogue,
manifest, memory-policy and blueprint/macro resolution APIs. Explicit
`simulation=True` requires a current `test`, `local` or `demo` runtime policy.
Live modes and policy/mock drift reject before lookup. Gateway enables it only
in demo, including the macro listing route.

Declaration validation preserves memory-policy, permission and version checks.
Locally computed JSON hashes and optional declared metadata are not authenticated
registry evidence. Listed blocks carry simulation/non-authoritative markers and
`registry_verified: false`; `verified_only` does not implement a chain filter.
The macro module and blueprint module are static planning data only.

An authenticated reader must still qualify current registration identities,
builder/fee/manifest/status and chain/finality binding through real callers. The
on-chain registry and typed settlement checks do not make this local catalogue a
verified off-chain mirror. Provider execution/receipts and both-chain end-to-end
qualification remain separate requirements.
