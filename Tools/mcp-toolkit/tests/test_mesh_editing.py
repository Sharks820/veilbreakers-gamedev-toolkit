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


# ---------------------------------------------------------------------------
# _validate_modifier_params tests
# ---------------------------------------------------------------------------


class TestValidateModifierParams:
    """Test modifier parameter validation (pure logic, no Blender)."""

    def test_missing_modifier_type_errors(self):
        """Missing modifier_type produces an error."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({})
        assert len(errors) == 1
        assert "modifier_type is required" in errors[0]

    def test_invalid_modifier_type_errors(self):
        """Unrecognised modifier_type produces an error."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({"modifier_type": "CLOTH"})
        assert len(errors) == 1
        assert "Invalid modifier_type" in errors[0]
        assert "'CLOTH'" in errors[0]

    def test_valid_modifier_type_no_errors(self):
        """Valid modifier_type with no settings produces no errors."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        for mod_type in (
            "SUBSURF", "BEVEL", "MIRROR", "ARRAY", "SOLIDIFY",
            "DECIMATE", "REMESH", "SMOOTH", "BOOLEAN", "WIREFRAME",
            "SKIN", "LATTICE", "SHRINKWRAP",
        ):
            errors = _validate_modifier_params({"modifier_type": mod_type})
            assert errors == [], f"Unexpected errors for {mod_type}: {errors}"

    def test_valid_settings_keys_accepted(self):
        """Valid settings keys for a modifier type produce no errors."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({
            "modifier_type": "SUBSURF",
            "settings": {"levels": 3, "render_levels": 4},
        })
        assert errors == []

    def test_invalid_settings_keys_rejected(self):
        """Settings keys not valid for the modifier type produce errors."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({
            "modifier_type": "SUBSURF",
            "settings": {"levels": 3, "thickness": 0.5},
        })
        assert len(errors) == 1
        assert "Invalid settings keys" in errors[0]
        assert "thickness" in errors[0]

    def test_empty_settings_dict_no_errors(self):
        """Empty settings dict produces no errors."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({
            "modifier_type": "BEVEL",
            "settings": {},
        })
        assert errors == []

    def test_skin_with_no_default_keys_rejects_any_settings(self):
        """SKIN modifier has no default keys, so any settings key is invalid."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({
            "modifier_type": "SKIN",
            "settings": {"branch_smoothing": 0.5},
        })
        assert len(errors) == 1
        assert "Invalid settings keys" in errors[0]

    def test_multiple_bad_keys_all_reported(self):
        """Multiple invalid settings keys are all listed in the error."""
        from blender_addon.handlers.mesh import _validate_modifier_params

        errors = _validate_modifier_params({
            "modifier_type": "ARRAY",
            "settings": {"count": 5, "bad_key_1": 1, "bad_key_2": 2},
        })
        assert len(errors) == 1
        assert "bad_key_1" in errors[0]
        assert "bad_key_2" in errors[0]


class TestModifierDefaults:
    """Test MODIFIER_DEFAULTS and VALID_MODIFIER_TYPES constants."""

    def test_valid_modifier_types_matches_defaults_keys(self):
        """VALID_MODIFIER_TYPES must exactly match MODIFIER_DEFAULTS keys."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS, VALID_MODIFIER_TYPES

        assert VALID_MODIFIER_TYPES == frozenset(MODIFIER_DEFAULTS.keys())

    def test_all_thirteen_types_present(self):
        """All 13 documented modifier types are present."""
        from blender_addon.handlers.mesh import VALID_MODIFIER_TYPES

        expected = {
            "SUBSURF", "BEVEL", "MIRROR", "ARRAY", "SOLIDIFY",
            "DECIMATE", "REMESH", "SMOOTH", "BOOLEAN", "WIREFRAME",
            "SKIN", "LATTICE", "SHRINKWRAP",
        }
        assert expected == VALID_MODIFIER_TYPES

    def test_subsurf_defaults(self):
        """SUBSURF defaults include levels, render_levels, quality."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS

        d = MODIFIER_DEFAULTS["SUBSURF"]
        assert d["levels"] == 2
        assert d["render_levels"] == 3
        assert d["quality"] == 3

    def test_bevel_defaults(self):
        """BEVEL defaults include width, segments, limit_method, angle_limit."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS

        d = MODIFIER_DEFAULTS["BEVEL"]
        assert d["width"] == 0.02
        assert d["segments"] == 3
        assert d["limit_method"] == "ANGLE"
        assert abs(d["angle_limit"] - 0.524) < 0.001

    def test_mirror_defaults(self):
        """MIRROR defaults include use_axis and use_bisect_axis lists."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS

        d = MODIFIER_DEFAULTS["MIRROR"]
        assert d["use_axis"] == [True, False, False]
        assert d["use_bisect_axis"] == [False, False, False]

    def test_array_defaults(self):
        """ARRAY defaults include count and relative_offset_displace."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS

        d = MODIFIER_DEFAULTS["ARRAY"]
        assert d["count"] == 3
        assert d["relative_offset_displace"] == [1.0, 0.0, 0.0]

    def test_boolean_defaults(self):
        """BOOLEAN defaults include operation and object."""
        from blender_addon.handlers.mesh import MODIFIER_DEFAULTS

        d = MODIFIER_DEFAULTS["BOOLEAN"]
        assert d["operation"] == "DIFFERENCE"
        assert d["object"] == ""
