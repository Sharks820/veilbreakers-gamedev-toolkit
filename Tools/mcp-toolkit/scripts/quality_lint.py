#!/usr/bin/env python3
"""L2 Stub/Orphan AST lint -- detect structural bugs at edit time.

Usage: python scripts/quality_lint.py blender_addon/handlers/
       python scripts/quality_lint.py blender_addon/handlers/terrain_caves.py
Exit code 1 if any findings.

Patterns detected:
  L2-01  STUB-PASS          Function body is pass/return None/return literal
  L2-02  ORPHAN-DELTA        _name = func() where _name is never read
  L2-03  FROZEN-MUTABLE      @dataclass(frozen=True) with Dict/List/Set default
  L2-04  SILENT-SWALLOW      except Exception: pass (no comment)
  L2-05  BARE-EXCEPT         except: (no type specified)
  L2-06  CUBE-FALLBACK       Function returns a default box/cube geometry
  L2-07  HEIGHT-WRITER       stack.set("height",...) outside integrator
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    file: str
    line: int
    pattern_id: str
    pattern_name: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}  [{self.pattern_id}] {self.pattern_name}: {self.message}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_literal(node: ast.AST) -> bool:
    """Return True if node is a constant/literal (str, int, float, bool, None, [], {}, set())."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        # Empty collection literals
        if isinstance(node, ast.Dict):
            return len(node.keys) == 0
        return len(getattr(node, "elts", [])) == 0
    return False


def _is_pass_or_ellipsis(stmt: ast.stmt) -> bool:
    """Return True if statement is `pass` or `...` (Ellipsis)."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        if stmt.value.value is ...:
            return True
    return False


def _is_return_none_or_literal(stmt: ast.stmt) -> bool:
    """Return True if statement is `return`, `return None`, or `return <literal>`."""
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return True
        if _is_literal(stmt.value):
            return True
    return False


def _body_without_docstring(body: List[ast.stmt]) -> List[ast.stmt]:
    """Strip leading docstring from function body."""
    if not body:
        return body
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def _names_read_in(node: ast.AST) -> Set[str]:
    """Collect all Name nodes used in Load context (reads) within a subtree."""
    names: Set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            names.add(child.id)
    return names


# ---------------------------------------------------------------------------
# Pattern checkers
# ---------------------------------------------------------------------------

def check_stub_pass(func: ast.FunctionDef, filepath: str) -> Optional[Finding]:
    """L2-01: Function body is pass/return None/return literal only."""
    body = _body_without_docstring(func.body)
    if not body:
        return Finding(
            file=filepath, line=func.lineno,
            pattern_id="L2-01", pattern_name="STUB-PASS",
            message=f"Function `{func.name}` has empty body (only docstring)",
        )
    # Single-statement body
    if len(body) == 1:
        stmt = body[0]
        if _is_pass_or_ellipsis(stmt):
            return Finding(
                file=filepath, line=func.lineno,
                pattern_id="L2-01", pattern_name="STUB-PASS",
                message=f"Function `{func.name}` body is just `pass`/`...`",
            )
        if _is_return_none_or_literal(stmt):
            return Finding(
                file=filepath, line=func.lineno,
                pattern_id="L2-01", pattern_name="STUB-PASS",
                message=f"Function `{func.name}` body is just a return of None/literal",
            )
    return None


def check_orphan_delta(func: ast.FunctionDef, filepath: str) -> List[Finding]:
    """L2-02: _name = func() where _name never read in the function."""
    findings: List[Finding] = []

    # Gather all names read anywhere in the function body
    all_reads: Set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            all_reads.add(node.id)

    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("_") and target.id != "_":
                # Check if the value is a function call
                if isinstance(node.value, ast.Call):
                    if target.id not in all_reads:
                        findings.append(Finding(
                            file=filepath, line=node.lineno,
                            pattern_id="L2-02", pattern_name="ORPHAN-DELTA",
                            message=f"`{target.id}` assigned but never read in `{func.name}`",
                        ))
    return findings


def check_frozen_mutable(node: ast.ClassDef, filepath: str) -> List[Finding]:
    """L2-03: @dataclass(frozen=True) with Dict/List/Set field default."""
    findings: List[Finding] = []
    is_frozen = False
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            func_node = dec.func
            name = ""
            if isinstance(func_node, ast.Name):
                name = func_node.id
            elif isinstance(func_node, ast.Attribute):
                name = func_node.attr
            if name == "dataclass":
                for kw in dec.keywords:
                    if kw.arg == "frozen" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        is_frozen = True

    if not is_frozen:
        return findings

    mutable_types = {"Dict", "List", "Set", "dict", "list", "set"}
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and stmt.annotation is not None:
            ann = stmt.annotation
            ann_name = ""
            if isinstance(ann, ast.Name):
                ann_name = ann.id
            elif isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
                ann_name = ann.value.id
            if ann_name in mutable_types and stmt.value is not None:
                # Has a default value for a mutable type on a frozen dataclass
                findings.append(Finding(
                    file=filepath, line=stmt.lineno,
                    pattern_id="L2-03", pattern_name="FROZEN-MUTABLE",
                    message=f"Frozen dataclass `{node.name}` has mutable default for `{ann_name}` field",
                ))
    return findings


def check_silent_swallow(tree: ast.AST, filepath: str, source_lines: List[str]) -> List[Finding]:
    """L2-04: except Exception: pass without a comment."""
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # Must catch Exception specifically
        if node.type is None:
            continue  # bare except handled by L2-05
        type_name = ""
        if isinstance(node.type, ast.Name):
            type_name = node.type.id
        elif isinstance(node.type, ast.Attribute):
            type_name = node.type.attr
        if type_name != "Exception":
            continue
        # Body is single `pass`
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            # Check if there's a comment on the same line or line before
            pass_line = node.body[0].lineno
            has_comment = False
            for check_line in range(max(0, pass_line - 2), min(len(source_lines), pass_line + 1)):
                if "#" in source_lines[check_line]:
                    has_comment = True
                    break
            if not has_comment:
                findings.append(Finding(
                    file=filepath, line=node.lineno,
                    pattern_id="L2-04", pattern_name="SILENT-SWALLOW",
                    message="`except Exception: pass` with no explanatory comment",
                ))
    return findings


def check_bare_except(tree: ast.AST, filepath: str) -> List[Finding]:
    """L2-05: except: (no exception type specified)."""
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding(
                file=filepath, line=node.lineno,
                pattern_id="L2-05", pattern_name="BARE-EXCEPT",
                message="Bare `except:` without exception type",
            ))
    return findings


# Cube/box fallback indicator names
_CUBE_INDICATORS = {
    "_make_box", "make_box", "_create_box", "create_box",
    "_make_cube", "make_cube", "_create_cube", "create_cube",
    "primitive_cube_add", "ops.mesh.primitive_cube_add",
    "_fallback_box", "fallback_box", "_fallback_cube", "fallback_cube",
    "default_box", "default_cube",
}


def check_cube_fallback(func: ast.FunctionDef, filepath: str) -> List[Finding]:
    """L2-06: Function returns a default box/cube geometry as fallback."""
    findings: List[Finding] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            # return _make_box(...) or return make_cube(...)
            if isinstance(node.value, ast.Call):
                call_name = ""
                if isinstance(node.value.func, ast.Name):
                    call_name = node.value.func.id
                elif isinstance(node.value.func, ast.Attribute):
                    call_name = node.value.func.attr
                if call_name.lower() in _CUBE_INDICATORS or any(
                    ind in call_name.lower() for ind in ("make_box", "make_cube", "fallback_box", "fallback_cube")
                ):
                    findings.append(Finding(
                        file=filepath, line=node.lineno,
                        pattern_id="L2-06", pattern_name="CUBE-FALLBACK",
                        message=f"`{func.name}` returns cube/box fallback via `{call_name}`",
                    ))
    return findings


# ---------------------------------------------------------------------------
# L2-07: HEIGHT-WRITER — stack.set("height", ...) outside integrator
# ---------------------------------------------------------------------------

# Basename of the ONE file allowed to write height directly
_HEIGHT_WRITER_EXEMPT = "terrain_delta_integrator.py"


def check_height_writer(tree: ast.AST, filepath: str) -> List[Finding]:
    """L2-07: Detect stack.set("height", ...) outside the integrator."""
    basename = os.path.basename(filepath)
    if basename == _HEIGHT_WRITER_EXEMPT:
        return []

    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match *.set("height", ...)
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "set":
            continue
        # First positional arg must be the string "height"
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and first_arg.value == "height":
            findings.append(Finding(
                file=filepath,
                line=node.lineno,
                pattern_id="L2-07",
                pattern_name="HEIGHT-WRITER",
                message='Direct `stack.set("height", ...)` — use a *_delta channel instead',
            ))
    return findings


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------

def scan_file(filepath: str) -> List[Finding]:
    """Parse a single .py file and run all pattern checks."""
    findings: List[Finding] = []
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"WARNING: Cannot read {filepath}: {exc}", file=sys.stderr)
        return findings

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        print(f"WARNING: Syntax error in {filepath}: {exc}", file=sys.stderr)
        return findings

    source_lines = source.splitlines()

    # Tree-level checks
    findings.extend(check_silent_swallow(tree, filepath, source_lines))
    findings.extend(check_bare_except(tree, filepath))
    findings.extend(check_height_writer(tree, filepath))

    # Walk top-level and nested
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result = check_stub_pass(node, filepath)
            if result:
                findings.append(result)
            findings.extend(check_orphan_delta(node, filepath))
            findings.extend(check_cube_fallback(node, filepath))

        if isinstance(node, ast.ClassDef):
            findings.extend(check_frozen_mutable(node, filepath))

    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def collect_py_files(paths: List[str]) -> List[str]:
    """Expand directories to .py files, pass through individual .py files."""
    result: List[str] = []
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix == ".py":
            result.append(str(path))
        elif path.is_dir():
            for pyfile in sorted(path.rglob("*.py")):
                result.append(str(pyfile))
        else:
            print(f"WARNING: Skipping {p} (not a .py file or directory)", file=sys.stderr)
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/quality_lint.py <path> [<path> ...]", file=sys.stderr)
        print("  <path> can be a .py file or a directory (recurses for *.py)", file=sys.stderr)
        return 2

    targets = sys.argv[1:]
    py_files = collect_py_files(targets)

    if not py_files:
        print("No .py files found in the given paths.", file=sys.stderr)
        return 2

    all_findings: List[Finding] = []
    for filepath in py_files:
        all_findings.extend(scan_file(filepath))

    # Print results
    if all_findings:
        # Sort by file, then line
        all_findings.sort(key=lambda f: (f.file, f.line))
        print(f"\n=== L2 Quality Lint: {len(all_findings)} finding(s) ===\n")
        for f in all_findings:
            print(f"  {f}")
        print()
        return 1
    else:
        print(f"\nL2 Quality Lint: CLEAN ({len(py_files)} files scanned, 0 findings)\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
