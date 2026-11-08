# M7/T05 workflow permission source review — 2026-10-18

Status: **source-only review for independent DevSecOps assessment; no T05/G1 acceptance is claimed.**

## Bound inputs

| Input | SHA-256 |
|---|---|
| `.github/workflows/security-gates.yml` | `252034dd4634228c5203db0c0a450628e875c57772e3393cca0e33043ae6a210` |
| `scripts/audit/validate_workflow_security.py` | `053b8f26e1e82b36845a9625ad47e86a918aa52156985cfb2556cb7e95ab5cbf` |
| `docs/audit/AUDIT_PROGRAM.md` | `75dd1c14c2852ad964d4b70d9905980dcbf7b98f27e10d3cfa11668b085f1784` |
| `docs/audit/testnet-profile.json` | `67136081adf06054b9385db7fe94987744529ed5a5f221ffb6ada0f5057153db` |

## Static observations

- The workflow triggers on `workflow_dispatch`, pushes to `main`, and pull requests targeting `main` (`security-gates.yml:3-17`). Its top-level token permission is `contents: read` (`:19-20`).
- `sbom-generation` runs for non-docs-only pull requests as well as non-PR events and grants `id-token: write` to sign and upload an SBOM (`:648-688`). `security-evidence-gate` has `if: always()`, also grants `id-token: write`, signs the aggregate gate manifest, and enforces upstream job outcomes afterward (`:690-802`).
- The manual readiness job verifies the aggregate signature with a certificate identity regexp ending in `@refs/.+`; the public-stage canary signature check also accepts `@refs/.+` (`:804-837`). The YAML therefore does not itself restrict these certificate identities to a protected branch.
- `validate_workflow_security.py` checks immutable 40-hex action pins, required action commits, and selected tool/workflow controls (`:147-175` and later checks). It contains no assertions for job-level permissions, OIDC-signing event/ref conditions, or Cosign certificate ref scope. This is a validator coverage observation, not proof that the workflow is exploitable.
- The current profile is faucet-only, with staking rewards, real fiat, yield capital, and VDSO disabled. G1 requires final-tree execution and G0/G4 evidence; repository-local YAML alone cannot prove hosted branch protection, OIDC issuer policy, or a completed signed run.

## Review question and remaining evidence

DevSecOps and an independent workflow reviewer should determine whether signing SBOM/aggregate evidence from non-docs pull-request refs and accepting any `refs/` identity in the readiness verifier is consistent with the repository's protected-branch policy. The repository contains no current branch-protection export or hosted-run evidence establishing that policy. This review does not assert that a credential was exposed or that a malicious signature was accepted.

T05 remains `partial`; G1 remains unproven on the exact final tree. Required evidence still includes the protected-branch/ruleset export, confirmation of the intended OIDC signing and verifier identity boundary, and successful required jobs bound to the same final commit. If the policy needs tightening, make that change only in a separately reviewed workflow slice with regression coverage and exact-commit CI evidence.

No workflow, source, test, or profile bytes were changed. No CI job, validator, test, Aiken command, network request, or signing operation was run. This document is not an independent review and changes no finding, track, invariant, owner decision, or readiness status.
