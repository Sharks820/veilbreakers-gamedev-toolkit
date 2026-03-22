"""Unit tests for driver system validation functions.

Tests the pure-logic validators from handlers/drivers.py -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_driver_variable tests
# ---------------------------------------------------------------------------


class TestValidateDriverVariable:
    """Test individual driver variable validation."""

    def test_valid_variable(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "var1",
            "id_type": "OBJECT",
            "object": "Cube",
            "transform_type": "LOC_X",
        }, 0)
        assert errors == []

    def test_missing_name(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "id_type": "OBJECT",
            "object": "Cube",
        }, 0)
        assert any("name" in e for e in errors)

    def test_empty_name(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "",
            "id_type": "OBJECT",
            "object": "Cube",
        }, 0)
        assert any("name" in e for e in errors)

    def test_invalid_id_type(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "var1",
            "id_type": "INVALID",
            "object": "Cube",
        }, 0)
        assert any("id_type" in e for e in errors)

    def test_missing_object(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "var1",
            "id_type": "OBJECT",
        }, 0)
        assert any("object" in e for e in errors)

    def test_invalid_transform_type(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "var1",
            "id_type": "OBJECT",
            "object": "Cube",
            "transform_type": "INVALID",
        }, 0)
        assert any("transform_type" in e for e in errors)

    def test_no_transform_type_is_ok(self):
        from blender_addon.handlers.drivers import _validate_driver_variable

        errors = _validate_driver_variable({
            "name": "var1",
            "id_type": "OBJECT",
            "object": "Cube",
        }, 0)
        assert errors == []

    def test_all_id_types_accepted(self):
        from blender_addon.handlers.drivers import _validate_driver_variable, _ID_TYPES

        for id_type in _ID_TYPES:
            errors = _validate_driver_variable({
                "name": "var1",
                "id_type": id_type,
                "object": "Cube",
            }, 0)
            assert not any("id_type" in e for e in errors)

    def test_all_transform_types_accepted(self):
        from blender_addon.handlers.drivers import _validate_driver_variable, _TRANSFORM_TYPES

        for tt in _TRANSFORM_TYPES:
            errors = _validate_driver_variable({
                "name": "var1",
                "id_type": "OBJECT",
                "object": "Cube",
                "transform_type": tt,
            }, 0)
            assert not any("transform_type" in e for e in errors)


# ---------------------------------------------------------------------------
# _validate_add_driver_params tests
# ---------------------------------------------------------------------------


class TestValidateAddDriverParams:
    """Test add_driver parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        result = _validate_add_driver_params({
            "target_object": "Cube",
            "property_path": "location",
            "expression": "var1 * 2",
        })
        assert result["target_object"] == "Cube"
        assert result["property_path"] == "location"
        assert result["driver_type"] == "SCRIPTED"
        assert result["expression"] == "var1 * 2"
        assert result["property_index"] == -1
        assert result["variables"] == []

    def test_with_variables(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        result = _validate_add_driver_params({
            "target_object": "Cube",
            "property_path": "location",
            "expression": "var1 + var2",
            "variables": [
                {"name": "var1", "id_type": "OBJECT", "object": "Empty"},
                {"name": "var2", "id_type": "OBJECT", "object": "Cube"},
            ],
        })
        assert len(result["variables"]) == 2

    def test_non_scripted_driver_type(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        result = _validate_add_driver_params({
            "target_object": "Cube",
            "property_path": "location",
            "driver_type": "SUM",
        })
        assert result["driver_type"] == "SUM"

    def test_missing_target_object_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="target_object must be a non-empty string"):
            _validate_add_driver_params({
                "property_path": "location",
                "expression": "x",
            })

    def test_missing_property_path_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="property_path must be a non-empty string"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "expression": "x",
            })

    def test_invalid_driver_type_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="Unknown driver_type"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "driver_type": "INVALID",
            })

    def test_scripted_without_expression_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="expression is required"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "driver_type": "SCRIPTED",
            })

    def test_invalid_variable_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="Invalid driver variables"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "expression": "var1",
                "variables": [
                    {"name": "var1", "id_type": "INVALID", "object": "Cube"},
                ],
            })

    def test_non_dict_variable_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="Invalid driver variables"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "expression": "var1",
                "variables": ["not_a_dict"],
            })

    def test_non_list_variables_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="variables must be a list"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "expression": "var1",
                "variables": "not_a_list",
            })

    def test_non_int_property_index_raises(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params

        with pytest.raises(ValueError, match="property_index must be an integer"):
            _validate_add_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "expression": "x",
                "property_index": "zero",
            })

    def test_all_driver_types_accepted(self):
        from blender_addon.handlers.drivers import _validate_add_driver_params, _DRIVER_TYPES

        for dt in _DRIVER_TYPES:
            params = {
                "target_object": "Cube",
                "property_path": "location",
                "driver_type": dt,
            }
            if dt == "SCRIPTED":
                params["expression"] = "x"
            result = _validate_add_driver_params(params)
            assert result["driver_type"] == dt


# ---------------------------------------------------------------------------
# _validate_remove_driver_params tests
# ---------------------------------------------------------------------------


class TestValidateRemoveDriverParams:
    """Test remove_driver parameter validation."""

    def test_valid_params(self):
        from blender_addon.handlers.drivers import _validate_remove_driver_params

        result = _validate_remove_driver_params({
            "target_object": "Cube",
            "property_path": "location",
        })
        assert result["target_object"] == "Cube"
        assert result["property_path"] == "location"
        assert result["property_index"] == -1

    def test_with_index(self):
        from blender_addon.handlers.drivers import _validate_remove_driver_params

        result = _validate_remove_driver_params({
            "target_object": "Cube",
            "property_path": "location",
            "property_index": 2,
        })
        assert result["property_index"] == 2

    def test_missing_target_object_raises(self):
        from blender_addon.handlers.drivers import _validate_remove_driver_params

        with pytest.raises(ValueError, match="target_object must be a non-empty string"):
            _validate_remove_driver_params({"property_path": "location"})

    def test_missing_property_path_raises(self):
        from blender_addon.handlers.drivers import _validate_remove_driver_params

        with pytest.raises(ValueError, match="property_path must be a non-empty string"):
            _validate_remove_driver_params({"target_object": "Cube"})

    def test_non_int_property_index_raises(self):
        from blender_addon.handlers.drivers import _validate_remove_driver_params

        with pytest.raises(ValueError, match="property_index must be an integer"):
            _validate_remove_driver_params({
                "target_object": "Cube",
                "property_path": "location",
                "property_index": "zero",
            })


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestDriverConstants:
    """Verify driver constant sets are properly defined."""

    def test_driver_types(self):
        from blender_addon.handlers.drivers import _DRIVER_TYPES

        assert _DRIVER_TYPES == {"SCRIPTED", "SUM", "MIN", "MAX", "AVERAGE"}

    def test_id_types(self):
        from blender_addon.handlers.drivers import _ID_TYPES

        expected = {
            "OBJECT", "MESH", "ARMATURE", "MATERIAL", "SCENE",
            "WORLD", "CAMERA", "LIGHT", "CURVE", "KEY",
        }
        assert _ID_TYPES == expected

    def test_transform_types(self):
        from blender_addon.handlers.drivers import _TRANSFORM_TYPES

        expected = {
            "LOC_X", "LOC_Y", "LOC_Z",
            "ROT_X", "ROT_Y", "ROT_Z", "ROT_W",
            "SCALE_X", "SCALE_Y", "SCALE_Z",
        }
        assert _TRANSFORM_TYPES == expected
