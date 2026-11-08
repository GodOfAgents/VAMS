# F05.2a evidence category wording correction

This record-only correction narrows the generic ledger limitation so it matches the frozen evidence categories. Each PASS must cite reviewed evidence fitting its declared category. Simulator evidence is required for transaction-simulator cases; routing-only and context-only PASS entries retain their explicitly scoped non-ledger classifications.

The immediately preceding accepted ledger is copied to CASE-STATUS.json with only that limits sentence replaced and a classification clarification object added. No identifiers, dispositions, counts, registry assertions, or frozen contract content changed.

Independent review must confirm the exact one-sentence correction, strict JSON, preserved counts, and unchanged frozen contract and registry hashes. No behavioral evidence is created by this documentation slice.

Independent review outcome: PASS. The reviewer compared the exact prior ledger (SHA-256 391cb0c7855f00e321813e4b273cd249c7f4bc390cdd62acaf0913bf2d9db056) to this overlay and confirmed only schema_version, limits item 2, and evidence_category_clarification differ. source_registry, all negative and mutation records/counts/dispositions, and frozen assertions are unchanged. Strict JSON parsing passed.
