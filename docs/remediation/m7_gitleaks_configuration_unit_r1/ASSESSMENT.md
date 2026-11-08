# GitLeaks configuration unit tests

Date: 2026-10-03
Status: PASS; independent review PASS.

The existing tests verify exact rule-targeted allowlists, absence of a global stopword/commit/path bypass, scan-root-relative command construction, and rejection of a missing explicit scanner binary. The pytest suite mocks subprocess invocation and does not run GitLeaks; no repository scan or credential values were read. The separate generated-fixture regression is recorded independently.

Exact pinned command, source hashes, output, and exit are in RUN.json. Network was disabled and checkout was read-only.
