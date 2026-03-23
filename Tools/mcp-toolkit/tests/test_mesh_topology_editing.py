"""Unit tests for mesh topology editing validation functions.

Tests the pure-logic validators for loop cut, bevel, knife project,
and proportional edit -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_loop_cut_params tests
# ---------------------------------------------------------------------------


class TestValidateLoopCutParams:
    """Test loop cut parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        result = _validate_loop_cut_params({"name": "Cube"})
        assert result["name"] == "Cube"
        assert result["cuts"] == 1
        assert result["edge_index"] is None
        assert result["offset"] == 0.0

    def test_full_params(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        result = _validate_loop_cut_params({
            "name": "Cube",
            "cuts": 3,
            "edge_index": 5,
            "offset": 0.5,
        })
        assert result["cuts"] == 3
        assert result["edge_index"] == 5
        assert result["offset"] == 0.5

    def test_missing_name_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_loop_cut_params({})

    def test_empty_name_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_loop_cut_params({"name": ""})

    def test_zero_cuts_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="cuts must be a positive integer"):
            _validate_loop_cut_params({"name": "Cube", "cuts": 0})

    def test_negative_cuts_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="cuts must be a positive integer"):
            _validate_loop_cut_params({"name": "Cube", "cuts": -1})

    def test_float_cuts_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="cuts must be a positive integer"):
            _validate_loop_cut_params({"name": "Cube", "cuts": 1.5})

    def test_negative_edge_index_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="edge_index must be a non-negative integer"):
            _validate_loop_cut_params({"name": "Cube", "edge_index": -1})

    def test_float_edge_index_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="edge_index must be a non-negative integer"):
            _validate_loop_cut_params({"name": "Cube", "edge_index": 2.5})

    def test_offset_out_of_range_high(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="offset must be between -1 and 1"):
            _validate_loop_cut_params({"name": "Cube", "offset": 1.5})

    def test_offset_out_of_range_low(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="offset must be between -1 and 1"):
            _validate_loop_cut_params({"name": "Cube", "offset": -1.5})

    def test_offset_at_boundaries(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        r1 = _validate_loop_cut_params({"name": "Cube", "offset": -1.0})
        assert r1["offset"] == -1.0
        r2 = _validate_loop_cut_params({"name": "Cube", "offset": 1.0})
        assert r2["offset"] == 1.0

    def test_string_offset_raises(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        with pytest.raises(ValueError, match="offset must be a number"):
            _validate_loop_cut_params({"name": "Cube", "offset": "half"})

    def test_int_offset_coerced_to_float(self):
        from blender_addon.handlers.mesh import _validate_loop_cut_params

        result = _validate_loop_cut_params({"name": "Cube", "offset": 0})
        assert isinstance(result["offset"], float)


# ---------------------------------------------------------------------------
# _validate_bevel_params tests
# ---------------------------------------------------------------------------


class TestValidateBevelParams:
    """Test bevel edge parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        result = _validate_bevel_params({"name": "Cube", "width": 0.1})
        assert result["name"] == "Cube"
        assert result["width"] == 0.1
        assert result["segments"] == 1
        assert result["selection_mode"] == "sharp"
        assert result["angle_threshold"] == 30.0

    def test_full_params(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        result = _validate_bevel_params({
            "name": "Cube",
            "width": 0.5,
            "segments": 4,
            "selection_mode": "angle",
            "angle_threshold": 45.0,
        })
        assert result["width"] == 0.5
        assert result["segments"] == 4
        assert result["selection_mode"] == "angle"
        assert result["angle_threshold"] == 45.0

    def test_missing_name_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_bevel_params({"width": 0.1})

    def test_missing_width_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="width is required"):
            _validate_bevel_params({"name": "Cube"})

    def test_zero_width_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="width must be a positive number"):
            _validate_bevel_params({"name": "Cube", "width": 0})

    def test_negative_width_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="width must be a positive number"):
            _validate_bevel_params({"name": "Cube", "width": -0.1})

    def test_zero_segments_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="segments must be a positive integer"):
            _validate_bevel_params({"name": "Cube", "width": 0.1, "segments": 0})

    def test_invalid_selection_mode_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="Unknown selection_mode"):
            _validate_bevel_params({
                "name": "Cube", "width": 0.1, "selection_mode": "random",
            })

    def test_all_selection_modes_accepted(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        for mode in ("all", "sharp", "boundary", "angle"):
            result = _validate_bevel_params({
                "name": "Cube", "width": 0.1, "selection_mode": mode,
            })
            assert result["selection_mode"] == mode

    def test_angle_threshold_out_of_range(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="angle_threshold must be between 0 and 180"):
            _validate_bevel_params({
                "name": "Cube", "width": 0.1, "angle_threshold": 200,
            })

    def test_negative_angle_threshold_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="angle_threshold must be between 0 and 180"):
            _validate_bevel_params({
                "name": "Cube", "width": 0.1, "angle_threshold": -5,
            })

    def test_string_angle_threshold_raises(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        with pytest.raises(ValueError, match="angle_threshold must be a number"):
            _validate_bevel_params({
                "name": "Cube", "width": 0.1, "angle_threshold": "sharp",
            })

    def test_width_coerced_to_float(self):
        from blender_addon.handlers.mesh import _validate_bevel_params

        result = _validate_bevel_params({"name": "Cube", "width": 1})
        assert isinstance(result["width"], float)


# ---------------------------------------------------------------------------
# _validate_knife_params tests
# ---------------------------------------------------------------------------


class TestValidateKnifeParams:
    """Test knife project parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        result = _validate_knife_params({"name": "Cube"})
        assert result["name"] == "Cube"
        assert result["cut_type"] == "bisect"
        assert result["plane_point"] == [0.0, 0.0, 0.0]
        assert result["plane_normal"] == [0.0, 0.0, 1.0]

    def test_full_params(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        result = _validate_knife_params({
            "name": "Cube",
            "cut_type": "loop",
            "plane_point": [1.0, 2.0, 3.0],
            "plane_normal": [0.0, 1.0, 0.0],
        })
        assert result["cut_type"] == "loop"
        assert result["plane_point"] == [1.0, 2.0, 3.0]
        assert result["plane_normal"] == [0.0, 1.0, 0.0]

    def test_missing_name_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_knife_params({})

    def test_invalid_cut_type_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="Unknown cut_type"):
            _validate_knife_params({"name": "Cube", "cut_type": "knife"})

    def test_both_cut_types_accepted(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        for ct in ("bisect", "loop"):
            result = _validate_knife_params({"name": "Cube", "cut_type": ct})
            assert result["cut_type"] == ct

    def test_plane_point_wrong_length_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="plane_point must be a 3-element list"):
            _validate_knife_params({"name": "Cube", "plane_point": [1, 2]})

    def test_plane_normal_wrong_length_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="plane_normal must be a 3-element list"):
            _validate_knife_params({"name": "Cube", "plane_normal": [1]})

    def test_zero_normal_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="plane_normal must not be a zero vector"):
            _validate_knife_params({
                "name": "Cube", "plane_normal": [0.0, 0.0, 0.0],
            })

    def test_plane_point_string_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="plane_point must be a 3-element list"):
            _validate_knife_params({"name": "Cube", "plane_point": "origin"})

    def test_plane_normal_string_raises(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        with pytest.raises(ValueError, match="plane_normal must be a 3-element list"):
            _validate_knife_params({"name": "Cube", "plane_normal": "up"})

    def test_point_values_coerced_to_float(self):
        from blender_addon.handlers.mesh import _validate_knife_params

        result = _validate_knife_params({
            "name": "Cube",
            "plane_point": [1, 2, 3],
            "plane_normal": [0, 0, 1],
        })
        assert all(isinstance(c, float) for c in result["plane_point"])
        assert all(isinstance(c, float) for c in result["plane_normal"])


# ---------------------------------------------------------------------------
# _validate_proportional_edit_params tests
# ---------------------------------------------------------------------------


class TestValidateProportionalEditParams:
    """Test proportional edit parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        result = _validate_proportional_edit_params({
            "name": "Cube",
            "vertex_indices": [0, 1],
            "offset": [0.0, 0.0, 1.0],
            "radius": 2.0,
        })
        assert result["name"] == "Cube"
        assert result["vertex_indices"] == [0, 1]
        assert result["offset"] == [0.0, 0.0, 1.0]
        assert result["radius"] == 2.0
        assert result["falloff_type"] == "SMOOTH"

    def test_all_falloff_types(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        for ft in ("SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR"):
            result = _validate_proportional_edit_params({
                "name": "Cube",
                "vertex_indices": [0],
                "offset": [1, 0, 0],
                "radius": 1.0,
                "falloff_type": ft,
            })
            assert result["falloff_type"] == ft

    def test_missing_name_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_proportional_edit_params({
                "vertex_indices": [0], "offset": [0, 0, 1], "radius": 1.0,
            })

    def test_empty_vertex_indices_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="vertex_indices must be a non-empty list"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [],
                "offset": [0, 0, 1], "radius": 1.0,
            })

    def test_none_vertex_indices_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="vertex_indices must be a non-empty list"):
            _validate_proportional_edit_params({
                "name": "Cube", "offset": [0, 0, 1], "radius": 1.0,
            })

    def test_negative_vertex_index_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="non-negative integers"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [-1],
                "offset": [0, 0, 1], "radius": 1.0,
            })

    def test_float_vertex_index_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="non-negative integers"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [1.5],
                "offset": [0, 0, 1], "radius": 1.0,
            })

    def test_wrong_offset_length_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="offset must be a 3-element list"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [0],
                "offset": [0, 1], "radius": 1.0,
            })

    def test_missing_radius_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="radius is required"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [0],
                "offset": [0, 0, 1],
            })

    def test_zero_radius_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="radius must be a positive number"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [0],
                "offset": [0, 0, 1], "radius": 0,
            })

    def test_negative_radius_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="radius must be a positive number"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [0],
                "offset": [0, 0, 1], "radius": -1.0,
            })

    def test_invalid_falloff_type_raises(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        with pytest.raises(ValueError, match="Unknown falloff_type"):
            _validate_proportional_edit_params({
                "name": "Cube", "vertex_indices": [0],
                "offset": [0, 0, 1], "radius": 1.0,
                "falloff_type": "CONSTANT",
            })

    def test_offset_values_coerced_to_float(self):
        from blender_addon.handlers.mesh import _validate_proportional_edit_params

        result = _validate_proportional_edit_params({
            "name": "Cube", "vertex_indices": [0],
            "offset": [1, 2, 3], "radius": 1.0,
        })
        assert all(isinstance(c, float) for c in result["offset"])


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestMeshTopologyEditConstants:
    """Verify new constant sets are properly defined."""

    def test_bevel_selection_modes(self):
        from blender_addon.handlers.mesh import _BEVEL_SELECTION_MODES

        assert "all" in _BEVEL_SELECTION_MODES
        assert "sharp" in _BEVEL_SELECTION_MODES
        assert "boundary" in _BEVEL_SELECTION_MODES
        assert "angle" in _BEVEL_SELECTION_MODES

    def test_proportional_falloff_types(self):
        from blender_addon.handlers.mesh import _PROPORTIONAL_FALLOFF_TYPES

        expected = {"SMOOTH", "SPHERE", "ROOT", "SHARP", "LINEAR"}
        assert _PROPORTIONAL_FALLOFF_TYPES == expected

    def test_knife_cut_types(self):
        from blender_addon.handlers.mesh import _KNIFE_CUT_TYPES

        assert _KNIFE_CUT_TYPES == {"bisect", "loop"}
