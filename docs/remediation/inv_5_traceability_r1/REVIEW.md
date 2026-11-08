# INV-5 traceability-control synchronization

Date: 2026-09-24
Scope: INV-5 traceability-control synchronization only
Verdict: locally synchronized and verified; runtime behavior and F09 disposition unchanged

## Root cause and corrected contract

The previous INV-5 control was a prose substring check. It expected
`Institutional compliance routing requires an OMS verified identity`, while
the current fail-closed source says `live OMS verified identity`. The gate
therefore failed even though the current runtime control was stronger than the
historical sentence.

Schema 1.1 replaces that INV-5 prose anchor with structured Python AST and
exact test-identifier metadata. The validator resolves exact class/function
symbols and checks the P3 denial guard, live-provider result predicate,
provider-result provenance classification, explicit provider failure outcomes,
and both OMS signing guards. It rejects missing, duplicate, unknown,
incomplete, malformed, unsafe-path, or ambiguously modeled metadata. Tests
remain required evidence but cannot substitute for missing source enforcement.

Legacy `must_contain` anchors remain supported for INV-1–INV-4 and
INV-6–INV-10. Their canonical structural JSON digest is fixed by regression at
`4a74f5df05e42efb8af837ca0a35bdb3769ca2a7dff8ee67a895e141d4c84f85`,
proving this slice did not change those control contracts.

## Runtime truth verified before synchronization

- `CLRouter._route_polygon_kyc` requires the OMS service block, constructs an
  available verifier, and rejects unless
  `is_compliance_verified(agent_address)` is true.
- `OMSIdentityVerifier.verify_identity` returns an unsuccessful sanitized
  result for missing subjects, provider status failure, malformed provider
  data, request failure, parse failure, or unexpected provider failure.
- `OMSVerificationResult.usable_for_compliance` requires both verification
  success and `live-provider` evidence. `_result` assigns that provenance only
  for a successful, non-simulated result in a live runtime.
- `OMSSigner.sign_transaction` and `sign_message` retain fail-closed OMS
  checks. No OMS cache, fallback authorization, or test-only source control is
  treated as authoritative.

Two focused tests make the current boundary explicit: a provider success in a
non-live runtime cannot authorize P3, and an unavailable lazily constructed
OMS verifier denies P3. No production runtime file changed in this slice.

## Mutation evidence

All mutations operate only on temporary copies. The suite proves:

1. the current aggregate traceability contract passes;
2. the historical stale sentence fails for the original missing-anchor reason;
3. harmless denial-message prose changes pass;
4. removing the OMS denial guard fails;
5. replacing denial with a permissive fallback fails;
6. renaming a required regression test fails;
7. missing, duplicate, unknown, incomplete, and malformed metadata fail;
8. INV-1–INV-4 and INV-6–INV-10 metadata remain structurally unchanged by
   canonical digest; and
9. real OMS/CLR tests remain green.

## Fresh verification

- `python3 scripts/audit/validate_traceability.py`: passed.
- `python3 -m unittest -v scripts.audit.test_traceability`: 9 passed.
- Focused OMS/CLR runtime set: 45 passed.
- Affected M1/F17/INV-5 regression set: 413 passed.
- Relevant M2/Gateway regression set: 253 passed.
- `python3 -m unittest discover -s scripts/audit -p "test_*.py"`: 95 run,
  one skip, one unrelated environment failure. The history-rewrite script
  defaults to `PYTHON_BIN=python`, but this WSL host provides only `python3`.
- The identical remediation bundle with its supported
  `PYTHON_BIN=python3` override: 95 passed, one skipped.
- Workflow supply-chain validation and traceability validation: passed.
- Scoped Python compilation: passed.
- Documentation JSON validation: 27 files passed.
- Scoped stale-anchor/alternate-control searches: passed; the historical
  sentence remains only in its negative mutation fixture.
- `git diff --check`: passed.

No dependency was installed. No runtime, M2/Envoy, frontend, credential,
vendor, deployment, history, commit, push, or fetch action occurred.

## Invariant and mock-mode impact

| Invariant | Impact |
| --- | --- |
| INV-1 | Unchanged; regional emissions and its control metadata are unchanged. |
| INV-2 | Unchanged; insurance yield and its control metadata are unchanged. |
| INV-3 | Unchanged; session-key lifetime and its control metadata are unchanged. |
| INV-4 | Unchanged; session-key scope and its control metadata are unchanged. |
| INV-5 | Traceability synchronized to the existing fail-closed live-provider runtime behavior; no runtime logic changed. |
| INV-6 | Unchanged; TEE/root-EOA binding and its control metadata are unchanged. |
| INV-7 | Unchanged; oracle freshness and its control metadata are unchanged. |
| INV-8 | Unchanged; token supply and its control metadata are unchanged. |
| INV-9 | Unchanged; reward solvency and its control metadata are unchanged. |
| INV-10 | Unchanged; bridge proof and payload hash remain separate, and its control metadata is unchanged. |

Mock-mode selection and M1 containment are unchanged. F09 remains
`REMEDIATED`; this synchronization neither reopens nor changes its disposition.

## Remaining blockers and next slice

The history-rewrite environment mismatch remains out of scope and unchanged.
Frontend `/nodes` remains unresolved. F08 and M2 remain open. The next slice is
**frontend `/nodes` disposition**.
