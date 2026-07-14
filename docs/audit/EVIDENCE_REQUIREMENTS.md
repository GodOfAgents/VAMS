# VAMS Green-Signal Evidence Requirements

No evidence file should be created with invented addresses, receipts, reviewers,
timestamps, or approvals. Missing evidence remains missing and readiness fails.

## Repository Evidence Contract

All evidence belongs in one immutable stage-evidence bundle and must reference
the exact 40-character release commit. Operational evidence must not be
committed into that same target SHA: doing so creates a self-referential commit
claim. The regular CI run therefore emits only raw build/security evidence and
static policy inventory. A separate post-freeze `workflow_dispatch` ceremony
must upload `operational-evidence-bundle` from the frozen target SHA.
That producer is `.github/workflows/operational-evidence.yml`. It runs only on
the protected `testnet-operational-evidence` environment and a dedicated
`vams-testnet-evidence` self-hosted runner. The runner imports an immutable
snapshot from `/var/lib/vams/operational-evidence/<target-sha>/<stage>`, rejects
symlinks, secret material, and aggregate manifests, and runs the operational
bundle validator before upload. Repository CI never manufactures operational
observations or reviewer approvals.
Promotion is another `workflow_dispatch` run whose required inputs are the
target SHA, the numeric CI stage-evidence run ID, and a distinct numeric
operational-evidence run ID. The promotion workflow verifies both immutable
first-attempt runs completed successfully for the same SHA, verifies the
operational run came from a separate dispatched workflow, downloads both named
bundles, merges operational evidence, and only then creates and signs
`audit-evidence.json`. The signed manifest binds both run IDs.
Re-run attempts are rejected (`run_attempt` must equal `1`) so a numeric run ID
cannot silently resolve to evidence from a later attempt. The bundle mirrors
repository evidence paths under `docs/audit/`; nested evidence directories are
copied recursively, not flattened. This preserves the path and hash contract
used by runtime, privacy, assurance, and deployment validators.

Every required gate executes through the repository `run-gate` runner and
uploads its own `raw-gate-<name>` artifact. Under
`raw-gates/raw-gate-<name>/`, `gate.json` binds the exact command actually
executed, exit status, target SHA, prior run ID, fixed seed `20260713`, and a
SHA-256 for every raw transcript or scanner report. The aggregate validator
rejects missing, undeclared, empty, tampered, or command-substituted files; a
central job cannot synthesize a result-only receipt. The version `2.0.0`
aggregate manifest records a non-null SHA-256 for every `gate.json`, every raw
output, and every file in the downloaded bundle. Its canonical
`bundle_sha256` is calculated before signing. Missing, empty, failed, skipped,
unbound, or extra bundle files fail promotion. The aggregate manifest,
signature, and certificate stay outside the bound bundle, so a manifest can
never hash itself.

`assurance-index.json` maps every applicable track to one or more evidence
artifacts and SHA-256 hashes. Readiness consumes the downloaded bundle, verifies
its exact file set against the signed manifest, and checks that the manifest,
deployment records, runtime reports, and requested checkout all use the target
SHA and prior stage-evidence run ID.

Every readiness-critical nested deployment claim uses a bundle-relative path
and SHA-256 pair. The validator resolves the path inside the downloaded bundle,
rejects traversal and symlinks, recomputes the file hash, and for structured
observations verifies canonical content against the declared network, commit,
artifact, authority, role, transfer, privilege, VDSO state, or conformance
record. This applies to canonical artifact files, runtime/chain observations,
Cardano CBOR, Safe and script identities, timelock roles/control, role/control
transfers, deployer privilege checks, all seven VDSO module states, and Cardano
VDSO conformance. An arbitrary 64-hex placeholder cannot satisfy readiness.

The complete Git history and all fetched remote heads/tags must also pass
Gitleaks and TruffleHog. Gitleaks uses literal `--all`, 100% report redaction,
and a non-zero exit for every finding. TruffleHog scans Git history with
`--results=verified,unknown,unverified`; any emitted finding blocks the gate.
Its raw JSON is held outside the artifact tree, transformed fail-closed into a
strict sanitized report, and deleted. The persisted report retains detector,
verified status, commit, path, line, category counts, exact command, exit
status, commit SHA, and run binding, but rejects `Raw`, `RawV2`, credential,
token, secret, password, private-key, and related material. The blocking
historical private-key findings recorded in `docs/audit/GITLEAKS_ADJUDICATION.md`
require credential rotation, role-impact review, coordinated history cleanup,
and a clean rescan; an unconditional baseline is not acceptable evidence.

## Canary Inputs

| File | Required contents |
| --- | --- |
| `audit-evidence.json/.sig/.pem` | Successful exact-commit gates and valid Cosign identity |
| `assurance-index.json` | G0-G4 tracks verified, owner reviewer, zero blocking findings, artifact hashes |
| `polygon-amoy-rehearsal.json` | 3-of-5 governance/treasury, separate 2-of-3 emergency, distinct 2-of-3 VDSO guardian/quarantine and VDSO recovery Safe proxies, 48-hour delay, role-removal and rollback evidence |
| `cardano-preprod-rehearsal.json` | Equivalent multisig/timelock parameters, validator artifacts, rollback evidence |
| `runtime-integration.json` | External Gateway checks, real Celestia/Near submission and retrieval receipts, excluded mock/incomplete routes |
| `privacy-review.json` | Approved inventory, retention, redaction, publisher coverage, public-content review, zero blockers |

The Polygon manifest uses deployment-manifest schema version `2.0.0` and must
contain all seven VDSO modules: `VAMSObjectStore`, `VAMSProgramRegistry`,
`VAMSAdapterRegistry`, `VAMSProofRouter`, `VAMSReservationManager`,
`VAMSExecutionKernel`, and `VAMSCapabilityRouter`. Each module must have a
distinct rehearsed/deployed address, zero active entries, `empty=true`,
`paused=true`, and bound state-evidence SHA-256. All seven modules must remain
paused; the aggregate VDSO state must
remain `mode=off`, non-authoritative, and value-free for both canary and public
readiness. It must also prove `kernel_paused=true`,
`recovery_verifier_configured=false`, `execution_routes_enabled=false`, and
zero active domains, adapters, programs, verifiers, and routes. Polygon also
requires five distinct, code-identified Safe proxies: governance, treasury,
emergency pause, VDSO guardian/quarantine, and VDSO recovery. Guardian and
recovery authorities must be distinct from every other authority and from each
other; arbitrary EOAs or shared proxy addresses fail readiness.

Cardano VDSO evidence is conformance-only. The manifest must bind
`cardano/lib/vams/vdso.ak` and its conformance evidence, set `deployable=false`,
and must not list that library as a deployed validator artifact. A future
transaction validator requires a new reviewed schema and deployment ceremony.

`runtime-integration.json` uses schema version `2.0.0`. Every Gateway check
must bind a non-empty repository evidence artifact and SHA-256 digest. The file
must contain exactly one Celestia Mocha and one Near Testnet receipt, distinct
submitter and retrieval-observer identities, `mock_mode=false`, provider-native
inclusion references, and retrieved payload bytes whose artifact SHA-256 equals
the submitted payload SHA-256. Current VDSO Celestia/Near adapters, Avail,
EigenDA, and every mock/incomplete integration remain listed in
`excluded_live_routes`.

`privacy-review.json` also uses schema version `2.0.0`. Boolean approvals alone
are invalid: a named human reviewer and organization must bind separate data
inventory, retention, redaction-test, public-content, and publisher-inventory
artifacts. `docs/audit/privacy-publisher-inventory.json` is checked against
publisher symbols discovered from the DA, Sentinel, and VDSO source trees so a
new sink cannot bypass review by omission.

## Public Inputs

Public promotion replaces rehearsal manifests with deployed manifests and adds:

| File | Required contents |
| --- | --- |
| `closed-canary-report.json/.sig/.pem` | Schema v1.0.0; timezone-aware non-future interval of at least seven days; at least seven exact, gap-free UTC daily records with path/hash evidence; no stop condition; all seven drills passed with distinct path/hash evidence; non-empty metric artifacts bound by path/hash |
| `vdso-shadow-report.json` | Schema v1.0.0; public VDSO mode off while a separate private worker runs in shadow mode; source- and artifact-bound Python/Rust/Aiken implementation roots; at least 1 × 10^5 transitions and 604800 measured seconds; 100 or more fixed 1000-transition checkpoints; every enumerated stop condition false; zero divergence, external writes, and plaintext payloads; privacy result, restart recovery, replay determinism, and continuity passed; read-only, non-authoritative, value-free operation |
| `vdso-shadow-input.jsonl` | Append-only commitment-only input source; exact v1 fields, contiguous uint64 sequence, nonzero cursor and input commitments, canonical record hashes, no plaintext or extra fields, and no trailing unconsumed records |
| `vdso-shadow-audit.jsonl` | Canonical UTF-8 JSONL v1; hash-chained run, fixed 1000-transition chunk, and summary records; exact commit, seed, source-root, timestamp, sequence, state-root, backend-count, transcript-root, restart, replay, privacy, and stop-condition bindings |
| `independent-reviews.json` | Approved Solidity, Aiken, economics, Gateway/SDK, privacy, and AI-safety reports with zero blockers |
| `polygon-amoy-deployment.json` | Verified addresses, transactions, bytecode, owners, thresholds, role transfers, rollback |
| `cardano-preprod-deployment.json` | Script hashes, transactions, multisig ownership, parameters, rollback |

Every `Pending` field in `contracts/CONTRACTS.md` must be replaced with verified
facts before public promotion. The 14-day public soak is a post-onboarding gate
for incentives or increased exposure, not permission to bypass the seven-day
closed canary.

`vdso-shadow-report.json` is not a deployment claim. `public_vdso_mode=off`
keeps the committed public profile disabled while `worker_mode=shadow`
describes the separate private read-only comparison worker. The report must
bind the exact declared source paths (`neuron/vdso`, `vams-vm/crates`, and
`cardano/lib/vams/vdso.ak`), the canonical source-tree SHA-256 for each, and a
separate implementation-root artifact whose content and hash bind the same
commit and source root. Arbitrary 64-hex strings are not implementation-root
evidence. The required `vdso-shadow-audit.jsonl` artifact is canonical compact
JSON (sorted keys, one LF-terminated UTF-8 object per line) and forms an
unbroken SHA-256 record chain. Its run header copies the complete implementation
root object from the report and binds `vdso-shadow-input.jsonl` under the
`vdso-shadow-input-v1` contract. The input artifact is independently replayed
through exactly the reported transition count: records permit only sequence,
cursor commitment, input commitment, previous-record hash, and record hash
fields; sequences and source hashes must be gap-free and duplicate-free; and
the final file digest must match both the report and evidence-artifact record.
Each zero-based chunk contains exactly 1000
contiguous transitions, continuous start/end roots, equal Python/Rust/Aiken
transcript roots, backend evaluation counts of 1000, and UTC timestamps whose
internal and cross-chunk gaps do not exceed the configured limit. Each chunk
also binds its first and last source cursors and source-chain checkpoint to the
corresponding 1000 durable input records. At least 100
chunks and 604800 observed seconds are required. The final summary must equal
the recomputed chunk totals and final roots, record at least one restart and one
replay verification, and its record digest must equal the report's
`audit_chain_root_sha256`.

The report must record `privacy_result=pass`,
`stop_conditions_triggered=false`, and an exact `stop_conditions` object with
`transition_divergence`, `external_write`, `plaintext_payload`,
`restart_failure`, `replay_mismatch`, `privacy_failure`,
`public_mode_enabled`, `authoritative_enabled`, `value_bearing_enabled`,
`continuity_gap`, and `backend_unavailable` all set to `false`. Its evidence
records must be non-empty files under the
report directory with matching SHA-256 values, and the report cannot cite
itself. Any transition divergence, attempted external write, plaintext payload
observation, restart failure, replay mismatch, authoritative public mode, a
non-shadow worker, value-bearing domain, or fewer than `1 × 10^5` transitions
over seven full days is a hard public-readiness failure.
