# Independent post-run review — Python workflow r4

Outcome: **PASS**. The reviewer verified all four pre-review package checksum entries, confirmed the exact runner hash `0daf90dbf06726babb02df68df92c4aa6898e41d9f17676003b8729319c7a394`, and confirmed its Python source inventory skips paths under `EVIDENCE_REL`. RUN and RESULT agree on pinned Python 3.12.14, pytest 9.1.1, Envoy 1.39.1 and its SHA-256, workflow hash, HEAD, and stable before/after Python-source, workflow and filtered Git fingerprints. The main/design selectors match the CI split. Counts are 1,699/1,699 main and 10/10 design, zero failures, with `gate_pass: true`.

The reviewer noted that r3's inventory included its own evidence runner and that r4 corrects the fingerprint scope. This changes inventory accounting, not test selection or execution. Four new main cases match the INV-5 parameterized test addition.

Limits: raw JUnit and pytest output were deleted; the expected outer command is wrapper-written metadata, not independent process telemetry. This is local test evidence only and grants no hosted CI, ledger, live-network or deployment credit.
