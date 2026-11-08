# F05 inline-datum mutant import anchor

The disposable `remove_inline_datum_guard` mutation expected a stale import line omitting `Output`; current validator source includes it. This slice changes only that exact source-edit anchor, retaining fail-closed single-match replacement. A separately owned test file verifies the intended disposable diff and failure on duplicate/drifted anchors. Integrated offline focused tests passed 38/38.

The source-bound full harness protected 25 files unchanged but exited 1 during the inline-datum mutant's Aiken build; no complete result artifact exists. A separate isolated build reproduced exit 1 but captured only progress lines, not a precise compiler diagnostic. Source inspection finds that the generated helper imports/returns `OutputDatum`, absent from the pinned transaction module, which exports `Datum`. This is a likely cause requiring a distinct correction and fresh review.

No F05 negative or mutation ledger credit, ledger admission, or live-network evidence follows. The production validator, blueprint, and fixtures were not changed; INV-1 through INV-10 enforcement paths remain untouched. Readiness NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled. Owner F04/F05 decisions and the separate `unconditional_success` context-rebinding defect remain open.
