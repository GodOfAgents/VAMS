# M3.2/F04 design R5

This documentation-only delta freezes the authority, replay, reserve-routing,
and INV-10 proof/payload separation contract for the F04 design. The
RegistryAuthorityV1 reference is unique and exact; update and post-F05 slash
replay identities bind policy, identity asset, nonce, and action epoch; slash
reserve routing is fixed by the authority reference; and bridge_proof remains
distinct from payload_hash.

The acceptance matrix adds explicit mutations for replay reuse and concurrency,
stale epochs, reserve redirection, evidence rebinding/expiry, and proof/payload
aliasing. The validator now closes these fields and requires the 49-row matrix.
R5 tests exercise the validator and generator from three working directories,
with poisoned import paths, and validate mutation rejection through the public
validate seam.

No production Cardano source, compiled blueprint, lockfile, provenance,
dependency, deployment or runtime file changed. F04 remains design-only and
open; F01-F05, M3, Pre-Prod admission and promotion remain unchanged.
INV-10 is preserved by construction and mock-mode behavior is unchanged.
