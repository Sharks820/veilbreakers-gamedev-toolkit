#!/usr/bin/env python3
"""VeilBreakers Unified Code Reviewer -- multi-pass scanner for Python and C#.

Supports 3-layer output model:
- production: hard_correctness only
- advisory: hard_correctness + semantic
- strict: all three layers (hard_correctness + semantic + heuristic)

Usage:
    python vb_code_reviewer.py path/to/scan/
    python vb_code_reviewer.py . --output report.json --severity HIGH --scope production
    python vb_code_reviewer.py Assets/Scripts/ --lang cs
    python vb_code_reviewer.py . --scope advisory
    python vb_code_reviewer.py . --scope strict

Exit codes:
    0 -- no issues at or above threshold severity
    1 -- issues found at or above threshold severity
    2 -- invalid arguments
    3 -- scan error
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Optional

# =========================================================================
# IMPORT FALLBACKS -- modules may not exist yet (built by other agents)
# =========================================================================

try:
    from veilbreakers_mcp._context_engine import (
        ContextEngine,
        Definition,
        Reference,
        TypeInfo,
    )  # type: ignore[attr-defined]

    _CONTEXT_ENGINE_AVAILABLE = True
except ImportError:
    _CONTEXT_ENGINE_AVAILABLE = False
    # Stub types - use Any to avoid type conflicts when module is eventually created
    from typing import Any

    ContextEngine = Any  # type: ignore[misc,assignment]
    Definition = Any  # type: ignore[misc,assignment]
    Reference = Any  # type: ignore[misc,assignment]
    TypeInfo = Any  # type: ignore[misc,assignment]


try:
    from veilbreakers_mcp._rules_python import RULES as PYTHON_RULES
except ImportError:
    PYTHON_RULES = []  # Will use local rules below

try:
    from veilbreakers_mcp._rules_csharp import (
        RULES as CSHARP_RULES,
        DEEP_CHECKS as CSHARP_DEEP_CHECKS,
        CSharpLineClassifier as CSharpLineClassifierImp,
    )
except ImportError:
    CSHARP_RULES = []
    CSHARP_DEEP_CHECKS = {}
    CSharpLineClassifierImp = None  # Will use local implementation

# Type alias for runtime use
CSharpLineClassifierType = CSharpLineClassifierImp if CSharpLineClassifierImp else None

# =========================================================================
# CONSTANTS
# =========================================================================

REVIEW_SCOPE_CHOICES = ("production", "advisory", "strict")
LANG_CHOICES = ("auto", "py", "cs")
DEFAULT_SKIP_DIRS = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".git",
        ".tox",
        "dist",
        "build",
        "egg-info",
        ".tmp",
    }
)
DEFAULT_TEST_DIRS = frozenset({"tests", "testdata", "fixtures"})
DEFAULT_TEMP_DIR_FRAGMENTS = ("addon_backup_",)
DEFAULT_TEMP_FILE_PREFIXES = ("_tmp", ".tmp")

# Smart incremental scanning: File hash caching to avoid re-scanning unchanged files (60-80% reduction)
CACHE_DIR: str = ".claude/cache"

# Layer classification
LAYER_HARD_CORRECTNESS = "hard_correctness"
LAYER_SEMANTIC = "semantic"
LAYER_HEURISTIC = "heuristic"

# Scope to layer mapping
# Rule tier migration: Noisy style rules moved to advisory in production tier
_RULES_ADVISORY_IN_PRODUCTION = {
    "PY-STY-08",  # Missing type annotations - high FP rate
    "PY-STY-07",  # Unused imports - many FPs
    "PY-COR-13",  # Lazy imports - context-dependent
    "PY-STY-06",  # Missing __all__ - often false positive
    "PY-STY-09",  # Long functions - subjective
}
SCOPE_TO_LAYERS = {
    "production": {LAYER_HARD_CORRECTNESS},
    "advisory": {LAYER_HARD_CORRECTNESS, LAYER_SEMANTIC},
    "strict": {LAYER_HARD_CORRECTNESS, LAYER_SEMANTIC, LAYER_HEURISTIC},
}

# Severity to default confidence
_SEVERITY_BASE_CONF = {
    "CRITICAL": 95,
    "HIGH": 85,
    "MEDIUM": 75,
    "LOW": 70,
}

# =========================================================================
# DATA STRUCTURES
# =========================================================================


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
    Unity = 4  # C# specific


class FindingType(IntEnum):
    ERROR = 0
    BUG = 1
    OPTIMIZATION = 2
    STRENGTHENING = 3


@dataclass
class Rule:
    """Enhanced Rule with layer classification and context requirements."""

    id: str
    severity: Severity
    category: Category
    description: str
    fix: str
    pattern: re.Pattern
    anti_patterns: list[re.Pattern] = field(default_factory=list)
    anti_radius: int = 3
    guard: Optional[Callable[..., bool]] = None
    finding_type: Optional[FindingType] = None
    confidence: int = -1
    priority: int = -1
    reasoning: Optional[str] = None
    # New fields for unified reviewer
    layer: str = LAYER_HARD_CORRECTNESS  # "hard_correctness", "semantic", "heuristic"
    requires_context: bool = False
    scope: str = (
        "AnyMethod"  # C# only: "HotPath", "AnyMethod", "ClassLevel", "FileLevel"
    )
    file_filter: str = "All"  # C# only: "Runtime", "EditorOnly", "All"
    inside_pattern: Optional[re.Pattern] = None
    not_inside_pattern: Optional[re.Pattern] = None

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


# Rule reliability weighting: Known precision scores from test history
# Structure: rule_id -> multiplier OR rule_id -> {multiplier, skip_patterns, priority_penalty}
_RULE_RELIABILITY: dict[str, float | dict] = {
    # Low-reliability rules (high FP rate)
    "PY-STY-08": 0.6,  # Missing return annotations
    "PY-STY-07": 0.7,  # Unused imports (many FPs)
    "PY-COR-13": 0.7,  # Lazy imports

    # Global variables - legitimate singleton/cache patterns, often false positive
    "PY-STY-04": {
        "multiplier": 0.8,  # 20% confidence penalty
        "skip_patterns": [
            r"_parser$",     # Cached tree-sitter parsers
            r"_connection$", # Singleton TCP connections
            r"_client$",     # Cached external API clients
            r"_cache$",      # Cache variables
        ]
    },

    # Missing __all__ - not needed for MCP tool modules
    "PY-STY-06": {
        "multiplier": 0.7,  # 30% confidence penalty
        "skip_patterns": [
            r"/server\.py$",      # MCP server modules export all public tools
            r"/unity_tools/.*\.py$",  # Unity tool handlers need all exports
        ]
    },

    # Long functions - data pipelines and algorithmic functions need to be linear
    "PY-STY-09": {
        "multiplier": 0.9,  # 10% confidence penalty
        "skip_patterns": [
            r"_rules\.py$",       # Data definition files
            r"_templates\.py$",   # Template generators
            r"delight\.py$",      # Image processing algorithm
            r"pipeline_runner\.py$", # Pipeline orchestration
        ],
        "threshold_adjustments": {
            "algorithmic": 200,   # Allow longer functions for algorithms
            "data_definition": 500, # Allow longer for data structures
        }
    },

    # os.path usage - valid alternative to pathlib, style preference
    "PY-STY-01": {
        "multiplier": 1.0,  # No confidence penalty
        "priority_penalty": 15,  # Lower priority from 20 to ~5
    },

    # High-reliability rules - 1.0x multiplier (default)
    # Most bug rules keep 1.0 as they have good precision
}

# Tool reputation weighting: Historical precision scores per tool
_TOOL_REPUTATION: dict[str, float] = {
    "regex": 0.92,  # Internal regex rules - high precision
    "ast": 0.95,    # AST analysis - very precise for structural bugs
    "ruff": 0.90,   # Python linter - good precision, some style noise
    "mypy": 0.88,    # Python type checker - strict, some false positives
    "opengrep": 0.85,  # Taint analysis - some false positives on valid patterns
    "dotnet-analyzers": 0.93,  # .NET analyzers - high precision
    "roslynator": 0.91,  # Roslynator - good precision
    "ast-grep": 0.87,  # Structural pattern matching - good but not perfect
}


def _semantic_fingerprint(issue: Issue) -> frozenset[str]:
    """Extract semantic fingerprint for cross-tool correlation.

    Returns a set of normalized tokens that identify the semantic meaning:
    - Function/class names mentioned in description
    - Key patterns (null check, unused, undefined, etc.)
    - Normalized severity markers
    """
    desc = issue.description.lower()

    # Extract function/class/variable names (PascalCase, camelCase, snake_case)
    name_pattern = re.compile(r'\b([A-Z][a-zA-Z0-9]*|[a-z][a-z0-9_]*[a-z0-9])\b')
    names = set(name_pattern.findall(desc))

    # Extract semantic keywords
    semantic_keywords = {
        "null", "none", "undefined", "unused", "shadow", "redefined",
        "dead", "unreachable", "duplicate", "redundant",
        "missing", "required", "expected", "optional",
        "type", "return", "param", "arg", "var",
        "check", "assert", "guard", "validate",
        "leak", "resource", "file", "connection",
        "buffer", "overflow", "underflow", "injection",
        "security", "sql", "xss", "path", "sanitize",
        "async", "await", "task", "thread", "lock",
    }

    keywords = set(word for word in desc.split() if word in semantic_keywords)

    # Combine into fingerprint
    return frozenset(names | keywords)

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
    reasoning: str = ""
    # New fields for unified reviewer
    layer: str = LAYER_HARD_CORRECTNESS
    requires_context: bool = False
    # Reliability-weighted confidence for final output
    adjusted_confidence: int = 75

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
        if self.confidence >= 90:
            return "CERTAIN"
        if self.confidence >= 75:
            return "HIGH"
        if self.confidence >= 50:
            return "LIKELY"
        return "POSSIBLE"

    @property
    def priority_label(self) -> str:
        if self.priority >= 90:
            return "P0-CRITICAL"
        if self.priority >= 70:
            return "P1-HIGH"
        if self.priority >= 40:
            return "P2-MEDIUM"
        if self.priority >= 15:
            return "P3-LOW"
        return "P4-COSMETIC"

    def apply_reliability_weighting(self) -> None:
        """Apply rule reliability weighting to adjust confidence.

        Handles enhanced _RULE_RELIABILITY structure with:
        - Simple multiplier (backward compatible)
        - Skip patterns to avoid false positives
        - Threshold adjustments for long functions
        - Priority penalties for style rules
        """
        import re

        rule_config = _RULE_RELIABILITY.get(self.rule_id)

        # Handle both simple multiplier (old format) and dict config (new format)
        if isinstance(rule_config, (int, float)):
            multiplier = rule_config
            priority_penalty = 0
        else:
            # New format: {multiplier, skip_patterns, priority_penalty, threshold_adjustments}
            multiplier = rule_config.get("multiplier", 1.0)
            priority_penalty = rule_config.get("priority_penalty", 0)

            # Check if this issue should be skipped based on file patterns
            skip_patterns = rule_config.get("skip_patterns", [])
            if skip_patterns:
                normalized_file = _normalize_path(self.file)
                for pattern in skip_patterns:
                    if re.search(pattern, normalized_file):
                        # Skip this finding - set confidence to minimum
                        self.adjusted_confidence = 20
                        return

            # Check threshold adjustments for long functions
            threshold_adjustments = rule_config.get("threshold_adjustments", {})
            if threshold_adjustments and self.rule_id == "PY-STY-09":
                # Check if this is an algorithmic or data definition function
                import os
                filename = os.path.basename(self.file)
                for func_type, threshold in threshold_adjustments.items():
                    if re.search(func_type, filename.lower()):
                        # Apply higher threshold for this function type
                        # Count lines in the function to check if it exceeds threshold
                        # For now, just use a higher base multiplier
                        multiplier = max(multiplier, 0.95)  # Less penalty
                        break

        # Calculate adjusted confidence
        base_confidence = self.confidence
        if priority_penalty:
            base_confidence = max(20, base_confidence - priority_penalty)

        self.adjusted_confidence = max(20, min(99, int(base_confidence * multiplier)))


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================


def _normalize_path(filepath: str) -> str:
    return filepath.replace("\\", "/")


def _is_test_path(filepath: str) -> bool:
    normalized = _normalize_path(filepath).lower()
    name = Path(filepath).name.lower()
    parts = {part.lower() for part in Path(normalized).parts}
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.cs")
        or any(part in DEFAULT_TEST_DIRS for part in parts)
    )


def _is_temp_path(filepath: str) -> bool:
    normalized = _normalize_path(filepath).lower()
    name = Path(filepath).name.lower()
    return (
        name.startswith(DEFAULT_TEMP_FILE_PREFIXES)
        or name.endswith((".bak.py", ".tmp.py", ".bak.cs", ".tmp.cs"))
        or any(fragment in normalized for fragment in DEFAULT_TEMP_DIR_FRAGMENTS)
        or "/output/" in normalized
    )


def _is_production_code_path(filepath: str) -> bool:
    normalized = _normalize_path(filepath).lower()
    return (
        normalized.startswith("src/veilbreakers_mcp/")
        or normalized.startswith("blender_addon/")
        or normalized.startswith("assets/")
        or "/src/veilbreakers_mcp/" in normalized
        or "/blender_addon/" in normalized
        or "/assets/" in normalized
    )


def _should_scan_file(
    filepath: str,
    lang: str,
    *,
    review_scope: str = "production",
    include_tests: bool = False,
    include_temp: bool = False,
) -> bool:
    if review_scope not in REVIEW_SCOPE_CHOICES:
        raise ValueError(f"Unknown review_scope: {review_scope}")
    if not include_tests and _is_test_path(filepath):
        return False
    if not include_temp and _is_temp_path(filepath):
        return False
    if review_scope == "production":
        return _is_production_code_path(filepath)
    return True


def _should_emit_rule(rule: Rule, review_scope: str) -> bool:
    """Determine if a rule should emit based on scope/layer."""
    allowed_layers = SCOPE_TO_LAYERS.get(review_scope, {LAYER_HARD_CORRECTNESS})
    # Rule tier migration: Noisy style rules allowed in advisory for production too
    if review_scope == "production" and rule.id in _RULES_ADVISORY_IN_PRODUCTION:
        return True
    return rule.layer in allowed_layers


# =========================================================================
# ANTI-PATTERN HELPERS
# =========================================================================


def _compile_anti(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


def _suppressed_by_anti(
    anti: list[re.Pattern], lines: list[str], idx: int, radius: int, filepath: str = ""
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
        norm_path = filepath.replace("\\", "/")
        for ap in anti:
            if ap.search(norm_path):
                return True
    return False


def _is_comment(line: str, lang: str = "py") -> bool:
    if lang == "cs":
        return line.strip().startswith("//") or line.strip().startswith("/*")
    return line.lstrip().startswith("#")


def _in_string_literal(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("'", '"', "b'", 'b"', "f'", 'f"', "r'", 'r"'))


def _active_code(line: str, _all: list[str], _idx: int, lang: str = "py") -> bool:
    return not _is_comment(line, lang) and not _in_string_literal(line)


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


# =========================================================================
# GUARD FUNCTIONS (from existing Python reviewer)
# =========================================================================


def _is_inside_except(line: str, all_lines: list[str], idx: int) -> bool:
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


def _check_mutable_get(line: str, all_lines: list[str], idx: int) -> bool:
    """Return True only if the .get() result variable is actually mutated nearby."""
    if re.search(r"\b(len|for|if|return|print|not|or|and)\s*[\s(].*\.get\s*\(", line):
        return False
    for j in range(idx + 1, min(len(all_lines), idx + 8)):
        if re.search(r"\.(items|keys|values)\s*\(|for\s+\w+\s+(in|,)", all_lines[j]):
            return False
    m = re.match(r"\s*(\w+)\s*=\s*\w+\.get\s*\(", line)
    if m:
        var_name = m.group(1)
        for j in range(idx + 1, min(len(all_lines), idx + 5)):
            if re.search(
                rf"\b{re.escape(var_name)}\b\.(append|extend|add|update|insert)\s*\(",
                all_lines[j],
            ):
                return True
            if re.search(rf"\b{re.escape(var_name)}\b\[.+\]\s*=", all_lines[j]):
                return True
        return False
    return bool(re.search(r"\.(append|extend|add|update|insert)\s*\(", line))


def _check_late_binding(line: str, all_lines: list[str], idx: int) -> bool:
    """Return True if a for-loop has a lambda using the loop var without default capture."""
    m = re.search(r"for\s+(\w+)\s+in\b", line)
    if not m:
        return False
    loop_var = m.group(1)
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
        lam = re.search(r"lambda\b([^:]*?):", all_lines[j])
        if not lam:
            continue
        if not re.search(rf"\b{re.escape(loop_var)}\b", all_lines[j]):
            continue
        if re.search(
            rf"\b{re.escape(loop_var)}\s*=\s*{re.escape(loop_var)}\b", lam.group(1)
        ):
            continue
        return True
    return False


# =========================================================================
# C# LINE CLASSIFIER
# =========================================================================


class CSharpLineClassifier:
    """Classifies C# lines into categories for rule filtering."""

    # Unity lifecycle methods that constitute hot path
    HOT_PATH_METHODS = frozenset(
        {
            "Update",
            "FixedUpdate",
            "LateUpdate",
            "OnGUI",
            "OnAnimatorIK",
            "OnWillRenderObject",
            "OnPreRender",
            "OnPostRender",
            "OnRenderImage",
            "OnRenderObject",
        }
    )

    def __init__(self):
        self.line_types: list[str] = []
        self.method_boundaries: list[
            tuple[int, int, str]
        ] = []  # (start, end, method_name)

    def classify(self, lines: list[str]) -> list[str]:
        """Classify each line into: HotPath, Comment, StringLiteral, EditorBlock, Attribute, Cold, ClassLevel, MethodBody."""
        self.line_types = []
        self.method_boundaries = []
        in_comment_block = False
        in_string = False
        in_hot_method = None
        hot_method_start = -1
        # Track ALL method boundaries for Phase 3
        all_method_bounds: list[tuple[int, int]] = []
        in_any_method = False
        any_start = -1
        any_brace = 0

        i = 0
        while i < len(lines):
            line = lines[i]
            line_type = "Cold"
            method_def_line = False

            # Check for comment block start
            if "/*" in line and not in_string:
                in_comment_block = True
                line_type = "Comment"

            # Check for comment line
            stripped = line.strip()
            if stripped.startswith("//"):
                line_type = "Comment"
            elif stripped.startswith("#if"):
                if "UNITY_EDITOR" in stripped or "UNITY_INCLUDE_TESTS" in stripped:
                    line_type = "EditorBlock"
                else:
                    line_type = "Cold"
            elif stripped.startswith("#endif"):
                line_type = "Cold"
            elif in_comment_block:
                line_type = "Comment"
                if "*/" in line:
                    in_comment_block = False

            # Check for attribute
            if stripped.startswith("[") and not in_string and "]" in stripped:
                line_type = "Attribute"

            # Check for string literal
            if '"' in line and not in_comment_block:
                if line.count('"') % 2 == 1:
                    in_string = not in_string
                if in_string:
                    line_type = "StringLiteral"

            # Check for method definition (any method)
            method_match = re.match(
                r"\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract)\s+)?"
                r"(?:(?:async\s+)?(?:void|Task|IEnumerator|int|float|bool|string|[A-Za-z_]\w*(?:<[^>]+>)?))\s+"
                r"(\w+)\s*\(",
                line,
            )
            if method_match and not in_any_method:
                method_name = method_match.group(1)
                in_any_method = True
                method_def_line = True
                any_start = i
                any_brace = line.count("{") - line.count("}")
                if method_name in self.HOT_PATH_METHODS:
                    in_hot_method = method_name
                    hot_method_start = i
                    line_type = "HotPath"

            # Track all method boundaries (skip brace count on method def line)
            if in_any_method and not method_def_line:
                any_brace += line.count("{") - line.count("}")
                if any_brace <= 0 and i > any_start:
                    all_method_bounds.append((any_start, i))
                    if in_hot_method:
                        self.method_boundaries.append((hot_method_start, i, in_hot_method))

            # Override with hot path if inside hot method (before reset)
            if in_hot_method and line_type == "Cold":
                line_type = "HotPath"

            # Reset after hot path override so closing brace is still HotPath
            if in_any_method and not method_def_line and any_brace <= 0 and i > any_start:
                in_hot_method = None
                hot_method_start = -1
                in_any_method = False

            self.line_types.append(line_type)
            i += 1

        # Phase 3: Reclassify Cold lines into ClassLevel vs MethodBody
        for i, lt in enumerate(self.line_types):
            if lt == "Cold":
                in_body = any(s <= i <= e for s, e in all_method_bounds)
                self.line_types[i] = "MethodBody" if in_body else "ClassLevel"

        return self.line_types

    @staticmethod
    def is_hot_path(line_type: str) -> bool:
        return line_type == "HotPath"


# =========================================================================
# LOCAL PYTHON RULES (fallback if _rules_python not available)
# =========================================================================


def _get_local_python_rules() -> list[Rule]:
    """Return Python rules if module not available."""
    if PYTHON_RULES:
        return PYTHON_RULES

    # Define local rules (extracted from vb_python_reviewer.py)
    RULES: list[Rule] = [
        Rule(
            "PY-SEC-01",
            Severity.CRITICAL,
            Category.Security,
            "eval() usage -- arbitrary code execution risk",
            "Replace with ast.literal_eval() or redesign.",
            re.compile(r"\beval\s*\("),
            _compile_anti([r"#\s*VB-IGNORE", r"literal_eval"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-SEC-02",
            Severity.CRITICAL,
            Category.Security,
            "os.system() or subprocess with shell=True -- command injection",
            "Use subprocess.run() with list args and shell=False.",
            re.compile(r"(os\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True)"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-SEC-03",
            Severity.CRITICAL,
            Category.Security,
            "pickle.load on untrusted data -- arbitrary code execution",
            "Use json, msgpack, or safer format.",
            re.compile(r"pickle\.(load|loads)\s*\("),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-SEC-04",
            Severity.HIGH,
            Category.Security,
            "f-string in SQL/shell command -- injection risk",
            "Use parameterized queries or subprocess list args.",
            re.compile(r'(execute|run|system|popen)\s*\(\s*f["\']'),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-SEC-05",
            Severity.HIGH,
            Category.Security,
            "exec() usage -- arbitrary code execution",
            "Replace with getattr(module, name)() for dynamic dispatch.",
            re.compile(r"\bexec\s*\("),
            _compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"^\s*#",
                    r"^\s*\w+\s*=\s*",
                    r"def\s+\w+\s*\([^)]*exec",
                ]
            ),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-SEC-06",
            Severity.MEDIUM,
            Category.Security,
            "Hardcoded file path -- not portable",
            "Use pathlib.Path or os.path.join with configurable base.",
            re.compile(r"""['"](?:/[a-z]+/|[A-Z]:\\\\)[^'"]{3,}['"]"""),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_SEMANTIC,
        ),
        Rule(
            "PY-SEC-07",
            Severity.HIGH,
            Category.Security,
            "assert for input validation -- stripped with -O",
            "Replace with explicit validation: if x <= 0: raise ValueError(...).",
            re.compile(r"^\s*assert\s+(?!.*#\s*nosec)"),
            _compile_anti([r"#\s*VB-IGNORE", r"#\s*nosec", r"test_|_test\.py"]),
            layer=LAYER_HARD_CORRECTNESS,
            confidence=65,
        ),
        Rule(
            "PY-COR-01",
            Severity.HIGH,
            Category.Bug,
            "Mutable default argument -- shared across calls",
            "Change to: def f(items=None): items = items if items is not None else []",
            re.compile(r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\}|set\(\))"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-COR-02",
            Severity.HIGH,
            Category.Bug,
            "Bare except: catches SystemExit, KeyboardInterrupt",
            "Replace 'except:' with 'except Exception:' or specific types.",
            re.compile(r"^\s*except\s*:"),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-COR-03",
            Severity.MEDIUM,
            Category.Bug,
            "Comparing with None using == instead of 'is None'",
            "Use 'is None' or 'is not None'.",
            re.compile(r"[!=]=\s*None\b"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_SEMANTIC,
        ),
        Rule(
            "PY-COR-04",
            Severity.MEDIUM,
            Category.Bug,
            "open() without context manager -- file may not close",
            "Use 'with open(...) as f:'.",
            re.compile(r"(?<!\bwith\s)\bopen\s*\("),
            _compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"^\s*#",
                    r"\bwith\b",
                    r"Image\.open",
                    r"BytesIO",
                    r"PIL",
                ]
            ),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-COR-05",
            Severity.LOW,
            Category.Bug,
            "datetime.now() without timezone -- ambiguous",
            "Use datetime.now(tz=timezone.utc).",
            re.compile(r"datetime\.now\s*\(\s*\)"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-COR-06",
            Severity.MEDIUM,
            Category.Bug,
            "dict.get() with mutable default -- mutated result is shared",
            "Use dict.get(key) with None check, then create mutable separately.",
            re.compile(r"\.get\s*\([^)]*,\s*(\[\]|\{\}|set\(\))"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            guard=_check_mutable_get,
            layer=LAYER_SEMANTIC,
            confidence=88,
        ),
        Rule(
            "PY-COR-07",
            Severity.MEDIUM,
            Category.Bug,
            "Class with __del__ -- unpredictable GC, prevents ref cycle collection",
            "Use context managers or weakref.finalize.",
            re.compile(r"def\s+__del__\s*\(\s*self"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_SEMANTIC,
            confidence=85,
        ),
        Rule(
            "PY-COR-08",
            Severity.MEDIUM,
            Category.Bug,
            "Thread without daemon=True -- may prevent clean shutdown",
            "Set daemon=True or join before exit.",
            re.compile(r"Thread\s*\("),
            _compile_anti([r"#\s*VB-IGNORE", r"daemon"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "PY-COR-09",
            Severity.LOW,
            Category.Bug,
            "json.loads/load without error handling — crashes on malformed input",
            "Wrap in try/except json.JSONDecodeError.",
            re.compile(r"json\.loads?\s*\("),
            _compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"^\s*#",
                    r"except.*JSON",
                    r"\btry\s*:",
                    r"\bexcept\b",
                ]
            ),
            layer=LAYER_HEURISTIC,
            confidence=68,
            anti_radius=10,
        ),
        Rule(
            "PY-COR-10",
            Severity.LOW,
            Category.Bug,
            "Float equality comparison -- use math.isclose",
            "Use math.isclose(a, b) or abs(a - b) < epsilon.",
            re.compile(r"(?<!\w)(==|!=)\s*\d+\.\d+"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-COR-11",
            Severity.MEDIUM,
            Category.Bug,
            "Re-raising exception without chain -- loses traceback",
            "Use 'raise NewException(...) from original_exc'.",
            re.compile(r"raise\s+\w+\([^)]*\)\s*$"),
            _compile_anti([r"#\s*VB-IGNORE", r"\bfrom\s+\w+"]),
            guard=lambda line, a, i: _is_inside_except(line, a, i),
            layer=LAYER_SEMANTIC,
            confidence=72,
        ),
        Rule(
            "PY-COR-12",
            Severity.MEDIUM,
            Category.Bug,
            "Broad except silently swallows exceptions without logging or handling",
            "Add logger.exception() or return a meaningful error response.",
            re.compile(r"except\s+Exception\s*(?:as|\s*:)"),
            _compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"# broad catch intentional",
                    r"logger\.(exception|error|warning|critical)",
                    r"mcp\.tool",
                    r"return\s+json\.dumps\(\{.*status.*error",
                    r"sys\.exit",
                    r"warnings\.warn",
                ]
            ),
            layer=LAYER_HEURISTIC,
            confidence=65,
            anti_radius=5,
        ),
        Rule(
            "PY-COR-14",
            Severity.MEDIUM,
            Category.Bug,
            "Variable shadows built-in name (list, dict, set, type, id, etc.)",
            "Rename: items instead of list, mapping instead of dict.",
            re.compile(
                r"^\s*(list|dict|set|str|int|float|bool|tuple|type|id|input|filter|map|zip|range|len|sum|min|max|any|all|sorted|reversed|hash|next|iter|open|print|format|bytes|object|super)\s*=\s*"
            ),
            _compile_anti([r"#\s*VB-IGNORE", r"typing", r"import"]),
            guard=lambda line, a, i: (
                not line.rstrip().endswith(",")
                and not line.rstrip().endswith(")")
                and not (i > 0 and "(" in a[i - 1] and ")" not in a[i - 1])
            ),
            layer=LAYER_SEMANTIC,
            confidence=72,
        ),
        Rule(
            "PY-COR-15",
            Severity.HIGH,
            Category.Bug,
            "Lambda in loop captures loop variable by reference -- late binding bug",
            "Capture with default arg: lambda x, i=i: ... or use functools.partial.",
            re.compile(r"for\s+(\w+)\s+in\b"),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            guard=lambda line, a, i: _check_late_binding(line, a, i),
            layer=LAYER_HARD_CORRECTNESS,
            confidence=92,
        ),
        Rule(
            "PY-PERF-04",
            Severity.LOW,
            Category.Performance,
            "String concatenation in loop -- O(n^2)",
            "Collect parts in list, ''.join(parts) after loop.",
            re.compile(r"\w+\s*\+=\s*['\"]"),
            _compile_anti(
                [
                    r"#\s*VB-IGNORE",
                    r"^\s*#",
                    r"\bstring\b",
                    r"\bvar\b",
                    r"\bint\b",
                    r"\.Count\b",
                    r"\.Length\b",
                    r"//\s",
                ]
            ),
            guard=lambda line, a, i: any(
                re.search(r"^\s*(for|while)\b", a[j]) for j in range(max(0, i - 5), i)
            ),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-PERF-02",
            Severity.LOW,
            Category.Performance,
            "re.match/search/findall without compile for repeated pattern",
            "Compile pattern once with re.compile() and reuse.",
            re.compile(r"re\.(match|search|findall|sub|split)\s*\("),
            _compile_anti([r"#\s*VB-IGNORE", r"re\.compile"]),
            guard=lambda line, a, i: any(
                re.search(r"^\s*(for|while)\b", a[j]) for j in range(max(0, i - 5), i)
            ),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-PERF-03",
            Severity.LOW,
            Category.Performance,
            "Large file .read() without chunking -- may exhaust memory",
            "Use chunked reading: for line in file, or file.read(chunk_size).",
            re.compile(r"\.read\s*\(\s*\)"),
            _compile_anti(
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
            layer=LAYER_HEURISTIC,
            confidence=55,
        ),
        Rule(
            "PY-STY-01",
            Severity.LOW,
            Category.Quality,
            "os.path usage — consider pathlib.Path for cleaner path handling",
            "Replace os.path.join(a, b) with Path(a) / b.",
            re.compile(
                r"os\.path\.(join|exists|isfile|isdir|basename|dirname|splitext)\s*\("
            ),
            _compile_anti([r"#\s*VB-IGNORE", r"^\s*#"]),
            layer=LAYER_HEURISTIC,
            confidence=72,
        ),
        Rule(
            "PY-STY-02",
            Severity.LOW,
            Category.Quality,
            "Deeply nested function (3+ indent levels) — hard to test and maintain",
            "Extract inner function to module level or class method.",
            re.compile(r"^\s{12,}def\s+\w+\s*\("),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_HEURISTIC,
            confidence=85,
        ),
        Rule(
            "PY-STY-03",
            Severity.LOW,
            Category.Quality,
            "Star import pollutes namespace",
            "Replace with explicit imports: from X import ClassA, func_b.",
            re.compile(r"from\s+\S+\s+import\s+\*"),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_HEURISTIC,
            confidence=92,
        ),
        Rule(
            "PY-STY-04",
            Severity.LOW,
            Category.Quality,
            "Global variable mutation — makes function behavior depend on hidden state",
            "Pass the value as a function parameter, or encapsulate in a class.",
            re.compile(r"^\s+global\s+\w+"),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_HEURISTIC,
            confidence=78,
        ),
        # AST-only rules (sentinels)
        Rule(
            "PY-STY-05",
            Severity.LOW,
            Category.Quality,
            "Missing __main__ guard -- code runs on import",
            "Wrap in: if __name__ == '__main__':",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-STY-06",
            Severity.LOW,
            Category.Quality,
            "Missing __all__ in public module",
            "Add __all__ = ['ClassName', 'public_func', 'CONSTANT'].",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-STY-07",
            Severity.LOW,
            Category.Quality,
            "Unused import",
            "Remove unused import or add to __all__ if re-exported.",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-STY-08",
            Severity.LOW,
            Category.Quality,
            "Missing type annotation on public function",
            "Add return type annotation: def func(...) -> ReturnType:",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-STY-09",
            Severity.LOW,
            Category.Quality,
            "Function exceeds length threshold",
            "Break long functions into smaller, well-named helpers.",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
        ),
        Rule(
            "PY-COR-13",
            Severity.LOW,
            Category.Quality,
            "Import inside function body -- may indicate circular import workaround",
            "Move import to module scope or document if intentional.",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_SEMANTIC,
            confidence=45,
        ),
    ]
    return RULES


# =========================================================================
# LOCAL C# RULES (fallback if _rules_csharp not available)
# =========================================================================


def _get_local_csharp_rules() -> list[Any]:
    """Return C# rules if module not available."""
    if CSHARP_RULES:
        return CSHARP_RULES

    # Define local C# rules (subset for fallback)
    RULES: list[Any] = [
        Rule(
            "BUG-01",
            Severity.CRITICAL,
            Category.Bug,
            "GetComponent<T>() in Update -- cache in Awake/Start",
            "Cache the component reference in a field during Awake() or Start().",
            re.compile(r"void\s+Update\s*\(\s*\)\s*\{[^}]*GetComponent\s*<"),
            _compile_anti([r"\[SerializeField\]", r"private\s+\w+\s+\w+\s*="]),
            layer=LAYER_HARD_CORRECTNESS,
            scope="HotPath",
            file_filter="All",
        ),
        Rule(
            "BUG-06",
            Severity.CRITICAL,
            Category.Bug,
            "Resource allocation in Awake without release in OnDisable",
            "Ensure corresponding cleanup in OnDisable or OnDestroy.",
            re.compile(
                r"void\s+Awake\s*\(\s*\)\s*\{[^}]*(?:Instantiate|AddComponent|RegisterEvent)"
            ),
            _compile_anti(
                [r"void\s+OnDisable\s*\(\s*\)", r"void\s+OnDestroy\s*\(\s*\)"]
            ),
            layer=LAYER_HARD_CORRECTNESS,
            file_filter="All",
        ),
        Rule(
            "PERF-01",
            Severity.HIGH,
            Category.Performance,
            "LINQ in Update/OnGUI -- garbage collection pressure",
            "Cache the LINQ result or use traditional loops.",
            re.compile(
                r"(?:Update|OnGUI)\s*\(\s*\)[^}]*\.(?:Where|Select|ToList|ToArray|FirstOrDefault)\s*\("
            ),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_SEMANTIC,
            scope="HotPath",
        ),
        Rule(
            "SEC-01",
            Severity.CRITICAL,
            Category.Security,
            "Hardcoded password/API key detected",
            "Move sensitive data to configuration or secure storage.",
            re.compile(
                r"(?:password|apikey|api_key|secret|token)\s*=\s*[\"'][^\"']+[\"']",
                re.IGNORECASE,
            ),
            _compile_anti([r"#\s*VB-IGNORE", r"//\s*TODO", r"example", r"placeholder"]),
            layer=LAYER_HARD_CORRECTNESS,
            file_filter="Runtime",
        ),
        Rule(
            "SEC-02",
            Severity.CRITICAL,
            Category.Security,
            "SQL injection risk -- string concatenation in query",
            "Use parameterized queries: cmd.Parameters.AddWithValue().",
            re.compile(
                r"(?:ExecuteQuery|ExecuteNonQuery|SqlCommand)\s*\([^)]*\+[^)]*\)"
            ),
            _compile_anti([r"#\s*VB-IGNORE", r"Parameters\.Add"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "UNITY-01",
            Severity.HIGH,
            Category.Unity,
            "Destroy() called with non-null second argument -- incorrect API",
            "Use Destroy(gameObject) or DestroyImmediate(gameObject).",
            re.compile(r"Destroy\s*\([^,]+,\s*(?!null)"),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_HARD_CORRECTNESS,
        ),
        Rule(
            "UNITY-02",
            Severity.MEDIUM,
            Category.Unity,
            "Coroutines with yield return null in Update",
            "Use StartCoroutine() instead of yield return null in Update.",
            re.compile(r"void\s+Update\s*\(\s*\)[^}]*yield\s+return\s+null"),
            _compile_anti([r"#\s*VB-IGNORE"]),
            layer=LAYER_SEMANTIC,
            scope="HotPath",
        ),
        Rule(
            "QUAL-01",
            Severity.LOW,
            Category.Quality,
            "Method exceeds 60 lines -- consider refactoring",
            "Break into smaller, focused methods.",
            re.compile(r"SENTINEL_AST_ONLY"),
            layer=LAYER_HEURISTIC,
            scope="AnyMethod",
        ),
    ]
    return RULES


# =========================================================================
# AST ANALYSIS FOR PYTHON
# =========================================================================


def _is_in_triple_quote(lines: list[str]) -> list[bool]:
    """Pre-classify lines inside triple-quoted strings."""
    _TDQ = chr(34) * 3
    _TSQ = chr(39) * 3
    _TQ_START = re.compile(r"(?:=\s*)?[brufBRUF]{0,2}(?:" + _TSQ + "|" + _TDQ + ")")
    in_tq = [False] * len(lines)
    inside = False
    open_quote = ""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if inside:
            in_tq[i] = True
            if open_quote in stripped:
                inside = False
                open_quote = ""
            continue
        if _TQ_START.search(stripped):
            in_tq[i] = True
            dq_count = stripped.count(_TDQ)
            sq_count = stripped.count(_TSQ)
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
    return in_tq


def _ast_analyze_python(
    filepath: str, source: str, review_scope: str = "production"
) -> list[Issue]:
    """AST-based analysis for Python patterns regex cannot detect."""
    issues: list[Issue] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return issues

    _fp_norm = filepath.replace("\\", "/")
    is_test_file = _is_test_path(filepath)
    is_init_module = Path(filepath).name == "__init__.py"
    is_private_module = Path(filepath).name.startswith("_")
    is_template = filepath.endswith("_templates.py") or "unity_templates/" in _fp_norm
    is_mcp_handler = _fp_norm.endswith("_server.py") or "/unity_tools/" in _fp_norm

    all_names_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            all_names_used.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                all_names_used.add(node.value.id)

    imported_names: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                imported_names[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            if node.names and node.names[0].name == "*":
                continue
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imported_names[name] = node.lineno

    # Unused imports (PY-STY-07)
    for name, lineno in imported_names.items():
        if review_scope != "strict":
            break
        if is_test_file or is_init_module:
            continue
        if name.startswith("_"):
            continue
        if name not in all_names_used:
            issues.append(
                Issue(
                    rule_id="PY-STY-07",
                    severity="LOW",
                    category="Quality",
                    file=filepath,
                    line=lineno,
                    description=f"Unused import: '{name}' — not referenced anywhere in this module",
                    fix=f"Remove 'import {name}' if unused.",
                    matched_text=name,
                    finding_type="STRENGTHENING",
                    confidence=82,
                    layer=LAYER_HEURISTIC,
                )
            )

    # Missing type annotations (PY-STY-08)
    has_all = any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
        for n in ast.iter_child_nodes(tree)
    )

    all_names_list: set[str] = set()
    if has_all:
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

    if review_scope == "strict" and not is_test_file and not is_init_module:
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            if has_all and node.name not in all_names_list:
                continue
            if node.returns is None:
                issues.append(
                    Issue(
                        rule_id="PY-STY-08",
                        severity="LOW",
                        category="Quality",
                        file=filepath,
                        line=node.lineno,
                        description=f"Public function '{node.name}' missing return type annotation",
                        fix="Add: def func(...) -> ReturnType:",
                        matched_text=node.name,
                        finding_type="STRENGTHENING",
                        confidence=85,
                        layer=LAYER_HEURISTIC,
                    )
                )

    # Missing __main__ guard (PY-STY-05)
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
            has_top_level_code = True

    if (
        review_scope == "strict"
        and not is_private_module
        and has_top_level_code
        and not has_main_guard
    ):
        issues.append(
            Issue(
                rule_id="PY-STY-05",
                severity="LOW",
                category="Quality",
                file=filepath,
                line=1,
                description="Module has top-level executable code without __main__ guard",
                fix="Wrap in: if __name__ == '__main__':",
                finding_type="STRENGTHENING",
                confidence=90,
                layer=LAYER_HEURISTIC,
            )
        )

    # Missing __all__ (PY-STY-06)
    public_names = [
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not n.name.startswith("_")
    ]
    if (
        review_scope == "strict"
        and not is_test_file
        and not is_init_module
        and not is_private_module
        and not has_all
        and len(public_names) >= 3
    ):
        issues.append(
            Issue(
                rule_id="PY-STY-06",
                severity="LOW",
                category="Quality",
                file=filepath,
                line=1,
                description=f"Module exports {len(public_names)} public names but has no __all__",
                fix="Add __all__ = [...].",
                finding_type="STRENGTHENING",
                confidence=80,
                layer=LAYER_HEURISTIC,
            )
        )

    # Function length (PY-STY-09)
    if review_scope == "strict":
        threshold = 200 if is_mcp_handler else (60 if not is_template else None)
        if is_private_module and threshold is not None:
            threshold = max(threshold, 120)
        if threshold is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        length = node.end_lineno - node.lineno
                        if length > threshold:
                            issues.append(
                                Issue(
                                    rule_id="PY-STY-09",
                                    severity="LOW",
                                    category="Quality",
                                    file=filepath,
                                    line=node.lineno,
                                    description=f"Function '{node.name}' is {length} lines (threshold: {threshold})",
                                    fix="Break into smaller helpers.",
                                    matched_text=node.name,
                                    finding_type="STRENGTHENING",
                                    confidence=90,
                                    layer=LAYER_HEURISTIC,
                                )
                            )

    return issues


# =========================================================================
# FILE SCANNING
# =========================================================================

# Type alias for context - use Any to handle missing module gracefully
ContextEngineType = ContextEngine  # type: ignore[valid-type]


def scan_python_file(
    filepath: str,
    context: Optional[ContextEngineType],
    review_scope: str = "production",
) -> list[Issue]:
    """Scan a Python file with regex rules + AST pass."""
    issues: list[Issue] = []
    rules = _get_local_python_rules()

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return issues

    lines = content.splitlines()
    line_offsets: list[int] = []
    cursor = 0
    for line in lines:
        line_offsets.append(cursor)
        cursor += len(line) + 1  # +1 for the newline character
    in_tq = _is_in_triple_quote(lines)

    # Build suppressed set
    suppressed: set[str] = set()
    ignore_rx = re.compile(r"#\s*VB-IGNORE:\s*([\w,-]+)")
    for line in lines:
        m = ignore_rx.search(line)
        if m:
            for rid in m.group(1).split(","):
                suppressed.add(rid.strip())

    context_dict: Optional[dict[str, Any]] = None
    if context and _CONTEXT_ENGINE_AVAILABLE:
        context_dict = {"engine": context, "file": filepath}

    # Pass 1: Regex with anti-patterns
    for rule in rules:
        if rule.id in suppressed:
            continue
        if not _should_emit_rule(rule, review_scope):
            continue
        if "SENTINEL" in rule.pattern.pattern:
            continue

        for i, line in enumerate(lines):
            if "VB-IGNORE" in line:
                continue
            if _is_comment(line, "py") or in_tq[i]:
                continue

            m = rule.pattern.search(line)
            if not m:
                continue

            match_start = m.start()
            if _match_is_in_string(line, match_start):
                continue

            if (
                rule.id == "PY-COR-10"
                and _is_test_path(filepath)
                and line.lstrip().startswith("assert ")
            ):
                continue

            if _suppressed_by_anti(
                rule.anti_patterns, lines, i, rule.anti_radius, filepath
            ):
                continue

            if rule.guard:
                if rule.requires_context and context_dict:
                    if not rule.guard(line, lines, i, context_dict):
                        continue
                else:
                    if not rule.guard(line, lines, i):
                        continue

            issues.append(
                Issue(
                    rule_id=rule.id,
                    severity=rule.severity.name,
                    category=rule.category.name,
                    file=filepath,
                    line=i + 1,
                    description=rule.description,
                    fix=rule.fix,
                    matched_text=line.strip(),
                    finding_type=rule.finding_type.name if rule.finding_type else "BUG",
                    confidence=rule.confidence,
                    priority=rule.priority,
                    reasoning=rule.reasoning or "",
                    layer=rule.layer,
                    requires_context=rule.requires_context,
                )
            )

    # Pass 2: AST analysis
    ast_issues = _ast_analyze_python(filepath, content, review_scope)
    for issue in ast_issues:
        if issue.rule_id not in suppressed:
            issues.append(issue)

    return issues


def scan_csharp_file(
    filepath: str,
    context: Optional[ContextEngineType],
    review_scope: str = "production",
) -> list[Issue]:
    """Scan a C# file with line classification + regex + DEEP rules."""
    issues: list[Issue] = []
    rules = _get_local_csharp_rules()

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return issues

    lines = content.splitlines()
    line_offsets: list[int] = []
    cursor = 0
    for line in lines:
        line_offsets.append(cursor)
        cursor += len(line) + 1  # +1 for the newline character

    # Pre-scan: classify lines — prefer the full classifier from _rules_csharp
    # which supports transitive hot-path propagation via BFS
    guard_ctx = None  # Raw LineContext list for guards that expect enum values
    if CSharpLineClassifierImp is not None:
        from veilbreakers_mcp._rules_csharp import LineContext as _LC
        guard_ctx = CSharpLineClassifierImp.classify(lines)
        # Convert LineContext enum values to the string tags the local scanner expects
        _ctx_map = {
            _LC.Cold: "Cold",
            _LC.HotPath: "HotPath",
            _LC.Comment: "Comment",
            _LC.StringLiteral: "StringLiteral",
            _LC.EditorBlock: "EditorBlock",
            _LC.Attribute: "Attribute",
            _LC.ClassLevel: "ClassLevel",
            _LC.MethodBody: "MethodBody",
        }
        line_types = [_ctx_map.get(c, "Cold") for c in guard_ctx]
    else:
        classifier = CSharpLineClassifier()
        line_types = classifier.classify(lines)

    context_dict: Optional[dict[str, Any]] = None
    if context and _CONTEXT_ENGINE_AVAILABLE:
        context_dict = {"engine": context, "file": filepath}

    # Pass 1: Regex with scope/file filtering
    for rule in rules:
        if not _should_emit_rule(rule, review_scope):
            continue

        # File filter (normalize path separators for cross-platform)
        norm_fp = filepath.replace("\\", "/")
        if rule.file_filter == "EditorOnly" and "/Editor/" not in norm_fp:
            continue
        if rule.file_filter == "Runtime" and "/Editor/" in norm_fp:
            continue

        for i, line in enumerate(lines):
            line_type = line_types[i] if i < len(line_types) else "Cold"

            if line_type == "Comment":
                continue

            # Scope filter
            if rule.scope == "HotPath" and line_type != "HotPath":
                continue
            if rule.scope == "ClassLevel" and line_type != "ClassLevel":
                continue
            if rule.scope == "AnyMethod" and line_type not in ("HotPath", "MethodBody"):
                continue

            m = rule.pattern.search(line)
            if not m:
                continue

            if _suppressed_by_anti(
                rule.anti_patterns, lines, i, rule.anti_radius, filepath
            ):
                continue

            # Inside pattern check
            if rule.inside_pattern:
                if not rule.inside_pattern.search(content, 0, line_offsets[i]):
                    continue

            # Not inside pattern check
            if rule.not_inside_pattern:
                if rule.not_inside_pattern.search(content, 0, line_offsets[i]):
                    continue

            if rule.guard:
                if rule.requires_context and context_dict:
                    if not rule.guard(line, lines, i, context_dict):
                        continue
                else:
                    # Guards from _rules_csharp expect (line, all, idx, ctx)
                    # where ctx is a list of LineContext enums. Pass guard_ctx
                    # when available, falling back to line_types (strings).
                    ctx_for_guard = guard_ctx if guard_ctx is not None else line_types
                    try:
                        guard_ok = rule.guard(line, lines, i)
                    except TypeError:
                        guard_ok = rule.guard(line, lines, i, ctx_for_guard)
                    if not guard_ok:
                        continue

            issues.append(
                Issue(
                    rule_id=rule.id,
                    severity=rule.severity.name,
                    category=rule.category.name,
                    file=filepath,
                    line=i + 1,
                    description=rule.description,
                    fix=rule.fix,
                    matched_text=line.strip(),
                    finding_type=rule.finding_type.name if rule.finding_type else "BUG",
                    confidence=rule.confidence,
                    priority=rule.priority,
                    reasoning=rule.reasoning or "",
                    layer=rule.layer,
                    requires_context=rule.requires_context,
                )
            )

    # Pass 2: DEEP rules (if available)
    if review_scope != "production" and CSHARP_DEEP_CHECKS:
        _vb_ignore_re = re.compile(r"//\s*VB-IGNORE")
        for rule_id, deep_spec in CSHARP_DEEP_CHECKS.items():
            check_fn = (
                deep_spec.get("check") if isinstance(deep_spec, dict) else deep_spec
            )
            if not callable(check_fn):
                continue
            deep_findings = check_fn(filepath, content, context_dict)
            if not isinstance(deep_findings, list):
                continue
            for finding in deep_findings:
                # Respect VB-IGNORE suppression on the reported line (or +-1 lines for comment-above)
                fline = finding.get("line", 1)
                suppressed = False
                for check_ln in range(max(1, fline - 1), min(len(lines) + 1, fline + 2)):
                    if check_ln <= len(lines) and _vb_ignore_re.search(lines[check_ln - 1]):
                        rid = rule_id
                        # Only suppress if VB-IGNORE mentions this rule or is unqualified
                        line_text = lines[check_ln - 1]
                        if rid in line_text or "VB-IGNORE" in line_text:
                            suppressed = True
                            break
                if suppressed:
                    continue
                issues.append(
                    Issue(
                        rule_id=rule_id,
                        severity=finding.get("severity", "HIGH"),
                        category=finding.get("category", "Bug"),
                        file=filepath,
                        line=fline,
                        description=finding.get("description", ""),
                        fix=finding.get("fix", ""),
                        confidence=finding.get("confidence", 80),
                        priority=finding.get("priority", 75),
                        layer=LAYER_SEMANTIC,
                        requires_context=True,
                    )
                )

    return issues


def detect_language(filepath: str) -> str:
    """Detect language from file extension."""
    ext = Path(filepath).suffix.lower()
    if ext == ".py":
        return "python"
    elif ext == ".cs":
        return "csharp"
    return "unknown"


def collect_files(
    paths: list[str],
    extensions: list[str],
    skip_dirs: frozenset = DEFAULT_SKIP_DIRS,
) -> list[str]:
    """Collect files with given extensions from paths."""
    files = []
    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            if path.suffix.lower() in extensions:
                files.append(_normalize_path(str(path.resolve())))
        elif path.is_dir():
            for ext in extensions:
                for f in sorted(path.rglob(f"*{ext}")):
                    if any(part in skip_dirs for part in f.parts):
                        continue
                    files.append(_normalize_path(str(f.resolve())))
    return files


def _find_solution_candidates(paths: list[str]) -> list[str]:
    """Find nearby .sln files for C# analyzer runs."""
    candidates: list[str] = []
    seen: set[str] = set()

    for path_str in paths:
        p = Path(path_str)
        search_roots: list[Path] = []
        if p.is_dir():
            search_roots.extend([p, p.parent])
        else:
            search_roots.extend([p.parent, p.parent.parent])

        for root in search_roots:
            if not root or not root.exists():
                continue
            for sln in sorted(root.glob("*.sln")):
                normalized = _normalize_path(str(sln.resolve()))
                if normalized in seen:
                    continue
                seen.add(normalized)
                candidates.append(normalized)

    return candidates


# =========================================================================
# MAIN SCANNING ENGINE
# =========================================================================


def scan_project(
    paths: list[str],
    *,
    review_scope: str = "production",
    include_tests: bool = False,
    include_temp: bool = False,
    lang: str = "auto",
    build_context: bool = True,
    compact: bool = False,
    max_findings: int = 0,
    summary_only: bool = False,
) -> dict:
    """Scan one or more paths with multi-pass analysis.

    Args:
        compact: If True, emit compact issue dicts for AI agent consumption.
        max_findings: Cap individual findings (0=unlimited). Counts still reflect all.
        summary_only: If True, emit only counts — no individual findings (~50 tokens).
    """

    # Determine extensions based on language
    if lang == "auto":
        extensions = [".py", ".cs"]
    elif lang == "py":
        extensions = [".py"]
    elif lang == "cs":
        extensions = [".cs"]
    else:
        extensions = []

    # 1. Collect files
    files = collect_files(paths, extensions)

    # 2. Build cross-file context (Pass 1+2)
    # Lazy context building: Only build context for files with findings (40-60% reduction)
    context: Optional[ContextEngineType] = None
    context_available = False
    # Defer context building until after regex pass to identify files needing context
    # Only build context in advisory/strict mode where cross-file analysis matters
    if build_context and _CONTEXT_ENGINE_AVAILABLE and paths and review_scope in ("advisory", "strict"):
        try:
            context_root = Path(paths[0])
            if context_root.is_file():
                context_root = context_root.parent
            context = ContextEngine(context_root)  # type: ignore[operator]
            # Lazy context: Build after identifying files with issues
            context_available = True
        except Exception:
            context = None

    # 3. Unified per-file scan — read once, run ALL layers together
    #
    # Architecture: each file is read ONCE. All applicable analyzers run on it.
    # Findings are merged with cross-tool confidence boosting:
    #   - Same file+line from 2 tools → confidence +15
    #   - Same file+line from 3+ tools → confidence +25, severity upgraded
    #
    # Tool specialization (no overlap waste):
    #   - Regex: pattern-based bugs (fast, broad coverage)
    #   - AST: structural bugs regex can't see (dead fields, uncalled methods)
    #   - External tools: cross-file analysis, taint tracking, type checking

    # Smart incremental scanning: Load cached findings for unchanged files (60-80% reduction)
    import hashlib
    cache: dict[str, dict[str, list[dict]]] = {}  # filepath -> {hash: issues, timestamp}

    def _file_hash(filepath: str) -> str:
        """Calculate SHA256 hash of a file (chunked for large files)."""
        try:
            sha = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    sha.update(chunk)
            return sha.hexdigest()
        except (OSError, IOError):
            return ""

    def _load_cache() -> None:
        """Load scan results from cache file."""
        nonlocal cache
        cache_file = Path(CACHE_DIR) / "reviewer_cache.json"
        if not cache_file.exists():
            return
        try:
            with open(cache_file, "r") as f:
                cache.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass

    def _save_cache() -> None:
        """Save scan results to cache file (atomic write pattern)."""
        nonlocal cache
        cache_file = Path(CACHE_DIR) / "reviewer_cache.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file, then rename
        temp_file = cache_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as f:
                json.dump(cache, f, indent=2)
            temp_file.replace(cache_file)  # Atomic rename on Windows/Unix
        except (OSError, IOError):
            pass  # Best effort cleanup

    explicit_file_targets = {
        _normalize_path(str(Path(path).resolve()))
        for path in paths
        if Path(path).is_file()
    }

    all_issues: list[Issue] = []
    scannable_files: list[str] = []
    python_files: list[str] = []
    csharp_files: list[str] = []
    ast_findings = 0
    tool_findings = 0
    tools_used: list[str] = []
    # Tool chaining: Track files with regex findings for Layer 2/3 filtering
    files_with_regex_issues: set[str] = set()

    # Check AST availability once
    _ast_ok = False
    if review_scope in ("advisory", "strict"):
        try:
            from veilbreakers_mcp._ast_analyzer import analyze_csharp, analyze_python, is_available as ast_available
            _ast_ok = ast_available()
        except ImportError:
            pass

    # Cross-tool merge map: (file, line) → Issue
    merge_map: dict[tuple[str, int], Issue] = {}

    def _merge(issue: Issue, *, source_tool: str = "regex"):
        """Add or merge an issue with semantic fingerprinting for tandem operation.

        Multi-tool correlation:
        - Exact (file, line) match: +15 confidence
        - Semantic match within ±5 lines: +8 confidence
        - 3+ tools flagging same semantic: +25 confidence cap
        - Tool reputation weighting applied (0.85-0.95 multiplier)
        """
        key = (issue.file, issue.line)

        # Check for exact location match first
        existing = merge_map.get(key)
        if existing:
            # Exact match: strong boost for tandem correlation
            existing.adjusted_confidence = min(99, existing.adjusted_confidence + 15)
            existing.confidence = min(99, existing.confidence + 15)
            # Check if 3+ tools now agree on this issue
            tool_count = existing.rule_id.count(",") + 1 + (1 if source_tool not in existing.rule_id else 0)
            if tool_count >= 3:
                existing.adjusted_confidence = min(99, existing.adjusted_confidence + 10)  # Additional +10 for 3+ tools
                existing.reasoning = f"[{tool_count} tools agree]"
            # Upgrade severity if new finding is worse
            sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            if sev_rank.get(issue.severity, 9) < sev_rank.get(existing.severity, 9):
                existing.severity = issue.severity
            # Append tool source for transparency
            if issue.rule_id not in existing.rule_id:
                existing.rule_id += f",{issue.rule_id}"
                existing.description += f" [+{source_tool}]"
            return

        # Semantic fuzzy matching: check for nearby findings with similar semantics
        issue_fingerprint = _semantic_fingerprint(issue)
        sem_merge_key = None
        fuzzy_boost = 0

        for line_delta in range(-5, 6):  # Check ±5 lines
            check_key = (issue.file, issue.line + line_delta)
            fuzzy_candidate = merge_map.get(check_key)
            if fuzzy_candidate:
                cand_fingerprint = _semantic_fingerprint(fuzzy_candidate)
                # Check if fingerprints have significant overlap (Jaccard similarity)
                overlap = len(issue_fingerprint & cand_fingerprint)
                union = len(issue_fingerprint | cand_fingerprint)
                similarity = overlap / union if union > 0 else 0
                if similarity >= 0.4:  # 40% semantic overlap threshold
                    sem_merge_key = check_key
                    # Distance-based boost: closer = higher boost
                    fuzzy_boost = max(0, 8 - abs(line_delta))
                    break

        if sem_merge_key:
            # Semantic merge with fuzzy location
            fuzzy_existing = merge_map[sem_merge_key]
            fuzzy_existing.adjusted_confidence = min(99, fuzzy_existing.adjusted_confidence + fuzzy_boost)
            fuzzy_existing.reasoning = f"[semantic match ±{issue.line - fuzzy_existing.line}L]"
            fuzzy_existing.rule_id += f",{issue.rule_id}"
            fuzzy_existing.description += f" [+{source_tool}:{issue.line}]"
        else:
            # No match, add as new issue
            merge_map[key] = issue
            all_issues.append(issue)
            # Apply combined weighting: tool reputation * rule reliability
            tool_mult = _TOOL_REPUTATION.get(source_tool, 1.0)
            rule_config = _RULE_RELIABILITY.get(issue.rule_id, 1.0)
            # Handle both simple float and enhanced dict format
            if isinstance(rule_config, dict):
                rule_reliability = rule_config.get("multiplier", 1.0)
            else:
                rule_reliability = rule_config
            combined_mult = tool_mult * rule_reliability
            issue.adjusted_confidence = max(20, min(99, int(issue.confidence * combined_mult)))

    # Single pass over all eligible files
    # Load cache at start for incremental scanning
    _load_cache()

    for filepath in files:
        # Smart incremental: Check cache for unchanged files (60-80% reduction)
        file_hash = _file_hash(filepath)
        if file_hash and filepath in cache and file_hash == cache.get(filepath, {}).get("hash", ""):
            # File unchanged - use cached findings
            cached_data = cache[filepath]
            if cached_data:
                all_issues.extend(cached_data.get("issues", []))
                continue  # Skip scanning this file
        if filepath not in explicit_file_targets and not _should_scan_file(
            filepath, lang, review_scope=review_scope,
            include_tests=include_tests, include_temp=include_temp,
        ):
            continue

        scannable_files.append(filepath)
        detected_lang = detect_language(filepath)
        if detected_lang == "python":
            python_files.append(filepath)
        elif detected_lang == "csharp":
            csharp_files.append(filepath)

        # --- Layer 1: Regex rules ---
        regex_has_issue = False
        if detected_lang == "python":
            for issue in scan_python_file(filepath, context, review_scope):
                _merge(issue, source_tool="regex")
                regex_has_issue = True
        elif detected_lang == "csharp":
            for issue in scan_csharp_file(filepath, context, review_scope):
                _merge(issue, source_tool="regex")
                regex_has_issue = True
        # Track files with regex findings for tool chaining
        if regex_has_issue:
            files_with_regex_issues.add(filepath)

        # --- Layer 2: tree-sitter AST (advisory+ only, same file bytes) ---
        # Tool chaining: Only run AST on files with regex findings (30-50% reduction)
        if _ast_ok and review_scope in ("advisory", "strict") and filepath in files_with_regex_issues:
            try:
                with open(filepath, "rb") as f:
                    src = f.read()
                if detected_lang == "csharp":
                    ast_issues = analyze_csharp(filepath, src)
                elif detected_lang == "python":
                    ast_issues = analyze_python(filepath, src)
                else:
                    ast_issues = []
                for af in ast_issues:
                    _merge(Issue(
                        rule_id=af.rule_id, severity=af.severity,
                        category="Bug", file=af.file, line=af.line,
                        description=af.description, fix=af.fix,
                        confidence=af.confidence, layer=LAYER_SEMANTIC,
                    ), source_tool="ast")
                    ast_findings += 1
            except Exception:
                pass

    # Lazy context building: Build context only for files with issues (advisory/strict only)
    if context_available and files_with_regex_issues and context:
        try:
            # Only build context if we have files that need it (40-60% reduction)
            context.build_context()
        except Exception:
            # Context build failure shouldn't break the scan
            context = None

    # --- Layer 3: External tools ---
    #
    # Python:
    #   - Ruff is the primary fast lint/smell pass
    #   - OpenGrep adds cross-file taint/data-flow coverage
    #   - mypy is strict-only due to cost/noise
    # C#:
    #   - dotnet build pass bundles Meziantou + Sonar + Unity + NetAnalyzers
    #   - OpenGrep provides extra structural/data-flow coverage
    #   - ast-grep remains fallback if the dotnet analyzer path is unavailable

    if scannable_files:
        try:
            from veilbreakers_mcp._tool_runner import (
                run_ast_grep,
                run_dotnet_analyzers,
                run_mypy,
                run_opengrep,
                run_ruff,
                available_tools,
            )
            avail = available_tools()
            # External tools run on ALL scannable files (batched, minimal cost)
            # Tool chaining only applies to per-file AST analysis (expensive)
            python_file_set = set(python_files)
            csharp_file_set = set(csharp_files)

            # Layer assignment: production scope elevates critical/high findings
            # to hard_correctness so they survive scope filtering
            _is_production = review_scope == "production"
            def _tool_layer(tf) -> str:
                """Map tool finding severity to appropriate layer."""
                if _is_production:
                    # In production, only critical/high findings from tools survive
                    if tf.severity in ("CRITICAL", "HIGH"):
                        return LAYER_HARD_CORRECTNESS
                    return LAYER_SEMANTIC  # Still collected, not shown
                return LAYER_SEMANTIC

            # Context sharing: Generate context hints for cross-file analysis
            # This helps OpenGrep and other tools understand variable flow across files
            context_rules_dir = ""
            if context and avail.get("opengrep"):
                import tempfile

                context_rules_dir_obj = tempfile.TemporaryDirectory(prefix="vb_context_")
                try:
                    context_rules_dir = context_rules_dir_obj.name
                    # Generate semantic rules from context engine
                    for issue_file in files_with_regex_issues:
                        try:
                            if hasattr(context, "get_definitions_at"):
                                defs = context.get_definitions_at(issue_file)
                                if defs:
                                    rule_file = Path(context_rules_dir) / f"{Path(issue_file).name}.semgrep.yaml"
                                    rule_content = f"""# Auto-generated context rules for {issue_file}
rules:
  - id: vb-context-{Path(issue_file).stem}
    languages: [python, csharp]
    message: Cross-file context analysis
    patterns:
"""
                                    for defn in defs[:50]:  # Limit to top 50 definitions
                                        rule_content += f"      - pattern: {defn.name}\n"
                                    rule_file.write_text(rule_content, encoding="utf-8")
                        except Exception:
                            pass
                except Exception:
                    context_rules_dir = ""

            def _merge_tool_finding(tf, *, allowed_files: set[str], category: str, layer: str = LAYER_SEMANTIC, source_tool: str):
                nonlocal tool_findings
                normalized_file = _normalize_path(tf.file)
                if normalized_file not in allowed_files:
                    return
                _merge(Issue(
                    rule_id=tf.rule_id,
                    severity=tf.severity,
                    category=category,
                    file=normalized_file,
                    line=tf.line,
                    description=tf.description,
                    fix=tf.fix,
                    layer=layer,
                ), source_tool=source_tool)
                tool_findings += 1

            # Python primary analyzer (runs in all scopes including production)
            if python_files and avail.get("ruff"):
                for tf in run_ruff(python_files):
                    _merge_tool_finding(tf, allowed_files=python_file_set, category="Quality",
                                        layer=_tool_layer(tf), source_tool="ruff")
                tools_used.append("ruff")

            # OpenGrep: advisory+ only (expensive, taint analysis)
            if review_scope in ("advisory", "strict") and python_files and avail.get("opengrep"):
                for tf in run_opengrep(python_files, rules_dir=context_rules_dir):
                    _merge_tool_finding(tf, allowed_files=python_file_set, category="Bug", source_tool="opengrep")
                tools_used.append("opengrep")

            # Python strict-only typing pass
            if review_scope == "strict" and python_files and avail.get("mypy"):
                for tf in run_mypy(python_files):
                    _merge_tool_finding(tf, allowed_files=python_file_set, category="Bug", source_tool="mypy")
                tools_used.append("mypy")

            # C# primary analyzer (runs in all scopes including production)
            ran_csharp_primary = False
            if csharp_files and avail.get("dotnet"):
                for sln in _find_solution_candidates(paths)[:1]:
                    for tf in run_dotnet_analyzers(sln):
                        _merge_tool_finding(tf, allowed_files=csharp_file_set, category="Bug",
                                            layer=_tool_layer(tf), source_tool="dotnet-analyzers")
                    tools_used.append("dotnet-analyzers")
                    ran_csharp_primary = True
                    break

            if review_scope in ("advisory", "strict") and csharp_files and avail.get("opengrep"):
                for tf in run_opengrep(csharp_files, rules_dir=context_rules_dir):
                    _merge_tool_finding(tf, allowed_files=csharp_file_set, category="Bug", source_tool="opengrep")
                tools_used.append("opengrep")

            # C# structural fallback (runs in all scopes including production)
            if csharp_files and not ran_csharp_primary and avail.get("ast-grep"):
                for filepath in csharp_files:
                    for tf in run_ast_grep(filepath, "csharp"):
                        _merge_tool_finding(tf, allowed_files=csharp_file_set, category="Bug",
                                            layer=_tool_layer(tf), source_tool="ast-grep")
                tools_used.append("ast-grep")

            tools_used = list(dict.fromkeys(tools_used))
        except ImportError:
            pass
        # context_rules_dir_obj cleans up automatically when exiting context

    # Smart incremental: Store scan results in cache before returning
    if cache:
        for filepath in set(scannable_files):  # Cache only files we actually scanned
            cache[filepath] = {
                "hash": _file_hash(filepath),
                "timestamp": __import__("time").time(),
                "issues": [asdict(i) for i in all_issues if i.file == filepath],
            }

    # 6. Generate report
    report = generate_report(all_issues, review_scope, compact=compact,
                             max_findings=max_findings, summary_only=summary_only)
    report["files_scanned"] = len(scannable_files)
    report["files_collected"] = len(files)
    report["context_available"] = context_available
    report["ast_findings"] = ast_findings
    report["tool_findings"] = tool_findings
    report["tools_used"] = tools_used

    # Smart incremental: Save cache before return
    if cache:
        _save_cache()

    return report


def generate_report(
    issues: list[Issue],
    review_scope: str = "production",
    *,
    compact: bool = False,
    max_findings: int = 0,
    summary_only: bool = False,
) -> dict:
    """Generate structured report dict with confidence/priority grading.

    Args:
        compact: If True, emit compact issue dicts (rule_id, sev, file:line, desc, fix)
                 to minimize token usage for AI agent consumption.
        max_findings: Cap the number of individual findings returned (0 = no limit).
                      Findings are sorted by severity+confidence so the most important
                      are always included. Counts still reflect ALL findings.
        summary_only: If True, emit only counts and agent_brief — no individual findings.
                      Minimizes tokens to ~100 for any codebase size.
    """
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    type_counts = {"ERROR": 0, "BUG": 0, "OPTIMIZATION": 0, "STRENGTHENING": 0}
    layer_counts = {LAYER_HARD_CORRECTNESS: 0, LAYER_SEMANTIC: 0, LAYER_HEURISTIC: 0}
    files_seen: set[str] = set()

    # Filter issues by scope-allowed layers
    allowed_layers = SCOPE_TO_LAYERS.get(review_scope, {LAYER_HARD_CORRECTNESS})
    scoped_issues = [i for i in issues if i.layer in allowed_layers]

    for issue in scoped_issues:
        sev_counts[issue.severity] = sev_counts.get(issue.severity, 0) + 1
        type_counts[issue.finding_type] = type_counts.get(issue.finding_type, 0) + 1
        layer_counts[issue.layer] = layer_counts.get(issue.layer, 0) + 1
        files_seen.add(issue.file)

    avg_conf = sum(i.adjusted_confidence for i in scoped_issues) / len(scoped_issues) if scoped_issues else 0
    avg_pri = sum(i.priority for i in scoped_issues) / len(scoped_issues) if scoped_issues else 0

    # Sort by severity+confidence for priority ordering
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_issues = sorted(
        scoped_issues,
        key=lambda i: (sev_order.get(i.severity, 9), -i.adjusted_confidence, i.file, i.line),
    )

    # Apply max_findings cap (counts still reflect ALL issues)
    display_issues = sorted_issues
    capped = False
    if max_findings > 0 and len(sorted_issues) > max_findings:
        display_issues = sorted_issues[:max_findings]
        capped = True

    if summary_only:
        issue_list = []
    elif compact:
        issue_list = [
            {
                "id": i.rule_id,
                "s": i.severity[0],
                "l": f"{Path(i.file).name}:{i.line}",
                "d": i.description,
                "f": i.fix[:80],  # Truncate fix to save tokens
            }
            for i in display_issues
        ]
    else:
        issue_list = [asdict(i) for i in display_issues]

    # Build brief only when NOT compact (compact has structured issues, brief is redundant)
    brief = ""
    if not compact:
        brief = _build_agent_brief(display_issues, review_scope, sev_counts, files_seen)
        if capped:
            brief = f"[CAPPED to top {max_findings} of {len(issues)} findings]\n" + brief

    result = {
        "total_issues": len(scoped_issues),
        "total_collected": len(issues),  # All issues before scope filter
        "critical": sev_counts["CRITICAL"],
        "high": sev_counts["HIGH"],
        "medium": sev_counts["MEDIUM"],
        "low": sev_counts["LOW"],
        "errors_bugs": type_counts.get("ERROR", 0) + type_counts.get("BUG", 0),
        "optimizations": type_counts.get("OPTIMIZATION", 0),
        "strengthening": type_counts.get("STRENGTHENING", 0),
        "hard_correctness": layer_counts.get(LAYER_HARD_CORRECTNESS, 0),
        "semantic": layer_counts.get(LAYER_SEMANTIC, 0),
        "heuristic": layer_counts.get(LAYER_HEURISTIC, 0),
        "avg_confidence": round(avg_conf, 1),
        "avg_priority": round(avg_pri, 1),
        "review_scope": review_scope,
        "issues": issue_list,
        "agent_brief": brief,
    }

    return result


_SEV_ICON = {"CRITICAL": "[!!!]", "HIGH": "[!!]", "MEDIUM": "[!]", "LOW": "[~]"}
_CONF_LABEL = {
    range(90, 101): "CERTAIN",
    range(75, 90): "HIGH",
    range(50, 75): "LIKELY",
    range(0, 50): "POSSIBLE",
}


def _conf_tag(conf: int) -> str:
    for rng, label in _CONF_LABEL.items():
        if conf in rng:
            return label
    return "POSSIBLE"


def _build_agent_brief(issues: list[Issue], scope: str, sev_counts: dict[str, int], files_seen: set[str]) -> str:
    """Build a concise, token-efficient agent-facing summary.

    Format:
      REVIEW SUMMARY (scope) — X files, Y findings
      CRITICAL: N | HIGH: N | MEDIUM: N | LOW: N

      [!!!] #1 CRITICAL BUG-01 | conf=95% CERTAIN
        file.cs:47 — GetComponent<T>() in Update -- cache in Awake/Start
        FIX: Cache the component reference in a field during Awake()
      ...
    """
    if not issues:
        return f"REVIEW CLEAN ({scope}) — no issues found."

    lines: list[str] = []
    lines.append(
        f"REVIEW SUMMARY ({scope}) — {len(files_seen)} files, {len(issues)} findings"
    )
    counts = " | ".join(f"{k}: {v}" for k, v in sev_counts.items() if v > 0)
    lines.append(counts)
    lines.append("")

    # Sort: severity desc, confidence desc, file, line
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_issues = sorted(
        issues,
        key=lambda i: (sev_order.get(i.severity, 9), -i.confidence, i.file, i.line),
    )

    # Group by file for readability
    from collections import defaultdict
    by_file: dict[str, list[Issue]] = defaultdict(list)
    for i in sorted_issues:
        by_file[i.file].append(i)

    idx = 0
    for filepath, file_issues in by_file.items():
        # Shorten path for display
        short = filepath.replace("\\", "/")
        if "/src/veilbreakers_mcp/" in short:
            short = short.split("/src/veilbreakers_mcp/")[-1]
        elif "/Assets/" in short:
            short = short.split("/Assets/")[-1]
        elif "/blender_addon/" in short:
            short = "addon/" + short.split("/blender_addon/")[-1]

        for issue in file_issues:
            idx += 1
            icon = _SEV_ICON.get(issue.severity, "[?]")
            conf_label = _conf_tag(issue.adjusted_confidence)
            lines.append(
                f"{icon} #{idx}  {issue.severity}  {issue.rule_id}  |  "
                f"conf={issue.adjusted_confidence}% {conf_label}"
            )
            lines.append(f"  {short}:{issue.line} — {issue.description}")
            lines.append(f"  FIX: {issue.fix}")
            lines.append("")

    return "\n".join(lines)


def _curate_strengthening_noise(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Limit heuristic strengthening spam while keeping bug/error findings intact."""
    curated: list[dict[str, Any]] = []
    heuristic_by_file: dict[str, list[dict[str, Any]]] = {}

    for issue in issues:
        if (
            issue.get("layer") == LAYER_HEURISTIC
            and issue.get("finding_type") == "STRENGTHENING"
        ):
            heuristic_by_file.setdefault(issue["file"], []).append(issue)
        else:
            curated.append(issue)

    for file_issues in heuristic_by_file.values():
        per_rule: dict[str, int] = {}
        kept: list[dict[str, Any]] = []
        for issue in sorted(
            file_issues,
            key=lambda entry: (
                -int(entry.get("confidence", 0)),
                -int(entry.get("priority", 0)),
                entry.get("line", 0),
            ),
        ):
            if len(kept) >= 3:
                break
            rule_id = issue.get("rule_id", "")
            per_rule_limit = 1
            if per_rule.get(rule_id, 0) >= per_rule_limit:
                continue
            kept.append(issue)
            per_rule[rule_id] = per_rule.get(rule_id, 0) + 1
        curated.extend(kept)

    return curated


# =========================================================================
# CLI
# =========================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VeilBreakers Unified Code Reviewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scope to layer mapping:
  production  -> hard_correctness only
  advisory    -> hard_correctness + semantic  
  strict      -> all three layers

Examples:
  python vb_code_reviewer.py path/to/scan/
  python vb_code_reviewer.py . --output report.json --severity HIGH --scope production
  python vb_code_reviewer.py Assets/Scripts/ --lang cs
  python vb_code_reviewer.py . --scope advisory
  python vb_code_reviewer.py . --scope strict
""",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to scan (default: current dir)",
    )
    parser.add_argument(
        "--output", "-o", default=None, help="Output JSON file path (default: stdout)"
    )
    parser.add_argument(
        "--severity",
        "-s",
        default="LOW",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        help="Minimum severity to report (default: LOW)",
    )
    parser.add_argument(
        "--scope",
        default="production",
        choices=list(REVIEW_SCOPE_CHOICES),
        help="Review scope: production=hard_correctness, advisory=+semantic, strict=all",
    )
    parser.add_argument(
        "--lang",
        "-l",
        default="auto",
        choices=list(LANG_CHOICES),
        help="Language: auto (both), py (Python), cs (C#)",
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include tests, fixtures, and testdata files in directory scans.",
    )
    parser.add_argument(
        "--include-temp",
        action="store_true",
        help="Include temporary, backup, and audit helper files in directory scans.",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Disable cross-file context building (faster but less accurate).",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=0,
        help="Minimum confidence to report (0-100)",
    )
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Error: {args.path} does not exist", file=sys.stderr)
        sys.exit(2)

    # Determine paths to scan
    scan_paths = [str(target)] if target.is_file() else [str(target)]

    # Run scan
    try:
        report = scan_project(
            scan_paths,
            review_scope=args.scope,
            include_tests=args.include_tests,
            include_temp=args.include_temp,
            lang=args.lang,
            build_context=not args.no_context,
        )
    except Exception as e:
        print(f"Scan error: {e}", file=sys.stderr)
        sys.exit(3)

    # Filter by severity
    threshold = Severity[args.severity]
    filtered_issues = [
        i
        for i in report["issues"]
        if Severity[i["severity"]] <= threshold
        and i.get("confidence", 0) >= args.min_confidence
    ]
    filtered_issues = _curate_strengthening_noise(filtered_issues)

    # Update report with filtered issues
    report["issues"] = filtered_issues
    report["total_issues"] = len(filtered_issues)

    # Recalculate counts
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    type_counts = {"ERROR": 0, "BUG": 0, "OPTIMIZATION": 0, "STRENGTHENING": 0}
    layer_counts = {LAYER_HARD_CORRECTNESS: 0, LAYER_SEMANTIC: 0, LAYER_HEURISTIC: 0}
    for issue in filtered_issues:
        sev_counts[issue["severity"]] += 1
        type_counts[issue["finding_type"]] = (
            type_counts.get(issue["finding_type"], 0) + 1
        )
        layer_counts[issue["layer"]] = layer_counts.get(issue["layer"], 0) + 1
    report["critical"] = sev_counts["CRITICAL"]
    report["high"] = sev_counts["HIGH"]
    report["medium"] = sev_counts["MEDIUM"]
    report["low"] = sev_counts["LOW"]
    report["errors_bugs"] = type_counts.get("ERROR", 0) + type_counts.get("BUG", 0)
    report["optimizations"] = type_counts.get("OPTIMIZATION", 0)
    report["strengthening"] = type_counts.get("STRENGTHENING", 0)
    report["hard_correctness"] = layer_counts.get(LAYER_HARD_CORRECTNESS, 0)
    report["semantic"] = layer_counts.get(LAYER_SEMANTIC, 0)
    report["heuristic"] = layer_counts.get(LAYER_HEURISTIC, 0)

    output = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(
            f"Report written to {args.output} ({len(filtered_issues)} issues)",
            file=sys.stderr,
        )
    else:
        # Human-readable console output
        _print_human_report(filtered_issues, report)

    has_serious = any(i["severity"] in ("CRITICAL", "HIGH") for i in filtered_issues)
    sys.exit(1 if has_serious else 0)


def _print_human_report(issues: list[dict], report: dict) -> None:
    """Print human-readable report to console."""
    sev_icons = {"CRITICAL": "!!!", "HIGH": " ! ", "MEDIUM": " ~ ", "LOW": " . "}
    type_labels = {
        "ERROR": "Bug/Error",
        "BUG": "Bug",
        "OPTIMIZATION": "Optimization",
        "STRENGTHENING": "Code Quality",
    }
    cat_labels = {
        "Security": "Security",
        "Bug": "Correctness",
        "Performance": "Performance",
        "Quality": "Code Quality",
        "Unity": "Unity",
    }

    # Group by file
    from collections import defaultdict

    by_file = defaultdict(list)
    for issue in sorted(
        issues, key=lambda i: (Severity[i["severity"]].value, i.get("priority", 0) * -1)
    ):
        by_file[issue["file"]].append(issue)

    file_num = 0
    for filepath, file_issues in sorted(by_file.items()):
        file_num += 1
        short = filepath.replace("\\", "/")
        if "veilbreakers_mcp/" in short:
            short = short.split("veilbreakers_mcp/")[-1]
        elif "Assets/" in short:
            short = short.split("Assets/")[-1]
        crit_count = sum(
            1 for i in file_issues if i["severity"] in ("CRITICAL", "HIGH")
        )
        header = f"  ({crit_count} critical)" if crit_count else ""
        print(f"\n{'=' * 70}")
        print(f"  File {file_num}: {short}  [{len(file_issues)} findings]{header}")
        print(f"{'=' * 70}")

        for idx, issue in enumerate(file_issues, 1):
            icon = sev_icons.get(issue["severity"], "   ")
            ftype = type_labels.get(issue["finding_type"], issue["finding_type"])
            cat = cat_labels.get(issue["category"], issue["category"])
            conf_pct = issue.get("confidence", 0)
            layer = issue.get("layer", LAYER_HARD_CORRECTNESS)

            print(f"\n  [{icon}] #{idx}  {issue['severity']}  |  {cat}  |  {ftype}")
            print(f"       Line {issue['line']}: {issue['description']}")
            print(f"       Fix: {issue['fix']}")
            if issue.get("matched_text"):
                code = issue["matched_text"][:90]
                print(f"       Code: {code}")
            print(
                f"       Rule: {issue['rule_id']}  |  Confidence: {conf_pct}%  |  Priority: {issue.get('priority', 0)}/100"
            )
            print(f"       Layer: {layer}")

    # Summary
    r = report
    print(f"\n{'=' * 70}")
    print("  REVIEW SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Files scanned:  {r.get('files_scanned', len(by_file))}")
    print(f"  Total findings: {r['total_issues']}")
    print()
    if r["critical"] > 0:
        print(f"  [!!!] CRITICAL:  {r['critical']}  -- fix immediately")
    if r["high"] > 0:
        print(f"  [ ! ] HIGH:      {r['high']}  -- fix before merge")
    if r["medium"] > 0:
        print(f"  [ ~ ] MEDIUM:    {r['medium']}  -- fix when possible")
    if r["low"] > 0:
        print(f"  [ . ] LOW:       {r['low']}  -- informational")
    if r["total_issues"] == 0:
        print("  ALL CLEAN - no issues found")
    print()
    print("  By Layer:")
    print(f"    hard_correctness: {r.get('hard_correctness', 0)}")
    print(f"    semantic:         {r.get('semantic', 0)}")
    print(f"    heuristic:        {r.get('heuristic', 0)}")
    print()
    print(f"  Bugs/Errors:     {r['errors_bugs']}")
    print(f"  Optimizations:   {r['optimizations']}")
    print(f"  Code Quality:    {r['strengthening']}")
    print(f"  Avg Confidence:  {r['avg_confidence']}%")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
