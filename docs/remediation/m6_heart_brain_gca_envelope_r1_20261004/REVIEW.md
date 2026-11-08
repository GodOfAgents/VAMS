# Independent red-team review   — M6 GCA envelope design r2

Disposition: **PASS for design-slice acceptance**  
Date: 2026-10-04  
Review mode: independent, read-only

Exact reviewed artifacts:

- `DESIGN.md`   — `e10a564303f33fd742fe4ec24bc75fd57bcbb1e473b7dad875605533131fa87d`
- `envelope.schema.json`   — `68e204becf2586c406be43aae7723113c824cb6d71496d9fc47626188f16db42`
- `validate_schema.py`   — `562c7d5bd2778ec7663e5b289f11231f3c55c9410dec9c987b28d42a7499bfad`

The review checked the exact files against `docs/remediation/GCA_ACCEPTANCE.md`, `docs/remediation/PLAN.md`, the threat model, current source and invariants. It confirmed 33 required source-binding paths cover all required claim fields. `anchor_record` binds anchor ref, digest, checkpoint, observation time, freshness deadline and finality; evidence class/artifact/review, effect status/readback, and issued_at/expiry are separately bound. Logical intent, operation UUID, and replay nonce remain distinct.

The proposal leaves authority/trust-root choices open, addresses INV-1  –INV-10 without claiming proof, distinguishes evidence classes, and states enforcement/tests are not implemented or executed. Current source has no integration with the envelope.

The exact command `python3 -B /home/GodOfAgents/code/VAMS-testnet/docs/remediation/m6_heart_brain_gca_envelope_r1_20261004/validate_schema.py` passed: Draft 2020-12 meta-validation, complete 33-path sample, missing-binding rejection, malformed-nonce rejection, and unknown-field rejection. These are synthetic syntax checks only.

Residual implementation hardening (P2, outside design acceptance): impose and enforce a maximum capability-reference count and total envelope-size limit at composer/UI, Executor, and settlement routes. Readiness remains NOT READY.
