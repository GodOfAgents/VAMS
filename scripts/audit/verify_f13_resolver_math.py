#!/usr/bin/env python3
"""Offline F13 documentation math checks; no release or operational acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/remediation/repair_20261125"
PLAN = DOCS / "F13-RESOLVER-ACCURACY-PLAN.md"
DESIGN = DOCS / "F13-BOND-FLOOR-DISPUTE-CAP-DESIGN.md"
CONTRACT = ROOT / "contracts/src/economic/DeliveryDisputeV1.sol"
UNIT = 10**18
ALPHA = F(1, 80)  # Four one-sided bounds, family error <= 0.05.


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def bond_for(amount: int) -> int:
    require(amount > 0, "Rows must have positive integer amounts")
    return max((amount * 500 + 9_999) // 10_000, UNIT)


def binomial_cdf(k: int, n: int, p: F) -> F:
    """Exact finite sum, including endpoints; independent of a stats package."""
    require(0 <= k <= n and 0 <= p <= 1, "Invalid binomial inputs")
    return sum(
        (math.comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(k + 1)),
        F(0),
    )


@lru_cache(maxsize=None)
def upper_bound(k: int, n: int, alpha: F = ALPHA) -> F | None:
    require(0 <= k <= n and 0 < alpha < 1, "Invalid bound inputs")
    if n == 0:
        return None  # UNKNOWN, never a zero-error bound.
    if k == n:
        return F(1)
    lo, hi = F(0), F(1)
    for _ in range(64):
        mid = (lo + hi) / 2
        if binomial_cdf(k, n, mid) > alpha:
            lo = mid
        else:
            hi = mid
    require(binomial_cdf(k, n, lo) >= alpha, "Root lower bracket")
    require(binomial_cdf(k, n, hi) <= alpha, "Root upper bracket")
    return hi  # Conservative dyadic upper bracket; error <= 2^-64.


def bound_strictly_below(k: int, n: int, target: F) -> bool:
    """Decide against an exact target without rounded percentages/root estimates."""
    require(0 <= k <= n and 0 < target < 1, "Invalid comparison inputs")
    return n > 0 and k < n and binomial_cdf(k, n, target) < ALPHA


def honest_loss(bond: F, upheld: int, rejected: int, timed_out: int) -> F:
    require(min(upheld, rejected, timed_out) >= 0, "Negative outcome count")
    total = upheld + rejected + timed_out
    require(total > 0, "No observations")
    return bond * F(rejected + timed_out, total)


def percent(value: F) -> str:
    return f"{float(100 * value):.4f}%"


def confidence_table() -> str:
    rows = [
        "| Decided cases n | 0 wrong decisions | 1 | 2 |",
        "|---|---|---|---|",
    ]
    for n in (63, 100, 120):
        bounds = [upper_bound(k, n) for k in range(3)]
        require(all(p is not None for p in bounds), "Missing table bound")
        rows.append(f"| {n} | " + " | ".join(percent(p) for p in bounds) + " |")
    return "\n".join(rows)


def floor_table() -> str:
    rows = [
        "| Row A (VAMS) | Bond B (VAMS) | Effective B/A | Honest success needed (strictly above) | Expected honest bond loss / row |",
        "|---|---|---|---|---|",
    ]
    for label in ("0.1", "1", "5", "20", "100"):
        amount = int(F(label) * UNIT)
        bond = bond_for(amount)
        threshold = F(bond, amount + bond)
        loss_ratio = F(7, 25) * F(bond, amount)
        rows.append(
            f"| {label} | {F(bond, UNIT)} | {F(bond, amount)} | "
            f"{percent(threshold)} | {percent(loss_ratio)} |"
        )
    return "\n".join(rows)


def table_block(path: Path, label: str, table: str, write: bool) -> None:
    begin = f"<!-- BEGIN F13 {label} TABLE -->"
    end = f"<!-- END F13 {label} TABLE -->"
    text = path.read_text(encoding="utf-8")
    require(text.count(begin) == text.count(end) == 1, f"Invalid markers: {path.name}")
    prefix, rest = text.split(begin)
    existing, suffix = rest.split(end)
    expected = "\n" + table + "\n"
    if write:
        path.write_text(prefix + begin + expected + end + suffix, encoding="utf-8", newline="\n")
    else:
        require(existing == expected, f"Stale math table: {path.name}")


def verify() -> list[str]:
    groups = []
    source = CONTRACT.read_text(encoding="utf-8")
    for name, value in (
        ("DISPUTE_WINDOW", "72 hours"), ("RESOLUTION_PERIOD", "14 days"),
        ("BOND_BPS", "500"), ("BPS_DENOMINATOR", "10_000"),
        ("MIN_BOND", "1e18"), ("MAX_OPEN_DISPUTES_PER_AGENT", "20"),
    ):
        require(re.search(rf"\b{name}\s*=\s*{re.escape(value)}\s*;", source) is not None,
                f"Approved contract parameter mismatch: {name}")
    groups.append("unchanged approved contract parameters")

    require(bond_for(1) == UNIT, "Dust floor")
    require(bond_for(20 * UNIT - 1) == UNIT, "Below crossover")
    require(bond_for(20 * UNIT) == UNIT, "Exact crossover")
    require(bond_for(20 * UNIT + 1) == UNIT + 1, "Rounded crossover")
    for amount in (1, UNIT // 10, UNIT - 1, UNIT, 5 * UNIT, 20 * UNIT, 100 * UNIT):
        require((bond_for(amount) > amount) == (amount < UNIT), "Bond > principal boundary")
    groups.append("integer floor/crossover/greater-than-principal boundaries")

    require(honest_loss(F(5), 72, 8, 20) == F(7, 5), "1.40 outcome-count regression")
    mixed = F(5) * (F(20, 100) + F(80, 100) * F(8, 100))
    require(mixed == F(33, 25) and mixed != F(7, 5), "Old 1.32 error reproduced")
    # Exhaust all small outcome histograms; compare counts to conditional formulas.
    for u in range(7):
        for r in range(7):
            for t in range(7):
                if u + r == 0:
                    continue  # Accuracy undefined; test that separately below.
                q = F(t, u + r + t)
                delta = F(r, u + r)
                expected = F(5) * (q + (1 - q) * delta)
                require(honest_loss(F(5), u, r, t) == expected, "Conditional/count identity")
                epsilon = F(u, u + r)
                by_counts = (u * F(100) - (r + t) * F(5)) / (u + r + t)
                require((1 - q) * epsilon * 105 - 5 == by_counts, "Meritless outcome identity")
    require(honest_loss(F(5), 0, 0, 100) == 5, "All-timeout loss")
    groups.append("outcome-count identities and original denominator counterexample")

    require(F(UNIT, UNIT + 1) > F(1, 21), "One-unit success threshold")
    require(1 - F(UNIT, UNIT + 1) == F(1, UNIT + 1), "One-unit failure bound")
    p_h = F(4, 5) * F(9, 10)
    require(p_h * F(1, 10) - (1 - p_h) == F(-26, 125), "Dust EV = -0.208")
    require((1 - p_h) / F(1, 10) == F(14, 5), "Dust loss = 280% of row")
    for amount in (F(1, 10), F(1), F(5), F(20), F(100)):
        b = F(bond_for(int(amount * UNIT)), UNIT)
        p_star = b / (amount + b)
        require(p_star * amount - (1 - p_star) * b == 0, "Honest break-even")
        require(p_star * (amount + b) - b == 0, "Meritless break-even at q=0")
        for q in (F(0), F(1, 5), F(1, 2)):
            eps_star = b / ((1 - q) * (amount + b))
            require((1 - q) * eps_star * (amount + b) - b == 0, "Timeout-aware threshold")
        for cost in (amount, amount + F(1, 100)):
            success_needed = (b + cost) / (amount + b)
            require(success_needed >= 1, "C >= A precludes positive honest EV")
    # 100 meritless cases: 4 wrong upholds, 46 rejections, 50 timeouts.
    actual_m = F(4 * 100 - 96 * 5, 100)
    conditional_m = (1 - F(1, 2)) * F(4, 50) * 105 - 5
    pooled_m = (1 - F(20 + 50, 200)) * F(4, 50) * 105 - 5
    require(actual_m == conditional_m == F(-4, 5), "Class-specific timeout example")
    require(pooled_m == F(23, 50) and pooled_m != actual_m, "Pooled q changes EV sign")
    groups.append("floor-row EV, strict thresholds and timeout endpoints")

    require(binomial_cdf(1, 10, F(1, 2)) == F(11, 1024), "Independent binomial identity")
    require(upper_bound(0, 0) is None, "No decisions must stay UNKNOWN")
    require(upper_bound(120, 120) == 1, "All errors upper bound")
    require(abs(upper_bound(0, 1) - (1 - ALPHA)) <= F(1, 2**64), "Analytic n=1 bound")
    for n in (63, 100, 120):
        p0 = upper_bound(0, n)
        require((1 - p0) ** n <= ALPHA, "Closed-form zero-error identity")
        require(p0 < upper_bound(1, n) < upper_bound(2, n), "Error-count monotonicity")
    require(upper_bound(0, 120) < upper_bound(0, 100), "Sample-size monotonicity")
    require(not bound_strictly_below(0, 0, F(1, 21)), "UNKNOWN cannot accept")
    require(not bound_strictly_below(0, 1, 1 - ALPHA), "Equality cannot accept")
    require(bound_strictly_below(0, 120, F(1, 21)), "120 decisions, zero errors")
    require(not bound_strictly_below(1, 120, F(1, 21)), "120 decisions, one error fails family bound")
    require(4 * ALPHA == F(1, 20), "Family confidence allocation")
    groups.append("exact binomial inversion, analytic endpoints and strict acceptance")

    # Latest schedule = deadline - delay - 1 second, not the inclusive day-12 boundary.
    deadline, delay = 14 * 86_400, 48 * 3_600
    require(deadline - delay == 12 * 86_400, "Day-12 arithmetic")
    require(deadline - delay - 1 + delay < deadline, "Latest legal scheduling second")
    require(not deadline - delay + delay < deadline, "Exact deadline excluded")
    groups.append("exclusive timelock resolution boundary")
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-tables", action="store_true", help="Update only the two marked doc tables")
    args = parser.parse_args()
    groups = verify()
    table_block(PLAN, "CONFIDENCE", confidence_table(), args.write_tables)
    table_block(DESIGN, "FLOOR", floor_table(), args.write_tables)
    # Verify after a write too, so the same final bytes must pass the ordinary check.
    table_block(PLAN, "CONFIDENCE", confidence_table(), False)
    table_block(DESIGN, "FLOOR", floor_table(), False)
    groups.append("documented tables match independently checked exact calculations")
    print(json.dumps({
        "status": "PASS", "verification_groups": groups,
        "evidence_type": "offline mathematical/source consistency; no resolver observations",
        "sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (CONTRACT, PLAN, DESIGN, Path(__file__))},
    }, indent=2))


if __name__ == "__main__":
    main()
