"""CLR risk-value boundary tests with injected local data, never providers."""
import copy
from decimal import Decimal
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

# Import actual lane modules under explicit non-live configuration and HTTP guard.
with patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True), patch(
    "requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden")
):
    from neuron import clr_router as clr
    from neuron import chain_oracle
    from neuron.sdk import oms_identity

REAL_OMS_VERIFIER = oms_identity.OMSIdentityVerifier
ERROR = "Transaction value_usd must be a finite non-negative number"
APIS = ("route", "route_v3")


class NoValueHooks:
    def __init__(self):
        self.calls = []

    def forbidden(self, name):
        self.calls.append(name)
        raise AssertionError("Invalid value hook must not run")

    def __str__(self): return self.forbidden("str")
    def __repr__(self): return self.forbidden("repr")
    def __float__(self): return self.forbidden("float")
    def __int__(self): return self.forbidden("int")
    def __lt__(self, other): return self.forbidden("lt")
    def __gt__(self, other): return self.forbidden("gt")


INVALID = {
    "nan": lambda: float("nan"),
    "positive_infinity": lambda: float("inf"),
    "negative_infinity": lambda: -float("inf"),
    "negative_integer": lambda: -1,
    "negative_float": lambda: -0.125,
    "boolean_true": lambda: True,
    "boolean_false": lambda: False,
    "none": lambda: None,
    "numeric_text": lambda: "0",
    "nan_text": lambda: "nan",
    "bytes": lambda: b"0",
    "list": lambda: [],
    "mapping": lambda: {},
    "object_hooks": NoValueHooks,
    "complex": lambda: complex(1, 0),
    "decimal": lambda: Decimal("1"),
    "fraction": lambda: Fraction(1, 1),
}


class CLRValueValidationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"VAMS_ENV": "test"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.guards = []
        for module, name in ((clr, "OracleManager"), (chain_oracle, "OracleManager"),
                             (clr, "OMSIdentityVerifier"), (oms_identity, "OMSIdentityVerifier")):
            guard = patch.object(module, name, side_effect=AssertionError("Real constructor forbidden"))
            self.guards.append(guard.start())
            self.addCleanup(guard.stop)
        transport = patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden"))
        self.guards.append(transport.start())
        self.addCleanup(transport.stop)
        self.metrics = {
            name: chain_oracle.ChainMetrics(chain=name, gas_price_gwei=1.0,
                block_time_ms=400, last_block=1, congestion_pct=20.0,
                finality_ms=500, timestamp=1_000_000.0)
            for name in clr.STATIC_CHAINS
        }
        self.oracle = Mock(spec=["get_all_metrics"])
        self.oracle.get_all_metrics.return_value = self.metrics
        # Routing compatibility double only, never live OMS verification evidence.
        self.verifier = Mock(spec=["is_compliance_verified"])
        self.verifier.is_compliance_verified.return_value = True
        self.router = clr.CLRouter(oracle=self.oracle, identity_verifier=self.verifier)
        self.seed = self.router.route(clr.TransactionIntent(10, 30_000, False), clr.TrustTier.BRONZE)
        self.oracle.reset_mock()
        self.verifier.reset_mock()
        self.hasher = Mock(wraps=self.router._compute_routing_hash)
        self.router._compute_routing_hash = self.hasher
        self.stats_before = copy.deepcopy(self.router.get_stats())
        self.log_before = list(self.router.get_routing_log())
        self.log_object = self.router._routing_log

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def make_input(self, api, value, **fields):
        values = dict(value_usd=value, max_latency_ms=30_000, requires_privacy=False,
                      use_case_id="synthetic-routing-case")
        values.update(fields)
        model = clr.TransactionIntent if api == "route" else clr.VAMSTransactionMetadata
        return model(**values)

    def invoke(self, api, value, tier=clr.TrustTier.PLATINUM, **fields):
        request = self.make_input(api, value, **fields)
        return request, getattr(self.router, api)(request, tier)

    def assert_unchanged_state(self):
        self.assertEqual(self.router.get_stats(), self.stats_before)
        self.assertIs(self.router._routing_log, self.log_object)
        self.assertEqual(self.router.get_routing_log(), self.log_before)
        self.assertIs(self.router.get_routing_log()[0], self.seed)
        self.hasher.assert_not_called()

    def reject_invalid(self, api, value, tier=clr.TrustTier.PLATINUM, **fields):
        request = self.make_input(api, value, requires_institutional_compliance=True,
            agent_address="synthetic-subject", loaded_service_blocks=["ServiceBlock_OMS_v1"], **fields)
        original = dict(vars(request))
        blocks = list(request.loaded_service_blocks)
        error = None
        with self.assertNoLogs(clr.logger, level="DEBUG"):
            try:
                getattr(self.router, api)(request, tier)
            except Exception as caught:
                error = caught
        # Normalized failure assertion also distinguishes old TypeError/hook calls.
        self.assertIs(type(error), ValueError)
        self.assertEqual(str(error), ERROR)
        self.assertIsNone(error.__cause__)
        self.oracle.get_all_metrics.assert_not_called()
        self.verifier.is_compliance_verified.assert_not_called()
        self.assert_unchanged_state()
        self.assertEqual(set(vars(request)), set(original))
        for name, original_value in original.items():
            self.assertIs(getattr(request, name), original_value)
        self.assertEqual(request.loaded_service_blocks, blocks)
        if isinstance(value, NoValueHooks):
            self.assertEqual(value.calls, [])

    def assert_success(self, api, value, priority, chain, tier=clr.TrustTier.PLATINUM, **fields):
        request, decision = self.invoke(api, value, tier, **fields)
        self.assertEqual(decision.priority, priority)
        self.assertEqual(decision.chain, chain)
        self.oracle.get_all_metrics.assert_called_once_with()
        self.hasher.assert_called_once()
        metadata, hashed_decision = self.hasher.call_args.args
        self.assertIs(metadata.value_usd, value)
        self.assertIs(request.value_usd, value)
        self.assertIs(hashed_decision, decision)
        payload = (f"{metadata.use_case_id}:{value}:{metadata.max_latency_ms}:"
                   f"{metadata.requires_privacy}:{metadata.requires_compliance_privacy}:"
                   f"{metadata.requires_formal_verification}:{chain}:{priority.value}")
        self.assertEqual(decision.routing_hash, hashlib.sha256(payload.encode()).hexdigest()[:16])
        self.assertIs(decision.metrics, self.metrics[chain])
        self.assertEqual(decision.target_bridge, clr.STATIC_CHAINS[chain].bridge_transport)
        expected_fee = 0.0001 if chain == "Hydra" else (0.063 if chain in ("Ethereum", "Polygon") else (0.0000105 if chain == "SEI" else (0.001 if chain in ("Cardano", "Midnight", "Solana") else 0.10)))
        self.assertAlmostEqual(decision.fee_estimate_usd, expected_fee)
        stats = self.router.get_stats()
        self.assertEqual(stats["total_routed"], self.stats_before["total_routed"] + 1)
        self.assertEqual(stats["denied"], self.stats_before["denied"])
        self.assertEqual(stats["log_size"], self.stats_before["log_size"] + 1)
        self.assertEqual(stats["by_priority"][priority.value], self.stats_before["by_priority"][priority.value] + 1)
        self.assertEqual(stats["by_chain"][chain], self.stats_before["by_chain"].get(chain, 0) + 1)
        self.assertIs(self.router.get_routing_log()[-1], decision)
        if priority == clr.RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE:
            self.verifier.is_compliance_verified.assert_called_once_with("synthetic-subject")
        else:
            self.verifier.is_compliance_verified.assert_not_called()
        return request, decision

    def assert_permission_denied(self, api, value, tier, message, **fields):
        request = self.make_input(api, value, **fields)
        with self.assertRaises(PermissionError) as caught:
            getattr(self.router, api)(request, tier)
        self.assertEqual(str(caught.exception), message)
        self.oracle.get_all_metrics.assert_not_called()
        self.verifier.is_compliance_verified.assert_not_called()
        self.hasher.assert_not_called()
        expected = copy.deepcopy(self.stats_before)
        expected["denied"] += 1
        self.assertEqual(self.router.get_stats(), expected)
        self.assertEqual(self.router.get_routing_log(), self.log_before)

    def test_actual_lane_module_is_used(self):
        self.assertEqual(Path(clr.__file__).resolve(), Path(__file__).resolve().parents[1] / "clr_router.py")
        self.assertEqual(clr.CLR_SECURITY_THRESHOLD, 10_000)
        self.assertEqual(clr.CLR_VELOCITY_THRESHOLD, 1_000)


def invalid_test(api, factory):
    def test(self): self.reject_invalid(api, factory())
    return test


def positive_test(api, value):
    def test(self):
        fields = {"requires_compliance_privacy": True} if value > 50_000 else {}
        priority = clr.RoutingPriority.P0_COMPLIANCE_PRIVACY if fields else clr.RoutingPriority.P6_DEFAULT
        chain = "Midnight" if fields else "Ethereum"
        request, _ = self.assert_success(api, value, priority, chain, **fields)
        if isinstance(value, float) and value == 0.0:
            self.assertEqual(math.copysign(1.0, request.value_usd), math.copysign(1.0, value))
    return test


def boundary_test(api, name):
    def test(self):
        if name == "unverified_at1000":
            self.assert_success(api, 1000, clr.RoutingPriority.P6_DEFAULT, "Ethereum", clr.TrustTier.UNVERIFIED)
        elif name == "unverified_above1000":
            self.assert_permission_denied(api, 1000.25, clr.TrustTier.UNVERIFIED,
                "Transaction value $1000.25 exceeds UNVERIFIED limit ($1000). Verification required.")
        elif name == "silver_at50000":
            self.assert_success(api, 50000, clr.RoutingPriority.P2_HIGH_VALUE_SECURITY, "Ethereum", clr.TrustTier.SILVER)
        elif name == "silver_above50000":
            self.assert_permission_denied(api, 50000.25, clr.TrustTier.SILVER,
                "Transaction value $50000.25 requires GOLD Tier. Current: SILVER")
        else:
            self.assert_success(api, 50001, clr.RoutingPriority.P2_HIGH_VALUE_SECURITY, "Ethereum", clr.TrustTier.GOLD)
    return test


def threshold_test(api, offset):
    def test(self):
        priority = clr.RoutingPriority.P2_HIGH_VALUE_SECURITY if offset > 0 else clr.RoutingPriority.P6_DEFAULT
        self.assert_success(api, clr.CLR_SECURITY_THRESHOLD + offset, priority, "Ethereum")
    return test


PRIORITIES = {
    "p0_precedence": (20000, "Midnight", clr.RoutingPriority.P0_COMPLIANCE_PRIVACY,
        dict(requires_compliance_privacy=True, requires_confidential_compute=True,
             requires_institutional_compliance=True, requires_formal_verification=True, max_latency_ms=500)),
    "p1_precedence": (20000, "Phala", clr.RoutingPriority.P1_CONFIDENTIAL_COMPUTE,
        dict(requires_privacy=True, requires_institutional_compliance=True, requires_formal_verification=True)),
    "p3_compatibility_double": (1000, "Polygon", clr.RoutingPriority.P3_INSTITUTIONAL_COMPLIANCE,
        dict(requires_institutional_compliance=True, agent_address="synthetic-subject",
             loaded_service_blocks=["ServiceBlock_OMS_v1"], requires_formal_verification=True)),
    "p4": (1000, "Cardano", clr.RoutingPriority.P4_FORMAL_VERIFICATION, dict(requires_formal_verification=True)),
    "p5_hydra": (1, "Hydra", clr.RoutingPriority.P5_VELOCITY, dict(max_latency_ms=500, requires_sub_second_settle=True)),
    "p5_sei": (1, "SEI", clr.RoutingPriority.P5_VELOCITY, dict(max_latency_ms=500, use_case_id="synthetic_swap")),
    "p5_solana": (1, "Solana", clr.RoutingPriority.P5_VELOCITY, dict(max_latency_ms=500, use_case_id="synthetic_inference")),
}


def priority_test(api, case):
    def test(self):
        value, chain, priority, fields = case
        self.assert_success(api, value, priority, chain, **fields)
    return test


def permission_test(api, institutional):
    def test(self):
        if institutional:
            self.assert_permission_denied(api, 1, clr.TrustTier.GOLD,
                "Institutional compliance routing requires PLATINUM Tier.", requires_institutional_compliance=True)
        else:
            self.assert_permission_denied(api, 1, clr.TrustTier.BRONZE,
                "ZK-SD (Compliance Privacy) requires SILVER Tier or higher.", requires_compliance_privacy=True)
    return test


def invalid_precedence_test(api):
    def test(self): self.reject_invalid(api, float("nan"), clr.TrustTier.UNVERIFIED)
    return test


def mock_oms_test(api):
    def test(self):
        # Explicit local mock mode needs no API credential and is non-authoritative.
        verifier = REAL_OMS_VERIFIER(mock_mode=True, environ={"VAMS_ENV": "test"})
        subject = "0x99synthetic-subject"
        result = verifier.verify_identity(subject)
        self.assertTrue(result.verified)
        self.assertTrue(result.simulated)
        self.assertEqual(result.evidence_classification, "non-authoritative")
        self.assertFalse(result.usable_for_compliance)
        self.assertEqual(verifier.api_key, "")
        self.assertEqual(verifier.api_url, "")
        self.router.identity_verifier = verifier
        request = self.make_input(api, 1000, requires_institutional_compliance=True,
            agent_address=subject, loaded_service_blocks=["ServiceBlock_OMS_v1"])
        with self.assertRaises(PermissionError) as caught:
            getattr(self.router, api)(request, clr.TrustTier.PLATINUM)
        self.assertEqual(str(caught.exception), "Institutional compliance routing requires a live OMS verified identity.")
        self.oracle.get_all_metrics.assert_called_once_with()
        self.hasher.assert_not_called()
        self.assertEqual(self.router.get_stats(), {**self.stats_before, "denied": self.stats_before["denied"] + 1})
        self.assertEqual(self.router.get_routing_log(), self.log_before)
        self.verifier.is_compliance_verified.assert_not_called()
    return test


for _api in APIS:
    for _name, _factory in INVALID.items():
        setattr(CLRValueValidationTests, "test_invalid_" + _api + "_" + _name, invalid_test(_api, _factory))
    for _name, _value in (("zero_int", 0), ("zero_float", 0.0), ("negative_zero", -0.0),
                          ("integer", 1), ("float", 1.25), ("unrounded_int", 2**53 + 1), ("huge_int", 10**400)):
        setattr(CLRValueValidationTests, "test_valid_" + _api + "_" + _name, positive_test(_api, _value))
    for _name in ("unverified_at1000", "unverified_above1000", "silver_at50000", "silver_above50000", "gold_above50000"):
        setattr(CLRValueValidationTests, "test_tier_" + _api + "_" + _name, boundary_test(_api, _name))
    for _offset in (-1, 0, 1):
        setattr(CLRValueValidationTests, "test_security_threshold_" + _api + "_" + str(_offset).replace("-", "minus"), threshold_test(_api, _offset))
    for _name, _case in PRIORITIES.items():
        setattr(CLRValueValidationTests, "test_priority_" + _api + "_" + _name, priority_test(_api, _case))
    for _institutional in (False, True):
        setattr(CLRValueValidationTests, "test_permission_" + _api + "_" + str(_institutional), permission_test(_api, _institutional))
    setattr(CLRValueValidationTests, "test_invalid_before_tier_denial_" + _api, invalid_precedence_test(_api))
    setattr(CLRValueValidationTests, "test_mock_oms_success_remains_noncompliant_" + _api, mock_oms_test(_api))


if __name__ == "__main__":
    unittest.main()
