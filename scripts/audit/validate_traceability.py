#!/usr/bin/env python3
"""Validate architecture-version and core-invariant source traceability."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "docs" / "audit"
INVARIANT_SCHEMA_VERSION = "1.1.0"
_CONTROL_KEYS = frozenset({"id", "statement", "enforcement", "tests"})
_ANCHOR_KEYS = frozenset({"path", "must_contain", "python_ast", "python_tests", "aiken_boundary"})
_PYTHON_AST_KEYS = frozenset(
    {
        "control_type",
        "class",
        "function",
        "required_calls",
        "guarded_denials",
        "required_returns",
        "required_assignments",
        "required_exception_handlers",
        "minimum_false_result_calls",
        "minimum_raises",
    }
)
_CONTROL_TYPE_REQUIREMENTS = {
    "fail_closed_call": frozenset({"guarded_denials", "minimum_raises"}),
    "predicate": frozenset({"required_returns"}),
    "provider_result": frozenset({"required_assignments"}),
    "provider_boundary": frozenset(
        {"required_exception_handlers", "minimum_false_result_calls"}
    ),
    "signing_guard": frozenset({"guarded_denials"}),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _node_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _node_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _expression_dump(expression: str) -> str:
    parsed = ast.parse(expression, mode="eval")
    return ast.dump(parsed.body, include_attributes=False)


def _function_scope(
    tree: ast.Module, class_name: str, function_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(classes) != 1:
        return None
    functions = [
        node
        for node in classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    return functions[0] if len(functions) == 1 else None


def _raise_name(node: ast.Raise) -> str:
    exception = node.exc
    if isinstance(exception, ast.Call):
        return _node_name(exception.func)
    return _node_name(exception)


def _handler_names(node: ast.AST | None) -> set[str]:
    if isinstance(node, ast.Tuple):
        return {_node_name(item) for item in node.elts}
    name = _node_name(node)
    return {name} if name else set()


def _call_matches(call: ast.Call, expected: dict) -> bool:
    if _node_name(call.func) != expected["call"]:
        return False
    expected_arguments = [_expression_dump(value) for value in expected["arguments"]]
    observed_arguments = [ast.dump(value, include_attributes=False) for value in call.args]
    return observed_arguments == expected_arguments and not call.keywords


def _validate_python_ast(
    control_id: str, relative_path: str, text: str, specification: object
) -> list[str]:
    prefix = f"{control_id} python control {relative_path}"
    if not isinstance(specification, dict):
        return [f"{prefix} metadata must be an object"]
    unknown = set(specification) - _PYTHON_AST_KEYS
    if unknown:
        return [f"{prefix} has unknown metadata: {sorted(unknown)}"]
    control_type = specification.get("control_type")
    if control_type not in _CONTROL_TYPE_REQUIREMENTS:
        return [f"{prefix} has invalid control_type"]
    missing = _CONTROL_TYPE_REQUIREMENTS[control_type] - set(specification)
    if missing:
        return [f"{prefix} is incomplete: missing {sorted(missing)}"]
    class_name = specification.get("class")
    function_name = specification.get("function")
    if not isinstance(class_name, str) or not class_name:
        return [f"{prefix} requires one class symbol"]
    if not isinstance(function_name, str) or not function_name:
        return [f"{prefix} requires one function symbol"]
    try:
        tree = ast.parse(text, filename=relative_path)
    except SyntaxError:
        return [f"{prefix} source is not valid Python"]
    scope = _function_scope(tree, class_name, function_name)
    if scope is None:
        return [f"{prefix} missing exact symbol {class_name}.{function_name}"]

    errors: list[str] = []
    calls = [node for node in ast.walk(scope) if isinstance(node, ast.Call)]
    raises = [node for node in ast.walk(scope) if isinstance(node, ast.Raise)]

    required_calls = specification.get("required_calls", [])
    if not isinstance(required_calls, list) or any(
        not isinstance(item, str) or not item for item in required_calls
    ):
        errors.append(f"{prefix} required_calls must be a string list")
    else:
        observed_calls = {_node_name(node.func) for node in calls}
        for required in required_calls:
            if required not in observed_calls:
                errors.append(f"{prefix} missing call {required}")

    guarded_denials = specification.get("guarded_denials", [])
    if not isinstance(guarded_denials, list):
        errors.append(f"{prefix} guarded_denials must be a list")
    else:
        for denial in guarded_denials:
            if not isinstance(denial, dict) or set(denial) != {
                "call",
                "arguments",
                "exception",
            }:
                errors.append(f"{prefix} has malformed guarded denial")
                continue
            if (
                not isinstance(denial["call"], str)
                or not isinstance(denial["arguments"], list)
                or any(not isinstance(item, str) for item in denial["arguments"])
                or not isinstance(denial["exception"], str)
            ):
                errors.append(f"{prefix} has malformed guarded denial values")
                continue
            matched = False
            try:
                for branch in (node for node in ast.walk(scope) if isinstance(node, ast.If)):
                    test = branch.test
                    if not (
                        isinstance(test, ast.UnaryOp)
                        and isinstance(test.op, ast.Not)
                        and isinstance(test.operand, ast.Call)
                        and _call_matches(test.operand, denial)
                    ):
                        continue
                    branch_raises = [
                        child
                        for statement in branch.body
                        for child in ast.walk(statement)
                        if isinstance(child, ast.Raise)
                    ]
                    if any(_raise_name(child) == denial["exception"] for child in branch_raises):
                        matched = True
                        break
            except SyntaxError:
                errors.append(f"{prefix} has an invalid guarded-denial expression")
                continue
            if not matched:
                errors.append(
                    f"{prefix} lacks fail-closed {denial['call']} denial via "
                    f"{denial['exception']}"
                )

    required_returns = specification.get("required_returns", [])
    if not isinstance(required_returns, list) or any(
        not isinstance(item, str) or not item for item in required_returns
    ):
        errors.append(f"{prefix} required_returns must be a string list")
    else:
        observed_returns = {
            ast.dump(node.value, include_attributes=False)
            for node in ast.walk(scope)
            if isinstance(node, ast.Return) and node.value is not None
        }
        for expression in required_returns:
            try:
                expected = _expression_dump(expression)
            except SyntaxError:
                errors.append(f"{prefix} has an invalid required return expression")
                continue
            if expected not in observed_returns:
                errors.append(f"{prefix} missing required return expression")

    required_assignments = specification.get("required_assignments", [])
    if not isinstance(required_assignments, list):
        errors.append(f"{prefix} required_assignments must be a list")
    else:
        assignments = [node for node in ast.walk(scope) if isinstance(node, ast.Assign)]
        for required in required_assignments:
            if not isinstance(required, dict) or set(required) != {"target", "expression"}:
                errors.append(f"{prefix} has malformed required assignment")
                continue
            try:
                expected = _expression_dump(required["expression"])
            except (SyntaxError, TypeError):
                errors.append(f"{prefix} has an invalid assignment expression")
                continue
            matched = any(
                len(node.targets) == 1
                and _node_name(node.targets[0]) == required["target"]
                and ast.dump(node.value, include_attributes=False) == expected
                for node in assignments
            )
            if not matched:
                errors.append(f"{prefix} missing required assignment {required['target']}")

    required_handlers = specification.get("required_exception_handlers", [])
    if not isinstance(required_handlers, list) or any(
        not isinstance(item, str) or not item for item in required_handlers
    ):
        errors.append(f"{prefix} required_exception_handlers must be a string list")
    else:
        observed_handlers: set[str] = set()
        for handler in (node for node in ast.walk(scope) if isinstance(node, ast.ExceptHandler)):
            observed_handlers.update(_handler_names(handler.type))
        for required in required_handlers:
            if required not in observed_handlers:
                errors.append(f"{prefix} missing exception handler {required}")

    minimum_raises = specification.get("minimum_raises")
    if minimum_raises is not None:
        if type(minimum_raises) is not int or minimum_raises < 1:
            errors.append(f"{prefix} minimum_raises must be a positive integer")
        elif len(raises) < minimum_raises:
            errors.append(f"{prefix} has too few fail-closed raises")

    minimum_false_results = specification.get("minimum_false_result_calls")
    if minimum_false_results is not None:
        if type(minimum_false_results) is not int or minimum_false_results < 1:
            errors.append(
                f"{prefix} minimum_false_result_calls must be a positive integer"
            )
        else:
            observed = sum(
                1
                for call in calls
                if _node_name(call.func) == "self._result"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value is False
            )
            if observed < minimum_false_results:
                errors.append(f"{prefix} has too few explicit false provider outcomes")
    return errors


def _validate_python_tests(
    control_id: str, relative_path: str, text: str, expected: object
) -> list[str]:
    prefix = f"{control_id} test control {relative_path}"
    if not isinstance(expected, list) or not expected or any(
        not isinstance(item, str) or not item.startswith("test_") for item in expected
    ):
        return [f"{prefix} python_tests must be a non-empty test identifier list"]
    if len(expected) != len(set(expected)):
        return [f"{prefix} contains duplicate test identifiers"]
    try:
        tree = ast.parse(text, filename=relative_path)
    except SyntaxError:
        return [f"{prefix} source is not valid Python"]
    observed = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    errors = []
    for test_id in expected:
        if observed.count(test_id) != 1:
            errors.append(f"{prefix} missing exact test identifier {test_id}")
    return errors


_AIKEN_BOUNDARY_KEYS = frozenset({
    "control_type",
    "required_deposit_pattern",
    "required_fields",
    "forbidden_calls",
})


def _validate_aiken_boundary(
    control_id: str, relative_path: str, text: str, specification: object
) -> list[str]:
    prefix = f"{control_id} Aiken boundary {relative_path}"
    if not isinstance(specification, dict) or set(specification) != _AIKEN_BOUNDARY_KEYS:
        return [f"{prefix} metadata is incomplete or has unknown keys"]
    if specification.get("control_type") != "insurance_custody":
        return [f"{prefix} has invalid control_type"]
    fields = specification.get("required_fields")
    if (
        not isinstance(fields, list)
        or fields != ["bridge_proof", "payload_hash"]
        or len(set(fields)) != len(fields)
    ):
        return [f"{prefix} requires separate bridge_proof and payload_hash fields"]
    pattern = specification.get("required_deposit_pattern")
    if not isinstance(pattern, str) or not pattern or pattern not in text:
        return [f"{prefix} lacks unconditional Deposit rejection"]
    if any(field not in pattern for field in fields):
        return [f"{prefix} Deposit pattern does not preserve separate fields"]
    forbidden = specification.get("forbidden_calls")
    if (
        not isinstance(forbidden, list)
        or any(not isinstance(item, str) or not item for item in forbidden)
    ):
        return [f"{prefix} forbidden_calls must be a non-empty string list"]
    errors = []
    for call in forbidden:
        if call in text:
            errors.append(f"{prefix} contains forbidden structural authorizer {call!r}")
    return errors


def validate_invariant_controls(root: Path, controls: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(controls, dict):
        return ["invariant controls must be an object"]
    if set(controls) != {"schema_version", "architecture_version", "controls"}:
        errors.append("invariant controls have unknown or missing top-level metadata")
    if controls.get("schema_version") != INVARIANT_SCHEMA_VERSION:
        errors.append(
            f"invariant control schema_version must equal {INVARIANT_SCHEMA_VERSION}"
        )
    control_items = controls.get("controls")
    if not isinstance(control_items, list):
        return errors + ["invariant controls list is malformed"]
    ids = [item.get("id") if isinstance(item, dict) else None for item in control_items]
    expected_ids = [f"INV-{index}" for index in range(1, 11)]
    if ids != expected_ids:
        errors.append("invariant controls must be exactly INV-1 through INV-10")
    for control in control_items:
        if not isinstance(control, dict):
            errors.append("invariant control entry must be an object")
            continue
        control_id = control.get("id")
        if set(control) != _CONTROL_KEYS:
            errors.append(f"{control_id} has unknown or missing control metadata")
        if not isinstance(control.get("statement"), str) or not control["statement"].strip():
            errors.append(f"{control_id} has no invariant statement")
        for group in ("enforcement", "tests"):
            anchors = control.get(group)
            if not isinstance(anchors, list) or not anchors:
                errors.append(f"{control_id} has no {group} anchors")
                continue
            signatures: set[str] = set()
            for anchor in anchors:
                if not isinstance(anchor, dict):
                    errors.append(f"{control_id} has malformed {group} metadata")
                    continue
                signature = json.dumps(anchor, sort_keys=True, separators=(",", ":"))
                if signature in signatures:
                    errors.append(f"{control_id} has duplicate {group} metadata")
                    continue
                signatures.add(signature)
                unknown = set(anchor) - _ANCHOR_KEYS
                if unknown:
                    errors.append(f"{control_id} has unknown {group} metadata")
                    continue
                relative_path = anchor.get("path")
                if not isinstance(relative_path, str) or not relative_path:
                    errors.append(f"{control_id} has malformed {group} path")
                    continue
                parsed_path = PurePosixPath(relative_path)
                if parsed_path.is_absolute() or ".." in parsed_path.parts:
                    errors.append(f"{control_id} has unsafe {group} path")
                    continue
                evidence_fields = set(anchor) & {
                    "must_contain",
                    "python_ast",
                    "python_tests",
                    "aiken_boundary",
                }
                expected_field = "python_tests" if group == "tests" else "python_ast"
                if len(evidence_fields) != 1:
                    errors.append(f"{control_id} {group} anchor must select one evidence model")
                    continue
                if group == "enforcement" and "python_tests" in evidence_fields:
                    errors.append(f"{control_id} enforcement cannot use test identifiers")
                    continue
                if group == "tests" and "python_ast" in evidence_fields:
                    errors.append(f"{control_id} tests cannot use enforcement metadata")
                    continue
                path = root / relative_path
                if not path.is_file():
                    errors.append(f"{control_id} missing anchor: {relative_path}")
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "must_contain" in evidence_fields:
                    expected_values = anchor["must_contain"]
                    if not isinstance(expected_values, list) or not expected_values or any(
                        not isinstance(value, str) or not value for value in expected_values
                    ):
                        errors.append(f"{control_id} has malformed must_contain metadata")
                        continue
                    for expected in expected_values:
                        if expected not in text:
                            errors.append(
                                f"{control_id} anchor {relative_path} lacks {expected!r}"
                            )
                elif "aiken_boundary" in evidence_fields:
                    if group != "enforcement":
                        errors.append(f"{control_id} Aiken boundary is enforcement-only")
                    errors.extend(
                        _validate_aiken_boundary(
                            control_id, relative_path, text, anchor["aiken_boundary"]
                        )
                    )
                elif expected_field == "python_ast":
                    errors.extend(
                        _validate_python_ast(
                            control_id, relative_path, text, anchor["python_ast"]
                        )
                    )
                else:
                    errors.extend(
                        _validate_python_tests(
                            control_id, relative_path, text, anchor["python_tests"]
                        )
                    )
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    matrix = _load(AUDIT_DIR / "control-matrix.json")
    architecture = _load(AUDIT_DIR / "architecture-traceability.json")
    controls = _load(AUDIT_DIR / "invariant-controls.json")
    current = architecture.get("current_architecture_version")
    if current != matrix.get("architecture_version"):
        errors.append("architecture traceability version does not match control matrix")
    if controls.get("architecture_version") != current:
        errors.append("invariant control version does not match current architecture")

    versions = architecture.get("versions", [])
    if [item.get("version") for item in versions] != [
        "0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.8.0"
    ]:
        errors.append("architecture versions must trace 0.3.0 through 0.8.0")
    for item in versions:
        if item.get("lifecycle") not in {"historical", "current"}:
            errors.append(f"architecture version {item.get('version')} has invalid lifecycle")
        if not isinstance(item.get("maturity"), str) or not item["maturity"].strip():
            errors.append(f"architecture version {item.get('version')} lacks maturity")
        path = ROOT / item.get("document", "")
        if not path.is_file():
            errors.append(f"architecture document is missing: {path.relative_to(ROOT)}")
    for component in architecture.get("current_components", []):
        if not (ROOT / component).is_file():
            errors.append(f"current architecture component is missing: {component}")

    errors.extend(validate_invariant_controls(ROOT, controls))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Architecture and invariant traceability failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("Architecture 0.8.0 and INV-1..INV-10 traceability passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
