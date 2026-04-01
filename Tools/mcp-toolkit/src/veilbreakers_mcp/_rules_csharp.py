"""C# code review rules ported from code_review_templates.py.

This module contains all C# rules (BUG, PERF, SEC, UNITY, QUAL, GAME, etc.)
as Python dataclasses with regex patterns and guards.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from enum import IntEnum

from veilbreakers_mcp._types import Category, FindingType, Severity

# =============================================================================
# Data Classes
# =============================================================================


class Language(IntEnum):
    CSharp = 0
    Python = 1


class RuleScope(IntEnum):
    HotPath = 0
    AnyMethod = 1
    ClassLevel = 2
    FileLevel = 3


class FileFilter(IntEnum):
    Runtime = 0
    EditorOnly = 1
    All = 2


class LineContext(IntEnum):
    Cold = 0
    HotPath = 1
    Comment = 2
    StringLiteral = 3
    EditorBlock = 4
    Attribute = 5
    ClassLevel = 6
    MethodBody = 7


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
    scope: str = "AnyMethod"
    file_filter: str = "All"
    inside_pattern: Optional[re.Pattern] = None
    not_inside_pattern: Optional[re.Pattern] = None
    fast_check: Optional[str] = None
    language: Language = Language.CSharp


# =============================================================================
# CSharp Line Classifier
# =============================================================================


class CSharpLineClassifier:
    """Classifies each line of C# code into a LineContext.

    This is a direct port of the C# LineClassifier from code_review_templates.py.
    Performs transitive hot-path propagation (BFS from Update/FixedUpdate).
    """

    HOT_METHOD_SIG = re.compile(
        r"^\s*(private\s+|protected\s+|public\s+|internal\s+)?(override\s+)?void\s+(Update|LateUpdate|FixedUpdate|OnGUI|OnAnimatorMove|OnAnimatorIK)\s*\("
    )

    ANY_METHOD_SIG = re.compile(
        r"^\s*(private|protected|public|internal|static|override|virtual|abstract|async|void|int|float|bool|string|Task|IEnumerator|\w+)\s+\w+\s*\("
    )

    ATTR_LINE = re.compile(r"^\s*\[")
    EDITOR_IF_START = re.compile(r"#if\s+UNITY_EDITOR")
    END_IF = re.compile(r"#endif")

    @staticmethod
    def classify(lines: list[str]) -> list[LineContext]:
        """Classify all lines in a C# file."""
        ctx = [LineContext.Cold] * len(lines)
        in_hot_method = False
        hot_brace_depth = 0
        in_editor_block = False
        in_block_comment = False

        # Phase 1: Basic classification
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Block comment tracking
            if in_block_comment:
                ctx[i] = LineContext.Comment
                if "*/" in line_stripped:
                    in_block_comment = False
                continue

            if line_stripped.startswith("/*"):
                in_block_comment = "*/" not in line_stripped
                ctx[i] = LineContext.Comment
                continue

            # Single-line comment
            if CSharpLineClassifier._is_line_comment(line):
                ctx[i] = LineContext.Comment
                continue

            # Attribute lines
            if (
                CSharpLineClassifier.ATTR_LINE.match(line_stripped)
                and "=" not in line_stripped
            ):
                ctx[i] = LineContext.Attribute
                continue

            # #if UNITY_EDITOR blocks
            if CSharpLineClassifier.EDITOR_IF_START.search(line_stripped):
                in_editor_block = True
            if CSharpLineClassifier.END_IF.search(line_stripped) and in_editor_block:
                in_editor_block = False
                ctx[i] = LineContext.EditorBlock
                continue
            if in_editor_block:
                ctx[i] = LineContext.EditorBlock
                continue

            # Hot method tracking
            if CSharpLineClassifier.HOT_METHOD_SIG.match(line_stripped):
                in_hot_method = True
                hot_brace_depth = 0
            elif in_hot_method:
                # Exit hot path if we hit a different method signature
                if CSharpLineClassifier.ANY_METHOD_SIG.match(
                    line_stripped
                ) and not CSharpLineClassifier.HOT_METHOD_SIG.match(line_stripped):
                    in_hot_method = False
                    hot_brace_depth = 0

            if in_hot_method:
                hot_brace_depth += line.count("{") - line.count("}")
                if hot_brace_depth <= 0 and "}" in line:
                    in_hot_method = False
                    hot_brace_depth = 0
                ctx[i] = LineContext.HotPath
            else:
                ctx[i] = LineContext.Cold

        # Phase 2: Transitive hot-path propagation
        ctx = CSharpLineClassifier._propagate_hot_paths(lines, ctx)

        # Phase 3: Reclassify Cold lines into ClassLevel vs MethodBody
        method_bounds = _find_method_bounds(lines)
        for i, c in enumerate(ctx):
            if c != LineContext.Cold:
                continue
            in_method = any(start <= i <= end for _, start, end in method_bounds)
            ctx[i] = LineContext.MethodBody if in_method else LineContext.ClassLevel

        return ctx

    @staticmethod
    def _is_line_comment(line: str) -> bool:
        """Check if apparent '//' is actually a line comment (not inside a string)."""
        in_str = False
        in_verbatim = False
        escaped = False
        c = 0
        while c < len(line) - 1:
            ch = line[c]
            if in_verbatim:
                if ch == '"':
                    if c + 1 < len(line) and line[c + 1] == '"':
                        c += 2  # skip escaped "" in verbatim string
                        continue
                    else:
                        in_verbatim = False
                c += 1
                continue
            if escaped:
                escaped = False
                c += 1
                continue
            if ch == "\\" and in_str:
                escaped = True
                c += 1
                continue
            if ch == "@" and c + 1 < len(line) and line[c + 1] == '"' and not in_str:
                in_verbatim = True
                c += 2  # skip @"
                continue
            if ch == '"':
                in_str = not in_str
            if not in_str and ch == "/" and c + 1 < len(line) and line[c + 1] == "/":
                return True
            c += 1
        return False

    @staticmethod
    def _propagate_hot_paths(
        lines: list[str], ctx: list[LineContext]
    ) -> list[LineContext]:
        """Propagate hot path marking transitively through method calls."""
        # Build method boundaries
        methods: dict[str, tuple[int, int, bool]] = {}
        current_method = None
        method_start = -1
        method_depth = 0
        method_is_hot = False

        method_decl_re = re.compile(
            r"^(?:(?:private|protected|public|internal|static|override|virtual|abstract|async|sealed|new|partial)\s+)*"
            r"(void|Task|int|float|bool|string|IEnumerator|\w+)\s+(\w+)\s*\("
        )

        for i, line in enumerate(lines):
            if ctx[i] == LineContext.Comment:
                continue
            line_stripped = line.lstrip()
            if line_stripped.startswith("//"):
                continue

            match = method_decl_re.match(line_stripped)
            if match:
                m_name = match.group(2)
                if current_method is not None and method_start >= 0:
                    methods[current_method] = (method_start, i - 1, method_is_hot)
                current_method = m_name
                method_start = i
                method_is_hot = ctx[i] == LineContext.HotPath
                method_depth = 0

            if current_method is not None:
                method_depth += line.count("{") - line.count("}")
                if method_depth <= 0 and i > method_start and "}" in line:
                    methods[current_method] = (method_start, i, method_is_hot)
                    current_method = None

        if current_method is not None and method_start >= 0:
            methods[current_method] = (method_start, len(lines) - 1, method_is_hot)

        # Build call graph
        call_graph: dict[str, set[str]] = {}
        for name, (start, end, _) in methods.items():
            calls = set()
            for i in range(start, min(end + 1, len(lines))):
                if ctx[i] == LineContext.Comment:
                    continue
                for cm in re.finditer(r"\b(\w+)\s*\(", lines[i]):
                    if not CSharpLineClassifier._is_match_in_string(lines[i], cm.start()):
                        callee = cm.group(1)
                        if callee in methods and callee != name:
                            calls.add(callee)
            call_graph[name] = calls

        # BFS from known hot methods
        hot_methods = {m for m, (_, _, is_hot) in methods.items() if is_hot}
        queue = list(hot_methods)
        visited = set(hot_methods)

        while queue:
            method = queue.pop(0)
            if method not in call_graph:
                continue
            for callee in call_graph[method]:
                if callee not in visited:
                    visited.add(callee)
                    queue.append(callee)

        # Re-classify transitively hot methods
        for hot_method in visited:
            if hot_method not in methods:
                continue
            start, end, was_hot = methods[hot_method]
            if was_hot:
                continue
            for i in range(start, min(end + 1, len(ctx))):
                if ctx[i] == LineContext.Cold:
                    ctx[i] = LineContext.HotPath

        return ctx

    @staticmethod
    def _is_match_in_string(line: str, match_pos: int) -> bool:
        """Check if a match position falls inside a quoted string on the line."""
        in_single = False
        in_double = False
        escaped = False
        for k in range(len(line)):
            if k >= len(line):
                break
            ch = line[k]
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
            if k == match_pos:
                return in_single or in_double
        return False

    @staticmethod
    def count_char(s: str, c: str) -> int:
        """Count occurrences of char, skipping string literals."""
        n = 0
        in_str = False
        in_verbatim = False
        escaped = False
        i = 0
        while i < len(s):
            ch = s[i]
            if in_verbatim:
                if ch == '"':
                    if i + 1 < len(s) and s[i + 1] == '"':
                        i += 1
                    else:
                        in_verbatim = False
                i += 1
                continue
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\" and in_str:
                escaped = True
                i += 1
                continue
            if ch == "@" and i + 1 < len(s) and s[i + 1] == '"' and not in_str:
                in_verbatim = True
                i += 1
                i += 1
                continue
            if ch == '"':
                in_str = not in_str
                i += 1
                continue
            if not in_str and ch == c:
                n += 1
            i += 1
        return n


# =============================================================================
# Helper Functions
# =============================================================================


def matches_scope(ctx: LineContext, scope: str) -> bool:
    """Check if line context matches the required scope."""
    if scope == "HotPath":
        return ctx == LineContext.HotPath
    if scope == "AnyMethod":
        return ctx not in (LineContext.Comment, LineContext.Attribute)
    return ctx != LineContext.Comment


def in_fixed_update(
    line: str, all_lines: list[str], idx: int, ctx: list[LineContext]
) -> bool:
    """Check if we're inside a FixedUpdate method."""
    for i in range(idx, -1, -1):
        if re.search(r"void\s+FixedUpdate\s*\(", all_lines[i]):
            return True
        if i < idx and all_lines[i].count("{") > 0 and i < idx - 1:
            break
    return False


def body_length(all_lines: list[str], start: int) -> int:
    """Count brace-delimited body length from a method/class declaration."""
    depth = 0
    for j in range(start, len(all_lines)):
        depth += CSharpLineClassifier.count_char(
            all_lines[j], "{"
        ) - CSharpLineClassifier.count_char(all_lines[j], "}")
        if depth <= 0 and j > start:
            return j - start
    return 0


def _find_method_bounds(all_lines: list[str]) -> list[tuple[str, int, int]]:
    """Return (method_name, start_line_idx, end_line_idx) tuples."""
    bounds: list[tuple[str, int, int]] = []
    method_decl_re = re.compile(
        r"^\s*(?:(?:public|private|protected|internal|static|override|virtual|abstract|async|sealed|new|partial)\s+)*"
        r"(?:void|Task|UniTask|IEnumerator|int|float|bool|string|[A-Za-z_]\w*(?:<[^>]+>)?)\s+([A-Za-z_]\w*)\s*\("
    )
    current_name: Optional[str] = None
    start_idx = -1
    depth = 0

    for idx, line in enumerate(all_lines):
        stripped = line.strip()
        if current_name is None:
            match = method_decl_re.match(stripped)
            if match:
                current_name = match.group(1)
                start_idx = idx
                depth = CSharpLineClassifier.count_char(
                    line, "{"
                ) - CSharpLineClassifier.count_char(line, "}")
                if depth <= 0:
                    if "{" in line:
                        if current_name is not None:
                            finalized_name = current_name
                            bounds.append((finalized_name, start_idx, idx))
                        current_name = None
                        start_idx = -1
                        depth = 0
                    else:
                        depth = 0
        else:
            depth += CSharpLineClassifier.count_char(
                line, "{"
            ) - CSharpLineClassifier.count_char(line, "}")
            if depth <= 0:
                bounds.append((current_name, start_idx, idx))
                current_name = None
                start_idx = -1
                depth = 0

    if current_name is not None and start_idx >= 0:
        bounds.append((current_name, start_idx, len(all_lines) - 1))
    return bounds


def _method_name_for_line(all_lines: list[str], idx: int) -> Optional[str]:
    for method_name, start_idx, end_idx in _find_method_bounds(all_lines):
        if start_idx <= idx <= end_idx:
            return method_name
    return None


def _is_particle_system_play(
    line: str, all_lines: list[str], idx: int, _ctx: object = None
) -> bool:
    match = re.search(r"\b([A-Za-z_]\w*)\.Play\s*\(\s*\)", line)
    if not match:
        return False
    target = match.group(1)
    if target.lower() in {"ps", "particlesystem"} or "particle" in target.lower():
        return True

    window = all_lines[max(0, idx - 8) : min(len(all_lines), idx + 9)]
    decl_patterns = [
        rf"\bParticleSystem\s+{re.escape(target)}\b",
        rf"\b{re.escape(target)}\s*=\s*GetComponent\s*<\s*ParticleSystem\s*>",
        rf"\b{re.escape(target)}\s*=\s*.*ParticleSystem",
    ]
    return any(
        re.search(pattern, candidate)
        for pattern in decl_patterns
        for candidate in window
    )


def _is_await_in_teardown(
    line: str, all_lines: list[str], idx: int, _ctx: object = None
) -> bool:
    method_name = _method_name_for_line(all_lines, idx)
    return method_name in {"OnDisable", "OnDestroy"}


def _missing_event_teardown(
    line: str, all_lines: list[str], idx: int, _ctx: object = None
) -> bool:
    if "+=" not in line:
        return False
    # Reject numeric addition (count += 1), string addition, single-char additions
    if re.search(r"\+=\s*\d", line) or re.search(r'\+=\s*"', line) or re.search(r"\+=\s*[a-z]\s*", line):
        return False
    has_unsubscribe = any("-=" in candidate for candidate in all_lines)
    has_teardown = any(
        re.search(r"\bvoid\s+(OnDisable|OnDestroy)\s*\(", candidate)
        for candidate in all_lines
    )
    return not has_unsubscribe and not has_teardown


def _texture_field_has_destroy(
    line: str, all_lines: list[str], idx: int, _ctx: object = None
) -> bool:
    """Check if Texture2D is assigned to field AND file has Destroy()."""
    if "new Texture2D" not in line:
        return False  # Not a Texture2D creation
    # Check if assigned to field (starts with _)
    if not re.search(r"_\w+\s*=\s*new\s+Texture2D", line):
        return False  # Not a field assignment
    # Check if Destroy exists anywhere in file
    has_destroy = any("Destroy" in line for line in all_lines)
    return not has_destroy  # Flag only if no Destroy present


def _has_require_component_for(
    line: str, all_lines: list[str], idx: int, _ctx: object = None
) -> bool:
    """Check if [RequireComponent(typeof(T))] exists for GetComponent<T>() call on `this`."""
    match = re.search(r"GetComponent\s*<(\w+)>", line)
    if not match:
        return False  # Not a GetComponent call
    # Suppress if called on another object (variable.GetComponent<T>())
    before_gc = line[:match.start()].rstrip()
    if before_gc.endswith("."):
        # Called on another object, not `this` — RequireComponent doesn't help
        return False
    comp_type = match.group(1)
    # Suppress if already has null check on the same line or next line
    # Only suppress ?. when it appears AFTER GetComponent (result is null-checked),
    # not when it appears before (obj?.GetComponent<T>() null-checks the receiver instead).
    if re.search(r"(TryGetComponent|!=\s*null|==\s*null|if\s*\()", line):
        return False
    if re.search(r"GetComponent<\w+>\(\)\s*\?\.", line):
        return False
    if idx + 1 < len(all_lines) and re.search(r"(!=\s*null|==\s*null|if\s*\(.*null)", all_lines[idx + 1]):
        return False
    # Scan full file for [RequireComponent(typeof(T))]
    for other_line in all_lines:
        if f"typeof({comp_type})" in other_line or f"typeof<{comp_type}>" in other_line:
            return False  # Has RequireComponent, suppress
    return True  # No RequireComponent found on `this`, flag it


# =============================================================================
def _iter01_same_collection_guard(line: str, all_lines: list[str], idx: int) -> bool:
    """Return True only if the .Remove() operates on the SAME collection being iterated.

    Two-pass removal (iterate a buffer copy, remove from main collection) is safe.
    Suppresses UI element removal (.parent?.Remove) and non-collection .Remove() calls.
    """
    # Suppress UI element removal patterns (check first, before collection parsing)
    if re.search(r"\.parent\??\.\s*Remove\s*\(", line):
        return False

    # Extract collection name being removed from: e.g., "_cooldowns.Remove(...)"
    rm_match = re.search(r"(\w+)\??\.\s*Remove\s*\(", line)
    if not rm_match:
        return True  # Can't parse — let rule fire
    removed_collection = rm_match.group(1)
    # Suppress common non-collection Remove patterns
    if removed_collection in ("parent", "style", "classList", "hierarchy"):
        return False

    # Scan current line and upward for the nearest foreach
    for j in range(idx, max(0, idx - 20) - 1, -1):
        foreach_match = re.search(r"\bforeach\s*\([^)]*\bin\s+(\w+)", all_lines[j])
        if foreach_match:
            iterated_collection = foreach_match.group(1)
            # Only fire if iterating the SAME collection being modified
            return iterated_collection == removed_collection
    return False  # No foreach found — not a collection-during-iteration bug


def _static_collection_is_mutated(line: str, all_lines: list[str]) -> bool:
    """Return True if a static readonly collection field is mutated in the file.

    Lookup tables initialized inline and never modified are not bugs — suppress those.
    Only fire if .Add/.Remove/.Clear/.Insert/[key]= are found on the field.
    """
    m = re.search(r"static\s+readonly\s+\w+<[^>]+>\s+(\w+)\s*=", line)
    if not m:
        return True  # Can't extract name; let rule fire
    field_name = m.group(1)
    mutation_pat = re.compile(
        rf"\b{re.escape(field_name)}\b\s*\.\s*"
        r"(Add|Remove|RemoveAt|Insert|Clear|Push|Pop|Enqueue|Dequeue|TrimExcess)\s*\("
        rf"|\b{re.escape(field_name)}\b\s*\[[^\]]+\]\s*="
    )
    for other_line in all_lines:
        if mutation_pat.search(other_line):
            return True
    return False


# C# RULES - BUG (1-57)
# =============================================================================


def _create_rule(
    rule_id: str,
    severity: Severity,
    category: Category,
    description: str,
    fix: str,
    pattern: str,
    scope: str = "HotPath",
    file_filter: str = "Runtime",
    finding_type: FindingType = FindingType.BUG,
    confidence: int = -1,
    priority: int = -1,
    reasoning: Optional[str] = None,
    anti_patterns: Optional[list[str]] = None,
    anti_radius: int = 3,
    guard: Optional[Callable] = None,
    layer: str = "hard_correctness",
    flags: int = 0,
) -> Rule:
    """Helper to create a rule with auto-computed confidence/priority."""
    if confidence < 0:
        if severity == Severity.CRITICAL:
            confidence = 95
        elif severity == Severity.HIGH:
            confidence = 85
        elif severity == Severity.MEDIUM:
            confidence = 75
        else:
            confidence = 70

    if priority < 0:
        if severity == Severity.CRITICAL:
            priority = 95
        elif severity == Severity.HIGH:
            priority = 75
        elif severity == Severity.MEDIUM:
            priority = 50
        else:
            priority = 20

    anti_pats = [re.compile(p, flags) for p in (anti_patterns or [])]

    return Rule(
        id=rule_id,
        severity=severity,
        category=category,
        description=description,
        fix=fix,
        pattern=re.compile(pattern, flags),
        anti_patterns=anti_pats,
        anti_radius=anti_radius,
        guard=guard,
        finding_type=finding_type,
        confidence=confidence,
        priority=priority,
        reasoning=reasoning,
        layer=layer,
        scope=scope,
        file_filter=file_filter,
        language=Language.CSharp,
    )


# BUG Rules
RULES: list[Rule] = []

# BUG-01: GetComponent in Update
RULES.append(
    _create_rule(
        "BUG-01",
        Severity.CRITICAL,
        Category.Bug,
        "GetComponent<T>() in Update/LateUpdate/FixedUpdate -- cache in Awake/Start",
        "Cache the component reference in a field during Awake() or Start().",
        r"GetComponent\s*<",
        scope="HotPath",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"(Awake|Start|OnEnable)\s*\(",
            r"private\s+\w+\s+_\w+\s*=\s*GetComponent",
            r"/Editor/",
        ],
    )
)

# BUG-02: Camera.main in Update
RULES.append(
    _create_rule(
        "BUG-02",
        Severity.CRITICAL,
        Category.Bug,
        "Camera.main in Update -- calls FindGameObjectWithTag internally",
        "Cache Camera.main in a field during Start().",
        r"Camera\.main",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w*(cam|camera)\w*\s*=\s*Camera\.main"],
    )
)

# BUG-03: FindObjectOfType in Update
RULES.append(
    _create_rule(
        "BUG-03",
        Severity.CRITICAL,
        Category.Bug,
        "FindObjectOfType in Update -- O(n) scene scan every frame",
        "Cache the result in Start() or use a singleton/service locator pattern.",
        r"FindObjectOfType\s*[<(]",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-04: Heap allocation in Update
RULES.append(
    _create_rule(
        "BUG-04",
        Severity.HIGH,
        Category.Bug,
        "Heap allocation (new List/Dictionary/HashSet) inside Update",
        "Pre-allocate collections as fields and Clear() them in Update instead.",
        r"new\s+(List|Dictionary|HashSet|Queue|Stack|LinkedList)\s*<",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"\.Clear\s*\(\s*\)"],
    )
)

# BUG-05: String concatenation in Update
RULES.append(
    _create_rule(
        "BUG-05",
        Severity.HIGH,
        Category.Bug,
        "String concatenation with + in Update -- allocates new string each frame",
        "Use StringBuilder, string.Format, or interpolation cached outside the loop.",
        r'(?:"[^"]*"\s*\+\s*(?:"|\.ToString))|(?:\.ToString\s*\(\s*\)\s*\+\s*")',
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"const\s+string", r"StringBuilder"],
    )
)

# BUG-06: GameObject.Find in Update
RULES.append(
    _create_rule(
        "BUG-06",
        Severity.CRITICAL,
        Category.Bug,
        "GameObject.Find() in Update -- string-based scene search every frame",
        "Cache the reference in Start() or Awake().",
        r"GameObject\.Find\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-07: transform.position/rotation multiple accesses
RULES.append(
    _create_rule(
        "BUG-07",
        Severity.MEDIUM,
        Category.Bug,
        "transform.position/.rotation accessed multiple times -- crosses native boundary",
        "Cache transform.position/rotation in a local variable.",
        r"transform\.(position|rotation)\s*[;=\.\[].*transform\.(position|rotation)",
        scope="HotPath",
        flags=re.DOTALL,
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"var\s+\w+\s*=\s*transform\.(position|rotation)",
        ],
    )
)

# BUG-08: Accessing member after Destroy(gameObject)
RULES.append(
    _create_rule(
        "BUG-08",
        Severity.HIGH,
        Category.Bug,
        "Accessing member after Destroy(gameObject) -- object is destroyed",
        "Add 'return;' after Destroy(gameObject) or ensure no member access follows.",
        r"Destroy\s*\(\s*gameObject\s*\)",
        scope="AnyMethod",
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment
            and not any(
                all[j].strip().startswith(("return", "}", "break"))
                for j in range(i + 1, min(i + 4, len(all)))
                if all[j].strip() and not all[j].strip().startswith("//")
            )
        ),
    )
)

# BUG-09: Missing null check after GetComponent
RULES.append(
    _create_rule(
        "BUG-09",
        Severity.HIGH,
        Category.Bug,
        "Missing null check after GetComponent -- may return null",
        "Always null-check the result of GetComponent before use, or add [RequireComponent].",
        r"=\s*GetComponent\s*<[^>]+>\s*\(\s*\)\s*;",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"if\s*\(\s*\w+\s*[!=]=\s*null",
            r"Debug\.(Log|Assert)",
            r"\?\.",
            r"\[RequireComponent",
            r"(Awake|Start|OnEnable)\s*\(",
        ],
        layer="semantic",
        confidence=60,
    )
)

# BUG-10: 'is null' on UnityEngine.Object
RULES.append(
    _create_rule(
        "BUG-10",
        Severity.MEDIUM,
        Category.Bug,
        "'is null' on UnityEngine.Object -- Unity overloads == for destroyed object check",
        "Use '== null' instead of 'is null' for Unity objects.",
        r"\bis\s+null\b",
        scope="AnyMethod",
        confidence=55,
        reasoning="'is null' is correct for plain C# objects, strings, interfaces, and generics. Only wrong when used on UnityEngine.Object subclasses where == null checks for destroyed objects.",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"System\.",
            r"struct\s",
            r"string\s",
            r"List<",
            r"Dictionary<",
            r"I[A-Z]\w+\s",
        ],
        layer="semantic",
        finding_type=FindingType.BUG,
    )
)

# BUG-11: async void method
RULES.append(
    _create_rule(
        "BUG-11",
        Severity.HIGH,
        Category.Bug,
        "async void method -- exceptions are silently swallowed",
        "Use async Task/UniTask instead; only async void for event handlers.",
        r"async\s+void\s+(?!On[A-Z]|Start|Awake|Handle|Button_|Btn_)\w+\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"ICommand", r"EventHandler"],
    )
)

# BUG-12: Coroutine started but never stopped
RULES.append(
    _create_rule(
        "BUG-12",
        Severity.MEDIUM,
        Category.Bug,
        "Coroutine started but never stopped -- potential memory leak",
        "Store the Coroutine reference and StopCoroutine in OnDisable/OnDestroy.",
        r"StartCoroutine\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"=\s*StartCoroutine",
            r"StopCoroutine",
            r"StopAllCoroutines",
        ],
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment
            and bool(
                re.search(
                    r"StartCoroutine\s*\(\s*\w*(Loop|Repeat|Continuous|Forever|Tick|Poll|Spawn)",
                    line,
                    re.IGNORECASE,
                )
            )
        ),
    )
)

# BUG-13: new WaitForSeconds() allocated every yield
RULES.append(
    _create_rule(
        "BUG-13",
        Severity.MEDIUM,
        Category.Bug,
        "new WaitForSeconds() allocated every yield -- cache as a field",
        "Declare a WaitForSeconds field and reuse it.",
        r"yield\s+return\s+new\s+WaitForSeconds\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-15: Collision callback detected
RULES.append(
    _create_rule(
        "BUG-15",
        Severity.LOW,
        Category.Quality,
        "Collision callback detected -- verify Rigidbody setup semantically",
        "Confirm at least one participating object has the required Rigidbody setup in scene/prefab data.",
        r"void\s+(OnTriggerEnter|OnCollisionEnter|OnTriggerEnter2D|OnCollisionEnter2D)\s*\(",
        scope="AnyMethod",
        finding_type=FindingType.STRENGTHENING,
        confidence=35,
        reasoning="Method presence alone cannot prove whether Rigidbody requirements are satisfied.",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="semantic",
    )
)

# BUG-16: Physics cast without LayerMask
RULES.append(
    _create_rule(
        "BUG-16",
        Severity.LOW,
        Category.Quality,
        "Physics cast without LayerMask -- verify intent semantically",
        "Use a LayerMask when broad collision queries are unintended; keep unmasked casts only when explicitly required.",
        r"Physics\d*\.Raycast\s*\([^)]*\)\s*;",
        scope="AnyMethod",
        finding_type=FindingType.STRENGTHENING,
        confidence=40,
        reasoning="Unmasked raycasts are often intentional for broad queries.",
        anti_patterns=[r"//\s*VB-IGNORE", r"(LayerMask|layerMask|layer)"],
        layer="semantic",
    )
)

# BUG-17: Time.deltaTime in FixedUpdate
RULES.append(
    _create_rule(
        "BUG-17",
        Severity.MEDIUM,
        Category.Bug,
        "Time.deltaTime in FixedUpdate -- use Time.fixedDeltaTime",
        "Replace with Time.fixedDeltaTime or omit (already fixed step).",
        r"Time\.deltaTime",
        scope="HotPath",
        guard=lambda line, all, i, ctx: in_fixed_update(line, all, i, ctx),
    )
)

# BUG-18: Empty Unity lifecycle method
RULES.append(
    _create_rule(
        "BUG-18",
        Severity.LOW,
        Category.Bug,
        "Empty Unity lifecycle method -- still called, wasting CPU",
        "Remove empty lifecycle methods entirely.",
        r"void\s+(Update|Start|Awake|LateUpdate|FixedUpdate|OnGUI|OnAnimatorMove)\s*\(\s*\)",
        scope="FileLevel",
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment and body_length(all, i) <= 2
        ),
    )
)

# BUG-19: foreach in hot path
RULES.append(
    _create_rule(
        "BUG-19",
        Severity.LOW,
        Category.Performance,
        "foreach in hot path -- verify collection/runtime semantics",
        "Use for loop with index instead.",
        r"foreach\s*\(",
        scope="HotPath",
        finding_type=FindingType.OPTIMIZATION,
        confidence=50,
        reasoning="Modern Unity (2021+) with .NET Standard 2.1 does not allocate enumerators for List<T> and arrays in foreach.",
        anti_patterns=[r"//\s*VB-IGNORE", r"Span<", r"ReadOnlySpan<", r"_buffer|_temp|Buffer\b"],
        layer="heuristic",  # Modern Unity (2021+/.NET Standard 2.1) doesn't allocate enumerators for List/Array
    )
)

# BUG-20: Debug.Log in production (heuristic -- too noisy for production scope)
RULES.append(
    _create_rule(
        "BUG-20",
        Severity.LOW,
        Category.Quality,
        "Debug.Log in production code -- wrap in #if UNITY_EDITOR or [Conditional]",
        'Use #if UNITY_EDITOR or [Conditional("UNITY_EDITOR")] wrapper.',
        r"Debug\.(Log|LogWarning|LogError|LogException)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR", r"\[Conditional"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
        confidence=40,
    )
)

# BUG-21: Resources.Load at runtime without caching
RULES.append(
    _create_rule(
        "BUG-21",
        Severity.HIGH,
        Category.Bug,
        "Resources.Load at runtime without caching -- disk I/O each call",
        "Cache the loaded resource or use Addressables.",
        r"Resources\.Load\s*[<(]",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w+\s*=\s*Resources\.Load"],
    )
)

# BUG-22: Instantiate without parent transform
RULES.append(
    _create_rule(
        "BUG-22",
        Severity.MEDIUM,
        Category.Bug,
        "Instantiate without parent transform -- world-space recalculation",
        "Pass a parent transform as the second argument.",
        r"Instantiate\s*\(\s*[^,)]+\s*\)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"\.SetParent", r"\.transform\.parent"],
    )
)

# BUG-23: AddComponent in Update
RULES.append(
    _create_rule(
        "BUG-23",
        Severity.CRITICAL,
        Category.Bug,
        "AddComponent in Update loop -- creates components every frame",
        "Move AddComponent to initialization or one-time event.",
        r"\.AddComponent\s*[<(]",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-24: Private field missing SerializeField with Tooltip/Header
RULES.append(
    _create_rule(
        "BUG-24",
        Severity.LOW,
        Category.Bug,
        "Private field missing [SerializeField] but preceded by [Tooltip]/[Header]",
        "Add [SerializeField] to private fields visible in Inspector.",
        r"private\s+\w+\s+\w+\s*;",
        scope="ClassLevel",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\[SerializeField\]",
            r"\[HideInInspector\]",
            r"static|const|readonly",
        ],
        guard=lambda line, all, i, ctx: (
            i > 0 and ("[Tooltip" in all[i - 1] or "[Header" in all[i - 1])
        ),
    )
)

# BUG-25: Public Inspector field
RULES.append(
    _create_rule(
        "BUG-25",
        Severity.LOW,
        Category.Quality,
        "Public Inspector field -- verify encapsulation intent semantically",
        "Use [SerializeField] private instead of public for Inspector fields.",
        r"^\s+public\s+(?!static|const|readonly|override|virtual|abstract|event|delegate|class|struct|enum|interface)\w+\s+\w+\s*[;=]",
        scope="ClassLevel",
        finding_type=FindingType.STRENGTHENING,
        confidence=35,
        reasoning="Public serialized fields can be intentional data contracts.",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r":\s*ScriptableObject",
            r":\s*SOBase",
            r"\[System\.Serializable\]",
        ],
        layer="heuristic",  # Unity projects use public fields intentionally for serialization
    )
)

# BUG-26: Comparing tag with ==
RULES.append(
    _create_rule(
        "BUG-26",
        Severity.MEDIUM,
        Category.Bug,
        "Comparing tag with == instead of CompareTag() -- allocates string",
        'Use gameObject.CompareTag("tag") instead.',
        r'\.tag\s*==\s*"[^"]+"',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-27: Vector3.Distance in loop
RULES.append(
    _create_rule(
        "BUG-27",
        Severity.MEDIUM,
        Category.Bug,
        "Vector3.Distance in loop -- use sqrMagnitude to avoid sqrt",
        "Use (a - b).sqrMagnitude < threshold * threshold.",
        r"Vector\d\.Distance\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"sqrMagnitude"],
    )
)

# BUG-28: LINQ in Update
RULES.append(
    _create_rule(
        "BUG-28",
        Severity.HIGH,
        Category.Bug,
        "LINQ in Update -- allocates iterators, closures, temp collections",
        "Replace LINQ with manual loops in hot paths.",
        r"\.\s*(Where|Select|OrderBy|GroupBy|Any|All|First|Last|Count|Sum|ToList|ToArray|ToDictionary|FirstOrDefault|LastOrDefault|Single|SingleOrDefault)\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"Mathf\.", r"Math\.", r"Vector\d\.", r"Quaternion\."],
    )
)

# BUG-29: Animator.StringToHash not cached
RULES.append(
    _create_rule(
        "BUG-29",
        Severity.MEDIUM,
        Category.Bug,
        "Animator.StringToHash not cached -- recalculates hash every call",
        "Declare static readonly int fields for animator hashes.",
        r"Animator\.StringToHash\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"static\s+readonly\s+int"],
    )
)

# BUG-30: material property creating runtime instance
RULES.append(
    _create_rule(
        "BUG-30",
        Severity.MEDIUM,
        Category.Bug,
        "material property creating runtime instance -- use sharedMaterial or MPB",
        "Use renderer.sharedMaterial or MaterialPropertyBlock.",
        r"\.\s*material\s*[\.=](?!s)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"sharedMaterial", r"MaterialPropertyBlock"],
    )
)

# BUG-31: Null-conditional bypassing Unity semantics
RULES.append(
    _create_rule(
        "BUG-31",
        Severity.LOW,
        Category.Quality,
        "Null-conditional ?. or ?? may bypass Unity destroyed-object semantics",
        "Use explicit == null check: Unity overloads == to detect destroyed objects.",
        r"\b\w+\s*(\?\.|(\?\?))",
        scope="AnyMethod",
        finding_type=FindingType.STRENGTHENING,
        confidence=30,
        reasoning="Regex can rarely prove the target expression is a UnityEngine.Object instance.",
        anti_patterns=[r"//\s*VB-IGNORE", r"System\.\w+", r"string\?", r"int\?"],
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment
            and bool(
                re.search(
                    r"(Component|GameObject|Transform|Renderer|Collider|Rigidbody|Camera|Light|MonoBehaviour)\s",
                    line,
                )
            )
        ),
        layer="semantic",
    )
)

# BUG-32: GetComponentInChildren/InParent in Update
RULES.append(
    _create_rule(
        "BUG-32",
        Severity.CRITICAL,
        Category.Bug,
        "GetComponentInChildren/InParent in Update -- cache it",
        "Cache in Awake/Start. Traverses entire hierarchy.",
        r"GetComponent(InChildren|InParent)\s*[<(]",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w+\s*=\s*GetComponent"],
    )
)

# BUG-33: FindWithTag in Update
RULES.append(
    _create_rule(
        "BUG-33",
        Severity.CRITICAL,
        Category.Bug,
        "FindWithTag/FindGameObjectsWithTag in Update -- O(n) scene scan",
        "Cache in Start() or use a registry pattern.",
        r"(FindWithTag|FindGameObjectsWithTag)\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-34: Dictionary serialization
RULES.append(
    _create_rule(
        "BUG-34",
        Severity.MEDIUM,
        Category.Bug,
        "Dictionary<K,V> in [Serializable] class -- Unity cannot serialize dictionaries",
        "Use a List<SerializableKeyValue> wrapper or ISerializationCallbackReceiver.",
        r"\bDictionary\s*<",
        scope="ClassLevel",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"ISerializationCallbackReceiver",
            r"SerializationCallback",
            r"JsonConvert",
        ],
        guard=lambda line, all, i, ctx: any(
            "[Serializable]" in all[j] or "[SerializeField]" in all[j]
            for j in range(max(0, i - 10), i)
        ),
        layer="semantic",
        finding_type=FindingType.BUG,
    )
)

# BUG-35: yield return 0 (boxing)
RULES.append(
    _create_rule(
        "BUG-35",
        Severity.LOW,
        Category.Bug,
        "yield return 0 -- boxes int to object; use yield return null",
        "Replace 'yield return 0' with 'yield return null' to avoid boxing allocation.",
        r"yield\s+return\s+0\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# BUG-36: Input polling in FixedUpdate
RULES.append(
    _create_rule(
        "BUG-36",
        Severity.HIGH,
        Category.Bug,
        "Input.GetKey/GetButton in FixedUpdate -- misses input on frames without physics step",
        "Read input in Update(), store in a field, apply in FixedUpdate().",
        r"Input\.(GetKey|GetKeyDown|GetKeyUp|GetButton|GetButtonDown|GetButtonUp|GetMouseButton|GetMouseButtonDown)\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"void\s+Update"],
        guard=lambda line, all, i, ctx: in_fixed_update(line, all, i, ctx),
    )
)

# BUG-37: ConfigureAwait(false) in Unity
RULES.append(
    _create_rule(
        "BUG-37",
        Severity.MEDIUM,
        Category.Bug,
        "ConfigureAwait(false) in Unity -- Unity has single-threaded sync context",
        "Remove .ConfigureAwait(false); Unity automatically returns to main thread.",
        r"\.ConfigureAwait\s*\(\s*false\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR", r"/Editor/"],
    )
)

# BUG-38: Texture2D created without Destroy
RULES.append(
    _create_rule(
        "BUG-38",
        Severity.HIGH,
        Category.Bug,
        "new Texture2D() without Destroy -- leaks native GPU memory",
        "Call Destroy(texture) when no longer needed, or use a texture pool.",
        r"new\s+Texture2D\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"Destroy\s*\(",
            r"DestroyImmediate",
            r"Object\.Destroy",
            r"_texture\s*=\s*new\s+Texture2D",
            r"_generated\w+\.\w+\(",
            r"_\w+Texture\s*=",
        ],
        anti_radius=100,
        guard=_texture_field_has_destroy,
    )
)

# BUG-39: RenderTexture not released
RULES.append(
    _create_rule(
        "BUG-39",
        Severity.CRITICAL,
        Category.Bug,
        "new RenderTexture() without Release -- leaks native GPU memory",
        "Call rt.Release() and Destroy(rt) in cleanup, or use RenderTexture.GetTemporary/ReleaseTemporary.",
        r"new\s+RenderTexture\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.Release\s*\(\)",
            r"ReleaseTemporary",
            r"Destroy\s*\(",
            r"_\w+Texture\s*=",
            r"_generated\w+\.\w+\(",
        ],
        anti_radius=30,
    )
)

# BUG-40: DontDestroyOnLoad(this)
RULES.append(
    _create_rule(
        "BUG-40",
        Severity.LOW,
        Category.Bug,
        "DontDestroyOnLoad(this) -- should use DontDestroyOnLoad(gameObject)",
        "Pass gameObject instead of this to ensure the entire GameObject persists.",
        r"DontDestroyOnLoad\s*\(\s*this\s*\)",
        scope="AnyMethod",
        confidence=90,
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

# =============================================================================
# PERFORMANCE RULES (PERF-01 to PERF-36)
# =============================================================================

RULES.append(
    _create_rule(
        "PERF-01",
        Severity.MEDIUM,
        Category.Performance,
        "Boxing value type to object -- causes GC allocation",
        "Use generics or overloaded methods to avoid boxing.",
        r"\(\s*object\s*\)\s*\w+",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-02",
        Severity.MEDIUM,
        Category.Performance,
        "Closure allocation in lambda/delegate in hot path",
        "Capture in a struct or pass via static method + state parameter.",
        r"=>\s*\{?[^}]*\b(this|[a-z_]\w*)\b",
        scope="HotPath",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"static\s+(void|bool|int)",
            r"static\s*\(",
            r"static\s*\w+\s*=>",
        ],
        guard=lambda line, all_lines, idx, ctx=None: (
            # Only fire on actual lambda/delegate expressions, not expression-bodied members.
            # Expression-bodied members have a method/property signature before `=>`
            not bool(re.search(
                r"^\s*(?:(?:public|private|protected|internal|static|override|virtual|abstract|sealed|async)\s+)*"
                r"(?:void|bool|int|float|string|Task|IEnumerator|[A-Z]\w*(?:<[^>]+>)?)\s+"
                r"\w+\s*(?:<[^>]+>)?\s*\([^)]*\)\s*=>",
                line,
            ))
            # Also exclude property expression bodies
            and not bool(re.search(
                r"^\s*(?:(?:public|private|protected|internal|static)\s+)*"
                r"(?:\w+(?:<[^>]+>)?)\s+\w+\s*=>",
                line,
            ))
            # Also exclude switch expression arms (pattern => value)
            and not bool(re.search(
                r"^\s*(?:_|\w+(?:\.\w+)*)\s*=>",
                line,
            ))
        ),
        finding_type=FindingType.OPTIMIZATION,
        confidence=50,
        reasoning="Most lambdas in Update don't allocate closures in modern Unity/.NET. Only a concern with captured locals that change per-frame.",
    )
)

RULES.append(
    _create_rule(
        "PERF-03",
        Severity.LOW,
        Category.Performance,
        "Large struct passed by value -- consider in/ref parameter",
        "Use 'in' for readonly pass or 'ref' for mutable pass.",
        r"\(\s*(Matrix4x4|Bounds|RaycastHit|ContactPoint|NavMeshHit)\s+\w+\s*[,)]",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"\bin\b", r"\bref\b"],
    )
)

RULES.append(
    _create_rule(
        "PERF-04",
        Severity.LOW,
        Category.Performance,
        "Unbounded List.Add without Capacity pre-allocation",
        "Set list.Capacity or use new List<T>(expectedSize).",
        r"new\s+List\s*<[^>]+>\s*\(\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Capacity\s*="],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "PERF-05",
        Severity.LOW,
        Category.Performance,
        "String.Format in hot path -- use cached StringBuilder",
        "Use StringBuilder.AppendFormat or pre-allocated string ops.",
        r"[Ss]tring\.Format\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-06",
        Severity.MEDIUM,
        Category.Performance,
        "Texture2D.GetPixel/SetPixel per-pixel -- use bulk API",
        "Use GetPixels32()/SetPixels32() for bulk pixel ops.",
        r"\.(GetPixel|SetPixel)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"GetPixels32|SetPixels32"],
    )
)

RULES.append(
    _create_rule(
        "PERF-07",
        Severity.HIGH,
        Category.Performance,
        "Mesh property in loop -- each access copies entire array",
        "Cache mesh.vertices/normals/etc in a local array before the loop.",
        r"mesh\.(vertices|normals|uv|tangents|colors|triangles)\b",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"var\s+\w+\s*=\s*mesh\."],
    )
)

RULES.append(
    _create_rule(
        "PERF-08",
        Severity.MEDIUM,
        Category.Performance,
        "Physics cast without maxDistance -- scans to infinity",
        "Always specify a maxDistance parameter.",
        r"Physics\d*\.(Raycast|SphereCast|CapsuleCast|BoxCast)\s*\(\s*[^,]+\s*,\s*[^,]+\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-09",
        Severity.LOW,
        Category.Performance,
        "Mathf.Pow(x, 2) -- use x * x for simple multiply",
        "Use x * x instead of Mathf.Pow(x, 2f).",
        r"Mathf\.Pow\s*\([^,]+,\s*2\.?0?f?\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-10",
        Severity.MEDIUM,
        Category.Performance,
        "Camera.main.ScreenToWorldPoint in Update without cache",
        "Cache Camera.main in Start().",
        r"Camera\.main\.Screen",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w*(cam|camera)\s*="],
    )
)

RULES.append(
    _create_rule(
        "PERF-11",
        Severity.MEDIUM,
        Category.Performance,
        "Nested for loops O(n^2) -- consider spatial hashing or early exit",
        "Use spatial partitioning, break/continue, or reduce inner loop.",
        r"for\s*\([^)]+\)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"break\s*;"],
        guard=lambda line, all, i, ctx: (
            ctx[i] == LineContext.HotPath
            and any(
                re.search(r"for\s*\([^)]+\)", all[j])
                for j in range(i + 1, min(i + 8, len(all)))
            )
        ),
        confidence=50,
        reasoning="Nested for loops over small fixed-size collections (e.g. 4x4 matrix, 3D vector components) are fine.",
    )
)

RULES.append(
    _create_rule(
        "PERF-12",
        Severity.LOW,
        Category.Performance,
        "SetParent without worldPositionStays=false",
        "Pass false as second argument if world position preservation unneeded.",
        r"\.SetParent\s*\(\s*[^,)]+\s*\)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        finding_type=FindingType.OPTIMIZATION,
        confidence=45,
        layer="heuristic",
    )
)

RULES.append(
    _create_rule(
        "PERF-13",
        Severity.MEDIUM,
        Category.Performance,
        "ParticleSystem collision on all layers -- use collision LayerMask",
        "Set the collision LayerMask to only needed layers.",
        r"collisionModule\.(enabled\s*=\s*true|collidesWith)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"LayerMask"],
    )
)

RULES.append(
    _create_rule(
        "PERF-14",
        Severity.LOW,
        Category.Performance,
        "Light shadow casting on all objects -- use culling mask",
        "Set the light's culling mask to limit shadow-casting layers.",
        r"\.shadows\s*=\s*LightShadows\.(Soft|Hard)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"cullingMask"],
    )
)

RULES.append(
    _create_rule(
        "PERF-15",
        Severity.LOW,
        Category.Performance,
        "AudioSource spatialBlend 0 but using distance attenuation",
        "Set spatialBlend to 1 for 3D or remove rolloff settings.",
        r"spatialBlend\s*=\s*0",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        finding_type=FindingType.OPTIMIZATION,
        confidence=45,
        layer="heuristic",
    )
)

RULES.append(
    _create_rule(
        "PERF-16",
        Severity.MEDIUM,
        Category.Performance,
        "new NavMeshPath() in hot path -- allocates each call",
        "Reuse a NavMeshPath instance.",
        r"new\s+NavMeshPath\s*\(\s*\)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w+\s*=\s*new\s+NavMeshPath"],
    )
)

RULES.append(
    _create_rule(
        "PERF-17",
        Severity.HIGH,
        Category.Performance,
        "ForceUpdateCanvases() called -- very expensive",
        "Let Unity batch canvas updates naturally.",
        r"ForceUpdateCanvases\s*\(\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-18",
        Severity.MEDIUM,
        Category.Performance,
        "LayoutRebuilder.ForceRebuildLayoutImmediate every frame",
        "Only rebuild when content changes, then disable LayoutGroup.",
        r"LayoutRebuilder\.ForceRebuildLayoutImmediate\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-19",
        Severity.LOW,
        Category.Performance,
        "SetActive toggling in hot path -- consider CanvasGroup.alpha",
        "Use CanvasGroup.alpha or disable MeshRenderer for frequent toggles.",
        r"\.SetActive\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"CanvasGroup"],
        guard=lambda line, all_lines, idx, ctx=None: (
            # Suppress for expression-bodied members (one-liner wrappers)
            not bool(re.search(
                r"^\s*(?:(?:public|private|protected|internal|static|override|virtual)\s+)*"
                r"(?:void|bool)\s+\w+\s*\([^)]*\)\s*=>",
                line,
            ))
        ),
    )
)

RULES.append(
    _create_rule(
        "PERF-20",
        Severity.MEDIUM,
        Category.Performance,
        "Multiple cameras rendering -- ensure proper culling/depth",
        "Reduce camera count or use stacking with optimized clear flags.",
        r"new\s+.*Camera\b.*enabled\s*=\s*true|Camera\.allCameras",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        confidence=40,
    )
)

RULES.append(
    _create_rule(
        "PERF-21",
        Severity.HIGH,
        Category.Performance,
        "Use NonAlloc physics API to avoid array allocation every frame",
        "Replace RaycastAll with RaycastNonAlloc, OverlapSphere with OverlapSphereNonAlloc.",
        r"Physics\.(RaycastAll|SphereCastAll|CapsuleCastAll|BoxCastAll|OverlapSphere|OverlapBox|OverlapCapsule)\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"NonAlloc"],
    )
)

RULES.append(
    _create_rule(
        "PERF-22",
        Severity.MEDIUM,
        Category.Performance,
        "Setting material properties in Update creates Material instances -- use MPB",
        "Use renderer.GetPropertyBlock()/SetPropertyBlock().",
        r"\.\s*material\s*\.\s*Set(Color|Float|Int|Vector|Texture|Matrix)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"MaterialPropertyBlock", r"sharedMaterial"],
    )
)

RULES.append(
    _create_rule(
        "PERF-23",
        Severity.MEDIUM,
        Category.Performance,
        "ToLower()/ToUpper() for comparison -- allocates new string",
        "Use string.Equals(a, b, StringComparison.OrdinalIgnoreCase) instead.",
        r"\.(ToLower|ToUpper|ToLowerInvariant|ToUpperInvariant)\s*\(\s*\)\s*(==|!=|\.Equals|\.Contains|\.StartsWith)",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"StringComparison\.(Ordinal|InvariantCulture)IgnoreCase",
        ],
    )
)

RULES.append(
    _create_rule(
        "PERF-26",
        Severity.MEDIUM,
        Category.Performance,
        "String.Contains without StringComparison -- culture-sensitive by default",
        "Use string.Contains(value, StringComparison.Ordinal) for culture-invariant comparison.",
        r'\.Contains\s*\(\s*"[^"]*"\s*\)',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"StringComparison", r"Ordinal"],
        confidence=50,
        guard=lambda line, all_lines, idx, ctx=None: (
            # Suppress on collection.Contains("str") — only string.Contains needs StringComparison.
            # Check if the variable is likely a string (not a list/array/hashset).
            not bool(re.search(
                r"\b(list|List|array|Array|set|Set|hashSet|HashSet|collection|items|ids)\w*\.Contains\s*\(",
                line,
            ))
            # Also suppress for null-conditional Contains on non-string types
            and not bool(re.search(r"\?\.\s*Contains\s*\(", line))
        ),
    )
)

RULES.append(
    _create_rule(
        "PERF-27",
        Severity.MEDIUM,
        Category.Performance,
        "Transform.Find in hot path -- string-based child lookup every frame",
        "Cache the child Transform reference in Start() or Awake().",
        r'\.Find\s*\(\s*"[^"]*"\s*\)',
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"_\w+\s*=\s*\w+\.Find"],
    )
)

RULES.append(
    _create_rule(
        "PERF-28",
        Severity.MEDIUM,
        Category.Performance,
        "Multiple GetComponent calls for same type -- cache once",
        "Call GetComponent<T>() once in Awake/Start and store the reference.",
        r"GetComponent\s*<(\w+)>\s*\(\s*\)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-29",
        Severity.LOW,
        Category.Performance,
        "Enum.HasFlag causes boxing allocation -- use bitwise check",
        "Use (flags & MyEnum.Value) != 0 instead of flags.HasFlag(MyEnum.Value).",
        r"\.HasFlag\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "PERF-30",
        Severity.MEDIUM,
        Category.Performance,
        "Instantiate in a loop without object pooling -- high GC pressure",
        "Use an ObjectPool<T> or custom pool to recycle instances.",
        r"Instantiate\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"ObjectPool", r"pool\."],
    )
)

RULES.append(
    _create_rule(
        "PERF-31",
        Severity.LOW,
        Category.Performance,
        "new List<T>(list) copies entire list -- use AddRange or pass as IReadOnlyList",
        "If you only need to read, pass IReadOnlyList<T> or use .AsReadOnly().",
        r"new\s+List\s*<[^>]+>\s*\(\s*\w+\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        confidence=45,
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "PERF-32",
        Severity.HIGH,
        Category.Performance,
        "Manual GC.Collect() causes frame hitch -- let Unity manage garbage collection timing",
        "Remove GC.Collect(). Only acceptable during loading screens with GC.WaitForPendingFinalizers().",
        r"GC\.Collect\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"loading",
            r"Loading",
            r"SceneManager",
            r"#if\s+UNITY_EDITOR",
        ],
    )
)

RULES.append(
    _create_rule(
        "PERF-36",
        Severity.MEDIUM,
        Category.Performance,
        "Shader.PropertyToID not cached -- recalculates string hash every call",
        'Cache: static readonly int _PropID = Shader.PropertyToID("_PropName"); then use _PropID.',
        r"Shader\.PropertyToID\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"static\s+readonly\s+int", r"static\s+int"],
    )
)

# =============================================================================
# SECURITY RULES (SEC-01 to SEC-13)
# =============================================================================

RULES.append(
    _create_rule(
        "SEC-01",
        Severity.CRITICAL,
        Category.Security,
        "System.IO.File operation without path validation -- path traversal risk",
        "Validate and sanitize file paths; reject '..' and absolute paths from user input.",
        r"System\.IO\.(File|Directory)\.(Read|Write|Delete|Move|Copy|Create|Open|Append)",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"Application\.(dataPath|persistentDataPath|streamingAssetsPath)",
            r"/Editor/",
        ],
    )
)

RULES.append(
    _create_rule(
        "SEC-02",
        Severity.CRITICAL,
        Category.Security,
        "Process.Start -- command injection risk",
        "Never pass user input to Process.Start; whitelist allowed commands.",
        r"Process\.Start\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR"],
    )
)

RULES.append(
    _create_rule(
        "SEC-03",
        Severity.HIGH,
        Category.Security,
        "JsonUtility.FromJson on untrusted input -- validate schema",
        "Validate deserialized object fields and reject unexpected values.",
        r"JsonUtility\.FromJson\s*[<(]",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "SEC-04",
        Severity.HIGH,
        Category.Security,
        "PlayerPrefs storing sensitive data -- plaintext storage",
        "Encrypt sensitive data or use a secure store.",
        r"PlayerPrefs\.(SetString|SetInt|SetFloat)\s*\(\s*"
        "(password|token|key|secret|credential|auth)",
        scope="AnyMethod",
        confidence=80,
    )
)

RULES.append(
    _create_rule(
        "SEC-05",
        Severity.MEDIUM,
        Category.Security,
        "HTTP URL (non-HTTPS) -- data in plaintext",
        "Use HTTPS URLs for all network requests.",
        r'(?:http://|UnityWebRequest\.Get\s*\(\s*"http://)',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"localhost", r"127\.0\.0\.1"],
    )
)

RULES.append(
    _create_rule(
        "SEC-06",
        Severity.CRITICAL,
        Category.Security,
        "CompileAssemblyFromSource -- arbitrary code execution",
        "Never compile user-provided code at runtime.",
        r"(CompileAssemblyFrom|CSharpCodeProvider|CodeDomProvider)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "SEC-07",
        Severity.CRITICAL,
        Category.Security,
        "SQL query with string concat -- SQL injection risk",
        "Use parameterized queries.",
        r"(SELECT|INSERT|UPDATE|DELETE)\s+.*\s*\+\s*\w+",
        scope="AnyMethod",
        confidence=80,
    )
)

RULES.append(
    _create_rule(
        "SEC-08",
        Severity.CRITICAL,
        Category.Security,
        "Hardcoded credential or API key in source",
        "Store in environment variables or secure vault.",
        r'(api[_-]?key|password|secret|token|credential)\s*=\s*"[^"]{8,}"',
        scope="FileLevel",
        confidence=80,
    )
)

RULES.append(
    _create_rule(
        "SEC-09",
        Severity.HIGH,
        Category.Security,
        "Resources.Load with user-provided path -- directory traversal",
        "Whitelist allowed resource paths.",
        r"Resources\.Load\s*\(\s*\w+\s*\)",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"const\s+string",
            r"nameof\s*\(",
            r'Resources\.Load\s*\(\s*"',
        ],
    )
)

RULES.append(
    _create_rule(
        "SEC-10",
        Severity.HIGH,
        Category.Security,
        "Application.OpenURL with dynamic URL -- URL injection",
        "Validate and whitelist URLs.",
        r'Application\.OpenURL\s*\(\s*[^")\s]+',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "SEC-11",
        Severity.CRITICAL,
        Category.Security,
        "Reflection used to invoke methods -- bypasses access control",
        "Avoid reflection on user-controlled type/method names. Whitelist allowed types.",
        r"(MethodInfo|Type)\.\w*Invoke\s*\(|(Type\.GetType|Assembly\.GetType)\s*\(\s*\w+",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR"],
    )
)

RULES.append(
    _create_rule(
        "SEC-12",
        Severity.HIGH,
        Category.Security,
        "WWW class used (deprecated) -- use UnityWebRequest with certificate validation",
        "Replace WWW with UnityWebRequest and implement certificate validation.",
        r"\bWWW\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "SEC-13",
        Severity.LOW,
        Category.Security,
        "Debug.Log may expose sensitive data in production builds",
        "Use conditional compilation or log level checks for sensitive data logging.",
        r'Debug\.Log\w*\s*\(\s*\$?"',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+(UNITY_EDITOR|DEBUG)"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
        confidence=35,
    )
)

# =============================================================================
# UNITY RULES (UNITY-01 to UNITY-31)
# =============================================================================

RULES.append(
    _create_rule(
        "UNITY-01",
        Severity.HIGH,
        Category.Unity,
        "MonoBehaviour constructor -- use Awake()/Start() instead",
        "Unity manages MonoBehaviour lifecycle; use Awake/Start.",
        r"\bpublic\s+\w+\s*\(\s*\)\s*\{",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"ScriptableObject", r"struct\s"],
        guard=lambda line, all, i, ctx: any(
            "MonoBehaviour" in all[j] for j in range(max(0, i - 30), i)
        ),
    )
)

RULES.append(
    _create_rule(
        "UNITY-02",
        Severity.HIGH,
        Category.Unity,
        "ScriptableObject constructor -- use OnEnable or CreateInstance",
        "Use ScriptableObject.CreateInstance<T>() and OnEnable.",
        r"\bpublic\s+\w+\s*\(\s*\)\s*\{",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"MonoBehaviour"],
        guard=lambda line, all, i, ctx: any(
            "ScriptableObject" in all[j] for j in range(max(0, i - 30), i)
        ),
    )
)

RULES.append(
    _create_rule(
        "UNITY-03",
        Severity.MEDIUM,
        Category.Unity,
        "Accessing .gameObject/.transform after Destroy(gameObject) -- use-after-destroy",
        "Add 'return;' after Destroy(gameObject) or null-check before accessing destroyed object's members.",
        r"\.(gameObject|transform)\b",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"if\s*\(\s*\w+\s*!=\s*null", r"return\s*;"],
        confidence=50,
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment
            and any(
                "Destroy(" in all[j] or "DestroyImmediate(" in all[j]
                for j in range(max(0, i - 5), i)
            )
        ),
        layer="semantic",
    )
)

RULES.append(
    _create_rule(
        "UNITY-04",
        Severity.HIGH,
        Category.Unity,
        "DontDestroyOnLoad without singleton duplicate check",
        "Add: if (Instance != null) { Destroy(gameObject); return; }",
        r"DontDestroyOnLoad\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"Instance\s*!=\s*null",
            r"_instance\s*!=\s*null",
            r"HasInstance",
            r"Destroy\(gameObject\)",
            r"Destroy\s*\(\s*this",
        ],
        anti_radius=15,
    )
)

RULES.append(
    _create_rule(
        "UNITY-05",
        Severity.MEDIUM,
        Category.Unity,
        "GetComponent in Awake/Start without [RequireComponent]",
        "Add [RequireComponent(typeof(T))] to guarantee the component exists.",
        r"GetComponent\s*<(\w+)>\s*\(\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"TryGetComponent"],
        guard=_has_require_component_for,
        layer="semantic",
        finding_type=FindingType.BUG,
    )
)

RULES.append(
    _create_rule(
        "UNITY-06",
        Severity.MEDIUM,
        Category.Unity,
        "Invoke/InvokeRepeating with string method name",
        "Use Coroutines, async/await, or direct method references.",
        r'\.(Invoke|InvokeRepeating)\s*\(\s*"',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-07",
        Severity.MEDIUM,
        Category.Unity,
        "Scene loaded without additive mode may leak DontDestroyOnLoad objects",
        "Use LoadSceneMode.Additive or clean up persistent objects.",
        r"SceneManager\.LoadScene\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Additive"],
        confidence=40,
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "UNITY-08",
        Severity.HIGH,
        Category.Unity,
        "Event += without matching -= -- memory leak if subscriber outlives publisher",
        "Add -= unsubscribe in OnDisable() or OnDestroy().",
        r"\w+\.\w+\s*\+=\s*\w+\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"\+=\s*\d", r'\+=\s*"'],
        guard=_missing_event_teardown,
    )
)

RULES.append(
    _create_rule(
        "UNITY-09",
        Severity.MEDIUM,
        Category.Unity,
        "Editor-only API outside #if UNITY_EDITOR block",
        "Wrap EditorApplication/AssetDatabase/etc. in #if UNITY_EDITOR.",
        r"\b(EditorApplication|AssetDatabase|EditorUtility|PrefabUtility|SerializedObject|SerializedProperty)\.",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR"],
        layer="hard_correctness",
        finding_type=FindingType.BUG,
    )
)

RULES.append(
    _create_rule(
        "UNITY-10",
        Severity.MEDIUM,
        Category.Unity,
        "Serializing interface or abstract type -- Unity serializer cannot handle",
        "Use concrete type or ISerializationCallbackReceiver.",
        r"\[SerializeField\]\s*(private|protected|public)?\s*(I[A-Z]\w+|abstract\s+\w+)\s+\w+",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"SerializeReference"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-11",
        Severity.LOW,
        Category.Unity,
        "Large array in ScriptableObject -- consider Addressables",
        "Use Addressables or split data into smaller chunks.",
        r"\[\]\s+\w+\s*=\s*new\s+\w+\[(?:[5-9]\d{2,}|\d{4,})\]",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-12",
        Severity.HIGH,
        Category.Unity,
        "Event subscription without teardown lifecycle -- likely missing unsubscribe path",
        "Add -= cleanup in OnDisable or OnDestroy, or make the teardown intent explicit.",
        r"\+=\s*\w+\s*;",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE"],
        guard=_missing_event_teardown,
        layer="semantic",
        finding_type=FindingType.STRENGTHENING,
        confidence=65,
    )
)

RULES.append(
    _create_rule(
        "UNITY-13",
        Severity.LOW,
        Category.Unity,
        "Awake execution order dependency without [DefaultExecutionOrder]",
        "Add [DefaultExecutionOrder(N)] to control initialization order.",
        r"void\s+Awake\s*\(\s*\)",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"\[DefaultExecutionOrder"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "UNITY-14",
        Severity.MEDIUM,
        Category.Unity,
        "Static field in MonoBehaviour -- shared across instances",
        "Use instance fields or a dedicated static manager.",
        r"static\s+(?!readonly|void|bool|int|float|string|event|Action|Func|delegate)\w+\s+\w+",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"Instance", r"Singleton", r"const\s"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "UNITY-15",
        Severity.LOW,
        Category.Unity,
        "Singleton MonoBehaviour missing [DisallowMultipleComponent]",
        "Add [DisallowMultipleComponent].",
        r"static\s+\w+\s+Instance\s*[{;=]",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"\[DisallowMultipleComponent"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-16",
        Severity.HIGH,
        Category.Unity,
        "GetComponent/Destroy in OnValidate -- fails during prefab import",
        "Wrap in #if UNITY_EDITOR and use EditorApplication.delayCall.",
        r"(GetComponent|Destroy|DestroyImmediate)\s*[<(]",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"EditorApplication\.delayCall",
            r"#if\s+UNITY_EDITOR",
        ],
        guard=lambda line, all, i, ctx: (
            _method_name_for_line(all, i) in {"OnValidate", "Reset"}
        ),
    )
)

RULES.append(
    _create_rule(
        "UNITY-17",
        Severity.MEDIUM,
        Category.Unity,
        "OnGUI called every frame -- consider UI Toolkit",
        "For runtime UI prefer UI Toolkit or Canvas.",
        r"void\s+OnGUI\s*\(\s*\)",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"/Editor/"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-18",
        Severity.MEDIUM,
        Category.Unity,
        "SendMessage/BroadcastMessage -- slow reflection, no compile-time safety",
        "Use direct method calls, C# events, or a message bus interface.",
        r"\b(SendMessage|BroadcastMessage|SendMessageUpwards)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"/Editor/"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-19",
        Severity.HIGH,
        Category.Unity,
        "Shader.Find() at runtime -- returns null if shader not in Always Included list",
        "Serialize shader references or load from Resources/Addressables.",
        r"Shader\.Find\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"/Editor/", r"#if\s+UNITY_EDITOR"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-20",
        Severity.HIGH,
        Category.Unity,
        "Accessing .material creates an instance -- must Destroy() it manually",
        "Use .sharedMaterial for read, or track/destroy instanced materials.",
        r"(?<!\bshared)\bmaterial\s*\.\s*(color|mainTexture|shader|renderQueue)",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"sharedMaterial",
            r"MaterialPropertyBlock",
            r"Destroy\s*\(\s*\w*[Mm]at",
        ],
        anti_radius=10,
    )
)

RULES.append(
    _create_rule(
        "UNITY-21",
        Severity.HIGH,
        Category.Unity,
        "Rigidbody.MovePosition/MoveRotation outside FixedUpdate -- jerky movement",
        "Call Rigidbody.MovePosition only in FixedUpdate for smooth physics movement.",
        r"(MovePosition|MoveRotation)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"FixedUpdate"],
        confidence=60,
    )
)

RULES.append(
    _create_rule(
        "UNITY-23",
        Severity.MEDIUM,
        Category.Unity,
        "TMP_Text.text assigned in Update -- allocates string every frame",
        "Cache the string or use TMP_Text.SetText() with zero-alloc overloads.",
        r"\.text\s*=\s*[^;]+;",
        scope="HotPath",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"SetText",
            r"(Start|Awake|OnEnable|Initialize|Init)\s*\(",
        ],
    )
)

RULES.append(
    _create_rule(
        "UNITY-24",
        Severity.HIGH,
        Category.Unity,
        "NavMeshAgent.SetDestination without IsOnNavMesh check -- may throw",
        "Check agent.isOnNavMesh before calling SetDestination.",
        r"\.SetDestination\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"isOnNavMesh", r"IsOnNavMesh"],
    )
)

RULES.append(
    _create_rule(
        "UNITY-25",
        Severity.MEDIUM,
        Category.Unity,
        "ScriptableObject field modified at runtime -- shared across all references",
        "Clone the SO at runtime: Instantiate(mySO) or use a runtime data copy.",
        r"(?:_\w+SO|_\w+Data|_\w+Config)\s*\.\s*\w+\s*[+\-*/]?=",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"Instantiate",
            r"ScriptableObject\.CreateInstance",
        ],
        confidence=45,
    )
)

RULES.append(
    _create_rule(
        "UNITY-27",
        Severity.MEDIUM,
        Category.Unity,
        "MonoBehaviour with both Update and FixedUpdate -- potential input/physics confusion",
        "Ensure input is read in Update and physics applied in FixedUpdate. Don't mix.",
        r"void\s+Update\s*\(",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE"],
        guard=lambda line, all, i, ctx: any(
            re.search(r"void\s+FixedUpdate\s*\(", all[j])
            for j in range(len(all))
        ),
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
        confidence=40,
    )
)

RULES.append(
    _create_rule(
        "UNITY-28",
        Severity.HIGH,
        Category.Unity,
        "NativeArray/NativeContainer not Disposed -- leaks unmanaged memory",
        "Call .Dispose() in OnDestroy, use Allocator.Temp (auto-disposes at frame end), or wrap in using statement.",
        r"new\s+Native(Array|List|HashSet|HashMap|Queue|Stack|MultiHashMap)\s*<",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.Dispose\s*\(",
            r"using\s+var",
            r"using\s*\(",
            r"Allocator\.Temp\b",
        ],
        anti_radius=20,
    )
)

RULES.append(
    _create_rule(
        "UNITY-31",
        Severity.CRITICAL,
        Category.Unity,
        "Unity Object created in field initializer -- runs on loading thread, crashes in release builds",
        "Move to Awake() or Start(). Field initializers run on the loading thread where Unity APIs are unavailable.",
        r"=\s*new\s+(GameObject|Texture2D|Material|Mesh|RenderTexture|Sprite|ComputeBuffer)\s*\(",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"\bvar\b", r"\bawait\b"],
        # Only flag field initializers: must look like a field declaration (type + name = new ...)
        # NOT a local variable (var x = new ...) or method-body assignment
        guard=lambda line, all, i, ctx: (
            # Field initializers use explicit type, not var
            not re.search(r"\bvar\b", line)
            # Field initializers are at class-body indentation (1 level, ~4-12 chars)
            and len(line) - len(line.lstrip()) <= 12
            # Must have a type declaration pattern (access modifier + type + name = new)
            and bool(re.search(
                r"^\s*(private|protected|public|internal|static|readonly|\[)\s",
                line,
            ))
        ),
    )
)

# =============================================================================
# QUALITY RULES (QUAL-01 to QUAL-28)
# =============================================================================

RULES.append(
    _create_rule(
        "QUAL-01",
        Severity.LOW,
        Category.Quality,
        "Method exceeds 50 lines -- consider extracting sub-methods",
        "Break long methods into smaller, well-named helpers.",
        r"(void|int|float|bool|string|var|Task|IEnumerator)\s+\w+\s*\([^)]*\)\s*\{",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        guard=lambda line, all, i, ctx: body_length(all, i) > 50,
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-02",
        Severity.LOW,
        Category.Quality,
        "Excessive nesting depth (>4 levels) -- flatten with early returns",
        "Use guard clauses, early returns, or extract nested logic.",
        r"^\s{20,}(if|for|while|foreach|switch)\b",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-03",
        Severity.LOW,
        Category.Quality,
        "Magic number in code -- use a named constant",
        "Define a const or static readonly field.",
        r"[=<>+\-*/]\s*(?<![.0-9])((?:[2-9]\d{2,}|\d{4,})(?:\.\d+)?f?)\s*[;,)\]}]",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"const\s",
            r"readonly\s",
            r"(Color|Vector|Rect|new\s+\w+\[)",
        ],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-04",
        Severity.LOW,
        Category.Quality,
        "Missing XML documentation on public method",
        "Add /// <summary> documentation to public API methods.",
        r"^\s+public\s+\S+\s+\w+\s*\([^)]*\)\s*\{?$",
        scope="ClassLevel",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"///",
            r"override\s+",
            r"^\s+public\s+\S+\s+\w+\s*\([^)]*\)\s*=>",
        ],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-05",
        Severity.LOW,
        Category.Quality,
        "Inconsistent naming -- private fields should use _camelCase",
        "Follow Unity C# conventions: _camelCase for private.",
        r"private\s+\w+\s+([A-Z]\w+)\s*[;=]",
        scope="ClassLevel",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"const\s",
            r"static\s",
            r"readonly\s",
            r"event\s",
        ],
    )
)

RULES.append(
    _create_rule(
        "QUAL-06",
        Severity.LOW,
        Category.Quality,
        "Empty catch block swallows exception silently",
        "At minimum log the exception.",
        r"catch\s*(\([^)]*\))?\s*\{\s*\}",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"// intentionally empty"],
    )
)

RULES.append(
    _create_rule(
        "QUAL-07",
        Severity.LOW,
        Category.Quality,
        "TODO/FIXME/HACK comment -- track or resolve",
        "Create a task/issue and reference its ID.",
        r"//\s*(TODO|FIXME|HACK|XXX|TEMP|WORKAROUND)\b",
        scope="FileLevel",
    )
)

RULES.append(
    _create_rule(
        "QUAL-08",
        Severity.LOW,
        Category.Quality,
        "Unused using directive -- verify with IDE",
        "Remove unused using statements. Use IDE 'Remove Unused Usings' command.",
        r"^using\s+\w+(\.\w+)*\s*;",
        scope="FileLevel",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
        confidence=30,
    )
)

RULES.append(
    _create_rule(
        "QUAL-09",
        Severity.LOW,
        Category.Quality,
        "Complex boolean condition (>3 operators) -- extract to named variable",
        "Extract complex conditions into a descriptive bool variable.",
        r"if\s*\(.*?(&&|\|\|).*?(&&|\|\|).*?(&&|\|\|)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-10",
        Severity.LOW,
        Category.Quality,
        "Switch statement missing default case",
        "Add a default case (even just throwing ArgumentOutOfRangeException).",
        r"switch\s*\([^)]+\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"\bdefault\s*:"],
        # Only flag if no default case exists in the switch body
        guard=lambda line, all, i, ctx: not any(
            re.search(r"\bdefault\s*:", all[j])
            for j in range(i + 1, min(i + 50, len(all)))
        ),
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

RULES.append(
    _create_rule(
        "QUAL-11",
        Severity.LOW,
        Category.Quality,
        "Non-sealed custom exception -- seal to prevent unintended inheritance",
        "Mark custom exception classes as sealed.",
        r"class\s+\w+Exception\s*:",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"sealed\s"],
    )
)

RULES.append(
    _create_rule(
        "QUAL-12",
        Severity.MEDIUM,
        Category.Quality,
        "Mutable static collection -- thread safety risk",
        "Use Concurrent* or make readonly with immutable contents.",
        r"static\s+(List|Dictionary|HashSet|Queue|Stack)\s*<",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"readonly\s", r"Concurrent"],
    )
)

RULES.append(
    _create_rule(
        "QUAL-13",
        Severity.HIGH,
        Category.Quality,
        "lock(this) or lock(typeof(...)) -- use dedicated lock object",
        "Use: private readonly object _lock = new object();",
        r"lock\s*\(\s*(this|typeof\s*\()",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "QUAL-14",
        Severity.MEDIUM,
        Category.Quality,
        "IDisposable not disposed -- use 'using' statement",
        "Wrap in 'using' block or call Dispose() in finally/OnDestroy.",
        r"new\s+(StreamReader|StreamWriter|FileStream|BinaryReader|BinaryWriter|HttpClient|WebClient|MemoryStream|UnityWebRequest)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"using\s+(var|\()", r"\.Dispose\s*\("],
    )
)

RULES.append(
    _create_rule(
        "QUAL-15",
        Severity.LOW,
        Category.Quality,
        "Null check on value type -- value types cannot be null",
        "Remove null check on value types.",
        r"(int|float|double|bool|byte|char|long|short|Vector[234]|Quaternion|Color|Rect|Bounds)\s+\w+.*==\s*null",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"\?"],
    )
)

RULES.append(
    _create_rule(
        "QUAL-16",
        Severity.LOW,
        Category.Quality,
        "Dead code after return/break/continue/throw",
        "Remove unreachable statements.",
        r"(return\s+[^;]+;|break\s*;|continue\s*;|throw\s+[^;]+;)\s*$",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#(else|elif|endif)"],
        # Guard: only flag if the NEXT non-empty, non-comment, non-brace line
        # exists within the same block (not } or case:)
        guard=lambda line, all, i, ctx: (
            ctx[i] != LineContext.Comment
            and i + 1 < len(all)
            and any(
                all[j].strip() and not all[j].strip().startswith(("//", "}", "case ", "default:", "#"))
                and not all[j].strip() == "{"
                for j in range(i + 1, min(i + 3, len(all)))
            )
        ),
        layer="heuristic",
        finding_type=FindingType.STRENGTHENING,
    )
)

# =============================================================================
# GAME-SPECIFIC RULES (GAME-01 to GAME-10)
# =============================================================================

RULES.append(
    _create_rule(
        "GAME-01",
        Severity.MEDIUM,
        Category.Performance,
        "Animator parameter set with string -- use cached StringToHash ID",
        'Declare: static readonly int hashParam = Animator.StringToHash("Param"); then use the hash.',
        r'\.(SetTrigger|SetBool|SetFloat|SetInteger|GetBool|GetFloat|GetInteger|ResetTrigger)\s*\(\s*"[^"]+"',
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"StringToHash"],
    )
)

RULES.append(
    _create_rule(
        "GAME-02",
        Severity.HIGH,
        Category.Performance,
        "AudioSource.PlayClipAtPoint creates hidden GameObject -- use audio pool",
        "Implement an AudioPool or use a pooled AudioSource.PlayOneShot() instead.",
        r"AudioSource\.PlayClipAtPoint\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "GAME-03",
        Severity.HIGH,
        Category.Performance,
        "RectTransform property animated in Update -- dirties entire Canvas, forces rebuild",
        "Split UI into static and dynamic Canvases. Use CanvasGroup.alpha for fading.",
        r"(rectTransform|RectTransform)\.(sizeDelta|anchoredPosition|localPosition|offsetMin|offsetMax)\s*=",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"CanvasGroup", r"DOTween", r"PrimeTween"],
    )
)

RULES.append(
    _create_rule(
        "GAME-04",
        Severity.HIGH,
        Category.Bug,
        "ParticleSystem.main struct copy -- modifying returned copy has no effect",
        "Store in local variable first: var main = ps.main; main.startSpeed = val;",
        r"(\w+\.)?(particleSystem|GetComponent\s*<\s*ParticleSystem\s*>\s*\(\s*\))\.main\.\w+\s*=",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"var\s+\w+\s*=.*\.main"],
    )
)

RULES.append(
    _create_rule(
        "GAME-05",
        Severity.HIGH,
        Category.Bug,
        "ParticleSystem.Play() called every frame without isPlaying check",
        "Guard with: if (!ps.isPlaying) ps.Play();",
        r"\b[A-Za-z_]\w*\.Play\s*\(\s*\)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"isPlaying", r"if\s*\("],
        guard=_is_particle_system_play,
    )
)

RULES.append(
    _create_rule(
        "GAME-06",
        Severity.CRITICAL,
        Category.Bug,
        "Async Task in MonoBehaviour without CancellationToken -- orphaned task after Destroy",
        "Pass destroyCancellationToken or this.GetCancellationTokenOnDestroy().",
        r"async\s+(Task|UniTask)\s+\w+\s*\([^)]*\)",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"CancellationToken",
            r"destroyCancellationToken",
            r"GetCancellationTokenOnDestroy",
        ],
    )
)

RULES.append(
    _create_rule(
        "GAME-07",
        Severity.LOW,
        Category.Performance,
        "Rigidbody.velocity direct assignment -- use AddForce with ForceMode.VelocityChange",
        "Use rb.AddForce(velocity, ForceMode.VelocityChange) for physics-correct velocity changes. Direct assignment is correct for teleporting/resetting.",
        r"\.\s*velocity\s*=\s*(?!Vector3\.zero)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"isKinematic", r"kinematic"],
        confidence=40,
        finding_type=FindingType.STRENGTHENING,
        layer="heuristic",
    )
)

RULES.append(
    _create_rule(
        "GAME-08",
        Severity.MEDIUM,
        Category.Performance,
        ".Count() LINQ method on List/Array -- use .Count/.Length property instead",
        "Use collection.Count (List) or array.Length directly -- O(1) vs O(n).",
        r"\.(Count|Any|All)\s*\(\s*\)",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"\.Length\b", r"\.Count\b(?!\s*\()"],
    )
)

RULES.append(
    _create_rule(
        "GAME-09",
        Severity.HIGH,
        Category.Bug,
        "SendWebRequest() without yield/await -- fire-and-forget web request, result never observed",
        "Use: yield return request.SendWebRequest(); or await request.SendWebRequest();",
        r"\.SendWebRequest\s*\(\s*\)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"yield\s+return", r"await\s"],
    )
)

RULES.append(
    _create_rule(
        "GAME-10",
        Severity.MEDIUM,
        Category.Bug,
        "SetTrigger in Update without state check -- causes trigger queue buildup",
        'Check animator state first: if (!animator.GetCurrentAnimatorStateInfo(0).IsName("Attack"))',
        r"\.SetTrigger\s*\(",
        scope="HotPath",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"GetCurrentAnimatorStateInfo",
            r"IsInTransition",
        ],
    )
)

# =============================================================================
# ADDITIONAL BUG RULES AND SPECIAL RULES
# =============================================================================

RULES.append(
    _create_rule(
        "BUG-41",
        Severity.MEDIUM,
        Category.Bug,
        "StartCoroutine with string method name -- no compile-time safety, uses reflection",
        "Use StartCoroutine(MethodName()) with IEnumerator return value.",
        r'StartCoroutine\s*\(\s*"[^"]*"\)',
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
    )
)

RULES.append(
    _create_rule(
        "BUG-42",
        Severity.MEDIUM,
        Category.Bug,
        "new WaitUntil/WaitWhile allocated every yield -- cache as field",
        "Declare a WaitUntil/WaitWhile field and reuse it.",
        r"yield\s+return\s+new\s+Wait(Until|While)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"_wait\w+\s*=\s*new\s+Wait(Until|While)"],
    )
)

RULES.append(
    _create_rule(
        "BUG-43",
        Severity.LOW,
        Category.Bug,
        "Float equality comparison -- use Mathf.Approximately",
        "Use Mathf.Approximately(a, b) instead of a == b for floats.",
        r"(?<!\w)([a-zA-Z_]\w*)\s*==\s*(\d+\.?\d*f?|[a-zA-Z_]\w*)\s*[;)\]]",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Mathf\.Approximately", r"\.Equals"],
        guard=lambda line, all_lines, idx, ctx=None: (
            # Only fire when comparing float-like values (contain "." or common float field names)
            # Suppress comparisons that are clearly non-float (string, bool, int, enum, object refs)
            not bool(re.search(
                r'\b(true|false|null|"")\s*;$'
                r'|\.Count\s*==|\.Length\s*==|\.count\s*==|\.length\s*=='
                r'|\bslotIndex\b|\bindex\b|\bId\b|\bid\b|\bID\b|\bCount\b|\bLength\b',
                line,
            ))
            and bool(re.search(
                r'\b(distance|dist|angle|magnitude|sqrMagnitude|speed|velocity|time|delta'
                r'|height|width|radius|scale|alpha|opacity|intensity|threshold'
                r'|position|rotation|euler)\b',
                line, re.IGNORECASE,
            ))
        ),
    )
)

RULES.append(
    _create_rule(
        "BUG-44",
        Severity.HIGH,
        Category.Bug,
        "Assigning to transform.position.x/y/z -- does nothing (struct copy)",
        "Store position in local var, modify, then assign back: var p = transform.position; p.x = val; transform.position = p;",
        r"transform\.(position|localPosition|rotation|localRotation|eulerAngles|localEulerAngles)\.\w+\s*[+\-*/]?=",
        scope="AnyMethod",
        confidence=95,
    )
)

RULES.append(
    _create_rule(
        "BUG-45",
        Severity.MEDIUM,
        Category.Bug,
        "AddForce without ForceMode -- defaults to ForceMode.Force (mass-dependent)",
        "Specify ForceMode explicitly: ForceMode.Impulse for instant, ForceMode.VelocityChange for mass-independent.",
        r"\.AddForce\s*\([^)]*\)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"ForceMode"],
        confidence=55,
    )
)

RULES.append(
    _create_rule(
        "BUG-47",
        Severity.MEDIUM,
        Category.Bug,
        "Coroutine with no yield return -- runs synchronously, not as coroutine",
        "Add at least one yield return statement, or convert to a regular method.",
        r"IEnumerator\s+\w+\s*\([^)]*\)\s*\{",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"yield\s+return", r"yield\s+break"],
        anti_radius=30,
        confidence=60,
    )
)

RULES.append(
    _create_rule(
        "BUG-48",
        Severity.HIGH,
        Category.Bug,
        "Destroy() on a component removes only the component, not the GameObject",
        "Use Destroy(gameObject) to remove the entire GameObject, or Destroy(component) intentionally.",
        r"Destroy\s*\(\s*(?:this|GetComponent)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"gameObject"],
        confidence=55,
    )
)

RULES.append(
    _create_rule(
        "BUG-49",
        Severity.CRITICAL,
        Category.Bug,
        "Infinite while(true) loop without yield/break/return in coroutine",
        "Add yield return null or yield return new WaitForSeconds() inside the loop.",
        r"while\s*\(\s*true\s*\)\s*\{",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"yield\s+return",
            r"yield\s+break",
            r"break\s*;",
            r"return\s*;",
        ],
        anti_radius=15,
    )
)

# BUG-51 and BUG-52 removed: exact duplicates of BUG-41 and BUG-42

RULES.append(
    _create_rule(
        "BUG-53",
        Severity.HIGH,
        Category.Bug,
        "Sprite.Create() without Destroy -- leaks native memory",
        "Call Destroy(sprite) when no longer needed, or pool created sprites.",
        r"Sprite\.Create\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"Destroy\s*\(",
            r"DestroyImmediate",
            r"Object\.Destroy",
            r"_sprite\s*=\s*Sprite\.Create",
        ],
        anti_radius=15,
    )
)

RULES.append(
    _create_rule(
        "BUG-54",
        Severity.HIGH,
        Category.Bug,
        "Animator.enabled = false resets state machine -- use speed = 0 to pause",
        "Set animator.speed = 0f to pause. Only disable Animator in OnDisable/OnDestroy.",
        r"animator\w*\.enabled\s*=\s*false",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.speed\s*=\s*0",
            r"OnDisable",
            r"OnDestroy",
        ],
    )
)

RULES.append(
    _create_rule(
        "BUG-55",
        Severity.HIGH,
        Category.Bug,
        "await in OnDestroy/OnDisable -- continuation runs after object destruction",
        "Use destroyCancellationToken (Unity 2023+) or avoid async in teardown.",
        r"await\s+",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"destroyCancellationToken",
            r"CancellationToken",
        ],
        guard=_is_await_in_teardown,
    )
)

RULES.append(
    _create_rule(
        "BUG-56",
        Severity.MEDIUM,
        Category.Bug,
        "Accumulating eulerAngles causes gimbal lock and 0/360 wrapping artifacts",
        "Use transform.Rotate(delta) or accumulate in a Vector3 field, then apply: transform.rotation = Quaternion.Euler(accum);",
        r"\.eulerAngles\s*\+=",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Quaternion\.Euler", r"Rotate\s*\("],
        confidence=65,
    )
)

RULES.append(
    _create_rule(
        "BUG-57",
        Severity.HIGH,
        Category.Bug,
        "UnityWebRequest downloadHandler accessed without checking .result -- silent failure on network errors",
        "Check: if (request.result == UnityWebRequest.Result.Success) before accessing .downloadHandler.text/data.",
        r"\.downloadHandler\.(text|data|bytes)\b",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.result\s*[!=]=",
            r"\.isNetworkError",
            r"\.isHttpError",
            r"ConnectionError",
            r"ProtocolError",
            r"Success",
        ],
        anti_radius=10,
    )
)

# =============================================================================
# SPECIAL RULES (SAVE, TWEEN, THREAD, ITER, BUILD)
# =============================================================================

RULES.append(
    _create_rule(
        "SAVE-01",
        Severity.CRITICAL,
        Category.Security,
        "BinaryFormatter is a critical security vulnerability -- arbitrary code execution via deserialization",
        "Use JSON (JsonUtility, Newtonsoft), MessagePack, or a custom binary serializer.",
        r"BinaryFormatter",
        scope="AnyMethod",
    )
)

RULES.append(
    _create_rule(
        "TWEEN-01",
        Severity.HIGH,
        Category.Bug,
        "DOTween/PrimeTween not killed in OnDestroy -- tween continues on destroyed object",
        "Kill tweens in OnDestroy: transform.DOKill() or Tween.Kill().",
        r"\.(DOFade|DOScale|DOMove|DORotate|DOColor|DOLocalMove|DOAnchorPos|DOSizeDelta|DOPunchScale|DOShakePosition)\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.DOKill\s*\(",
            r"\.Kill\s*\(",
            r"DOTween\.Kill",
            r"OnDestroy",
        ],
        anti_radius=30,
    )
)

RULES.append(
    _create_rule(
        "THREAD-01",
        Severity.CRITICAL,
        Category.Bug,
        "Task.Run creates thread pool thread -- cannot access Unity API from background thread",
        "Use UniTask.RunOnThreadPool with SwitchToMainThread, or use coroutines.",
        r"Task\.Run\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR", r"/Editor/"],
    )
)

RULES.append(
    _create_rule(
        "ITER-01",
        Severity.HIGH,
        Category.Bug,
        "Modifying collection during iteration -- InvalidOperationException",
        "Collect items to remove in a separate list, then remove after the loop.",
        r"\.Remove\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.ToList\s*\(\s*\)",
            r"for\s*\(\s*int",
            r"_iterationBuffer|_buffer|_toRemove|_pendingRemov",
            r"new\s+List<.*>\(\s*\w",  # new List<T>(source) — copy constructor, not empty init
            r"_removalQueue|_removeList|_toDelete|_pendingDeletes",
            r"\.Except\s*\(",
            r"\.RemoveAll\s*\(",
        ],
        anti_radius=20,
        # Only flag if iterating the SAME collection being removed from.
        # Two-pass removal (iterate buffer, remove from main) is safe.
        guard=lambda line, all_lines, idx, ctx=None: _iter01_same_collection_guard(line, all_lines, idx),
    )
)

RULES.append(
    _create_rule(
        "BUILD-01",
        Severity.CRITICAL,
        Category.Bug,
        "using UnityEditor outside #if UNITY_EDITOR -- causes build failure",
        "Wrap in #if UNITY_EDITOR / #endif or move to Editor/ folder.",
        r"^using\s+UnityEditor",
        scope="FileLevel",
        file_filter="Runtime",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR", r"[/\\]Editor[/\\]", r"[/\\]Tests[/\\]"],
    )
)

# =============================================================================
# NEW RULES: Save / Async / Lifecycle / VFX bugs
# =============================================================================

# SAVE-02: Delete before verified write (data loss on write failure)
RULES.append(
    _create_rule(
        "SAVE-02",
        Severity.CRITICAL,
        Category.Bug,
        "File/slot deleted before replacement write is verified -- data loss on write failure",
        "Write the replacement first, verify success, then delete the old data.",
        r"(Delete|Remove)(Slot|Save|File)\w*\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"if\s*\(!?\s*\w+\)\s*(return|throw)"],
        confidence=80,
        guard=lambda line, all_lines, idx, ctx=None: (
            # Only fire if there's a write/save call nearby AFTER the delete (indicating
            # delete-before-write pattern). User-initiated deletes are intentional.
            any(
                re.search(r"(Save|Write|Create)\w*\s*\(", all_lines[j])
                for j in range(idx + 1, min(len(all_lines), idx + 15))
            )
        ),
    )
)

# ASYNC-01: TaskCompletionSource without cancellation/timeout
RULES.append(
    _create_rule(
        "ASYNC-01",
        Severity.HIGH,
        Category.Bug,
        "TaskCompletionSource without cancellation path -- can hang forever if completion never fires",
        "Add a CancellationToken or timeout to prevent infinite await.",
        r"new\s+TaskCompletionSource",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"CancellationToken", r"CancelAfter", r"TimeSpan", r"timeout", r"Timer"],
        anti_radius=30,
        confidence=78,
    )
)

# ASYNC-02: Ignoring async Task return value
RULES.append(
    _create_rule(
        "ASYNC-02",
        Severity.HIGH,
        Category.Bug,
        "Async operation result ignored -- failure goes undetected",
        "Check the return value: if (!await SaveAsync()) { /* handle failure */ }",
        r"await\s+\w+\.(Save|Write|Delete|Create|Load)Async\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"(bool|var|if)\s+\w+\s*=\s*await", r"if\s*\(\s*!?\s*await"],
        confidence=72,
    )
)

# SAVE-03: State committed before I/O verified
RULES.append(
    _create_rule(
        "SAVE-03",
        Severity.HIGH,
        Category.Bug,
        "State committed to fields before async I/O is verified -- partial state on failure",
        "Only update in-memory state after the write succeeds, or snapshot/restore on failure.",
        r"_current\w+\s*=\s*(?!null)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        guard=lambda line, all, i, ctx: any(
            re.search(r"(Save|Write|Flush|Persist)Async\s*\(", all[j])
            for j in range(i + 1, min(i + 10, len(all)))
        ),
        confidence=65,
        layer="semantic",
    )
)

# BUG-64: Shared mutable buffer returned from method
RULES.append(
    _create_rule(
        "BUG-64",
        Severity.HIGH,
        Category.Bug,
        "Method returns a shared pre-allocated collection -- callers see stale data after next call",
        "Return a new List<T>(buffer), accept a caller-provided list, or return IReadOnlyList<T>.",
        r"return\s+_\w*(buffer|Buffer|temp|Temp|cache|Cache|result|Result)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"new\s+List", r"\.ToList\(\)", r"\.AsReadOnly\(\)", r"IReadOnly"],
        confidence=72,
        layer="semantic",
    )
)

# BUG-65: Static readonly mutable collection
RULES.append(
    _create_rule(
        "BUG-65",
        Severity.MEDIUM,
        Category.Bug,
        "Static readonly mutable collection -- readonly prevents reassignment but callers can still Add/Remove items",
        "Use Array.Empty<T>(), ReadOnlyCollection<T>, or ImmutableList<T> instead.",
        r"static\s+readonly\s+(List|Dictionary|HashSet|Queue|Stack|LinkedList|SortedList|SortedDictionary)<",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"ReadOnly", r"Immutable", r"Frozen"],
        confidence=88,
        guard=lambda line, all_lines, idx, ctx=None: (
            # Only fire if the collection is actually mutated somewhere in the file.
            # Suppress for lookup tables that are initialized inline and never modified.
            _static_collection_is_mutated(line, all_lines)
        ),
    )
)

# LIFECYCLE-01: Static field in MonoBehaviour without RuntimeInitializeOnLoadMethod reset
RULES.append(
    _create_rule(
        "LIFECYCLE-01",
        Severity.MEDIUM,
        Category.Unity,
        "Static field in MonoBehaviour without [RuntimeInitializeOnLoadMethod] reset -- stale across Editor play sessions",
        "Add [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)] static void ResetStatics() to clear static fields.",
        r"private\s+static\s+(?!readonly|const|event|Action|Func|delegate)\w+\s+_\w+",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"RuntimeInitializeOnLoadMethod", r"SubsystemRegistration"],
        anti_radius=50,
        confidence=65,
        layer="semantic",
    )
)

# VFX-01: Runtime material creation without destroy
RULES.append(
    _create_rule(
        "VFX-01",
        Severity.MEDIUM,
        Category.Bug,
        "Runtime material created with new Material() -- must Destroy() in OnDestroy to avoid GPU leak",
        "Store the material reference and call Destroy(material) in OnDestroy.",
        r"new\s+Material\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Destroy\s*\(", r"DestroyImmediate", r"_\w+[Mm]at\w*\s*=", r"_dynamicMaterials", r"\.Add\s*\(\s*mat"],
        anti_radius=30,
        confidence=75,
    )
)

# VFX-02: Shared post-processing override mutated from multiple coroutines
RULES.append(
    _create_rule(
        "VFX-02",
        Severity.MEDIUM,
        Category.Bug,
        "Post-processing override mutated in coroutine -- concurrent coroutines will fight over the value",
        "Centralize screen effects in a single manager with priority queue for overlapping effects.",
        r"\.\s*(intensity|weight|blend)\s*\.\s*(value|Override)\s*=",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"_screenEffectManager", r"ScreenEffectQueue"],
        confidence=55,
        layer="semantic",
    )
)

# TASK-01: Task.CompletedTask returned in catch block
RULES.append(
    _create_rule(
        "TASK-01",
        Severity.HIGH,
        Category.Bug,
        "Returning Task.CompletedTask in catch block -- caller cannot detect the failure",
        "Return Task.FromException(ex) or set a failure flag the caller can check.",
        r"return\s+Task\.(CompletedTask|FromResult)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE"],
        guard=lambda line, all, i, ctx: any(
            re.search(r"\bcatch\b", all[j])
            for j in range(max(0, i - 10), i)
        ),
        confidence=85,
    )
)

# =============================================================================
# DEEP CHECKS - Advanced semantic analysis functions
# =============================================================================


def _get_context_engine(context_dict: object) -> Any:
    if isinstance(context_dict, dict):
        return context_dict.get("engine")
    return None


def _get_relative_scan_path(file_path: str, engine: Any) -> str:
    if engine is None:
        return Path(file_path).name.replace("\\", "/")
    try:
        return (
            Path(file_path)
            .resolve()
            .relative_to(engine.project_root.resolve())
            .as_posix()
        )
    except Exception:
        return Path(file_path).name.replace("\\", "/")


def _extract_csharp_variable_types(source: str) -> dict[str, str]:
    variable_types: dict[str, str] = {}
    for line in source.splitlines():
        if "(" in line and ")" in line and "{" in line:
            continue
        match = re.search(
            r"(?:public|private|protected|internal|readonly|static|const)?\s*"
            r"(?:\[[^\]]+\]\s*)?"
            r"([A-Za-z_]\w*(?:<[^>]+>)?)\s+([A-Za-z_]\w*)\s*(?:=|;)",
            line,
        )
        if match:
            variable_types[match.group(2)] = match.group(1)
    return variable_types


def _deep_destroyed_object_access(
    file_path: str, source: str, context_dict: object
) -> list[dict[str, object]]:
    engine = _get_context_engine(context_dict)
    if engine is None:
        return []

    findings: list[dict[str, object]] = []
    variable_types = _extract_csharp_variable_types(source)
    for line_no, line in enumerate(source.splitlines(), start=1):
        match = re.search(
            r"ReferenceEquals\s*\(\s*([A-Za-z_]\w*)\s*,\s*null\s*\)", line
        )
        if not match:
            continue
        variable_name = match.group(1)
        variable_type = variable_types.get(variable_name)
        if variable_type and engine.is_unity_object(variable_type):
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "Bug",
                    "line": line_no,
                    "description": "ReferenceEquals(x, null) on a Unity object bypasses destroyed-object null semantics.",
                    "fix": "Use x == null for UnityEngine.Object-derived values.",
                    "confidence": 88,
                    "priority": 82,
                }
            )
    return findings


def _deep_hot_path_propagation(
    file_path: str, source: str, context_dict: object
) -> list[dict[str, object]]:
    engine = _get_context_engine(context_dict)
    if engine is None:
        return []

    rel_file = _get_relative_scan_path(file_path, engine)
    heavy_patterns = [
        (
            re.compile(r"GetComponent\s*<"),
            "GetComponent in transitively hot method -- cache the component reference.",
        ),
        (
            re.compile(r"Camera\.main"),
            "Camera.main in transitively hot method -- cache the camera reference.",
        ),
        (
            re.compile(r"FindObjectOfType\s*[<(]"),
            "FindObjectOfType in transitively hot method -- avoid scene scans in hot path.",
        ),
        (
            re.compile(r"GameObject\.Find\s*\("),
            "GameObject.Find in transitively hot method -- cache references outside the hot path.",
        ),
    ]

    findings: list[dict[str, object]] = []
    lines = source.splitlines()
    for method_name, start_idx, end_idx in _find_method_bounds(lines):
        if not engine.is_hot_path(method_name, rel_file):
            continue
        for idx in range(start_idx, end_idx + 1):
            for pattern, description in heavy_patterns:
                if pattern.search(lines[idx]):
                    findings.append(
                        {
                            "severity": "MEDIUM",
                            "category": "Performance",
                            "line": idx + 1,
                            "description": description,
                            "fix": "Move the expensive lookup out of the lifecycle-driven call chain and cache the result.",
                            "confidence": 80,
                            "priority": 72,
                        }
                    )
    return findings


def _deep_event_memory_leak(
    file_path: str, source: str, _context_dict: object
) -> list[dict[str, object]]:
    lines = source.splitlines()
    subscription_lines = [
        idx + 1
        for idx, line in enumerate(lines)
        if re.search(r"\+=\s*[A-Za-z_]\w+\s*;", line)
        and not re.search(r"\+=\s*\d|\+=\s*\"", line)
    ]
    has_unsubscribe = any(re.search(r"-=\s*[A-Za-z_]\w+\s*;", line) for line in lines)
    has_teardown = any(
        re.search(r"\bvoid\s+(OnDisable|OnDestroy)\s*\(", line) for line in lines
    )
    if subscription_lines and not has_unsubscribe and not has_teardown:
        return [
            {
                "severity": "HIGH",
                "category": "Unity",
                "line": subscription_lines[0],
                "description": "Event subscription found with no unsubscribe path or teardown lifecycle method in the file.",
                "fix": "Add -= cleanup in OnDisable/OnDestroy or centralize subscription disposal.",
                "confidence": 82,
                "priority": 78,
            }
        ]
    return []


def _deep_coroutine_leak(
    file_path: str, source: str, _context_dict: object
) -> list[dict[str, object]]:
    lines = source.splitlines()
    start_lines = [
        idx + 1
        for idx, line in enumerate(lines)
        if re.search(r"StartCoroutine\s*\(", line)
    ]
    if not start_lines:
        return []

    has_stop = any(
        re.search(r"StopCoroutine|StopAllCoroutines", line) for line in lines
    )
    teardown_present = any(
        re.search(r"\bvoid\s+(OnDisable|OnDestroy)\s*\(", line) for line in lines
    )
    long_running = any(
        re.search(r"while\s*\(\s*true\s*\)", line)
        or re.search(r"IEnumerator\s+\w*(Loop|Repeat|Forever|Poll|Tick)", line)
        for line in lines
    )
    if long_running and not has_stop and not teardown_present:
        return [
            {
                "severity": "MEDIUM",
                "category": "Bug",
                "line": start_lines[0],
                "description": "Coroutine starts in this file but no stop path or teardown lifecycle method is present for likely long-running work.",
                "fix": "Store the Coroutine handle and stop it from OnDisable/OnDestroy, or add an explicit exit path.",
                "confidence": 74,
                "priority": 68,
            }
        ]
    return []


def _deep_null_return_consistency(
    file_path: str, source: str, _context_dict: object
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    lines = source.splitlines()
    empty_return_patterns = [
        re.compile(r"return\s+string\.Empty\s*;"),
        re.compile(r"return\s+\"\"\s*;"),
        re.compile(r"return\s+new\s+List<"),
        re.compile(r"return\s+Array\.Empty<"),
        re.compile(r"return\s+Enumerable\.Empty<"),
    ]
    for method_name, start_idx, end_idx in _find_method_bounds(lines):
        body = lines[start_idx : end_idx + 1]
        has_null = any(re.search(r"return\s+null\s*;", line) for line in body)
        has_empty = any(
            pattern.search(line) for pattern in empty_return_patterns for line in body
        )
        if has_null and has_empty:
            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "Bug",
                    "line": start_idx + 1,
                    "description": f"{method_name} mixes null and empty-object return styles, which makes callers harder to reason about.",
                    "fix": "Pick one contract (null or empty) and keep it consistent for the method.",
                    "confidence": 76,
                    "priority": 60,
                }
            )
    return findings


def _deep_type_resolution(
    file_path: str, source: str, context_dict: object
) -> list[dict[str, object]]:
    engine = _get_context_engine(context_dict)
    if engine is None:
        return []

    findings: list[dict[str, object]] = []
    variable_types = _extract_csharp_variable_types(source)
    for line_no, line in enumerate(source.splitlines(), start=1):
        match = re.search(r"\b([A-Za-z_]\w*)\s+is\s+not?\s+null\b", line)
        if not match:
            match = re.search(r"\b([A-Za-z_]\w*)\s+is\s+null\b", line)
        if not match:
            continue
        variable_name = match.group(1)
        variable_type = variable_types.get(variable_name)
        if variable_type and engine.is_unity_object(variable_type):
            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "Unity",
                    "line": line_no,
                    "description": f"{variable_name} appears to be a Unity object, so 'is null' bypasses Unity's destroyed-object semantics.",
                    "fix": "Use == null / != null when checking UnityEngine.Object-derived values.",
                    "confidence": 83,
                    "priority": 70,
                }
            )
    return findings


def _deep_incomplete_state_clearing(
    file_path: str, source: str, _context_dict: object
) -> list[dict[str, object]]:
    """DEEP-07: Detect Clear/Reset/OnCombatEnd/OnDisable/Initialize methods that
    clear SOME but not ALL tracking collections in a class."""
    findings: list[dict[str, object]] = []
    lines = source.splitlines()

    # First pass: find all collection fields (List, Dictionary, HashSet, Queue)
    collection_fields: set[str] = set()
    collection_field_re = re.compile(
        r"(?:private|protected|public|internal)\s+"
        r"(?:readonly\s+)?"
        r"(?:List|Dictionary|HashSet|Queue|Stack|LinkedList|SortedList|SortedSet)<[^>]+>\s+"
        r"([A-Za-z_]\w*)\s*[;=]"
    )
    for line in lines:
        m = collection_field_re.search(line)
        if m:
            collection_fields.add(m.group(1))

    if len(collection_fields) < 2:
        return findings

    # Second pass: find reset/clear methods and check which collections they clear
    clear_call_re = re.compile(r"\b([A-Za-z_]\w*)\.Clear\s*\(")

    for method_name, start_idx, end_idx in _find_method_bounds(lines):
        # Check if method name matches a reset/clear pattern
        if not re.search(
            r"^(Clear|Reset|OnCombatEnd|OnDefeat|OnDisable|Initialize|Cleanup|Dispose|Teardown)",
            method_name,
        ):
            continue

        body = lines[start_idx : end_idx + 1]
        cleared_in_method: set[str] = set()
        for body_line in body:
            for cm in clear_call_re.finditer(body_line):
                cleared_in_method.add(cm.group(1))
            # Also catch = null, = new List<>(), .Clear()
            for cf in collection_fields:
                if re.search(rf"\b{re.escape(cf)}\s*=\s*(null|new\b)", body_line):
                    cleared_in_method.add(cf)

        # Only flag if method clears at least one but not all
        relevant = cleared_in_method & collection_fields
        missed = collection_fields - cleared_in_method
        if relevant and missed and len(missed) <= len(collection_fields) // 2 + 1:
            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "Bug",
                    "line": start_idx + 1,
                    "description": (
                        f"{method_name}() clears {len(relevant)} of {len(collection_fields)} "
                        f"tracking collections but misses: {', '.join(sorted(missed)[:5])}"
                    ),
                    "fix": "Ensure all tracking collections are cleared in the reset path to avoid stale state.",
                    "confidence": 68,
                    "priority": 62,
                }
            )
    return findings


def _deep_task_awaitable_mixing(
    file_path: str, source: str, _context_dict: object
) -> list[dict[str, object]]:
    """DEEP-08: Find methods returning Awaitable that await Task (not Awaitable),
    then check if Awaitable.MainThreadAsync() follows before Unity API calls."""
    findings: list[dict[str, object]] = []
    lines = source.splitlines()

    # Unity API patterns that require main thread
    unity_api_re = re.compile(
        r"\b(transform|gameObject|GetComponent|Instantiate|Destroy|"
        r"SetActive|enabled|position|rotation|localScale|"
        r"Debug\.Log|Application\.)\b"
    )

    for method_name, start_idx, end_idx in _find_method_bounds(lines):
        # Check if method returns Awaitable (Unity 6+)
        decl_line = lines[start_idx] if start_idx < len(lines) else ""
        if not re.search(r"\bAwaitable\b", decl_line):
            continue

        body = lines[start_idx : end_idx + 1]
        body_text = "\n".join(body)

        # Check if it awaits a Task (not Awaitable)
        awaits_task = bool(re.search(r"await\s+(?:Task\.|UniTask\.|\w+\.Run)", body_text))
        if not awaits_task:
            continue

        # Check if MainThreadAsync is called after the Task await
        has_main_thread_return = bool(
            re.search(r"Awaitable\s*\.\s*MainThreadAsync|SwitchToMainThread", body_text)
        )

        # Check if Unity API is used after the await
        task_await_idx = None
        for bi, bline in enumerate(body):
            if re.search(r"await\s+(?:Task\.|UniTask\.|\w+\.Run)", bline):
                task_await_idx = bi
                break

        if task_await_idx is not None:
            remaining = body[task_await_idx + 1 :]
            uses_unity_after = any(unity_api_re.search(rl) for rl in remaining)

            if uses_unity_after and not has_main_thread_return:
                findings.append(
                    {
                        "severity": "HIGH",
                        "category": "Bug",
                        "line": start_idx + task_await_idx + 1,
                        "description": (
                            f"{method_name}() returns Awaitable but awaits a Task -- "
                            f"Unity API calls after the await may run off the main thread"
                        ),
                        "fix": "Call await Awaitable.MainThreadAsync() after the Task await and before any Unity API usage.",
                        "confidence": 74,
                        "priority": 72,
                    }
                )
    return findings


def _deep_task_cancellation(
    filepath: str, source: str, _context_dict: object
) -> list[dict[str, Any]]:
    """DEEP-09: Find async methods without CancellationToken parameter that await long-running ops."""
    findings = []
    lines = source.splitlines()

    # Find async method boundaries and whether they accept CancellationToken
    method_has_token: dict[int, bool] = {}  # method_start_line -> has_token
    current_method_start = -1
    current_method_has_token = False
    brace_depth = 0

    for i, line in enumerate(lines):
        # Detect async method signature
        if re.search(r"\basync\s+(?:Task|UniTask|Awaitable|void)\b", line):
            current_method_start = i
            current_method_has_token = "CancellationToken" in line
            brace_depth = 0
        # Track braces
        brace_depth += line.count("{") - line.count("}")
        if current_method_start >= 0 and brace_depth <= 0 and "}" in line:
            method_has_token[current_method_start] = current_method_has_token
            current_method_start = -1

    # Only flag await lines in methods that DON'T have CancellationToken
    current_method_start = -1
    brace_depth = 0
    suppress_tokens = {
        "WithCancellation", "WaitAsync", "TimeoutAfter", "CancellationToken",
        ".Delay(", "Task.WhenAll", "Task.WhenAny", "Task.CompletedTask",
        "Task.FromResult", "Task.FromException", "yield return",
        "Awaitable.WaitForSecondsAsync", "Awaitable.NextFrameAsync",
        "UniTask.Yield", "UniTask.Delay",
    }

    for i, line in enumerate(lines):
        if re.search(r"\basync\s+(?:Task|UniTask|Awaitable|void)\b", line):
            current_method_start = i
            brace_depth = 0

        brace_depth += line.count("{") - line.count("}")

        if "await " in line and current_method_start >= 0:
            # Skip if method already has CancellationToken
            if method_has_token.get(current_method_start, False):
                continue
            # Skip if the await line has a suppression token
            if any(tok in line for tok in suppress_tokens):
                continue
            # Skip UI/coroutine-style awaits that don't need cancellation
            if re.search(r"await\s+(Awaitable\.|UniTask\.|PrimeTween|SceneManager)", line):
                continue
            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "Bug",
                    "line": i + 1,
                    "description": "Async method awaits without CancellationToken parameter — may hang indefinitely",
                    "fix": "Add CancellationToken ct = default parameter and propagate to awaited calls.",
                    "confidence": 60,
                    "priority": 55,
                }
            )

        if current_method_start >= 0 and brace_depth <= 0 and "}" in line:
            current_method_start = -1

    return findings


# =============================================================================
# NEW RULES FROM AUDIT (Phase 3)
# =============================================================================

# BUG-63: Shared Volume profile override in coroutine
RULES.append(
    _create_rule(
        "BUG-63",
        Severity.MEDIUM,
        Category.Bug,
        "Shared Volume profile override in coroutine affects all listeners",
        "Create new AudioMixerGroup or Volume profile per coroutine instance.",
        r"volumeProfile\.override\s*=\s*true",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"StartCoroutine\s*\(\s*nameof"],
        layer="semantic",
    )
)

# UNITY-32: OnDrawGizmos without HideInNormalInspector
RULES.append(
    _create_rule(
        "UNITY-32",
        Severity.LOW,
        Category.Unity,
        "OnDrawGizmos without [HideInNormalInspector] -- clutters Inspector",
        "Add [HideInNormalInspector] above OnDrawGizmos method.",
        r"\bvoid\s+OnDrawGizmos\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"HideInNormalInspector"],
        layer="heuristic",
    )
)

# SEC-14: JSON deserialization without schema validation
RULES.append(
    _create_rule(
        "SEC-14",
        Severity.MEDIUM,
        Category.Security,
        "JSON deserialization without schema validation -- injection risk",
        "Validate JSON schema before deserialization or use safe parser.",
        r"JsonUtility\.FromJson|JsonConvert\.DeserializeObject|JObject\.Parse",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"JToken\.Validate", r"Schema\.Validate"],
        layer="semantic",
    )
)

# PERF-42: LINQ .Where().ToList() in hot path
RULES.append(
    _create_rule(
        "PERF-42",
        Severity.MEDIUM,
        Category.Performance,
        "LINQ .Where().ToList() in hot path -- allocates garbage",
        "Use for-loop with manual filtering or pre-filtered collection.",
        r"\.Where\s*\([^)]+\)\.ToList\s*\(",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="heuristic",
    )
)


# =============================================================================
# HIGH-VALUE RULES FROM GAP ANALYSIS (Phase 6)
# =============================================================================

# ADDR-01: Addressables LoadAssetAsync without Release tracking
RULES.append(
    _create_rule(
        "ADDR-01",
        Severity.CRITICAL,
        Category.Bug,
        "Addressables.LoadAssetAsync/InstantiateAsync without Release tracking -- memory leak",
        "Store AsyncOperationHandle and call Addressables.Release(handle) when done.",
        r"Addressables\.(LoadAssetAsync|InstantiateAsync)\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"AsyncOperationHandle", r"\.Release\s*\("],
        layer="hard_correctness",
    )
)

# DOTS-02: NativeArray with wrong allocator
RULES.append(
    _create_rule(
        "DOTS-02",
        Severity.HIGH,
        Category.Bug,
        "NativeArray with Allocator.Temp stored in field -- memory leak or crash",
        "Use Allocator.Persistent for fields, or Dispose TempJob arrays after use.",
        r"private\s+.*NativeArray<[^>]+>\s+\w+\s*=.*Allocator\.Temp",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"Allocator\.Persistent", r"Allocator\.TempJob"],
        layer="hard_correctness",
    )
)

# DOTS-05: String operations in Burst jobs
RULES.append(
    _create_rule(
        "DOTS-05",
        Severity.HIGH,
        Category.Bug,
        "String/ToString() in Burst job -- Burst compilation fails or GC pressure",
        "Use FixedString, NativeText, or pre-convert outside job.",
        r"\.ToString\s*\(\)|string\s+\w+\s*=|\".*\"\s*\+",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"FixedString", "NativeText", "BurstCompile"],
        guard=lambda line, all, i, ctx: any("IJob" in line or "BurstCompile" in line for line in all[max(0,i-10):i+1]),
        layer="semantic",
    )
)

# ASYNC-03: Task.Result/.Wait() deadlock risk
RULES.append(
    _create_rule(
        "ASYNC-03",
        Severity.HIGH,
        Category.Bug,
        "Task.Result or .Wait() on Unity main thread -- potential deadlock",
        "Use await or UniTask.RunOnThreadPool with proper context switching.",
        r"\.(Result|Wait)\s*\(\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"ConfigureAwait\(false\)", r"RunOnThreadPool"],
        layer="hard_correctness",
    )
)

# DOTS-01: ref struct stored in class field
RULES.append(
    _create_rule(
        "DOTS-01",
        Severity.HIGH,
        Category.Bug,
        "ref struct (NativeArray, Entity, etc.) stored in class field -- silent corruption",
        "ref structs must be stack-allocated only. Use struct or class instead.",
        r"(private|public|protected|internal)\s+.*\s+\w+\s*;\s*//.*ref|NativeArray<|Entity\s+",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"const\s+", r"static\s+readonly"],
        guard=lambda line, all, i, ctx: any(stw in line for stw in ["NativeArray", "NativeContainer", "EntityRef", "EntityCommand"]),
        layer="semantic",
    )
)

# DOTS-03: Jobs without dependency chain
RULES.append(
    _create_rule(
        "DOTS-03",
        Severity.HIGH,
        Category.Bug,
        "Multiple jobs scheduled without JobHandle dependency -- race condition",
        "Chain JobHandles: JobHandle jh = job1.Schedule(); job2.Schedule(jh);",
        r"\.Schedule\s*\(\s*\)",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"JobHandle\s+\w+\s*=", r"\.Schedule\s*\([^)]+\)"],
        guard=lambda line, all, i, ctx: sum(1 for line in all[max(0,i-3):i+1] if ".Schedule(" in line) > 1,
        layer="semantic",
    )
)

# UNITY-33: Scene reference in prefab (runtime break)
RULES.append(
    _create_rule(
        "UNITY-33",
        Severity.HIGH,
        Category.Unity,
        "Prefab referencing scene object -- breaks on instantiation",
        "Use events, interfaces, or runtime FindObjectOfType instead.",
        r"(public|private|protected|internal)\s+GameObject\s+\w+;\s*//.*scene",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"FindObjectOfType", "GetComponent", "SerializeField"],
        layer="heuristic",
    )
)

# ASYNC-04: Missing CancellationToken
RULES.append(
    _create_rule(
        "ASYNC-04",
        Severity.MEDIUM,
        Category.Bug,
        "Async method without CancellationToken -- cannot cancel operation",
        "Add CancellationToken ct = default parameter to async methods.",
        r"async\s+Task<[^>]*>\s+\w+\s*\([^)]*\)\s*{",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"CancellationToken", r"IProgress", r"await\s+Task\.CompletedTask"],
        layer="semantic",
    )
)

# INPUT-01: Input polling in Update instead of callbacks
RULES.append(
    _create_rule(
        "INPUT-01",
        Severity.MEDIUM,
        Category.Unity,
        "Input polling in Update instead of InputAction callbacks -- less responsive",
        "Use inputAction.performed += ctx => ... for better responsiveness and rebinding.",
        r"(Keyboard|Mouse|Gamepad|Input)\.current\.\w+\.wasPressedThisFrame",
        scope="HotPath",
        anti_patterns=[r"//\s*VB-IGNORE", r"\.performed\s*\+=", r"\.Invoke\s*\("],
        layer="heuristic",
    )
)

# PERF-40: Struct with reference type fields
RULES.append(
    _create_rule(
        "PERF-40",
        Severity.MEDIUM,
        Category.Performance,
        "Struct containing reference type (string, class, array) -- boxing, poor cache locality",
        "Use class for reference types, or use ref-only fields in struct.",
        r"struct\s+\w+\s*{[^}]*}(string|List<|Dictionary<|IEnumerable<|class\s+\w+)",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"readonly\s+struct", r"ref\s+struct"],
        layer="semantic",
    )
)


# PERF-43: FindObjectsByType / FindObjectsOfType in hot path or per-event code
RULES.append(
    _create_rule(
        "PERF-43",
        Severity.MEDIUM,
        Category.Performance,
        "FindObjectsByType/FindObjectsOfType per event -- cache the result",
        "Cache the result in a field during Awake/Start or subscribe to creation/destruction events.",
        r"FindObjects(?:ByType|OfType)\s*[<(]",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"void\s+(Awake|Start|OnEnable)\s*\(",
            r"_cached|_instances|_all\w+",
        ],
        layer="hard_correctness",
    )
)

# BUG-66: ComputeBuffer leak detection
RULES.append(
    _create_rule(
        "BUG-66",
        Severity.HIGH,
        Category.Bug,
        "ComputeBuffer created without Release/Dispose -- GPU memory leak",
        "Call buffer.Release() in OnDestroy or use a using block.",
        r"new\s+ComputeBuffer\s*\(",
        scope="AnyMethod",
        anti_patterns=[
            r"//\s*VB-IGNORE",
            r"\.Release\s*\(",
            r"\.Dispose\s*\(",
            r"using\s*\(",
        ],
        layer="hard_correctness",
    )
)

# UNITY-34: SerializeField on property (silently ignored)
RULES.append(
    _create_rule(
        "UNITY-34",
        Severity.HIGH,
        Category.Bug,
        "[SerializeField] on property is silently ignored by Unity serializer",
        "Move [SerializeField] to a backing field, not a property.",
        r"\[SerializeField\]\s*(public|private|protected)\s+\w+\s+\w+\s*\{",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE"],
        layer="hard_correctness",
    )
)

# QUAL-17: Exception swallowing in catch returning default
RULES.append(
    _create_rule(
        "QUAL-17",
        Severity.MEDIUM,
        Category.Bug,
        "Catch block returns default value -- caller cannot detect failure",
        "Return Task.FromException(ex), throw, or set a failure flag.",
        r"catch\s*(\([^)]*\))?\s*\{[^}]*return\s+(null|default|0|false)\s*;",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"//\s*intentional"],
        layer="semantic",
        flags=re.DOTALL,
    )
)


# LIFECYCLE-02: Application.persistentDataPath in static field initializer
RULES.append(
    _create_rule(
        "LIFECYCLE-02",
        Severity.CRITICAL,
        Category.Bug,
        "Application.persistentDataPath in static initializer -- may crash before Unity runtime initializes",
        "Use a lazy property or initialize in Awake/Start instead of static readonly.",
        r"static\s+(?:readonly\s+)?string\s+\w+\s*=\s*[^>]*Application\.persistentDataPath",
        scope="ClassLevel",
        anti_patterns=[r"//\s*VB-IGNORE", r"\?\?="],
        layer="hard_correctness",
    )
)

# BUG-67: DestroyImmediate in runtime code
RULES.append(
    _create_rule(
        "BUG-67",
        Severity.MEDIUM,
        Category.Bug,
        "DestroyImmediate used at runtime -- bypasses normal destruction pipeline, use Destroy() instead",
        "Replace with Destroy(obj) at runtime. DestroyImmediate is only safe in Editor code.",
        r"DestroyImmediate\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"#if\s+UNITY_EDITOR", r"/Editor/"],
        layer="hard_correctness",
    )
)

# BUG-68: Fire-and-forget async (discarded Task)
RULES.append(
    _create_rule(
        "BUG-68",
        Severity.HIGH,
        Category.Bug,
        "Fire-and-forget async -- unobserved Task exceptions and potential race conditions",
        "Await the task, use UniTask.Forget() with error handling, or store in a field for cancellation.",
        r"_\s*=\s*\w+Async\s*\(",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"UniTask\.Forget", r"FireAndForget", r"ContinueWith"],
        layer="hard_correctness",
    )
)

# BUG-69: Time.fixedDeltaTime set to timeScale * base (becomes 0 when paused)
RULES.append(
    _create_rule(
        "BUG-69",
        Severity.HIGH,
        Category.Bug,
        "fixedDeltaTime set proportional to timeScale -- becomes 0 when game is paused, breaking physics",
        "Clamp fixedDeltaTime to a minimum value or skip the update when timeScale is 0.",
        r"Time\.fixedDeltaTime\s*=\s*.*Time\.timeScale",
        scope="AnyMethod",
        anti_patterns=[r"//\s*VB-IGNORE", r"Mathf\.Max", r"Mathf\.Clamp"],
        layer="hard_correctness",
    )
)


def _deep_dead_field(
    filepath: str, content: str, context: Any
) -> list[dict]:
    """Detect fields that are SET (assigned to) but never READ in method logic.

    This catches bugs like GambitController._forcedTarget which is set via
    SetForcedTarget() but never read in DecideAndAct().
    """
    findings: list[dict] = []
    lines = content.split("\n")

    # Phase 1: Find private/protected fields with setter methods
    field_pattern = re.compile(
        r"(?:private|protected)\s+\w+(?:<[^>]+>)?\s+(_\w+)\s*[;=]"
    )
    # Skip common Unity patterns that are written by framework but read implicitly
    skip_patterns = re.compile(
        r"(_coroutine|Coroutine|_tween|_cts|_token|_cancellation|_audioSource"
        r"|_renderer|_collider|_rigidbody|_animator|_image|_text|_button"
        r"|_canvas|_panel|_container|_element|_label|_slider|_toggle"
        r"|_style|_template|_document|_root|_visual|_overlay|_transform"
        r"|SerializeField|Header|Tooltip)", re.IGNORECASE
    )
    fields: dict[str, int] = {}  # name -> line number
    for i, line in enumerate(lines):
        m = field_pattern.search(line)
        if m and not re.search(r"(const|static\s+readonly|event\s)", line):
            if not skip_patterns.search(line):
                fields[m.group(1)] = i + 1

    if not fields:
        return findings

    # Phase 2: For each field, check if it's written AND read
    for field_name, def_line in fields.items():
        escaped = re.escape(field_name)
        writes = 0
        read_lines: set[int] = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            # Check for writes: field = value, field.Set(), field.Clear()
            if re.search(rf"{escaped}\s*=\s*[^=]", line) and i + 1 != def_line:
                writes += 1
            if re.search(rf"{escaped}\.(Clear|Set|Add|Remove|Enqueue|Push)\s*\(", line):
                writes += 1
            # Check for reads: field in conditions, returns, method args, RHS of assignments
            # Use a set so multiple patterns matching the same line don't double-count.
            if re.search(rf"(?:if|while|return|&&|\|\|)\s*.*{escaped}", line):
                read_lines.add(i)
            if re.search(rf"\(\s*.*{escaped}", line) and not re.search(rf"^\s*{escaped}\s*=", line):
                read_lines.add(i)
            if re.search(rf"\b{escaped}\b\.", line) and not re.search(rf"^\s*{escaped}\s*[.=]", line):
                read_lines.add(i)
            # RHS of assignments to other variables: `x = _field` or `x = _field + y`
            if re.search(rf"=\s*.*{escaped}", line) and not re.search(rf"^\s*{escaped}\s*=", line):
                read_lines.add(i)
            # Used as argument: Method(_field) or Method(x, _field)
            if re.search(rf",\s*{escaped}\b|\(\s*{escaped}\b", line):
                read_lines.add(i)
            # Property getter body
            if re.search(rf"=>\s*{escaped}\s*;", line):
                read_lines.add(i)
            # Interpolation: $"...{_field}..."
            if re.search(rf"\{{{escaped}", line):
                read_lines.add(i)

        reads = len(read_lines)
        if writes >= 3 and reads == 0:
            findings.append({
                "line": def_line,
                "severity": "HIGH",
                "category": "Bug",
                "description": f"Field '{field_name}' is written {writes} times but never read in conditions or logic -- likely dead code or missing integration",
                "fix": f"Wire '{field_name}' into the decision logic that should use it, or remove the field.",
                "confidence": 78,
                "priority": 75,
            })

    return findings


def _deep_singleton_ready_check(
    filepath: str, content: str, context: Any
) -> list[dict]:
    """Detect singleton data access before async initialization completes.

    Pattern: class has IsReady/IsInitialized and an async init, but public
    getters don't check the ready flag.
    """
    findings: list[dict] = []
    lines = content.split("\n")

    has_ready = any(re.search(r"\b(IsReady|IsInitialized|IsLoaded)\b", line) for line in lines)
    has_async_init = any(re.search(r"async\s+Task\s+\w*(Init|Load|Setup)\w*Async", line) for line in lines)

    if not has_ready or not has_async_init:
        return findings

    # Find public methods that return data without checking IsReady
    for i, line in enumerate(lines):
        m = re.search(r"public\s+\w+(?:<[^>]+>)?\s+(\w+)\s*\(", line)
        if not m:
            continue
        method_name = m.group(1)
        if method_name in ("Awake", "Start", "OnDestroy", "OnEnable", "OnDisable"):
            continue
        if "Async" in method_name or "Init" in method_name:
            continue

        # Find the method's closing brace by tracking brace depth
        body_start = i
        brace_depth = 0
        body_end = body_start
        for k in range(body_start, len(lines)):
            brace_depth += lines[k].count("{") - lines[k].count("}")
            if k > body_start and brace_depth <= 0:
                body_end = k + 1
                break
        else:
            body_end = len(lines)
        body = "\n".join(lines[body_start:body_end])
        if re.search(r"\b(IsReady|IsInitialized|IsLoaded)\b", body):
            continue
        # Check if it returns data from a dictionary/list lookup
        if re.search(r"return\s+_\w+\[|return\s+_\w+\.TryGetValue|\.ContainsKey", body):
            findings.append({
                "line": i + 1,
                "severity": "HIGH",
                "category": "Bug",
                "description": f"Public method '{method_name}' accesses data without checking IsReady -- returns empty/null before async init completes",
                "fix": "Add 'if (!IsReady) { Debug.LogWarning(...); return default; }' at method start.",
                "confidence": 72,
                "priority": 70,
            })

    return findings


def _deep_undisposed_disposable(
    filepath: str, content: str, context: Any
) -> list[dict]:
    """Detect IDisposable fields (SemaphoreSlim, CancellationTokenSource, etc.)
    that are created but never disposed in OnDestroy or Dispose.
    """
    findings: list[dict] = []
    lines = content.split("\n")

    disposable_types = {
        "SemaphoreSlim", "CancellationTokenSource", "Timer", "FileStream",
        "StreamReader", "StreamWriter", "HttpClient", "TcpClient",
        "NetworkStream", "MemoryStream",
    }

    for i, line in enumerate(lines):
        for dtype in disposable_types:
            if re.search(rf"new\s+{dtype}\s*\(", line):
                # Extract field name
                m = re.search(rf"(\w+)\s*=\s*new\s+{dtype}", line)
                if not m:
                    continue
                field_name = m.group(1)
                # Check if Dispose/Release is called on this field
                field_disposed = any(
                    re.search(rf"{re.escape(field_name)}\s*[\?.]?\s*\.(Dispose|Release|Close)\s*\(", line)
                    for line in lines
                )
                if not field_disposed:
                    findings.append({
                        "line": i + 1,
                        "severity": "MEDIUM",
                        "category": "Bug",
                        "description": f"IDisposable '{field_name}' ({dtype}) created but never disposed -- resource leak",
                        "fix": f"Call {field_name}.Dispose() in OnDestroy() or implement IDisposable pattern.",
                        "confidence": 82,
                        "priority": 65,
                    })

    return findings


def _deep_shared_buffer_return(
    filepath: str, content: str, context: Any
) -> list[dict]:
    """Detect methods that return shared/temp collection buffers to callers.

    Pattern: method declares or clears a field named *buffer/*temp/*cache,
    fills it, then returns it. Callers get a reference that will be mutated
    on the next call.
    """
    findings: list[dict] = []
    lines = content.split("\n")
    # Find methods that clear+fill+return a shared field
    buffer_names = set()
    for i, line in enumerate(lines):
        m = re.search(r"(_\w*(buffer|Buffer|temp|Temp|cache|Cache)\w*)\.(Clear|clear)\s*\(", line)
        if m:
            buffer_names.add(m.group(1))
    for i, line in enumerate(lines):
        m = re.search(r"return\s+(" + "|".join(re.escape(b) for b in buffer_names) + r")\s*;", line) if buffer_names else None
        if m:
            findings.append({
                "line": i + 1,
                "severity": "HIGH",
                "category": "Bug",
                "description": f"Method returns shared mutable buffer '{m.group(1)}' -- callers see stale data on next call",
                "fix": f"Return new List<T>({m.group(1)}) or accept a caller-provided output list.",
                "confidence": 85,
                "priority": 80,
            })
    return findings


def _deep_unbounded_collection(
    filepath: str, content: str, context: Any
) -> list[dict]:
    """Detect Queue/List that grows via Enqueue/Add but never has size limits.

    Pattern: field is a Queue<T>, Enqueue is called, but no Dequeue/Count check
    or size limit exists near the Enqueue.
    """
    findings: list[dict] = []
    lines = content.split("\n")
    # Find Queue fields
    queue_fields = set()
    for line in lines:
        m = re.search(r"(?:private|protected)\s+Queue<\w+>\s+(_\w+)", line)
        if m:
            queue_fields.add(m.group(1))
    if not queue_fields:
        return findings
    for i, line in enumerate(lines):
        for qf in queue_fields:
            if re.search(rf"{re.escape(qf)}\.Enqueue\s*\(", line):
                # Check if there's a size limit nearby (within 5 lines above)
                has_limit = False
                for j in range(max(0, i - 5), i + 1):
                    if re.search(rf"{re.escape(qf)}\.(Count|count)\s*(>=|>|==)", lines[j]):
                        has_limit = True
                    if re.search(r"(kMax|MAX_|_max|maxSize|capacity)", lines[j], re.IGNORECASE):
                        has_limit = True
                if not has_limit:
                    findings.append({
                        "line": i + 1,
                        "severity": "MEDIUM",
                        "category": "Bug",
                        "description": f"Queue '{qf}' grows via Enqueue without size limit -- unbounded memory growth",
                        "fix": f"Add a max size check before Enqueue: if ({qf}.Count >= kMaxSize) {qf}.Dequeue();",
                        "confidence": 72,
                        "priority": 55,
                    })
                    break  # One finding per queue
    return findings


DEEP_CHECKS: dict[str, dict] = {
    "DEEP-01": {
        "name": "Destroyed Object Access",
        "description": "Detect when UnityEngine.Object == null check may be true due to destroyed object",
        "check": _deep_destroyed_object_access,
    },
    "DEEP-02": {
        "name": "Hot Path Propagation",
        "description": "Propagate hot path context from Update/FixedUpdate to called methods",
        "check": _deep_hot_path_propagation,
    },
    "DEEP-03": {
        "name": "Event Memory Leak",
        "description": "Detect Event += without corresponding -= in lifecycle methods",
        "check": _deep_event_memory_leak,
    },
    "DEEP-04": {
        "name": "Coroutine Leak",
        "description": "Detect StartCoroutine without StopCoroutine in OnDestroy",
        "check": _deep_coroutine_leak,
    },
    "DEEP-05": {
        "name": "Null Return Consistency",
        "description": "Check if methods have consistent null vs empty return patterns",
        "check": _deep_null_return_consistency,
    },
    "DEEP-06": {
        "name": "Type Resolution",
        "description": "Resolve symbol types to increase confidence of Unity.Object-specific rules",
        "check": _deep_type_resolution,
    },
    "DEEP-07": {
        "name": "Incomplete State Clearing",
        "description": "Detect reset/clear methods that clear some but not all tracking collections",
        "check": _deep_incomplete_state_clearing,
    },
    "DEEP-08": {
        "name": "Task/Awaitable Mixing",
        "description": "Find Awaitable methods that await Task without returning to main thread before Unity API calls",
        "check": _deep_task_awaitable_mixing,
    },
    "DEEP-09": {
        "name": "Task Cancellation",
        "description": "Find Task/async await without cancellation/timeout — potential hang",
        "check": _deep_task_cancellation,
    },
    "DEEP-10": {
        "name": "Shared Mutable Buffer Return",
        "description": "Detect methods returning shared/temp collection buffers to callers",
        "check": _deep_shared_buffer_return,
    },
    "DEEP-11": {
        "name": "Unbounded Queue/Collection Growth",
        "description": "Detect Queue/List that grows via Enqueue/Add but never has size limits",
        "check": _deep_unbounded_collection,
    },
    "DEEP-12": {
        "name": "Dead Field (Written But Never Read in Logic)",
        "description": "Detect fields that are SET but never used in method bodies or conditions",
        "check": _deep_dead_field,
    },
    "DEEP-13": {
        "name": "Singleton Ready-Before-Init",
        "description": "Detect data access on singletons before their async init completes",
        "check": _deep_singleton_ready_check,
    },
    "DEEP-14": {
        "name": "IDisposable Without Dispose Call",
        "description": "Detect IDisposable fields created but never disposed in OnDestroy/Dispose",
        "check": _deep_undisposed_disposable,
    },
}

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RULES",
    "DEEP_CHECKS",
    "CSharpLineClassifier",
    "Rule",
    "Severity",
    "Category",
    "FindingType",
    "Language",
    "RuleScope",
    "FileFilter",
    "LineContext",
]
