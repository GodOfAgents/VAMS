# M7 T06 local-history scan (available refs only)

Date: 2026-10-04

## Result

Pinned Gitleaks 8.30.1 completed an offline, fully redacted scan of the 9 refs and 89 reachable commits present in the canonical local checkout. It exited 0 with an empty report (0 entries; no rule counts). The private temporary report was deleted before sanitized evidence was written. The checkout was non-shallow; HEAD, branch, refs, reachable commit count, and porcelain-status digest matched before and after the scan.

The four protected historical commits recorded in the T06 audit were each absent locally. The scan therefore covers only available local history. It does not inspect hosted refs, prove credential/provider revocation or impact, authorize history rewriting, or satisfy the post-rewrite/remote zero-finding gate. T06 remains PARTIAL and BLOCKING. This result does not change any finding disposition or deployment gate.

## Execution

The capture wrapper was independently reviewed before execution. Exact invocation:

```text
bwrap --unshare-net --ro-bind / / --tmpfs /tmp --dev-bind /dev /dev --proc /proc --bind /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_t06_local_history_89_r1 /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m7_t06_local_history_89_r1 --chdir /home/GodOfAgents/code/VAMS-testnet /home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python -B docs/remediation/m7_t06_local_history_89_r1/run_capture.py
```

The checkout was read-only inside the network-denied boundary; only this evidence directory was writable. The wrapper retained the scanner's redacted report only in a private temporary directory, then removed it. It published the report hash, count, rule counts, exact Git snapshot, tool/config/script hashes, and sanitized exit. Neither report contents, finding paths, matched values, nor scanner stdout/stderr were retained.

## Verification and classification

- Scanner exit: 0; report entries: 0; rule counts: `{}`.
- Gitleaks binary: pinned local 8.30.1, SHA-256 `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509`.
- Config SHA-256: `40ddce18233e73c94668ddd47a5abe2a6afa0e9bc4602657dc34ec2b78606ecd`.
- Capture script SHA-256: `2c3c3ff5cd00106a19ae4be11e882b19d0132dde6347487a5c74fe49936432e3`.
- Report SHA-256: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.
- Four protected commits are absent; see `RUN.json` for their IDs and exact snapshot.
- This is local historical-scan evidence only. It is neither TruffleHog evidence nor hosted-history, provider-revocation, ledger, or live-network evidence.

The evidence-package write occurred after the scan, so the current dirty-status digest naturally includes these new files and differs from the scan-time digest. HEAD, branch, ref OIDs, and reachable history remain the recorded values. No application source, toolchain, credential, or Git ref was changed.

## Independent review

Independent read-only post-run review PASS. The reviewer verified the script and tool/config hashes, current 9-ref/89-commit Git snapshot, absence of all four protected commits, scanner exit/count coherence, report-hash consistency with the empty report, redaction/retention behavior, and the stated local-only limitations. The exact sandbox invocation was also subject to pre-run safety review; the post-run reviewer noted that a separate execution transcript is not retained. See `REVIEW.md`.
