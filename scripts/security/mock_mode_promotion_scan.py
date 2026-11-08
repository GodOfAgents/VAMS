#!/usr/bin/env python3
"""Verify live-mode mock guards are present at known VAMS integration boundaries."""

from __future__ import annotations

import sys
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_GUARDS = {
    "gateway/server.py": (
        "policy = load_runtime_policy()",
        "mock_mode=policy.gateway_mock_enabled",
    ),
    "neuron/runtime_safety.py": (
        "class RuntimeMode(str, Enum):",
        "class ImmutableRuntimeConfiguration:",
        "REGISTERED_MOCK_VARIABLES = (",
        "if mode in LIVE_MODES and enabled_mock_variables:",
        "if policy is not None and policy != observed:",
    ),
    "neuron/da/performance_audit.py": (
        'require_not_live_mock(\n            "PerformanceAuditLog"',
        "class PerformanceAuditLog(ImmutableRuntimeConfiguration):",
        "LIVE_CAPABLE_PROTOCOLS = {DAProtocol.CELESTIA}",
        '"release_evidence_eligible": False',
    ),
    "neuron/da/adapters/celestia_adapter.py": (
        "Live RPC failures never fall back to locally generated receipts",
        'raise DAAdapterError("Celestia live submission failed")',
        "verified=False",
    ),
    "neuron/da/adapters/near_adapter.py": (
        "Near live submission is disabled until a signed blob-store transaction",
        "verified=False",
    ),
    "neuron/da/adapters/avail_adapter.py": (
        "class AvailDAAdapter(ImmutableRuntimeConfiguration, DAAdapter):",
        'resolve_component_mock_mode(',
        '"AvailDAAdapter is a structured stub',
        'evidence_classification="non-authoritative"',
    ),
    "neuron/da/adapters/eigenda_adapter.py": (
        "class EigenDAAdapter(ImmutableRuntimeConfiguration, DAAdapter):",
        'resolve_component_mock_mode(',
        '"EigenDAAdapter is a structured stub',
        'evidence_classification="non-authoritative"',
    ),
    "neuron/sdk/oms_identity.py": (
        'resolve_component_mock_mode(',
        '"OMSIdentityVerifier",',
        '"live-provider"',
    ),
    "neuron/sdk/trails_client.py": (
        "class TrailsClient(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        'require_live_result',
    ),
    "neuron/payments/coinme_client.py": (
        "class CoinmeClient(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        '"CoinmeClient live execution is disabled',
        '"evidence_classification": "non-authoritative"',
    ),
    "neuron/payments/payment_channel.py": (
        "class PaymentChannelManager(ImmutableRuntimeConfiguration):",
        '"PaymentChannelManager live execution is disabled',
        '"signature": f"simulated:signature:',
    ),
    "neuron/payments/x402.py": (
        "class X402Client(ImmutableRuntimeConfiguration):",
        '"X402Client live execution is disabled',
    ),
    "neuron/sdk/avail_substrate.py": (
        "class AvailDASDK(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        'structured stub',
    ),
    "neuron/sdk/eigenda_kzg.py": (
        "class EigenDASDK(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        'confirmation polling exhausted',
    ),
    "neuron/sdk/iagon_storage.py": (
        "class IagonStorageSDK(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        '"IagonStorageSDK live execution is disabled',
    ),
    "neuron/sdk/akash_orchestrator.py": (
        "class AkashOrchestratorSDK(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        '"AkashOrchestratorSDK live execution is disabled',
    ),
    "neuron/sdk/phala_tee.py": (
        "class PhalaTEE(ImmutableRuntimeConfiguration):",
    ),
    "neuron/trust_plugins/tee_plugin.py": (
        "class TEEProofPlugin(BaseProofPlugin, ImmutableRuntimeConfiguration):",
    ),
    "neuron/sdk/trust_aggregator.py": (
        '"TrustAggregatorClient rejects non-authoritative TEE evidence"',
    ),
    "neuron/sdk/interrupt_handler.py": (
        "class InterruptVectorTable(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        '"InterruptVectorTable live execution is disabled',
    ),
    "neuron/sdk/x402_recovery.py": (
        "class EscrowStateClient(ImmutableRuntimeConfiguration):",
        "class X402InterruptHandler(ImmutableRuntimeConfiguration):",
        '"X402InterruptHandler live execution is disabled',
    ),
    "neuron/mev_protection.py": (
        "class EncryptedMempool(ImmutableRuntimeConfiguration):",
        '"EncryptedMempool live execution is disabled',
        '"BatchAuctionSettler live execution is disabled',
    ),
    "neuron/verifiers/celestia_light_client.py": (
        "class CelestiaLightClient(ImmutableRuntimeConfiguration):",
        '"CelestiaLightClient live execution is disabled',
        "A reachable network head is not proof",
    ),
    "neuron/da_router.py": (
        "class DARouter(ImmutableRuntimeConfiguration):",
        '"DARouter live execution is disabled',
    ),
    "neuron/sentinel/sentinel_node.py": (
        "class VAMSSentinelNode(ImmutableRuntimeConfiguration):",
        '"VAMSSentinelNode live execution is disabled',
    ),
    "neuron/neuron.py": (
        "class VamsNeuron(ImmutableRuntimeConfiguration):",
        'policy = load_runtime_policy()',
        '"VamsNeuron live startup is disabled',
        "def _validate_cli_boundary(policy: RuntimePolicy, args: argparse.Namespace)",
        'requires explicit VAMS_ENV=demo',
    ),
    "neuron/gateway/server.py": (
        "observed_policy = load_runtime_policy()",
        "if supplied_policy is not None and supplied_policy != observed_policy:",
        '"Legacy neuron gateway is unavailable in live modes',
        '"evidence_classification": policy.evidence_classification',
    ),
    "neuron/anchoring.py": (
        "class L1StateAnchor(ImmutableRuntimeConfiguration):",
        'resolve_component_mock_mode(',
        '"L1StateAnchor live execution is disabled',
        'tx_hash = f"simulated:sha256:',
    ),
    "neuron/demo_cli.py": (
        '"Demo CLI requires explicit VAMS_ENV=demo"',
        '"Runtime: demo | non-live | evidence: non-authoritative"',
        'This is not deployment, durability, recovery, or L1 proof.',
    ),
    "neuron/sdk/cognitive_drift.py": (
        "class CognitiveDriftDetector(ImmutableRuntimeConfiguration):",
        '"CognitiveDriftDetector live synchronization is disabled',
        'evidence_classification: str = "non-authoritative"',
    ),
    "scripts/security/runtime_mode_preflight.py": (
        "policy = load_runtime_policy",
        "if require_live and not policy.is_live:",
        "policy.sanitized_summary()",
    ),
    "neuron/storage/arweave.py": ('require_not_live_mock("ArweaveStorage upload"',),
    "neuron/vdso/da.py": ('require_not_live_mock(\n            "VDSO encrypted sidecar publisher"',),
    "neuron/vdso/routing.py": ("if profile.mock_mode or profile.stub:",),
    "neuron/bridge_executor.py": (
        "class BridgeExecutor(ImmutableRuntimeConfiguration):",
        "class MultiISMVerifier(ImmutableRuntimeConfiguration):",
        '"BridgeExecutor live execution is disabled',
        '"ICBClient live verification is disabled',
    ),
}


def _parse_tree(source: str, label: str) -> tuple[ast.Module | None, list[str]]:
    try:
        return ast.parse(source), []
    except SyntaxError as exc:
        return None, [f"{label}: invalid Python syntax at line {exc.lineno}"]


def _class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    return next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name),
        None,
    )


def _method(cls: ast.ClassDef | None, name: str) -> ast.FunctionDef | None:
    if cls is None:
        return None
    return next(
        (node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name),
        None,
    )


def _name(node: ast.AST | None, wanted: str) -> bool:
    return isinstance(node, ast.Name) and node.id == wanted


def _attribute(node: ast.AST | None, base: str, attr: str) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == attr and _name(node.value, base)


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _calls(node: ast.AST, name: str):
    return [item for item in ast.walk(node) if isinstance(item, ast.Call) and _call_name(item) == name]


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def _is_false(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _is_empty_bytes(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value == b""


def _first_return(node: ast.AST) -> ast.Return | None:
    return next((item for item in ast.walk(node) if isinstance(item, ast.Return)), None)


def _has_runtime_assert_first(method: ast.FunctionDef | None) -> bool:
    body = _effective_body(method)
    if not body or not isinstance(body[0], ast.Expr):
        return False
    value = body[0].value
    return isinstance(value, ast.Call) and _call_name(value) == "_assert_current_runtime"


def _effective_body(method: ast.FunctionDef | None) -> list[ast.stmt]:
    if method is None:
        return []
    body = method.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _is_live_test(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "is_live"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "runtime_policy"
        and _name(node.value.value, "self")
    )


def _raises_live_safety(node: ast.AST) -> bool:
    return any(
        isinstance(item, ast.Raise)
        and isinstance(item.exc, ast.Call)
        and _call_name(item.exc) == "LiveModeSafetyError"
        for item in ast.walk(node)
    )


def _has_early_live_rejection(method: ast.FunctionDef | None) -> bool:
    if not _has_runtime_assert_first(method):
        return False
    body = _effective_body(method)
    for index, statement in enumerate(body[:5]):
        if (
            isinstance(statement, ast.If)
            and not statement.orelse
            and _is_live_test(statement.test)
            and _single_raise(statement.body, "LiveModeSafetyError")
        ):
            if index == 1:
                return True
            if index == 2:
                mock_guard = body[1]
                return (
                    isinstance(mock_guard, ast.If)
                    and _attribute(mock_guard.test, "self", "mock_mode")
                    and not mock_guard.orelse
                    and _single_raise(mock_guard.body, "LiveModeSafetyError")
                )
            return False
    return False


def _ambient_policy_contract(tree: ast.Module) -> bool:
    helper = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_ambient_policy_for"),
        None,
    )
    if helper is None:
        return False
    body = _effective_body(helper)
    if len(body) != 4:
        return False
    if not _assigns_policy(body[0], "ambient", "os.environ"):
        return False
    if not _assigns_policy(body[1], "configured", "source"):
        return False
    mismatch = body[2]
    return (
        isinstance(mismatch, ast.If)
        and not mismatch.orelse
        and _ambient_mismatch_test(mismatch.test)
        and _single_raise(mismatch.body, "RuntimeConfigurationError")
        and isinstance(body[3], ast.Return)
        and _name(body[3].value, "ambient")
    )


def _assigns_policy(statement: ast.stmt, target: str, argument: str) -> bool:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not _name(statement.targets[0], target):
        return False
    value = statement.value
    if not isinstance(value, ast.Call) or _call_name(value) != "load_runtime_policy" or len(value.args) != 1:
        return False
    if argument == "source":
        return _name(value.args[0], "source")
    return isinstance(value.args[0], ast.Attribute) and value.args[0].attr == "environ" and _name(value.args[0].value, "os")


def _is_compare(node: ast.AST, left: ast.AST, op_type: type[ast.cmpop], right: ast.AST) -> bool:
    operator_type = op_type if isinstance(op_type, type) else type(op_type)
    return (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], operator_type)
        and len(node.comparators) == 1
        and _same_expression(node.left, left)
        and _same_expression(node.comparators[0], right)
    )


def _same_expression(left: ast.AST, right: ast.AST) -> bool:
    if isinstance(left, ast.Name) and isinstance(right, ast.Name):
        return left.id == right.id
    if isinstance(left, ast.Attribute) and isinstance(right, ast.Attribute):
        return left.attr == right.attr and _same_expression(left.value, right.value)
    if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
        return type(left.value) is type(right.value) and left.value == right.value
    return False


def _ambient_mismatch_test(node: ast.AST) -> bool:
    if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or) or len(node.values) != 2:
        return False
    configured_mismatch = _is_compare(
        node.values[0], ast.Name(id="configured"), ast.NotEq(), ast.Name(id="ambient")
    )
    supplied_branch = node.values[1]
    if not isinstance(supplied_branch, ast.BoolOp) or not isinstance(supplied_branch.op, ast.And) or len(supplied_branch.values) != 2:
        return False
    supplied_present = _is_compare(
        supplied_branch.values[0], ast.Name(id="supplied"), ast.IsNot(), ast.Constant(value=None)
    )
    supplied_mismatch = _is_compare(
        supplied_branch.values[1], ast.Name(id="supplied"), ast.NotEq(), ast.Name(id="ambient")
    )
    return configured_mismatch and supplied_present and supplied_mismatch


def _single_raise(body: list[ast.stmt], exception: str) -> bool:
    return (
        len(body) == 1
        and isinstance(body[0], ast.Raise)
        and isinstance(body[0].exc, ast.Call)
        and _call_name(body[0].exc) == exception
    )


def _mock_mismatch_rejects(init: ast.FunctionDef) -> bool:
    for item in ast.walk(init):
        if not isinstance(item, ast.If) or item.orelse or not _single_raise(item.body, "RuntimeConfigurationError"):
            continue
        test = item.test
        if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.And) or len(test.values) != 2:
            continue
        has_selection = _is_compare(
            test.values[0], ast.Name(id="mock_mode"), ast.IsNot(), ast.Constant(value=None)
        )
        has_conflict = _is_compare(
            test.values[1], ast.Name(id="mock_mode"), ast.NotEq(), ast.Name(id="ambient_mock")
        )
        if has_selection and has_conflict:
            return True
    return False


def _guarded_mismatch(method: ast.FunctionDef | None, left: ast.AST, right: ast.AST, exception: str) -> bool:
    if method is None:
        return False
    return any(
        isinstance(item, ast.If)
        and not item.orelse
        and _is_compare(item.test, left, ast.NotEq(), right)
        and _single_raise(item.body, exception)
        for item in ast.walk(method)
    )


def _ambient_mock_constructor(cls: ast.ClassDef | None, component: str) -> bool:
    init = _method(cls, "__init__")
    if init is None:
        return False
    ambient_resolution = any(
        len(call.args) >= 3
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == component
        and isinstance(call.args[2], ast.Constant)
        and call.args[2].value is None
        and isinstance(_keyword(call, "environ"), ast.Attribute)
        and _keyword(call, "environ").attr == "environ"
        and _name(_keyword(call, "environ").value, "os")
        for call in _calls(init, "resolve_component_mock_mode")
    )
    checks_explicit_selection = any(
        isinstance(item, ast.Compare)
        and _name(item.left, "mock_mode")
        and any(_name(other, "ambient_mock") for other in item.comparators)
        for item in ast.walk(init)
    )
    calls_ambient_policy = any(
        _call_name(call) == "_ambient_policy_for"
        and any(_name(arg, "source") for arg in call.args)
        and any(_name(arg, "runtime_policy") for arg in call.args)
        for call in _calls(init, "_ambient_policy_for")
    )
    init_body = _effective_body(init)
    freezes = (
        bool(init_body)
        and isinstance(init_body[-1], ast.Expr)
        and isinstance(init_body[-1].value, ast.Call)
        and _call_name(init_body[-1].value) == "_freeze_runtime_configuration"
    )
    explicit_mismatch_rejects = _mock_mismatch_rejects(init)
    return ambient_resolution and checks_explicit_selection and calls_ambient_policy and freezes and explicit_mismatch_rejects


def _immutable_runtime_fields(cls: ast.ClassDef | None) -> bool:
    if cls is None:
        return False
    for item in cls.body:
        if not isinstance(item, ast.Assign) or not any(_name(target, "_immutable_runtime_fields") for target in item.targets):
            continue
        value = item.value
        if isinstance(value, ast.Call) and _call_name(value) == "frozenset" and value.args:
            values = value.args[0]
            if isinstance(values, (ast.Set, ast.List, ast.Tuple)):
                actual = {element.value for element in values.elts if isinstance(element, ast.Constant)}
                return actual == {"runtime_policy", "mock_mode"}
    return False


def _ambient_revalidation(cls: ast.ClassDef | None) -> bool:
    method = _method(cls, "_assert_current_runtime")
    if method is None:
        return False
    ambient_load = any(
        call.args
        and isinstance(call.args[0], ast.Attribute)
        and call.args[0].attr == "environ"
        and _name(call.args[0].value, "os")
        for call in _calls(method, "load_runtime_policy")
    )
    current_policy_rejects = _guarded_mismatch(
        method,
        ast.Name(id="current"),
        ast.Attribute(value=ast.Name(id="self"), attr="runtime_policy"),
        "_PhalaRuntimeDriftError" if cls and cls.name == "PhalaTEE" else "_TEEPluginRuntimeDriftError",
    )
    current_mock_rejects = _guarded_mismatch(
        method,
        ast.Name(id="current_mock"),
        ast.Attribute(value=ast.Name(id="self"), attr="mock_mode"),
        "_PhalaRuntimeDriftError" if cls and cls.name == "PhalaTEE" else "_TEEPluginRuntimeDriftError",
    )
    return ambient_load and current_policy_rejects and current_mock_rejects


def _tee_plugin_nonmock_rejection(method: ast.FunctionDef | None, *, verification: bool) -> bool:
    if not _has_runtime_assert_first(method):
        return False
    body = _effective_body(method)
    if len(body) < 2 or not isinstance(body[1], ast.If):
        return False
    guard = body[1]
    if not (
        isinstance(guard.test, ast.UnaryOp)
        and isinstance(guard.test.op, ast.Not)
        and _attribute(guard.test.operand, "self", "mock_mode")
    ):
        return False
    if guard.orelse or len(guard.body) != 1:
        return False
    returned = _first_return(guard)
    if returned is None:
        return False
    if verification:
        return _is_false(returned.value)
    if not isinstance(returned.value, ast.Call) or _call_name(returned.value) != "ProofResult":
        return False
    return (
        _is_false(_keyword(returned.value, "valid"))
        and _is_empty_bytes(_keyword(returned.value, "proof_data"))
    )


def _quorum_guard(method: ast.FunctionDef | None) -> bool:
    if not _has_runtime_assert_first(method):
        return False
    body = _effective_body(method)
    for statement in body[1:2]:
        if not isinstance(statement, ast.If):
            continue
        test = statement.test
        if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.Or):
            continue
        has_exact_int = any(
            isinstance(compare, ast.Compare)
            and isinstance(compare.left, ast.Call)
            and _call_name(compare.left) == "type"
            and len(compare.left.args) == 1
            and _name(compare.left.args[0], "required")
            and any(isinstance(op, ast.IsNot) for op in compare.ops)
            and any(_name(item, "int") for item in compare.comparators)
            for compare in ast.walk(test)
        )
        has_exact_two = any(
            isinstance(compare, ast.Compare)
            and _name(compare.left, "required")
            and any(isinstance(op, ast.NotEq) for op in compare.ops)
            and any(isinstance(item, ast.Constant) and type(item.value) is int and item.value == 2 for item in compare.comparators)
            for compare in ast.walk(test)
        )
        if has_exact_int and has_exact_two and not statement.orelse and _single_raise(statement.body, "ValueError"):
            return _final_quorum(method)
    return False


def _final_quorum(method: ast.FunctionDef) -> bool:
    body = _effective_body(method)
    if not body or not isinstance(body[-1], ast.Return) or not isinstance(body[-1].value, ast.Tuple) or not body[-1].value.elts:
        return False
    threshold = body[-1].value.elts[0]
    return (
        isinstance(threshold, ast.Compare)
        and len(threshold.ops) == 1
        and isinstance(threshold.ops[0], ast.GtE)
        and _name(threshold.left, "valid_count")
        and len(threshold.comparators) == 1
        and isinstance(threshold.comparators[0], ast.Constant)
        and type(threshold.comparators[0].value) is int
        and threshold.comparators[0].value >= 2
    )


def check_tee_sources(phala_text: str, plugin_text: str) -> list[str]:
    """Check source-level TEE fail-closed invariants using Python AST, not comments."""
    errors: list[str] = []
    phala_tree, parse_errors = _parse_tree(phala_text, "neuron/sdk/phala_tee.py")
    errors.extend(parse_errors)
    plugin_tree, parse_errors = _parse_tree(plugin_text, "neuron/trust_plugins/tee_plugin.py")
    errors.extend(parse_errors)
    if phala_tree is None or plugin_tree is None:
        return errors

    phala = _class(phala_tree, "PhalaTEE")
    plugin = _class(plugin_tree, "TEEProofPlugin")
    report = _class(phala_tree, "AttestationReport")
    if phala is None or not any(_name(base, "ImmutableRuntimeConfiguration") for base in phala.bases):
        errors.append("neuron/sdk/phala_tee.py: PhalaTEE must freeze effective runtime configuration")
    if plugin is None or not any(_name(base, "ImmutableRuntimeConfiguration") for base in plugin.bases):
        errors.append("neuron/trust_plugins/tee_plugin.py: TEEProofPlugin must freeze effective runtime configuration")
    if not _ambient_policy_contract(phala_tree):
        errors.append("neuron/sdk/phala_tee.py: constructor policy must be bound to ambient os.environ")
    if not _ambient_policy_contract(plugin_tree):
        errors.append("neuron/trust_plugins/tee_plugin.py: constructor policy must be bound to ambient os.environ")
    if not _ambient_mock_constructor(phala, "PhalaTEE") or not _immutable_runtime_fields(phala):
        errors.append("neuron/sdk/phala_tee.py: ambient mock selection and frozen runtime fields are required")
    if not _ambient_mock_constructor(plugin, "TEEProofPlugin") or not _immutable_runtime_fields(plugin):
        errors.append("neuron/trust_plugins/tee_plugin.py: ambient mock selection and frozen runtime fields are required")
    if not _ambient_revalidation(phala) or not _ambient_revalidation(plugin):
        errors.append("TEE runtime drift must be revalidated against ambient os.environ")

    usable = _method(report, "usable_as_live_evidence")
    usable_body = _effective_body(usable)
    if len(usable_body) != 1 or not isinstance(usable_body[0], ast.Return) or not _is_false(usable_body[0].value):
        errors.append("neuron/sdk/phala_tee.py: legacy reports must never be usable as live evidence")
    claim_field = None if report is None else next(
        (
            item
            for item in report.body
            if isinstance(item, ast.AnnAssign)
            and _name(item.target, "provider_claim_valid")
        ),
        None,
    )
    claim_serializer = _method(report, "to_dict")
    if (
        claim_field is None
        or not isinstance(claim_field.value, ast.Constant)
        or claim_field.value.value is not None
        or claim_serializer is None
        or not any(
            isinstance(item, ast.Dict)
            and any(isinstance(key, ast.Constant) and key.value == "provider_claim_valid" for key in item.keys)
            for item in ast.walk(claim_serializer)
        )
    ):
        errors.append("neuron/sdk/phala_tee.py: parsed provider claim must be optional, default-none, and serialized separately")

    report_method = _method(phala, "_report")
    if report_method is None:
        errors.append("neuron/sdk/phala_tee.py: missing guarded report builder")
    else:
        accepts_only_simulation = any(
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and _name(item.targets[0], "accepted")
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "bool"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.BoolOp)
            and isinstance(item.value.args[0].op, ast.And)
            and {_id.id for _id in item.value.args[0].values if isinstance(_id, ast.Name)} == {"valid", "simulated"}
            for item in ast.walk(report_method)
        )
        report_construction = any(
            isinstance(item, ast.Call)
            and _call_name(item) == "AttestationReport"
            and _name(_keyword(item, "is_valid"), "accepted")
            and isinstance(_keyword(item, "evidence_classification"), ast.Constant)
            and _keyword(item, "evidence_classification").value == "non-authoritative"
            for item in ast.walk(report_method)
        )
        if not accepts_only_simulation or not report_construction:
            errors.append("neuron/sdk/phala_tee.py: provider JSON must not promote report validity/evidence")

    for method_name in ("call_phat_contract", "execute_python_in_enclave"):
        if not _has_early_live_rejection(_method(phala, method_name)):
            errors.append(f"neuron/sdk/phala_tee.py: {method_name} must reject live dispatch before protected input use")
    direct_call = _method(phala, "call_phat_contract")
    direct_body = _effective_body(direct_call)
    if not (
        len(direct_body) > 1
        and isinstance(direct_body[1], ast.If)
        and _attribute(direct_body[1].test, "self", "mock_mode")
        and not direct_body[1].orelse
        and _single_raise(direct_body[1].body, "LiveModeSafetyError")
    ):
        errors.append("neuron/sdk/phala_tee.py: mock-mode direct contract calls must fail closed")

    for method_name in ("verify_sgx_quote", "verify_nitro_quote"):
        method = _method(phala, method_name)
        positive_claim_rejected = method is not None and any(
            isinstance(item, ast.Call)
            and _call_name(item) == "_report"
            and _is_false(_keyword(item, "valid"))
            and isinstance(_keyword(item, "provider_claim_valid"), ast.Subscript)
            and _name(_keyword(item, "provider_claim_valid").value, "result")
            and isinstance(_keyword(item, "error"), ast.IfExp)
            and isinstance(_keyword(item, "error").body, ast.Constant)
            and _keyword(item, "error").body.value == "authentic_verifier_unavailable"
            for item in ast.walk(method)
        )
        if not positive_claim_rejected:
            errors.append(f"neuron/sdk/phala_tee.py: {method_name} must keep provider positives unverified")

    if not _tee_plugin_nonmock_rejection(_method(plugin, "generate_proof"), verification=False):
        errors.append("neuron/trust_plugins/tee_plugin.py: non-mock proof generation must reject with empty proof before callbacks")
    if not _tee_plugin_nonmock_rejection(_method(plugin, "verify_proof"), verification=True):
        errors.append("neuron/trust_plugins/tee_plugin.py: non-mock proof verification must reject before input access")
    if not _quorum_guard(_method(phala, "verify_multi_tee")):
        errors.append("neuron/sdk/phala_tee.py: multi-TEE threshold must be exact integer 2 before quote access")

    return errors


def main() -> int:
    missing: list[str] = []

    for rel_path, snippets in REQUIRED_GUARDS.items():
        path = ROOT / rel_path
        if not path.exists():
            missing.append(f"{rel_path}: file missing")
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"{rel_path}: missing guard `{snippet}`")

    tee_paths = ("neuron/sdk/phala_tee.py", "neuron/trust_plugins/tee_plugin.py")
    tee_texts = []
    for rel_path in tee_paths:
        path = ROOT / rel_path
        if not path.exists():
            missing.append(f"{rel_path}: file missing")
            tee_texts.append("")
        else:
            tee_texts.append(path.read_text(encoding="utf-8", errors="ignore"))
    if all(tee_texts):
        missing.extend(check_tee_sources(*tee_texts))

    if missing:
        print("Mock-mode promotion scan failed:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("Mock-mode promotion scan passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
