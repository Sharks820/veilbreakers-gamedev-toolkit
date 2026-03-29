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
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Data classes — defined locally to avoid circular imports.
# The same definitions exist in vb_code_reviewer.py; they must stay in sync.
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class Category(IntEnum):
    Security = 0
    Bug = 1
    Performance = 2
    Quality = 3
    Unity = 4


class FindingType(IntEnum):
    ERROR = 0
    BUG = 1
    OPTIMIZATION = 2
    STRENGTHENING = 3


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


def _active_code(
    line: str, _all: list[str], _idx: int, _context: Optional[dict] = None
) -> bool:
    """Check if line is active code (not comment or string)."""
    return not _is_comment(line) and not _in_string_literal(line)


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


def _check_broad_except_silent(
    line: str,
    all_lines: list[str],
    idx: int,
    _context: Optional[dict] = None,
) -> bool:
    """Improved PY-COR-12 guard: checks for logging, structured return, or deliberate handling.

    Only fires when broad except silently swallows the exception without
    proper logging, error propagation, or deliberate fallback handling.
    """
    except_indent = len(line) - len(line.lstrip())
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
        candidate_stripped = candidate.lstrip()
        if re.search(r"^\s*(for|while)\b", candidate):
            loop_indent = len(candidate) - len(candidate.lstrip())
            if loop_indent < line_indent:
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"literal_eval"]),
            layer="hard_correctness",
            requires_context=False,
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
                    r"#\s*VB-IGNORE",
                    r"^\s*#",
                    r"^\s*\w+\s*=\s*",
                    r"def\s+\w+\s*\([^)]*exec",
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer="hard_correctness",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-02",
            severity=Severity.HIGH,
            category=Category.Bug,
            description="Bare except: catches SystemExit, KeyboardInterrupt",
            fix="Replace 'except:' with 'except Exception:' at minimum, or 'except (ValueError, KeyError):' for specific types.",
            pattern=re.compile(r"^\s*except\s*:"),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE"]),
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
                    r"#\s*VB-IGNORE",
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
                [r"#\s*VB-IGNORE", r"re\.compile.*\n\s*(for|while)"]
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer="semantic",
            requires_context=False,
            finding_type=FindingType.STRENGTHENING,
        ),
        Rule(
            id="PY-COR-05",
            severity=Severity.LOW,
            category=Category.Bug,
            description="datetime.now() without timezone -- ambiguous",
            fix="Use datetime.now(tz=timezone.utc).",
            pattern=re.compile(r"datetime\.now\s*\(\s*\)"),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"daemon"]),
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-09",
            severity=Severity.LOW,
            category=Category.Bug,
            description="json.loads/load without error handling — crashes on malformed input",
            fix="Wrap in try/except json.JSONDecodeError to handle corrupt JSON gracefully.",
            pattern=re.compile(r"json\.loads?\s*\("),
            anti_patterns=_compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"except.*JSON",
                    r"\btry\s*:",
                    r"\bexcept\b",
                ]
            ),
            anti_radius=20,
            layer="semantic",
            requires_context=False,
            confidence=68,
        ),
        Rule(
            id="PY-COR-10",
            severity=Severity.LOW,
            category=Category.Bug,
            description="Float equality comparison -- use math.isclose",
            fix="Use math.isclose(a, b) or abs(a - b) < epsilon.",
            pattern=re.compile(r"(?<!\w)(==|!=)\s*\d+\.\d+"),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer="semantic",
            requires_context=False,
        ),
        Rule(
            id="PY-COR-11",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Re-raising exception without chain -- loses traceback",
            fix="Use 'raise NewException (...) from original_exc' to preserve the traceback chain.",
            pattern=re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"\bfrom\s+\w+"]),
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
                    r"#\s*VB-IGNORE",
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
                [r"#\s*VB-IGNORE", r"typing", r"import"]
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            guard=_check_late_binding,
            layer="semantic",
            requires_context=False,
            confidence=92,
        ),
        # ---- PERFORMANCE ----
        Rule(
            id="PY-PERF-02",
            severity=Severity.LOW,
            category=Category.Performance,
            description="re.match/search/findall without compile for repeated pattern",
            fix="Compile pattern once with re.compile() and reuse.",
            pattern=re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"re\.compile"]),
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
                    r"#\s*VB-IGNORE",
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
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
                [r"#\s*VB-IGNORE", r"#\s*nosec", r"test_|_test\.py"]
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer="heuristic",
            requires_context=False,
            confidence=72,
            finding_type=FindingType.STRENGTHENING,
        ),
        Rule(
            id="PY-STY-02",
            severity=Severity.LOW,
            category=Category.Quality,
            description="Deeply nested function (3+ indent levels) — hard to test and maintain",
            fix="Extract inner function to module level or class method for better testability.",
            pattern=re.compile(r"^\s{12,}def\s+\w+\s*\("),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE"]),
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
                r"#\s*VB-IGNORE",
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"\.remove\s*\(", r"try:", r"finally:"]),
            layer="semantic",  # Real resource leak if handler crashes mid-execution
            requires_context=False,
        ),
        Rule(
            id="BLE-03",
            severity=Severity.MEDIUM,
            category=Category.Bug,
            description="Creating UV layer without checking if exists -- duplicate layers",
            fix="Check 'if not mesh.uv_layers:' before creating new UV layer.",
            pattern=re.compile(r"\.uv_layers\.new\s*\("),
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"if\s+not\s+.*uv_layers"]),
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"use_nodes\s*=\s*True"]),
            anti_radius=30,  # Check wider radius for use_nodes setup
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
            anti_patterns=_compile_anti([r"#\s*VB-IGNORE", r"=\s*asyncio\.create_task", r"await\s+asyncio\.create_task"]),
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
    issues = []
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
    issues = []
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
    issues = []
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
    issues = []
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
    issues = []
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
    issues = []
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
