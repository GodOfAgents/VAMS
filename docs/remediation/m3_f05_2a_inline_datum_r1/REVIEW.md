# F05.2a inline-datum mutation acceptance

remove_inline_datum_guard / datum_missing is accepted at synthetic transaction-simulator scope after independent review of corrected candidate r2.

Candidate: /home/GodOfAgents/vams-evidence/m3-f05-2a-inline-datum-mutation-20261002-r2/
Candidate manifest SHA-256: 2c3fb57f14c9eaa2afffdea91ea532acf8dd3dbcf6a10966729633fd2ad8a8e9
Independent review: /home/GodOfAgents/vams-evidence/m3-f05-2a-inline-datum-independent-review-20261002-r2/REVIEW.json
Review SHA-256: 6f8c639aaa260a91963c0e6fe32486047df0ef9114463d14efb1b9b1dba774be

Exact command:

PYTHONDONTWRITEBYTECODE=1 /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python /home/GodOfAgents/vams-evidence/m3-f05-2a-inline-datum-mutation-20261002-r2/run_inline_datum_mutation.py

Result: exit 0. All eight original-valid, original-datum-missing-negative, mutant-valid, and mutant-datum-missing-negative cases pass across pinned Aiken 1.1.21 and 1.1.23 with target invocation and clean teardown. Stale-script and wrong-policy routing controls fail before target invocation. The disposable mutant redirects the authority datum read to sponsor_datum, adds the donor helper, and corrects the import to the standard library's actual Datum type. In the negative, only the authority output datum is removed; the sponsor output retains the byte-identical canonical inline donor Datum, including unchanged PoP fields. Funding witnesses match persisted resolved-input payment-key hashes. The canonical policy, blueprint, and lock were untouched.

Candidate r1 is preserved but receives no credit: the disposable mutant imported nonexistent OutputDatum and failed to compile before simulation. Candidate r2 uses Datum and passes independent review. datum_missing was already credited as a negative case; this mutation adds no negative-case credit.

Counts: 42/55 negative cases PASS (13 pending, 0 failed); 17/21 mutations PASS (4 pending, 0 failed). Evidence is synthetic transaction-simulator evidence only. It establishes neither ledger admission nor live-network behavior. No canonical production source, applied policy identity, blueprint, or lock was changed. F05/M3 remain open and testnet readiness is not established; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
