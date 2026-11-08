# M2R4-01 closed frontend command-contract remediation

Date: 2026-09-24  
Scope: workflow validator and its regressions only  
Disposition: locally remediated; independent M2-R5 focused delta review required

## Reproduction

Before the fix, two valid temporary workflow copies changed the protected test
or scan step to:

```text
set +e
<required npm command>
true
```

`validate_workflow_text` returned zero errors for both `npm test` and
`npm run scan:bundle`. The authoritative workflow was not modified during the
reproduction, and the temporary directories were removed automatically.

## Root cause and repair

The validator previously searched named step blocks for one exact command line
while allowing arbitrary additional shell lines. The required command could
therefore remain present while `set +e` and a terminal success command replaced
its exit status.

The frontend control is now a closed structural contract. Each of the four
reviewed steps—dependency install, telemetry/security test, production build,
and production-bundle scan—must have:

- exactly one canonical step name;
- only the `run` step property;
- the normalized exact two-line body `cd frontend-vite` followed by its one
  approved npm command;
- exactly one occurrence of that command across frontend steps; and
- the reviewed install → test → build → scan ordering.

This rejects extra commands, prefixes, suffixes, error-mode changes, alternate
success, command substitution, additional step properties, duplicates,
conditions, and `continue-on-error`. The known-good workflow already matched
the contract and was not changed.

## Regression coverage

Workflow mutations are written to auto-removed temporary copies and evaluated
through the public `validate_workflow_text` result. New cases reject:

1. `set +e`, `npm test`, terminal `true`;
2. `set +e`, `npm run scan:bundle`, terminal `true`;
3. terminal `true` after `npm test`;
4. terminal `true` after `npm run scan:bundle`.

Existing removal, `|| true`, condition, step/job `continue-on-error`, duplicate,
and ordering cases remain. The ordering fixture now moves intact canonical
steps so body validation and ordering are tested independently.

## Changed files

- `scripts/audit/validate_workflow_security.py`
- `scripts/audit/test_workflow_security.py`
- `docs/CHANGELOG.md`
- `docs/remediation/STATUS.md`
- `docs/remediation/SESSION_HANDOFF.md`
- this review

`.github/workflows/security-gates.yml`, frontend source/configuration,
`package-lock.json`, Gateway runtime/auth/replay/route code, Envoy, INV-5 code,
dependencies, vendors, credentials, and action pins were not changed.

## Fresh verification

- pre-fix temporary reproduction: both `set +e`/terminal-success variants were
  accepted with zero errors.
- focused frontend workflow regressions: PASS, 7/7 test methods.
- complete workflow-security suite: PASS, 19/19.
- authoritative validator: PASS; all 40 actions remain commit-pinned.
- four independent post-fix temporary mutations: REJECTED, one error each.
- authoritative workflow through public validator: PASS, zero errors.
- workflow YAML parse: PASS.
- frontend telemetry/security tests: PASS, 4/4.
- production frontend build: PASS, 1,712 modules and 9 output files.
- production-bundle scan: PASS, 9 files / 7 patterns / zero matches.
- remediation JSON parse: PASS, 7 files.
- `git diff --check`: PASS.
- no `package-lock.json` or repository `dist` status change.

No dependencies were installed. Frontend verification used an existing
external dependency cache through a bounded temporary copy that was removed.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1–INV-4 | Unchanged; no economic or session-key surface changed. |
| INV-5 | Unchanged; CLR/OMS runtime and traceability controls were untouched. |
| INV-6–INV-10 | Unchanged; no TEE, oracle, supply, reward, or bridge surface changed. |

F17, M1 containment, Gateway behavior, frontend `/nodes`, and mock-mode
behavior are unchanged. This is local implementation evidence, not independent
acceptance. Keep `F08 = REVALIDATED_OPEN` and `M2 = open`. T06/history remains
outside scope. Next: independent M2-R5 focused delta review and F08 closure
decision.
