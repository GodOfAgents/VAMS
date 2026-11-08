# M0.3c-R5 remediation review

Status: locally implemented and verified; independent M0.3c-R6 review required.

Repository: /home/GodOfAgents/code/VAMS-testnet
Branch: testnet/remediation-20260907
Superproject HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f
Parent submodule: aa677e9d28ed78fc427ec47ba2baef2030c58e7c
Target nested submodule: fcbae5394ae8ad52d8e580a3477db99814b9d565

## Reproduced R4 findings

The immutable R4 package passed strict checksum verification and its
SHA256SUMS file hashes to
c2f74e04c89184195c962e266f3485ed59070a0515f51514e7a785bac58bb1bc.

Before editing, all eight documented schema mutations passed the old validator
after both checksum layers were rebuilt. The undeclared ERC custom-error probe
was confirmed by the old production classifier and exact-set gate while the
independent reconciler rejected it. The prior mutation tests were also shown to
stop at checksum rejection unless both layers were rebuilt. Sanitized
reproduction records are retained in the R5 evidence package.

## Remediation

Durable M0.3c artifact validation now uses closed field sets for every object,
duplicate-safe JSON loading, strict booleans and integers, canonical paths,
bounded depth, collection counts, strings, serialized size, exact environment
fields, and the exact authorized changed-file set. Dynamic hash maps have exact
key sets. Unknown, missing, null, malformed, overlong, duplicate, rebound, or
sensitive nested data fails with a stable validation code. raw_removed remains
a required boolean.

Expected-error confirmation now requires a unique declaration in the pinned
Solidity tree after comments and strings are removed, plus an ERC-standard
context appropriate to the reviewed test path. A separate independent semantic
oracle starts from a fresh Gitleaks scan of the 821 directly owned Git blobs.
It uses a bounded JavaScript token parser and cryptography 50.0.1 DER public-key
parsing. The oracle does not import or call the adjudicator classifier.

The independent attestation binds the superproject HEAD, parent and target
commits, all 158 stable identities, canonical paths, rules, line ranges,
file SHA-256 values, Git blob object IDs, the decisions digest, first-party
source-manifest digest, scanner hash/version, oracle hash, pinned Python
hash/version, and cryptography module hash/version. The exact-set gate requires
one agreeing attestation record for each decision. Missing, stale, ambiguous,
or disagreeing semantics remain unresolved. Potential-credential records remain
publishable as sanitized blockers and cannot pass the gate.

## Observed local verification

- Focused M0.3c-R5 tests: 39/39 passed.
- Rebuilt-checksum adversarial validator matrix: 53/53 passed; both checksum
  layers passed before every schema assertion.
- M0.3a regression tests: 20/20 passed.
- M0.3b regression tests: 16/16 passed.
- Existing Gitleaks tests: 11/11 passed.
- Negative fixture regression: passed.
- Fresh unsuppressed Gitleaks 8.30.1 scan: exit 1, 158 findings, 22 paths.
- Independent Git-object and semantic reconciliation: 821 blobs, three child
  gitlinks excluded, 83 declared expected-error assertions, 75 public EC DER
  vectors, raw report removed.
- Fail-closed mutation matrix: passed.
- Dual-proof exact-set gate: exit 0 with 158 confirmed, 0 unresolved, and
  0 potential credentials.
- Preserved R1 schema/checksum validation and git diff checks: passed.

No raw scanner match, secret, snippet, entropy value, fingerprint, credential
value, or value-derived digest is retained.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1 | No impact; regional emissions are unchanged. |
| INV-2 | No impact; insurance deployment limits are unchanged. |
| INV-3 | No impact; session-key lifetime is unchanged. |
| INV-4 | No impact; session-key scope is unchanged. |
| INV-5 | No impact; OMS fail-closed routing is unchanged. |
| INV-6 | No impact; TEE identity binding is unchanged. |
| INV-7 | No impact; oracle freshness and fallback are unchanged. |
| INV-8 | No impact; the VAMS supply cap is unchanged. |
| INV-9 | No impact; reward solvency is unchanged. |
| INV-10 | No impact; bridge proof and payload separation is unchanged. |

Mock mode is unchanged. This slice changes only local adjudication, validation,
tests, and audit records. It does not change runtime, gateway, contracts,
deployment, CI execution, vendor content, or scanner configuration.

M0.3c-R5 is not an independent approval. M0, M7, T06, F18, and every promotion
gate remain open. The next single slice is independent M0.3c-R6 review.
