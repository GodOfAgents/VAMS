# M0.3b-R1 local source review

This is local adjudication, not independent review or release approval.

Superproject: 829ab544571f12efe50ecb5740f129c8acb3e16f.
Direct upgradeable gitlink and clean HEAD:
aa677e9d28ed78fc427ec47ba2baef2030c58e7c.

The nested gitlink at
contracts/lib/openzeppelin-contracts-upgradeable/lib/openzeppelin-contracts
is fcbae5394ae8ad52d8e580a3477db99814b9d565 and is excluded from this
tranche by Git object type and ownership.

## Exact source review

A fresh Gitleaks 8.30.1 scan of the 682 blobs owned directly by the pinned
upgradeable commit produced 160 generic-api-key findings across 24 paths.
The staging walk skipped four entries whose Git type is commit and mode is
160000. No finding from a nested gitlink entered the tranche.

Every finding was reviewed from its exact pinned line:

- 83 JavaScript findings are Chai revertedWithCustomError assertions that
  identify expected public ERC error names. They do not assign, retrieve, or
  compare credentials.
- 75 findings are keyDer fields in the public ECDSA P1363 verification-vector
  document. Every matching group is EcdsaP1363Verify with key type
  EcPublicKey, and OpenSSL parses each object as a DER public key.
- 2 Solidity findings are ERC-7201 storage-location constants. Each constant
  independently recomputes from the adjacent public namespace formula:
  keccak256(abi.encode(uint256(keccak256(namespace)) - 1)) with the low byte
  cleared. They are deterministic layout identifiers, not credential
  material.

Only the proof categories above are retained. Scanner matches, source
snippets, DER bytes, storage-slot bytes, entropy measurements, fingerprints,
and value-derived hashes are not copied into adjudication records.

## Reachability review

- Production compilation: Foundry source is contracts/src. The two vendor
  Solidity files are not in the import closure of VAMS production sources.
  The remaining 158 findings are JavaScript tests or JSON vector data and
  cannot be Solidity compilation units.
- Deployment: contracts/script and the deployment configuration do not import
  the two vendor Solidity files or reference any of the 24 reviewed paths.
- CI execution: the workflow runs Forge in contracts, Python tests, Aiken,
  Rust, and frontend npm commands. It does not invoke the upgradeable vendor
  JavaScript tests or their JSON vector loader.
- Runtime and gateway: tracked and unignored first-party runtime source has no
  reference or loader for the reviewed paths.
- Frontend: frontend-vite runs Vite and ESLint and has no reference to the
  reviewed paths.
- Credential loading: first-party credential and environment-loading paths do
  not read these vendor files.

The source-manifest digest in every decision binds the current first-party
source and configuration inventory, including unignored new source. The helper
rehashes it before and after scanning. Documentation, Codex instructions, and
vendor contents are outside that first-party manifest; vendor contents are
instead bound by the clean direct gitlink and per-file pinned blob equality.

This is a static source/configuration reachability result, not a deployment
trace. Any source, configuration, direct gitlink, file, finding identity,
review, or evidence-reference change invalidates confirmation.

## Decision and gate policy

Separate decisions.json contains one record for each stable finding ID.
Confirmation requires the exact pinned identity, one of the three exact source
proofs, all seven reachability domains absent, accepted local review, a current
non-secret evidence reference, clean direct-submodule pin, and equality with
the pinned Git blob.

The exact-set gate is separate from Gitleaks and does not suppress findings.
Additions, removals, duplicates, rebound identities, stale evidence,
unresolved dispositions, and potential-credential dispositions fail it.
Potential-credential blockers are published in sanitized form before a
nonzero result. Raw scanner output exists only in a mode-0700 temporary
directory and is deleted before publication.

M0, M7, T06, F18, and every promotion gate remain open. Independent review is
the next separate slice. The nested-submodule tranche is not started here.
