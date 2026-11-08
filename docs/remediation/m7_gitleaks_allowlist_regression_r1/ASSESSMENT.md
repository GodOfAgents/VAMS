# GitLeaks narrow allowlist regression

Date: 2026-10-03
Status: PASS; independent review PASS.

The workflow allowlist regression uses the already-installed pinned GitLeaks binary against generated temporary fixtures. It checks that approved public expressions remain allowed and four synthetic secret categories are rejected. It does not scan VAMS history or resolve the existing GitLeaks finding dispositions.

Exact commands, isolation arguments, source/binary hashes, outputs, and exits are recorded in RUN.json. Network was disabled and the checkout was mounted read-only. No tools were installed or fetched.
