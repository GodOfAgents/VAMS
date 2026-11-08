# M7 neuron requirements dependency audit

Result: PASS for the current `neuron/requirements.txt` dependency resolution only. This is not installed-environment, hosted-CI, or full supply-chain evidence.

Canonical tree at run: HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`.

Input and tool binding:

- `neuron/requirements.txt`: SHA-256 `a7563450beb54994461ebc0057ff4da02c9754c2b1dcf7690c533b84cb75734d`.
- `.github/workflows/security-gates.yml`: SHA-256 `baf53503673b70c5185f654f8f694f1feaf98af68ee56e29c83c01ee0cf0593c`.
- Existing scanner: `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pip-audit`, version 2.10.1, SHA-256 `310dabedfa526a73c82ac3e0f80a8af761aa3ebf2ef4026c49d06352e7691b95`.

Exact command: `/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/pip-audit -r neuron/requirements.txt`.

The root run exited 0 and reported `No known vulnerabilities found`. The combined output from the retained run is outside the checkout at `/home/GodOfAgents/vams-evidence/m7-pip-audit-neuron-r1-20261006/pip-audit.stdout`, SHA-256 `15950a68a7ed99c59779717acefdceb3f69cfd31bde67d2c954f2a3cea4d7955`. It was captured with stderr redirected to stdout.

An independent reviewer reran the exact command in canonical WSL. It exited 0, with `No known vulnerabilities found` emitted to stderr and empty stdout. The reviewer checked the requirements, workflow, and scanner hashes immediately before and after; all remained unchanged. Reviewer stdout SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The workflow lists this requirements-file audit separately from `pip-audit --local`. An earlier installed-environment scan reported 13 advisory rows across five packages; that result is separate and is not cleared by this PASS. Requirements-file resolution may query package-index metadata. No tool or persistent dependency installation, source change, requirements change, credential change, or vendor change was made in this slice.
