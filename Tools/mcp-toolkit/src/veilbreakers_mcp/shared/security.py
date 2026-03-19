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
    "getattr", "setattr", "delattr",
    "__import__",
    "open", "input", "breakpoint", "help",
    "globals", "locals", "vars", "dir",
})

BLOCKED_DUNDERS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__import__",
    "__builtins__", "__globals__", "__code__", "__func__",
    "__mro__", "__dict__", "__init_subclass__", "__set_name__",
    "__del__", "__getattr__", "__getattribute__",
    "__reduce__", "__reduce_ex__",
    "__loader__", "__spec__",
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
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_FUNCTIONS:
            self.violations.append(
                f"Blocked function: '{node.func.id}()' (security restriction)"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if (
            node.attr.startswith("__")
            and node.attr.endswith("__")
            and node.attr in BLOCKED_DUNDERS
        ):
            self.violations.append(
                f"Blocked attribute access: '{node.attr}' (security restriction)"
            )
        self.generic_visit(node)


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

    validator = SecurityValidator()
    validator.visit(tree)
    return len(validator.violations) == 0, validator.violations
