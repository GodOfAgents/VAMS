# Independent review — M7 current-source strict Aiken R2

Date: 2026-10-05
Reviewer: /root/cardano_strict_provenance_review
Result: PASS

## Scope

This is an independent, read-only review of the retained package
`docs/remediation/m7_aiken_strict_current_r2_20261005/` in the canonical WSL
checkout `/home/GodOfAgents/code/VAMS-testnet`. No Aiken test or build was
rerun. No canonical file was edited.

The review checks package checksums, current tool identities, retained result
counts and output hashes, current manifest/blueprint/source-manifest links,
current Git identity and dirty-state corroboration, and the explicit evidence
limits.

## Exact checks and results

1. `sha256sum -c docs/remediation/m7_aiken_strict_current_r2_20261005/SHA256SUMS`
   PASS:
   - ASSESSMENT.md: `eec9898074e47d423e260da0eb7da994f496aa223d1256474eca15250e6a341d`
   - RUN.json: `47399a0c12a7fb559854ba329616a79c570b109753362f2b5b0f85c596147aea`

2. Retained run contract and counts parsed from RUN.json: PASS.
   - command: pinned Aiken `check --deny --seed 20260711 --max-success 250`
   - exit: 0
   - total: 124
   - passed: 124
   - failed: 0
   - unit: 117
   - property: 7
   - max_success: 250
   - stdout SHA-256:
     `7b85975db2d0d0b1a740a0aa85139fafa2706b31c66860495c0d30b8f9f0f07e`
   - stderr SHA-256:
     `6d2bf5a0c258f6248b45f5946a93dc1f474ac563ba3f064ac5a99bb340a851f6`

3. Current pinned tool identities: PASS.
   - Aiken reports `aiken v1.1.21+42babe5`
   - Aiken binary SHA-256:
     `07f3f927f1a8c71fc61273fdff850d9b98edb28dde207c8a32585991f2c88e79`
   - bubblewrap reports `bubblewrap 0.11.1`
   - bubblewrap binary SHA-256:
     `0abea81db798ebf6b4742ac0664802d97521547a353c2a0dbdc21d76cbbfd2c0`
   - retained network boundary: `bwrap --unshare-net`

4. Current manifest and blueprint binding: PASS.
   - `cardano/aiken-dependency-manifest.json` SHA-256:
     `d4bbe77962932359f2d2d8598f7758b84868c9377aba23f96c103baefac7ec93`
   - `cardano/plutus.json` SHA-256:
     `718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492`
   - manifest blueprint digest equals the current blueprint digest.
   - all 16 compilation source entries were checked against current
     `cardano/` files; all sizes and SHA-256 values match, with zero
     mismatches.
   - the 26 retained blueprint program entries are present.
   - source compilation manifest digest:
     `4a896a2df8254afc022207fd8477087106cb4ff242d6d1b753026973afb8f960`.
     It matches the current-forward R11 snapshot record and the R2 RUN.json
     link.

5. Canonical checkout identity and status corroboration: PASS.
   - branch: `testnet/remediation-20260907`
   - HEAD: `829ab544571f12efe50ecb5740f129c8acb3e16f`
   - current porcelain entry count: 150
   - current `git status --porcelain=v1` SHA-256:
     `011f32387bf42fa461a18eaa3b7577f1a1b71c8ab28261a284537f1836edc6e2`
   - this matches the latest current-tree M7 inventory record.
   - RUN.json explicitly records `canonical_inventory_unchanged=true`,
     `canonical_status_unchanged=true`, and `source_unchanged=true`.
   - the current source-entry and manifest digests also match the retained
     current-forward inputs.

6. Status and handoff scope: PASS.
   Current `docs/remediation/STATUS.md` and
   `docs/remediation/SESSION_HANDOFF.md` preserve NOT READY status and keep
   deployment, Deposit, Slash activation, and ExecuteIntent disabled. The
   records keep F05/M3, F04 anchoring, T06/history, M0.4/GitLeaks, remaining
   invariant/security/dependency/reproducibility gates, and chain prerequisites
   open. The strict R2 package is retained evidence pending its acceptance
   append; this review does not alter those records.

## Evidence boundary

The retained run is local current-source validator and provenance evidence
only. Its 124/124 result does not establish Cardano Pre-Prod ledger admission,
paired ledger behavior, live-network behavior, F04 anchor authorization, F05
ledger admission, or deployment readiness. It grants no original-policy,
full-ledger, live-network, or deployment credit by inference. The retained
package explicitly keeps readiness NOT READY and all four deployment/activation
flags false.

The retained stdout and stderr are represented by hashes only; this review
verifies the recorded digests and bindings, not unrecoverable output bytes.
This review did not execute Aiken, bubblewrap, ledger simulation, or network
actions.

## Conclusion

PASS. The strict Aiken package is internally consistent, bound to the current
16-source manifest and blueprint, and uses the recorded pinned Aiken and
bubblewrap identities. Its narrow local provenance scope and all unresolved
readiness gates remain explicit.
