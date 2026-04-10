#!/usr/bin/env python3
"""L5 Test substance auditor -- classify tests as REAL/SHALLOW/TAUTOLOGICAL.

Usage: python scripts/test_substance_lint.py tests/
       python scripts/test_substance_lint.py tests/test_terrain_caves.py
Exit code 1 if real_ratio < 0.5.

Classification:
  SHALLOW:      Test only asserts is not None, len > 0, isinstance, type checks
  TAUTOLOGICAL: Test asserts something always true (assert True, assert 1 == 1)
  REAL:         Everything else (meaningful behavioral assertions)
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestClass:
    REAL = "REAL"
    SHALLOW = "SHALLOW"
    TAUTOLOGICAL = "TAUTOLOGICAL"


@dataclass
class TestResult:
    file: str
    name: str
    line: int
    classification: str
    reason: str = ""


ASSERT_METHODS = {
    "assertEqual", "assertNotEqual", "assertTrue", "assertFalse",
    "assertIs", "assertIsNot", "assertIsNone", "assertIsNotNone",
    "assertIn", "assertNotIn", "assertIsInstance", "assertNotIsInstance",
    "assertRaises", "assertRaisesRegex", "assertAlmostEqual", "assertGreater",
    "assertLess", "assertGreaterEqual", "assertLessEqual", "assertRegex",
    "assertCountEqual", "assertListEqual", "assertDictEqual",
    "assertSequenceEqual", "assertSetEqual", "assertTupleEqual",
    "assert_called", "assert_called_once", "assert_called_with",
    "assert_called_once_with", "assert_not_called",
}
RAISES_CONTEXT_METHODS = {"raises", "assertRaises", "assertRaisesRegex"}


# ---------------------------------------------------------------------------
# Assert analysis helpers
# ---------------------------------------------------------------------------

def _is_tautological_assert(node: ast.AST) -> bool:
    """Check if an assert statement is always true."""
    if isinstance(node, ast.Assert):
        test = node.test
        # assert True
        if isinstance(test, ast.Constant) and test.value is True:
            return True
        # assert 1 == 1, assert "a" == "a", etc.
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
            if isinstance(test.ops[0], ast.Eq):
                left = test.left
                right = test.comparators[0]
                if isinstance(left, ast.Constant) and isinstance(right, ast.Constant):
                    if left.value == right.value:
                        return True
        return False

    # self.assertTrue(True)
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        call = node.value
        method = _get_method_name(call)
        if method == "assertTrue" and len(call.args) >= 1:
            arg = call.args[0]
            if isinstance(arg, ast.Constant) and arg.value is True:
                return True
        if method == "assertEqual" and len(call.args) >= 2:
            a, b = call.args[0], call.args[1]
            if isinstance(a, ast.Constant) and isinstance(b, ast.Constant) and a.value == b.value:
                return True

    return False


def _is_shallow_assert(node: ast.AST) -> bool:
    """Check if an assert is shallow (only type/existence checks)."""
    # assert x is not None
    if isinstance(node, ast.Assert):
        test = node.test
        if isinstance(test, ast.Compare) and len(test.ops) == 1:
            op = test.ops[0]
            comp = test.comparators[0]
            if isinstance(op, ast.IsNot) and isinstance(comp, ast.Constant) and comp.value is None:
                return True
            if isinstance(op, ast.Is) and isinstance(comp, ast.Constant) and comp.value is not None:
                return False  # assert x is <specific value> is meaningful
        # assert isinstance(x, SomeType)
        if isinstance(test, ast.Call):
            if isinstance(test.func, ast.Name) and test.func.id == "isinstance":
                return True
        # assert len(x) > 0  or  assert len(x) >= 1
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
            left = test.left
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len":
                op = test.ops[0]
                comp = test.comparators[0]
                if isinstance(op, ast.Gt) and isinstance(comp, ast.Constant) and comp.value == 0:
                    return True
                if isinstance(op, ast.GtE) and isinstance(comp, ast.Constant) and comp.value == 1:
                    return True
        return False

    # self.assertIsNotNone(x), self.assertIsInstance(x, T)
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        method = _get_method_name(node.value)
        if method in ("assertIsNotNone", "assertIsInstance"):
            return True

    return False


def _get_method_name(call: ast.Call) -> str:
    """Extract method name from a call node (e.g., self.assertEqual -> assertEqual)."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_raises_context(node: ast.AST) -> bool:
    """Check if a node is a pytest/unittest exception assertion context manager."""
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        context_expr = item.context_expr
        if isinstance(context_expr, ast.Call):
            method = _get_method_name(context_expr)
            if method in RAISES_CONTEXT_METHODS:
                return True
    return False


def _is_direct_assert_node(node: ast.AST) -> bool:
    """Check if a node is any direct assertion in the current function body."""
    if isinstance(node, ast.Assert):
        return True
    if _is_raises_context(node):
        return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        method = _get_method_name(node.value)
        if method in ASSERT_METHODS:
            return True
    return False


def _collect_top_level_functions(
    tree: ast.Module,
) -> Dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Collect top-level helper functions defined in a test module."""
    functions: Dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
    return functions


def _helper_has_real_assertions(
    helper_name: str,
    helpers: Dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    memo: Dict[str, bool],
    stack: Set[str],
) -> bool:
    """Return True when a helper contains meaningful assertions."""
    if helper_name in memo:
        return memo[helper_name]
    if helper_name in stack:
        return False

    helper = helpers[helper_name]
    next_stack = set(stack)
    next_stack.add(helper_name)

    for node in ast.walk(helper):
        if _is_direct_assert_node(node):
            if not _is_tautological_assert(node) and not _is_shallow_assert(node):
                memo[helper_name] = True
                return True
            continue

        if isinstance(node, ast.Call):
            called_name = _get_method_name(node)
            if called_name in helpers and called_name not in next_stack:
                if _helper_has_real_assertions(called_name, helpers, memo, next_stack):
                    memo[helper_name] = True
                    return True

    memo[helper_name] = False
    return False


def _collect_real_assertion_helpers(tree: ast.Module) -> Set[str]:
    """Collect helper functions whose bodies enforce meaningful assertions."""
    helpers = _collect_top_level_functions(tree)
    memo: Dict[str, bool] = {}
    real_helpers: Set[str] = set()

    for helper_name in helpers:
        if _helper_has_real_assertions(helper_name, helpers, memo, set()):
            real_helpers.add(helper_name)

    return real_helpers


def _is_real_assertion_helper_call(node: ast.AST, real_helpers: Set[str]) -> bool:
    """Check if a node calls a local helper with meaningful assertions."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and _get_method_name(node.value) in real_helpers
    )


# ---------------------------------------------------------------------------
# Test function classification
# ---------------------------------------------------------------------------

def classify_test(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    real_assertion_helpers: Optional[Set[str]] = None,
) -> Tuple[str, str]:
    """Classify a test function. Returns (classification, reason)."""
    assert_nodes: List[ast.AST] = []
    helper_real_count = 0
    real_assertion_helpers = real_assertion_helpers or set()

    for node in ast.walk(func):
        if _is_direct_assert_node(node):
            assert_nodes.append(node)
        elif _is_real_assertion_helper_call(node, real_assertion_helpers):
            helper_real_count += 1

    if not assert_nodes and helper_real_count == 0:
        return TestClass.SHALLOW, "no assertions found"

    tautological_count = 0
    shallow_count = 0
    real_count = helper_real_count

    for node in assert_nodes:
        if _is_tautological_assert(node):
            tautological_count += 1
        elif _is_shallow_assert(node):
            shallow_count += 1
        else:
            real_count += 1

    total = len(assert_nodes) + helper_real_count

    # All tautological
    if tautological_count == total:
        return TestClass.TAUTOLOGICAL, f"all {total} assertions are tautological"

    # All shallow (or mix of shallow + tautological, no real)
    if real_count == 0:
        reasons = []
        if shallow_count > 0:
            reasons.append(f"{shallow_count} shallow")
        if tautological_count > 0:
            reasons.append(f"{tautological_count} tautological")
        return TestClass.SHALLOW, f"only {', '.join(reasons)} assertions ({total} total)"

    return TestClass.REAL, f"{real_count}/{total} real assertions"


def is_test_function(node: ast.AST) -> bool:
    """Check if a node is a test function or method."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name.startswith("test_") or node.name.startswith("test")
    return False


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_file(filepath: str) -> List[TestResult]:
    """Scan a test file and classify all test functions."""
    results: List[TestResult] = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError) as exc:
        print(f"WARNING: Cannot parse {filepath}: {exc}", file=sys.stderr)
        return results

    real_assertion_helpers = _collect_real_assertion_helpers(tree)

    for node in ast.walk(tree):
        if is_test_function(node):
            classification, reason = classify_test(node, real_assertion_helpers)
            results.append(TestResult(
                file=filepath,
                name=node.name,
                line=node.lineno,
                classification=classification,
                reason=reason,
            ))

    return results


def collect_test_files(paths: List[str]) -> List[str]:
    """Expand directories to test_*.py files."""
    result: List[str] = []
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix == ".py":
            result.append(str(path))
        elif path.is_dir():
            for pyfile in sorted(path.rglob("test_*.py")):
                result.append(str(pyfile))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_substance_lint.py <path> [<path> ...]", file=sys.stderr)
        return 2

    targets = sys.argv[1:]
    test_files = collect_test_files(targets)

    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 2

    all_results: List[TestResult] = []
    for filepath in test_files:
        all_results.extend(scan_file(filepath))

    if not all_results:
        print("\nNo test functions found in scanned files.\n")
        return 0

    # Tally
    real = [r for r in all_results if r.classification == TestClass.REAL]
    shallow = [r for r in all_results if r.classification == TestClass.SHALLOW]
    tautological = [r for r in all_results if r.classification == TestClass.TAUTOLOGICAL]
    total = len(all_results)
    real_ratio = len(real) / total if total > 0 else 0.0

    # Report
    print("\n=== L5 Test Substance Audit ===")
    print(f"Files scanned: {len(test_files)}")
    print(f"Tests found:   {total}")
    print(f"  REAL:         {len(real):>4}  ({len(real)/total*100:.0f}%)")
    print(f"  SHALLOW:      {len(shallow):>4}  ({len(shallow)/total*100:.0f}%)")
    print(f"  TAUTOLOGICAL: {len(tautological):>4}  ({len(tautological)/total*100:.0f}%)")
    print(f"  real_ratio:   {real_ratio:.2f}")
    print()

    # Show non-REAL tests
    non_real = shallow + tautological
    if non_real:
        non_real.sort(key=lambda r: (r.file, r.line))
        print("  Non-REAL tests:")
        for r in non_real:
            print(f"    {r.file}:{r.line}  {r.name}  [{r.classification}] {r.reason}")
        print()

    if real_ratio < 0.5:
        print(f"FAIL: real_ratio {real_ratio:.2f} < 0.50 threshold\n")
        return 1
    else:
        print(f"PASS: real_ratio {real_ratio:.2f} >= 0.50 threshold\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
