# Independent review — M7 Python workflow gate — 2026-10-04

Reviewer: /root/python_workflow_review (read-only; exact integrated evidence package and raw captures).

Result: PASS with one disclosed raw-manifest checksum exception.

The retained outputs substantiate the commands and outcomes: the root suite reports 1,696 passed, 444 subtests, and four failed; the separate F05 design suite reports 10 passed; the PATH-corrected targeted history test reports 1 passed. The four failures are the three documented legacy F04 mint expectations plus the PATH-only history test. This correctly leaves the root suite failed and does not imply deployment readiness.

The canonical and isolated-snapshot Git statuses match the bound digest. The source inventory delta contains only audit.log and pytest cache lastfailed/nodeids. Captured bwrap arguments show --unshare-net; the child network namespace differs from the host; canonical source was mounted read-only. The PATH recheck raw SHA256SUMS manifest verifies.

Raw workflow checksum exception: 7,561 entries were checked; exactly one differs. The manifest’s pre-run digest for ./snapshot/.pytest_cache/v/cache/lastfailed is cee5869b7ed2ce4808a2879af55e210889c0e237d4e07bfafe43b76edd195f85; its post-run digest is a19280ce6454e4a64be7708506e3e3716622e375ed433f6989131401db6277dc. The source-inventory delta independently records this expected pytest-cache write. The other 7,560 manifest entries verify. The wrapper exit 1 propagates the expected failing root suite.

No source behavior, test count, evidence class, or readiness status is upgraded by this review. It is local static/test evidence only. F05 evidence remains synthetic and its accepted ledger classifications remain 45/55 negatives and 18/21 mutations. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
