# M7 local Python audit provenance and dependency scope

State: READ-ONLY ASSESSMENT; independent review PASS. No package, source, workflow, or runtime change is authorized or made by this record.

## Inputs and identity

Canonical checkout HEAD: 829ab544571f12efe50ecb5740f129c8acb3e16f; branch testnet/remediation-20260907.
neuron/requirements.txt SHA-256: a7563450beb54994461ebc0057ff4da02c9754c2b1dcf7690c533b84cb75734d.
gateway/requirements.txt SHA-256: c442d01c246812c909fd28f6cf90c14c5e17921597d409c0492fbbf808e0f0b3.
.github/workflows/security-gates.yml SHA-256: baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c (working-tree identity; this file is already dirty relative to HEAD).
The audited runtime is the existing pinned Python 3.12.14 environment at /home/GodOfAgents/vams-evidence/toolchains/vams-py312; pip-audit is 2.10.1, binary SHA-256 310dabedfa526a73c82ac3e0f80a8af761aa3ebf2ef4026c49d06352e7691b95.

## Findings and scope

The separately accepted requirements-file audit for neuron/requirements.txt passed with no known vulnerabilities. The local installed-environment audit pip-audit --local --vulnerability-service pypi exited 1 with 13 advisory rows across anyio 4.14.1, httpcore2 2.5.0, httpx2 2.5.0, pip 26.1.2, and urllib3 2.7.0. Exact sanitized combined output and its reproduction are recorded in docs/remediation/m7_pip_audit_local_r1_20261006/; output SHA-256 36d265a3940f713f02ca68973ca90f0c663212d79a193c90bb6de6d090936a24. The duplicate pip advisory row is retained. Severity, exploitability, and runtime reachability are not assigned.

Read-only pip show places all five distributions in the local verification environment. Reverse dependencies reported there: urllib3 -> requests; anyio -> installed httpx, httpx2, and starlette; httpcore2 -> httpx2; pip -> pip-api. The independent source review confirmed first-party code directly imports requests and FastAPI, while Starlette appears transitively through FastAPI; it found no direct imports of the five audited package names. Neither neuron/requirements.txt nor gateway/requirements.txt directly declares those five names; requests and FastAPI are direct project dependencies.

The checked-in workflow explicitly installs pip 26.2, anyio 4.14.1, httpx2 2.12.0, and pip-audit 2.10.1, then installs gateway and neuron requirements and runs both requirements-file audits plus pip-audit --local --vulnerability-service pypi. The anyio pin matches the locally scanned version, which has three reported advisory rows. Therefore the configured local-environment CI audit is expected to remain blocked unless a reviewed dependency/workflow resolution changes; no hosted CI run was performed. Local httpx2 2.5.0 and pip 26.1.2 differ from workflow pins. This record does not claim exact hosted resolver output, a hosted CI failure, or a deployed-runtime vulnerability.

## Reproduction and raw capture hashes

Read-only capture: Python pip show for the five distributions; repository-wide neuron and gateway Python import search for anyio|httpcore2|httpx2|urllib3; direct requirement search for the same package names; and workflow lines 466-480. Files are outside the checkout at /home/GodOfAgents/vams-evidence/m7-pip-audit-local-provenance-r1-20261006/:

- pip-show.txt: 01fd59a6611d7619c782634e5fb3604e39765f74f33064d06f521a84ca76aa0c
- first-party-import-search.txt: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (zero matches)
- direct-requirement-search.txt: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 (zero matches)
- workflow-audit-install.txt: c62914dd2328c5025001dcc38c4a9e0f6a2fff176c6d945256b20df483755bdc

Independent review: PASS. Reviewer verified the raw capture hashes and independently inspected current requirements, workflow pins, package metadata, and first-party imports. Review limitations: empty search captures do not bind command metadata; review supplied its own independent source search. No severity/exploitability conclusion.

## Decision boundary

This is a bounded assessment of the local verification-environment failure and its reverse-dependency scope. It does not establish deployed runtime exposure, hosted CI execution, or absence of transitive exposure. No dependency refresh, installation, hosted run, or runtime restriction change occurred. Any package/toolchain version change requires separate owner authorization. M7 and readiness remain open; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
