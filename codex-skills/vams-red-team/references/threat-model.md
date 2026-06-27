# VAMS Threat Model Prompts

Attack classes:

- MEV and ordering: sandwiching, frontrunning, oracle reveal manipulation.
- Bridge forgery: proof replay, payload/proof confusion, fallback transport abuse.
- Economic drain: reward insolvency, yield over-allocation, escrow underfunding.
- Regional collusion: thin-liquidity bid floor manipulation for N < 5 providers.
- Wash trading: operator-linked rewards returned inside 7 days.
- Session key abuse: expired keys, overbroad whitelists, high value caps.
- TEE bypass: attestation bound to session key instead of root EOA.
- Identity bypass: OMS outage treated as allow instead of deny.
- Mock evidence: DA, Trails, TEE, x402, or identity mocks used as live proof.
- Gateway compromise: weak auth, default password, permissive CORS, public HTTP.
- Cognitive attacks: prompt injection, memory poisoning, SIRA term poisoning, HIPIF data loss.

Review math:

- For thin liquidity: `P_floor = alpha * Bid_min + (1 - alpha) * P_hardware`, with alpha tending to 0 as N drops.
- For pass-through rewards: `Reward_net = Reward_base * (1 - exp(-lambda * delta_t))`.
