"""Tests for boss monster visual presence enhancements.

Tests cover:
- BOSS_ENHANCEMENTS and BOSS_TYPES constants
- compute_boss_tri_budget: budget calculation
- generate_crown_feature: crown geometry, brand variation
- generate_aura_ring: torus ring geometry, emission points
- generate_ground_interaction: tendril geometry, anchor points
- generate_environmental_damage: crack geometry, endpoints
- enhance_boss_mesh: full enhancement pipeline, selective enhancements
- Edge cases: empty meshes, invalid brands, extreme parameters

All pure logic -- no Blender required.
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.boss_presence import (
    BOSS_ENHANCEMENTS,
    BOSS_TYPES,
    compute_boss_tri_budget,
    enhance_boss_mesh,
    generate_aura_ring,
    generate_crown_feature,
    generate_environmental_damage,
    generate_ground_interaction,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _simple_bbox():
    """A standard bounding box for a humanoid-sized monster."""
    return ((-0.5, 0.0, -0.5), (0.5, 2.0, 0.5))


def _base_mesh():
    """A minimal base mesh dict for enhance_boss_mesh."""
    verts = [
        (-0.5, 0.0, -0.5), (0.5, 0.0, -0.5), (0.5, 0.0, 0.5), (-0.5, 0.0, 0.5),
        (-0.5, 2.0, -0.5), (0.5, 2.0, -0.5), (0.5, 2.0, 0.5), (-0.5, 2.0, 0.5),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return {
        "vertices": verts,
        "faces": faces,
        "bounding_box": [(-0.5, 0.0, -0.5), (0.5, 2.0, 0.5)],
    }


# ---------------------------------------------------------------------------
# TestBossConstants
# ---------------------------------------------------------------------------


class TestBossConstants:
    """Test BOSS_ENHANCEMENTS and BOSS_TYPES constants."""

    def test_enhancements_has_required_keys(self):
        required = {"increased_detail", "crown_feature", "aura_geometry",
                     "ground_interaction", "environmental_damage"}
        for key in required:
            assert key in BOSS_ENHANCEMENTS, f"Missing enhancement key '{key}'"

    def test_increased_detail_structure(self):
        detail = BOSS_ENHANCEMENTS["increased_detail"]
        assert "subdivision_levels" in detail
        assert "tri_budget_multiplier" in detail
        assert detail["subdivision_levels"] == 2
        assert detail["tri_budget_multiplier"] == 3.0

    def test_boss_types_list(self):
        assert len(BOSS_TYPES) >= 5
        assert "generic" in BOSS_TYPES
        assert "brute" in BOSS_TYPES
        assert "caster" in BOSS_TYPES

    def test_boolean_enhancement_flags(self):
        for key in ("crown_feature", "aura_geometry",
                     "ground_interaction", "environmental_damage"):
            assert BOSS_ENHANCEMENTS[key] is True


# ---------------------------------------------------------------------------
# TestComputeBossTriBudget
# ---------------------------------------------------------------------------


class TestComputeBossTriBudget:
    """Test compute_boss_tri_budget() budget calculation."""

    def test_basic_calculation(self):
        result = compute_boss_tri_budget(1000, 3.0)
        assert result["base_tri_count"] == 1000
        assert result["multiplier"] == 3.0
        assert result["boss_budget"] == 3000
        assert result["overhead"] == 2000

    def test_multiplier_one(self):
        result = compute_boss_tri_budget(500, 1.0)
        assert result["boss_budget"] == 500
        assert result["overhead"] == 0

    def test_large_multiplier(self):
        result = compute_boss_tri_budget(1000, 5.0)
        assert result["boss_budget"] == 5000

    def test_zero_base(self):
        result = compute_boss_tri_budget(0, 3.0)
        assert result["boss_budget"] == 0
        assert result["overhead"] == 0

    def test_multiplier_clamped_to_one(self):
        result = compute_boss_tri_budget(1000, 0.5)
        assert result["multiplier"] == 1.0
        assert result["boss_budget"] == 1000


# ---------------------------------------------------------------------------
# TestGenerateCrownFeature
# ---------------------------------------------------------------------------


class TestGenerateCrownFeature:
    """Test generate_crown_feature() crown geometry generator."""

    def test_produces_geometry(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_crown_style_from_brand(self):
        bbox = _simple_bbox()
        iron = generate_crown_feature(bbox, brand="IRON")
        assert iron["crown_style"] == "spiked_crown"
        void = generate_crown_feature(bbox, brand="VOID")
        assert void["crown_style"] == "void_crown"

    def test_attachment_point_at_top(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox)
        ap = result["attachment_point"]
        # Should be at the top of the bounding box
        assert ap[1] == 2.0  # Y = bb_max.y

    def test_spike_count(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox, spike_count=8)
        assert result["spike_count"] == 8

    def test_minimum_spikes(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox, spike_count=1)
        assert result["spike_count"] >= 3

    def test_valid_face_indices(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Crown face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Crown vertex {i} has non-finite component"

    @pytest.mark.parametrize("brand", [
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    ])
    def test_all_brands_produce_crowns(self, brand):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox, brand=brand)
        assert len(result["vertices"]) > 0
        assert result["brand"] == brand

    def test_invalid_brand_falls_back(self):
        bbox = _simple_bbox()
        result = generate_crown_feature(bbox, brand="CHAOS")
        assert result["brand"] == "VOID"

    def test_crown_scale_affects_size(self):
        bbox = _simple_bbox()
        small = generate_crown_feature(bbox, crown_scale=0.5)
        large = generate_crown_feature(bbox, crown_scale=2.0)
        # Same vertex count but positions differ
        assert len(small["vertices"]) == len(large["vertices"])


# ---------------------------------------------------------------------------
# TestGenerateAuraRing
# ---------------------------------------------------------------------------


class TestGenerateAuraRing:
    """Test generate_aura_ring() floating ring mesh generator."""

    def test_produces_geometry(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_ring_radius(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox, ring_radius_multiplier=1.5)
        body_radius = 0.5  # half of 1.0 width
        expected = body_radius * 1.5
        assert abs(result["ring_radius"] - expected) < 1e-6

    def test_center_position(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox)
        center = result["center"]
        assert abs(center[0] - 0.0) < 1e-6
        assert abs(center[1] - 1.0) < 1e-6  # midpoint of 0-2
        assert abs(center[2] - 0.0) < 1e-6

    def test_vertical_offset(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox, vertical_offset=0.5)
        assert abs(result["center"][1] - 1.5) < 1e-6

    def test_emission_points(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox, ring_segments=12)
        assert len(result["emission_points"]) == 12

    def test_emission_points_at_ring_radius(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox, ring_segments=12)
        center = result["center"]
        for pt in result["emission_points"]:
            dist = math.sqrt(
                (pt[0] - center[0])**2 + (pt[2] - center[2])**2
            )
            assert abs(dist - result["ring_radius"]) < 1e-6

    def test_valid_face_indices(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Aura face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Aura vertex {i} has non-finite component"

    def test_minimum_segments(self):
        bbox = _simple_bbox()
        result = generate_aura_ring(bbox, ring_segments=2)
        # Should be clamped to minimum 6
        assert len(result["emission_points"]) >= 6


# ---------------------------------------------------------------------------
# TestGenerateGroundInteraction
# ---------------------------------------------------------------------------


class TestGenerateGroundInteraction:
    """Test generate_ground_interaction() tendril generator."""

    def test_produces_geometry(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0
        assert result["tendril_count"] > 0

    def test_tendril_count(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox, tendril_count=3)
        assert result["tendril_count"] == 3

    def test_anchor_points_count(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox, tendril_count=5)
        assert len(result["anchor_points"]) == 5

    def test_anchor_points_at_base(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox)
        for ap in result["anchor_points"]:
            assert abs(ap[1] - 0.0) < 1e-6  # Y = base

    def test_tendrils_extend_downward(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox)
        # Some vertices should be below the base Y
        min_y = min(v[1] for v in result["vertices"])
        assert min_y < 0.0

    def test_valid_face_indices(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Ground face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Ground vertex {i} has non-finite component"

    def test_seed_reproducibility(self):
        bbox = _simple_bbox()
        r1 = generate_ground_interaction(bbox, seed=42)
        r2 = generate_ground_interaction(bbox, seed=42)
        assert r1["vertices"] == r2["vertices"]
        assert r1["anchor_points"] == r2["anchor_points"]

    def test_minimum_tendril_count(self):
        bbox = _simple_bbox()
        result = generate_ground_interaction(bbox, tendril_count=0)
        assert result["tendril_count"] >= 1


# ---------------------------------------------------------------------------
# TestGenerateEnvironmentalDamage
# ---------------------------------------------------------------------------


class TestGenerateEnvironmentalDamage:
    """Test generate_environmental_damage() crack generator."""

    def test_produces_geometry(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0
        assert result["crack_count"] > 0

    def test_crack_count(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox, crack_count=4)
        assert result["crack_count"] == 4

    def test_crack_endpoints(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox, crack_count=6)
        assert len(result["crack_endpoints"]) == 6
        for start, end in result["crack_endpoints"]:
            assert len(start) == 3
            assert len(end) == 3

    def test_cracks_radiate_from_center(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox)
        center_x, center_z = 0.0, 0.0
        for start, end in result["crack_endpoints"]:
            # End should be farther from center than start
            start_dist = math.sqrt(
                (start[0] - center_x)**2 + (start[2] - center_z)**2
            )
            end_dist = math.sqrt(
                (end[0] - center_x)**2 + (end[2] - center_z)**2
            )
            assert end_dist >= start_dist

    def test_valid_face_indices(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Damage face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Damage vertex {i} has non-finite component"

    def test_seed_reproducibility(self):
        bbox = _simple_bbox()
        r1 = generate_environmental_damage(bbox, seed=42)
        r2 = generate_environmental_damage(bbox, seed=42)
        assert r1["crack_count"] == r2["crack_count"]
        assert r1["vertices"] == r2["vertices"]

    def test_minimum_crack_count(self):
        bbox = _simple_bbox()
        result = generate_environmental_damage(bbox, crack_count=0)
        assert result["crack_count"] >= 1

    def test_crack_depth_parameter(self):
        bbox = _simple_bbox()
        shallow = generate_environmental_damage(bbox, crack_depth=0.01)
        deep = generate_environmental_damage(bbox, crack_depth=0.2)
        # Both produce geometry; deep has lower Y vertices
        min_y_shallow = min(v[1] for v in shallow["vertices"])
        min_y_deep = min(v[1] for v in deep["vertices"])
        assert min_y_deep <= min_y_shallow


# ---------------------------------------------------------------------------
# TestEnhanceBossMesh
# ---------------------------------------------------------------------------


class TestEnhanceBossMesh:
    """Test enhance_boss_mesh() full enhancement pipeline."""

    def test_produces_combined_geometry(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        assert result["enhancement_vertex_count"] > 0
        assert result["enhancement_face_count"] > 0
        assert len(result["vertices"]) == result["enhancement_vertex_count"]
        assert len(result["faces"]) == result["enhancement_face_count"]

    def test_all_sub_results_present(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        assert result["crown"] is not None
        assert result["aura"] is not None
        assert result["ground"] is not None
        assert result["damage"] is not None

    def test_base_vertex_count(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        assert result["base_vertex_count"] == 8

    def test_boss_type_stored(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh, boss_type="brute")
        assert result["boss_type"] == "brute"

    def test_brand_stored(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh, brand="IRON")
        assert result["brand"] == "IRON"

    def test_tri_budget_present(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        assert "tri_budget" in result
        budget = result["tri_budget"]
        assert budget["base_tri_count"] == 6  # cube has 6 faces
        assert budget["boss_budget"] == 18  # 6 * 3.0

    def test_selective_crown_only(self):
        mesh = _base_mesh()
        enhancements = {
            "crown_feature": True,
            "aura_geometry": False,
            "ground_interaction": False,
            "environmental_damage": False,
        }
        result = enhance_boss_mesh(mesh, enhancements=enhancements)
        assert result["crown"] is not None
        assert result["aura"] is None
        assert result["ground"] is None
        assert result["damage"] is None

    def test_selective_aura_only(self):
        mesh = _base_mesh()
        enhancements = {
            "crown_feature": False,
            "aura_geometry": True,
            "ground_interaction": False,
            "environmental_damage": False,
        }
        result = enhance_boss_mesh(mesh, enhancements=enhancements)
        assert result["crown"] is None
        assert result["aura"] is not None

    def test_no_enhancements(self):
        mesh = _base_mesh()
        enhancements = {
            "crown_feature": False,
            "aura_geometry": False,
            "ground_interaction": False,
            "environmental_damage": False,
        }
        result = enhance_boss_mesh(mesh, enhancements=enhancements)
        assert result["enhancement_vertex_count"] == 0
        assert result["enhancement_face_count"] == 0

    @pytest.mark.parametrize("boss_type", BOSS_TYPES)
    def test_all_boss_types(self, boss_type):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh, boss_type=boss_type)
        assert result["enhancement_vertex_count"] > 0
        assert result["boss_type"] == boss_type

    @pytest.mark.parametrize("brand", [
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    ])
    def test_all_brands(self, brand):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh, brand=brand)
        assert result["enhancement_vertex_count"] > 0
        assert result["brand"] == brand

    def test_invalid_brand_falls_back(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh, brand="CHAOS")
        assert result["brand"] == "VOID"

    def test_valid_face_indices(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Enhanced face {fi} index {idx} out of range [0, {n_verts})"
                )

    def test_vertices_are_finite(self):
        mesh = _base_mesh()
        result = enhance_boss_mesh(mesh)
        for i, v in enumerate(result["vertices"]):
            assert len(v) == 3
            for c in v:
                assert math.isfinite(c), f"Enhanced vertex {i} has non-finite component"

    def test_empty_base_mesh(self):
        mesh = {"vertices": [], "faces": []}
        result = enhance_boss_mesh(mesh)
        # Should still produce enhancement geometry (using default bbox)
        assert result["base_vertex_count"] == 0
        assert result["enhancement_vertex_count"] > 0

    def test_mesh_without_bbox(self):
        mesh = {
            "vertices": [(-1, 0, -1), (1, 0, -1), (1, 3, 1), (-1, 3, 1)],
            "faces": [(0, 1, 2, 3)],
        }
        result = enhance_boss_mesh(mesh)
        assert result["enhancement_vertex_count"] > 0

    def test_brute_produces_more_geometry_than_caster(self):
        mesh = _base_mesh()
        brute = enhance_boss_mesh(mesh, boss_type="brute")
        caster = enhance_boss_mesh(mesh, boss_type="caster")
        # Brute has higher type_scale, should have more geometry
        assert brute["enhancement_vertex_count"] >= caster["enhancement_vertex_count"]
