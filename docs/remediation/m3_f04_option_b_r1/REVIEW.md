## M3 F04 Option-B implementation and fixture freeze — 2026-09-29

This scoped record implements the authorized Option-B DID contract and forward
provenance reset. `AgentDatumV1.did` remains the exact raw UTF-8 byte sequence;
the validator enforces 32–256 bytes and UTF-8 round-trip validity without
lowercasing, hex reinterpretation, or normalization. Accepted identity-token
vectors remain frozen.

The forward provenance root is the current canonical lock
`6f3b369ff5e7caf986ddf9b877af8bf1b71679307d90155e59f128313648d60f`. The
historical `8fc8bf1ccf3cf0c91acc94232646ebabb23469eb7c2d4acb1f4f0b0b67f8213b`
bytes were unavailable; no raw-byte continuity claim is made.

### Fresh results

- Frozen fixture schema: 49 unique rows, 67 evaluations; focused fixture tests 14/14, including stake-only mutation isolation.
- Independent fixture review: PASS; independent encoder and policy/authority bindings accepted.
- Compiled public evaluator: 49/49 rows, 67/67 evaluations, zero pending; status PASS.
- Compiled mutation matrix: 9/9 targeted mutations rejected.
- Worst accepted evaluator cost: CPU 593,824,999; memory 1,482,647; context CBOR 1,856 bytes.
- Isolated pinned Aiken 1.1.21 production checks: 120/120 pass; two isolated builds are byte-identical (`plutus.json` SHA-256 `55006d4e3f70826933f21b1a9bb55c076aceb3f33a4cf50910d5abc9c719f065`).
- Forward provenance suite: 21/21 pass; historical mutation suite: 16/16 pass.
- `cardano/aiken.lock` remains byte-identical to the current forward root; no canonical Aiken build was run.

This is implementation and local evidence only, not independent F04 acceptance.
F04 and F01–F05 remain `REVALIDATED_OPEN`; M3 remains `OPEN`; Deposit and
ExecuteIntent remain disabled; Pre-Prod admission is `INCONCLUSIVE`; promotion
is `NOT READY`. INV-1–INV-10, M1/M2 containment and mock behavior are unchanged.
The next slice is independent F04 compiled implementation review.
