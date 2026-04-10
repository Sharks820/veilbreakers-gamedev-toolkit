"""VeilBreakers Python Rules Module.

This module contains all 30 Python code review rules extracted and improved
from the original vb_python_reviewer.py. Rules are classified into three layers:

- Layer 1 (hard_correctness): Deterministic, no false positives
- Layer 2 (semantic): Context-aware guards needed
- Layer 3 (heuristic): Strict/audit mode only

Each rule includes optional guard functions for false positive suppression.
Guard functions accept (line, all_lines, idx, context=None) and return bool.
When requires_context=True, the scanner passes cross-file context dict.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from veilbreakers_mcp._types import Category, FindingType, Severity


_SEVERITY_BASE_CONF = {
    "CRITICAL": 95,
    "HIGH": 85,
    "MEDIUM": 75,
    "LOW": 70,
}


@dataclass
class Rule:
    id: str
    severity: Severity
    category: Category
    description: str
    fix: str
    pattern: re.Pattern
    anti_patterns: list[re.Pattern] = field(default_factory=list)
    anti_radius: int = 3
    guard: Optional[Callable] = None
    finding_type: Optional[FindingType] = None
    confidence: int = -1
    priority: int = -1
    reasoning: Optional[str] = None
    layer: str = "hard_correctness"
    requires_context: bool = False
    auto_fix: Optional[Callable[..., Any]] = None

    def __post_init__(self):
        if self.confidence < 0:
            self.confidence = _SEVERITY_BASE_CONF.get(self.severity.name, 60)
        if self.priority < 0:
            if self.severity == Severity.CRITICAL:
                self.priority = 95
            elif self.severity == Severity.HIGH:
                self.priority = 75
            elif self.severity == Severity.MEDIUM:
                self.priority = 50
            else:
                self.priority = 20
        if self.finding_type is None:
            if self.category == Category.Performance:
                self.finding_type = FindingType.OPTIMIZATION
            elif self.category == Category.Quality:
                self.finding_type = FindingType.STRENGTHENING
            elif self.category == Category.Security:
                self.finding_type = FindingType.ERROR
            else:
                self.finding_type = FindingType.BUG


# =========================================================================
#  Anti-pattern helpers (Guard Functions)
# =========================================================================


def _suppressed_by_anti(
    anti: list[re.Pattern],
    lines: list[str],
    idx: int,
    radius: int,
    filepath: str = "",
) -> bool:
    """Return True if any anti-pattern matches nearby lines or filepath."""
    if not anti:
        return False
    lo = max(0, idx - radius)
    hi = min(len(lines) - 1, idx + radius)
    for j in range(lo, hi + 1):
        for ap in anti:
            if ap.search(lines[j]):
                return True
    if filepath:
        for ap in anti:
            if ap.search(filepath):
                return True
    return False


def _is_comment(line: str) -> bool:
    """Check if line is a comment."""
    return line.lstrip().startswith("#")


def _in_string_literal(line: str) -> bool:
    """Check if line starts with a string literal."""
    stripped = line.lstrip()
    return stripped.startswith(("'", '"', "b'", 'b"', "f'", 'f"', "r'", 'r"'))


def _docstring_insertion_index(lines: list[str], start_idx: int) -> int:
    """Return the first safe line index after an opening function docstring."""
    if start_idx >= len(lines):
        return start_idx
    stripped = lines[start_idx].lstrip()
    quote_match = re.match(r'^[rubfRUBF]*("""|\'\'\'|"|\')', stripped)
    if not quote_match:
        return start_idx
    quote = quote_match.group(1)
    if quote in ('"', "'"):
        return start_idx + 1
    if stripped.count(quote) >= 2 and stripped != quote:
        return start_idx + 1
    for idx in range(start_idx + 1, len(lines)):
        if quote in lines[idx]:
            return idx + 1
    return start_idx


def _autofix_eval(line: str, _all_lines: list[str], idx: int) -> dict[str, Any] | None:
    if "ast.literal_eval" in line:
        return None
    replaced = re.sub(r"\beval\s*\(", "ast.literal_eval(", line, count=1)
    if replaced == line:
        return None
    return {
        "edits": [{"start": idx, "end": idx + 1, "replacement": [replaced]}],
        "imports": ["import ast"],
    }


def _autofix_mutable_default(
    line: str, all_lines: list[str], idx: int
) -> dict[str, Any] | None:
    match = re.search(
        r"^(?P<indent>\s*)def\s+(?P<name>\w+)\s*\((?P<params>.*)\)\s*:\s*$", line
    )
    if not match:
        return None
    params = match.group("params")
    default_match = re.search(
        r"(?P<param>\w+)\s*=\s*(?P<default>\[\]|\{\}|set\(\))", params
    )
    if not default_match:
        return None
    if idx + 1 < len(all_lines):
        next_line = all_lines[idx + 1].lstrip()
        if re.match(r'^[rubfRUBF]*("""|\'\'\'|"|\')', next_line):
            return None
    param_name = default_match.group("param")
    default_value = default_match.group("default")
    new_params = (
        params[: default_match.start()]
        + f"{param_name}=None"
        + params[default_match.end() :]
    )
    new_def_line = f"{match.group('indent')}def {match.group('name')}({new_params}):"
    body_indent = f"{match.group('indent')}    "
    insert_at = _docstring_insertion_index(all_lines, idx + 1)
    return {
        "edits": [
            {"start": idx, "end": idx + 1, "replacement": [new_def_line]},
            {
                "start": insert_at,
                "end": insert_at,
                "replacement": [
                    f"{body_indent}if {param_name} is None:",
                    f"{body_indent}    {param_name} = {default_value}",
                ],
            },
        ]
    }


def _autofix_none_comparison(
    line: str, _all_lines: list[str], idx: int
) -> dict[str, Any] | None:
    replaced = re.sub(r"==\s*None\b", "is None", line)
    replaced = re.sub(r"!=\s*None\b", "is not None", replaced)
    if replaced == line:
        return None
    return {
        "edits": [{"start": idx, "end": idx + 1, "replacement": [replaced]}]
    }


def _autofix_float_equality(
    line: str, _all_lines: list[str], idx: int
) -> dict[str, Any] | None:
    stripped = line.strip()
    comment = ""
    if " #" in stripped:
        stripped, comment = stripped.split(" #", 1)
        comment = f"  #{comment}"
    prefix = ""
    suffix = ""
    expr = stripped
    for keyword in ("if ", "elif ", "while ", "return ", "assert "):
        if expr.startswith(keyword):
            prefix = keyword
            expr = expr[len(keyword) :]
            break
    if expr.endswith(":"):
        expr = expr[:-1].rstrip()
        suffix = ":"
    match = re.match(
        r"(?P<left>.+?)\s*(?P<op>==|!=)\s*(?P<right>\d+\.\d+)\s*$", expr
    )
    if not match:
        return None
    left = match.group("left").strip()
    right = match.group("right")
    replacement_expr = f"math.isclose({left}, {right})"
    if match.group("op") == "!=":
        replacement_expr = f"not {replacement_expr}"
    leading = line[: len(line) - len(line.lstrip())]
    replaced = f"{leading}{prefix}{replacement_expr}{suffix}{comment}"
    if replaced == line:
        return None
    return {
        "edits": [{"start": idx, "end": idx + 1, "replacement": [replaced]}],
        "imports": ["import math"],
    }


def _autofix_pathlib_join(
    line: str, _all_lines: list[str], idx: int
) -> dict[str, Any] | None:
    match = re.search(r"os\.path\.join\((?P<args>[^()]*)\)", line)
    if not match:
        return None
    args = [arg.strip() for arg in match.group("args").split(",") if arg.strip()]
    if len(args) < 2:
        return None
    path_expr = " / ".join([f"Path({args[0]})", *args[1:]])
    replaced = f"{line[: match.start()]}{path_expr}{line[match.end() :]}"
    if replaced == line:
        return None
    return {
        "edits": [{"start": idx, "end": idx + 1, "replacement": [replaced]}],
        "imports": ["from pathlib import Path"],
    }


def _active_code(
    line: str, _all: list[str], _idx: int, _context: Optional[dict] = None
) -> bool:
    """Check if line is active code (not comment or string)."""
    return not _is_comment(line) and not _in_string_literal(line)


def _has_blender_cleanup_in_scope(
    line: str, all_lines: list[str], idx: int, _context: Optional[dict] = None
) -> bool:
    """Return True only when a Blender allocation still looks unprotected.

    BLE-02 used to look only a few lines around the allocation, which caused
    false positives when cleanup or protection lived later in the same function.
    This guard scans the surrounding function body for a cleanup call or an
    enclosing try/finally-style protection block before emitting a finding.
    """
    current_indent = len(line) - len(line.lstrip())

    # Walk backward to find the current function boundary.
    func_start = 0
    for j in range(idx, -1, -1):
        stripped = all_lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(all_lines[j]) - len(all_lines[j].lstrip())
        if indent < current_indent and stripped.startswith(("def ", "async def ")):
            func_start = j
            break

    func_indent = len(all_lines[func_start]) - len(all_lines[func_start].lstrip()) if func_start < len(all_lines) else 0

    # Walk forward until the function ends.
    func_end = len(all_lines)
    for j in range(idx + 1, len(all_lines)):
        stripped = all_lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(all_lines[j]) - len(all_lines[j].lstrip())
        if indent <= func_indent and not stripped.startswith(("elif ", "else:", "except ", "finally:")):
            func_end = j
            break

    cleanup_markers = (
        ".remove(",
        "remove(obj",
        "remove(mesh",
        "remove(mat",
        "remove(material",
        "remove(cliff_obj",
        "remove(cliff_mesh",
    )
    for j in range(idx + 1, func_end):
        candidate = all_lines[j]
        stripped = candidate.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(marker in candidate for marker in cleanup_markers):
            return False
        if stripped.startswith("finally:"):
            return False

    # If the allocation already lives under a try block inside the same function,
    # assume the surrounding control flow is intentionally managing cleanup.
    for j in range(idx - 1, func_start - 1, -1):
        stripped = all_lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(all_lines[j]) - len(all_lines[j].lstrip())
        if indent < current_indent and stripped.startswith("try:"):
            return False

    return True


def _match_is_in_string(line: str, match_pos: int) -> bool:
    """Return True if match_pos falls inside a quoted string on this line."""
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if idx == match_pos:
            return in_single or in_double
    return False


def _is_inside_except(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Return True if this raise is actually inside an except block body."""
    raise_indent = len(line) - len(line.lstrip())
    for j in range(idx - 1, max(0, idx - 10) - 1, -1):
        stripped = all_lines[j].lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        line_indent = len(all_lines[j]) - len(all_lines[j].lstrip())
        if line_indent <= raise_indent and not stripped.startswith("except"):
            if stripped.startswith(("raise ", "return ", "pass", "logger", "log")):
                continue
            return False
        if stripped.startswith("except") and line_indent < raise_indent:
            return True
    return False


def _check_mutable_get(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Return True only if the .get() result variable is actually mutated nearby.

    This guard reduces false positives by only flagging when the mutable default
    is actually being modified, not just read.
    """
    # Skip if consumed read-only on the same line
    if re.search(r"\b(len|for|if|return|print|not|or|and)\s*[\s(].*\.get\s*\(", line):
        return False
    # Skip if next lines show read-only usage
    for j in range(idx + 1, min(len(all_lines), idx + 8)):
        if re.search(r"\.(items|keys|values)\s*\(|for\s+\w+\s+(in|,)", all_lines[j]):
            return False
    # Extract the variable name that receives the .get() result
    m = re.match(r"\s*(\w+)\s*=\s*\w+\.get\s*\(", line)
    if m:
        var_name = m.group(1)
        # Only flag if THIS variable is mutated (.append, .extend, [key]=)
        for j in range(idx + 1, min(len(all_lines), idx + 5)):
            if re.search(
                rf"\b{re.escape(var_name)}\b\.(append|extend|add|update|insert)\s*\(",
                all_lines[j],
            ):
                return True
            if re.search(rf"\b{re.escape(var_name)}\b\[.+\]\s*=", all_lines[j]):
                return True
        return False
    # Inline .get() (not assigned) — only flag if mutation is chained on .get() result
    # e.g., d.get("k", []).append(v) — this is the mutable default bug
    # but NOT: x.extend(d.get("k", [])) — this extends x, not the default
    return bool(re.search(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))\)\s*\.(append|extend|add|update|insert)\s*\(", line))


def _check_late_binding(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Return True if a for-loop has a lambda using the loop var without default capture.

    Skips ``for`` that is part of a list/dict/set comprehension or generator
    expression -- those create their own scope and are not late-binding bugs.
    """
    m = re.search(r"for\s+(\w+)\s+in\b", line)
    if not m:
        return False
    loop_var = m.group(1)
    loop_indent = len(line) - len(line.lstrip())

    # If the ``for`` lives inside a comprehension [...], {...}, or (...) it
    # is NOT a loop-level variable capture -- skip.
    match_pos = m.start()
    before = line[:match_pos]
    after = line[match_pos:]
    open_sq = before.count("[") - before.count("]")
    open_cr = before.count("{") - before.count("}")
    open_paren = before.count("(") - before.count(")")
    if open_sq > 0 or open_cr > 0:
        return False
    if open_paren > 0 and re.search(r"\bfor\s+\w+\s+in\b", after):
        if ")" in after:
            return False

    for j in range(idx + 1, min(len(all_lines), idx + 8)):
        candidate_line = all_lines[j]
        stripped_candidate = candidate_line.strip()
        if stripped_candidate and not stripped_candidate.startswith("#"):
            candidate_indent = len(candidate_line) - len(candidate_line.lstrip())
            if candidate_indent <= loop_indent:
                break

        lam = re.search(r"lambda\b([^:]*?):", candidate_line)
        if not lam:
            continue
        if _match_is_in_string(candidate_line, lam.start()):
            continue
        # Check for loop var in the lambda BODY (after the colon), not the whole line
        lambda_body = candidate_line[lam.end():]
        if not re.search(rf"\b{re.escape(loop_var)}\b", lambda_body):
            continue
        if re.search(
            rf"\b{re.escape(loop_var)}\s*=\s*{re.escape(loop_var)}\b", lam.group(1)
        ):
            continue
        return True
    return False


def _check_discarded_assignment(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """PY-COR-16 guard: `_name = func()` where _name is never referenced again.

    Catches the terrain_caves.py:821 pattern where a function return value
    that the caller must apply (delta, mask, patch) is silently discarded
    because the author used an underscore prefix thinking it was "unused".
    """
    m = re.match(r"^(\s*)(_[a-zA-Z]\w*)\s*=\s*(\w+[\w.]*)\s*\(", line)
    if not m:
        return False
    indent_str = m.group(1)
    var_name = m.group(2)
    # Bare `_ = ...` is explicit discard, accept it
    if var_name == "_":
        return False
    # Module-level assignment (indent 0) — skip, this is a private module constant
    # that is referenced by name elsewhere in the module.
    if len(indent_str) == 0:
        return False
    # UPPER_SNAKE_CASE indicates a constant, not a discarded value
    if var_name[1:].isupper() or re.match(r"_[A-Z][A-Z0-9_]*$", var_name):
        return False
    # Skip if the function name itself is clearly a side-effect setter
    func_name = m.group(3).split(".")[-1]
    side_effect_prefixes = ("set", "apply", "update", "mark", "register", "emit", "log", "print", "write", "save", "push", "append", "add_", "insert", "remove", "delete", "clear", "reset")
    if func_name.lower().startswith(side_effect_prefixes):
        return False
    # Look ahead for ANY read of var_name in subsequent code.
    # Nested helpers still count as a legitimate use, so don't stop at inner defs.
    for j in range(idx + 1, min(len(all_lines), idx + 200)):
        lookahead = all_lines[j]
        stripped = lookahead.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        # Reference counts as read; assignment to same name does not
        if re.search(rf"(?<![\.\w]){re.escape(var_name)}\b", lookahead):
            # Exclude left-hand-side reassignment `_name = ...`
            if re.match(rf"^\s*{re.escape(var_name)}\s*=\s*[^=]", lookahead):
                continue
            return False  # read found, not discarded
    return True


def _check_frozen_mutable_field(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """PY-COR-17 guard: field line is inside a `@dataclass(frozen=True)` class.

    Walks backward from the current line to find the enclosing class definition;
    fires only if a `@dataclass(frozen=True)` decorator precedes it.
    """
    field_indent = len(line) - len(line.lstrip())
    # Walk backward within the same indentation band
    for j in range(idx - 1, max(0, idx - 80), -1):
        prev = all_lines[j]
        stripped = prev.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        prev_indent = len(prev) - len(prev.lstrip())
        # Found a class header at an outer indent
        if prev_indent < field_indent and stripped.startswith("class "):
            # Scan the 1-4 lines above the class for a frozen=True decorator
            for k in range(max(0, j - 4), j):
                if re.search(r"@dataclass\s*\([^)]*frozen\s*=\s*True", all_lines[k]):
                    return True
            return False
    return False


def _check_validator_self_rollback(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """PY-COR-18 guard: rollback() call is inside a function named validate_*.

    Walks backward to find the enclosing `def validate_...(`. Validators should
    report, not rollback; rollback is the orchestrator's decision.
    """
    call_indent = len(line) - len(line.lstrip())
    for j in range(idx - 1, max(0, idx - 200), -1):
        prev = all_lines[j]
        stripped = prev.lstrip()
        if not stripped:
            continue
        prev_indent = len(prev) - len(prev.lstrip())
        if prev_indent < call_indent and stripped.startswith("def "):
            m = re.match(r"def\s+(\w+)", stripped)
            if m and m.group(1).startswith("validate"):
                return True
            return False
    return False


def _check_fallback_before_primary(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """PY-COR-19 guard: fallback branch contains an early `return`, and the
    enclosing function has more code after the block (implying that trailing
    code is the *real* primary check, now unreachable when fallback is true).
    """
    if "fallback" not in line.lower():
        return False
    # Skip if `fallback` is just a local variable (RHS of assignment or function arg)
    stripped_line = line.lstrip()
    if re.match(r"(\w+\s*=\s*.*fallback|if\s+fallback\s*:)", stripped_line):
        # `if fallback:` where fallback is a variable — not the bug pattern.
        # The bug pattern is `if obj.xxx_fallback:` (attribute flag) or
        # `if camera.basis_fallback:` (flag indicating fallback mode).
        if re.match(r"if\s+\w+\s*:", stripped_line):
            return False  # bare `if fallback:` — just a variable
    if_indent = len(line) - len(line.lstrip())
    # 0. Check if a peer-scope `return` already ran BEFORE this if-block
    # (meaning primary already had its chance — this fallback is legitimately second).
    for j in range(idx - 1, max(0, idx - 30), -1):
        prev = all_lines[j]
        ps = prev.lstrip()
        if not ps or ps.startswith("#"):
            continue
        prev_indent = len(prev) - len(prev.lstrip())
        if prev_indent < if_indent and ps.startswith("def "):
            break
        if prev_indent == if_indent and ps.startswith("return "):
            return False  # primary already returned above — fallback is correctly second
    # 1. Confirm the next non-empty line at indent > if_indent is a `return`
    block_has_return = False
    block_end = idx + 1
    for j in range(idx + 1, min(len(all_lines), idx + 15)):
        nxt = all_lines[j]
        stripped = nxt.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        this_indent = len(nxt) - len(nxt.lstrip())
        if this_indent <= if_indent:
            block_end = j
            break
        if re.match(r"return\b", stripped):
            block_has_return = True
    if not block_has_return:
        return False
    # 2. Find enclosing def indent
    fn_indent = -1
    for j in range(idx - 1, max(0, idx - 200), -1):
        prev = all_lines[j]
        stripped = prev.lstrip()
        if not stripped:
            continue
        prev_indent = len(prev) - len(prev.lstrip())
        if prev_indent < if_indent and stripped.startswith("def "):
            fn_indent = prev_indent
            break
    if fn_indent < 0:
        return False
    # 3. After the if-block, look for ANY further code at if_indent
    # (same scope as the fallback) inside the same function.
    for j in range(block_end, min(len(all_lines), idx + 200)):
        nxt = all_lines[j]
        stripped = nxt.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        this_indent = len(nxt) - len(nxt.lstrip())
        # Left the function entirely
        if this_indent <= fn_indent:
            return False
        # Same-scope code (peer statements) found — fallback returned before primary
        if this_indent == if_indent:
            return True
    return False


def _check_broad_except_silent(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Improved PY-COR-12 guard: checks for logging, structured return, or deliberate handling.

    Only fires when broad except silently swallows the exception without
    proper logging, error propagation, or deliberate fallback handling.

    Suppression 1 (2026-04-09): enclosing function named _safe_*/_try_*/_probe_*
    Suppression 2 (2026-04-09): trailing/adjacent intent comment (non-fatal, best-effort, etc.)
    Suppression 3 (2026-04-09): fallback-flag pattern (ok = False; try; ok = True; except: pass)
    Suppression 4 (2026-04-09): `continue` in for-loop best-effort pattern
    """
    except_indent = len(line) - len(line.lstrip())

    # --- Suppression 1: sentinel-return function contracts ---
    for j in range(idx - 1, max(0, idx - 200), -1):
        prev = all_lines[j]
        stripped = prev.lstrip()
        if not stripped:
            continue
        prev_indent = len(prev) - len(prev.lstrip())
        if prev_indent < except_indent and stripped.startswith("def "):
            fn_m = re.match(r"def\s+(\w+)", stripped)
            if fn_m:
                fn_name = fn_m.group(1)
                if fn_name.startswith(("_safe_", "_try_", "_probe_")) or fn_name.endswith("_or_none"):
                    return False
            break

    # --- Suppression 2: intent comments on pass/continue/return lines ---
    _intent_rx = re.compile(
        r"#.*(non[- ]?fatal|best[- ]?effort|fallback|non[- ]?critical|optional|"
        r"pragma:\s*no cover|intentional|fall[- ]?through|best effort|non.critical|"
        r"enhancement is non|skip|ignore)",
        re.IGNORECASE,
    )
    for j in range(idx, min(len(all_lines), idx + 6)):
        if _intent_rx.search(all_lines[j]):
            return False

    # --- Suppression 3: fallback-flag pattern ---
    # Look backward for `*_ok = False` within 8 lines before the `try:` for this except
    try_line_idx = None
    for j in range(idx - 1, max(0, idx - 30), -1):
        stripped = all_lines[j].lstrip()
        if stripped.startswith("try:") or stripped.startswith("try "):
            try_line_idx = j
            break
    if try_line_idx is not None:
        for j in range(max(0, try_line_idx - 8), try_line_idx):
            if re.search(r"\w+_ok\s*=\s*False", all_lines[j]):
                return False

    # --- Suppression 4: continue in for-loop best-effort ---
    for j in range(idx + 1, min(len(all_lines), idx + 6)):
        stripped = all_lines[j].lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        this_indent = len(all_lines[j]) - len(all_lines[j].lstrip())
        if this_indent <= except_indent:
            break
        if stripped == "continue":
            # Verify we're inside a for loop by walking backward
            for k in range(idx - 1, max(0, idx - 40), -1):
                for_stripped = all_lines[k].lstrip()
                for_indent = len(all_lines[k]) - len(all_lines[k].lstrip())
                if for_indent < except_indent and for_stripped.startswith(("for ", "while ")):
                    return False
            break

    # Look ahead in the except block for meaningful handling
    for j in range(idx + 1, min(len(all_lines), idx + 15)):
        line_j = all_lines[j]
        stripped = line_j.lstrip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Exit the except block if we hit a line at same or lower indentation
        # that starts a new block (except/def/class)
        line_j_indent = len(line_j) - len(line_j.lstrip())
        if line_j_indent <= except_indent and stripped.startswith(
            ("except", "def ", "class ", "finally", "else:")
        ):
            break

        # Check for proper logging
        if re.search(r"log(ger)?\.(exception|error|warning|critical)\s*\(", line_j):
            return False  # Has logging - not silent
        if re.search(r"log(ger)?\.(debug|info)\s*\(", line_j) and (
            "exc_info" in line_j or "exception" in line.lower()
        ):
            return False

        # Check for print/stderr output (CLI error reporting)
        if re.search(r"\bprint\s*\(.*\b(error|err|exception|fail)", line_j, re.IGNORECASE):
            return False
        if "sys.stderr" in line_j or "sys.exit" in line_j:
            return False

        # Check for structured return (not just bare return/pass)
        if re.search(r"return\s+", line_j):
            # Bare returns to None/False/0 are not "structured" UNLESS they're
            # clearly a deliberate fallback pattern
            if re.search(r"return\s+(None|False|0|\{\}|\[\])?\s*$", line_j):
                continue  # Silent swallow, could be an issue
            return False  # Has structured return - not silent

        # Check for fallback assignment — only suppress if there's ALSO logging in the except block
        if re.search(r'\w+\s*=\s*(None|False|0|\[\]|\{\}|""|\'\')\s*$', line_j):
            has_logging = any(
                re.search(r'(logger|logging|log\.|print\(|Debug\.|warnings\.warn|ErrorLogger)', all_lines[k])
                for k in range(idx, min(len(all_lines), idx + 15))
            )
            if has_logging:
                return False  # Fallback with logging — acceptable
            continue  # Fallback WITHOUT logging — still a silent swallow

        if re.search(r"json\.dumps\s*\(|dict\s*\(|\{.+:.+\}", line_j):
            return False

        # Check for error collection (dict assignment or list append with error info)
        if re.search(r'\[.+\]\s*=\s*\{.*"(error|status|message)', line_j, re.IGNORECASE):
            return False  # Error info stored in dict
        # Multi-line dict assignment: container["key"] = { on this line, content on next
        if re.search(r'\[.+\]\s*=\s*\{\s*$', line_j):
            for k in range(j + 1, min(len(all_lines), j + 5)):
                if re.search(r'"(error|status|message|failed)"', all_lines[k], re.IGNORECASE):
                    return False
        if re.search(r"\.(append|extend)\s*\(.*\b(error|exc|exception|err)\b", line_j, re.IGNORECASE):
            return False  # Error collected in list
        # Multi-line append: .append({ on this line, error info on next lines
        if re.search(r"\.(append|extend)\s*\(\s*\{?\s*$", line_j):
            for k in range(j + 1, min(len(all_lines), j + 5)):
                if re.search(r"\b(error|exc|exception|err|failed)\b", all_lines[k], re.IGNORECASE):
                    return False

        # Check for re-raise
        if re.search(r"\braise\b", line_j):
            return False  # Re-raising, not silent

        # Check for warnings module
        if re.search(r"warnings\.warn\s*\(", line_j):
            return False

    # If we get here, the except block appears to silently swallow
    return True


def _check_unused_import(
    line: str,
    all_lines: list[str],
    idx: int,
    context: Optional[dict] = None,
) -> bool:
    """Enhanced PY-STY-07 guard: checks multiple conditions before flagging.

    Only fires if import is:
    1. Not used in the file (checked by AST)
    2. Not in __all__
    3. Not a known runtime-glue module (bpy, bl_ui, etc.)
    4. Not a re-export (from x import y as y)

    When context is provided, uses cross-file information for better accuracy.
    """
    # This guard is primarily used with AST analysis, so most validation
    # happens in _ast_analyze_unused_imports. Here we do quick heuristics.
    stripped = line.strip()

    # Check if it's a known runtime-glue module (likely intentional)
    glue_modules = {"bpy", "bl_ui", "bl_math", "bl_utils", "mathutils", "bmesh"}
    for mod in glue_modules:
        if f"import {mod}" in stripped or f"from {mod} " in stripped:
            return False

    # Check for re-export pattern: from x import y as y
    if re.search(r"from\s+\w+\s+import\s+(\w+)\s+as\s+\1\b", stripped):
        return False  # Re-export, not unused

    # Default: let AST analysis handle it
    return True


def _check_shadow_builtin(
    line: str,
    all_lines: list[str],
    idx: int,
    context: Optional[dict] = None,
) -> bool:
    """Check if shadowing a built-in is actually problematic.

    Uses cross-file context when available to check if the shadowed
    built-in is actually used elsewhere in the codebase.
    """
    # Skip keyword arguments (line ends with , or ) — inside function call)
    if line.rstrip().endswith(",") or line.rstrip().endswith(")"):
        return False
    # Skip if previous line has open paren (multi-line function call)
    if idx > 0 and "(" in all_lines[idx - 1] and ")" not in all_lines[idx - 1]:
        return False

    # If context available, check if built-in is used elsewhere
    if context and "imports_used" in context:
        # Extract the shadowed name
        m = re.match(
            r"^\s*(list|dict|set|str|int|float|bool|tuple|type|id|input|filter|map|zip|range|len|sum|min|max|any|all|sorted|reversed|hash|next|iter|open|print|format|bytes|object|super)\s*=",
            line,
        )
        if m:
            shadowed = m.group(1)
            if shadowed in context.get("imports_used", set()):
                return False  # Used elsewhere - context knows it's intentional

    return True


def _check_concatenation_in_loop(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Check if string concatenation is inside a loop."""
    for j in range(max(0, idx - 5), idx):
        if re.search(r"^\s*(for|while)\b", all_lines[j]):
            return True
    return False


def _check_regex_in_loop(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Check if regex with a LITERAL pattern is used inside a loop body.

    Only flags when the regex call uses a string literal pattern (r"...", "...")
    that could be precompiled. Skips dynamic patterns (variables, f-strings)
    and calls that are part of the loop condition itself.
    """
    # Must have a string literal pattern argument to be precompilable
    if not re.search(r're\.\w+\s*\(\s*[bruf]*["\']', line):
        return False
    # Must be inside a loop body, not on the for/while line itself
    stripped = line.lstrip()
    if stripped.startswith(("for ", "while ")):
        return False
    # Check for containing loop within 10 lines above
    line_indent = len(line) - len(line.lstrip())
    for j in range(max(0, idx - 10), idx):
        candidate = all_lines[j]
        if re.search(r"^\s*(for|while)\b", candidate):
            loop_indent = len(candidate) - len(candidate.lstrip())
            if loop_indent < line_indent:
                return True
    return False


def _check_path_traversal(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    if re.search(
        r"Path\s*\([^)]*\)\.(name|suffix|stem|parent|parts|exists|is_file|is_dir)\b",
        line,
    ):
        return False
    if "__file__" in line or re.search(r"\bcwd\s*=", line):
        return False
    if not re.search(
        r"(\bopen\s*\(|read_text\s*\(|write_text\s*\(|read_bytes\s*\(|write_bytes\s*\(|unlink\s*\(|mkdir\s*\(|rename\s*\(|replace\s*\(|os\.path\.join\s*\()",
        line,
    ):
        return False
    if not re.search(
        r"\b(?:(?:user|request|input|param|query|upload|download|save|truth|history)[A-Za-z0-9_]*(?:path|file|filename|dir)?|file_path)\b",
        line,
        re.IGNORECASE,
    ):
        return False
    window = "\n".join(all_lines[max(0, idx - 3) : min(len(all_lines), idx + 4)])
    return not re.search(
        r"(resolve\(|normpath\(|safe_join|Path\s*\([^)]*\)\.resolve)",
        window,
    )


def _check_ssrf_request(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    if re.search(r'["\']https?://', line):
        return False
    if not re.search(r"\b(url|uri|endpoint|host)\b", line, re.IGNORECASE):
        return False
    window = "\n".join(all_lines[max(0, idx - 3) : min(len(all_lines), idx + 4)])
    return not re.search(
        r"(allowlist|whitelist|trusted_hosts|approved_hosts)",
        window,
        re.IGNORECASE,
    )


def _check_async_lock_await(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    if "await " not in line:
        return False
    await_indent = len(line) - len(line.lstrip())
    for j in range(idx - 1, max(-1, idx - 8), -1):
        candidate = all_lines[j]
        if re.search(r"^\s*(async\s+with|with)\s+.*\b(?:lock|Lock)\b.*:", candidate):
            lock_indent = len(candidate) - len(candidate.lstrip())
            return lock_indent < await_indent
    return False


def _check_unlocked_global_mutation(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    match = re.search(r"^\s*global\s+(\w+)", line)
    if not match:
        return False
    global_name = match.group(1)
    window = "\n".join(all_lines[idx : min(len(all_lines), idx + 8)])
    if re.search(r"(lock|Lock|RLock|threading\.)", window):
        return False
    return bool(
        re.search(
            rf"\b{re.escape(global_name)}(\s*\[[^\]]+\]\s*=|\.append\s*\(|\.extend\s*\(|\.update\s*\(|\.add\s*\()",
            window,
        )
    )


def _check_gather_without_error_collection(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    if "return_exceptions" in line:
        return False
    window = "\n".join(all_lines[max(0, idx - 3) : idx + 1])
    return "try:" not in window


def _check_popen_without_wait(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    assigned = re.search(r"(\w+)\s*=\s*subprocess\.Popen\s*\(", line)
    if not assigned:
        return True
    proc_name = assigned.group(1)
    window = "\n".join(all_lines[idx + 1 : min(len(all_lines), idx + 10)])
    return not re.search(rf"\b{re.escape(proc_name)}\.(communicate|wait)\s*\(", window)


def _check_optional_result_without_none_check(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    match = re.search(
        r"^\s*(\w+)\s*=\s*[\w\.]*(find|get|lookup|resolve|maybe|optional|try)\w*\s*\(",
        line,
        re.IGNORECASE,
    )
    if not match:
        return False
    var_name = match.group(1)
    for candidate in all_lines[idx + 1 : min(len(all_lines), idx + 6)]:
        if re.search(rf"\bif\s+{re.escape(var_name)}\s+is\s+None\b", candidate):
            return False
        if re.search(rf"\bassert\s+{re.escape(var_name)}\s+is\s+not\s+None\b", candidate):
            return False
        if re.search(rf"\b{re.escape(var_name)}(\.|\[)", candidate):
            return True
    return False


# =========================================================================
#  Known patterns for AST analysis
# =========================================================================

# Known lazy import modules that are OK (intentional lazy loading)
LAZY_OK_MODULES = frozenset(
    {
        "numpy",
        "np",
        "PIL",
        "google",
        "defusedxml",
        "cv2",
        "scipy",
        "torch",
        "sklearn",
        "pandas",
        "matplotlib",
        "fnmatch",
        "shutil",
        "tempfile",
        "subprocess",
        "os",
        "httpx",
        "json",
        "typing",
        "importlib",
        "pkgutil",
    }
)

# Local roots for lazy import detection
LOCAL_ROOTS = frozenset({"blender_addon", "veilbreakers_mcp"})

# Known runtime-glue modules (not truly unused)
RUNTIME_GLUE_MODULES = frozenset(
    {
        "bpy",
        "bl_ui",
        "bl_math",
        "bl_utils",
        "mathutils",
        "bmesh",
        "blender",
        "bpy_extras",
    }
)

# Built-in names that can be shadowed
BUILTIN_NAMES = frozenset(
    {
        "list",
        "dict",
        "set",
        "str",
        "int",
        "float",
        "bool",
        "tuple",
        "type",
        "id",
        "input",
        "filter",
        "map",
        "zip",
        "range",
        "len",
        "sum",
        "min",
        "max",
        "any",
        "all",
        "sorted",
        "reversed",
        "hash",
        "next",
        "iter",
        "open",
        "print",
        "format",
        "bytes",
        "object",
        "super",
    }
)


# =========================================================================
#  Rule definitions (30 rules) -- classified by layer
# =========================================================================


def _compile_anti(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


def create_rules() -> list[Any]:
    """Create and return all 35 Python rules with proper classification."""

    RULES = [
        # ==================================================================
        #  LAYER 1: HARD CORRECTNESS (Deterministic, no FP)
        #  These rules fire on syntactic patterns that are always bugs
        # ==================================================================
        # ---- SECURITY ----
        Rule(
            id="PY-SEC-01",
            severity=Severity.CRITICAL,
            category=Category.Security,
            description="eval() usage -- arbitrary code execution risk",
            fix="Replace with ast.literal_eval() or redesign.",
            pattern=re.compile(r"\beval\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"literal_eval"]),
            layer="hard_correctness",
            requires_context=False,
            auto_fix=_autofix_eval,
        ),
        Rule(
            id="PY-SEC-02",
            severity=Severity.CRITICAL,
            category=Category.Security,
            description="os.system() or subprocess with shell=True -- command injection",
            fix="Use subprocess.run() with list args and shell=False.",
            pattern=re.compile(
                r"(os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True)"
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-SEC-03",
            severity=Severity.CRITICAL,
            category=Category.Security,
            description="pickle.load on untrusted data -- arbitrary code execution",
            fix="Use json, msgpack, or safer format.",
            pattern=re.compile(r"pickle\.(load|loads)\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-SEC-04",
            severity=Severity.HIGH,
            category=Category.Security,
            description="f-string in SQL/shell command -- injection risk",
            fix="For SQL: cursor.execute('SELECT * FROM t WHERE id = %s', (user_id,)). For shell: subprocess.run(['cmd', arg], shell=False).",
            pattern=re.compile(r'(execute|run|system|popen)\s*\(\s*f["\']'),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-SEC-05",
            severity=Severity.HIGH,
            category=Category.Security,
            description="exec() usage -- arbitrary code execution",
            fix="Replace with getattr(module, name)() for dynamic dispatch, or a dict mapping names to callables.",
            pattern=re.compile(r"\bexec\s*\("),
            anti_patterns=_compile_anti(
                [
                    r"#\\s*(?:VB|REVIEW)-IGNORE",
                    r"^\s*#",
                    r"^\s*\w+\s*=\s*",
                    r"def\s+\w+\s*\([^)]*exec",
                    r"#\s*noqa",  # Author already triaged via ruff/flake8 suppression
                ]
            ),
            layer="hard_correctness",
            requires_context=False,
        ),
        # ---- CORRECTNESS ----
        Rule(
            id="PY-COR-01",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Mutable default argument -- shared across calls",
            fix="Change 'def f(items=[])' to 'def f(items=None):', then 'items = items if items is not None else []' in the body.",
            pattern=re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="hard_correctness",
            requires_context=False,
            auto_fix=_autofix_mutable_default,
        ),
        Rule(
            id="PY-COR-02",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Bare except: catches SystemExit, KeyboardInterrupt",
            fix="Replace 'except:' with 'except Exception:' at minimum, or 'except (ValueError, KeyError):' for specific types.",
            pattern=re.compile(r"^\s*except\s*:"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-04",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="open() without context manager -- file may not close",
            fix="Use 'with open(...) as f:'.",
            pattern=re.compile(r"(?<!\bwith\s)\bopen\s*\("),
            anti_patterns=_compile_anti(
                [
                    r"#\\s*(?:VB|REVIEW)-IGNORE",
                    r"^\s*#",
                    r"\bwith\b",
                    r"Image\.open",
                    r"BytesIO",
                    r"PIL",
                ]
            ),
            layer="hard_correctness",
            requires_context=False,
        ),
        # ---- PERFORMANCE ----
        Rule(
            id="PY-PERF-01",
            severity=Severity.LOW,
            category=Category.Performance,
            description="re.compile in loop -- should compile once outside",
            fix="Compile the regex once before the loop.",
            pattern=re.compile(
                r"^\s*(for|while)\b.*re\.(compile|match|search|findall|sub)\s*\("
            ),
            anti_patterns=_compile_anti(
                [r"#\\s*(?:VB|REVIEW)-IGNORE", r"re\.compile.*\n\s*(for|while)"]
            ),
            layer="hard_correctness",
            requires_context=False,
            confidence=90,
        ),
        # ==================================================================
        #  LAYER 2: SEMANTIC (Context-aware guards needed)
        #  These rules require semantic analysis to avoid false positives
        # ==================================================================
        # ---- CORRECTNESS ----
        Rule(
            id="PY-COR-03",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Comparing with None using == instead of 'is None'",
            fix="Use 'is None' or 'is not None'.",
            pattern=re.compile(r"[!=]=\s*None\b"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            auto_fix=_autofix_none_comparison,
        ),
        Rule(
            id="PY-COR-05",
            severity=Severity.LOW,
            category=Category.Bug,
            description="datetime.now() without timezone -- ambiguous",
            fix="Use datetime.now(tz=timezone.utc).",
            pattern=re.compile(r"datetime\.now\s*\(\s*\)"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
        ),
        # PY-COR-06: only flag if result is mutated, not just read
        Rule(
            id="PY-COR-06",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="dict.get() with mutable default -- mutated result is shared",
            fix="Use dict.get(key) with None check, then create mutable separately.",
            pattern=re.compile(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_mutable_get,
            layer="semantic",
            requires_context=False,
            confidence=88,
        ),
        Rule(
            id="PY-COR-07",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Class with __del__ -- unpredictable GC, prevents ref cycle collection",
            fix="Use context managers or weakref.finalize.",
            pattern=re.compile(r"def\s+__del__\s*\(\s*self"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=85,
        ),
        Rule(
            id="PY-COR-08",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Thread without daemon=True -- may prevent clean shutdown",
            fix="Set daemon=True or join before exit.",
            pattern=re.compile(r"Thread\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"daemon"]),
            layer="semantic",
            requires_context=False,
        ),
        # PY-COR-09: DELETED 2026-04-09 — 0% precision (7 findings, all FP).
        # Every hit was a loader/parser function where raising on corrupt input
        # is the correct behavior. Rule's premise ("wrap json.load in try/except")
        # contradicts the codebase's correct error-surfacing style.
        Rule(
            id="PY-COR-10",
            severity=Severity.LOW,
            category=Category.Bug,
            description="Float equality comparison -- use math.isclose",
            fix="Use math.isclose(a, b) or abs(a - b) < epsilon.",
            pattern=re.compile(r"(?<!\w)(==|!=)\s*(?!0\.0\b)\d+\.\d+"),
            anti_patterns=_compile_anti([
                r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#",
                r"\bnp\.", r"\.astype\s*\(", r"asarray",
                r"dtype\s*=",
            ]),
            layer="semantic",
            requires_context=False,
            reasoning="Exempt == 0.0/!= 0.0 (idiomatic zero-guard) and numpy array contexts (mask ops).",
            auto_fix=_autofix_float_equality,
        ),
        Rule(
            id="PY-COR-11",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Re-raising exception without chain -- loses traceback",
            fix="Use 'raise NewException (...) from original_exc' to preserve the traceback chain.",
            pattern=re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"\bfrom\s+\w+"]),
            guard=lambda line, a, i, ctx=None: _is_inside_except(line, a, i, ctx),
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=72,
        ),
        # PY-COR-12: REWRITTEN - now checks for silent swallow
        Rule(
            id="PY-COR-12",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Broad except that silently swallows exceptions without logging or return",
            fix="Add logger.exception() or return a meaningful error response.",
            pattern=re.compile(r"except\s+Exception\s*(?:as|\s*:)"),
            anti_patterns=_compile_anti(
                [
                    r"#\\s*(?:VB|REVIEW)-IGNORE",
                    r"# broad catch intentional",
                    r"logger\.exception",
                    r"mcp\.tool",
                    r"return\s+json\.dumps",
                ]
            ),
            anti_radius=10,
            guard=_check_broad_except_silent,
            layer="semantic",
            requires_context=False,
            confidence=75,
        ),
        # PY-COR-13: Import inside function - needs context
        Rule(
            id="PY-COR-13",
            severity=Severity.LOW,
            category=Category.Bug,
            description="Import inside function body -- may indicate circular import workaround",
            fix="Restructure modules to avoid circular dependencies.",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),  # Handled by AST pass
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=45,
            reasoning="Requires package dependency context. Local lazy imports can be valid for Blender startup, optional wiring, or cycle breaking.",
        ),
        # PY-COR-14: Shadow built-ins - add cross-file check
        Rule(
            id="PY-COR-14",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Variable shadows built-in name (list, dict, set, type, id, etc.) — may break code that needs the built-in later",
            fix="Rename: items instead of list, mapping instead of dict, obj_type instead of type, obj_id instead of id.",
            pattern=re.compile(
                r"^\s*(list|dict|set|str|int|float|bool|tuple|type|id|input|filter|map|zip|range|len|sum|min|max|any|all|sorted|reversed|hash|next|iter|open|print|format|bytes|object|super)\s*=\s*"
            ),
            anti_patterns=_compile_anti(
                [r"#\\s*(?:VB|REVIEW)-IGNORE", r"typing", r"import"]
            ),
            guard=_check_shadow_builtin,
            layer="semantic",
            requires_context=True,  # Can use cross-file context
            finding_type=FindingType.STRENGTHENING,
            confidence=72,
        ),
        # PY-COR-15: Late binding closure in loop
        Rule(
            id="PY-COR-15",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Lambda in loop captures loop variable by reference -- late binding bug",
            fix="Capture with default arg: lambda x, i=i: ... or use functools.partial.",
            pattern=re.compile(r"for\s+(\w+)\s+in\b"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_late_binding,
            layer="semantic",
            requires_context=False,
            confidence=92,
        ),
        # PY-COR-16: Discarded assignment -- `_name = func()` where name is never read
        # Catches terrain_caves.py:821 `_delta = carve_cave_volume(...)` class of bug:
        # underscore-prefixed var assigned from a function call that returns data the
        # caller is supposed to apply; the discard silently drops the delta.
        Rule(
            id="PY-COR-16",
            severity=Severity.CRITICAL,
            category=Category.Bug,
            description="Discarded return value: underscore-prefixed variable assigned from function call but never read",
            fix="If the return value is needed (delta, mask, array), remove the underscore prefix and apply it. If truly unused, use bare `_` or call the function as a statement.",
            pattern=re.compile(
                r"^\s*_[a-zA-Z]\w*\s*=\s*\w+[\w.]*\s*\("
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_discarded_assignment,
            layer="semantic",
            requires_context=False,
            confidence=88,
            reasoning="Terrain audit P0: pass_caves discarded carve_cave_volume delta, zero geometry output.",
        ),
        # PY-COR-17: Frozen dataclass with mutable default field
        # Catches terrain_semantics.py:669,743 TerrainIntentState/HeroFeatureSpec crash
        Rule(
            id="PY-COR-17",
            severity=Severity.CRITICAL,
            category=Category.Bug,
            description="Frozen dataclass with mutable collection field (Dict/List/Set) -- hash() raises TypeError",
            fix="Use frozenset/tuple/Mapping, or remove frozen=True, or use default_factory=tuple with a conversion in __post_init__.",
            pattern=re.compile(
                r":\s*(Dict|List|Set|dict|list|set)\b[^=]*=\s*field\s*\("
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_frozen_mutable_field,
            layer="semantic",
            requires_context=False,
            confidence=90,
            reasoning="Terrain audit P0: frozen=True + Dict field crashes hash() at runtime the moment the instance enters a set.",
        ),
        # PY-COR-18: Self-rollback in validator
        # Catches terrain_validation.py validate_* methods that call rollback on
        # channels the pipeline itself produces, causing auto-rollback on every run.
        Rule(
            id="PY-COR-18",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Validator method calls self.rollback()/state.rollback() on failure path -- may rollback producers' own output",
            fix="Validators should report errors and return False/raise. Rollback is the orchestrator's decision, not the validator's.",
            pattern=re.compile(
                r"^\s*(self|state|ctx)\.rollback\s*\("
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_validator_self_rollback,
            layer="semantic",
            requires_context=False,
            confidence=82,
            reasoning="Terrain audit P0: validate_unity_export_ready auto-rolled-back every real pipeline run.",
        ),
        # PY-COR-19: Fallback branch returns before primary check
        # Catches terrain_frustum is_in_frustum style bug where a fallback-ok path
        # returns before the primary-ok path is evaluated.
        Rule(
            id="PY-COR-19",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Fallback branch returns True/ok before primary check runs -- reverses intent",
            fix="Reorder: primary check first, fallback only when primary is unavailable or inconclusive.",
            pattern=re.compile(
                r"^\s*if\s+[\w.()]*fallback[\w]*\s*:\s*(#.*)?$"
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            guard=_check_fallback_before_primary,
            layer="semantic",
            requires_context=False,
            confidence=72,
            reasoning="Terrain audit P0: is_in_frustum basis-fallback returned before forward-sign check.",
        ),
        # ---- PERFORMANCE ----
        Rule(
            id="PY-PERF-02",
            severity=Severity.LOW,
            category=Category.Performance,
            description="re.match/search/findall without compile for repeated pattern",
            fix="Compile pattern once with re.compile() and reuse.",
            pattern=re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"re\.compile"]),
            guard=_check_regex_in_loop,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-PERF-03",
            severity=Severity.LOW,
            category=Category.Performance,
            description="Large file .read() without chunking -- may exhaust memory",
            fix="Use chunked reading: for line in file, or file.read(chunk_size).",
            pattern=re.compile(r"\.read\s*\(\s*\)"),
            anti_patterns=_compile_anti(
                [
                    r"#\\s*(?:VB|REVIEW)-IGNORE",
                    r"^\s*#",
                    r'"rb"',
                    r"BytesIO",
                    r"img_bytes",
                    r"image_data",
                    r"base64",
                    r'encoding="utf-8"',
                    r"\.read_text\s*\(",
                ]
            ),
            layer="semantic",
            requires_context=False,
            confidence=55,
            reasoning=".read() is correct for small files. Pattern cannot determine file size.",
        ),
        # ==================================================================
        #  LAYER 3: HEURISTIC (Strict/audit mode only)
        #  Advisory rules that are often intentional
        # ==================================================================
        # ---- SECURITY ----
        Rule(
            id="PY-SEC-06",
            severity=Severity.MEDIUM,
            category=Category.Security,
            description="Hardcoded file path -- not portable",
            fix="Use pathlib.Path or os.path.join with configurable base.",
            pattern=re.compile(r"""['"](?:/[a-z]+/|[A-Z]:\\\\)[^'"]{3,}['"]"""),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
        ),
        Rule(
            id="PY-SEC-07",
            severity=Severity.HIGH,
            category=Category.Security,
            description="assert for input validation -- stripped with -O",
            fix="Replace 'assert x > 0' with 'if x <= 0: raise ValueError(\"x must be positive\")'.",
            pattern=re.compile(r"^\s*assert\s+(?!.*#\s*nosec)"),
            anti_patterns=_compile_anti(
                [r"#\\s*(?:VB|REVIEW)-IGNORE", r"#\s*nosec", r"test_|_test\.py"]
            ),
            layer="heuristic",
            requires_context=False,
            confidence=65,
            reasoning="Cannot distinguish input validation from internal invariant checks.",
        ),
        # ---- STYLE ----
        Rule(
            id="PY-STY-01",
            severity=Severity.LOW,
            category=Category.Quality,
            description="os.path usage — consider pathlib.Path for cleaner path handling",
            fix="Replace os.path.join(a, b) with Path(a) / b. pathlib is more readable and handles cross-platform paths.",
            pattern=re.compile(
                r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\s*\("
            ),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"^\s*#"]),
            layer="heuristic",
            requires_context=False,
            confidence=72,
            finding_type=FindingType.STRENGTHENING,
            auto_fix=_autofix_pathlib_join,
        ),
        Rule(
            id="PY-STY-02",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Deeply nested function (3+ indent levels) — hard to test and maintain",
            fix="Extract inner function to module level or class method for better testability.",
            pattern=re.compile(r"^\s{12,}def\s+\w+\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            layer="heuristic",
            requires_context=False,
            confidence=85,
            finding_type=FindingType.STRENGTHENING,
        ),
        Rule(
            id="PY-STY-03",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Star import pollutes namespace — imported names are unknown to readers and tools",
            fix="Replace with explicit imports: from X import ClassA, func_b, CONST_C.",
            pattern=re.compile(r"from\s+\S+\s+import\s+\*"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            layer="heuristic",
            requires_context=False,
            confidence=92,
            finding_type=FindingType.STRENGTHENING,
        ),
        Rule(
            id="PY-STY-04",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Global variable mutation — makes function behavior depend on hidden state",
            fix="Pass the value as a function parameter, or encapsulate in a class with clear ownership.",
            pattern=re.compile(r"^\s+global\s+\w+"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            layer="heuristic",
            requires_context=False,
            confidence=78,
            finding_type=FindingType.STRENGTHENING,
        ),
        # PY-STY-07: Unused import - handled by AST with enhanced guards
        Rule(
            id="PY-STY-07",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Unused import -- not referenced anywhere in this module",
            fix="Remove 'import name' or 'from ... import name' if truly unused. If re-exported, add to __all__.",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),  # Handled by AST pass
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=82,
        ),
        # PY-STY-05/06/08/09: AST-only rules
        Rule(
            id="PY-STY-05",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Missing __main__ guard -- code runs on import",
            fix="Wrap in: if __name__ == '__main__':",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=90,
        ),
        Rule(
            id="PY-STY-06",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Missing __all__ in public module",
            fix="Add __all__ = ['ClassName', 'public_func', 'CONSTANT'] at module top listing all intended public names.",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=80,
        ),
        Rule(
            id="PY-STY-08",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Missing type annotation on public function",
            fix="Add return type annotation: def func(...) -> ReturnType:",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=85,
        ),
        Rule(
            id="PY-STY-09",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Function exceeds length threshold",
            fix="Break long functions into smaller, well-named helpers.",
            pattern=re.compile(r"SENTINEL_AST_ONLY"),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
            confidence=90,
        ),
        # ---- GENERAL WEB / CONCURRENCY / RESOURCE RULES ----
        Rule(
            id="PY-SEC-08",
            severity=Severity.HIGH,
            category=Category.Security,
            description="User-controlled path reaches filesystem operation without normalization",
            fix="Resolve against a trusted base directory and reject paths that escape it.",
            pattern=re.compile(
                r"(\bopen\s*\(|Path\s*\([^)]*\)\.(read_text|write_text|read_bytes|write_bytes|open|unlink|mkdir|rename|replace)\s*\(|os\.path\.join\s*\()"
            ),
            anti_patterns=_compile_anti(
                [r"#\\s*(?:VB|REVIEW)-IGNORE", r"resolve\(", r"normpath\(", r"__file__"]
            ),
            guard=_check_path_traversal,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-SEC-09",
            severity=Severity.HIGH,
            category=Category.Security,
            description="requests call uses a user-controlled URL/host -- possible SSRF",
            fix="Allowlist destinations or resolve against a trusted service catalog before issuing the request.",
            pattern=re.compile(r"requests\.(get|post|put|delete|request)\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r'["\']https?://']),
            guard=_check_ssrf_request,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-SEC-10",
            severity=Severity.HIGH,
            category=Category.Security,
            description="render_template_string with dynamic input -- server-side template injection risk",
            fix="Render a static template file and pass user data as context variables instead.",
            pattern=re.compile(r"render_template_string\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r'["\']\s*\)']),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-20",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="await while holding a threading lock -- can deadlock or starve peers",
            fix="Release the lock before awaiting, or switch to an asyncio-compatible lock.",
            pattern=re.compile(r"\bawait\b"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            guard=_check_async_lock_await,
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-21",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Function mutates shared global state without an obvious lock",
            fix="Protect the shared mutable global with a lock or move the state behind a synchronized owner object.",
            pattern=re.compile(r"^\s*global\s+\w+"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            guard=_check_unlocked_global_mutation,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-22",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="asyncio.gather without return_exceptions or local error collection",
            fix="Pass return_exceptions=True or wrap the gather call in explicit exception handling.",
            pattern=re.compile(r"asyncio\.gather\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"return_exceptions\s*="]),
            guard=_check_gather_without_error_collection,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-PERF-04",
            severity=Severity.LOW,
            category=Category.Performance,
            description="logger call uses f-string -- string is formatted even when the log level is disabled",
            fix="Use lazy logger formatting: logger.error('value=%s', value).",
            pattern=re.compile(r"logger\.(debug|info|warning|error|exception|critical)\s*\(\s*f[\"']"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            layer="heuristic",
            requires_context=False,
            finding_type=FindingType.OPTIMIZATION,
        ),
        Rule(
            id="PY-RES-08",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="subprocess.Popen result is never waited or communicated -- child process may leak",
            fix="Call communicate()/wait() or use subprocess.run() when streaming is not required.",
            pattern=re.compile(r"subprocess\.Popen\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"subprocess\.run\s*\("]),
            guard=_check_popen_without_wait,
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-RES-09",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="requests call without timeout -- network hang can block the worker indefinitely",
            fix="Pass an explicit timeout=(connect, read) or timeout=<seconds>.",
            pattern=re.compile(r"requests\.(get|post|put|delete|request)\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"timeout\s*="]),
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-23",
            severity=Severity.LOW,
            category=Category.Bug,
            description="Result from an Optional-style helper is dereferenced without a nearby None check",
            fix="Check for None explicitly before dereferencing the result.",
            pattern=re.compile(r"^\s*\w+\s*=\s*[\w\.]*(find|get|lookup|resolve|maybe|optional|try)\w*\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE"]),
            guard=_check_optional_result_without_none_check,
            layer="heuristic",
            requires_context=False,
        ),
        # ==================================================================
        #  BLENDER-SPECIFIC RULES (Phase 6)
        # ==================================================================
        Rule(
            id="BLE-01",
            severity=Severity.LOW,
            category=Category.Quality,
            description="bpy.ops without undo push -- Blender state corruption on error",
            fix="Wrap in try/finally with bpy.ops.ed.undo_push(message='action_name')",
            pattern=re.compile(r"bpy\.ops\.\w+\.\w+\s*\("),
            anti_patterns=_compile_anti([
                r"#\\s*(?:VB|REVIEW)-IGNORE",
                r"undo_push",
                r"bpy\.ops\.ed\.undo",
                r"def\s+handle_",  # Addon handler functions have MCP-level undo management
                r"handlers/",  # Addon handler modules
            ]),
            layer="heuristic",  # Only in strict mode — too noisy for production
            requires_context=False,
        ),
        Rule(
            id="BLE-02",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="bpy.data.objects.new/meshes.new without cleanup on error path",
            fix="Use try/except/finally to ensure cleanup: bpy.data.objects.remove(obj) on error.",
            pattern=re.compile(r"bpy\.data\.(objects|meshes|materials)\.new\s*\("),
            anti_patterns=_compile_anti([
                r"#\\s*(?:VB|REVIEW)-IGNORE", r"\.remove\s*\(", r"try:", r"finally:",
                r"def\s+handle_",  # MCP handler dispatch-level cleanup
                r"handlers/",  # Addon handler modules
            ]),
            anti_radius=50,  # Raised from 12: function-level cleanup is normal
            guard=_has_blender_cleanup_in_scope,
            layer="heuristic",  # Demoted 2026-04-09: 85% FP at semantic, ~15% precision
            requires_context=False,
        ),
        Rule(
            id="BLE-03",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Creating UV layer without checking if exists -- duplicate layers",
            fix="Check 'if not mesh.uv_layers:' before creating new UV layer.",
            pattern=re.compile(r"\.uv_layers\.new\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"if\s+not\s+.*uv_layers"]),
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="BLE-04",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Accessing material.node_tree.nodes without use_nodes=True",
            fix="Set material.use_nodes = True before accessing node_tree.nodes.",
            pattern=re.compile(r"\.node_tree\.nodes"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"\.use_nodes"]),
            anti_radius=30,  # Check wider radius for use_nodes setup/check
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-ASYNC-01",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="asyncio.create_task without await or tracking -- 'Task was never retrieved' warning",
            fix="Store task: 'task = asyncio.create_task(coro())' or await immediately.",
            pattern=re.compile(r"asyncio\.create_task\s*\("),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"=\s*asyncio\.create_task", r"await\s+asyncio\.create_task"]),
            layer="hard_correctness",
            requires_context=False,
        ),

        # ==================================================================
        #  MISSING DETECTION PATTERNS
        #  Patterns identified by gap analysis that were not previously caught
        # ==================================================================

        # Database connection lifecycle - opened without context manager support
        Rule(
            id="PY-RES-01",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Database connection opened in __init__ without context manager support -- connection leak risk",
            fix="Implement __enter__/__exit__ or __del__ for cleanup, or use contextlib",
            pattern=re.compile(r"self\.\w+\s*=\s*sqlite3\.connect"),
            layer="hard_correctness",
            requires_context=False,
        ),

        # Temp directory without cleanup
        Rule(
            id="PY-RES-02",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="tempfile.mkdtemp() without cleanup or context manager -- temp directory leak",
            fix="Use tempfile.TemporaryDirectory() as context manager or clean up in finally block",
            pattern=re.compile(r"tempfile\.mkdtemp\s*\("),
            anti_patterns=_compile_anti([r"shutil\.rmtree", r"cleanup", r"TemporaryDirectory"]),
            anti_radius=40,
            layer="hard_correctness",
            requires_context=False,
        ),

        # PY-RES-03: DELETED 2026-04-09 — 100% FP rate (48 findings, all correct
        # defensive max() zero-guards flagged as bugs). Rule contradicts the
        # defensive-coding idiom it claims to promote.

        # Mutable default with truthy empty check
        Rule(
            id="PY-RES-04",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Mutable default with 'or []' fallback -- empty list is replaced with defaults unexpectedly",
            fix="Use 'if param is None:' instead of 'param or []' to distinguish None from empty",
            pattern=re.compile(r"=\s*None\s*\)[^)]{0,200}?\w+\s+or\s*\["),
            layer="semantic",
            requires_context=False,
        ),

        # Empty exception handler
        Rule(
            id="PY-RES-05",
            severity=Severity.MEDIUM,
            category=Category.Quality,
            description="Empty exception handler silently swallows errors -- should log or rethrow",
            fix="Add logging: 'except Exception as exc: logger.warning(\"...\", exc)'",
            pattern=re.compile(r"except\s+Exception\s*:\s*pass"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"intentional", r"graceful"]),
            anti_radius=5,
            layer="semantic",
            requires_context=False,
        ),

        # Global variable mutation
        Rule(
            id="PY-RES-06",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Global variable mutation -- consider dependency injection or singleton pattern",
            fix="Use class-level state, dependency injection, or documented singleton pattern",
            pattern=re.compile(r"^\s*global\s+\w+"),
            anti_patterns=_compile_anti([r"#\\s*(?:VB|REVIEW)-IGNORE", r"singleton", r"cache"]),
            anti_radius=10,
            layer="heuristic",
            requires_context=False,
        ),

        # Resource opened without context manager
        Rule(
            id="PY-RES-07",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Resource opened without context manager -- potential resource leak",
            fix="Use 'with open(...) as f:' pattern to ensure cleanup",
            pattern=re.compile(r"(?:socket|file|connection)\s*\.\s*open\s*\("),
            anti_patterns=_compile_anti([r"with\s+", r"finally\s*:"]),
            anti_radius=30,
            layer="hard_correctness",
            requires_context=False,
        ),
    ]

    return RULES


# =========================================================================
#  AST-aware analysis functions
# =========================================================================


def _ast_analyze_unused_imports(
    filepath: str,
    source: str,
    is_test_file: bool = False,
    is_init_module: bool = False,
) -> list[dict]:
    """AST-based analysis for unused imports with enhanced guards.

    This is the PY-STY-07 implementation that checks:
    1. If import is actually used in the code
    2. If import is in __all__ (re-exported)
    3. If import is a known runtime-glue module
    4. If import is a re-export (from x import y as y)
    """
    issues: list[dict[str, object]] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Collect all names used in the module
    all_names_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            all_names_used.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                all_names_used.add(node.value.id)

    # Collect imports
    imported_names: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            if node.names[0].name == "*":
                continue
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names[name] = node.lineno

    # Check for __all__ definition
    all_names_list: set[str] = set()
    for n in ast.iter_child_nodes(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    if isinstance(n.value, (ast.List, ast.Tuple)):
                        for elt in n.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                all_names_list.add(elt.value)

    # Analyze each import
    for name, lineno in imported_names.items():
        # Skip private imports
        if name.startswith("_"):
            continue

        # Check if in __all__ (re-exported)
        if name in all_names_list:
            continue

        # Check if it's a known runtime-glue module
        if name in RUNTIME_GLUE_MODULES:
            continue

        # Check if it's actually used
        if name not in all_names_used:
            issues.append(
                {
                    "rule_id": "PY-STY-07",
                    "line": lineno,
                    "name": name,
                    "filepath": filepath,
                }
            )

    return issues


def _ast_analyze_lazy_imports(
    filepath: str,
    source: str,
    is_test_file: bool = False,
) -> list[dict]:
    """AST-based analysis for lazy imports (PY-COR-13)."""
    issues: list[dict[str, object]] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Collect imports inside try blocks (optional dependency pattern)
        try_import_lines: set[int] = set()
        for child in ast.walk(func_node):
            if isinstance(child, ast.Try):
                for body_stmt in child.body:
                    if isinstance(body_stmt, (ast.Import, ast.ImportFrom)):
                        try_import_lines.add(body_stmt.lineno)

        for child in ast.iter_child_nodes(func_node):
            if not isinstance(child, (ast.Import, ast.ImportFrom)):
                continue
            if child.lineno in try_import_lines:
                continue  # Optional dependency pattern

            mod_name = ""
            is_local_import = False
            if isinstance(child, ast.Import):
                mod_name = child.names[0].name.split(".")[0]
                is_local_import = mod_name in LOCAL_ROOTS
            elif isinstance(child, ast.ImportFrom):
                if child.level and child.level > 0:
                    mod_name = child.module or child.names[0].name
                    is_local_import = True
                elif child.module:
                    mod_name = child.module.split(".")[0]
                    is_local_import = mod_name in LOCAL_ROOTS

            if mod_name in LAZY_OK_MODULES or not is_local_import:
                continue

            issues.append(
                {
                    "rule_id": "PY-COR-13",
                    "line": child.lineno,
                    "name": mod_name,
                    "filepath": filepath,
                }
            )

    return issues


def _ast_analyze_type_annotations(
    filepath: str,
    source: str,
    is_test_file: bool = False,
    is_init_module: bool = False,
) -> list[dict]:
    """AST-based analysis for missing type annotations (PY-STY-08)."""
    issues: list[dict[str, object]] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Check for __all__
    has_all = False
    all_names_list: set[str] = set()
    for n in ast.iter_child_nodes(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    has_all = True
                    if isinstance(n.value, (ast.List, ast.Tuple)):
                        for elt in n.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                all_names_list.add(elt.value)

    if is_test_file or is_init_module:
        return issues

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        # Only flag public functions (in __all__ or has docstring)
        if has_all and node.name not in all_names_list:
            continue
        if node.returns is None:
            issues.append(
                {
                    "rule_id": "PY-STY-08",
                    "line": node.lineno,
                    "name": node.name,
                    "filepath": filepath,
                }
            )

    return issues


def _ast_analyze_main_guard(
    filepath: str,
    source: str,
    is_test_file: bool = False,
    is_init_module: bool = False,
) -> list[dict]:
    """AST-based analysis for missing __main__ guard (PY-STY-05)."""
    issues: list[dict[str, object]] = []
    module_name = Path(filepath).name
    if module_name.startswith("_"):
        return issues
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    has_main_guard = False
    has_top_level_code = False

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
            ):
                has_main_guard = True
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and isinstance(
                call.func.value, ast.Name
            ):
                if call.func.value.id in {"RULES", "__all__", "PYTHON_GUARD_FUNCTIONS"}:
                    continue
            has_top_level_code = True

    if has_top_level_code and not has_main_guard:
        issues.append(
            {
                "rule_id": "PY-STY-05",
                "line": 1,
                "filepath": filepath,
            }
        )

    return issues


def _ast_analyze_all_export(
    filepath: str,
    source: str,
    is_test_file: bool = False,
    is_init_module: bool = False,
) -> list[dict]:
    """AST-based analysis for missing __all__ (PY-STY-06)."""
    issues: list[dict[str, object]] = []
    module_name = Path(filepath).name
    if module_name.startswith("_"):
        return issues
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Check if __all__ exists
    has_all = any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
        for n in ast.iter_child_nodes(tree)
    )

    if has_all:
        return issues

    # Count public names
    public_names = [
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    ]

    if not is_test_file and not is_init_module and len(public_names) >= 3:
        issues.append(
            {
                "rule_id": "PY-STY-06",
                "line": 1,
                "count": len(public_names),
                "filepath": filepath,
            }
        )

    return issues


def _ast_analyze_function_length(
    filepath: str,
    source: str,
    is_template: bool = False,
    is_mcp_handler: bool = False,
    threshold: Optional[int] = None,
) -> list[dict]:
    """AST-based analysis for long functions (PY-STY-09)."""
    issues: list[dict[str, object]] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Skip templates entirely
    if is_template:
        return issues

    # Determine threshold
    if threshold is None:
        if is_mcp_handler:
            threshold = 200
        else:
            threshold = 60

    module_name = Path(filepath).name
    if module_name.startswith("_"):
        threshold = max(threshold, 120)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, "end_lineno") and node.end_lineno:
                length = node.end_lineno - node.lineno
                if length > threshold:
                    issues.append(
                        {
                            "rule_id": "PY-STY-09",
                            "line": node.lineno,
                            "name": node.name,
                            "length": length,
                            "threshold": threshold,
                            "filepath": filepath,
                        }
                    )

    return issues


# =========================================================================
#  Guard function dictionary for external access
# =========================================================================

PYTHON_GUARD_FUNCTIONS: dict[str, Callable] = {
    "_suppressed_by_anti": _suppressed_by_anti,
    "_is_comment": _is_comment,
    "_in_string_literal": _in_string_literal,
    "_active_code": _active_code,
    "_match_is_in_string": _match_is_in_string,
    "_is_inside_except": _is_inside_except,
    "_check_mutable_get": _check_mutable_get,
    "_check_late_binding": _check_late_binding,
    "_check_broad_except_silent": _check_broad_except_silent,
    "_check_unused_import": _check_unused_import,
    "_check_shadow_builtin": _check_shadow_builtin,
    "_check_concatenation_in_loop": _check_concatenation_in_loop,
    "_check_regex_in_loop": _check_regex_in_loop,
    "_check_path_traversal": _check_path_traversal,
    "_check_ssrf_request": _check_ssrf_request,
    "_check_async_lock_await": _check_async_lock_await,
    "_check_unlocked_global_mutation": _check_unlocked_global_mutation,
    "_check_gather_without_error_collection": _check_gather_without_error_collection,
    "_check_popen_without_wait": _check_popen_without_wait,
    "_check_optional_result_without_none_check": _check_optional_result_without_none_check,
}


# =========================================================================
#  Module exports
# =========================================================================

__all__ = [
    "RULES",
    "PYTHON_GUARD_FUNCTIONS",
    "create_rules",
    "LAZY_OK_MODULES",
    "LOCAL_ROOTS",
    "RUNTIME_GLUE_MODULES",
    "BUILTIN_NAMES",
    # AST analysis functions
    "_ast_analyze_unused_imports",
    "_ast_analyze_lazy_imports",
    "_ast_analyze_type_annotations",
    "_ast_analyze_main_guard",
    "_ast_analyze_all_export",
    "_ast_analyze_function_length",
]


# Create the rules list on module import
RULES: list[Any] = create_rules()

