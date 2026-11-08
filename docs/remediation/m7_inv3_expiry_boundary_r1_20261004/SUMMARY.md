# INV-3 session expiry boundary remediation

The session-key verifier now rejects a key when the current timestamp equals or exceeds expires_at. The validity interval is half-open, preserving the 24-hour maximum while excluding the expiration instant.

The new deterministic regression froze the verifier clock at the session's exact expires_at. Before the fix it failed because the verifier returned true. After the one-comparison correction, the focused wallet module passed 10/10. The current offline Python workflow split passed 1,700/1,700 main tests and 10/10 design tests.

Independent review passed the exact source/test behavior and r5 capture; see REVIEW.md. Exact commands, hashes, result counts, and scope caveats are in RUN.json and RESULT.json; full workflow capture is in ../m7_pytest_tmp_overlay_r5/.

Invariant impact: INV-3 affected; INV-4 preserved; INV-1, INV-2, INV-5 through INV-10 not touched.

This is local SDK/test evidence only. It does not establish hosted CI, live-wallet or chain behavior, ledger admission, or deployment readiness. F05 remains 45/55 negative cases and 18/21 mutations; testnet readiness remains NOT READY, and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
