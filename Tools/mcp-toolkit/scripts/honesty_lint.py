#!/usr/bin/env python3
"""L4 Honesty linter -- verify plan claims match reality.

Usage: python scripts/honesty_lint.py [plan.md] [source_dir ...]
       python scripts/honesty_lint.py  (uses defaults from terrain contract)

Checks:
  1. Every [x] checkbox in markdown -> extract function name -> verify exists in source with >5 LOC
  2. Report checked vs unchecked ratio
Exit code 1 if any claimed function is missing or is a stub (<= 5 LOC).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClaimResult:
    function_name: str
    line_in_plan: int
    found: bool
    source_file: Optional[str] = None
    loc: int = 0
    is_stub: bool = False

    @property
    def status(self) -> str:
        if not self.found:
            return "MISSING"
        if self.is_stub:
            return "STUB"
        return "OK"


# ---------------------------------------------------------------------------
# Extract function names from [x] checkboxes
# ---------------------------------------------------------------------------

# Patterns to extract function names from checkbox lines:
#   - [x] `func_name` ...
#   - [x] func_name(...) ...
#   - [x] Implement func_name ...
#   - [x] ... pass_something ...
_FUNC_PATTERNS = [
    re.compile(r"`(\w+)`"),                          # backtick-quoted
    re.compile(r"\b(pass_\w+)\b"),                   # pass_xxx convention
    re.compile(r"\b(register_\w+)\b"),               # register_xxx
    re.compile(r"\b(\w+)\s*\("),                     # name( call syntax
]


def extract_checkbox_claims(plan_text: str) -> List[Tuple[int, str]]:
    """Return list of (line_number, function_name) from checked checkboxes."""
    claims: List[Tuple[int, str]] = []
    seen: Set[str] = set()

    for lineno, line in enumerate(plan_text.splitlines(), 1):
        # Match checked checkbox: - [x] or * [x] or [x]
        if not re.search(r"\[x\]", line, re.IGNORECASE):
            continue

        # Try to extract a function name
        for pattern in _FUNC_PATTERNS:
            match = pattern.search(line)
            if match:
                name = match.group(1)
                # Skip common non-function words
                if name.lower() in {"true", "false", "none", "self", "cls", "the", "and", "for", "all"}:
                    continue
                if len(name) < 3:
                    continue
                if name not in seen:
                    seen.add(name)
                    claims.append((lineno, name))
                break

    return claims


def count_checkboxes(plan_text: str) -> Tuple[int, int]:
    """Return (checked_count, unchecked_count)."""
    checked = len(re.findall(r"\[x\]", plan_text, re.IGNORECASE))
    unchecked = len(re.findall(r"\[\s?\]", plan_text))
    return checked, unchecked


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------

def build_function_index(source_dirs: List[str]) -> Dict[str, Tuple[str, int]]:
    """Build {func_name: (filepath, line_count)} from all .py files in source dirs."""
    index: Dict[str, Tuple[str, int]] = {}

    for src_dir in source_dirs:
        src_path = Path(src_dir)
        if not src_path.exists():
            continue
        py_files = list(src_path.rglob("*.py")) if src_path.is_dir() else [src_path]

        for pyfile in py_files:
            try:
                source = pyfile.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(pyfile))
            except (SyntaxError, OSError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Calculate LOC (non-blank, non-comment, non-docstring lines)
                    loc = _function_loc(node, source)
                    # Keep the largest version if name appears in multiple files
                    if node.name not in index or index[node.name][1] < loc:
                        index[node.name] = (str(pyfile), loc)

    return index


def _function_loc(func: ast.FunctionDef, source: str) -> int:
    """Count meaningful LOC in a function (exclude docstring, blank, comment-only)."""
    lines = source.splitlines()
    start = func.lineno - 1
    end = func.end_lineno if hasattr(func, "end_lineno") and func.end_lineno else start + 1
    body_lines = lines[start:end]

    count = 0
    in_docstring = False
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip triple-quoted docstrings (simplified)
        if '"""' in stripped or "'''" in stripped:
            quotes = '"""' if '"""' in stripped else "'''"
            occ = stripped.count(quotes)
            if occ == 1:
                in_docstring = not in_docstring
                continue
            elif occ >= 2:
                continue  # single-line docstring
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        count += 1

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Defaults
    plan_path: Optional[str] = None
    source_dirs: List[str] = []

    args = sys.argv[1:]
    for arg in args:
        if arg.endswith(".md"):
            plan_path = arg
        else:
            source_dirs.append(arg)

    # Try finding defaults — search cwd and up to 3 parent levels
    if plan_path is None:
        candidates = [
            "docs/terrain_ultra_implementation_plan_2026-04-08.md",
            ".planning/contracts/terrain.yaml",
        ]
        search_roots = [Path(".")]
        for i in range(1, 4):
            search_roots.append(Path(*[".."] * i))
        for root in search_roots:
            for c in candidates:
                full = root / c
                if full.exists():
                    plan_path = str(full)
                    break
            if plan_path:
                break

    if plan_path is None:
        print("No plan file found. Pass a .md file as argument.", file=sys.stderr)
        print("Usage: python scripts/honesty_lint.py [plan.md] [source_dir ...]", file=sys.stderr)
        return 2

    if not source_dirs:
        default_dirs = ["blender_addon/handlers/", "src/"]
        for root in [Path(".")] + [Path(*[".."] * i) for i in range(1, 4)]:
            found = [str(root / d) for d in default_dirs if (root / d).exists()]
            if found:
                source_dirs = found
                break
        if not source_dirs:
            print("No source directories found. Pass source dirs as arguments.", file=sys.stderr)
            return 2

    # Read plan
    try:
        plan_text = Path(plan_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"Cannot read plan file: {exc}", file=sys.stderr)
        return 2

    # Extract claims and build index
    claims = extract_checkbox_claims(plan_text)
    checked, unchecked = count_checkboxes(plan_text)
    func_index = build_function_index(source_dirs)

    # Verify claims
    results: List[ClaimResult] = []
    for line_no, func_name in claims:
        if func_name in func_index:
            filepath, loc = func_index[func_name]
            is_stub = loc <= 5
            results.append(ClaimResult(
                function_name=func_name,
                line_in_plan=line_no,
                found=True,
                source_file=filepath,
                loc=loc,
                is_stub=is_stub,
            ))
        else:
            results.append(ClaimResult(
                function_name=func_name,
                line_in_plan=line_no,
                found=False,
            ))

    # Report
    failures = [r for r in results if r.status != "OK"]

    print(f"\n=== L4 Honesty Lint ===")
    print(f"Plan:      {plan_path}")
    print(f"Sources:   {', '.join(source_dirs)}")
    print(f"Checkboxes: {checked} checked, {unchecked} unchecked", end="")
    if checked + unchecked > 0:
        ratio = checked / (checked + unchecked) * 100
        print(f" ({ratio:.0f}% done)")
    else:
        print()
    print(f"Claims verified: {len(results)} functions")
    print()

    if results:
        ok_count = sum(1 for r in results if r.status == "OK")
        missing_count = sum(1 for r in results if r.status == "MISSING")
        stub_count = sum(1 for r in results if r.status == "STUB")
        print(f"  OK: {ok_count}  |  MISSING: {missing_count}  |  STUB (<=5 LOC): {stub_count}")
        print()

    if failures:
        print("  FAILURES:")
        for r in failures:
            if r.status == "MISSING":
                print(f"    plan:{r.line_in_plan}  {r.function_name} -> NOT FOUND in source")
            elif r.status == "STUB":
                print(f"    plan:{r.line_in_plan}  {r.function_name} -> STUB ({r.loc} LOC) in {r.source_file}")
        print()
        return 1
    else:
        if results:
            print("  All claimed functions verified.\n")
        else:
            print("  No function claims extracted from checkboxes.\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
