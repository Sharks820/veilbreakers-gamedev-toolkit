"""Unit tests for sculpt brush validation logic.

Tests the _validate_sculpt_brush_params pure-logic validator and
related constants from handlers/mesh.py -- no Blender/bpy required.
"""

import pytest


class TestSculptBrushTypes:
    """Test that the brush type constant set is complete."""

    def test_brush_types_are_frozenset(self):
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        assert isinstance(_SCULPT_BRUSH_TYPES, frozenset)

    def test_all_expected_brushes_present(self):
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        expected = {
            "DRAW", "CLAY_STRIPS", "CREASE", "GRAB", "INFLATE", "SMOOTH",
            "FLATTEN", "PINCH", "SNAKE_HOOK", "LAYER", "BLOB", "SCRAPE",
        }
        assert expected.issubset(_SCULPT_BRUSH_TYPES), (
            f"Missing brushes: {expected - _SCULPT_BRUSH_TYPES}"
        )

    def test_brush_count(self):
        from blender_addon.handlers.mesh import _SCULPT_BRUSH_TYPES

        assert len(_SCULPT_BRUSH_TYPES) >= 12


class TestValidateSculptBrushParams:
    """Test _validate_sculpt_brush_params validator."""

    def _valid_params(self, **overrides):
        base = {
            "name": "Cube",
            "brush_type": "DRAW",
            "strength": 0.5,
            "radius": 50.0,
        }
        base.update(overrides)
        return base

    def test_valid_params_no_errors(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params())
        assert errors == []

    def test_valid_with_stroke_points(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(
            stroke_points=[[0, 0, 0], [1, 1, 1], [2, 2, 2]]
        ))
        assert errors == []

    def test_missing_name(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(name=None))
        assert any("name" in e for e in errors)

    def test_empty_name(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(name=""))
        assert any("name" in e for e in errors)

    def test_missing_brush_type(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        params = self._valid_params()
        del params["brush_type"]
        errors = _validate_sculpt_brush_params(params)
        assert any("brush_type" in e for e in errors)

    def test_invalid_brush_type(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(brush_type="INVALID_BRUSH")
        )
        assert any("brush_type" in e.lower() or "Invalid" in e for e in errors)

    def test_all_valid_brush_types_accepted(self):
        from blender_addon.handlers.mesh import (
            _validate_sculpt_brush_params,
            _SCULPT_BRUSH_TYPES,
        )

        for bt in _SCULPT_BRUSH_TYPES:
            errors = _validate_sculpt_brush_params(
                self._valid_params(brush_type=bt)
            )
            assert errors == [], f"brush_type={bt} should be valid"

    def test_strength_negative(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(strength=-0.1))
        assert any("strength" in e for e in errors)

    def test_strength_over_one(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(strength=1.5))
        assert any("strength" in e for e in errors)

    def test_strength_boundaries(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        assert _validate_sculpt_brush_params(self._valid_params(strength=0.0)) == []
        assert _validate_sculpt_brush_params(self._valid_params(strength=1.0)) == []

    def test_radius_zero(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(radius=0))
        assert any("radius" in e for e in errors)

    def test_radius_negative(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(self._valid_params(radius=-10))
        assert any("radius" in e for e in errors)

    def test_stroke_points_not_list(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(stroke_points="bad")
        )
        assert any("stroke_points" in e for e in errors)

    def test_stroke_points_bad_element(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(stroke_points=[[0, 0]])  # 2 elements, need 3
        )
        assert any("stroke_points" in e for e in errors)

    def test_stroke_points_non_numeric(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(stroke_points=[["a", "b", "c"]])
        )
        assert any("stroke_points" in e for e in errors)

    def test_detail_size_negative(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(detail_size=-5.0)
        )
        assert any("detail_size" in e for e in errors)

    def test_detail_size_zero(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params(
            self._valid_params(detail_size=0)
        )
        assert any("detail_size" in e for e in errors)

    def test_multiple_errors(self):
        from blender_addon.handlers.mesh import _validate_sculpt_brush_params

        errors = _validate_sculpt_brush_params({
            "name": "",
            "brush_type": "INVALID",
            "strength": 5.0,
            "radius": -1,
        })
        assert len(errors) >= 4
