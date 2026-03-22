#!/usr/bin/env python3
"""VeilBreakers Python Code Reviewer.

Two-pass review system for Python codebases:
  Pass 1: Compiled regex pattern matching (fast, line-by-line)
  Pass 2: AST-aware analysis for imports, function signatures, scoping

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
    Correctness = 1
    Performance = 2
    Style = 3


@dataclass
class Rule:
    id: str
    severity: Severity
    category: Category
    description: str
    fix: str
    pattern: re.Pattern
    guard: Optional[object] = None  # callable(line, all_lines, idx) -> bool


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


# Guard helpers
def _not_in_comment(line: str, _all: list[str], _idx: int) -> bool:
    stripped = line.lstrip()
    return not stripped.startswith("#")


def _not_in_string(line: str, _all: list[str], _idx: int) -> bool:
    stripped = line.lstrip()
    return not stripped.startswith(("'", '"', "b'", 'b"', "f'", 'f"', "r'", 'r"'))


def _active_code(line: str, all_lines: list[str], idx: int) -> bool:
    return _not_in_comment(line, all_lines, idx) and _not_in_string(line, all_lines, idx)


# Rule definitions (30 rules)
RULES: list[Rule] = [
    # ---- SECURITY ----
    Rule("PY-SEC-01", Severity.CRITICAL, Category.Security,
         "eval() usage -- arbitrary code execution risk",
         "Replace with ast.literal_eval() for safe data parsing, or redesign to avoid eval.",
         re.compile(r"\beval\s*\("), guard=_active_code),
    Rule("PY-SEC-02", Severity.CRITICAL, Category.Security,
         "os.system() or subprocess with shell=True -- command injection risk",
         "Use subprocess.run() with a list of args and shell=False.",
         re.compile(r"(os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True)"),
         guard=_active_code),
    Rule("PY-SEC-03", Severity.CRITICAL, Category.Security,
         "pickle.load on potentially untrusted data -- arbitrary code execution",
         "Use json, msgpack, or a safer serialization format.",
         re.compile(r"pickle\.(load|loads)\s*\("), guard=_active_code),
    Rule("PY-SEC-04", Severity.HIGH, Category.Security,
         "f-string with variable in SQL/shell command -- injection risk",
         "Use parameterized queries for SQL; use subprocess with list args for shell.",
         re.compile(r'(execute|run|system|popen)\s*\(\s*f["\']'),
         guard=_active_code),
    Rule("PY-SEC-05", Severity.HIGH, Category.Security,
         "exec() usage -- arbitrary code execution",
         "Avoid exec(); refactor to use safe alternatives.",
         re.compile(r"\bexec\s*\("), guard=_active_code),
    Rule("PY-SEC-06", Severity.MEDIUM, Category.Security,
         "Hardcoded file path -- not portable, consider pathlib or config",
         "Use pathlib.Path or os.path.join with configurable base directories.",
         re.compile(r"['\"](/[a-z]+/|[A-Z]:\\\\)[^'\"]{3,}['\"]"),
         guard=_active_code),
    Rule("PY-SEC-07", Severity.HIGH, Category.Security,
         "assert used for input validation -- stripped in optimized mode (-O)",
         "Use if/raise ValueError for validation that must always run.",
         re.compile(r"^\s*assert\s+(?!.*#\s*nosec)"),
         guard=_not_in_comment),
    # ---- CORRECTNESS ----
    Rule("PY-COR-01", Severity.HIGH, Category.Correctness,
         "Mutable default argument -- shared across calls, causes subtle bugs",
         "Use None as default and create the mutable inside the function body.",
         re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
         guard=_active_code),
    Rule("PY-COR-02", Severity.HIGH, Category.Correctness,
         "Bare except: clause -- catches SystemExit, KeyboardInterrupt, etc.",
         "Catch specific exceptions: except ValueError, except Exception as e.",
         re.compile(r"^\s*except\s*:"), guard=_not_in_comment),
    Rule("PY-COR-03", Severity.MEDIUM, Category.Correctness,
         "Comparing with None using == instead of 'is None'",
         "Use 'is None' or 'is not None' for identity comparison with None.",
         re.compile(r"[!=]=\s*None\b"), guard=_active_code),
    Rule("PY-COR-04", Severity.MEDIUM, Category.Correctness,
         "open() without context manager -- file may not be closed on exception",
         "Use 'with open(...) as f:' to ensure proper cleanup.",
         re.compile(r"(?<!\bwith\s)\bopen\s*\("),
         guard=lambda line, a, i: "with" not in line and _active_code(line, a, i)),
    Rule("PY-COR-05", Severity.LOW, Category.Correctness,
         "datetime.now() without timezone -- ambiguous in distributed systems",
         "Use datetime.now(tz=timezone.utc) or datetime.now(ZoneInfo('...')).",
         re.compile(r"datetime\.now\s*\(\s*\)"), guard=_active_code),
    Rule("PY-COR-06", Severity.MEDIUM, Category.Correctness,
         "dict.get() with mutable default -- result is mutated (shared object bug)",
         "Use dict.get(key) with None check, then create mutable separately.",
         re.compile(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))"),
         guard=lambda line, a, i: _active_code(line, a, i) and any(
             ".append" in a[j] or ".extend" in a[j] or "self." in a[j]
             for j in range(i, min(len(a), i + 3)))),
    Rule("PY-COR-07", Severity.MEDIUM, Category.Correctness,
         "Class with __del__ -- unpredictable GC timing, prevents ref cycle collection",
         "Use context managers (__enter__/__exit__) or weakref.finalize instead.",
         re.compile(r"def\s+__del__\s*\(\s*self"), guard=_active_code),
    Rule("PY-COR-08", Severity.MEDIUM, Category.Correctness,
         "Thread created without daemon=True -- may prevent clean shutdown",
         "Set daemon=True or ensure thread is joined before exit.",
         re.compile(r"Thread\s*\("),
         guard=lambda line, a, i: "daemon" not in line and _active_code(line, a, i)),
    Rule("PY-COR-09", Severity.LOW, Category.Correctness,
         "json.loads without error handling -- will raise on malformed input",
         "Wrap json.loads in try/except json.JSONDecodeError.",
         re.compile(r"json\.loads?\s*\("),
         guard=lambda line, a, i: not any("except" in a[j] and "JSON" in a[j]
             for j in range(max(0, i-5), min(len(a), i+10))) and _active_code(line, a, i)),
    Rule("PY-COR-10", Severity.LOW, Category.Correctness,
         "Float equality comparison -- use math.isclose for floating-point",
         "Use math.isclose(a, b) or abs(a - b) < epsilon.",
         re.compile(r"(?<!\w)(==|!=)\s*\d+\.\d+"),
         guard=_active_code),
    Rule("PY-COR-11", Severity.MEDIUM, Category.Correctness,
         "Re-raising exception without chain -- loses traceback context",
         "Use 'raise NewException(...) from e' to preserve the exception chain.",
         re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
         guard=lambda line, a, i: any("except" in a[j] for j in range(max(0, i-5), i)) and _active_code(line, a, i)),
    Rule("PY-COR-12", Severity.MEDIUM, Category.Correctness,
         "Exception type too broad -- catches bugs along with expected errors",
         "Catch specific exceptions instead of bare Exception.",
         re.compile(r"except\s+Exception\s*(?:as|\s*:)"),
         guard=_not_in_comment),
    # ---- PERFORMANCE ----
    Rule("PY-PERF-01", Severity.LOW, Category.Performance,
         "String concatenation in loop -- O(n^2), use str.join or list append",
         "Collect parts in a list and ''.join(parts) after the loop.",
         re.compile(r"(?:for|while)\b.*\n\s+\w+\s*\+=\s*['\"]"),
         guard=_not_in_comment),
    Rule("PY-PERF-02", Severity.LOW, Category.Performance,
         "re.match/search/findall without re.compile for repeated pattern",
         "Compile the pattern once with re.compile() and reuse the compiled object.",
         re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
         guard=_active_code),
    Rule("PY-PERF-03", Severity.LOW, Category.Performance,
         "Large file read without chunking -- may exhaust memory",
         "Use chunked reading: for line in file, or file.read(chunk_size).",
         re.compile(r"\.read\s*\(\s*\)"), guard=_active_code),
    # ---- STYLE ----
    Rule("PY-STY-01", Severity.LOW, Category.Style,
         "os.path usage instead of pathlib.Path -- pathlib is more Pythonic",
         "Use pathlib.Path for path manipulation (Python 3.4+).",
         re.compile(r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\s*\("),
         guard=_active_code),
    Rule("PY-STY-02", Severity.LOW, Category.Style,
         "Nested function definitions over 3 levels -- hard to read and test",
         "Extract inner functions to module level or class methods.",
         re.compile(r"^\s{12,}def\s+\w+\s*\("),
         guard=_not_in_comment),
    Rule("PY-STY-03", Severity.LOW, Category.Style,
         "Star import (from X import *) -- namespace pollution, hides origin",
         "Import specific names: from X import a, b, c.",
         re.compile(r"from\s+\S+\s+import\s+\*"),
         guard=_not_in_comment),
    Rule("PY-STY-04", Severity.LOW, Category.Style,
         "Global variable mutation -- makes code hard to reason about",
         "Pass as function parameters or use a class to encapsulate state.",
         re.compile(r"^\s+global\s+\w+"), guard=_not_in_comment),
    Rule("PY-STY-05", Severity.LOW, Category.Style,
         "Missing if __name__ == '__main__' guard -- code runs on import",
         "Wrap script-level code in: if __name__ == '__main__':",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass
    Rule("PY-STY-06", Severity.LOW, Category.Style,
         "Missing __all__ in public module -- unclear public API surface",
         "Add __all__ = ['PublicClass', 'public_func'] to define the public API.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass
    Rule("PY-STY-07", Severity.LOW, Category.Style,
         "Unused import detected",
         "Remove the unused import to keep the namespace clean.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass
    # PY-STY-08: Only flag public functions (no _ prefix)
    Rule("PY-STY-08", Severity.LOW, Category.Style,
         "Missing type annotation on public function",
         "Add return type annotation and parameter type hints.",
         re.compile(r"SENTINEL_NEVER_MATCHES_PLACEHOLDER")),  # handled by AST pass
]

# Pass 2: AST-aware analysis
def _ast_analyze(filepath: str, source: str) -> list[Issue]:
    """AST-based analysis for patterns that regex cannot reliably detect."""
    issues: list[Issue] = []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    # Collect all names used in the module (for unused import detection)
    all_names_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            all_names_used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Collect top-level attribute access like `os.path`
            if isinstance(node.value, ast.Name):
                all_names_used.add(node.value.id)

    # Check imports
    imported_names: dict[str, int] = {}  # name -> line
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.names[0].name == "*":
                continue  # handled by regex rule
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names[name] = node.lineno

    # PY-STY-07: Unused imports
    for name, lineno in imported_names.items():
        if name.startswith("_"):
            continue  # convention: private/re-export
        if name not in all_names_used:
            issues.append(Issue(
                rule_id="PY-STY-07",
                severity=Severity.LOW.name,
                category=Category.Style.name,
                file=filepath,
                line=lineno,
                description=f"Unused import: '{name}'",
                fix="Remove the unused import to keep the namespace clean.",
                matched_text=name,
            ))

    # PY-STY-08: Missing type annotations on public functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            if node.returns is None:
                issues.append(Issue(
                    rule_id="PY-STY-08",
                    severity=Severity.LOW.name,
                    category=Category.Style.name,
                    file=filepath,
                    line=node.lineno,
                    description=f"Public function '{node.name}' missing return type annotation",
                    fix="Add return type annotation: def func(...) -> ReturnType:",
                    matched_text=node.name,
                ))

    # PY-STY-05: Missing __main__ guard (only for files with top-level executable code)
    has_main_guard = False
    has_top_level_code = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            # Check for if __name__ == "__main__"
            test = node.test
            if (isinstance(test, ast.Compare) and
                    isinstance(test.left, ast.Name) and
                    test.left.id == "__name__"):
                has_main_guard = True
        elif isinstance(node, ast.Expr):
            # Function calls at module level
            if isinstance(node.value, ast.Call):
                has_top_level_code = True

    if has_top_level_code and not has_main_guard:
        issues.append(Issue(
            rule_id="PY-STY-05",
            severity=Severity.LOW.name,
            category=Category.Style.name,
            file=filepath,
            line=1,
            description="Module has top-level executable code without __main__ guard",
            fix="Wrap script-level code in: if __name__ == '__main__':",
        ))

    # PY-STY-06: Missing __all__ in modules with public names
    has_all = any(
        isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__"
            for t in n.targets
        )
        for n in ast.iter_child_nodes(tree)
    )
    public_names = [
        n for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    ]
    if not has_all and len(public_names) >= 3:
        issues.append(Issue(
            rule_id="PY-STY-06",
            severity=Severity.LOW.name,
            category=Category.Style.name,
            file=filepath,
            line=1,
            description=f"Module exports {len(public_names)} public names but has no __all__",
            fix="Add __all__ = [...] to define the public API.",
        ))

    # Circular import detection hint: if any import is inside a function body
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    issues.append(Issue(
                        rule_id="PY-COR-13",
                        severity=Severity.LOW.name,
                        category=Category.Correctness.name,
                        file=filepath,
                        line=child.lineno,
                        description="Import inside function body -- may indicate circular import workaround",
                        fix="Restructure modules to avoid circular dependencies.",
                    ))

    return issues


# Scanner
def scan_file(filepath: str) -> list[Issue]:
    """Scan a single Python file with both passes."""
    issues: list[Issue] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return issues

    lines = content.split("\n")

    # Build set of suppressed rules
    suppressed: set[str] = set()
    ignore_re = re.compile(r"#\s*VB-IGNORE:\s*([\w,-]+)")
    for line in lines:
        m = ignore_re.search(line)
        if m:
            for rule_id in m.group(1).split(","):
                suppressed.add(rule_id.strip())

    # Pass 1: Regex
    for rule in RULES:
        if rule.id in suppressed:
            continue
        # Skip sentinel rules (AST-only)
        if "SENTINEL" in rule.pattern.pattern:
            continue
        for i, line in enumerate(lines):
            if "VB-IGNORE" in line:
                continue
            if rule.pattern.search(line):
                if rule.guard and not rule.guard(line, lines, i):
                    continue
                issues.append(Issue(
                    rule_id=rule.id,
                    severity=rule.severity.name,
                    category=rule.category.name,
                    file=filepath,
                    line=i + 1,
                    description=rule.description,
                    fix=rule.fix,
                    matched_text=line.strip(),
                ))

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

    for py_file in sorted(root.rglob("*.py")):
        # Skip common non-project dirs
        parts = py_file.parts
        if any(p in (".venv", "venv", "node_modules", "__pycache__",
                      ".git", ".tox", "dist", "build", "egg-info")
               for p in parts):
            continue
        all_issues.extend(scan_file(str(py_file)))

    return all_issues


def generate_report(issues: list[Issue]) -> dict:
    """Generate a structured report dict."""
    severity_counts = {s.name: 0 for s in Severity}
    for issue in issues:
        severity_counts[issue.severity] += 1

    return {
        "total_issues": len(issues),
        "critical": severity_counts["CRITICAL"],
        "high": severity_counts["HIGH"],
        "medium": severity_counts["MEDIUM"],
        "low": severity_counts["LOW"],
        "issues": [asdict(i) for i in issues],
    }


def main():
    parser = argparse.ArgumentParser(
        description="VeilBreakers Python Code Reviewer")
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
        print(f"Error: {args.path} is not a valid file or directory",
              file=sys.stderr)
        sys.exit(2)

    # Filter by severity
    threshold = Severity[args.severity]
    issues = [i for i in issues if Severity[i.severity] <= threshold]

    report = generate_report(issues)

    output = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output} ({len(issues)} issues)",
              file=sys.stderr)
    else:
        print(output)

    # Exit code: 1 if any CRITICAL or HIGH issues
    has_serious = any(i.severity in ("CRITICAL", "HIGH") for i in issues)
    sys.exit(1 if has_serious else 0)


if __name__ == "__main__":
    main()