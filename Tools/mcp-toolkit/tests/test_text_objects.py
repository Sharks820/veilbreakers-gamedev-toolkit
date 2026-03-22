"""Unit tests for text object creation and conversion validation functions.

Tests the pure-logic validators from handlers/text_objects.py -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_create_text_params tests
# ---------------------------------------------------------------------------


class TestValidateCreateTextParams:
    """Test create_text parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        result = _validate_create_text_params({"text": "Hello"})
        assert result["text"] == "Hello"
        assert result["name"] == "Text"
        assert result["font_size"] == 1.0
        assert result["extrude_depth"] == 0.0
        assert result["bevel_depth"] == 0.0
        assert result["resolution"] == 12
        assert result["align"] == "LEFT"
        assert result["font_path"] is None
        assert result["position"] == [0.0, 0.0, 0.0]

    def test_full_params(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        result = _validate_create_text_params({
            "text": "VeilBreakers",
            "name": "Title",
            "font_size": 2.5,
            "extrude_depth": 0.3,
            "bevel_depth": 0.05,
            "resolution": 24,
            "align": "CENTER",
            "font_path": "/fonts/gothic.ttf",
            "position": [1.0, 2.0, 3.0],
        })
        assert result["text"] == "VeilBreakers"
        assert result["name"] == "Title"
        assert result["font_size"] == 2.5
        assert result["extrude_depth"] == 0.3
        assert result["bevel_depth"] == 0.05
        assert result["resolution"] == 24
        assert result["align"] == "CENTER"
        assert result["font_path"] == "/fonts/gothic.ttf"
        assert result["position"] == [1.0, 2.0, 3.0]

    def test_missing_text_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="text must be a non-empty string"):
            _validate_create_text_params({})

    def test_empty_text_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="text must be a non-empty string"):
            _validate_create_text_params({"text": ""})

    def test_empty_name_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="name must be a non-empty string"):
            _validate_create_text_params({"text": "Hello", "name": "   "})

    def test_negative_font_size_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="font_size must be a positive number"):
            _validate_create_text_params({"text": "Hello", "font_size": -1.0})

    def test_zero_font_size_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="font_size must be a positive number"):
            _validate_create_text_params({"text": "Hello", "font_size": 0})

    def test_negative_extrude_depth_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="extrude_depth must be a non-negative number"):
            _validate_create_text_params({"text": "Hello", "extrude_depth": -0.5})

    def test_negative_bevel_depth_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="bevel_depth must be a non-negative number"):
            _validate_create_text_params({"text": "Hello", "bevel_depth": -0.1})

    def test_zero_resolution_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="resolution must be a positive integer"):
            _validate_create_text_params({"text": "Hello", "resolution": 0})

    def test_float_resolution_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="resolution must be a positive integer"):
            _validate_create_text_params({"text": "Hello", "resolution": 12.5})

    def test_invalid_align_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="Unknown align"):
            _validate_create_text_params({"text": "Hello", "align": "MIDDLE"})

    def test_all_alignments_accepted(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        for align in ("LEFT", "CENTER", "RIGHT", "JUSTIFY", "FLUSH"):
            result = _validate_create_text_params({"text": "Hello", "align": align})
            assert result["align"] == align

    def test_non_string_font_path_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="font_path must be a string"):
            _validate_create_text_params({"text": "Hello", "font_path": 123})

    def test_invalid_position_raises(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        with pytest.raises(ValueError, match="position must have 3 elements"):
            _validate_create_text_params({"text": "Hello", "position": [1, 2]})

    def test_name_stripped(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        result = _validate_create_text_params({"text": "Hello", "name": "  Title  "})
        assert result["name"] == "Title"

    def test_int_font_size_coerced(self):
        from blender_addon.handlers.text_objects import _validate_create_text_params

        result = _validate_create_text_params({"text": "Hello", "font_size": 2})
        assert isinstance(result["font_size"], float)
        assert result["font_size"] == 2.0


# ---------------------------------------------------------------------------
# _validate_text_to_mesh_params tests
# ---------------------------------------------------------------------------


class TestValidateTextToMeshParams:
    """Test text_to_mesh parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.text_objects import _validate_text_to_mesh_params

        result = _validate_text_to_mesh_params({"name": "MyText"})
        assert result["name"] == "MyText"
        assert result["apply_modifiers"] is True

    def test_full_params(self):
        from blender_addon.handlers.text_objects import _validate_text_to_mesh_params

        result = _validate_text_to_mesh_params({
            "name": "Title",
            "apply_modifiers": False,
        })
        assert result["name"] == "Title"
        assert result["apply_modifiers"] is False

    def test_missing_name_raises(self):
        from blender_addon.handlers.text_objects import _validate_text_to_mesh_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_text_to_mesh_params({})

    def test_empty_name_raises(self):
        from blender_addon.handlers.text_objects import _validate_text_to_mesh_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_text_to_mesh_params({"name": ""})

    def test_non_bool_apply_modifiers_raises(self):
        from blender_addon.handlers.text_objects import _validate_text_to_mesh_params

        with pytest.raises(ValueError, match="apply_modifiers must be a boolean"):
            _validate_text_to_mesh_params({"name": "Text", "apply_modifiers": 1})


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestTextConstants:
    """Verify text object constant sets are properly defined."""

    def test_alignments(self):
        from blender_addon.handlers.text_objects import _ALIGNMENTS

        assert _ALIGNMENTS == {"LEFT", "CENTER", "RIGHT", "JUSTIFY", "FLUSH"}
