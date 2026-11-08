"""Local public CLR timing-boundary tests; all dependencies are injected."""
import copy
from decimal import Decimal
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True), patch(
    "requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden")
):
    from neuron import clr_router as clr
    from neuron import chain_oracle
    from neuron.sdk import oms_identity

APIS = ("route", "route_v3")
FIELDS = ("max_latency_ms", "max_finality_ms")


class NoValueHooks:
    def __init__(self): self.calls = []
    def forbidden(self, name):
        self.calls.append(name)
        raise AssertionError("Malformed input hook must not run")
    def __str__(self): return self.forbidden("str")
    def __repr__(self): return self.forbidden("repr")
    def __float__(self): return self.forbidden("float")
    def __int__(self): return self.forbidden("int")
    def __lt__(self, other): return self.forbidden("lt")
    def __gt__(self, other): return self.forbidden("gt")
    def __mul__(self, other): return self.forbidden("mul")


INVALID = {
    "nan": lambda: float("nan"), "positive_infinity": lambda: float("inf"),
    "negative_infinity": lambda: -float("inf"), "negative_integer": lambda: -1,
    "negative_float": lambda: -0.125, "true": lambda: True, "false": lambda: False,
    "none": lambda: None, "text": lambda: "0", "nan_text": lambda: "nan",
    "bytes": lambda: b"0", "list": lambda: [], "mapping": lambda: {},
    "hooks": NoValueHooks, "complex": lambda: complex(1, 0),
    "decimal": lambda: Decimal("1"), "fraction": lambda: Fraction(1, 1),
}


class CLRTimingValidationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        env.start(); self.addCleanup(env.stop)
        self.guards = []
        for module, name in ((clr, "OracleManager"), (chain_oracle, "OracleManager"),
                             (clr, "OMSIdentityVerifier"), (oms_identity, "OMSIdentityVerifier")):
            guard = patch.object(module, name, side_effect=AssertionError("Real constructor forbidden"))
            self.guards.append(guard.start()); self.addCleanup(guard.stop)
        guard = patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden"))
        self.guards.append(guard.start()); self.addCleanup(guard.stop)
        self.metric = chain_oracle.ChainMetrics(chain="Ethereum", gas_price_gwei=1.0,
            block_time_ms=3000, last_block=1, congestion_pct=20.0,
            finality_ms=500, timestamp=1_000_000.0)
        self.oracle = Mock(spec=["get_all_metrics"])
        self.oracle.get_all_metrics.return_value = {"Ethereum": self.metric}
        # Synthetic routing compatibility only, not live compliance evidence.
        self.verifier = Mock(spec=["is_compliance_verified"])
        self.verifier.is_compliance_verified.return_value = True
        self.router = clr.CLRouter(oracle=self.oracle, identity_verifier=self.verifier)
        self.seed = self.router.route(clr.TransactionIntent(10, 30000, False), clr.TrustTier.BRONZE)
        self.oracle.reset_mock(); self.verifier.reset_mock()
        self.hasher = Mock(wraps=self.router._compute_routing_hash)
        self.router._compute_routing_hash = self.hasher
        self.stats_before = copy.deepcopy(self.router.get_stats())
        self.log_before = list(self.router.get_routing_log())
        self.log_object = self.router._routing_log

    def tearDown(self):
        for guard in self.guards: guard.assert_not_called()

    def request(self, api, **fields):
        data = dict(value_usd=10, max_latency_ms=30000, max_finality_ms=0,
            requires_privacy=False, use_case_id="synthetic-timing-swap")
        data.update(fields)
        model = clr.TransactionIntent if api == "route" else clr.VAMSTransactionMetadata
        return model(**data)

    def reject(self, api, error_field, tier=clr.TrustTier.PLATINUM, **fields):
        request = self.request(api, **fields)
        original = dict(vars(request))
        blocks = list(request.loaded_service_blocks)
        error = None
        with self.assertNoLogs(clr.logger, level="DEBUG"):
            try: getattr(self.router, api)(request, tier)
            except Exception as caught: error = caught
        self.assertIs(type(error), ValueError)
        self.assertEqual(str(error), "Transaction " + error_field + " must be a finite non-negative number")
        self.assertIsNone(error.__cause__)
        self.oracle.get_all_metrics.assert_not_called()
        self.verifier.is_compliance_verified.assert_not_called()
        self.hasher.assert_not_called()
        self.assertEqual(self.router.get_stats(), self.stats_before)
        self.assertIs(self.router._routing_log, self.log_object)
        self.assertEqual(self.router.get_routing_log(), self.log_before)
        self.assertIs(self.router.get_routing_log()[0], self.seed)
        self.assertEqual(set(vars(request)), set(original))
        for name, value in original.items():
            self.assertIs(getattr(request, name), value)
            if isinstance(value, NoValueHooks): self.assertEqual(value.calls, [])
        self.assertEqual(request.loaded_service_blocks, blocks)

    def success(self, api, chain, priority, feasible=1, **fields):
        request = self.request(api, **fields)
        decision = getattr(self.router, api)(request, clr.TrustTier.PLATINUM)
        self.assertEqual(decision.chain, chain)
        self.assertEqual(decision.priority, priority)
        self.assertEqual(decision.feasible_chains, feasible)
        self.oracle.get_all_metrics.assert_called_once_with()
        self.hasher.assert_called_once()
        metadata, hashed_decision = self.hasher.call_args.args
        self.assertIs(hashed_decision, decision)
        for field in ("value_usd",) + FIELDS:
            self.assertIs(getattr(metadata, field), getattr(request, field))
            if field in fields:
                self.assertIs(getattr(metadata, field), fields[field])
        for field in FIELDS:
            value = getattr(request, field)
            if isinstance(value, float) and value == 0.0:
                self.assertEqual(math.copysign(1.0, getattr(metadata, field)), math.copysign(1.0, value))
        payload = (f"{metadata.use_case_id}:{metadata.value_usd}:{metadata.max_latency_ms}:"
                   f"{metadata.requires_privacy}:{metadata.requires_compliance_privacy}:"
                   f"{metadata.requires_formal_verification}:{chain}:{priority.value}")
        self.assertEqual(decision.routing_hash, hashlib.sha256(payload.encode()).hexdigest()[:16])
        self.assertEqual(decision.target_bridge, clr.STATIC_CHAINS[chain].bridge_transport)
        self.assertIs(decision.metrics, self.metric if chain == "Ethereum" else None)
        fees = {"Ethereum": 0.063, "Polygon": 0.01, "Midnight": 0.30, "Phala": 0.05,
                "Cardano": 0.20, "Hydra": 0.0001, "SEI": 0.002, "Solana": 0.001}
        self.assertAlmostEqual(decision.fee_estimate_usd, fees[chain])
        stats = self.router.get_stats()
        self.assertEqual(stats["total_routed"], self.stats_before["total_routed"] + 1)
        self.assertEqual(stats["denied"], self.stats_before["denied"])
        self.assertEqual(stats["log_size"], self.stats_before["log_size"] + 1)
        self.assertEqual(stats["by_priority"][priority.value], self.stats_before["by_priority"][priority.value] + 1)
        self.assertEqual(stats["by_chain"][chain], self.stats_before["by_chain"].get(chain, 0) + 1)
        self.assertIs(self.router.get_routing_log()[-1], decision)
        if priority == clr.RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE:
            self.verifier.is_compliance_verified.assert_called_once_with("synthetic-subject")
        else: self.verifier.is_compliance_verified.assert_not_called()

    def test_actual_lane_source_is_used(self):
        self.assertEqual(Path(clr.__file__).resolve(), Path(__file__).resolve().parents[1] / "clr_router.py")
        self.assertEqual(clr.CLR_VELOCITY_THRESHOLD, 1000)
        self.assertEqual(clr.CLR_SECURITY_THRESHOLD, 10000)


def invalid_test(api, field, factory):
    def test(self): self.reject(api, field, **{field: factory()})
    return test


def valid_test(api, field, value):
    def test(self):
        if field == "max_latency_ms" and value < clr.CLR_VELOCITY_THRESHOLD:
            chain, priority, feasible = "SEI", clr.RoutingPriority.P5_VELOCITY, 1
        elif field == "max_finality_ms" and 0 < value < self.metric.finality_ms:
            # Preserve current no-feasible-route fallback, not a feasibility guarantee.
            chain, priority, feasible = "Polygon", clr.RoutingPriority.P6_DEFAULT, 0
        else: chain, priority, feasible = "Ethereum", clr.RoutingPriority.P6_DEFAULT, 1
        self.success(api, chain, priority, feasible, **{field: value})
    return test


def precedence_test(api, case):
    def test(self):
        if case == "amount_first":
            self.reject(api, "value_usd", value_usd=float("nan"), max_latency_ms=NoValueHooks(), max_finality_ms=NoValueHooks())
        elif case == "latency_first":
            self.reject(api, "max_latency_ms", max_latency_ms=float("nan"), max_finality_ms=NoValueHooks())
        else:
            self.reject(api, "max_latency_ms", clr.TrustTier.UNVERIFIED,
                max_latency_ms=-1, max_finality_ms=-1, requires_institutional_compliance=True)
    return test


def boundary_test(api, field, delta, fractional=False):
    def test(self):
        if field == "max_latency_ms":
            limit = 1000.25 if fractional else 1000
            self.metric.block_time_ms = limit * 3 + delta
            fields = {field: limit}
        else:
            limit = 500
            self.metric.finality_ms = limit + delta
            fields = {field: limit}
        accepted = delta <= 0
        self.success(api, "Ethereum" if accepted else "Polygon", clr.RoutingPriority.P6_DEFAULT,
                     1 if accepted else 0, **fields)
    return test


PRIORITIES = {
    "p0": ("Midnight", clr.RoutingPriority.P0_COMPLIANCE_PRIVACY,
        dict(requires_compliance_privacy=True, requires_confidential_compute=True,
             requires_institutional_compliance=True, requires_formal_verification=True)),
    "p1": ("Phala", clr.RoutingPriority.P1_CONFIDENTIAL_COMPUTE,
        dict(requires_privacy=True, requires_institutional_compliance=True, value_usd=20000)),
    "p2": ("Ethereum", clr.RoutingPriority.P2_HIGH_VALUE_SECURITY,
        dict(value_usd=20000, requires_institutional_compliance=True)),
    "p3": ("Polygon", clr.RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE,
        dict(requires_institutional_compliance=True, requires_formal_verification=True,
             agent_address="synthetic-subject", loaded_service_blocks=["ServiceBlock_OMS_v1"])),
    "p4": ("Cardano", clr.RoutingPriority.P4_FORMAL_VERIFICATION, dict(requires_formal_verification=True)),
    "p5_hydra": ("Hydra", clr.RoutingPriority.P5_VELOCITY, dict(requires_sub_second_settle=True)),
    "p5_solana": ("Solana", clr.RoutingPriority.P5_VELOCITY, dict(use_case_id="synthetic-inference")),
}


def priority_test(api, case):
    def test(self):
        chain, priority, fields = case
        self.success(api, chain, priority, max_latency_ms=0.125, max_finality_ms=0.125, **fields)
    return test


def denial_test(api):
    def test(self):
        request = self.request(api, value_usd=1001, max_latency_ms=0.125, max_finality_ms=0.125)
        with self.assertRaises(PermissionError) as caught:
            getattr(self.router, api)(request, clr.TrustTier.UNVERIFIED)
        self.assertEqual(str(caught.exception), "Transaction value $1001 exceeds UNVERIFIED limit ($1000). Verification required.")
        self.oracle.get_all_metrics.assert_not_called(); self.verifier.is_compliance_verified.assert_not_called()
        self.hasher.assert_not_called()
        self.assertEqual(self.router.get_stats(), {**self.stats_before, "denied": self.stats_before["denied"] + 1})
        self.assertEqual(self.router.get_routing_log(), self.log_before)
    return test


def invalid_institutional_test(api):
    def test(self):
        self.reject(api, "max_finality_ms", max_finality_ms=float("nan"),
            requires_institutional_compliance=True, agent_address="synthetic-subject",
            loaded_service_blocks=["ServiceBlock_OMS_v1"])
    return test


for _api in APIS:
    for _field in FIELDS:
        for _name, _factory in INVALID.items():
            setattr(CLRTimingValidationTests, "test_invalid_" + _api + "_" + _field + "_" + _name,
                    invalid_test(_api, _field, _factory))
        for _name, _value in (("zero_int", 0), ("zero_float", 0.0), ("negative_zero", -0.0),
                              ("fractional", 0.125), ("integer", 1), ("normal_float", 1000.25), ("huge_integer", 10**400)):
            setattr(CLRTimingValidationTests, "test_valid_" + _api + "_" + _field + "_" + _name,
                    valid_test(_api, _field, _value))
        for _delta in (-0.125, 0, 0.125):
            setattr(CLRTimingValidationTests, "test_comparison_" + _api + "_" + _field + "_" + str(_delta).replace("-", "minus"),
                    boundary_test(_api, _field, _delta))
    for _delta in (0, 0.125):
        setattr(CLRTimingValidationTests, "test_fractional_jitter_" + _api + "_" + str(_delta),
                boundary_test(_api, "max_latency_ms", _delta, True))
    for _name in ("amount_first", "latency_first", "validation_before_access"):
        setattr(CLRTimingValidationTests, "test_precedence_" + _api + "_" + _name, precedence_test(_api, _name))
    for _name, _case in PRIORITIES.items():
        setattr(CLRTimingValidationTests, "test_priority_" + _api + "_" + _name, priority_test(_api, _case))
    setattr(CLRTimingValidationTests, "test_valid_denial_accounting_" + _api, denial_test(_api))
    setattr(CLRTimingValidationTests, "test_invalid_institutional_no_verifier_" + _api, invalid_institutional_test(_api))


if __name__ == "__main__": unittest.main()
