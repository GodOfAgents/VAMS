# M3.2/F04 design freeze R1

This is a documentation-only contract freeze for the hybrid seed-bound
identity NFT and registry state machine. The policy is bound to one consumed
bootstrap reference; the token derivation, AgentDatumV1 schema, authority
epoch, topology, value rules and mutation matrix are closed in the companion
artifacts.

R3 closes the design ambiguities around exact deregistration payout/cardinality,
unique authority references and action epochs, same-script continuation identity,
non-ADA conservation, owner/operator permissions, symbolic binding to the
actual parameterized policy, and the post-F05 evidence interface. Slash remains
unconditionally rejected before F05.

The current Cardano sources and compiled blueprint remain unchanged and do not
implement this contract. No F04 remediation, testnet readiness, Pre-Prod
admission or promotion claim is made.

Only this directory is in scope. INV-1–INV-10, mock-mode behavior, credentials,
deployment state and provenance are unchanged. The next implementation slice
must compile the real entrypoints with pinned Aiken and independently review
every matrix mutation.
