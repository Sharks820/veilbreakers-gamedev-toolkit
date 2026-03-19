"""AST-based security validator for Blender code execution.

This is the addon-local copy - it runs inside Blender's Python
environment and does not depend on the MCP package being installed.
"""
import ast

ALLOWED_IMPORTS = frozenset({
    "bpy", "mathutils", "bmesh", "math", "random", "json",
    "bpy.data", "bpy.context", "bpy.ops", "bpy.types",
    "mathutils.Vector", "mathutils.Matrix", "mathutils.Euler",
    "mathutils.Quaternion", "mathutils.Color",
})

BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "http", "urllib",
    "shutil", "ctypes", "importlib", "pathlib", "io",
    "pickle", "shelve", "tempfile", "glob", "fnmatch",
    "__builtins__", "builtins", "code", "codeop",
})

BLOCKED_FUNCTIONS = frozenset({
    "exec", "eval", "compile", "getattr", "setattr", "delattr",
})

BLOCKED_DUNDERS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__import__",
    "__builtins__", "__globals__", "__code__", "__func__",
})


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
            elif module not in {m.split(".")[0] for m in ALLOWED_IMPORTS}:
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
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"Syntax error: {e}"]

    validator = SecurityValidator()
    validator.visit(tree)
    return len(validator.violations) == 0, validator.violations
