# M1.3 local implementation review

Status: locally implemented and tested; accepted by independent M1 review.

The repository-native runtime preflight parses the central immutable policy,
can require a live mode and an exact expected mode, and outputs only sanitized
classification. The primary Neuron boundary rejects live startup before owned
effects while incomplete clients remain. CI declares test mode and separately
checks exact testnet preflight. The legacy CDK shell is a fail-closed scaffold,
not deployment evidence.

The deployment shell was not executed. Static validation confirms its preflight
and unconditional incomplete-scaffold block. No deployment or external action
occurred.

The initial independent review found additional executable boundaries. The
corrected central policy now parses all 25 registered M1 mock flags during
preflight and rejects a supplied policy that conflicts with the effective
environment. The standalone demo requires exact `VAMS_ENV=demo`, emits only
`simulated:` transaction identifiers and non-authoritative claims, and its L1
anchor no longer attempts a provider before falling back. The legacy Neuron
gateway rejects every live mode before lifespan yield or Uvicorn startup.
Neuron communications, routing, and x402 demonstration branches require exact
demo mode before identity, routing, payment, or audit effects.

Corrected verification passes 173 final runtime/entrypoint/preflight public-
boundary tests and 624 integrated M1/F17/affected tests. The reviewer's aggregate testnet mock configuration exits
1 and names the offending registered flag. The corrected-state independent
decision is recorded in `docs/remediation/m1_r2/REVIEW.md`.

Corrected-state re-review also verified and then required closure of alternate-
gateway policy rebinding and the demo's live-looking static agent identifier.
The gateway now compares supplied/startup policy to fresh process policy before
yield or Uvicorn, and the demo uses only `simulated:` agent/transaction names,
simulation-complete labels, and simulated-state receipt wording.
