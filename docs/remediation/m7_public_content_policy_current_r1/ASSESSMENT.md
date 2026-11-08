# M7 current-source public-content policy scan

The workflow public-content-policy job invokes scripts/security/public_content_policy_scan.py. The scanner checks Git's cached and non-ignored untracked paths against docs/funding/** and docs/team/idex-*.md. It exited 0 with no blocked paths under pinned Python 3.12.14, network disabled, and a read-only checkout.

Independent review PASS. The reviewer verified workflow wiring, scanner rules, inventory, and independently reproduced the passing output. The inventory comparison excludes this evidence package and matched at 1,694 paths, SHA-256 51359db032ebb08334c411e03a5aad6fefa5a76959640fb808854e12601c276f. The scanner itself still considers the package paths, which match neither blocked pattern.

This is a path-only check of current cached and non-ignored untracked files. It does not inspect ignored files or repository history. The CI job does not pin its Python version. No application code changed; this does not establish deployment readiness. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
