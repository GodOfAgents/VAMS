"""Static guard for SQL identifiers in the effect persistence modules.

Bandit B608 is suppressed line by line in ``neuron/effect_*.py`` (owner
decision 7, 2026-11-08). The suppression is only valid while every value
interpolated into an executed SQL f-string is a fixed identifier:

* a module constant (in any effect module) matching ``public.vams_effect_v<N>_<name>``;
* a class attribute bound to such a constant (``self._scope_table``);
* a loop variable ``table`` that the same function checks against the fixed
  ``_TABLES5`` set or the ``public.vams_effect_v[34]_[a-z_]+`` regex first;
* ``suffix``, assigned only ``' FOR UPDATE'`` or ``''``.

Every ``# nosec B608`` must sit inside such a guarded statement. Data values
must stay as driver parameters.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EFFECT_FILES = sorted((ROOT / "neuron").glob("effect_*.py"))
IDENTIFIER = re.compile(r"public\.vams_effect_v[0-9]+_[a-z0-9_]+")
TABLE_CHECKS = ("if table not in _TABLES5", r"re.fullmatch(r'public\.vams_effect_v[34]_[a-z_]+', table)")


def _module_constants() -> dict[str, str]:
    constants: dict[str, str] = {}
    for path in EFFECT_FILES:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)):
                constants[node.targets[0].id] = node.value.value
    return constants


def _class_attributes(tree: ast.Module, constants: dict[str, str]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for node in cls.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in constants):
                attributes[node.targets[0].id] = constants[node.value.id]
    return attributes


def _enclosing_functions(tree: ast.Module):
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield function


def _suffix_is_fixed(function: ast.AST) -> bool:
    for node in ast.walk(function):
        if (isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "suffix" for t in node.targets)):
            value = node.value
            if not (isinstance(value, ast.IfExp)
                    and isinstance(value.body, ast.Constant) and value.body.value == " FOR UPDATE"
                    and isinstance(value.orelse, ast.Constant) and value.orelse.value == ""):
                return False
    return True


class EffectSqlIdentifierGuardTests(unittest.TestCase):
    def setUp(self):
        self.constants = _module_constants()

    def _guarded_statements(self, path: Path):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        attributes = _class_attributes(tree, self.constants)
        guarded = []
        for function in _enclosing_functions(tree):
            function_source = ast.get_source_segment(source, function) or ""
            for call in ast.walk(function):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and call.func.attr == "execute" and call.args
                        and isinstance(call.args[0], ast.JoinedStr)):
                    continue
                for part in call.args[0].values:
                    if not isinstance(part, ast.FormattedValue):
                        continue
                    with self.subTest(file=path.name, line=call.lineno, expr=ast.unparse(part.value)):
                        self.assertEqual(part.conversion, -1)
                        self.assertIsNone(part.format_spec)
                        value = part.value
                        if isinstance(value, ast.Name) and value.id in self.constants:
                            self.assertRegex(self.constants[value.id], f"^{IDENTIFIER.pattern}$")
                        elif (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                              and value.value.id == "self" and value.attr in attributes):
                            self.assertRegex(attributes[value.attr], f"^{IDENTIFIER.pattern}$")
                        elif isinstance(value, ast.Name) and value.id == "table":
                            self.assertTrue(any(check in function_source for check in TABLE_CHECKS),
                                            "table identifier must be validated in the same function")
                        elif isinstance(value, ast.Name) and value.id == "suffix":
                            self.assertTrue(_suffix_is_fixed(function))
                        else:
                            self.fail("unapproved SQL interpolation")
                guarded.append((call.args[0].lineno, call.args[0].end_lineno))
        return source, guarded

    def test_every_interpolated_identifier_is_fixed(self):
        total = 0
        for path in EFFECT_FILES:
            _, guarded = self._guarded_statements(path)
            total += len(guarded)
        self.assertGreater(total, 0)

    def test_every_b608_suppression_is_inside_a_guarded_statement(self):
        for path in EFFECT_FILES:
            source, guarded = self._guarded_statements(path)
            for number, line in enumerate(source.splitlines(), start=1):
                if "nosec B608" in line:
                    with self.subTest(file=path.name, line=number):
                        self.assertTrue(any(start <= number <= end for start, end in guarded))

    def test_b608_suppressions_stay_in_effect_modules(self):
        for path in (ROOT / "neuron").rglob("*.py"):
            if path in EFFECT_FILES or "tests" in path.parts:
                continue
            self.assertNotIn("nosec B608", path.read_text(encoding="utf-8"), str(path))
        for path in (ROOT / "gateway").rglob("*.py"):
            self.assertNotIn("nosec B608", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
