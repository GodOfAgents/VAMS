# Historical tests retired from the live suite

Owner decision 6 of 2026-11-08 ("Retire as historical"). These tests remain in
the repository as evidence of the source they were written against. They are
deselected by exact node ID in `pytest.ini`, so every pytest run reports them
as deselected. No other test in their files is affected.

| Test | Written against | Why it no longer applies |
|---|---|---|
| `docs/remediation/m3_2b_r4/test_mutation_harness.py::MutationHarnessTests::test_adversarial_harness_mutations_are_rejected` | 2026-09-28 timelock/registry source (blueprint `7477763e…5477`) | Expected accept/reject results bound to superseded validator source |
| `docs/remediation/m3_2b_r4/test_mutation_harness.py::MutationHarnessTests::test_three_way_reachability_is_repeated_and_phase_separated` | same | same |
| `docs/remediation/m3_2b_r6/test_binding_guard.py::BindingGuardTests::test_public_result_has_four_binding_cases_and_stale_rejection` | September binding-guard source | Four-case public result bound to superseded source |
| `docs/remediation/m3_f04_impl_r2/test_interface_migration.py::F04InterfaceMigrationTests::test_blueprint_uses_migrated_public_schemas` | September F04 multipurpose registry | Expects registry source text (`datum.did == did`) removed by the standalone-anchor design |
| `docs/remediation/m3_f04_impl_r4/test_supplemental_entrypoints.py::SupplementalMatrixTests::test_each_new_case_has_an_explicit_contract_guard` | September F04 multipurpose registry | Expects registry-side mint acceptance |
| `docs/remediation/m3_f04_impl_r4/test_supplemental_entrypoints.py::SupplementalMatrixTests::test_every_supplemental_case_against_applied_public_entrypoint` | same | Expects `accept` for registry mint cases; current source correctly returns `reject` |

Superseding records: `VAMS-implementation-20261029/IDENTITY-DESIGN-RECONCILIATION-30.md`
(2026-10-31: preserve intentional registry-side mint rejection; standalone
`agent_nft` and per-bootstrap anchors are normative) and the
`m7_f04_registry_mint_rejection_r1_20261004` review.

Current-design coverage: the 884 native Aiken tests (including 724 governance
v2 cases) in `aiken check`. F04 anchor/standalone acceptance against applied
Plutus V3 programs remains open work under the C2 backlog item; retiring these
tests does not close it.

Rule for future additions: only an owner decision may add a test here, with
its node ID, source binding and superseding record. Failing tests are not
retired to obtain a green result.
