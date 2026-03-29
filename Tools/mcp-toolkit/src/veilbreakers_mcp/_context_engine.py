"""
Cross-File Context Engine for VB Code Reviewer.

This module provides symbol table, call graph, and definition-use chain analysis
across Python and C# files for intelligent, context-aware code review.

Architecture: Section 2 of docs/superpowers/specs/2026-03-28-reviewer-architecture.md
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Definition:
    """Represents a symbol definition (class, method, field, property, function, variable)."""

    file: str
    line: int
    name: str
    type: str  # "class", "method", "field", "property", "function", "variable"
    signature: str = ""  # Full signature for methods
    scope: str = ""  # "class:ClassName", "module", "global"
    is_static: bool = False
    visibility: str = "private"  # "public", "private", "protected", "internal"


@dataclass
class Reference:
    """Represents a symbol reference (call, type_use, inheritance, attribute, import)."""

    file: str
    line: int
    column: int = 0
    context: str = "call"  # "call", "type_use", "inheritance", "attribute", "import"
    resolved_symbol: Optional[str] = None  # The definition it points to


@dataclass
class TypeInfo:
    """Type information for resolved types."""

    name: str
    base_type: str = ""
    generic_params: list[str] = field(default_factory=list)
    is_unity_object: bool = False  # True if inherits UnityEngine.Object
    is_serializable: bool = (
        False  # True if has [SerializeField] or is public in MonoBehaviour
    )
    is_mono_behaviour: bool = False
    is_scriptable_object: bool = False


@dataclass
class VariableState:
    """Tracks the state of a variable across its lifetime for null-check coverage analysis."""

    name: str
    defined_at: tuple[str, int]  # (file, line)
    null_checks: list[tuple[str, int]] = field(
        default_factory=list
    )  # (file, line) of null checks
    uses: list[tuple[str, int]] = field(
        default_factory=list
    )  # (file, line) of usage sites
    is_nullable: bool = True


# =============================================================================
# Unity-Specific Patterns
# =============================================================================


# Unity lifecycle methods that are considered "hot" (called every frame)
UNITY_LIFECYCLE_METHODS = {
    "Update",
    "FixedUpdate",
    "LateUpdate",
    "OnGUI",
    "Awake",
    "Start",
    "OnEnable",
    "OnDisable",
    "OnDestroy",
    "OnCollisionEnter",
    "OnCollisionExit",
    "OnCollisionStay",
    "OnTriggerEnter",
    "OnTriggerExit",
    "OnTriggerStay",
    "OnAnimatorIK",
    "OnApplicationFocus",
    "OnApplicationPause",
    "OnApplicationQuit",
    "OnBecameInvisible",
    "OnBecameVisible",
    "OnBeforeTransformParentChanged",
    "OnCollisionEnter2D",
    "OnDrawGizmos",
    "OnDrawGizmosSelected",
    "OnJointBreak",
    "OnParticleCollision",
    "OnParticleTrigger",
    "OnParticleSystemStopped",
    "OnPostRender",
    "OnPreCull",
    "OnPreRender",
    "OnRenderImage",
    "OnRenderObject",
    "OnTransformChildrenChanged",
    "OnTransformParentChanged",
    "OnValidate",
    "Reset",
    "OnAnimatorMove",
}

# Unity event subscription patterns
UNITY_EVENT_PATTERNS = [
    re.compile(r"(\w+)\.Register\s*\(\s*(?:typeof\()?(\w+)\)?"),
    re.compile(r"(\w+)\s*\+=\s*(\w+)"),  # event += handler
    re.compile(r"EventBus<(\w+)>\.Subscribe"),
    re.compile(r"(\w+)\.Unsubscribe\s*\("),
    re.compile(r"(\w+)\s*-=\s*(\w+)"),  # event -= handler
]

# Unity type inheritance patterns
UNITY_OBJECT_PATTERNS = [
    re.compile(
        r":\s*(?:public\s+|private\s+|protected\s+)?(\w+)\s*\(\s*\)\s*where\s+\1\s*:\s*(?:UnityEngine\.)?Object"
    ),
    re.compile(r":\s*(?:public\s+|private\s+|protected\s+)?MonoBehaviour"),
    re.compile(r":\s*(?:public\s+|private\s+|protected\s+)?ScriptableObject"),
    re.compile(r"class\s+\w+\s*:\s*(?:public\s+|private\s+|protected\s+)?(\w+)"),
]

# Unity serialization attribute patterns
UNITY_SERIALIZATION_PATTERNS = [
    re.compile(r"\[SerializeField\]"),
    re.compile(r"\[Header\s*\("),
    re.compile(r"\[Tooltip\s*\("),
]


# =============================================================================
# Context Engine
# =============================================================================


class ContextEngine:
    """
    Multi-pass context builder for cross-file code analysis.

    Provides symbol table, call graph, and definition-use chain analysis
    across Python and C# files.

    Pass 1 - Symbol Collection: Extract definitions, references, imports from files
    Pass 2 - Context Resolution: Build call graph, detect hot paths, track events
    Pass 3 - Enrichment: Detect Unity types, calculate null-check coverage
    """

    def __init__(
        self,
        project_root: Path,
        file_extensions: list[str] | None = None,
    ):
        """
        Initialize the context engine.

        Args:
            project_root: Root directory of the project to analyze
            file_extensions: List of file extensions to process (default: [".py", ".cs"])
        """
        self.project_root = Path(project_root)
        self.file_extensions = file_extensions or [".py", ".cs"]

        # Pass 1 outputs
        self.definitions: dict[str, list[Definition]] = {}  # name -> [Definition, ...]
        self.references: dict[str, list[Reference]] = {}  # name -> [Reference, ...]
        self.types: dict[str, TypeInfo] = {}
        self.imports: dict[str, list[str]] = {}  # file -> [imported_module, ...]

        # Pass 2 outputs
        self.call_graph: dict[
            str, set[str]
        ] = {}  # "file:method" -> {"file:method", ...}
        self.hot_methods: set[str] = set()  # Methods in Update/FixedUpdate/LateUpdate
        self.variable_states: dict[str, VariableState] = {}
        self.event_subscriptions: dict[
            str, list[str]
        ] = {}  # event_name -> [subscriber_method, ...]
        self.event_unsubscriptions: dict[
            str, list[str]
        ] = {}  # event_name -> [subscriber_method, ...]

        self._indexed_files: set[str] = set()
        self._file_to_definitions: dict[
            str, list[Definition]
        ] = {}  # file -> [Definition, ...]
        self._method_to_file: dict[str, str] = {}  # "method" -> "file"

    def build_context(self) -> None:
        """Run all 3 passes: Symbol Collection → Context Resolution → Enrichment."""
        self._pass1_symbol_collection()
        self._pass2_context_resolution()
        self._pass3_enrichment()

    def _pass1_symbol_collection(self) -> None:
        """Pass 1: Collect symbols from all files in the project."""
        # Find all relevant files
        files_to_process = []
        for ext in self.file_extensions:
            files_to_process.extend(self.project_root.rglob(f"*{ext}"))

        # Filter out unwanted directories
        exclude_dirs = {
            "__pycache__",
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "bin",
            "obj",
        }

        filtered_files = []
        for f in files_to_process:
            # Skip files in excluded directories
            if any(excluded in f.parts for excluded in exclude_dirs):
                continue
            filtered_files.append(f)

        # Process each file
        for file_path in filtered_files:
            self._index_file(file_path)

    def _pass2_context_resolution(self) -> None:
        """Pass 2: Resolve cross-file references and build call graph."""
        # Build reverse call graph (who calls whom)
        reverse_call_graph: dict[str, set[str]] = {}

        for method, callees in self.call_graph.items():
            for callee in callees:
                if callee not in reverse_call_graph:
                    reverse_call_graph[callee] = set()
                reverse_call_graph[callee].add(method)

        # BFS from Unity lifecycle methods to find hot paths
        self._compute_hot_methods(reverse_call_graph)

        # Resolve references to definitions
        self._resolve_references()

        # Track event subscriptions
        self._track_event_subscriptions()

    def _pass3_enrichment(self) -> None:
        """Pass 3: Enrich data with Unity-specific analysis."""
        # Detect Unity object types
        self._detect_unity_types()

        # Calculate null-check coverage
        self._calculate_null_check_coverage()

    def _index_file(self, file_path: Path) -> None:
        """Index a single file to extract definitions and references."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            # Skip files that can't be read
            return

        rel_path = str(file_path.relative_to(self.project_root))
        self._indexed_files.add(rel_path)

        if file_path.suffix == ".py":
            self._index_python_file(rel_path, content)
        elif file_path.suffix == ".cs":
            self._index_csharp_file(rel_path, content)

    def _index_python_file(self, file_path: str, content: str) -> None:
        """Extract definitions and references from a Python file using AST NodeVisitor."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        definitions_in_file: list[Definition] = []
        imports_in_file: list[str] = []

        # Use a NodeVisitor with a proper scope stack so parent context is always
        # correct regardless of the order ast.walk() would have visited nodes.
        engine = self  # capture for use inside visitor

        class _Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self._class_stack: list[str] = []
                self._method_stack: list[str] = []

            @property
            def current_class(self) -> str:
                return self._class_stack[-1] if self._class_stack else ""

            @property
            def current_method(self) -> str:
                return self._method_stack[-1] if self._method_stack else ""

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                defn = Definition(
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    type="class",
                    scope="module",
                )
                definitions_in_file.append(defn)
                engine._add_definition(node.name, defn)
                self._class_stack.append(node.name)
                self.generic_visit(node)
                self._class_stack.pop()

            def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
                scope = f"class:{self.current_class}" if self.current_class else "module"
                is_static = any(
                    (isinstance(n, ast.Name) and n.id == "staticmethod")
                    or (isinstance(n, ast.Attribute) and n.attr == "staticmethod")
                    for n in node.decorator_list
                )
                args = [arg.arg for arg in node.args.args]
                signature = f"def {node.name}({', '.join(args)})"
                defn = Definition(
                    file=file_path,
                    line=node.lineno,
                    name=node.name,
                    type="method" if self.current_class else "function",
                    signature=signature,
                    scope=scope,
                    is_static=is_static,
                    visibility="public" if node.name[0].isupper() else "private",
                )
                definitions_in_file.append(defn)
                engine._add_definition(node.name, defn)
                if self.current_class:
                    engine._method_to_file[f"{self.current_class}.{node.name}"] = file_path
                else:
                    engine._method_to_file[node.name] = file_path
                self._method_stack.append(node.name)
                self.generic_visit(node)
                self._method_stack.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_func(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_func(node)

            def visit_Assign(self, node: ast.Assign) -> None:
                if self.current_class:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            defn = Definition(
                                file=file_path,
                                line=node.lineno,
                                name=target.id,
                                type="field",
                                scope=f"class:{self.current_class}",
                            )
                            definitions_in_file.append(defn)
                            engine._add_definition(target.id, defn)
                # Track variable definitions for null-check coverage
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        engine._track_variable_definition(target.id, file_path, node.lineno)
                self.generic_visit(node)

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                if isinstance(node.target, ast.Name):
                    engine._track_variable_definition(node.target.id, file_path, node.lineno)
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Name):
                    ref = Reference(
                        file=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        context="call",
                    )
                    engine._add_reference(node.func.id, ref)
                    if self.current_class and self.current_method:
                        caller = f"{self.current_class}.{self.current_method}"
                        engine._add_call(caller, node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    ref = Reference(
                        file=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        context="call",
                    )
                    engine._add_reference(node.func.attr, ref)
                self.generic_visit(node)

            def visit_Name(self, node: ast.Name) -> None:
                if isinstance(node.ctx, ast.Load):
                    engine._track_variable_use(node.id, file_path, node.lineno)
                self.generic_visit(node)

            def visit_Compare(self, node: ast.Compare) -> None:
                compares_none = any(
                    isinstance(comp, ast.Constant) and comp.value is None
                    for comp in node.comparators
                )
                if compares_none and isinstance(node.left, ast.Name):
                    engine._track_null_check(node.left.id, file_path, node.lineno)
                self.generic_visit(node)

            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    imports_in_file.append(alias.name)
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    imports_in_file.append(node.module)
                self.generic_visit(node)

        _Visitor().visit(tree)

        self.imports[file_path] = imports_in_file
        self._file_to_definitions[file_path] = definitions_in_file

    def _index_csharp_file(self, file_path: str, content: str) -> None:
        """Extract definitions and references from a C# file using regex."""
        lines = content.split("\n")
        definitions_in_file: list[Definition] = []

        # Current scope tracking
        current_class = ""
        current_method = ""

        # Class/struct/interface definitions
        class_pattern = re.compile(
            r"(?:public|private|protected|internal|static|abstract|sealed)?\s*"
            r"(class|struct|interface|enum)\s+(\w+)"
            r"(?:\s*:\s*([^{]+))?"
        )

        # Method definitions
        method_pattern = re.compile(
            r"(?:public|private|protected|internal|static|virtual|override|abstract|sealed)?\s*"
            r"(?:async\s+)?"
            r"(\w+(?:<[^>]+>)?)\s+"  # Return type (with generic)
            r"(\w+)\s*"  # Method name
            r"\(([^)]*)\)"  # Parameters
        )

        # Field/property definitions
        field_pattern = re.compile(
            r"(?:public|private|protected|internal|static|readonly)?\s*"
            r"(?:\[([^\]]+)\]\s*)?"
            r"(\w+(?:<[^>]+>)?)\s+"  # Type
            r"(\w+)\s*"  # Field name
            r"(?:=\s*([^;]+))?;"  # Optional initializer
        )

        # Method calls
        call_pattern = re.compile(
            r"(\w+(?:<[^>]+>)?)\s*\("  # Method name with generic
        )

        # Event subscription patterns
        event_sub_pattern = re.compile(r"(\w+)\s*\+=\s*(\w+)")
        event_unsub_pattern = re.compile(r"(\w+)\s*-=\s*(\w+)")
        eventbus_register = re.compile(r"EventBus<(\w+)>\.Subscribe")

        # Brace-depth tracking for scope reset
        brace_depth = 0
        class_entry_depth: int = -1   # brace depth at which current_class was entered
        method_entry_depth: int = -1  # brace depth at which current_method was entered

        for i, line in enumerate(lines, start=1):
            # Update brace depth BEFORE processing so we can detect class/method exit
            open_braces = line.count("{")
            close_braces = line.count("}")

            # Reset method scope when we return to the depth at which it was entered
            if current_method and method_entry_depth >= 0 and close_braces > 0:
                if brace_depth - close_braces <= method_entry_depth:
                    current_method = ""
                    method_entry_depth = -1

            # Reset class scope when we return to the depth at which it was entered
            if current_class and class_entry_depth >= 0 and close_braces > 0:
                if brace_depth - close_braces <= class_entry_depth:
                    current_class = ""
                    class_entry_depth = -1

            brace_depth += open_braces - close_braces

            # Check for class definitions
            class_match = class_pattern.search(line)
            if class_match:
                type_keyword = class_match.group(1)
                class_name = class_match.group(2)
                bases = class_match.group(3) or ""

                defn = Definition(
                    file=file_path,
                    line=i,
                    name=class_name,
                    type=type_keyword,
                    scope="module",
                    visibility="public" if "public" in line else "private",
                )
                definitions_in_file.append(defn)
                self._add_definition(class_name, defn)
                # Record depth before the opening brace of this class body
                class_entry_depth = brace_depth - open_braces
                current_class = class_name
                current_method = ""
                method_entry_depth = -1

                primary_base = bases.split(",", 1)[0].strip() if bases else ""
                type_info = self.types.get(class_name) or TypeInfo(
                    name=class_name,
                    base_type=primary_base,
                )
                type_info.base_type = primary_base
                self.types[class_name] = type_info

                # Track Unity types
                if "MonoBehaviour" in bases:
                    type_info.is_mono_behaviour = True
                    type_info.is_unity_object = True
                elif "ScriptableObject" in bases:
                    type_info.is_scriptable_object = True
                    type_info.is_unity_object = True
                elif "UnityEngine.Object" in bases or "Object" in bases:
                    type_info.is_unity_object = True

            # Check for method definitions
            method_match = method_pattern.search(line)
            if method_match and current_class:
                return_type = method_match.group(1)
                method_name = method_match.group(2)
                params = method_match.group(3) or ""

                # Skip constructors and property methods
                if (
                    method_name == current_class
                    or method_name.startswith("set_")
                    or method_name.startswith("get_")
                ):
                    pass
                else:
                    signature = f"{return_type} {method_name}({params})"
                    scope = f"class:{current_class}"

                    defn = Definition(
                        file=file_path,
                        line=i,
                        name=method_name,
                        type="method",
                        signature=signature,
                        scope=scope,
                        is_static="static" in line,
                        visibility="public" if "public" in line else "private",
                    )
                    definitions_in_file.append(defn)
                    self._add_definition(method_name, defn)

                    # Track method for call graph
                    self._method_to_file[f"{current_class}.{method_name}"] = file_path
                    # Record depth before the opening brace of this method body
                    method_entry_depth = brace_depth - open_braces
                    current_method = method_name

            # Check for field definitions
            field_match = field_pattern.search(line)
            if field_match and current_class:
                attributes = field_match.group(1) or ""
                field_type = field_match.group(2)
                field_name = field_match.group(3)

                # Check for serialization attributes
                is_serialized = bool(
                    "[SerializeField]" in attributes
                    or "[Header" in attributes
                    or ("public" in line and "static" not in line)
                )

                defn = Definition(
                    file=file_path,
                    line=i,
                    name=field_name,
                    type="field",
                    scope=f"class:{current_class}",
                    visibility="public" if "public" in line else "private",
                )
                definitions_in_file.append(defn)
                self._add_definition(field_name, defn)
                self._track_variable_definition(field_name, file_path, i)

                # Track serialization
                if is_serialized and current_class in self.types:
                    self.types[current_class].is_serializable = True

            # Check for method calls
            for call_match in call_pattern.finditer(line):
                method_name = call_match.group(1)
                # Skip keywords and types
                if method_name in {
                    "if",
                    "while",
                    "for",
                    "foreach",
                    "return",
                    "new",
                    "throw",
                    "switch",
                }:
                    continue

                ref = Reference(
                    file=file_path,
                    line=i,
                    column=call_match.start(),
                    context="call",
                )
                self._add_reference(method_name, ref)

                # Build call graph
                if current_class and current_method:
                    caller = f"{current_class}.{current_method}"
                    self._add_call(caller, method_name)

            # Check for event subscriptions
            event_sub_match = event_sub_pattern.search(line)
            if event_sub_match:
                event_name = event_sub_match.group(1)
                if current_class and current_method:
                    if event_name not in self.event_subscriptions:
                        self.event_subscriptions[event_name] = []
                    self.event_subscriptions[event_name].append(
                        f"{current_class}.{current_method}"
                    )

            event_unsub_match = event_unsub_pattern.search(line)
            if event_unsub_match:
                event_name = event_unsub_match.group(1)
                if current_class and current_method:
                    if event_name not in self.event_unsubscriptions:
                        self.event_unsubscriptions[event_name] = []
                    self.event_unsubscriptions[event_name].append(
                        f"{current_class}.{current_method}"
                    )

            # Check for EventBus Subscribe
            eventbus_match = eventbus_register.search(line)
            if eventbus_match:
                event_type = eventbus_match.group(1)
                if event_type not in self.event_subscriptions:
                    self.event_subscriptions[event_type] = []
                if current_class and current_method:
                    self.event_subscriptions[event_type].append(
                        f"{current_class}.{current_method}"
                    )

            local_decl_match = re.search(
                r"(?:var|[A-Za-z_]\w*(?:<[^>]+>)?)\s+([A-Za-z_]\w*)\s*=",
                line,
            )
            if local_decl_match:
                self._track_variable_definition(local_decl_match.group(1), file_path, i)

            for null_check_match in re.finditer(
                r"\b([A-Za-z_]\w*)\s*(?:==|!=)\s*null\b|\bnull\s*(?:==|!=)\s*([A-Za-z_]\w*)\b",
                line,
            ):
                name = null_check_match.group(1) or null_check_match.group(2)
                if name:
                    self._track_null_check(name, file_path, i)

            for name_match in re.finditer(r"\b([A-Za-z_]\w*)\b", line):
                self._track_variable_use(name_match.group(1), file_path, i)

        self._file_to_definitions[file_path] = definitions_in_file

    def _add_definition(self, name: str, defn: Definition) -> None:
        """Add a definition to the symbol table."""
        if name not in self.definitions:
            self.definitions[name] = []
        self.definitions[name].append(defn)

    def _add_reference(self, name: str, ref: Reference) -> None:
        """Add a reference to the symbol table."""
        if name not in self.references:
            self.references[name] = []
        self.references[name].append(ref)

    def _add_call(self, caller: str, callee: str) -> None:
        """Add a call relationship to the call graph."""
        if caller not in self.call_graph:
            self.call_graph[caller] = set()
        self.call_graph[caller].add(callee)

    @staticmethod
    def _normalize_file_path(value: str) -> str:
        return value.replace("\\", "/").lower()

    def _track_variable_definition(self, name: str, file_path: str, line: int) -> None:
        if name not in self.variable_states:
            self.variable_states[name] = VariableState(
                name=name, defined_at=(file_path, line)
            )

    def _track_variable_use(self, name: str, file_path: str, line: int) -> None:
        var_state = self.variable_states.get(name)
        if not var_state:
            return
        use_site = (file_path, line)
        if use_site not in var_state.uses:
            var_state.uses.append(use_site)

    def _track_null_check(self, name: str, file_path: str, line: int) -> None:
        var_state = self.variable_states.get(name)
        if not var_state:
            self.variable_states[name] = VariableState(
                name=name, defined_at=(file_path, line)
            )
            var_state = self.variable_states[name]
        check_site = (file_path, line)
        if check_site not in var_state.null_checks:
            var_state.null_checks.append(check_site)

    def _compute_hot_methods(self, reverse_call_graph: dict[str, set[str]]) -> None:
        """
        Compute hot methods using BFS from Unity lifecycle methods.

        A method is "hot" if it's called from Update, FixedUpdate, LateUpdate, or OnGUI.
        """
        # Initialize queue with Unity lifecycle methods that exist in the codebase
        queue = []
        for method in UNITY_LIFECYCLE_METHODS:
            # Check both simple name and Class.Method format
            if method in self._method_to_file:
                queue.append(method)
            # Also check for class-qualified versions
            for qualified_method in list(self._method_to_file.keys()):
                if qualified_method.endswith(f".{method}"):
                    queue.append(qualified_method)

        visited: set[str] = set(queue)

        while queue:
            current = queue.pop(0)
            self.hot_methods.add(current)

            current_callees = self.call_graph.get(current, set())
            for callee in current_callees:
                qualified_matches = [
                    method_key
                    for method_key in self._method_to_file.keys()
                    if method_key == callee or method_key.endswith(f".{callee}")
                ]
                for qualified_callee in qualified_matches:
                    if qualified_callee not in visited:
                        visited.add(qualified_callee)
                        queue.append(qualified_callee)

    def _resolve_references(self) -> None:
        """Resolve references to their definitions."""
        for name, refs in self.references.items():
            defns = self.definitions.get(name, [])
            if defns:
                # Simple resolution: store the symbol name so resolve_reference() can look it up
                for ref in refs:
                    ref.resolved_symbol = name

    def _track_event_subscriptions(self) -> None:
        """Track event subscriptions for lifecycle pair checking."""
        for mapping in (self.event_subscriptions, self.event_unsubscriptions):
            for event_name, methods in list(mapping.items()):
                mapping[event_name] = sorted(set(methods))

    def _detect_unity_types(self) -> None:
        """Detect Unity-specific types from base class analysis."""
        changed = True
        while changed:
            changed = False
            for type_info in self.types.values():
                base = type_info.base_type.strip()
                before = (
                    type_info.is_unity_object,
                    type_info.is_mono_behaviour,
                    type_info.is_scriptable_object,
                )

                if base in {"MonoBehaviour", "UnityEngine.MonoBehaviour"}:
                    type_info.is_mono_behaviour = True
                    type_info.is_unity_object = True
                elif base in {"ScriptableObject", "UnityEngine.ScriptableObject"}:
                    type_info.is_scriptable_object = True
                    type_info.is_unity_object = True
                elif base in {"Object", "UnityEngine.Object"}:
                    type_info.is_unity_object = True
                elif base in self.types and self.types[base].is_unity_object:
                    parent = self.types[base]
                    type_info.is_unity_object = True
                    type_info.is_mono_behaviour = parent.is_mono_behaviour
                    type_info.is_scriptable_object = parent.is_scriptable_object

                after = (
                    type_info.is_unity_object,
                    type_info.is_mono_behaviour,
                    type_info.is_scriptable_object,
                )
                if after != before:
                    changed = True

    def _calculate_null_check_coverage(self) -> None:
        """Calculate null-check coverage for tracked variables."""
        # This is a simplified implementation
        # Full implementation would require more sophisticated AST analysis
        for var_name, var_state in self.variable_states.items():
            total_uses = len(var_state.uses)
            if total_uses == 0:
                continue

            # Count null checks
            checks = len(var_state.null_checks)
            var_state.is_nullable = checks < total_uses

    # =========================================================================
    # Public API
    # =========================================================================

    def get_definitions(self, name: str) -> list[Definition]:
        """
        Get all definitions for a symbol name.

        Args:
            name: The symbol name to look up

        Returns:
            List of Definition objects for this symbol
        """
        return self.definitions.get(name, [])

    def get_callers(self, method_name: str, file: str = "") -> list[str]:
        """
        Get all callers of a method (cross-file).

        Args:
            method_name: Name of the method to find callers for
            file: Optional file filter

        Returns:
            List of qualified method names that call this method
        """
        # Build reverse call graph
        reverse_graph: dict[str, set[str]] = {}
        for caller, callees in self.call_graph.items():
            for callee in callees:
                if callee not in reverse_graph:
                    reverse_graph[callee] = set()
                reverse_graph[callee].add(caller)

        callers = reverse_graph.get(method_name, set())

        if file:
            target_file = self._normalize_file_path(file)
            callers = {
                c
                for c in callers
                if self._normalize_file_path(self._method_to_file.get(c, ""))
                == target_file
            }

        return list(callers)

    def is_hot_path(self, method_name: str, file: str) -> bool:
        """
        Check if method is in Update/FixedUpdate/LateUpdate chain.

        Args:
            method_name: Name of the method to check
            file: File containing the method

        Returns:
            True if the method is transitively called from a Unity lifecycle method
        """
        # Check both simple and qualified names
        qualified_name = method_name
        if file:
            for key, val in self._method_to_file.items():
                if val == file and (
                    key.endswith(f".{method_name}") or key == method_name
                ):
                    qualified_name = key
                    break

        return qualified_name in self.hot_methods

    def is_unity_object(self, type_name: str) -> bool:
        """
        Check if a type inherits from UnityEngine.Object.

        Args:
            type_name: Name of the type to check

        Returns:
            True if the type is a Unity object (MonoBehaviour, ScriptableObject, etc.)
        """
        type_info = self.types.get(type_name)
        if type_info:
            return type_info.is_unity_object
        return False

    def has_null_check_coverage(
        self,
        variable_name: str,
        file: str,
        line: int,
    ) -> float:
        """
        Return 0.0-1.0 indicating how well a variable is null-guarded by callers.

        Args:
            variable_name: Name of the variable
            file: File containing the usage
            line: Line number of the usage

        Returns:
            Coverage score from 0.0 (no coverage) to 1.0 (fully covered)
        """
        var_state = self.variable_states.get(variable_name)
        if not var_state:
            return 0.0

        if not var_state.uses:
            return 1.0

        # Count uses before this line
        uses_before = sum(1 for f, l in var_state.uses if f == file and l < line)
        checks_before = sum(
            1 for f, l in var_state.null_checks if f == file and l < line
        )

        if uses_before == 0:
            return 1.0

        return min(1.0, checks_before / uses_before)

    def resolve_reference(self, ref: Reference) -> Optional[Definition]:
        """
        Try to resolve a reference to its definition.

        Args:
            ref: The reference to resolve

        Returns:
            The resolved Definition, or None if not found
        """
        # Try to find definition by name
        name = ref.resolved_symbol or ""
        defns = self.definitions.get(name, [])

        if not defns:
            return None

        # Return definition from same file if possible
        for defn in defns:
            if defn.file == ref.file:
                return defn

        # Otherwise return first definition
        return defns[0]

    def get_event_subscriptions(self, event_name: str) -> list[str]:
        """
        Get all methods that subscribe to an event.

        Args:
            event_name: Name of the event

        Returns:
            List of qualified method names that subscribe to this event
        """
        return self.event_subscriptions.get(event_name, [])

    def get_event_unsubscriptions(self, event_name: str) -> list[str]:
        """Get all methods that unsubscribe from an event."""
        return self.event_unsubscriptions.get(event_name, [])


# =============================================================================
# Module Exports
# =============================================================================


__all__ = [
    "ContextEngine",
    "Definition",
    "Reference",
    "TypeInfo",
    "VariableState",
    "UNITY_LIFECYCLE_METHODS",
]
