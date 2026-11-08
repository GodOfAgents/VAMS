# M7 current-source strict Aiken gate  2026-10-05

The current Cardano source snapshot passed the pinned strict Aiken gate: 124/124 scenarios, comprising 117 unit and 7 property tests, with `--deny --seed 20260711 --max-success 250`. The command exited 0 in a network-isolated disposable snapshot.

The canonical checkout was not used as a writable test directory. Source was copied into a disposable workspace under bubblewrap; no source, evidence, credentials, dependencies, or Git refs changed. Output was retained only through SHA-256 hashes: stdout `7b85975db2d0d0b1a740a0aa85139fafa2706b31c66860495c0d30b8f9f0f07e`, stderr `6d2bf5a0c258f6248b45f5946a93dc1f474ac563ba3f064ac5a99bb340a851f6`.

The run is bound to current-forward manifest `cardano/aiken-dependency-manifest.json` SHA-256 `d4bbe77962932359f2d2d8598f7758b84868c9377aba23f96c103baefac7ec93`, blueprint `cardano/plutus.json` SHA-256 `718845f253ebdfb9f1d565e34511534f6b565cf1dd898402b67109180dff6492`, and the 16-source compilation manifest SHA-256 `4a896a2df8254afc022207fd8477087106cb4ff242d6d1b753026973afb8f960`. Aiken v1.1.21+42babe5 and bubblewrap 0.11.1 identities are recorded in RUN.json.

This is local validator and provenance evidence only. It does not establish Cardano Pre-Prod ledger admission, live-network behavior, F04 anchor authorization, F05 ledger admission, or deployment readiness. Readiness remains NOT READY; Deposit, Slash activation, ExecuteIntent, and deployment remain disabled.
