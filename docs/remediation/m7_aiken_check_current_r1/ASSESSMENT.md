# Current Cardano validator gate recheck

## Result

The workflow command aiken check --deny --seed 20260711 --max-success 250 exits 1 on the current Cardano source. Its JSON test summary reports 122/122 scenarios passed, 0 failed (115 unit, 7 property). A diagnostic run without --deny exits 0 with the same 122/122 summary. The pinned CLI documentation states that --deny treats warnings as errors. The exact warning count and text are not asserted because this sanitized pipe capture retained only hashes and no warning lines.

The current manifest declares aiken-lang/stdlib and aiken-lang/fuzz at version v2; the lock records corresponding etags. The failure source therefore remains an open strict-warning/dependency-version gate, not a failed validator scenario. No dependency or vendor files were changed.

## Scope

The current snapshot includes 15 Aiken source files and 6 project inputs, bound by the combined digest in RESULT.json. The canonical cardano tree was read-only; each check ran on a fresh temporary copy. The pinned Aiken 1.1.21 binary was used. No compiler/tool was installed or fetched. Raw stdout/stderr were discarded after hashing and summary parsing.

The repository instruction aiken test is not a supported subcommand in pinned Aiken 1.1.21; aiken test --help reports an unrecognized subcommand. The workflow's aiken check command runs the scenarios and is the gate captured here.

These Aiken unit/property scenarios are test evidence only. They do not add to F05 negative/mutation ledger counts and establish no simulator admission, ledger transaction, or live-network evidence.

## Readiness impact

The workflow Cardano gate remains failed due to strict warning handling. F05 remains at 45/55 negative cases and 18/21 mutations; the current check does not change those counts. Readiness remains NOT READY, and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. Do not silence warnings or change dependency/vendor pins without the appropriate reviewed remediation.
