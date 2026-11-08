# M3.2a-R17 scoped remediation review

Date: 2026-09-27
Branch/HEAD: testnet/remediation-20260907 / 829ab544571f12efe50ecb5740f129c8acb3e16f
Scope: R16 oracle findings only. No frozen R7 artifact, Cardano source, lockfile, dependency, production, credential, deployment, vendor or Git-history change.

## R16 mapping

- Symlink registry acceptance: the frozen datum loader now uses descriptor-bound O_NOFOLLOW|O_CLOEXEC directory walking, bounded regular-file reads and close-on-all-paths. R17 tests reject final and ancestor symlinks, byte-identical symlink substitution, directories and oversized files; twenty repeated reads show no descriptor growth.
- Missing canonical equality: typed bounded datum decoding now performs decode, schema typing, canonical re-encode and exact candidate/canonical/frozen byte and size equality. The R17 mutation test perturbs the encoder and the independent parser assertion fails closed.
- Authority successor trust: the authority successor seam validates the pre-state against the frozen authority vector, fixed script address/value/NFT, immutable fields, fixed epoch, canonical datum and bounded counters, then derives the successor internally and compares the candidate. Wrong address, copied/changed datum and unchanged selected counter reject.
- Optional topology: reserve validation requires one closed frozen transition, rejects null/empty/unknown values and caller topology objects, loads the hashed frozen topology before classification, and enforces its output cardinality.

## Verification

- R17 focused tests: 6/6 passed.
- Complete R9 oracle tests: 10/10 passed.
- Governance tests: 12/12 passed.
- Existing provenance runner was invoked with current source; its long-running local output is retained outside the repository and no source/provenance files changed.
- Pinned isolated Aiken 1.1.21 verifier: two runs, both check/build exit 0, ok=true, identical source manifest d255e13f04d2e27b595430cc2decf532c38e0444c01488dbfb7f312edc3afa55, blueprint 7b39b883cdc7b55aef08554e92cb089a4b3a91a6250138c4f0b181b37cfd0a80 and dependency hashes.
- Frozen R7 artifact and cardano/aiken.lock hashes match the accepted values.
- Python compilation, JSON/documentation checks, recursive submodule capture and git diff --check are required final checks.

R17 is implementation evidence only; no independent acceptance is claimed. F01-F05 remain open, Deposit remains disabled, M3 remains OPEN, Pre-Prod admission is INCONCLUSIVE, promotion is NOT READY, and M3.2b is not authorized. INV-1 through INV-10 and mock behavior are unchanged.

Next slice: independent M3.2a-R18 oracle delta review.
