# M7 control-matrix crosswalk assessment

This read-only slice maps all 36 rows in docs/audit/control-matrix.json to configured jobs in .github/workflows/security-gates.yml and accepted evidence records visible in the canonical checkout. It separates automation from current acceptance and identifies external, blocked, partial, and not-evidenced controls. No CI, application source, control-matrix status, credential, or activation state changed.

The fresh pinned-Python diagnostic passed schema validation for all 36 tracks (exit 0), then failed canary readiness (exit 1). Applicable T01-T35 states remain implemented, partial, or blocked rather than verified; the tree is dirty; and the signed commit-bound evidence manifest, assurance index, both chain rehearsal manifests, runtime report, and privacy review are absent. See READINESS-RESULT.txt and scripts/audit/audit_program.py:1079-1172.

Current coverage classifications: 18 partial, 9 blocked, 8 not evidenced, and 1 external/not evidenced. No row has complete, accepted current hosted workflow evidence. Matrix states are reproduced separately in CROSSWALK.md and are not rewritten. The full row mapping and source hashes are in CROSSWALK.md and RUN.json.

F05 remains 45/55 negative cases and 18/21 mutations. F04 policy-anchor model/authority choices remain pending; Gitleaks/M0.4 and T06/history remain open. Testnet readiness is NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Independent final review: PASS. The reviewer confirmed exact T01–T36 coverage, current source hashes, conservative T06/history and hosted-evidence scope, readiness diagnostic fidelity, and final package integrity. One T06 wording ambiguity was corrected before final review. See REVIEW.md.

Independent final review: PASS. The reviewer confirmed exact T01-T36 coverage, current source hashes, conservative T06/history and hosted-evidence scope, readiness diagnostic fidelity, and final package integrity. One T06 wording ambiguity was corrected before final review. See REVIEW.md.
