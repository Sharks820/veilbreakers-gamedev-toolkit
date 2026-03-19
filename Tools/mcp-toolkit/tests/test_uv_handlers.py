"""Unit tests for UV handler math functions.

Tests pure math functions from handlers/uv.py that do NOT require bpy/Blender.
Blender-dependent tests are marked with @pytest.mark.blender and skipped by default.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# _polygon_area_2d tests
# ---------------------------------------------------------------------------


class FakeUV:
    """Minimal stand-in for mathutils.Vector 2D, used by _polygon_area_2d."""

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


def test_polygon_area_2d_unit_square():
    """Unit square (1x1) should have area 1.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    coords = [FakeUV(0, 0), FakeUV(1, 0), FakeUV(1, 1), FakeUV(0, 1)]
    assert abs(_polygon_area_2d(coords) - 1.0) < 1e-9


def test_polygon_area_2d_triangle():
    """Triangle with vertices (0,0), (4,0), (0,3) should have area 6.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    coords = [FakeUV(0, 0), FakeUV(4, 0), FakeUV(0, 3)]
    assert abs(_polygon_area_2d(coords) - 6.0) < 1e-9


def test_polygon_area_2d_degenerate_line():
    """Fewer than 3 coords should return 0.0."""
    from blender_addon.handlers.uv import _polygon_area_2d

    assert _polygon_area_2d([FakeUV(0, 0), FakeUV(1, 1)]) == 0.0
    assert _polygon_area_2d([FakeUV(0, 0)]) == 0.0
    assert _polygon_area_2d([]) == 0.0


def test_polygon_area_2d_pentagon():
    """Regular pentagon with circumradius 1 should have area ~2.378."""
    from blender_addon.handlers.uv import _polygon_area_2d

    n = 5
    coords = [
        FakeUV(math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n))
        for k in range(n)
    ]
    expected = (n / 2) * math.sin(2 * math.pi / n)  # standard formula
    assert abs(_polygon_area_2d(coords) - expected) < 1e-6


# ---------------------------------------------------------------------------
# Texel density formula tests
# ---------------------------------------------------------------------------


def test_texel_density_formula_basic():
    """TD = sqrt(uv_area / face_3d_area) * texture_size."""
    # uv_area=0.01, face_3d_area=1.0, texture_size=1024
    # TD = sqrt(0.01 / 1.0) * 1024 = 0.1 * 1024 = 102.4
    uv_area = 0.01
    face_3d_area = 1.0
    texture_size = 1024
    td = math.sqrt(uv_area / face_3d_area) * texture_size
    assert abs(td - 102.4) < 1e-6


def test_texel_density_formula_scaled():
    """Double the texture size should double the texel density."""
    uv_area = 0.04
    face_3d_area = 1.0
    td_512 = math.sqrt(uv_area / face_3d_area) * 512
    td_1024 = math.sqrt(uv_area / face_3d_area) * 1024
    assert abs(td_1024 / td_512 - 2.0) < 1e-9


def test_texel_density_formula_equal_areas():
    """When uv_area == face_3d_area, TD should equal texture_size."""
    uv_area = 1.0
    face_3d_area = 1.0
    texture_size = 2048
    td = math.sqrt(uv_area / face_3d_area) * texture_size
    assert abs(td - 2048.0) < 1e-6
