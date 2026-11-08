# M0.3c-R1 local nested-submodule source review

This is local adjudication, not independent review or release approval.

Superproject: 829ab544571f12efe50ecb5740f129c8acb3e16f.

Parent upgradeable gitlink and clean HEAD:
aa677e9d28ed78fc427ec47ba2baef2030c58e7c.

Target nested OpenZeppelin gitlink and clean HEAD:
fcbae5394ae8ad52d8e580a3477db99814b9d565.

## Exact ownership and source review

A fresh Gitleaks 8.30.1 scan of the 821 blobs owned directly by the pinned
nested OpenZeppelin commit produced 158 generic-api-key findings across 22
paths. The Git-object walk excluded three mode-160000 commit entries:
erc4626-tests, forge-std, and halmos-cheatcodes. Findings from the top-level
OpenZeppelin tranche, the parent upgradeable tranche, and the three child
submodules are outside this tranche.

Scanner-relative paths are normalized to the full canonical superproject path
before stable finding IDs are computed. Stable IDs bind the superproject HEAD,
target nested commit, canonical nested path, rule, and exact line range. Parent
and target clean pins are also required in every decision. Similar names,
bytes, or source semantics in M0.3a or M0.3b do not authorize a decision here.

Every finding was reviewed from its exact pinned source context:

- 83 JavaScript findings are Chai revertedWithCustomError assertions that name
  expected public ERC custom errors. They do not assign, retrieve, or compare
  credentials.
- 75 findings are keyDer fields in the public ECDSA P1363 verification-vector
  document. Every matching group declares ECDSA, EcdsaP1363Verify, and
  EcPublicKey, and OpenSSL parses each DER object as a public key.

No mathematical constant finding occurs in this tranche. Scanner matches,
source snippets, DER bytes, entropy measurements, fingerprints, and
value-derived hashes are not copied into adjudication records.

## Reachability review

- Production compilation: all 158 findings are JavaScript tests or JSON vector
  data outside the Foundry Solidity source and import roots.
- Deployment: contracts/script and deployment configuration do not reference
  any of the 22 reviewed paths.
- CI execution: the security workflow runs Forge, Python, Aiken, Rust, and
  frontend commands. It does not invoke the nested vendor JavaScript suite or
  load its vector document.
- Runtime and gateway: first-party runtime and gateway source has no reference
  or loader for the reviewed paths.
- Frontend: frontend-vite does not reference the reviewed paths.
- Credential loading: first-party credential and environment-loading paths do
  not read these vendor fixtures.

The first-party source-manifest digest in every decision binds current source
and configuration, including unignored new source. Vendor contents are bound
separately by the clean parent and target gitlinks, exact pinned Git blobs, and
per-file SHA-256.

This is a static source, import, and configuration reachability result, not a
deployment trace. Any source, configuration, pin, file, finding identity,
review, or evidence-reference change invalidates confirmation.

## Decision and gate policy

Separate decisions.json contains one record for each nested-tranche stable
finding ID. Confirmation requires exact parent and target provenance, exact
pinned identity, one of the two reviewed source proofs, all seven reachability
domains absent, accepted local review, and a current non-secret evidence
reference.

The exact-set gate is separate from Gitleaks and adds no suppression. Additions,
removals, duplicates, rebound identities, cross-tranche decisions, stale
evidence, unresolved dispositions, and potential-credential dispositions fail
the gate. Potential-credential blockers are published only in sanitized form.
Raw scanner output exists only in a mode-0700 temporary directory and is
deleted before publication.

INV-1 through INV-10 and mock-mode behavior are not touched. M0, M7, T06, F18,
and every promotion gate remain open. Independent M0.3c review is the next
separate slice.

## Local verification

Focused M0.3c tests passed 17/17. M0.3a and M0.3b regression suites passed
20/20 and 16/16, and the existing Gitleaks suite passed 11/11. The negative
fixture, fresh independent scanner/Git-object/semantic reconciliation, 26-case
mutation matrix, separate exact-set gate, schema/checksum validation, and
`git diff --check` passed. The unsuppressed scan remained exit 1 with 158
findings; the separate adjudication gate exited 0.

Evidence: `/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r1-20260917T140325Z-829ab544571f`. Independent review is still required.


## M0.3c-R3 remediation — 2026-09-18

The two Medium M0.3c-R2 findings are locally remediated. Durable-evidence validation now uses closed artifact schemas, duplicate-key detection, field/type/path/hash/enum/range checks, and explicit limits for depth, collection size, serialized JSON size, and string length. The three preserved R2 bypasses were reproduced against the immutable pre-fix validator and rejected by the corrected validator. Error output contains only schema, status, and exception type.

Independent reconciliation no longer imports or calls the adjudicator and no longer repeats its assertion regex or OpenSSL DER path. It uses a bounded JavaScript token parser, verifies names against pinned Solidity error declarations, and parses DER public keys with cryptography 50.0.1. Its fresh Gitleaks 8.30.1 run preserves 158 findings across 22 paths: 83 expected custom-error assertions and 75 public ECDSA DER vectors.

Focused M0.3c tests pass 26/26. M0.3a, M0.3b, and existing Gitleaks regressions pass 20/20, 16/16, and 11/11. Evidence: /home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r3-20260918T054032Z-829ab544571f. Independent M0.3c-R4 review remains required. M0, M7, T06, F18, and all promotion gates remain open.
