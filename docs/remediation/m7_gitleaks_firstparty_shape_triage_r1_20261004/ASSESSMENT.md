# M7 first-party finding shape triage — value-free, no disposition

This triage processes the 385 sanitized first-party finding identities from the r5 capture. Before parsing any source file, the runner checked its current SHA-256 against the per-finding file SHA-256 in the r5 sanitized result. All 385 identities matched across 31 files; none changed or was missing. The runner was reviewed before execution, ran with the checkout read-only and network disabled, and emitted only paths, finding line ranges, allowlisted field-path segments, type/length/hex/entropy categories, AST node types, and hashes.

The 382 JSON findings mapped to one candidate scalar on each recorded line. Their candidate string shapes are: 143 in the 32–63 character bucket, 138 exactly 64 characters, and 101 in the 128+ bucket; all 382 candidates are hex-shaped strings. The sanitizer does not provide match columns, so these are line-level candidates, not confirmation of the detector’s exact substring. The three Python findings have nine string literals across their line spans: two 1–16 character non-hex strings, six 17–31 character non-hex strings, and one 64-character hex-shaped string. AST candidates are contextual, not exact match attribution. Non-allowlisted JSON keys are masked as opaque-key.

The identities are concentrated in remediation evidence: 274 findings in the two F05 mutation-provenance COMPILES files, 49 in the F05 design VECTORS file, and 62 across the remaining evidence files; three findings are in two Python files. These path and shape patterns do not establish that any value is harmless or secret. No finding is adjudicated, closed, or allowlisted. M0.4 remains FAIL pending source evidence and owner disposition. This is not T06 history/impact evidence.

A provisional unreviewed parser attempt treated pretty-printed JSON lines as standalone JSON and produced no usable scalar mappings; it was not accepted as evidence. The reviewed line-span parser above produced the reported result.

The exact command, input/output hashes, and summary are in RUN.json. Independent post-run review PASS; see REVIEW.md. F04/F05 owner decisions and F05 ledger deficits remain; readiness is NOT READY and deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.


## Authority boundary and next decision

The triage is sufficient to prepare owner disposition, but not to classify any finding. The pinned gate requires zero first-party findings. Before inspecting or changing first-party finding content, accepting any as noncredential fixtures, modifying scanner behavior/allowlists, or changing the zero-first-party policy, the Audit Lead/project owner must set the per-finding disposition authority and evidence standard. The current material does not define that authority. This triage makes no recommendation to waive the gate; no source or policy change is authorized by this evidence.
