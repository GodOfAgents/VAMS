# M2 frontend CI enforcement remediation review

Date: 2026-09-24  
Scope: M2 frontend CI enforcement only  
Disposition: locally remediated; independent M2-R4 delta review required

## Finding addressed

Independent M2-R3 reported one Medium finding: the mandatory `frontend-gate`
installed dependencies, audited packages, linted, and built the SPA, but it did
not execute the existing frontend telemetry/security tests and did not scan the
resulting production bundle for the reviewed credential patterns. A successful
build therefore did not prove either control had run.

Pre-fix workflow inspection confirmed that `Build Verification` was the final
frontend step. The existing `npm test` command and the prior review's
9-file/7-pattern bundle check were available locally but absent from CI.

## Disposition

The existing frontend job now executes, in mandatory order:

1. `npm ci` using `frontend-vite/package-lock.json`;
2. `npm test` for the `/nodes` telemetry/security disposition;
3. the unchanged npm audit and frontend lint checks;
4. `npm run build`;
5. `npm run scan:bundle` against the resulting `dist` tree.

The bundle scan is a small version-controlled Node script shared by local and
CI verification. Its pattern set is unchanged from the reviewed frontend
disposition: `/nodes`, `GATEWAY_ADMIN_PASSWORD`, `M2_PRIVATE`, `M2_SIGNING`,
`BEGIN PRIVATE KEY`, `VITE_VAMS_ADMIN`, and `VITE_M2`. It scans every regular
bundle file deterministically, rejects symlinks and non-regular entries, and
fails on a missing, non-directory, or empty bundle. It does not print bundle
contents.

The workflow validator structurally identifies the `frontend-gate` and its
named steps. It requires exactly one dependency-install, telemetry test,
production build, and bundle-scan command; requires the frontend working
directory; enforces install-before-test-before-build-before-scan ordering; and
rejects step/job `continue-on-error`, conditional security steps, command
fallbacks, removal, and duplication.

## Changed files

- `.github/workflows/security-gates.yml`
- `.gitignore`
- `frontend-vite/package.json`
- `frontend-vite/scripts/scan-production-bundle.mjs`
- `scripts/audit/validate_workflow_security.py`
- `scripts/audit/test_workflow_security.py`
- `docs/CHANGELOG.md`
- `docs/remediation/STATUS.md`
- `docs/remediation/SESSION_HANDOFF.md`
- this review

No Gateway, authentication, replay, ingress, route-policy, telemetry behavior,
INV-5 runtime, dependency-lock, or vendor file changed in this slice.

## Negative mutation evidence

Fresh in-memory copies of the authoritative workflow were mutated without
changing the workflow file. The regression check failed when `npm test` was
removed and separately failed when `npm run scan:bundle` was removed. It also
failed when either command gained `|| true`, when either step gained
`continue-on-error: true` or `if: always()`, when the job gained
`continue-on-error: true`, and when scan/build order was reversed.

## Fresh verification

The canonical checkout has no frontend `node_modules`. No dependency was
installed. Frontend sources were copied to a bounded temporary directory,
junctioned to the existing external dependency cache, exercised with Node
24.19.0/npm 11.17.0, and the temporary directory was removed.

- `npm test`: PASS, 4/4 tests.
- `npm run build`: PASS, 1,712 modules transformed; 9 output files.
- `npm run scan:bundle`: PASS, 9 files and 7 patterns, zero matches.
- `npm run lint`: PASS.
- focused frontend workflow mutations: PASS, 5/5 test methods, including the
  separate control-removal and non-blocking mutations.
- `python3 -m unittest -v scripts.audit.test_workflow_security`: PASS, 17/17.
- `python3 scripts/audit/validate_workflow_security.py`: PASS, all 40 action
  references remain commit-pinned.
- PyYAML parse of `.github/workflows/security-gates.yml`: PASS.
- recursive JSON parse under `docs/remediation`: PASS, 7 files.
- `git diff --check`: PASS.

Final scoped diff inspection found no action-version change attributable to
this slice, no `package-lock.json` change, no generated `dist` artifact, no
new workflow suppression/skip, and no credential or privileged value.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1–INV-4 | Unchanged; no economic or session-key code changed. |
| INV-5 | Unchanged; OMS/CLR runtime and traceability controls were not modified. |
| INV-6–INV-10 | Unchanged; no TEE, oracle, token, reward, or bridge code changed. |

F17, M1 containment, runtime behavior, and mock-mode selection are unchanged.
This slice enforces already-reviewed frontend controls in CI; it does not alter
the frontend `/nodes` disposition itself.

## Remaining blockers

The independent R3 runtime findings remain passing claims and were not reopened
or promoted by this implementation. `F08 = REVALIDATED_OPEN` and `M2 = open`.
The separate T06/history environment issue is unchanged. The next slice is an
independent M2-R4 delta review and F08 closure decision.
