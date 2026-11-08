# F05.2a current applied-policy identity revalidation - 2026-10-03

Status: PASS for current-source synthetic fixture identity after independent review.

The prior identity record no longer matched all current Cardano inputs after later M7 provenance changes, so the applied policy was reproduced again from the canonical checkout. The exact command and tool hashes are in RUN.json. It ran under bubblewrap with `--unshare-net` and a read-only root; only `/tmp` and this evidence folder were writable. Two disposable builds each ran Aiken build, two blueprint applications, and policy calculation. The outer command exited 0; all eight inner Aiken commands exited 0. Aiken copied two dependencies from its existing cache; no network fetch or tool installation occurred.

Both builds produced the same 3,467-byte compiled policy with SHA-256 `fc8726cff89172d4944e257a2eb2659d35363c8e5a4d423ed8a2112eb5af7e59`, matching the frozen applied artifact and valid transaction witness. Both derived policy ID `9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731`. The run binds the current blueprint SHA-256 `c4230410d0caac45f2c71d36e45a539c78087697128ce1533306d17e96a48008`, current raw lock SHA-256 `acffff4aee9569e1ee1de468839077af467b5e403fd96450290cd367b339c651`, and 21 Cardano input hashes. Before and after inventories are equal, and the independent reviewer confirmed all 21 still match the current checkout.

The exact output is `run2/RESULT.json` (SHA-256 `5e4aa181142e34d8e95288b3077306d1d2a7960ceda81f1a07200e8c9524882d`). The independent review is recorded in REVIEW.md.

This closes only the F05.2a original applied-policy identity gate for the synthetic fixture. It grants no negative-case or mutation credit and establishes no ledger admission, Cardano Pre-Prod, live-network, or deployment evidence. The accepted F05 overlay remains 45/55 negative cases and 18/21 mutations. INV-1 through INV-10 were not touched. Readiness remains NOT READY; deployment, Deposit, Slash activation, and ExecuteIntent remain disabled.

Next single slice: resolve the F04 normative identity-entrypoint choice recorded in docs/remediation/STATUS.md. No F04 validator behavior change is authorized before that choice.
