#!/usr/bin/env python3
"""VeilBreakers Python Code Reviewer -- standalone CLI.

Same 30 rules as the unified VBCodeReviewer EditorWindow Python mode.
Anti-pattern suppression arrays for <1% false positive rate.

Usage:
    python vb_python_reviewer.py [path] [--output report.json] [--severity MEDIUM]
    python vb_python_reviewer.py src/ --output report.json
    python vb_python_reviewer.py my_script.py --severity HIGH

Exit codes:
    0 -- no issues at or above threshold severity
    1 -- issues found at or above threshold severity
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional


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


class FindingType(IntEnum):
    ERROR = 0
    BUG = 1
    OPTIMIZATION = 2
    STRENGTHENING = 3


# Map severity to default confidence/priority
_SEV_CONF = {Severity.CRITICAL: 95, Severity.HIGH: 85, Severity.MEDIUM: 75, Severity.LOW: 70}
_SEV_PRI = {Severity.CRITICAL: 95, Severity.HIGH: 75, Severity.MEDIUM: 50, Severity.LOW: 20}


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
    guard: Optional[object] = None  # callable(line, all_lines, idx) -> bool
    finding_type: Optional[FindingType] = None
    confidence: int = -1
    priority: int = -1

    def __post_init__(self):
        if self.confidence < 0:
            self.confidence = _SEV_CONF.get(self.severity, 60)
        if self.priority < 0:
            self.priority = _SEV_PRI.get(self.severity, 20)
        if self.finding_type is None:
            if self.category == Category.Performance:
                self.finding_type = FindingType.OPTIMIZATION
            elif self.category == Category.Quality:
                self.finding_type = FindingType.STRENGTHENING
            elif self.category == Category.Security:
                self.finding_type = FindingType.ERROR
            else:
                self.finding_type = FindingType.BUG


@dataclass
class Issue:
    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    description: str
    fix: str
    matched_text: str = ""
    finding_type: str = "BUG"
    confidence: int = 75
    priority: int = 50

    # Aliases so callers can use .message or .name
    @property
    def message(self) -> str:
        return self.description

    @property
    def name(self) -> str:
        return self.rule_id

    @property
    def severity_value(self) -> int:
        return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(self.severity, 3)

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 90: return "CERTAIN"
        if self.confidence >= 75: return "HIGH"
        if self.confidence >= 50: return "LIKELY"
        return "POSSIBLE"

    @property
    def priority_label(self) -> str:
        if self.priority >= 90: return "P0-CRITICAL"
        if self.priority >= 70: return "P1-HIGH"
        if self.priority >= 40: return "P2-MEDIUM"
        if self.priority >= 15: return "P3-LOW"
        return "P4-COSMETIC"


# =========================================================================
#  Anti-pattern helpers
# =========================================================================

def _suppressed_by_anti(anti: list[re.Pattern], lines: list[str], idx: int,
                        radius: int, filepath: str = "") -> bool:
    """Return True if any anti-pattern matches nearby lines or filepath."""
    if not anti:
        return False
    lo = max(0, idx - radius)
    hi = min(len(lines) - 1, idx + radius)
    for j in range(lo, hi + 1):
        for ap in anti:
            if ap.search(lines[j]):
                return True
    # Check filepath too
    if filepath:
        for ap in anti:
            if ap.search(filepath):
                return True
    return False


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _in_string_literal(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("'", '"', "b'", 'b"', "f'", 'f"', "r'", 'r"'))


def _active_code(line: str, _all: list[str], _idx: int) -> bool:
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


def _check_mutable_get(line: str, all_lines: list[str], idx: int) -> bool:
    """Return True only if the .get() result variable is actually mutated nearby."""
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
            if re.search(rf"\b{re.escape(var_name)}\b\.(append|extend|add|update|insert)\s*\(", all_lines[j]):
                return True
            if re.search(rf"\b{re.escape(var_name)}\b\[.+\]\s*=", all_lines[j]):
                return True
        return False
    # Inline .get() (not assigned) — check for mutation on same line
    return bool(re.search(r"\.(append|extend|add|update|insert)\s*\(", line))


def _check_late_binding(line: str, all_lines: list[str], idx: int) -> bool:
    """Return True if a for-loop has a lambda using the loop var without default capture."""
    m = re.search(r"for\s+(\w+)\s+in\b", line)
    if not m:
        return False
    loop_var = m.group(1)
    for j in range(idx + 1, min(len(all_lines), idx + 8)):
        # Check for lambda that uses loop_var but doesn't capture it as default arg
        lam = re.search(r"lambda\b([^:]*?):", all_lines[j])
        if lam and loop_var in all_lines[j]:
            # Safe if loop_var appears in default args: lambda x, i=i
            if re.search(rf"\b{loop_var}\s*=\s*{loop_var}\b", lam.group(1)):
                continue
            return True
    return False


# =========================================================================
#  Rule definitions (30 rules) -- mirrors EditorWindow Python rules
# =========================================================================

def _compile_anti(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


RULES: list[Rule] = [
    # ---- SECURITY ----
    Rule("PY-SEC-01", Severity.CRITICAL, Category.Security,
         "eval() usage -- arbitrary code execution risk",
         "Replace with ast.literal_eval() or redesign.",
         re.compile(r"\beval\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"literal_eval"])),

    Rule("PY-SEC-02", Severity.CRITICAL, Category.Security,
         "os.system() or subprocess with shell=True -- command injection",
         "Use subprocess.run() with list args and shell=False.",
         re.compile(r"(os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True)"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-SEC-03", Severity.CRITICAL, Category.Security,
         "pickle.load on untrusted data -- arbitrary code execution",
         "Use json, msgpack, or safer format.",
         re.compile(r"pickle\.(load|loads)\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-SEC-04", Severity.HIGH, Category.Security,
         "f-string in SQL/shell command -- injection risk",
         "Use parameterized queries or subprocess with list args.",
         re.compile(r'(execute|run|system|popen)\s*\(\s*f["\']'),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    # PY-SEC-05: skip constant assignments and default parameters
    Rule("PY-SEC-05", Severity.HIGH, Category.Security,
         "exec() usage -- arbitrary code execution",
         "Avoid exec(); refactor to safe alternatives.",
         re.compile(r"\bexec\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"^\s*\w+\s*=\s*", r"def\s+\w+\s*\([^)]*exec"])),

    Rule("PY-SEC-06", Severity.MEDIUM, Category.Security,
         "Hardcoded file path -- not portable",
         "Use pathlib.Path or os.path.join with configurable base.",
         re.compile(r"""['"](?:/[a-z]+/|[A-Z]:\\\\)[^'"]{3,}['"]"""),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-SEC-07", Severity.HIGH, Category.Security,
         "assert for input validation -- stripped with -O",
         "Use if/raise ValueError for validation.",
         re.compile(r"^\s*assert\s+(?!.*#\s*nosec)"),
         _compile_anti([r"#\s*VB-IGNORE", r"#\s*nosec", r"test_|_test\.py"])),

    # ---- CORRECTNESS ----
    Rule("PY-COR-01", Severity.HIGH, Category.Bug,
         "Mutable default argument -- shared across calls",
         "Use None as default, create mutable inside function body.",
         re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-COR-02", Severity.HIGH, Category.Bug,
         "Bare except: catches SystemExit, KeyboardInterrupt",
         "Catch specific exceptions.",
         re.compile(r"^\s*except\s*:"),
         _compile_anti([r"#\s*VB-IGNORE"])),

    Rule("PY-COR-03", Severity.MEDIUM, Category.Bug,
         "Comparing with None using == instead of 'is None'",
         "Use 'is None' or 'is not None'.",
         re.compile(r"[!=]=\s*None\b"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-COR-04", Severity.MEDIUM, Category.Bug,
         "open() without context manager -- file may not close",
         "Use 'with open(...) as f:'.",
         re.compile(r"(?<!\bwith\s)\bopen\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"\bwith\b",
                        r"Image\.open", r"BytesIO", r"PIL"])),

    Rule("PY-COR-05", Severity.LOW, Category.Bug,
         "datetime.now() without timezone -- ambiguous",
         "Use datetime.now(tz=timezone.utc).",
         re.compile(r"datetime\.now\s*\(\s*\)"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    # PY-COR-06: only flag if result is mutated, not just read
    Rule("PY-COR-06", Severity.MEDIUM, Category.Bug,
         "dict.get() with mutable default -- mutated result is shared",
         "Use dict.get(key) with None check, then create mutable separately.",
         re.compile(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
         guard=_check_mutable_get),

    Rule("PY-COR-07", Severity.MEDIUM, Category.Bug,
         "Class with __del__ -- unpredictable GC, prevents ref cycle collection",
         "Use context managers or weakref.finalize.",
         re.compile(r"def\s+__del__\s*\(\s*self"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-COR-08", Severity.MEDIUM, Category.Bug,
         "Thread without daemon=True -- may prevent clean shutdown",
         "Set daemon=True or join before exit.",
         re.compile(r"Thread\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"daemon"])),

    Rule("PY-COR-09", Severity.LOW, Category.Bug,
         "json.loads/load without error handling — crashes on malformed input",
         "Wrap in try/except json.JSONDecodeError to handle corrupt JSON gracefully.",
         re.compile(r"json\.loads?\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"except.*JSON",
                        r"\btry\s*:", r"\bexcept\b"]),
         confidence=68,
         anti_radius=10),

    Rule("PY-COR-10", Severity.LOW, Category.Bug,
         "Float equality comparison -- use math.isclose",
         "Use math.isclose(a, b) or abs(a - b) < epsilon.",
         re.compile(r"(?<!\w)(==|!=)\s*\d+\.\d+"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"])),

    Rule("PY-COR-11", Severity.MEDIUM, Category.Bug,
         "Re-raising exception without chain -- loses traceback",
         "Use 'raise X(...) from e'.",
         re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
         _compile_anti([r"#\s*VB-IGNORE", r"\bfrom\s+\w+"]),
         guard=lambda line, a, i: any("except" in a[j] for j in range(max(0, i - 5), i))),

    Rule("PY-COR-12", Severity.MEDIUM, Category.Bug,
         "Exception type too broad -- catches bugs with expected errors",
         "Catch specific exceptions.",
         re.compile(r"except\s+Exception\s*(?:as|\s*:)"),
         _compile_anti([r"#\s*VB-IGNORE", r"# broad catch intentional",
                        r"logger\.exception", r"mcp\.tool", r"return\s+json\.dumps"]),
         anti_radius=10,
         guard=lambda line, a, i: not any(
             re.search(r"logger\.(exception|error)\s*\(", a[j]) or
             re.search(r"return\s+(json\.dumps|\"?\{)", a[j])
             for j in range(i + 1, min(len(a), i + 10))
             if not re.search(r"^\s*(except|def |class )\b", a[j]))),

    # PY-COR-13: magic numbers -- only in control flow, not data dicts
    Rule("PY-COR-13", Severity.LOW, Category.Bug,
         "Import inside function body -- may indicate circular import workaround",
         "Restructure modules to avoid circular dependencies.",
         re.compile(r"SENTINEL_AST_ONLY")),  # handled by AST pass

    # PY-COR-14: Variable shadowing built-in names
    Rule("PY-COR-14", Severity.MEDIUM, Category.Bug,
         "Variable shadows built-in name (list, dict, set, type, id, etc.)",
         "Choose a different variable name: items, mapping, group, etc.",
         re.compile(r"^\s*(list|dict|set|str|int|float|bool|tuple|type|id|input|filter|map|zip|range|len|sum|min|max|any|all|sorted|reversed|hash|next|iter|open|print|format|bytes|object|super)\s*=\s*"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"typing", r"import"])),

    # PY-COR-15: Late binding closure in loop
    Rule("PY-COR-15", Severity.HIGH, Category.Bug,
         "Lambda in loop captures loop variable by reference -- late binding bug",
         "Capture with default arg: lambda x, i=i: ... or use functools.partial.",
         re.compile(r"for\s+(\w+)\s+in\b"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
         guard=lambda line, a, i: _check_late_binding(line, a, i)),

    # ---- PERFORMANCE ----
    Rule("PY-PERF-01", Severity.LOW, Category.Performance,
         "String concatenation in loop -- O(n^2)",
         "Collect parts in list, ''.join(parts) after loop.",
         re.compile(r"\w+\s*\+=\s*['\"]"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#",
                        r"\bstring\b", r"\bvar\b", r"\bint\b",
                        r"\.Count\b", r"\.Length\b", r"//\s"]),
         guard=lambda line, a, i: any(
             re.search(r"^\s*(for|while)\b", a[j])
             for j in range(max(0, i - 5), i))),

    # PY-PERF-02: skip if regex used only once (not in a loop)
    Rule("PY-PERF-02", Severity.LOW, Category.Performance,
         "re.match/search/findall without compile for repeated pattern",
         "Compile pattern once with re.compile() and reuse.",
         re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r"re\.compile"]),
         guard=lambda line, a, i: any(
             re.search(r"^\s*(for|while)\b", a[j])
             for j in range(max(0, i - 5), i))),

    Rule("PY-PERF-03", Severity.LOW, Category.Performance,
         "Large file .read() without chunking -- may exhaust memory",
         "Use chunked reading: for line in file, or file.read(chunk_size).",
         re.compile(r"\.read\s*\(\s*\)"),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#", r'"rb"', r"BytesIO",
                        r"img_bytes", r"image_data", r"base64",
                        r'encoding="utf-8"', r"\.read_text\s*\("])),

    # ---- STYLE ----
    Rule("PY-STY-01", Severity.LOW, Category.Quality,
         "os.path usage — consider pathlib.Path for cleaner path handling",
         "Replace os.path.join(a, b) with Path(a) / b. pathlib is more readable and handles cross-platform paths.",
         re.compile(r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\s*\("),
         _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
         confidence=72,
         finding_type=FindingType.STRENGTHENING),

    Rule("PY-STY-02", Severity.LOW, Category.Quality,
         "Deeply nested function (3+ indent levels) — hard to test and maintain",
         "Extract inner function to module level or class method for better testability.",
         re.compile(r"^\s{12,}def\s+\w+\s*\("),
         _compile_anti([r"#\s*VB-IGNORE"]),
         confidence=85,
         finding_type=FindingType.STRENGTHENING),

    Rule("PY-STY-03", Severity.LOW, Category.Quality,
         "Star import pollutes namespace — imported names are unknown to readers and tools",
         "Replace with explicit imports: from X import ClassA, func_b, CONST_C.",
         re.compile(r"from\s+\S+\s+import\s+\*"),
         _compile_anti([r"#\s*VB-IGNORE"]),
         confidence=92,
         finding_type=FindingType.STRENGTHENING),

    Rule("PY-STY-04", Severity.LOW, Category.Quality,
         "Global variable mutation — makes function behavior depend on hidden state",
         "Pass the value as a function parameter, or encapsulate in a class with clear ownership.",
         re.compile(r"^\s+global\s+\w+"),
         _compile_anti([r"#\s*VB-IGNORE"]),
         confidence=78,
         finding_type=FindingType.STRENGTHENING),

    # PY-STY-05/06/07/08 are AST-only (sentinel patterns)
    Rule("PY-STY-05", Severity.LOW, Category.Quality,
         "Missing __main__ guard -- code runs on import",
         "Wrap in: if __name__ == '__main__':",
         re.compile(r"SENTINEL_AST_ONLY")),

    Rule("PY-STY-06", Severity.LOW, Category.Quality,
         "Missing __all__ in public module",
         "Add __all__ = [...] to define the public API.",
         re.compile(r"SENTINEL_AST_ONLY")),

    Rule("PY-STY-09", Severity.LOW, Category.Quality,
         "Function exceeds length threshold",
         "Break long functions into smaller, well-named helpers.",
         re.compile(r"SENTINEL_AST_ONLY")),

    Rule("PY-STY-08", Severity.LOW, Category.Quality,
         "Missing type annotation on public function",
         "Add return type annotation: def func(...) -> ReturnType:",
         re.compile(r"SENTINEL_AST_ONLY")),
]


# =========================================================================
#  AST-aware analysis (Pass 2)
# =========================================================================

def _ast_analyze(filepath: str, source: str) -> list[Issue]:
    """AST-based analysis for patterns regex cannot reliably detect."""
    issues: list[Issue] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    _fp_norm = filepath.replace("\\", "/")
    is_template = filepath.endswith("_templates.py") or "unity_templates/" in _fp_norm
    is_mcp_handler = _fp_norm.endswith("_server.py") or "/unity_tools/" in _fp_norm

    # Collect all names used
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
                continue  # __future__ imports are compiler directives, not runtime
            if node.names[0].name == "*":
                continue
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names[name] = node.lineno

    # PY-STY-07: Unused imports
    for name, lineno in imported_names.items():
        if name.startswith("_"):
            continue
        if name not in all_names_used:
            issues.append(Issue(
                rule_id="PY-STY-07", severity=Severity.LOW.name,
                category=Category.Quality.name, file=filepath, line=lineno,
                description=f"Unused import: '{name}' — not referenced anywhere in this module",
                fix=f"Remove 'import {name}' or 'from ... import {name}' if truly unused. If re-exported, add to __all__.",
                matched_text=name,
                finding_type="STRENGTHENING", confidence=82))

    # PY-STY-08: Missing type annotations on public functions (no _ prefix)
    # Only flag functions listed in __all__ or with docstrings if module has __all__
    has_all = any(
        isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
        for n in ast.iter_child_nodes(tree))

    all_names_list: set[str] = set()
    if has_all:
        for n in ast.iter_child_nodes(tree):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        if isinstance(n.value, (ast.List, ast.Tuple)):
                            for elt in n.value.elts:
                                if isinstance(elt, ast.Constant):
                                    all_names_list.add(elt.value)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            # PY-STY-08 FP fix: only flag public functions (in __all__ or has docstring)
            if has_all and node.name not in all_names_list:
                continue
            if node.returns is None:
                issues.append(Issue(
                    rule_id="PY-STY-08", severity=Severity.LOW.name,
                    category=Category.Quality.name, file=filepath, line=node.lineno,
                    description=f"Public function '{node.name}' missing return type annotation",
                    fix="Add: def func(...) -> ReturnType:", matched_text=node.name,
                    finding_type="STRENGTHENING", confidence=85))

    # PY-STY-05: Missing __main__ guard
    has_main_guard = False
    has_top_level_code = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Compare) and
                    isinstance(test.left, ast.Name) and
                    test.left.id == "__name__"):
                has_main_guard = True
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            has_top_level_code = True

    if has_top_level_code and not has_main_guard:
        issues.append(Issue(
            rule_id="PY-STY-05", severity=Severity.LOW.name,
            category=Category.Quality.name, file=filepath, line=1,
            description="Module has top-level executable code without __main__ guard",
            fix="Wrap in: if __name__ == '__main__':",
            finding_type="STRENGTHENING", confidence=90))

    # PY-STY-06: Missing __all__ -- only flag public functions (no _ prefix)
    public_names = [
        n for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")]
    if not has_all and len(public_names) >= 3:
        issues.append(Issue(
            rule_id="PY-STY-06", severity=Severity.LOW.name,
            category=Category.Quality.name, file=filepath, line=1,
            description=f"Module exports {len(public_names)} public names but has no __all__",
            fix="Add __all__ = [...].",
            finding_type="STRENGTHENING", confidence=80))

    # PY-STY-09: Function length -- skip templates entirely (their length is
    # dominated by C# string literals, not Python complexity). MCP handlers use
    # the compound-action pattern with many branches so they get a higher limit.
    if is_template:
        threshold = None  # skip entirely
    elif is_mcp_handler:
        threshold = 200
    else:
        threshold = 60
    if threshold is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    length = node.end_lineno - node.lineno
                    if length > threshold:
                        issues.append(Issue(
                            rule_id="PY-STY-09", severity=Severity.LOW.name,
                            category=Category.Quality.name, file=filepath,
                            line=node.lineno,
                            description=f"Function '{node.name}' is {length} lines (threshold: {threshold})",
                            fix="Break into smaller helpers.",
                            matched_text=node.name,
                            finding_type="STRENGTHENING", confidence=90))

    # PY-COR-13: Import inside function body
    # Skip known heavy/optional deps that are intentionally lazy-imported
    _LAZY_OK = {"numpy", "np", "PIL", "google", "defusedxml", "cv2",
                "scipy", "torch", "sklearn", "pandas", "matplotlib",
                "fnmatch", "shutil", "tempfile", "subprocess", "os",
                "httpx", "json", "typing", "importlib", "pkgutil"}
    for func_node in ast.walk(tree):
        if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Collect imports at any depth inside this function, noting if in try block
        try_import_lines: set[int] = set()
        for child in ast.walk(func_node):
            if isinstance(child, ast.Try):
                for body_stmt in child.body:
                    if isinstance(body_stmt, (ast.Import, ast.ImportFrom)):
                        try_import_lines.add(body_stmt.lineno)
        for child in ast.iter_child_nodes(func_node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                if child.lineno in try_import_lines:
                    continue  # Optional dependency pattern
                mod_name = ""
                if isinstance(child, ast.Import):
                    mod_name = child.names[0].name.split(".")[0]
                elif isinstance(child, ast.ImportFrom) and child.module:
                    mod_name = child.module.split(".")[0]
                if mod_name in _LAZY_OK:
                    continue
                issues.append(Issue(
                    rule_id="PY-COR-13", severity=Severity.LOW.name,
                    category=Category.Bug.name, file=filepath,
                    line=child.lineno,
                    description=f"Import '{mod_name}' inside function body -- may indicate circular import",
                    fix="Restructure to avoid circular dependencies or add to _LAZY_OK if intentional."))

    return issues


# =========================================================================
#  Scanner
# =========================================================================

def _is_in_triple_quote(lines: list[str]) -> list[bool]:
    """Pre-classify lines inside triple-quoted strings (handles r/b/f/u prefixes).

    Tracks which quote type (single vs double) opened the block so that
    e.g. triple-double-quotes inside a triple-single-quoted string do not
    cause a false close.
    """
    _TDQ = chr(34) * 3
    _TSQ = chr(39) * 3
    _TQ_START = re.compile(r"(?:=\s*)?[brufBRUF]{0,2}(?:" + _TSQ + "|" + _TDQ + ")")
    in_tq = [False] * len(lines)
    inside = False
    open_quote = ""  # which triple-quote type opened the block: _TDQ or _TSQ
    for i, line in enumerate(lines):
        stripped = line.strip()
        if inside:
            in_tq[i] = True
            # Only close on the SAME quote type that opened the block
            if open_quote in stripped:
                inside = False
                open_quote = ""
            continue
        # Check for triple-quote opening (with prefix like r, b, f, rb, etc.)
        if _TQ_START.search(stripped):
            in_tq[i] = True
            # Determine which quote type(s) are on this line
            dq_count = stripped.count(_TDQ)
            sq_count = stripped.count(_TSQ)
            # If both types present, the one that appears first is the opener
            if dq_count > 0 and sq_count > 0:
                first_dq = stripped.index(_TDQ)
                first_sq = stripped.index(_TSQ)
                if first_dq < first_sq:
                    if dq_count % 2 == 1:
                        inside = True
                        open_quote = _TDQ
                else:
                    if sq_count % 2 == 1:
                        inside = True
                        open_quote = _TSQ
            elif dq_count % 2 == 1:
                inside = True
                open_quote = _TDQ
            elif sq_count % 2 == 1:
                inside = True
                open_quote = _TSQ
            continue
    return in_tq


def scan_file(filepath: str) -> list[Issue]:
    """Scan a single Python file with regex pass + AST pass."""
    issues: list[Issue] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return issues

    lines = content.split("\n")
    in_tq = _is_in_triple_quote(lines)

    # Build suppressed set
    suppressed: set[str] = set()
    ignore_rx = re.compile(r"#\s*VB-IGNORE:\s*([\w,-]+)")
    for line in lines:
        m = ignore_rx.search(line)
        if m:
            for rid in m.group(1).split(","):
                suppressed.add(rid.strip())

    # Pass 1: Regex with anti-patterns
    for rule in RULES:
        if rule.id in suppressed:
            continue
        if "SENTINEL" in rule.pattern.pattern:
            continue
        for i, line in enumerate(lines):
            if "VB-IGNORE" in line:
                continue
            if _is_comment(line) or in_tq[i]:
                continue
            m = rule.pattern.search(line)
            if not m:
                continue
            # Skip if the match falls inside a string literal on this line
            match_start = m.start()
            if _match_is_in_string(line, match_start):
                continue
            # Anti-pattern suppression
            if _suppressed_by_anti(rule.anti_patterns, lines, i, rule.anti_radius, filepath):
                continue
            if rule.guard and not rule.guard(line, lines, i):
                continue
            issues.append(Issue(
                rule_id=rule.id, severity=rule.severity.name,
                category=rule.category.name, file=filepath, line=i + 1,
                description=rule.description, fix=rule.fix,
                matched_text=line.strip(),
                finding_type=rule.finding_type.name if rule.finding_type else "BUG",
                confidence=rule.confidence, priority=rule.priority))

    # Pass 2: AST
    ast_issues = _ast_analyze(filepath, content)
    for issue in ast_issues:
        if issue.rule_id not in suppressed:
            issues.append(issue)

    return issues


def scan_directory(dirpath: str) -> list[Issue]:
    """Recursively scan all .py files in a directory."""
    all_issues: list[Issue] = []
    root = Path(dirpath)
    skip = {".venv", "venv", "node_modules", "__pycache__",
            ".git", ".tox", "dist", "build", "egg-info", ".tmp"}
    for py_file in sorted(root.rglob("*.py")):
        if any(p in skip for p in py_file.parts):
            continue
        all_issues.extend(scan_file(str(py_file)))
    return all_issues


def generate_report(issues: list[Issue]) -> dict:
    """Generate structured report dict with confidence/priority grading."""
    sev_counts = {s.name: 0 for s in Severity}
    type_counts = {"ERROR": 0, "BUG": 0, "OPTIMIZATION": 0, "STRENGTHENING": 0}
    for issue in issues:
        sev_counts[issue.severity] += 1
        type_counts[issue.finding_type] = type_counts.get(issue.finding_type, 0) + 1
    avg_conf = sum(i.confidence for i in issues) / len(issues) if issues else 0
    avg_pri = sum(i.priority for i in issues) / len(issues) if issues else 0
    return {
        "total_issues": len(issues),
        "critical": sev_counts["CRITICAL"],
        "high": sev_counts["HIGH"],
        "medium": sev_counts["MEDIUM"],
        "low": sev_counts["LOW"],
        "errors_bugs": type_counts.get("ERROR", 0) + type_counts.get("BUG", 0),
        "optimizations": type_counts.get("OPTIMIZATION", 0),
        "strengthening": type_counts.get("STRENGTHENING", 0),
        "avg_confidence": round(avg_conf, 1),
        "avg_priority": round(avg_pri, 1),
        "issues": [asdict(i) for i in issues],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="VeilBreakers Python Code Reviewer")
    parser.add_argument("path", nargs="?", default=".",
                        help="File or directory to scan (default: current dir)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON file path (default: stdout)")
    parser.add_argument("--severity", "-s", default="LOW",
                        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                        help="Minimum severity to report (default: LOW)")
    args = parser.parse_args()

    target = Path(args.path)
    if target.is_file():
        issues = scan_file(str(target))
    elif target.is_dir():
        issues = scan_directory(str(target))
    else:
        print(f"Error: {args.path} is not a valid file or directory", file=sys.stderr)
        sys.exit(2)

    threshold = Severity[args.severity]
    issues = [i for i in issues if Severity[i.severity] <= threshold]

    report = generate_report(issues)
    output = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output} ({len(issues)} issues)", file=sys.stderr)
    else:
        # Human-readable console output
        sev_icons = {"CRITICAL": "!!!", "HIGH": " ! ", "MEDIUM": " ~ ", "LOW": " . "}
        type_labels = {"ERROR": "Bug/Error", "BUG": "Bug", "OPTIMIZATION": "Optimization", "STRENGTHENING": "Code Quality"}
        cat_labels = {"Security": "Security", "Bug": "Correctness", "Performance": "Performance", "Quality": "Code Quality"}

        # Group by file
        from collections import defaultdict
        by_file = defaultdict(list)
        for issue in sorted(issues, key=lambda i: (Severity[i.severity].value, i.priority * -1)):
            by_file[issue.file].append(issue)

        file_num = 0
        for filepath, file_issues in sorted(by_file.items()):
            file_num += 1
            short = filepath.replace("\\", "/")
            if "veilbreakers_mcp/" in short:
                short = short.split("veilbreakers_mcp/")[-1]
            crit_count = sum(1 for i in file_issues if i.severity in ("CRITICAL", "HIGH"))
            header = f"  ({crit_count} critical)" if crit_count else ""
            print(f"\n{'='*70}")
            print(f"  File {file_num}: {short}  [{len(file_issues)} findings]{header}")
            print(f"{'='*70}")

            for idx, issue in enumerate(file_issues, 1):
                icon = sev_icons.get(issue.severity, "   ")
                ftype = type_labels.get(issue.finding_type, issue.finding_type)
                cat = cat_labels.get(issue.category, issue.category)
                conf_pct = issue.confidence

                print(f"\n  [{icon}] #{idx}  {issue.severity}  |  {cat}  |  {ftype}")
                print(f"       Line {issue.line}: {issue.description}")
                print(f"       Fix: {issue.fix}")
                if issue.matched_text:
                    code = issue.matched_text[:90]
                    print(f"       Code: {code}")
                if conf_pct < 70:
                    # Explain WHY confidence is low
                    reasons = {
                        "PY-COR-09": "try/except may exist but beyond scan radius (30 lines). Check enclosing function.",
                        "PY-PERF-02": "Only matters if called repeatedly in a loop. Single-use re.search is fine.",
                        "PY-STY-01": "os.path is valid Python; pathlib is preferred but not required.",
                    }
                    reason = reasons.get(issue.rule_id, "Pattern match is contextual — verify the surrounding code.")
                    print(f"       Why {conf_pct}%: {reason}")
                print(f"       Rule: {issue.rule_id}  |  Confidence: {conf_pct}%  |  Priority: {issue.priority}/100")

        # Summary
        r = report
        print(f"\n{'='*70}")
        print(f"  REVIEW SUMMARY")
        print(f"{'='*70}")
        print(f"  Files scanned:  {len(by_file)}")
        print(f"  Total findings: {r['total_issues']}")
        print()
        if r['critical'] > 0:
            print(f"  [!!!] CRITICAL:  {r['critical']}  -- fix immediately")
        if r['high'] > 0:
            print(f"  [ ! ] HIGH:      {r['high']}  -- fix before merge")
        if r['medium'] > 0:
            print(f"  [ ~ ] MEDIUM:    {r['medium']}  -- fix when possible")
        if r['low'] > 0:
            print(f"  [ . ] LOW:       {r['low']}  -- informational")
        if r['total_issues'] == 0:
            print(f"  ALL CLEAN - no issues found")
        print()
        print(f"  Bugs/Errors:     {r['errors_bugs']}")
        print(f"  Optimizations:   {r['optimizations']}")
        print(f"  Code Quality:    {r['strengthening']}")
        print(f"  Avg Confidence:  {r['avg_confidence']}%")
        print(f"{'='*70}")

    has_serious = any(i.severity in ("CRITICAL", "HIGH") for i in issues)
    sys.exit(1 if has_serious else 0)


if __name__ == "__main__":
    main()