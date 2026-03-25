"""Tests for the AAA mesh geometry enhancement pipeline.

Tests pure-logic components without Blender:
- Enhancement profile loading and defaults
- Sharp edge detection by dihedral angle
- MeshSpec edge annotation integration
- Profile parameter overrides
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.mesh_enhance import (
    ENHANCE_PROFILES,
    compute_sharp_edges_pure,
    get_enhance_profile,
    list_enhance_profiles,
)
from blender_addon.handlers.procedural_meshes import (
    _auto_detect_sharp_edges,
    _make_box,
    _make_cylinder,
    _make_result,
    _merge_meshes,
)


# ---------------------------------------------------------------------------
# Profile configuration tests
# ---------------------------------------------------------------------------


class TestEnhanceProfiles:
    """Test enhancement profile definitions and loading."""

    def test_all_profiles_exist(self):
        expected = {"weapon", "architecture", "organic", "prop", "character", "vegetation"}
        assert set(ENHANCE_PROFILES.keys()) == expected

    def test_profile_required_keys(self):
        required_keys = {
            "sharp_angle_threshold",
            "crease_value",
            "subdiv_levels_viewport",
            "subdiv_levels_render",
            "bevel_width",
            "bevel_segments",
            "bevel_angle_limit",
            "use_weighted_normals",
            "smooth_shading",
            "auto_smooth_angle",
            "displacement_strength",
            "displacement_scale",
            "description",
        }
        for name, profile in ENHANCE_PROFILES.items():
            missing = required_keys - set(profile.keys())
            assert not missing, f"Profile '{name}' missing keys: {missing}"

    def test_get_enhance_profile_returns_copy(self):
        p1 = get_enhance_profile("weapon")
        p2 = get_enhance_profile("weapon")
        assert p1 is not p2
        assert p1 == p2

    def test_get_enhance_profile_unknown_falls_back_to_prop(self):
        result = get_enhance_profile("nonexistent")
        expected = get_enhance_profile("prop")
        assert result == expected

    def test_list_enhance_profiles(self):
        profiles = list_enhance_profiles()
        assert len(profiles) == 6
        for name, desc in profiles.items():
            assert isinstance(desc, str)
            assert len(desc) > 5

    def test_weapon_profile_has_zero_displacement(self):
        p = get_enhance_profile("weapon")
        assert p["displacement_strength"] == 0.0

    def test_organic_profile_has_high_subdiv(self):
        p = get_enhance_profile("organic")
        assert p["subdiv_levels_viewport"] >= 2

    def test_vegetation_profile_has_no_bevel(self):
        p = get_enhance_profile("vegetation")
        assert p["bevel_width"] == 0.0
        assert p["bevel_segments"] == 0

    def test_architecture_profile_has_full_crease(self):
        p = get_enhance_profile("architecture")
        assert p["crease_value"] == 1.0

    def test_all_profiles_have_positive_auto_smooth(self):
        for name, profile in ENHANCE_PROFILES.items():
            assert profile["auto_smooth_angle"] > 0, f"Profile '{name}' has non-positive auto_smooth_angle"


# ---------------------------------------------------------------------------
# Sharp edge detection tests (pure logic)
# ---------------------------------------------------------------------------


class TestSharpEdgeDetection:
    """Test dihedral angle-based sharp edge detection."""

    @staticmethod
    def _cube_geometry():
        """Return a unit cube's vertices and faces."""
        verts, faces = _make_box(0, 0, 0, 0.5, 0.5, 0.5)
        return verts, faces

    def test_cube_all_edges_sharp_at_low_threshold(self):
        """A cube has 90-degree edges -- all should be sharp at 30 deg threshold."""
        verts, faces = self._cube_geometry()
        sharp = compute_sharp_edges_pure(verts, faces, angle_threshold_deg=30.0)
        # A cube has 12 edges, all at 90 degrees
        assert len(sharp) == 12

    def test_cube_no_edges_sharp_at_high_threshold(self):
        """No edges sharp when threshold exceeds 90 degrees."""
        verts, faces = self._cube_geometry()
        sharp = compute_sharp_edges_pure(verts, faces, angle_threshold_deg=100.0)
        assert len(sharp) == 0

    def test_empty_geometry_returns_empty(self):
        sharp = compute_sharp_edges_pure([], [], angle_threshold_deg=30.0)
        assert sharp == []

    def test_single_face_all_boundary_edges(self):
        """A single triangle: all 3 edges are boundary (1 face) -> all sharp."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        faces = [(0, 1, 2)]
        sharp = compute_sharp_edges_pure(verts, faces, angle_threshold_deg=30.0)
        assert len(sharp) == 3

    def test_coplanar_faces_no_sharp_edges(self):
        """Two coplanar triangles sharing an edge: 0 degree dihedral -> not sharp."""
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2), (0, 2, 3)]
        sharp = compute_sharp_edges_pure(verts, faces, angle_threshold_deg=1.0)
        # Only boundary edges (4 outer edges are boundary)
        # The shared edge (0,2) is coplanar -> not sharp
        boundary_count = sum(1 for e in sharp if True)
        # 4 boundary edges + 0 sharp interior
        assert len(sharp) == 4

    def test_sharp_edges_are_sorted_pairs(self):
        """Each sharp edge pair has min(a,b), max(a,b) ordering."""
        verts, faces = self._cube_geometry()
        sharp = compute_sharp_edges_pure(verts, faces, angle_threshold_deg=30.0)
        for a, b in sharp:
            assert a < b, f"Edge ({a}, {b}) not sorted"

    def test_auto_detect_matches_compute_pure(self):
        """_auto_detect_sharp_edges should match compute_sharp_edges_pure."""
        verts, faces = self._cube_geometry()
        sharp_pure = compute_sharp_edges_pure(verts, faces, 35.0)
        sharp_auto = _auto_detect_sharp_edges(verts, faces, 35.0)
        # Convert to comparable sets
        set_pure = {tuple(e) for e in sharp_pure}
        set_auto = {(min(e[0], e[1]), max(e[0], e[1])) for e in sharp_auto}
        assert set_pure == set_auto


# ---------------------------------------------------------------------------
# MeshSpec edge annotation integration tests
# ---------------------------------------------------------------------------


class TestMeshSpecEdgeAnnotations:
    """Test that _make_result embeds sharp edge data in MeshSpec."""

    def test_make_result_includes_sharp_edges(self):
        """_make_result should auto-detect and embed sharp_edges."""
        verts, faces = _make_box(0, 0, 0, 0.5, 0.5, 0.5)
        result = _make_result("TestBox", verts, faces)
        assert "sharp_edges" in result
        assert len(result["sharp_edges"]) == 12  # cube has 12 sharp edges

    def test_make_result_sharp_angle_zero_skips_detection(self):
        """sharp_angle=0 should skip edge detection."""
        verts, faces = _make_box(0, 0, 0, 0.5, 0.5, 0.5)
        result = _make_result("TestBox", verts, faces, sharp_angle=0)
        assert "sharp_edges" not in result

    def test_cylinder_has_fewer_sharp_edges_at_high_threshold(self):
        """A cylinder with many segments should have fewer sharp edges at wider angles."""
        verts, faces = _make_cylinder(0, 0, 0, 0.5, 1.0, segments=16)
        sharp_tight = _auto_detect_sharp_edges(verts, faces, 10.0)
        sharp_wide = _auto_detect_sharp_edges(verts, faces, 45.0)
        assert len(sharp_tight) >= len(sharp_wide)

    def test_merged_mesh_preserves_sharp_edges(self):
        """Sharp edges survive _merge_meshes."""
        box1_v, box1_f = _make_box(0, 0, 0, 0.5, 0.5, 0.5)
        box2_v, box2_f = _make_box(2, 0, 0, 0.5, 0.5, 0.5)
        merged_v, merged_f = _merge_meshes((box1_v, box1_f), (box2_v, box2_f))
        sharp = _auto_detect_sharp_edges(merged_v, merged_f, 35.0)
        # Two cubes = 24 sharp edges (12 each, no shared edges)
        assert len(sharp) == 24

    def test_make_result_metadata_preserved(self):
        """Edge annotation doesn't break existing metadata."""
        verts, faces = _make_box(0, 0, 0, 0.5, 0.5, 0.5)
        result = _make_result("TestBox", verts, faces, category="test")
        assert result["metadata"]["name"] == "TestBox"
        assert result["metadata"]["category"] == "test"
        assert result["metadata"]["poly_count"] == len(faces)
        assert result["metadata"]["vertex_count"] == len(verts)


# ---------------------------------------------------------------------------
# Performance / scale tests
# ---------------------------------------------------------------------------


class TestEdgeDetectionPerformance:
    """Ensure edge detection handles larger meshes without issue."""

    def test_large_cylinder_completes(self):
        """64-segment cylinder edge detection should complete quickly."""
        verts, faces = _make_cylinder(0, 0, 0, 1.0, 2.0, segments=64)
        sharp = _auto_detect_sharp_edges(verts, faces, 35.0)
        # Should detect the cap edges as sharp (boundary) + some side edges
        assert len(sharp) > 0

    def test_merged_many_boxes(self):
        """Edge detection on 10 merged boxes."""
        parts = []
        for i in range(10):
            v, f = _make_box(i * 3, 0, 0, 0.5, 0.5, 0.5)
            parts.append((v, f))
        merged_v, merged_f = _merge_meshes(*parts)
        sharp = _auto_detect_sharp_edges(merged_v, merged_f, 35.0)
        assert len(sharp) == 120  # 10 cubes * 12 edges each
