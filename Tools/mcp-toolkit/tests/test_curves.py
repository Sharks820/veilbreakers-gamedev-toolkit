"""Unit tests for curve creation and conversion validation functions.

Tests the pure-logic validators from handlers/curves.py -- no Blender/bpy required.
"""

import pytest


# ---------------------------------------------------------------------------
# _validate_create_curve_params tests
# ---------------------------------------------------------------------------


class TestValidateCreateCurveParams:
    """Test create_curve parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        result = _validate_create_curve_params({
            "points": [[0, 0, 0], [1, 0, 0]],
        })
        assert result["name"] == "Curve"
        assert result["curve_type"] == "BEZIER"
        assert result["points"] == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        assert result["closed"] is False
        assert result["resolution"] == 12

    def test_full_params(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        result = _validate_create_curve_params({
            "name": "MyPath",
            "curve_type": "NURBS",
            "points": [[0, 0, 0], [1, 1, 0], [2, 0, 0]],
            "closed": True,
            "resolution": 24,
        })
        assert result["name"] == "MyPath"
        assert result["curve_type"] == "NURBS"
        assert len(result["points"]) == 3
        assert result["closed"] is True
        assert result["resolution"] == 24

    def test_empty_name_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="name must be a non-empty string"):
            _validate_create_curve_params({
                "name": "   ",
                "points": [[0, 0, 0], [1, 0, 0]],
            })

    def test_invalid_curve_type_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="Unknown curve_type"):
            _validate_create_curve_params({
                "curve_type": "POLY",
                "points": [[0, 0, 0], [1, 0, 0]],
            })

    def test_both_curve_types_accepted(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        for ct in ("BEZIER", "NURBS"):
            result = _validate_create_curve_params({
                "curve_type": ct,
                "points": [[0, 0, 0], [1, 0, 0]],
            })
            assert result["curve_type"] == ct

    def test_empty_points_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="non-empty list"):
            _validate_create_curve_params({"points": []})

    def test_none_points_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="non-empty list"):
            _validate_create_curve_params({})

    def test_single_point_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="At least 2 points"):
            _validate_create_curve_params({"points": [[0, 0, 0]]})

    def test_point_with_too_few_coords_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="Point 1 must be a list of at least 3"):
            _validate_create_curve_params({
                "points": [[0, 0, 0], [1, 2]],
            })

    def test_point_values_coerced_to_float(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        result = _validate_create_curve_params({
            "points": [[1, 2, 3], [4, 5, 6]],
        })
        for pt in result["points"]:
            assert all(isinstance(c, float) for c in pt)

    def test_extra_point_coords_truncated(self):
        """Points with more than 3 coords should keep only x, y, z."""
        from blender_addon.handlers.curves import _validate_create_curve_params

        result = _validate_create_curve_params({
            "points": [[1, 2, 3, 99], [4, 5, 6, 99]],
        })
        assert result["points"] == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]

    def test_non_bool_closed_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="closed must be a boolean"):
            _validate_create_curve_params({
                "points": [[0, 0, 0], [1, 0, 0]],
                "closed": 1,
            })

    def test_zero_resolution_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="resolution must be a positive integer"):
            _validate_create_curve_params({
                "points": [[0, 0, 0], [1, 0, 0]],
                "resolution": 0,
            })

    def test_float_resolution_raises(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        with pytest.raises(ValueError, match="resolution must be a positive integer"):
            _validate_create_curve_params({
                "points": [[0, 0, 0], [1, 0, 0]],
                "resolution": 12.5,
            })

    def test_name_stripped(self):
        from blender_addon.handlers.curves import _validate_create_curve_params

        result = _validate_create_curve_params({
            "name": "  MyPath  ",
            "points": [[0, 0, 0], [1, 0, 0]],
        })
        assert result["name"] == "MyPath"


# ---------------------------------------------------------------------------
# _validate_curve_to_mesh_params tests
# ---------------------------------------------------------------------------


class TestValidateCurveToMeshParams:
    """Test curve_to_mesh parameter validation."""

    def test_minimal_valid_params(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        result = _validate_curve_to_mesh_params({"name": "BezierCurve"})
        assert result["name"] == "BezierCurve"
        assert result["profile_shape"] == "CIRCLE"
        assert result["profile_size"] == 0.1

    def test_full_params(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        result = _validate_curve_to_mesh_params({
            "name": "Path",
            "profile_shape": "SQUARE",
            "profile_size": 0.5,
        })
        assert result["profile_shape"] == "SQUARE"
        assert result["profile_size"] == 0.5

    def test_missing_name_raises(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        with pytest.raises(ValueError, match="name is required"):
            _validate_curve_to_mesh_params({})

    def test_invalid_profile_shape_raises(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        with pytest.raises(ValueError, match="Unknown profile_shape"):
            _validate_curve_to_mesh_params({
                "name": "Curve", "profile_shape": "TRIANGLE",
            })

    def test_all_profile_shapes_accepted(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        for shape in ("CIRCLE", "SQUARE", "CUSTOM"):
            result = _validate_curve_to_mesh_params({
                "name": "Curve", "profile_shape": shape,
            })
            assert result["profile_shape"] == shape

    def test_zero_profile_size_raises(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        with pytest.raises(ValueError, match="profile_size must be a positive number"):
            _validate_curve_to_mesh_params({
                "name": "Curve", "profile_size": 0,
            })

    def test_negative_profile_size_raises(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        with pytest.raises(ValueError, match="profile_size must be a positive number"):
            _validate_curve_to_mesh_params({
                "name": "Curve", "profile_size": -0.5,
            })

    def test_int_profile_size_coerced(self):
        from blender_addon.handlers.curves import _validate_curve_to_mesh_params

        result = _validate_curve_to_mesh_params({
            "name": "Curve", "profile_size": 1,
        })
        assert isinstance(result["profile_size"], float)


# ---------------------------------------------------------------------------
# _validate_extrude_along_curve_params tests
# ---------------------------------------------------------------------------


class TestValidateExtrudeAlongCurveParams:
    """Test extrude_along_curve parameter validation."""

    def test_valid_params(self):
        from blender_addon.handlers.curves import _validate_extrude_along_curve_params

        result = _validate_extrude_along_curve_params({
            "curve_name": "Path",
            "profile_name": "Profile",
        })
        assert result["curve_name"] == "Path"
        assert result["profile_name"] == "Profile"

    def test_missing_curve_name_raises(self):
        from blender_addon.handlers.curves import _validate_extrude_along_curve_params

        with pytest.raises(ValueError, match="curve_name is required"):
            _validate_extrude_along_curve_params({"profile_name": "Profile"})

    def test_missing_profile_name_raises(self):
        from blender_addon.handlers.curves import _validate_extrude_along_curve_params

        with pytest.raises(ValueError, match="profile_name is required"):
            _validate_extrude_along_curve_params({"curve_name": "Path"})

    def test_empty_curve_name_raises(self):
        from blender_addon.handlers.curves import _validate_extrude_along_curve_params

        with pytest.raises(ValueError, match="curve_name is required"):
            _validate_extrude_along_curve_params({
                "curve_name": "", "profile_name": "Profile",
            })

    def test_empty_profile_name_raises(self):
        from blender_addon.handlers.curves import _validate_extrude_along_curve_params

        with pytest.raises(ValueError, match="profile_name is required"):
            _validate_extrude_along_curve_params({
                "curve_name": "Path", "profile_name": "",
            })


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestCurveConstants:
    """Verify curve constant sets are properly defined."""

    def test_curve_types(self):
        from blender_addon.handlers.curves import _CURVE_TYPES

        assert _CURVE_TYPES == {"BEZIER", "NURBS"}

    def test_profile_shapes(self):
        from blender_addon.handlers.curves import _PROFILE_SHAPES

        assert _PROFILE_SHAPES == {"CIRCLE", "SQUARE", "CUSTOM"}
