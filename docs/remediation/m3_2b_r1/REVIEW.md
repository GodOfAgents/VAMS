# M3.2b-R1 frozen governor/timelock implementation

Date: 2026-09-28
Scope: Cardano governance/timelock implementation only.

## Baseline and prerequisite

The accepted M3.2a-R22 package was verified before editing:
'/home/GodOfAgents/vams-evidence/m3-2a-r22-review-20260927-829ab544571f'
with SHA256SUMS digest
'35e89e15e545b33ecabd87cb320e93943e42ef8a66e3180102e242f556dfa1ac'.
The repository origin, branch, HEAD and pre-existing dirty paths were preserved.

The frozen R7 JSON files under docs/remediation/m3_2a_r7/ were not modified.
Their reviewed hashes remain recorded in the external evidence package.

## Implementation

Added the frozen versioned governance data types and bounded helper module:

- cardano/lib/vams/types.ak
- cardano/lib/vams/governance.ak
- cardano/validators/governor.ak
- cardano/validators/timelock.ak
- cardano/validators/governance_policies.ak

The implementation binds deterministic authority, proposal, receipt and intent
asset names to the R7 preimages, enforces bounded transaction shape and finite
validity intervals, validates 3-of-5 configured authority signatures for
timelock cancellation, keeps authority counters immutable except for one
typed counter transition, and rejects ExecuteIntent before F05.

cardano/plutus.json was regenerated with pinned Aiken 1.1.21 and now exposes
the named policy and validator entrypoints. The lockfile was already dirty at the accepted baseline; the pinned compiler refreshed only its cache etag timestamps during local verification. No dependency identity, credential, vendor, deployment or Git-history change was made intentionally.

## Verification

- Pinned Aiken 1.1.21 aiken check --skip-tests: PASS, 0 errors.
- Full pinned aiken check --seed 424242: PASS, exit 0, existing scenarios
  completed; the command output was retained in the external package.
- Pinned aiken build: PASS and regenerated cardano/plutus.json.
- aiken fmt --check for the five scoped Aiken files: PASS.
- Frozen R7 governance specification via standard-library unittest:
  python3 -m unittest -q docs/remediation/m3_2a_r7/test_governance_spec.py
 +?u????T 12 tests passed.
- scripts/remediation/test_m3_2b_public_validator.py: structural blueprint,
  81-row matrix and four asset-vector checks PASS.
- Existing R9 provenance suite: two runs remain RED because its accepted
  manifest hashes intentionally predate this Cardano source change; no
  provenance model was altered.
- scripts/remediation/test_m3_2b_mutations.py: frozen mutation inventory,
  nine-transition topology and pre-F05 Execute rejection checks PASS.
- The public harness intentionally reports 36 public_handler rows as
  evaluator_pending: this repository does not yet contain a qualified
  transaction evaluator or executable public-handler fixtures. It therefore
  does not claim the required 81-case on-chain acceptance matrix. Source review
  also leaves the public CreateProposal handler layer absent and does not yet
  prove every frozen value/refund/topology conservation row at a compiled
  transaction boundary. These are explicit follow-up blockers, not suppressed
  failures.

## Boundary and status

This is implementation work, not independent acceptance. F01-F05 remain open,
Deposit and Execute remain disabled pending F05, M3 remains OPEN, Pre-Prod
admission is INCONCLUSIVE, and promotion is NOT READY. M3.2b-R1 must receive
an independent review before any milestone closure.

INV-1 through INV-10, M1/M2 containment and mock-mode behavior are unchanged.

Evidence package: /home/GodOfAgents/vams-evidence/m3-2b-r1-implementation-20260928-829ab544571f/.
