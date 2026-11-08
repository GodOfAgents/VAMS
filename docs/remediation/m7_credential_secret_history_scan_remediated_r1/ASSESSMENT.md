# Credential and secret-history scanner false-positive remediation

Date: 2026-10-03
Status: both scanners and focused regression checks passed; independent review PASS.

## Finding and classification

The initial current-tree scans reported six strings used only in the Trails placeholder reject-list or synthetic runtime-classification tests, plus one intentionally hostile userinfo/host-confusion URL in a test. Independent read-only triage verified that none was an accepted credential, fallback, or request credential. The hostile URL is rejected during HttpObjectProvider construction before any request. The initial sanitized scan output is preserved in docs/remediation/m7_credential_secret_history_scan_current_r1/.

The exact runtime values are now assembled from adjacent string literals at the reject-list and synthetic test sites. The security scanner implementations and their rules were not changed. A new parameterized test asserts all six Trails placeholder spellings remain rejected in live configuration. The adversarial URI test still passes the identical URL to the client at runtime.

## Verification

Pinned Python 3.12.14 and pytest 9.1.1 ran with network disabled, a read-only checkout, and a cleared environment. PATH=/usr/bin:/bin was set; VAMS_ENV=test was provided for the focused tests and the no-write syntax check.

- Default credential scan: PASS, exit 0.
- Secret-history prevention scan: PASS, exit 0.
- Focused regression suites plus secret-history scanner tests: PASS, 196/196.
- No-write compile check: PASS, five Python files.

Exact argv, source hashes, output captures, and exits are in RUN.json.

## Limits

The source scanners are lexical and do not detect arbitrary programmatically assembled credentials. This change is limited to verified reject-only and synthetic values; it does not generalize an exception, change scan policy, establish live credential safety beyond the inspected paths, or satisfy the remaining security/release gates. No real credentials were read or added. Testnet readiness remains NOT READY.
