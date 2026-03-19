from veilbreakers_mcp.shared.security import validate_code


def test_safe_bpy_code():
    safe, violations = validate_code("import bpy\nbpy.ops.mesh.primitive_cube_add()")
    assert safe is True
    assert violations == []


def test_blocked_import_os():
    safe, violations = validate_code("import os\nos.system('rm -rf /')")
    assert safe is False
    assert any("os" in v for v in violations)


def test_blocked_import_subprocess():
    safe, violations = validate_code("import subprocess\nsubprocess.run(['ls'])")
    assert safe is False
    assert any("subprocess" in v for v in violations)


def test_blocked_exec():
    safe, violations = validate_code("exec('print(1)')")
    assert safe is False


def test_blocked_eval():
    safe, violations = validate_code("eval('1+1')")
    assert safe is False


def test_blocked_getattr():
    safe, violations = validate_code("getattr(obj, '__class__')")
    assert safe is False


def test_blocked_dunder_access():
    safe, violations = validate_code("x.__class__.__bases__")
    assert safe is False
    assert len(violations) >= 1


def test_syntax_error():
    safe, violations = validate_code("def broken(")
    assert safe is False
    assert any("Syntax error" in v for v in violations)


def test_allowed_mathutils():
    safe, violations = validate_code("from mathutils import Vector\nv = Vector((1, 0, 0))")
    assert safe is True


def test_allowed_bmesh():
    safe, violations = validate_code("import bmesh\nimport math")
    assert safe is True


def test_blocked_from_import():
    safe, violations = validate_code("from os.path import join")
    assert safe is False
    assert any("os" in v for v in violations)


def test_unknown_import():
    safe, violations = validate_code("import requests")
    assert safe is False
    assert any("Unknown import" in v for v in violations)
