#!/usr/bin/env python3
"""
regen_contract_tests.py -- Validate terrain.yaml contract against real code.

Reads .planning/contracts/terrain.yaml and verifies:
  1. Every pass file exists on disk
  2. Every pass function is defined in its file
  3. No pass function body is <=5 LOC (stub detection)
  4. Every claimed 'mutates' channel is written to in the function body

Exit code 0 if all pass, 1 if any fail.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # veilbreakers-gamedev-toolkit
CONTRACT_PATH = REPO_ROOT / ".planning" / "contracts" / "terrain.yaml"
HANDLERS_DIR = REPO_ROOT / "Tools" / "mcp-toolkit" / "blender_addon" / "handlers"


def load_contract() -> dict:
    """Load and return the terrain contract YAML."""
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_file_ref(file_ref: str) -> tuple[str, int | None]:
    """Parse 'terrain_cliffs.py:552' -> ('terrain_cliffs.py', 552)."""
    if ":" in file_ref:
        parts = file_ref.rsplit(":", 1)
        try:
            return parts[0], int(parts[1])
        except ValueError:
            return file_ref, None
    return file_ref, None


def _count_function_loc(source_path: Path, func_name: str) -> int | None:
    """Count lines in the body of *func_name* using AST. Returns None if not found."""
    try:
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
    except (SyntaxError, OSError):
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            if node.body:
                first = node.body[0].lineno
                last = node.body[-1].end_lineno or node.body[-1].lineno
                return last - first + 1
            return 0
    return None


def _function_body_source(source_path: Path, func_name: str) -> str | None:
    """Return the raw source text of *func_name*'s body."""
    try:
        lines = source_path.read_text(encoding="utf-8").splitlines()
        tree = ast.parse("\n".join(lines), filename=str(source_path))
    except (SyntaxError, OSError):
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            if node.body:
                first = node.body[0].lineno - 1  # 0-indexed
                last = (node.body[-1].end_lineno or node.body[-1].lineno)
                return "\n".join(lines[first:last])
            return ""
    return None


def _check_mutates(source_path: Path, func_name: str, channels: list[str]) -> list[str]:
    """Return list of channels NOT found written in the function body."""
    body = _function_body_source(source_path, func_name)
    if body is None:
        return channels  # can't verify -- treat all as missing

    missing = []
    for ch in channels:
        # Normalise: 'height (conditional)' -> 'height'
        clean = re.sub(r"\s*\(.*\)", "", ch).strip()
        # Check common patterns: stack["channel"], stack.channel, ["channel"], .channel =
        patterns = [
            re.escape(f'["{clean}"]'),
            re.escape(f"['{clean}']"),
            rf"\b{re.escape(clean)}\b",
        ]
        found = any(re.search(p, body) for p in patterns)
        if not found:
            missing.append(ch)
    return missing


# ------------------------------------------------------------------
# Main validation
# ------------------------------------------------------------------
class Result:
    def __init__(self, bundle: str, check: str, passed: bool, detail: str = ""):
        self.bundle = bundle
        self.check = check
        self.passed = passed
        self.detail = detail

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        msg = f"  [{status}] {self.bundle} / {self.check}"
        if self.detail:
            msg += f"  -- {self.detail}"
        return msg


def validate_contract() -> list[Result]:
    contract = load_contract()
    results: list[Result] = []

    bundle_keys = [k for k in contract if k.startswith("bundle_")]

    for bkey in sorted(bundle_keys):
        bundle = contract[bkey]
        bname = bundle.get("name", bkey)
        passes = bundle.get("passes", [])

        for p in passes:
            pname = p["name"]
            file_ref = p["file"]
            filename, _line = _parse_file_ref(file_ref)
            fpath = HANDLERS_DIR / filename

            # 1. File exists
            exists = fpath.is_file()
            results.append(Result(bname, f"{pname}: file exists ({filename})", exists))
            if not exists:
                continue

            # 2. Function importable (defined in file)
            loc = _count_function_loc(fpath, pname)
            func_found = loc is not None
            results.append(Result(bname, f"{pname}: function defined", func_found))
            if not func_found:
                continue

            # 3. Body > 5 LOC
            not_stub = loc > 5
            results.append(Result(bname, f"{pname}: not a stub (LOC={loc})", not_stub))

            # 4. Mutates channels written
            mutates = p.get("mutates", [])
            if mutates:
                missing = _check_mutates(fpath, pname, mutates)
                ok = len(missing) == 0
                detail = f"missing writes: {missing}" if missing else ""
                results.append(Result(bname, f"{pname}: mutates channels written", ok, detail))

        # Helpers (if present)
        for helper in bundle.get("helpers", []):
            hname = helper["name"]
            hfile = helper["file"]
            hfilename, _ = _parse_file_ref(hfile)
            hpath = HANDLERS_DIR / hfilename
            if hpath.is_file():
                hloc = _count_function_loc(hpath, hname)
                results.append(Result(bname, f"helper {hname}: defined", hloc is not None))
            else:
                results.append(Result(bname, f"helper {hname}: file exists ({hfilename})", False))

    return results


def main() -> int:
    print(f"Loading contract: {CONTRACT_PATH}")
    results = validate_contract()

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print(f"\n{'='*60}")
    print(f"Terrain Contract Validation: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    for r in results:
        if not r.passed:
            print(r)

    if failed == 0:
        print("  All checks PASSED.")

    print(f"\n{'='*60}")
    print(f"Total: {passed + failed}  |  PASS: {passed}  |  FAIL: {failed}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
