"""AST-based security validator for Blender code execution.

Validates user-submitted Python code against a strict allowlist before
execution. Both the MCP server and the Blender addon maintain identical
copies of this file — changes MUST be applied to both:
  - src/veilbreakers_mcp/shared/security.py  (MCP server side)
  - blender_addon/security.py                (Blender addon side)
"""
import ast

ALLOWED_IMPORTS = frozenset({
    "bpy", "mathutils", "bmesh", "math", "random", "json",
    "bpy.data", "bpy.context", "bpy.ops", "bpy.types",
    "mathutils.Vector", "mathutils.Matrix", "mathutils.Euler",
    "mathutils.Quaternion", "mathutils.Color",
})

_ALLOWED_ROOTS = frozenset({m.split(".")[0] for m in ALLOWED_IMPORTS})

BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "http", "urllib",
    "shutil", "ctypes", "importlib", "pathlib", "io",
    "pickle", "shelve", "tempfile", "glob", "fnmatch",
    "__builtins__", "builtins", "code", "codeop",
    "signal", "multiprocessing", "_thread", "threading",
    "webbrowser", "ftplib", "smtplib", "xmlrpc",
    "struct", "atexit", "zipfile", "tarfile",
})

BLOCKED_FUNCTIONS = frozenset({
    "exec", "eval", "compile",
    "__import__",
    "breakpoint",
    "globals", "locals", "vars",
})

# Block all dunder attribute access except a safe allowlist.
# This is an allowlist approach — only these dunders are permitted.
_ALLOWED_DUNDERS = frozenset({
    "__name__", "__len__", "__str__", "__repr__", "__iter__",
    "__next__", "__enter__", "__exit__", "__contains__",
    "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
    "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__",
    "__mod__", "__pow__", "__neg__", "__pos__", "__abs__",
    "__int__", "__float__", "__bool__", "__hash__",
    "__getitem__", "__setitem__", "__delitem__",
    "__init__", "__new__", "__call__",
    "__doc__",
})

# Dangerous bpy operations that escape the sandbox
BLOCKED_BPY_ATTRS = frozenset({
    "execfile",         # bpy.utils.execfile — runs arbitrary scripts
    "exec_line",        # bpy.utils.exec_line
    "python_file_run",  # bpy.ops.script.python_file_run
    "addon_install",    # bpy.ops.preferences.addon_install
    "addon_enable",     # bpy.ops.preferences.addon_enable
    "run_script",       # bpy.ops.text.run_script
    "open_mainfile",    # bpy.ops.wm.open_mainfile
    "save_mainfile",    # bpy.ops.wm.save_mainfile
    "save_as_mainfile", # bpy.ops.wm.save_as_mainfile
    "handlers",         # bpy.app.handlers — persistent backdoor registration
    "driver_namespace", # bpy.app.driver_namespace — persistent storage
    "register_class",   # bpy.utils.register_class — persistent operator backdoor
    "unregister_class", # bpy.utils.unregister_class — paired with register_class
})

# Names that cannot appear as bare variable references
BLOCKED_NAMES = frozenset({
    "__builtins__", "__import__", "__loader__", "__spec__",
})

MAX_CODE_LENGTH = 50_000


class SecurityValidator(ast.NodeVisitor):
    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node):
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in BLOCKED_IMPORTS:
                self.violations.append(
                    f"Blocked import: '{alias.name}' (security restriction)"
                )
            elif module not in _ALLOWED_ROOTS:
                self.violations.append(
                    f"Unknown import: '{alias.name}' (not in allowlist)"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            module = node.module.split(".")[0]
            if module in BLOCKED_IMPORTS:
                self.violations.append(
                    f"Blocked import: 'from {node.module}' (security restriction)"
                )
            elif module not in _ALLOWED_ROOTS:
                self.violations.append(
                    f"Unknown import: 'from {node.module}' (not in allowlist)"
                )
        else:
            self.violations.append(
                "Blocked import: relative imports are not allowed"
            )
        for alias in node.names:
            if alias.name == "*":
                self.violations.append(
                    f"Blocked: star import 'from {node.module or '.'} import *' "
                    "(security restriction)"
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        # Block bare-name calls: exec(), eval(), open(), __import__(), etc.
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_FUNCTIONS:
            self.violations.append(
                f"Blocked function: '{node.func.id}()' (security restriction)"
            )
        # Block method calls where the method name matches a blocked function
        # e.g., obj.exec(), obj.eval(), obj.compile(), str.format()
        if isinstance(node.func, ast.Attribute) and node.func.attr in BLOCKED_FUNCTIONS:
            self.violations.append(
                f"Blocked method call: '.{node.func.attr}()' (security restriction)"
            )
        # Block dangerous bpy operations (sandbox escape vectors)
        if isinstance(node.func, ast.Attribute) and node.func.attr in BLOCKED_BPY_ATTRS:
            self.violations.append(
                f"Blocked bpy operation: '.{node.func.attr}()' (security restriction)"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node):
        attr = node.attr
        # Block all dunders except the safe allowlist
        if attr.startswith("__") and attr.endswith("__") and len(attr) > 4:
            if attr not in _ALLOWED_DUNDERS:
                self.violations.append(
                    f"Blocked attribute access: '{attr}' (security restriction)"
                )
        # Block dangerous bpy attribute access (not just calls)
        if attr in BLOCKED_BPY_ATTRS:
            self.violations.append(
                f"Blocked bpy attribute: '.{attr}' (security restriction)"
            )
        self.generic_visit(node)

    def visit_Name(self, node):
        # Block access to dangerous bare names like __builtins__
        if node.id in BLOCKED_NAMES:
            self.violations.append(
                f"Blocked name: '{node.id}' (security restriction)"
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_decorators(node)
        self.generic_visit(node)

    def _check_decorators(self, node):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id in BLOCKED_FUNCTIONS:
                self.violations.append(
                    f"Blocked decorator: '@{decorator.id}' (security restriction)"
                )


def validate_code(code: str) -> tuple[bool, list[str]]:
    """Validate Python code against security whitelist.

    Returns:
        (is_safe, violations) tuple
    """
    if len(code) > MAX_CODE_LENGTH:
        return False, [f"Code too long: {len(code)} chars (max {MAX_CODE_LENGTH})"]

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]
    except RecursionError:
        return False, ["Code too deeply nested (possible DoS attempt)"]

    validator = SecurityValidator()
    validator.visit(tree)
    return len(validator.violations) == 0, validator.violations
