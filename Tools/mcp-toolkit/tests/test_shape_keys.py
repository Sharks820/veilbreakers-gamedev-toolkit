"""Unit tests for shape key workflow validation functions.

Tests the pure-logic validators from handlers/mesh.py -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_shape_key_operation tests
# ---------------------------------------------------------------------------


class TestValidateShapeKeyOperation:
    """Test shape key operation parameter validation."""

    def test_valid_list_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "LIST",
        })
        assert errors == []

    def test_valid_create_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "CREATE",
            "key_name": "Smile",
        })
        assert errors == []

    def test_valid_set_value_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "SET_VALUE",
            "key_name": "Smile",
            "value": 0.5,
        })
        assert errors == []

    def test_valid_edit_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {0: [0.1, 0.0, 0.0], 1: [0.0, 0.1, 0.0]},
        })
        assert errors == []

    def test_valid_delete_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "DELETE",
            "key_name": "Smile",
        })
        assert errors == []

    def test_valid_add_driver_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "ADD_DRIVER",
            "key_name": "Smile",
            "driver_expression": "bone_val * 2",
        })
        assert errors == []

    def test_missing_name(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "operation": "LIST",
        })
        assert any("name" in e for e in errors)

    def test_missing_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
        })
        assert any("operation is required" in e for e in errors)

    def test_invalid_operation(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "INVALID",
        })
        assert any("Invalid operation" in e for e in errors)

    def test_create_missing_key_name(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "CREATE",
        })
        assert any("key_name" in e for e in errors)

    def test_set_value_out_of_range(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "SET_VALUE",
            "key_name": "Smile",
            "value": 1.5,
        })
        assert any("between 0 and 1" in e for e in errors)

    def test_set_value_negative(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "SET_VALUE",
            "key_name": "Smile",
            "value": -0.1,
        })
        assert any("between 0 and 1" in e for e in errors)

    def test_set_value_non_numeric(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "SET_VALUE",
            "key_name": "Smile",
            "value": "half",
        })
        assert any("must be a number" in e for e in errors)

    def test_set_value_boundary_valid(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        # 0 and 1 should be valid
        for val in (0, 0.0, 1, 1.0):
            errors = _validate_shape_key_operation({
                "name": "Cube",
                "operation": "SET_VALUE",
                "key_name": "Smile",
                "value": val,
            })
            assert errors == [], f"value={val} should be valid"

    def test_edit_missing_vertex_offsets(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
        })
        assert any("vertex_offsets must be a dict" in e for e in errors)

    def test_edit_empty_vertex_offsets(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {},
        })
        assert any("must not be empty" in e for e in errors)

    def test_edit_invalid_vertex_index(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {"abc": [0.1, 0.0, 0.0]},
        })
        assert any("must be an integer" in e for e in errors)

    def test_edit_negative_vertex_index(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {-1: [0.1, 0.0, 0.0]},
        })
        assert any("non-negative" in e for e in errors)

    def test_edit_invalid_offset_shape(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {0: [0.1, 0.0]},
        })
        assert any("offset must be" in e for e in errors)

    def test_edit_string_keys_valid(self):
        """JSON sends keys as strings -- should be accepted."""
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "EDIT",
            "key_name": "Smile",
            "vertex_offsets": {"0": [0.1, 0.0, 0.0], "5": [0.0, 0.1, 0.0]},
        })
        assert errors == []

    def test_delete_missing_key_name(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "DELETE",
        })
        assert any("key_name" in e for e in errors)

    def test_add_driver_missing_expression(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "ADD_DRIVER",
            "key_name": "Smile",
        })
        assert any("driver_expression" in e for e in errors)

    def test_add_driver_missing_key_name(self):
        from blender_addon.handlers.mesh import _validate_shape_key_operation

        errors = _validate_shape_key_operation({
            "name": "Cube",
            "operation": "ADD_DRIVER",
            "driver_expression": "x * 2",
        })
        assert any("key_name" in e for e in errors)


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestShapeKeyConstants:
    """Verify shape key constant sets are properly defined."""

    def test_shape_key_operations(self):
        from blender_addon.handlers.mesh import _SHAPE_KEY_OPERATIONS

        expected = {"CREATE", "SET_VALUE", "EDIT", "DELETE", "LIST", "ADD_DRIVER"}
        assert _SHAPE_KEY_OPERATIONS == expected
