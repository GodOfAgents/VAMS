# Gitleaks Historical Finding Adjudication

Current-tree scan follow-up, 2026-10-31 (checkpoint22): the unchanged pinned
Gitleaks8.30.1 narrow-allowlist regression passes. The unchanged M0.4 current-tree
gate exits1 for first-party matches. A separate metadata-only diagnostic scans
all6,690 manifest files:640 first-party matches across70paths (636 in retained
remediation documents,4 in3remediation helpers), all generic-api-key. Its479 vendor
identities exactly match the existing baseline (161/160/158). This diagnostic is
not an adjudication or a substitute for the failing gate. Current public file
digests explain59 matches by exact source-hash equality;581 remain unresolved by
the initial shape analysis. All640 initial records remain UNREVIEWED.

The newest decoder campaign field is a verified public report digest. Represent
it explicitly as focused_scan_evidence {artifact,algorithm,digest}, preserving its
value and all other campaign fields. The unchanged scanner reproduces1 match on
the original and0 on the proposed record. Preserve both originals and exact run
identities; this one correction does not accept the other639 initial matches or
complete T06. Historical evidence and its hashes stay intact. No allowlist, vendor,
workflow or official finding/track disposition changes. No private value, match,
snippet, entropy or scanner fingerprint is retained in the diagnostic packet.

Full-history Gitleaks, all-category TruffleHog, credential-impact/rotation/history
coordination, independent disposition and the other frozen gates remain required.
No history rewrite, provider request, external service, dependency acquisition,
Aiken/Slot08/R28, signing, role/fund operation or deployment occurred. Product
source/855Solidity/7Python results keep their prior source identity; these metadata
checks do not repeat or enlarge them. F16 remains open; all18 finding records,
13open findings/0of36verified tracks and all INV-1--INV-10 controls are unchanged.
The full A--G program still requires BOTH PolygonAmoy and CardanoPre-Prod.


## M0.4 aggregate current-tree baseline — 2026-09-21

Pinned Gitleaks 8.30.1 now runs one repository-native aggregate current-tree
gate in CI after recursive submodule checkout. The gate reports exactly zero
first-party findings and 479 reviewed vendor identities: M0.3a 161, M0.3b 160,
and M0.3c 158. It verifies the three approved owner commits, clean worktrees,
direct Git blob ownership, deepest-child gitlink attribution, canonical paths,
rules, line ranges, file hashes, and stable sanitized identity digests.

The baseline SHA-256 is
`3a4526acf33ab4adeff87da1553cb5e4493799c3696664c2d60a126a9aa086f4`.
A separate no-import reconstruction reproduced the exact set. Raw reports are
temporary and deleted on all gate paths; durable output contains no raw match,
secret, snippet, entropy, fingerprint, or scanner report.

No `.gitleaks.toml` allowlist or vendor content changed. The R9 evidence
validator remains auxiliary and outside CI/promotion trust. This current-tree
result does not replace complete-history Gitleaks, TruffleHog, default-
credential closure, or T06 credential-incident requirements, all of which
remain open.

## M0.3b-R1 — direct upgradeable adjudication — 20260916T125143Z

At superproject HEAD '829ab544571f12efe50ecb5740f129c8acb3e16f', the clean direct
upgradeable gitlink 'aa677e9d28ed78fc427ec47ba2baef2030c58e7c' owns 160 fresh
Gitleaks 8.30.1 findings across 24 paths. Gitlink-typed entries were excluded
from the scanner staging tree, so the nested OpenZeppelin submodule was not
included. Exact source review confirmed 83 public error assertions, 75 public
ECDSA DER vectors, and 2 deterministic ERC-7201 storage locations. Dispositions
are 160 confirmed noncredential fixtures, 0 unresolved, and 0 potential
credentials.

The unsuppressed scanner still exits 1. A separate exact-set adjudication gate
passes only for the complete content-addressed decision set and fails closed
for source, identity, review, disposition, manifest, or set drift. Evidence is
'/home/GodOfAgents/vams-evidence/m0-20260909/m0-3b-r1-20260916T125143Z-829ab544571f'. No '.gitleaks.toml' or vendor change was made. Independent review,
M0, M7, T06, F18, and every promotion gate remain open.

**Local scan date:** 2026-07-15

**Latest fully triaged CI artifact:** run `29416245559`, 2026-07-15

**Latest reproducing PR run:** `29611633518`, 869 findings across 65 scanned
commits

**Tool:** Gitleaks v8.30.1

## Gate Result

The history scan is **blocking**. No unconditional baseline or global
allowlist is accepted. The preparation branch adds only two rule-targeted
`generic-api-key` AND allowlists for exact public curve-type expressions and
exact 40-hex-character EVM addresses. Regression fixtures prove that 64-hex
private keys, AWS-style tokens, generic API tokens, and adjacent-line secrets
still fail.
The earlier local complete-history inventory reported 1,740 matches across 15
finding-bearing commits: 1,737 generic API-key matches and three private-key
matches. The underlying sanitized local report is not in the repository, so
those counts cannot yet be independently reconciled path by path.

Protected CI run `29416245559` scanned the PR merge SHA
`e2526ffb0e42540d13a82b75d06f60b293159622` with:

```text
gitleaks git . --redact=100 --report-format json \
  --report-path raw-gate/gitleaks-report.json --log-opts=--all --exit-code 1
```

It reported 869 fully redacted matches across 27 paths and nine
finding-bearing commits: 867 `generic-api-key` and two `private-key` findings.
The raw gate bound the report to SHA-256
`9aad228b9ae34c08e48fc14f5bc859f3785f493e7d1781813781f4672334417e`.
No matched value is reproduced here.

## Exact Protected-CI Path Classification

These counts are derived from the sanitized run `29416245559` artifact and
sum exactly to 869.

| Group | Sanitized paths | Matches | Status |
| --- | --- | ---: | --- |
| Deleted Foundry output | `contracts/test_output_cmd.json`, `contracts/clean_output.json` | 802 | Generated output; remove from rewritten history rather than baseline globally. |
| Upstream Foundry fixtures | Eleven paths under `.foundry/` | 46 | Remove the tracked vendor tree from the current tree and all rewritten history; do not allowlist it. |
| Current Neuron source/configuration | `neuron/secp256k1.py`, `neuron/config.py`, `neuron/eth_client/sequence_wallet.py` | 6 | Allow only exact public curve/address matches under the targeted rule; remove the deleted wallet helper from rewritten history. |
| Legacy provider helpers | Five paths under `scripts/`: `simulate-request.mjs`, `simulate-request-v2.mjs`, `simulate-request-v3.mjs`, `register-agent.mjs`, `verify-escrow.mjs` | 9 | Blocking; correlated with Infura/Polygon TruffleHog detections and targeted for removal. |
| Historical deployment helpers | `EmergencyLockdown.s.sol`, `DeployX402.s.sol`, `RegisterAgent.s.sol` | 3 | Allow only the exact 40-hex public EVM-address matches under `generic-api-key`; other rules and adjacent matches remain active. |
| Historical Telegram bot | `telegram-bot/bot.js` | 1 | Remove the deleted file from rewritten history; do not allowlist it. |
| PEM identity paths | `node_identity.pem`, `neuron/node_identity.pem` | 2 | Confirmed private-key paths; never allowlist. Rotation, impact review, and history removal are mandatory. |

The difference between the earlier 1,740 local findings and the 869 CI
findings likely reflects different reachable-ref sets, but that is an
inference—not an adjudication. Preserve both inventories and reconcile them
after the coordinated all-ref rewrite.

## TruffleHog Correlation

Run `29413794423` recorded one verified Infura finding and 19 unverified
findings. The verified item was at historical path `scripts/simulate-request-v3.mjs`,
line 6, commit `1321f91586784d218ebc11126de588fbcf649ec6`.

The later protected run `29416245559` recorded the same 20 sanitized detector
events as unverified: zero verified and 20 unverified. This is consistent with
the provider credential no longer verifying, but it does **not** prove the
revocation time, affected project, replacement, access/billing impact, or
reviewer acceptance. Those facts require separate sanitized provider evidence.
See [TRUFFLEHOG_TRIAGE.md](TRUFFLEHOG_TRIAGE.md).

## Required Closure

1. Revoke every provider credential found in the five legacy helper paths.
   Retain only a non-sensitive provider/project fingerprint, the real dashboard
   observation time, `exact_revocation_time_unavailable=true`, the access and
   billing review interval, impact disposition, and Architect identity.
2. Record both historical PEM finding occurrences, then derive the two
   unique public-key fingerprints from public representations—not from raw
   private PEM bytes. Permanently decommission both unused identities and
   record that no replacement fingerprint exists because no role, funds, or
   dependency relied on either identity.
3. Prove each unique PEM identity controls no deployment signer, funded account,
   node, provider, Safe, timelock, or validator role. Record Polygon Amoy and
   Cardano Pre-Prod account-derived checks or cryptographic non-applicability.
4. Use the disposable-mirror procedure in
   [CREDENTIAL_INCIDENT_RUNBOOK.md](CREDENTIAL_INCIDENT_RUNBOOK.md). Do not run
   a rewrite in a working clone and do not push without explicit approval.
5. Apply the checked-in rule-targeted allowlists only after their negative
   regression passes. Remove `.foundry/`, PEMs, deleted legacy helpers,
   generated outputs, the deleted wallet helper, and the deleted Telegram bot
   from all rewritten refs. Never allowlist those paths.
6. Coordinate every ref, fork, open PR, cached GitHub view, and collaborator
   clone. Collaborators must discard old clones and reclone.
7. Rerun complete-history Gitleaks and all-category TruffleHog. Both final
   schema-bound reports must contain zero findings.
8. Only then create `credential-incident-report.json` in the protected
   operational evidence bundle. Every referenced artifact must exist, be
   non-empty, and match its declared SHA-256.

No credential-incident closure report is committed in the repository. Missing
external evidence remains missing, and readiness remains **NO-GO**.

## M0.1 working-tree inventory

The repository-native inventory stages tracked files, non-ignored untracked files, and initialized pinned submodule content in a fresh temporary directory. It excludes generated bytecode, caches, temporary outputs, and ignored build artifacts by construction; validates canonical paths, symlink containment, submodule provenance, and `sha256sum -c` checksums before invoking pinned Gitleaks 8.30.1. The sanitized ledger and deterministic summary contain metadata only. M0.2 restored the pinned executable and recorded 479 redacted `generic-api-key` findings across 69 pinned OpenZeppelin paths; the 3,279-path manifest contained zero generated `.pyc` or cache paths. Findings remain unresolved and no readiness claim is made.

M0.3a adjudication reconciled exactly 161 findings in `contracts/lib/openzeppelin-contracts` at commit `239795bea728c8dca4deb6c66856dd58a6991112`, bound to superproject HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`. All 161 are recorded individually as `unresolved`; no allowlist or credential disposition was applied. Durable evidence is `gitleaks-adjudication-openzeppelin-20260915T011500Z-829ab5`.

## M0.3a-R1 — evidence-driven adjudication — 20260916T051313Z

Local repair and verification only, on branch `testnet/remediation-20260907`,
HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f` with existing dirty work preserved. The previous M0.3a output
was a placeholder inventory, not completed adjudication; its artifacts remain
unchanged.

Observed dispositions: **161 confirmed_noncredential_fixture, 0 unresolved,
0 potential_credential**, across 23 paths. Exact review found 86 expected ERC
error assertions and 75 public ECDSA DER verification vectors. Every decision
binds its stable ID, HEAD, clean OpenZeppelin gitlink/HEAD, exact file SHA-256,
path/rule/line, deterministic role/proof, reachability snapshot and accepted
local reviewer. Independent review remains pending.

Evidence: `/home/GodOfAgents/vams-evidence/m0-20260909/m0-3a-r1-20260916T051313Z-829ab544571f`. The `tranche/source-checksums.sha256` digest is
`46962e118fd1ee67383c47afa4c714c8b8865ad45eb75651325d44dc14421d38`. Approved decisions SHA-256:
`6d33e8d7df837f03bb2ee4dd15054c912e0ded4d957965c1d7f5fb6b134a0a18`. The pack records exact commands, interpreter, durations, exits,
hashes, 161-record schema validation and M0.2/M0.3a reconciliation.

Verification: Python 3.12.14 focused tests **19/19**, existing Gitleaks tests
**11/11**, pinned allowlist negative regression passed; Gitleaks **8.30.1**
unsuppressed scan returned **1 with 161 findings**; separate exact-set
adjudication returned **0**. Tranche checksums passed. Source/configuration
reachability review covered all 23 paths and 454 first-party source files,
with zero execution references and no first-party Foundry file/FFI calls.
Raw scan data was deleted from its mode-0700 temporary directory before
publication. `git diff --check` is recorded in the same verification pack.

Changed scope: adjudication helper/tests; `docs/remediation/m0_3a_r1/`
decision, identity and review artifacts; audit, changelog and handoff notes.
No vendor or `.gitleaks.toml` edits, scanner suppression, commit, push or
deployment. INV-1 through INV-10 and live mock-mode behavior are not touched.
This gate covers only this exact dirty source snapshot and this single
submodule tranche; history scanning, other findings and release assurance
remain separate blockers. **M0, M7, T06, F18 and all promotion gates stay open.**

Next single slice: independent review of M0.3a-R1 and its evidence. Stop here;
do not begin another submodule or later remediation.

## M0.3a-R1 — evidence-driven adjudication — 20260916T051519Z

Local repair and verification only, on branch `testnet/remediation-20260907`,
HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f` with existing dirty work preserved. The previous M0.3a output
was a placeholder inventory, not completed adjudication; its artifacts remain
unchanged.

Observed dispositions: **161 confirmed_noncredential_fixture, 0 unresolved,
0 potential_credential**, across 23 paths. Exact review found 86 expected ERC
error assertions and 75 public ECDSA DER verification vectors. Every decision
binds its stable ID, HEAD, clean OpenZeppelin gitlink/HEAD, exact file SHA-256,
path/rule/line, deterministic role/proof, reachability snapshot and accepted
local reviewer. Independent review remains pending.

Evidence: `/home/GodOfAgents/vams-evidence/m0-20260909/m0-3a-r1-20260916T051519Z-829ab544571f`. The `tranche/source-checksums.sha256` digest is
`608075bcbe423fa0eacaaa01c0c4c302f0678a759fe13ead9cf07a6202f68bad`. Approved decisions SHA-256:
`5f41aa64b31ead7918c2d9d07ec0a803f44af8e213aa2e1d55e404e7d67f16e4`. The pack records exact commands, interpreter, durations, exits,
hashes, 161-record schema validation and M0.2/M0.3a reconciliation.

Verification: Python 3.12.14 focused tests **20/20**, existing Gitleaks tests
**11/11**, pinned allowlist negative regression passed; Gitleaks **8.30.1**
unsuppressed scan returned **1 with 161 findings**; separate exact-set
adjudication returned **0**. Tranche checksums passed. Source/configuration
reachability review covered all 23 paths and 454 first-party source files,
with zero execution references and no first-party Foundry file/FFI calls.
Raw scan data was deleted from its mode-0700 temporary directory before
publication. `git diff --check` is recorded in the same verification pack.

Changed scope: adjudication helper/tests; `docs/remediation/m0_3a_r1/`
decision, identity and review artifacts; audit, changelog and handoff notes.
No vendor or `.gitleaks.toml` edits, scanner suppression, commit, push or
deployment. INV-1 through INV-10 and live mock-mode behavior are not touched.
This gate covers only this exact dirty source snapshot and this single
submodule tranche; history scanning, other findings and release assurance
remain separate blockers. **M0, M7, T06, F18 and all promotion gates stay open.**

Next single slice: independent review of M0.3a-R1 and its evidence. Stop here;
do not begin another submodule or later remediation.

## M0.3c-R1 — nested OpenZeppelin source adjudication

At superproject HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, the
parent upgradeable gitlink `aa677e9d28ed78fc427ec47ba2baef2030c58e7c`
pins the target nested OpenZeppelin gitlink
`fcbae5394ae8ad52d8e580a3477db99814b9d565`. Both working trees were clean.
An independent Git-object walk enumerated 821 directly owned blobs and excluded
the `erc4626-tests`, `forge-std`, and `halmos-cheatcodes` child gitlinks.

The pinned, unsuppressed Gitleaks 8.30.1 scan returned exit 1 with 158
`generic-api-key` findings across 22 canonical nested-submodule paths. One
decision exists per stable identity: 83 are exact expected custom-error
assertions and 75 are public ECDSA DER verification vectors independently
parsed as public keys. Final dispositions are **158
confirmed_noncredential_fixture, 0 unresolved, and 0 potential_credential**.
No scanner match, source snippet, DER datum, entropy, fingerprint, or
match-derived digest is retained.

Every decision binds the superproject HEAD, parent and target clean pins,
canonical path, rule, line range, source-file SHA-256, first-party source
manifest, source semantics, fixture role, all seven reachability domains,
accepted review, and non-secret evidence references. The exact-set gate is
separate from scanner behavior and rejects additions, omissions, duplicates,
rebindings, stale evidence, pending review, unresolved or potential findings,
cross-tranche decisions, and nested sensitive fields. The scanner remains
unsuppressed.

Evidence: `/home/GodOfAgents/vams-evidence/m0-20260909/m0-3c-r1-20260917T140325Z-829ab544571f`. Approved decisions SHA-256: `a079b6b85aaf510df2fedc63d60802229fde0eb7a91ecc344854aba2c21b3aa1`.
Independent M0.3c review remains pending. This result does not close M0, M7,
T06, F18, or any promotion gate.


## M0.3c-R3 validator and oracle remediation

M0.3c durable evidence now rejects duplicate JSON keys, unknown artifact fields, malformed identity scalars, composite sensitive metadata, overlong strings, oversized collections, excessive nesting, and unexpected artifacts. The preserved R1 package remains valid under the closed schema.

The independent nested-submodule reconciliation uses a bounded token parser for JavaScript assertion calls and cryptography 50.0.1 for DER public-key parsing. The production adjudicator remains unchanged. A fresh unsuppressed scan still yields 158 findings across 22 paths, reconciled as 83 expected custom-error assertions and 75 public ECDSA DER vectors. No Gitleaks suppression or allowlist changed. Independent R4 review is pending.


## M0.3c-R5 closed-schema and dual-proof remediation

R4's eight schema bypasses, undeclared-error semantic disagreement, and
checksum-short-circuit test weakness were reproduced before editing. R5 now
requires strict closed schemas, both checksum layers before schema assertions,
unique pinned Solidity error declarations in a valid ERC context, and a
content-addressed independent semantic attestation for every confirmed
identity. Fresh local verification preserved 158 findings across 22 paths:
83 declared expected-error assertions and 75 public EC DER vectors. The
unsuppressed scanner still exits 1; the separate dual-proof gate exits 0.
Independent M0.3c-R6 review remains required. M0, M7, T06, F18, and all
promotion gates remain open.

## M0.3c-R7 filesystem and execution-context remediation

R6 demonstrated that checksum-valid packages could retain unsafe open values or filesystem entries and that repository-wide same-standard declarations could authorize unrelated custom-error assertions. R7 replaces those boundaries with exact no-follow topology inspection and field-specific closed validation. Custom-error evidence binds the assertion and invoked operation to the actual deployed artifact, exact signature/selector, pinned declaration/caller blobs, and a proven inheritance/interface/used-library chain. A separate oracle independently derives the same context.

Fresh unsuppressed Gitleaks 8.30.1 results remain 158 findings across 22 nested-submodule paths: 83 exact expected-error execution contexts and 75 public DER vectors. All 158 are locally confirmed noncredential fixtures; zero are unresolved or potential credentials. The scanner remains unsuppressed and exits 1; the content-addressed exact-set gate exits 0. Independent M0.3c-R8 review is required. M0, M7, T06, F18, and all promotion gates remain open.

## M0.3c-R9 local remediation

R9 validates durable artifacts from one descriptor-bound immutable snapshot and rejects deterministic post-snapshot replacements or writes. The independent oracle derives all execution contexts from pinned Git objects without production semantic catalogs. Fresh reconciliation remains 158 confirmed noncredential fixtures: 83 expected-error contexts and 75 public DER vectors. Independent R10 review remains required; this does not close M0 or any promotion gate.
