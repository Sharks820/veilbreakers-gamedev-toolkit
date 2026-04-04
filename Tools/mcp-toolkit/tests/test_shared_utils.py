"""Tests for _shared_utils terrain placement and interpolation utilities.

Relies on conftest.py bpy/bmesh/mathutils stubs.
"""

from __future__ import annotations

from blender_addon.handlers._shared_utils import (
    safe_place_object,
    smoothstep,
)


# -----------------------------------------------------------------------
# smoothstep
# -----------------------------------------------------------------------


class TestSmoothstep:
    def test_zero(self):
        assert smoothstep(0.0) == 0.0

    def test_one(self):
        assert smoothstep(1.0) == 1.0

    def test_half(self):
        assert smoothstep(0.5) == 0.5

    def test_clamp_negative(self):
        assert smoothstep(-1.0) == 0.0

    def test_clamp_above(self):
        assert smoothstep(2.0) == 1.0

    def test_quarter(self):
        result = smoothstep(0.25)
        expected = 0.25 * 0.25 * (3.0 - 2.0 * 0.25)
        assert abs(result - expected) < 1e-9

    def test_monotonic(self):
        """smoothstep must be monotonically increasing."""
        prev = 0.0
        for i in range(1, 101):
            t = i / 100.0
            val = smoothstep(t)
            assert val >= prev, f"Not monotonic at t={t}: {val} < {prev}"
            prev = val


# -----------------------------------------------------------------------
# safe_place_object
# -----------------------------------------------------------------------


class TestSafePlaceObject:
    def test_no_terrain_returns_offset(self):
        """With no terrain, fall back to z=offset_z."""
        result = safe_place_object(5.0, 10.0)
        assert result is not None
        x, y, z = result
        assert x == 5.0
        assert y == 10.0
        assert abs(z - 0.02) < 1e-6  # default offset

    def test_custom_offset(self):
        result = safe_place_object(1.0, 2.0, offset_z=0.1)
        assert result is not None
        assert abs(result[2] - 0.1) < 1e-6

    def test_bounds_inside(self):
        result = safe_place_object(5.0, 5.0, bounds=(0, 0, 10, 10))
        assert result is not None

    def test_bounds_outside_x(self):
        result = safe_place_object(15.0, 5.0, bounds=(0, 0, 10, 10))
        assert result is None

    def test_bounds_outside_y(self):
        result = safe_place_object(5.0, -1.0, bounds=(0, 0, 10, 10))
        assert result is None

    def test_water_exclusion_above(self):
        """z above water_level should pass."""
        result = safe_place_object(5.0, 5.0, water_level=-1.0)
        assert result is not None

    def test_water_exclusion_below(self):
        """z below water_level should be rejected."""
        result = safe_place_object(5.0, 5.0, water_level=1.0)
        # fallback z=0.02, water_level=1.0 -> 0.02 < 1.0 -> None
        assert result is None

    def test_returns_tuple_of_three(self):
        result = safe_place_object(3.0, 4.0)
        assert result is not None
        assert len(result) == 3

    def test_terrain_name_none_ok(self):
        """Passing terrain_name=None should not crash."""
        result = safe_place_object(0.0, 0.0, terrain_name=None)
        assert result is not None

    def test_terrain_name_nonexistent(self):
        """Passing a non-existent terrain name falls back gracefully."""
        result = safe_place_object(0.0, 0.0, terrain_name="NonExistentTerrain")
        assert result is not None
        # Falls back to offset_z
        assert abs(result[2] - 0.02) < 1e-6

    def test_zero_offset(self):
        result = safe_place_object(1.0, 2.0, offset_z=0.0)
        assert result is not None
        assert result[2] == 0.0

    def test_bounds_edge(self):
        """On the boundary should pass."""
        result = safe_place_object(10.0, 10.0, bounds=(0, 0, 10, 10))
        assert result is not None

    def test_combined_bounds_and_water(self):
        """In bounds but underwater should reject."""
        result = safe_place_object(5.0, 5.0, water_level=1.0, bounds=(0, 0, 10, 10))
        assert result is None
