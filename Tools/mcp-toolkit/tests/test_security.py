from veilbreakers_mcp.shared.security import validate_code


# --- Allowed imports ---

def test_safe_bpy_code():
    safe, violations = validate_code("import bpy\nbpy.ops.mesh.primitive_cube_add()")
    assert safe is True
    assert violations == []


def test_allowed_mathutils():
    safe, violations = validate_code("from mathutils import Vector\nv = Vector((1, 0, 0))")
    assert safe is True


def test_allowed_bmesh():
    safe, violations = validate_code("import bmesh\nimport math")
    assert safe is True


def test_allowed_json():
    safe, violations = validate_code("import json\njson.dumps({'a': 1})")
    assert safe is True


# --- Blocked imports (explicit blocklist) ---

def test_blocked_import_os():
    safe, violations = validate_code("import os\nos.system('rm -rf /')")
    assert safe is False
    assert any("os" in v for v in violations)


def test_blocked_import_subprocess():
    safe, violations = validate_code("import subprocess\nsubprocess.run(['ls'])")
    assert safe is False
    assert any("subprocess" in v for v in violations)


def test_blocked_from_import():
    safe, violations = validate_code("from os.path import join")
    assert safe is False
    assert any("os" in v for v in violations)


# --- Unknown imports (not in allowlist) ---

def test_unknown_import():
    safe, violations = validate_code("import requests")
    assert safe is False
    assert any("Unknown import" in v for v in violations)


def test_unknown_from_import_struct():
    safe, violations = validate_code("from struct import pack")
    assert safe is False
    assert any("Unknown import" in v or "struct" in v for v in violations)


def test_unknown_from_import_signal():
    safe, violations = validate_code("from signal import SIGKILL")
    assert safe is False


def test_unknown_from_import_multiprocessing():
    safe, violations = validate_code("from multiprocessing import Pool")
    assert safe is False


def test_unknown_from_import_thread():
    safe, violations = validate_code("from _thread import start_new_thread")
    assert safe is False


# --- Star imports ---

def test_star_import_blocked():
    safe, violations = validate_code("from os import *")
    assert safe is False
    assert any("star import" in v.lower() for v in violations)


def test_star_import_allowed_module_still_blocked():
    safe, violations = validate_code("from bpy import *")
    assert safe is False
    assert any("star import" in v.lower() for v in violations)


# --- Relative imports ---

def test_relative_import_blocked():
    safe, violations = validate_code("from . import something")
    assert safe is False
    assert any("relative" in v.lower() for v in violations)


# --- __import__ bypass ---

def test_dunder_import_call():
    safe, violations = validate_code("__import__('os').system('whoami')")
    assert safe is False
    assert any("__import__" in v for v in violations)


# --- Blocked functions ---

def test_blocked_exec():
    safe, violations = validate_code("exec('print(1)')")
    assert safe is False


def test_blocked_eval():
    safe, violations = validate_code("eval('1+1')")
    assert safe is False


def test_blocked_getattr():
    safe, violations = validate_code("getattr(obj, '__class__')")
    assert safe is False


def test_blocked_open():
    safe, violations = validate_code("open('/etc/passwd').read()")
    assert safe is False
    assert any("open" in v for v in violations)


def test_blocked_globals():
    safe, violations = validate_code("globals()")
    assert safe is False


def test_blocked_locals():
    safe, violations = validate_code("locals()")
    assert safe is False


def test_blocked_vars():
    safe, violations = validate_code("vars()")
    assert safe is False


def test_blocked_dir():
    safe, violations = validate_code("dir()")
    assert safe is False


def test_blocked_breakpoint():
    safe, violations = validate_code("breakpoint()")
    assert safe is False


def test_blocked_input():
    safe, violations = validate_code("input('>')")
    assert safe is False


# --- Blocked dunder attributes ---

def test_blocked_dunder_class():
    safe, violations = validate_code("x.__class__")
    assert safe is False


def test_blocked_dunder_bases():
    safe, violations = validate_code("x.__class__.__bases__")
    assert safe is False
    assert len(violations) >= 2  # both __class__ and __bases__


def test_blocked_dunder_dict():
    safe, violations = validate_code("x.__dict__")
    assert safe is False


def test_blocked_dunder_mro():
    safe, violations = validate_code("x.__mro__")
    assert safe is False


def test_blocked_dunder_subclasses():
    safe, violations = validate_code("x.__subclasses__()")
    assert safe is False


def test_blocked_dunder_globals():
    safe, violations = validate_code("f.__globals__")
    assert safe is False


# --- Nested imports (should be caught by generic_visit recursion) ---

def test_nested_import_in_function():
    safe, violations = validate_code("def inner():\n    import os\ninner()")
    assert safe is False
    assert any("os" in v for v in violations)


# --- Code size limit ---

def test_code_too_long():
    safe, violations = validate_code("x = 1\n" * 100_000)
    assert safe is False
    assert any("too long" in v.lower() for v in violations)


# --- Syntax error ---

def test_syntax_error():
    safe, violations = validate_code("def broken(")
    assert safe is False
    assert any("Syntax error" in v for v in violations)


# --- Bare name blocking ---

def test_blocked_builtins_bare_name():
    safe, violations = validate_code("b = __builtins__")
    assert safe is False
    assert any("__builtins__" in v for v in violations)


# --- Dangerous bpy operations ---

def test_blocked_bpy_execfile():
    safe, violations = validate_code("bpy.utils.execfile('/tmp/evil.py')")
    assert safe is False
    assert any("execfile" in v for v in violations)


def test_blocked_bpy_handlers():
    safe, violations = validate_code("bpy.app.handlers.frame_change_post.append(f)")
    assert safe is False
    assert any("handlers" in v for v in violations)


def test_blocked_bpy_script_run():
    safe, violations = validate_code("bpy.ops.script.python_file_run(filepath='x')")
    assert safe is False
    assert any("python_file_run" in v for v in violations)


def test_blocked_bpy_save_mainfile():
    safe, violations = validate_code("bpy.ops.wm.save_as_mainfile(filepath='x')")
    assert safe is False
    assert any("save_as_mainfile" in v for v in violations)


# --- Decorator bypass ---

def test_blocked_decorator_exec():
    safe, violations = validate_code("@exec\ndef f(): pass")
    assert safe is False
    assert any("decorator" in v.lower() for v in violations)


def test_blocked_decorator_eval():
    safe, violations = validate_code("@eval\ndef f(): pass")
    assert safe is False


# --- Method call bypass ---

def test_blocked_method_call_exec():
    safe, violations = validate_code("obj.exec('code')")
    assert safe is False
    assert any(".exec" in v for v in violations)


def test_blocked_method_call_compile():
    safe, violations = validate_code("obj.compile('code', 'f', 'exec')")
    assert safe is False


# --- Dunder allowlist (non-allowed dunders blocked) ---

def test_blocked_dunder_code():
    safe, violations = validate_code("f.__code__")
    assert safe is False


def test_blocked_dunder_func():
    safe, violations = validate_code("f.__func__")
    assert safe is False


def test_blocked_dunder_import():
    safe, violations = validate_code("x.__import__")
    assert safe is False


def test_allowed_dunder_name():
    """__name__ is in the dunder allowlist and should pass."""
    safe, violations = validate_code("x = bpy.__name__")
    assert safe is True


def test_allowed_dunder_len():
    """__len__ is in the dunder allowlist and should pass."""
    safe, violations = validate_code("x.__len__()")
    assert safe is True


def test_allowed_dunder_init():
    """__init__ is in the dunder allowlist and should pass."""
    safe, violations = validate_code("class Foo:\n    def __init__(self): pass")
    assert safe is True


# --- Format string dunder bypass ---

def test_blocked_format_method_call():
    """str.format() blocked to prevent dunder info leak via format specifiers."""
    safe, violations = validate_code("'{0.__class__}'.format(x)")
    assert safe is False
    assert any("format" in v for v in violations)


def test_blocked_format_bare_call():
    safe, violations = validate_code("format(42, 'd')")
    assert safe is False


# --- Class decorator bypass ---

def test_blocked_class_decorator_exec():
    safe, violations = validate_code("@exec\nclass Foo: pass")
    assert safe is False
    assert any("decorator" in v.lower() for v in violations)


def test_blocked_class_decorator_eval():
    safe, violations = validate_code("@eval\nclass Foo: pass")
    assert safe is False
