# M7 local pip-audit requirements scan

## Result

Pinned pip-audit 2.10.1 completed successfully against both current Python requirement sets. The resolved audit reported 62 dependencies for `neuron/requirements.txt` and 17 for `gateway/requirements.txt`, with zero vulnerabilities in each report. The only raw output was held in process memory, hashed, and discarded; retained records contain package/version/advisory metadata only, and the vulnerability lists are empty.

## Verification and scope

See [RUN.json](RUN.json) for exact commands, workflow/tool/requirements hashes, exit codes, dependency counts, and output hashes. [RESULT.json](RESULT.json) is the sanitized result. The workflow's `pip-audit --local --vulnerability-service pypi` command was not run because this pinned local Python environment is not the workflow environment populated with VAMS dependencies. CI parity and the broader dependency gate therefore remain unverified.

The commands queried PyPI vulnerability and package metadata. No package or tool was installed; the temporary cache path was under `/tmp`.

## Readiness impact

This closes only these two local requirements-file audits for the captured dirty checkout. It does not close Gitleaks, CI/local-environment auditing, other scanners, dependency-policy review, or any contract, validator, governance, testnet-rehearsal, or T06/history gate. No application source, credentials, vendor files, or Git history changed.
