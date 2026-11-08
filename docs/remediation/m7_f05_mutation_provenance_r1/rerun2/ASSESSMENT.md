# F05 current-tree synthetic provenance replay

The accepted F05 mutation-provenance capture was replayed against the integrated canonical tree after the F04 registry-mint rejection. The current registry source hash is captured identically before and after. The runner returned pass: 57 case observations, 21/21 compiled mutations detected, 55 unconditional-success synthetic subcases, 542 Aiken commands, 35 compiles, 134 evaluations, and 47/47 protected inputs unchanged.

The replay produced synthetic compiled UPLC evidence only. It generated a synthetic policy identity using ephemeral committee test material, not the frozen original applied-script identity. It does not establish paired original-policy transaction simulation, ledger admission, Cardano Pre-Prod execution, or live-network behavior. All five ephemeral signing-key memfds were closed, the temporary workroot was removed, and no private-key bytes were retained.

The accepted F05 ledger classifications are unchanged at 45/55 negative cases and 18/21 mutations. Ten negatives and three mutations remain pending their documented owner evidence-scope decisions. This replay adds provenance for current integrated source only; it does not promote those pending rows or mark F05 complete. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.
