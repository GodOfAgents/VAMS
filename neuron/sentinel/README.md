# Sentinel Network (`neuron/sentinel/`)

Sentinel supplies local challenge and DA-publication scaffolding. Live node
construction is disabled pending authenticated challenge identity, actual chain
anchoring and confirmed publication. It does not establish remote hardware,
execution correctness, SLA enforcement or automatic on-chain slashing.

## Current source behavior

- `sentinel_node.py` selects local challenges with `secrets.SystemRandom`.
  Scheduling is randomized; it is not a verified randomness function.
- `challenges/cpu_benchmark.py`, `gpu_benchmark.py`, `storage_iops.py` and
  `memory_bandwidth.py` contain local benchmark algorithms. Running them on one
  host does not demonstrate the registered remote node's capacity or identity.
  `latency_probe.py` currently measures a simulated delay, not a remote ping.
- `PerformanceAuditLog.publish_sentinel_report` is the current DA boundary.
  Existing runtime/mock/adapter restrictions remain. A local mocked response is
  not an authentic DA receipt or independently verified exact-byte retrieval.
- `_submit_sla_report` rejects before SDK/key/signing/broadcast access because no
  qualified transaction producer and receipt verifier is implemented. It cannot
  report a completed chain transaction or enable slashing/rewards.
- Gain/anomaly/world-state-fidelity telemetry remains observational and does not
  supply consent, authority, TEE/ZK proof, reward eligibility or execution proof.

## Return and runtime contract

`audit_node` returns `True` only for explicit boolean DA-publication success in
the unchanged local runtime when no SLA configuration was supplied. If an SLA
address or key is configured, its requested/incomplete chain stage is unavailable
and the result is `False`. Exceptions, malformed/truthy non-boolean success and
runtime drift also return `False`. This boolean is not a transaction receipt.
Publication can already have occurred before a later failure or drift; `False`
does not prove absence and does not authorize an automatic retry.

The node retains the same environment mapping supplied at construction (default:
`os.environ`) and its immutable startup policy/mock selection. It revalidates
that source before probes/publication/scheduling and after awaited work. An
injected mapping remains the component's configured source; it is not silently
replaced with an unrelated global environment. This is configuration continuity,
not the missing authenticated current-host policy/authority mechanism.

## Qualification still required

Real remote challenge identity, native proof verification, approved operator/
custody identities, privacy/data disposition, DA publication and independent
exact retrieval, SLA transaction intent/roles/nonces/receipt/finality, adversarial
runtime integration and full qualification gates remain required. This local
containment does not qualify a provider or enable a live factory. Both-chain
testnet readiness remains NOT READY. Deposit, Slash activation, ExecuteIntent,
real fiat/yield and the restricted economic disablements remain unchanged.
