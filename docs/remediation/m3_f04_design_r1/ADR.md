# M3/F04 registry design R1

Status: design frozen; implementation and independent review remain open.

This design is documentation-only. It does not alter the current Aiken
validators, blueprint, lockfile, provenance, dependencies or deployment.

## Identity

Registration consumes one bootstrap OutputReference exactly once as a regular
input. The parameterized identity-NFT policy is bound to that reference. The
single 32-byte token name is the BLAKE2b-256 digest of the domain tag
`VAMS/agent/v1\\0`, a u16 big-endian DID length, the DID, immutable owner
verification-key hash, seed transaction ID and seed index. The policy mints
exactly one derived unit, retains one through updates/slashes and burns one on
deregistration. Other units, names, policies or quantities reject.

## State and transitions

AgentDatumV1, authority binding, finite limits, transition topology, value
rules and mutation rows are machine-readable in the companion artifacts.
Owner, DID, policy and token are immutable. An owner may change operator and
metadata; an operator may change metadata only, and neither operator nor owner
may bypass stake, identity or epoch rules. Nonce increments exactly once;
action_epoch must match the unique RegistryAuthorityV1 reference input.
Registration creates exactly one state output. Update creates exactly one
same-script, same-identity continuation. Deregistration creates exactly one
owner payout, returns every non-identity state asset and burns exactly one
identity unit; it creates no state continuation. Slash has a complete post-F05
interface and equation but rejects unconditionally in the pre-F05 profile.

The policy binding is symbolic but exact: the policy ID is the hash of the
actual compiled parameterized NFT policy applied to the consumed bootstrap
reference. It cannot be copied from a datum or replaced by a fixture alias.
The post-F05 slash interface requires one verified evidence reference bound to
identity policy/token, action epoch, authorized slasher and expiry.

This is not F04 remediation or deployment evidence. INV-1–INV-10 and mock-mode
behavior are unchanged.
