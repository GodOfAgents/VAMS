# Independent review: M7 T06 local-history scan

Verdict: PASS for this bounded local scan evidence package; T06 remains open.

The read-only reviewer independently checked the completed `RUN.json` and capture wrapper. The script SHA-256 is `2c3c3ff5cd00106a19ae4be11e882b19d0132dde6347487a5c74fe49936432e3`, matching the recorded value. The pinned Gitleaks 8.30.1 hash and `.gitleaks.toml` hash match the recorded tool and config identities. The current checkout independently reports HEAD `829ab544571f12efe50ecb5740f129c8acb3e16f`, branch `testnet/remediation-20260907`, 9 refs, 89 reachable commits, and non-shallow history, consistent with the run snapshot. Each of the four protected commit IDs is absent under `git cat-file -e`.

The recorded scanner exit is 0, entry count is 0, and rule counts are empty. The report hash is consistent with the empty JSON report. The wrapper rejects scanner exit/count disagreement, retains only rule-ID counts and a hash, and keeps the redacted report in a temporary directory; raw report and scanner stdout/stderr are not retained. No match values or finding paths appear in the evidence.

Scope qualification: review covers the artifact, wrapper, and independently queried current snapshot. The exact bwrap invocation received pre-run safety review, but there is no separate retained execution transcript. Four protected commits remain unavailable locally; hosted refs, credential/provider revocation and impact, coordinated history work, and post-rewrite scans remain unverified. This result does not close T06 or establish testnet readiness.
