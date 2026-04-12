"""Tests for fake_bpy strict stub module.

Validates that fake_bpy provides strict stubs (not MagicMock) that:
1. Raise AttributeError on unimplemented attributes
2. Allow handler imports to succeed
3. Provide usable mathutils types (Vector, Euler, Matrix, Quaternion)
4. Support bpy.props property functions
"""

import sys
import types
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_import_fake_bpy():
    """Import fake_bpy fresh (no caching issues)."""
    import fake_bpy
    return fake_bpy


# ---------------------------------------------------------------------------
# StrictModule behaviour
# ---------------------------------------------------------------------------

class TestStrictModuleErrors:
    """fake_bpy must raise AttributeError on unimplemented attributes."""

    def test_bpy_unknown_attr_raises(self):
        """bpy.some_random_attr must raise AttributeError, not return MagicMock."""
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bpy
        with pytest.raises(AttributeError, match="some_random_attr"):
            _ = bpy.some_random_attr

    def test_bpy_data_objects_raises(self):
        """bpy.data.objects must raise AttributeError (not installed)."""
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bpy
        with pytest.raises(AttributeError):
            _ = bpy.data.objects

    def test_bpy_types_is_module_like(self):
        """bpy.types must be a module-like object, not MagicMock."""
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bpy
        # Must have __name__ attribute like a module
        assert hasattr(bpy.types, "__name__")
        # Must NOT be a MagicMock
        assert "MagicMock" not in type(bpy.types).__name__


class TestBpyProps:
    """bpy.props property functions must be callable stubs returning None."""

    def test_string_property_callable(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bpy
        result = bpy.props.StringProperty(name="test", default="hello")
        assert result is None

    def test_all_property_functions_exist(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bpy
        prop_names = [
            "StringProperty", "IntProperty", "FloatProperty",
            "BoolProperty", "EnumProperty", "CollectionProperty",
            "PointerProperty", "FloatVectorProperty",
            "IntVectorProperty", "BoolVectorProperty",
        ]
        for name in prop_names:
            fn = getattr(bpy.props, name)
            assert callable(fn), f"bpy.props.{name} must be callable"
            assert fn(name="x") is None, f"bpy.props.{name}() must return None"


class TestMathutils:
    """mathutils stubs must provide usable (not MagicMock) types."""

    def test_vector_xyz(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Vector
        v = Vector([1.0, 2.0, 3.0])
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0

    def test_vector_len(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Vector
        v = Vector([1.0, 2.0, 3.0])
        assert len(v) == 3

    def test_vector_getitem(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Vector
        v = Vector([10.0, 20.0, 30.0])
        assert v[0] == 10.0
        assert v[1] == 20.0
        assert v[2] == 30.0

    def test_vector_arithmetic(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Vector
        a = Vector([1.0, 0.0, 0.0])
        b = Vector([0.0, 1.0, 0.0])
        c = a + b
        assert c[0] == 1.0
        assert c[1] == 1.0

    def test_euler_creation(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Euler
        e = Euler((0.0, 0.0, 0.0))
        # Must not be MagicMock
        assert "MagicMock" not in type(e).__name__
        assert hasattr(e, "x")

    def test_matrix_identity(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Matrix
        m = Matrix.Identity(4)
        # Must not be MagicMock
        assert "MagicMock" not in type(m).__name__

    def test_quaternion_creation(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        from mathutils import Quaternion
        q = Quaternion()
        assert "MagicMock" not in type(q).__name__


class TestBmesh:
    """bmesh stub must be importable but strict."""

    def test_bmesh_importable(self):
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bmesh
        assert bmesh is not None

    def test_bmesh_new_raises(self):
        """bmesh.new should raise AttributeError (not be a MagicMock)."""
        fb = _fresh_import_fake_bpy()
        fb.install()
        import bmesh
        with pytest.raises(AttributeError):
            _ = bmesh.new


class TestConftest:
    """After conftest installs stubs, imports must work and stubs must be strict."""

    def test_import_bpy_succeeds(self):
        """import bpy must succeed (conftest auto-installed)."""
        import bpy
        assert bpy is not None

    def test_bpy_nonexistent_raises(self):
        """bpy.nonexistent must raise AttributeError."""
        import bpy
        with pytest.raises(AttributeError):
            _ = bpy.nonexistent

    def test_no_magicmock_in_bpy(self):
        """bpy module itself must not be a MagicMock."""
        import bpy
        assert "MagicMock" not in type(bpy).__name__

    def test_handler_import_terrain_pipeline(self):
        """Handler with 'import bpy' at top level must still import."""
        try:
            import blender_addon.handlers.terrain_pipeline
        except ImportError:
            pytest.skip("terrain_pipeline not available")
        assert blender_addon.handlers.terrain_pipeline is not None

    def test_handler_import_animation(self):
        """Handler with 'import bpy' at top level must still import."""
        try:
            import blender_addon.handlers.animation
        except ImportError:
            pytest.skip("animation not available")
        assert blender_addon.handlers.animation is not None
