# M7 local installed-environment dependency audit

Gate result: FAIL for the scanned local Python 3.12.14 environment. This does not establish hosted CI state or application-runtime exploitability.

Canonical checkout: HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`.

Exact workflow command, executed with the existing pinned scanner:
`/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pip-audit --local --vulnerability-service pypi`

Observed exit code: 1. The scanner reported 13 advisory rows across five installed packages:

| Package | Installed | Advisory | Reported fix |
|---|---:|---|---|
| anyio | 4.14.1 | PYSEC-2026-4025 | 4.14.2 |
| anyio | 4.14.1 | PYSEC-2026-4023 | 4.14.2 |
| anyio | 4.14.1 | PYSEC-2026-4024 | 4.14.2 |
| httpcore2 | 2.5.0 | PYSEC-2026-3844 | 2.10.0 |
| httpx2 | 2.5.0 | PYSEC-2026-3849 | 2.11.0 |
| httpx2 | 2.5.0 | PYSEC-2026-3847 | 2.10.0 |
| httpx2 | 2.5.0 | PYSEC-2026-3848 | 2.11.0 |
| httpx2 | 2.5.0 | PYSEC-2026-3846 | 2.12.0 |
| pip | 26.1.2 | PYSEC-2026-3721 | 26.2 |
| pip | 26.1.2 | PYSEC-2026-3721 | 26.2.0 |
| urllib3 | 2.7.0 | PYSEC-2026-4177 | 2.8.0 |
| urllib3 | 2.7.0 | PYSEC-2026-4176 | 2.8.0 |
| urllib3 | 2.7.0 | PYSEC-2026-4175 | 2.8.0 |

The duplicate `pip` row is preserved as reported; the review did not infer whether either row is redundant. This output contains no severity or exploitability classification.

Source/tool binding:

- `neuron/requirements.txt`: SHA-256 `a7563450beb54994461ebc0057ff4da02c9754c2b1dcf7690c533b84cb75734d`.
- `.github/workflows/security-gates.yml`: SHA-256 `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`; this file is dirty versus HEAD and was not changed by this audit.
- Scanner: pip-audit 2.10.1, SHA-256 `310dabedfa526a73c82ac3e0f80a8af761aa3ebf2ef4026c49d06352e7691b95`.
- Python: 3.12.14.
- `pip freeze --all` digest before and after: `0ecca1d565d56c913370c34e8a2559cd7b30bebe188059b7054c112ae615837d`; unchanged.

Raw combined output is retained outside the checkout at `/home/GodOfAgents/vams-evidence/m7-pip-audit-local-r1-20261006/pip-audit-local.combined.log`, SHA-256 `36d265a3940f713f02ca68973ca90f0c663212d79a193c90bb6de6d090936a24`.

An independent reviewer reran the exact command in canonical WSL, reproduced exit 1 and the same 13 rows byte-for-byte, verified source/tool hashes, and confirmed the package inventory digest stayed unchanged. The local environment scan does not replace the separate requirements-file audit, hosted CI, or supply-chain gates.

No dependency or source file was changed. The scan is a current local-toolchain finding record, not proof that each package is reachable in a deployed runtime. No severity or exploitability claim is made.
