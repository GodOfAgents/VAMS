# Semgrep Timeout Adjudication

**Scan date:** 2026-07-13

**Tool:** Semgrep 1.169.0 Community rules

## Gate Result

The configured local gate passed with zero findings. The exact tracked-source
scan evaluated 520 rules over 444 Git-tracked files and the explicit untracked
VDSO supplement evaluated 314 rules over 61 source files. Both exited zero and
reported approximately 99.9% parse coverage.

Semgrep timed out on 17 rule/file pairs. A separate direct source review found
no matching vulnerability in any pair. This is therefore recorded as **pass
with adjudicated timeouts**, not as a timeout-free scan. Exact-commit CI output
and external reviewer acceptance remain required for release evidence.

## Tracked-Source Timeout Review

| File | Timed-out rule | Direct review |
| --- | --- | --- |
| `.github/workflows/security-gates.yml` | `yaml.github-actions.security.curl-eval.curl-eval` | No `curl`, `eval`, `bash -c`, or command-evaluation construct exists. |
| `.github/workflows/security-gates.yml` | `yaml.github-actions.security.run-shell-injection.run-shell-injection` | Event and SHA values were constrained and quoted; the remaining direct GitHub-context interpolation was subsequently moved to step environment variables. |
| `frontend-vite/src/App.jsx` | `javascript.browser.security.eval-detected.eval-detected` | No `eval` or `Function` constructor exists. |
| `frontend-vite/src/App.jsx` | `javascript.express.security.injection.raw-html-format.raw-html-format` | No raw-HTML sink exists; dynamic values use React JSX escaping. |
| `frontend-vite/src/App.jsx` | `javascript.lang.security.audit.unsafe-formatstring.unsafe-formatstring` | No format-string sink exists. |
| `gateway/server.py` | `python.lang.security.audit.insecure-transport.requests.request-with-http.request-with-http` | No outbound `requests` call exists. HTTP literals are loopback CORS defaults and local display text. |
| `gateway/vdso.py` | `python.django.security.injection.sql.sql-injection-using-raw.sql-injection-using-raw` | The module does not use Django, a database cursor, raw SQL, or query execution. `raw` variables are decoded byte buffers. |
| `neuron/neuron.py` | `python.boto3.security.hardcoded-token.hardcoded-token` | No Boto3/AWS credential sink or static credential exists. |
| `neuron/neuron.py` | `python.lang.security.dangerous-system-call.dangerous-system-call` | No subprocess or system-call execution exists. |
| `scripts/audit/audit_program.py` | `python.boto3.security.hardcoded-token.hardcoded-token` | No Boto3/AWS credential sink or static credential exists. |
| `scripts/audit/audit_program.py` | `python.django.security.injection.command.subprocess-injection.subprocess-injection` | No Django exists. The sole Git subprocess uses an argument array, fixed working directory, implicit `shell=False`, and constant-only call sites. |
| `scripts/audit/audit_program.py` | `python.flask.security.injection.subprocess-injection.subprocess-injection` | No Flask request input reaches the constant-only Git subprocess. |

## Supplemental VDSO Timeout Review

| File | Timed-out rule | Direct review |
| --- | --- | --- |
| `gateway/vdso.py` | `python.lang.security.dangerous-system-call.dangerous-system-call` | No system, subprocess, dynamic import, evaluation, or compilation call exists. |
| `neuron/tests/test_vdso_canary.py` | `python.boto3.security.hardcoded-token.hardcoded-token` | No Boto3/AWS credential sink or literal exists. |
| `neuron/tests/test_vdso_canary.py` | `python.flask.security.injection.nan-injection.nan-injection` | No NaN/Infinity construction, parsing, or serialization override exists. |
| `scripts/audit/runtime_privacy_evidence.py` | `python.boto3.security.hardcoded-token.hardcoded-token` | No Boto3/AWS credential sink or literal exists. |
| `scripts/audit/runtime_privacy_evidence.py` | `python.flask.security.injection.nan-injection.nan-injection` | No NaN/Infinity construction, parsing, or serialization override exists. |
| `scripts/docs/validate_vdso_evidence.py` | `python.boto3.security.hardcoded-token.hardcoded-token` | No Boto3/AWS credential sink or literal exists. |

## Release Evidence Requirement

Retain the raw exact-commit Semgrep output, this adjudication, and the source
revision together. Re-run the workflow after the post-scan workflow hardening.
Any new timeout, finding, source change in an adjudicated path, or reviewer
rejection invalidates this local adjudication and must fail the promotion gate.
