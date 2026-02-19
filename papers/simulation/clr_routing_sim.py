"""
CLR Routing Simulation v2 — Evaluation for arXiv Paper
=======================================================
"A Neuro-symbolic Safety Guardrail for Deterministic
 Multi-Chain Transaction Routing in Agentic Systems"

Author: Aseem Chishti
Usage:  python clr_routing_sim.py

v2 Changes (from v1):
  - Added Cardano (eUTXO, Ouroboros, formally verified) and Midnight
    (ZK-SD selective disclosure, compliance-grade privacy) chains.
  - Added finality_ms (economic irreversibility) distinct from latency.
  - Added per-trial stochastic jitter on cost and latency to simulate
    volatile gas markets.
  - Added compliance-privacy (ZK-SD) as a hard constraint.
  - Added formal-verification as a soft constraint.
  - |E| = 10 chains (was 8).

Key design principle:
  Privacy and Sovereignty requirements are HARD constraints (guardrails).
  If no chain satisfies them, the router REJECTS the transaction (returns
  None). The entropy-greedy loop runs only after hard constraints pass.
  This prioritises safety over liveness, per the neuro-symbolic pattern.
"""

import math
import random
import csv
import os
from dataclasses import dataclass, field, replace
from typing import List, Tuple, Optional
from collections import Counter

# ═══════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionEnvironment:
    """An execution environment (blockchain) with a property vector.

    Privacy types:
      - Public:  No privacy guarantees.
      - TEE:     Trusted execution environment (hardware-level).
      - ZK:      Zero-knowledge proofs (standard).
      - ZK-SD:   ZK with Selective Disclosure — compliance-grade privacy
                 (e.g., GDPR-compatible; Midnight's model).
    """
    name: str
    security: float             # s_e ∈ [0, 1]
    latency_ms: int             # l_e — median confirmation time (ms)
    finality_ms: int            # f_e — time to economic irreversibility (ms)
    privacy: str                # π_e ∈ {Public, TEE, ZK, ZK-SD}
    sovereignty: str            # v_e ∈ {Shared, Sovereign}
    cost_usd: float             # c_e — median gas cost (USD)
    cost_jitter_pct: float      # ±variance as fraction of median cost
    latency_jitter_pct: float   # ±variance as fraction of median latency
    formally_verified: bool     # True if consensus/VM has formal proofs


@dataclass
class TransactionIntent:
    """A transaction intent from an autonomous agent."""
    agent_id: int
    value_usd: float
    min_security: float
    max_latency_ms: int
    requires_privacy: bool
    requires_sovereignty: bool
    max_cost_usd: float
    requires_compliance_privacy: bool = False  # True → ZK-SD only
    requires_formal_verification: bool = False # True → formally-verified chains
    max_finality_ms: Optional[int] = None      # None = don't care


@dataclass
class RoutingResult:
    """Result of a routing decision."""
    selected: Optional[str]          # Chain name, or None if rejected/unroutable
    evaluations: int                  # Number of predicate evaluations
    entropy_profile: List[float]      # H(F) at each evaluation step
    is_pareto_optimal: bool           # Whether selection is Pareto-optimal
    rejected: bool = False            # True if a hard constraint could not be met
    rejection_reason: Optional[str] = None  # Human-readable rejection cause


# ═══════════════════════════════════════════════════════════════════════════
#  CHAIN CONFIGURATIONS (Appendix A of paper)
# ═══════════════════════════════════════════════════════════════════════════
#
#  finality_ms reference values:
#    Ethereum:  ~13 min (2 epochs × 32 slots × 12s)  = 780,000 ms
#    Polygon:   ~4.3 min (256 blocks × 2s checkpoints) = 256,000 ms
#    Avalanche: ~2s (sub-second with Snowman++)        = 2,000 ms
#    Solana:    ~6.4s (confirmed commitment)            = 6,400 ms
#    Arbitrum:  ~7d (optimistic rollup challenge window) = 604,800,000 ms
#    Phala:     ~3s (parachain finality)                 = 3,000 ms
#    Oasis:     ~6s (Tendermint BFT instant finality)    = 6,000 ms
#    Base:      ~7d (optimistic rollup challenge window)  = 604,800,000 ms
#    Cardano:   ~12 min (36 slots × 20s Ouroboros)       = 720,000 ms
#    Midnight:  ~1 min (Cardano sidechain, faster epoch)  = 60,000 ms
#
# ═══════════════════════════════════════════════════════════════════════════

CHAINS: List[ExecutionEnvironment] = [
    # ── Account-model L1s ─────────────────────────────────────────────────
    ExecutionEnvironment(
        "Ethereum",  0.99, 12_000, 780_000,
        "Public", "Shared", 8.50,
        cost_jitter_pct=0.40, latency_jitter_pct=0.30,
        formally_verified=False,
    ),
    ExecutionEnvironment(
        "Avalanche", 0.95, 2_000, 2_000,
        "Public", "Sovereign", 0.25,
        cost_jitter_pct=0.25, latency_jitter_pct=0.15,
        formally_verified=False,
    ),
    ExecutionEnvironment(
        "Solana", 0.85, 400, 6_400,
        "Public", "Shared", 0.001,
        cost_jitter_pct=0.30, latency_jitter_pct=0.25,
        formally_verified=False,
    ),

    # ── L2 Rollups ────────────────────────────────────────────────────────
    ExecutionEnvironment(
        "Polygon", 0.92, 800, 256_000,
        "Public", "Shared", 0.01,
        cost_jitter_pct=0.20, latency_jitter_pct=0.20,
        formally_verified=False,
    ),
    ExecutionEnvironment(
        "Arbitrum", 0.94, 1_500, 604_800_000,
        "Public", "Shared", 0.10,
        cost_jitter_pct=0.35, latency_jitter_pct=0.20,
        formally_verified=False,
    ),
    ExecutionEnvironment(
        "Base", 0.91, 1_000, 604_800_000,
        "Public", "Shared", 0.05,
        cost_jitter_pct=0.25, latency_jitter_pct=0.20,
        formally_verified=False,
    ),

    # ── Privacy chains ────────────────────────────────────────────────────
    ExecutionEnvironment(
        "Phala", 0.90, 3_000, 3_000,
        "TEE", "Shared", 0.50,
        cost_jitter_pct=0.20, latency_jitter_pct=0.30,
        formally_verified=False,
    ),
    ExecutionEnvironment(
        "Oasis", 0.88, 6_000, 6_000,
        "ZK", "Sovereign", 0.30,
        cost_jitter_pct=0.20, latency_jitter_pct=0.20,
        formally_verified=False,
    ),

    # ── eUTXO / Cardano ecosystem ─────────────────────────────────────────
    ExecutionEnvironment(
        "Cardano", 0.97, 20_000, 720_000,
        "Public", "Sovereign", 0.25,
        cost_jitter_pct=0.15, latency_jitter_pct=0.10,
        formally_verified=True,   # Ouroboros Praos, Haskell/Agda proofs
    ),
    ExecutionEnvironment(
        "Midnight", 0.93, 10_000, 60_000,
        "ZK-SD", "Sovereign", 0.40,
        cost_jitter_pct=0.20, latency_jitter_pct=0.15,
        formally_verified=True,   # Cardano sidechain, ZK + selective disclosure
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
#  STOCHASTIC JITTER — simulates volatile gas markets per trial
# ═══════════════════════════════════════════════════════════════════════════

def sample_env(base: ExecutionEnvironment, rng: random.Random) -> ExecutionEnvironment:
    """Return a runtime snapshot with per-trial jitter applied."""
    def jitter(val: float, pct: float) -> float:
        return val * (1.0 + rng.uniform(-pct, pct))

    return replace(base,
        latency_ms=max(50, int(jitter(base.latency_ms, base.latency_jitter_pct))),
        cost_usd=max(0.0001, jitter(base.cost_usd, base.cost_jitter_pct)),
    )


def sample_all(chains: List[ExecutionEnvironment],
               rng: random.Random) -> List[ExecutionEnvironment]:
    """Sample jittered snapshots for all chains."""
    return [sample_env(c, rng) for c in chains]


# ═══════════════════════════════════════════════════════════════════════════
#  ENTROPY CALCULATION
# ═══════════════════════════════════════════════════════════════════════════

def shannon_entropy(feasible_set: List[ExecutionEnvironment]) -> float:
    """Calculate Shannon entropy H(F) assuming uniform distribution."""
    n = len(feasible_set)
    if n <= 1:
        return 0.0
    return math.log2(n)


# ═══════════════════════════════════════════════════════════════════════════
#  CLR ROUTING (Algorithm 1 from paper)
# ═══════════════════════════════════════════════════════════════════════════

def clr_route(intent: TransactionIntent, chains: List[ExecutionEnvironment]) -> RoutingResult:
    """
    CLR routing — Neuro-symbolic Safety Guardrail implementation.

    Architecture:
      STAGE 0: HARD FILTER (Symbolic Guardrail)
        Privacy, sovereignty, and compliance requirements are NON-NEGOTIABLE.
        If the hard-filtered set is empty, the transaction is REJECTED
        (returns selected=None, rejected=True). No soft fallback occurs.

      STAGE 1: SOFT FILTER (Entropy-Greedy Optimisation)
        Once safety is guaranteed by Stage 0, the remaining constraints
        (latency, finality, cost, formal verification) are applied greedily
        by information gain. Skipping a predicate is allowed here only if
        it would empty the set, because all remaining chains are already safe.

    This two-stage split ensures safety properties are never traded for
    liveness, aligning with the neuro-symbolic agent safety literature.
    """
    # ── STAGE 0: HARD FILTER —————————————————————————————————————————————
    # Minimum security threshold is always a hard requirement.
    feasible = [e for e in chains if e.security >= intent.min_security]

    if not feasible:
        return RoutingResult(
            selected=None, evaluations=0, entropy_profile=[0.0],
            is_pareto_optimal=False, rejected=True,
            rejection_reason="No chain meets minimum security threshold"
        )

    evaluations = 0

    # Compliance privacy: HARD CONSTRAINT — ZK-SD chains only (Midnight).
    if intent.requires_compliance_privacy:
        compliant = [e for e in feasible if e.privacy == "ZK-SD"]
        evaluations += 1
        if not compliant:
            return RoutingResult(
                selected=None, evaluations=evaluations,
                entropy_profile=[shannon_entropy(feasible), 0.0],
                is_pareto_optimal=False, rejected=True,
                rejection_reason="Compliance privacy (ZK-SD) required but unavailable"
            )
        feasible = compliant

    # Privacy: HARD CONSTRAINT — route only to TEE/ZK/ZK-SD chains.
    elif intent.requires_privacy:
        privacy_safe = [e for e in feasible if e.privacy in ("TEE", "ZK", "ZK-SD")]
        evaluations += 1
        if not privacy_safe:
            return RoutingResult(
                selected=None, evaluations=evaluations,
                entropy_profile=[shannon_entropy(feasible), 0.0],
                is_pareto_optimal=False, rejected=True,
                rejection_reason="Privacy required but no TEE/ZK chain available"
            )
        feasible = privacy_safe

    # Sovereignty: HARD CONSTRAINT — route only to sovereign chains.
    if intent.requires_sovereignty:
        sovereign_safe = [e for e in feasible if e.sovereignty == "Sovereign"]
        evaluations += 1
        if not sovereign_safe:
            return RoutingResult(
                selected=None, evaluations=evaluations,
                entropy_profile=[shannon_entropy(feasible), 0.0],
                is_pareto_optimal=False, rejected=True,
                rejection_reason="Sovereignty required but no sovereign chain available"
            )
        feasible = sovereign_safe

    # Single chain survives hard filter → no further evaluation needed.
    entropy_profile = [shannon_entropy(feasible)]

    if len(feasible) == 1:
        entropy_profile.append(0.0)
        return RoutingResult(
            selected=feasible[0].name, evaluations=evaluations,
            entropy_profile=entropy_profile, is_pareto_optimal=True
        )

    # ── STAGE 1: SOFT ENTROPY-GREEDY FILTER ——————————————————————————————
    # Remaining constraints are soft: skip a predicate only if it would
    # empty the feasible set (all safe chains happen to fail it).
    soft_predicates = [
        ("value",    lambda e: e.security >= 0.93 if intent.value_usd > 10000 else True),
        ("latency",  lambda e: e.latency_ms <= intent.max_latency_ms),
        ("finality", lambda e: e.finality_ms <= intent.max_finality_ms
                              if intent.max_finality_ms else True),
        ("cost",     lambda e: e.cost_usd <= intent.max_cost_usd),
        ("formal",   lambda e: e.formally_verified
                              if intent.requires_formal_verification else True),
    ]

    for name, predicate in soft_predicates:
        if len(feasible) <= 1:
            break

        passed = [e for e in feasible if predicate(e)]
        evaluations += 1

        # Apply only if it actually filters AND does not empty the set.
        if 0 < len(passed) < len(feasible):
            feasible = passed

        entropy_profile.append(shannon_entropy(feasible))

    # Tie-breaking: lowest cost among the remaining safe chains.
    if len(feasible) > 1:
        feasible.sort(key=lambda e: e.cost_usd)

    entropy_profile.append(0.0)  # Final: selection collapsed to 1 chain.

    return RoutingResult(
        selected=feasible[0].name,
        evaluations=evaluations,
        entropy_profile=entropy_profile,
        is_pareto_optimal=True  # Post-hoc Pareto check applied by caller
    )


def random_route(intent: TransactionIntent, chains: List[ExecutionEnvironment]) -> RoutingResult:
    """Baseline: random chain selection from feasible set."""
    feasible = [e for e in chains if e.security >= intent.min_security]
    if not feasible:
        return RoutingResult(None, 0, [], False)
    selected = random.choice(feasible)
    return RoutingResult(selected.name, 0, [], False)


def roundrobin_route(intent: TransactionIntent, chains: List[ExecutionEnvironment],
                     counter: int) -> RoutingResult:
    """Baseline: round-robin chain selection."""
    feasible = [e for e in chains if e.security >= intent.min_security]
    if not feasible:
        return RoutingResult(None, 0, [], False)
    selected = feasible[counter % len(feasible)]
    return RoutingResult(selected.name, 0, [], False)


def ethereum_only(intent: TransactionIntent, chains: List[ExecutionEnvironment]) -> RoutingResult:
    """Baseline: always route to Ethereum."""
    eth = [e for e in chains if e.name == "Ethereum"][0]
    return RoutingResult(eth.name, 0, [], False)


# ═══════════════════════════════════════════════════════════════════════════
#  PARETO OPTIMALITY CHECK
# ═══════════════════════════════════════════════════════════════════════════

def compute_pareto_optimal(intent: TransactionIntent, chains: List[ExecutionEnvironment]) -> List[str]:
    """Compute the Pareto-optimal set for a given intent."""
    feasible = []
    for e in chains:
        if e.security < intent.min_security:
            continue
        if e.latency_ms > intent.max_latency_ms:
            continue
        if intent.requires_compliance_privacy and e.privacy != "ZK-SD":
            continue
        if intent.requires_privacy and e.privacy == "Public":
            continue
        if intent.requires_sovereignty and e.sovereignty != "Sovereign":
            continue
        if e.cost_usd > intent.max_cost_usd:
            continue
        feasible.append(e)

    if not feasible:
        return []

    # Pareto front: no other feasible chain dominates on all dimensions
    pareto = []
    for e in feasible:
        dominated = False
        for f in feasible:
            if f.name == e.name:
                continue
            if (f.security >= e.security and
                f.latency_ms <= e.latency_ms and
                f.cost_usd <= e.cost_usd and
                (f.security > e.security or
                 f.latency_ms < e.latency_ms or
                 f.cost_usd < e.cost_usd)):
                dominated = True
                break
        if not dominated:
            pareto.append(e.name)

    return pareto


# ═══════════════════════════════════════════════════════════════════════════
#  INTENT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

def generate_intent(agent_id: int) -> TransactionIntent:
    """Generate a random transaction intent with v2 fields."""
    r = random.random()

    # Compliance privacy: ~5% of intents (GDPR agents)
    requires_compliance = r < 0.05
    # Standard privacy: ~25% of remaining (total privacy ~30%)
    requires_privacy = (not requires_compliance) and (random.random() < 0.25)

    # Finality: ~15% of intents care about finality
    max_finality_ms = None
    if random.random() < 0.15:
        max_finality_ms = random.choice([10_000, 60_000, 300_000, 720_000])

    return TransactionIntent(
        agent_id=agent_id,
        value_usd=random.choice([100, 1000, 5000, 10000, 50000, 100000]),
        min_security=random.choice([0.80, 0.85, 0.90, 0.93, 0.95]),
        max_latency_ms=random.choice([500, 1000, 2000, 5000, 15000, 25000]),
        requires_privacy=requires_privacy,
        requires_sovereignty=random.random() < 0.2,
        max_cost_usd=random.choice([0.05, 0.50, 1.00, 5.00, 10.00]),
        requires_compliance_privacy=requires_compliance,
        requires_formal_verification=random.random() < 0.10,
        max_finality_ms=max_finality_ms,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN SIMULATION
# ═══════════════════════════════════════════════════════════════════════════

def run_simulation(n_agents: int = 1000, n_trials: int = 10000, seed: int = 42):
    """Run the full CLR evaluation simulation (strict guardrail mode)."""
    rng = random.Random(seed)
    random.seed(seed)

    print("=" * 70)
    print("  CLR Routing Simulation v2 -- Strict Guardrail Mode")
    print("  (Privacy, Compliance & Sovereignty are hard safety constraints)")
    print("=" * 70)
    print(f"  Agents: {n_agents}")
    print(f"  Trials: {n_trials}")
    print(f"  Chains: {len(CHAINS)}")
    print(f"  Seed:   {seed}")
    print(f"  Jitter: ENABLED (per-trial cost & latency variance)")
    print("=" * 70)

    # ── Run trials ───────────────────────────────────────────────────────
    clr_results = []
    random_results = []
    roundrobin_results = []
    ethonly_results = []

    for i in range(n_trials):
        agent_id = random.randint(0, n_agents - 1)
        intent = generate_intent(agent_id)

        # Per-trial jitter: each strategy sees the same snapshot
        snapshot = sample_all(CHAINS, rng)

        pareto_set = compute_pareto_optimal(intent, snapshot)

        # CLR
        clr_r = clr_route(intent, snapshot)
        clr_r.is_pareto_optimal = clr_r.selected in pareto_set if pareto_set else False
        clr_results.append(clr_r)

        # Random
        rand_r = random_route(intent, snapshot)
        rand_r.is_pareto_optimal = rand_r.selected in pareto_set if pareto_set else False
        random_results.append(rand_r)

        # Round-Robin
        rr_r = roundrobin_route(intent, snapshot, i)
        rr_r.is_pareto_optimal = rr_r.selected in pareto_set if pareto_set else False
        roundrobin_results.append(rr_r)

        # Ethereum-Only
        eth_r = ethereum_only(intent, snapshot)
        eth_r.is_pareto_optimal = eth_r.selected in pareto_set if pareto_set else False
        ethonly_results.append(eth_r)

    # ── Compute statistics ───────────────────────────────────────────────
    # Build chain lookup from base CHAINS (median values for finality)
    chain_finalities = {c.name: c.finality_ms for c in CHAINS}

    def stats(results: List[RoutingResult], label: str):
        total = len(results)
        rejected = sum(1 for r in results if r.rejected)
        rejection_pct = rejected / total * 100

        pareto_pct = sum(1 for r in results if r.is_pareto_optimal) / total * 100

        chain_costs = {c.name: c.cost_usd for c in CHAINS}
        chain_latencies = {c.name: c.latency_ms for c in CHAINS}

        valid = [r for r in results if r.selected is not None]
        avg_cost = sum(chain_costs.get(r.selected, 0) for r in valid) / max(len(valid), 1)
        avg_latency = sum(chain_latencies.get(r.selected, 0) for r in valid) / max(len(valid), 1)
        avg_finality_s = sum(
            chain_finalities.get(r.selected, 0) for r in valid
        ) / max(len(valid), 1) / 1000.0

        return {
            "label": label,
            "pareto_pct": pareto_pct,
            "avg_cost": avg_cost,
            "avg_latency": avg_latency,
            "avg_finality_s": avg_finality_s,
            "rejected": rejected,
            "rejection_pct": rejection_pct,
        }

    clr_stats = stats(clr_results, "CLR (Strict)")
    rand_stats = stats(random_results, "Random")
    rr_stats = stats(roundrobin_results, "Round-Robin")
    eth_stats = stats(ethonly_results, "Ethereum-Only")

    # ── Print Table 1 ────────────────────────────────────────────────────
    print("\n" + "-" * 85)
    print("  TABLE 1: Routing Performance Comparison (Strict Guardrail Mode, 10 chains)")
    print("-" * 85)
    print(f"  {'Strategy':<16} {'Pareto %':>10} {'Avg Cost ($)':>13} "
          f"{'Avg Lat (ms)':>13} {'Avg Final (s)':>14} {'Rejected %':>11}")
    print("  " + "-" * 81)
    for s in [rand_stats, rr_stats, eth_stats, clr_stats]:
        print(f"  {s['label']:<16} {s['pareto_pct']:>9.1f}% {s['avg_cost']:>12.2f} "
              f"{s['avg_latency']:>12.0f} {s['avg_finality_s']:>13.1f} "
              f"{s['rejection_pct']:>10.1f}%")

    # ── Entropy Profile ──────────────────────────────────────────────────
    max_steps = 8
    entropy_sums = [0.0] * max_steps
    entropy_counts = [0] * max_steps

    for r in clr_results:
        for j, h in enumerate(r.entropy_profile):
            if j < max_steps:
                entropy_sums[j] += h
                entropy_counts[j] += 1

    print("\n" + "-" * 70)
    print("  FIGURE 1: Mean Entropy at Each Evaluation Step")
    print("-" * 70)
    print(f"  {'Step j':>8}  {'H (bits)':>10}  {'Samples':>10}")
    print("  " + "-" * 32)
    for j in range(max_steps):
        if entropy_counts[j] > 0:
            avg_h = entropy_sums[j] / entropy_counts[j]
            print(f"  {j:>8}  {avg_h:>10.3f}  {entropy_counts[j]:>10}")

    # ── Mean evaluations ─────────────────────────────────────────────────
    mean_evals = sum(r.evaluations for r in clr_results) / len(clr_results)
    print(f"\n  Mean evaluations per decision: {mean_evals:.1f}")
    print(f"  Theoretical minimum (log2 {len(CHAINS)}): {math.log2(len(CHAINS)):.1f}")

    # ── Scalability ──────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("  SCALABILITY: Evaluations vs. Number of Chains")
    print("-" * 70)
    for n_chains in [4, 8, 10, 16, 32, 64]:
        test_chains = CHAINS[:min(n_chains, len(CHAINS))]
        while len(test_chains) < n_chains:
            test_chains.append(ExecutionEnvironment(
                f"Chain_{len(test_chains)}",
                0.80 + random.random() * 0.19,
                random.randint(200, 15000),
                random.randint(2000, 800_000),
                random.choice(["Public", "TEE", "ZK", "ZK-SD"]),
                random.choice(["Shared", "Sovereign"]),
                random.random() * 10,
                cost_jitter_pct=0.20,
                latency_jitter_pct=0.20,
                formally_verified=random.random() < 0.2,
            ))

        trial_evals = []
        for _ in range(1000):
            intent = generate_intent(0)
            r = clr_route(intent, test_chains)
            trial_evals.append(r.evaluations)

        mean_e = sum(trial_evals) / len(trial_evals)
        print(f"  |E| = {n_chains:>3}  ->  Mean evaluations: {mean_e:.1f}  "
              f"(log2: {math.log2(n_chains):.1f})")

    # ── Chain selection distribution ─────────────────────────────────────
    print("\n" + "-" * 70)
    print("  CLR Chain Selection Distribution (excluding rejections)")
    print("-" * 70)
    total_trials = len(clr_results)
    selections = Counter(r.selected for r in clr_results if r.selected)
    for chain, count in selections.most_common():
        pct = count / total_trials * 100
        bar = "#" * int(pct / 2)
        print(f"  {chain:<12} {count:>5} ({pct:>5.1f}%)  {bar}")

    # ── Rejection breakdown ───────────────────────────────────────────────
    rejected = [r for r in clr_results if r.rejected]
    if rejected:
        print("\n" + "-" * 70)
        print("  CLR REJECTION BREAKDOWN (Strict Guardrail)")
        print("-" * 70)
        reasons = Counter(r.rejection_reason for r in rejected)
        for reason, count in reasons.most_common():
            pct = count / total_trials * 100
            print(f"  {count:>5} ({pct:>5.1f}%)  {reason}")
        print(f"  Total rejected: {len(rejected)} / {total_trials} "
              f"({len(rejected)/total_trials*100:.1f}%)")
        print("  -> These transactions require human review or alternative routing.")

    # ── Export to CSV ────────────────────────────────────────────────────
    output_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(output_dir, "results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Strategy", "Pareto_Pct", "Avg_Cost", "Avg_Latency",
                         "Avg_Finality_s", "Rejection_Pct"])
        for s in [clr_stats, rand_stats, rr_stats, eth_stats]:
            writer.writerow([s['label'], f"{s['pareto_pct']:.1f}",
                            f"{s['avg_cost']:.2f}", f"{s['avg_latency']:.0f}",
                            f"{s['avg_finality_s']:.1f}",
                            f"{s['rejection_pct']:.1f}"])

    print(f"\n  Results exported to: {csv_path}")
    print("=" * 70)
    print("  Simulation complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_simulation()
