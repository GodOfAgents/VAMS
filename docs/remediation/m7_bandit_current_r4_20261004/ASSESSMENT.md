# M7 Bandit current-source gate assessment (r4)

Date: 2026-10-04
Disposition: **PASS at configured gate thresholds; one excluded medium/low-confidence candidate remains visible**
Readiness: **NOT READY**

## Scope and exact result

Current workflow command:

`bandit -r neuron/ gateway/ -ll -ii`

Pinned executable: `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/bandit`, Bandit 1.9.4, Python 3.12.14. The captured run used network isolation and a read-only mount of the canonical checkout; full command record is in `EVIDENCE-REFS.md`.

Result: exit 0; stdout says `No issues identified.` No scanner error was recorded. The source manifest covers 190 unique Python files under `neuron/` and `gateway/`, 37,142 LOC; before/after inventory digests match. The workflow hash and scanner executable hash match the current artifacts.

The unfiltered output metrics show one medium-severity, low-confidence issue, which is below the configured `-ii` confidence threshold. This is not zero total issues and is not an adjudication of the candidate. Aggregate metrics: 1,488 Low, 1 Medium, 0 High severity; 1 Low, 12 Medium, 1,476 High confidence; 2 specifically disabled checks; 0 files skipped.

## Independent review

Independent review **PASS** for the retained capture and evidence classification. Exact capture hashes and the reviewer 's provenance caveat are in `REVIEW.md`. The wrapper and metadata are capture records, not separate process telemetry; classify this as local static-analysis evidence, not independently attested sandbox execution.

## Invariant and readiness impact

No source or test file changed. This scan does not prove invariant behavior, complete security posture, or deployment readiness. Other security gates, current-tree findings, supply-chain checks, T06/history, F04/F05 decisions, and chain prerequisites remain open. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: run installed pip-audit 2.10.1 with the workflow command `pip-audit --local --vulnerability-service pypi`, without installing dependencies. If its advisory service is unavailable, record the gate as blocked.
