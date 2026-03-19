"""Unit tests for mesh editing helpers (selection criteria, edit validation, axis mapping).

Tests the pure-logic helpers from handlers/mesh.py that do NOT require bpy/Blender.
Blender-dependent integration tests should be marked with @pytest.mark.blender.
"""

import pytest


# ---------------------------------------------------------------------------
# _parse_selection_criteria tests
# ---------------------------------------------------------------------------


class TestParseSelectionCriteria:
    """Test selection criteria parsing from params dict."""

    def test_material_index_criteria(self):
        """material_index param is extracted correctly."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({"material_index": 2})
        assert criteria["material_index"] == 2

    def test_vertex_group_criteria(self):
        """vertex_group param is extracted correctly."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({"vertex_group": "Head"})
        assert criteria["vertex_group"] == "Head"

    def test_face_normal_direction_criteria(self):
        """face_normal_direction + normal_threshold are extracted correctly."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({
            "face_normal_direction": [0, 0, 1],
            "normal_threshold": 0.8,
        })
        assert criteria["face_normal_direction"] == [0, 0, 1]
        assert criteria["normal_threshold"] == 0.8

    def test_face_normal_direction_default_threshold(self):
        """face_normal_direction without explicit threshold uses default 0.7."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({
            "face_normal_direction": [0, 1, 0],
        })
        assert criteria["face_normal_direction"] == [0, 1, 0]
        assert criteria["normal_threshold"] == 0.7

    def test_loose_parts_criteria(self):
        """loose_parts param is extracted correctly."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({"loose_parts": True})
        assert criteria["loose_parts"] is True

    def test_combined_criteria(self):
        """Multiple criteria can be combined."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({
            "material_index": 1,
            "loose_parts": True,
        })
        assert criteria["material_index"] == 1
        assert criteria["loose_parts"] is True

    def test_empty_criteria(self):
        """Empty params returns empty criteria dict."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({})
        # Should have no selection keys (only non-selection params stripped)
        assert "material_index" not in criteria
        assert "vertex_group" not in criteria
        assert "face_normal_direction" not in criteria
        assert "loose_parts" not in criteria

    def test_ignores_non_criteria_params(self):
        """Non-criteria params like object_name are not in output."""
        from blender_addon.handlers.mesh import _parse_selection_criteria

        criteria = _parse_selection_criteria({
            "object_name": "Cube",
            "material_index": 3,
        })
        assert "object_name" not in criteria
        assert criteria["material_index"] == 3


# ---------------------------------------------------------------------------
# _validate_edit_operation tests
# ---------------------------------------------------------------------------


class TestValidateEditOperation:
    """Test edit operation validation."""

    def test_known_operations_accepted(self):
        """All documented operations should be accepted."""
        from blender_addon.handlers.mesh import _validate_edit_operation

        for op in ("extrude", "inset", "mirror", "separate", "join"):
            _validate_edit_operation(op)  # should not raise

    def test_unknown_operation_rejected(self):
        """Unknown operations should raise ValueError."""
        from blender_addon.handlers.mesh import _validate_edit_operation

        with pytest.raises(ValueError, match="Unknown edit operation"):
            _validate_edit_operation("spin")

    def test_case_insensitive_rejection(self):
        """Operations must be lowercase."""
        from blender_addon.handlers.mesh import _validate_edit_operation

        with pytest.raises(ValueError, match="Unknown edit operation"):
            _validate_edit_operation("Extrude")


# ---------------------------------------------------------------------------
# _axis_to_index tests
# ---------------------------------------------------------------------------


class TestAxisMapping:
    """Test axis string to index mapping for mirror operations."""

    def test_x_maps_to_0(self):
        from blender_addon.handlers.mesh import _axis_to_index

        assert _axis_to_index("X") == 0

    def test_y_maps_to_1(self):
        from blender_addon.handlers.mesh import _axis_to_index

        assert _axis_to_index("Y") == 1

    def test_z_maps_to_2(self):
        from blender_addon.handlers.mesh import _axis_to_index

        assert _axis_to_index("Z") == 2

    def test_lowercase_accepted(self):
        from blender_addon.handlers.mesh import _axis_to_index

        assert _axis_to_index("x") == 0
        assert _axis_to_index("y") == 1
        assert _axis_to_index("z") == 2

    def test_invalid_axis_raises(self):
        from blender_addon.handlers.mesh import _axis_to_index

        with pytest.raises(ValueError, match="Invalid axis"):
            _axis_to_index("W")


# ---------------------------------------------------------------------------
# _sculpt_operation_to_filter_type tests
# ---------------------------------------------------------------------------


class TestSculptOperationMapping:
    """Test sculpt operation to filter type mapping."""

    def test_smooth_is_special(self):
        """smooth operation uses bmesh, not sculpt filter -- returns None."""
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        assert _sculpt_operation_to_filter_type("smooth") is None

    def test_inflate_maps(self):
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        assert _sculpt_operation_to_filter_type("inflate") == "INFLATE"

    def test_flatten_maps(self):
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        assert _sculpt_operation_to_filter_type("flatten") == "SURFACE_SMOOTH"

    def test_crease_maps(self):
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        assert _sculpt_operation_to_filter_type("crease") == "SHARPEN"

    def test_unknown_sculpt_op_raises(self):
        from blender_addon.handlers.mesh import _sculpt_operation_to_filter_type

        with pytest.raises(ValueError, match="Unknown sculpt operation"):
            _sculpt_operation_to_filter_type("pinch")
