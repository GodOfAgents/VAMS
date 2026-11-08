# M3.2a-R15 remediation of R14 oracle trust defects

Date: 2026-09-27
Scope: only the four R14 oracle trust defects. No frozen R7 artifact, Cardano source, lockfile, dependency, deployment, credential, vendor or Git-history change.

R14 was verified at /home/GodOfAgents/vams-evidence/m3-2a-r14-review-20260927-829ab544571f with SHA256SUMS digest 8476aee085001921fed246e69c130ab2dc811f3adc8f0859806f8e91bd665c02. The pre-fix disposable copy reproduced synthetic datum-vector acceptance, self-authorized authority output, surplus reserve acceptance and missing topology binding.

Implemented:
- validate_inline_datum now accepts only a closed vector identifier, ignores/rejects caller-supplied expected dictionaries, loads the fixed reviewed DATUM_VECTORS.json, verifies its frozen SHA-256, rejects duplicate/unknown registry fields and IDs, and requires exact reviewed kind/value/bytes/size.
- validate_value_flow now requires exact governed reserve quantities.
- validate_reserve_outputs rejects caller-defined authority expectations without authenticated pre-state, validates authority continuation core fields, checks immutable/counter successor semantics when pre-state context is supplied, and binds selected transitions to the frozen topology output counts and frozen topology hash.
- Focused tests cover synthetic vectors, exact reserve surplus, self-authorized authority output, registry IDs, and topology output counts.

Fresh verification:
- focused oracle tests: 10/10;
- governance tests: 12/12;
- Python compilation: passed;
- frozen artifact and lockfile hashes unchanged;
- provenance and pinned Aiken checks remain required before acceptance.

This is remediation evidence only. F01-F05 remain open, M3 remains OPEN, Pre-Prod admission is INCONCLUSIVE, promotion is NOT READY, and M3.2b is not authorized.

INV-1 through INV-10 and mock behavior are unchanged.
