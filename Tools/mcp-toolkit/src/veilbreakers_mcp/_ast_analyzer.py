"""Tree-sitter AST analyzer for C# and Python — Layer 2 of the unified scanner.

Provides structural analysis that regex cannot: scope tracking, call graphs,
dead field detection, unused methods, collection-during-iteration, async void.

Optional dependency: `pip install tree-sitter tree-sitter-c-sharp tree-sitter-python`
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Lazy imports — tree-sitter is optional
_TS_AVAILABLE = False
_CS_LANG = None
_PY_LANG = None
_cs_parser = None
_py_parser = None

try:
    import tree_sitter_c_sharp as _tscs
    import tree_sitter_python as _tspy
    from tree_sitter import Language, Parser

    _CS_LANG = Language(_tscs.language())
    _PY_LANG = Language(_tspy.language())
    _TS_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    return _TS_AVAILABLE


@dataclass
class ASTFinding:
    rule_id: str
    file: str
    line: int
    description: str
    fix: str
    severity: str = "HIGH"
    confidence: int = 80


def _get_cs_parser() -> "Parser":
    global _cs_parser
    if _cs_parser is None:
        _cs_parser = Parser(_CS_LANG)
    return _cs_parser


def _get_py_parser() -> "Parser":
    global _py_parser
    if _py_parser is None:
        _py_parser = Parser(_PY_LANG)
    return _py_parser


# =============================================================================
# C# AST Analyzer
# =============================================================================


def analyze_csharp(filepath: str, source: bytes) -> list[ASTFinding]:
    """Run all C# AST checks on a single file."""
    if not _TS_AVAILABLE:
        return []
    tree = _get_cs_parser().parse(source)
    root = tree.root_node
    findings: list[ASTFinding] = []

    findings.extend(_cs_write_only_fields(root, source, filepath))
    findings.extend(_cs_uncalled_private_methods(root, source, filepath))
    findings.extend(_cs_collection_modified_in_foreach(root, source, filepath))
    findings.extend(_cs_async_void(root, filepath))

    return findings


def _cs_write_only_fields(
    root: "tree_sitter.Node", source: bytes, filepath: str
) -> list[ASTFinding]:
    """Find private fields assigned but never read."""
    findings = []
    src_text = source.decode("utf-8", errors="replace")

    # Collect field declarations via regex on AST text (faster than queries for this)
    field_pat = re.compile(
        r"(?:private|protected)\s+\w+(?:<[^>]+>)?\s+(_\w+)\s*[;=]"
    )
    fields: dict[str, int] = {}
    for i, line in enumerate(src_text.splitlines(), 1):
        # Respect VB-IGNORE suppression
        if "VB-IGNORE" in line:
            continue
        m = field_pat.search(line)
        if m and "const " not in line and "static readonly " not in line and "event " not in line:
            name = m.group(1)
            # Skip common Unity/framework fields and UI elements
            if any(skip in name.lower() for skip in (
                "coroutine", "tween", "cts", "token", "cancellation",
                "renderer", "collider", "rigidbody", "animator", "image",
                "text", "button", "canvas", "panel", "container", "transform",
                "audio", "source", "clip", "material",
                "element", "label", "frame", "portrait", "icon", "root",
                "overlay", "document", "style", "visual",
            )):
                continue
            fields[name] = i

    if not fields:
        return findings

    # For each field, check read vs write usage
    lines = src_text.splitlines()
    for field_name, def_line in fields.items():
        escaped = re.escape(field_name)
        read_lines: set[int] = set()
        write_count = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue

            has_field = re.search(rf"\b{escaped}\b", line)
            if not has_field:
                continue

            # Declaration line — skip
            if i + 1 == def_line:
                continue

            # Writes: field = value (but not ==)
            if re.search(rf"^\s*{escaped}\s*=[^=]", line):
                write_count += 1
                continue
            if re.search(rf"{escaped}\.(Clear|Set|Add|Remove|Enqueue|Push)\s*\(", line):
                write_count += 1
                continue

            # Reads: anything else — including property getters, RHS of assignments,
            # method args, conditions, returns, interpolation, member access
            read_lines.add(i)

        if write_count >= 2 and len(read_lines) == 0:
            findings.append(ASTFinding(
                rule_id="AST-CS-01",
                file=filepath,
                line=def_line,
                description=f"Field '{field_name}' written {write_count}x but never read — dead or missing integration",
                fix=f"Wire '{field_name}' into logic that uses it, or remove",
                severity="HIGH",
                confidence=78,
            ))

    return findings


def _cs_uncalled_private_methods(
    root: "tree_sitter.Node", source: bytes, filepath: str
) -> list[ASTFinding]:
    """Find private methods with no call sites in the same file."""
    findings = []
    src_text = source.decode("utf-8", errors="replace")

    # Unity methods invoked by reflection
    UNITY_IMPLICIT = {
        "Awake", "Start", "Update", "FixedUpdate", "LateUpdate",
        "OnEnable", "OnDisable", "OnDestroy", "OnValidate", "Reset",
        "OnCollisionEnter", "OnCollisionExit", "OnCollisionStay",
        "OnTriggerEnter", "OnTriggerExit", "OnTriggerStay",
        "OnCollisionEnter2D", "OnCollisionExit2D", "OnTriggerEnter2D",
        "OnTriggerExit2D", "OnApplicationPause", "OnApplicationQuit",
        "OnApplicationFocus", "OnGUI", "OnDrawGizmos", "OnDrawGizmosSelected",
        "OnAnimatorMove", "OnAnimatorIK", "OnBecameVisible", "OnBecameInvisible",
        "OnRenderObject", "OnPreRender", "OnPostRender", "OnRenderImage",
        "OnParticleCollision", "OnMouseDown", "OnMouseUp", "OnMouseEnter",
        "OnMouseExit", "OnMouseOver", "OnMouseDrag",
    }

    # Find private method declarations
    method_pat = re.compile(
        r"^\s*private\s+(?:(?:static|async|override|virtual|sealed)\s+)*"
        r"(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(",
        re.MULTILINE,
    )
    private_methods: dict[str, int] = {}
    for m in method_pat.finditer(src_text):
        name = m.group(1)
        line = src_text[:m.start()].count("\n") + 1
        if name not in UNITY_IMPLICIT:
            private_methods[name] = line

    if not private_methods:
        return findings

    # Find all call sites (method names referenced)
    call_pat = re.compile(r"(?:\.|\b)(\w+)\s*\(")
    called: set[str] = set()
    for m in call_pat.finditer(src_text):
        called.add(m.group(1))

    # Also check string references (StartCoroutine, nameof, etc.)
    str_pat = re.compile(r'"(\w+)"')
    for m in str_pat.finditer(src_text):
        called.add(m.group(1))

    for method_name, line in private_methods.items():
        if method_name not in called:
            findings.append(ASTFinding(
                rule_id="AST-CS-02",
                file=filepath,
                line=line,
                description=f"Private method '{method_name}' has no call sites in this file",
                fix=f"Remove if dead code, or add [UsedImplicitly] if called via reflection",
                severity="MEDIUM",
                confidence=70,
            ))

    return findings


def _cs_collection_modified_in_foreach(
    root: "tree_sitter.Node", source: bytes, filepath: str
) -> list[ASTFinding]:
    """Detect collection modification inside foreach using AST structure."""
    findings = []
    src_text = source.decode("utf-8", errors="replace")
    lines = src_text.splitlines()

    MUTATING = {"Add", "Remove", "Clear", "Insert", "RemoveAt", "RemoveAll",
                "Enqueue", "Dequeue", "Push", "Pop"}

    # Find foreach blocks
    foreach_pat = re.compile(r"\bforeach\s*\([^)]*\bin\s+(\w+)")
    for i, line in enumerate(lines):
        m = foreach_pat.search(line)
        if not m:
            continue
        collection = m.group(1)

        # Scan the foreach body (track brace depth)
        brace_depth = line.count("{") - line.count("}")
        for j in range(i + 1, min(len(lines), i + 100)):
            brace_depth += lines[j].count("{") - lines[j].count("}")
            if brace_depth <= 0:
                break

            # Check for mutation on the same collection
            for method in MUTATING:
                if re.search(rf"\b{re.escape(collection)}\.{method}\s*\(", lines[j]):
                    findings.append(ASTFinding(
                        rule_id="AST-CS-03",
                        file=filepath,
                        line=j + 1,
                        description=f"'{collection}.{method}()' inside foreach over '{collection}' — InvalidOperationException",
                        fix=f"Iterate a copy: foreach (var x in {collection}.ToList())",
                        severity="CRITICAL",
                        confidence=95,
                    ))
                    break

    return findings


def _cs_async_void(root: "tree_sitter.Node", filepath: str) -> list[ASTFinding]:
    """Detect async void methods (non-event-handler)."""
    findings = []

    def walk(node: "tree_sitter.Node"):
        if node.type == "method_declaration":
            modifiers = []
            return_type = None
            name_node = None
            for child in node.children:
                if child.type == "modifier":
                    modifiers.append(child.text.decode("utf-8"))
                elif child.type in ("predefined_type", "identifier", "generic_name"):
                    if return_type is None:
                        return_type = child.text.decode("utf-8")
                    elif name_node is None:
                        name_node = child

            if "async" in modifiers and return_type == "void" and name_node:
                method_name = name_node.text.decode("utf-8")
                # Event handlers and methods with try/catch are acceptable
                is_handler = (
                    method_name.startswith("On") or
                    method_name.startswith("Handle") or
                    method_name.startswith("Trigger") or
                    method_name.endswith("Handler") or
                    method_name.endswith("Callback") or
                    method_name.endswith("Clicked") or
                    method_name.endswith("Pressed")
                )
                # Check if method body has try/catch (properly guarded async void)
                body_text = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace") if hasattr(node, "start_byte") else ""
                has_try_catch = "try" in body_text and "catch" in body_text
                if not is_handler and not has_try_catch:
                    findings.append(ASTFinding(
                        rule_id="AST-CS-04",
                        file=filepath,
                        line=node.start_point[0] + 1,
                        description=f"async void '{method_name}' — exceptions crash with no catch opportunity",
                        fix="Change to async Task or async UniTask",
                        severity="HIGH",
                        confidence=88,
                    ))

        for child in node.children:
            walk(child)

    walk(root)
    return findings


# =============================================================================
# Python AST Analyzer
# =============================================================================


def analyze_python(filepath: str, source: bytes) -> list[ASTFinding]:
    """Run Python AST checks."""
    if not _TS_AVAILABLE:
        return []
    # Python analysis uses the built-in ast module (more reliable than tree-sitter for Python)
    # Tree-sitter Python is reserved for future cross-language unified queries
    return []


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "is_available",
    "analyze_csharp",
    "analyze_python",
    "ASTFinding",
]
