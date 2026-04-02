"""Tests for atmospheric_volumes handler."""

import pytest

from blender_addon.handlers.atmospheric_volumes import (
    ATMOSPHERIC_VOLUMES,
    BIOME_ATMOSPHERE_RULES,
    compute_atmospheric_placements,
    compute_volume_mesh_spec,
    estimate_atmosphere_performance,
)


# ---------------------------------------------------------------------------
# Volume definitions
# ---------------------------------------------------------------------------


class TestVolumeDefinitions:
    def test_seven_volume_types(self):
        assert len(ATMOSPHERIC_VOLUMES) == 7

    def test_all_volumes_have_required_fields(self):
        required = {"shape", "density", "height", "color", "opacity",
                     "animation", "animation_speed", "particle_type"}
        for name, vol in ATMOSPHERIC_VOLUMES.items():
            missing = required - set(vol.keys())
            assert not missing, f"Volume '{name}' missing: {missing}"

    def test_valid_shapes(self):
        valid = {"box", "sphere", "cone"}
        for name, vol in ATMOSPHERIC_VOLUMES.items():
            assert vol["shape"] in valid, f"Volume '{name}' has invalid shape"

    def test_color_is_rgb(self):
        for name, vol in ATMOSPHERIC_VOLUMES.items():
            assert len(vol["color"]) == 3


class TestBiomeRules:
    def test_all_biomes_have_rules(self):
        assert len(BIOME_ATMOSPHERE_RULES) >= 10

    def test_rules_reference_valid_volumes(self):
        for biome, rules in BIOME_ATMOSPHERE_RULES.items():
            for rule in rules:
                assert rule["volume"] in ATMOSPHERIC_VOLUMES, \
                    f"Biome '{biome}' references unknown volume '{rule['volume']}'"

    def test_rules_have_coverage_and_count(self):
        for biome, rules in BIOME_ATMOSPHERE_RULES.items():
            for rule in rules:
                assert "coverage" in rule
                assert "min_count" in rule
                assert 0 < rule["coverage"] <= 1.0


# ---------------------------------------------------------------------------
# Placement computation
# ---------------------------------------------------------------------------


class TestComputeAtmosphericPlacements:
    def test_known_biome(self):
        placements = compute_atmospheric_placements(
            "dark_forest", (0, 0, 100, 100), seed=42
        )
        assert len(placements) > 0

    def test_unknown_biome_uses_default(self):
        placements = compute_atmospheric_placements(
            "unknown_biome", (0, 0, 50, 50), seed=42
        )
        assert len(placements) > 0

    def test_placement_structure(self):
        placements = compute_atmospheric_placements(
            "corrupted_swamp", (0, 0, 100, 100)
        )
        for p in placements:
            assert "volume_type" in p
            assert "position" in p
            assert len(p["position"]) == 3
            assert "size" in p
            assert len(p["size"]) == 3
            assert "shape" in p
            assert "color" in p
            assert "density" in p
            assert "opacity" in p

    def test_placements_within_bounds(self):
        bounds = (10, 20, 50, 80)
        placements = compute_atmospheric_placements(
            "dark_forest", bounds, seed=42
        )
        for p in placements:
            x, y, z = p["position"]
            assert bounds[0] <= x <= bounds[2]
            assert bounds[1] <= y <= bounds[3]

    def test_density_scale(self):
        base = compute_atmospheric_placements(
            "frozen_peaks", (0, 0, 100, 100), density_scale=1.0
        )
        scaled = compute_atmospheric_placements(
            "frozen_peaks", (0, 0, 100, 100), density_scale=2.0
        )
        # More density should produce equal or more volumes
        assert len(scaled) >= len(base)

    def test_deterministic(self):
        p1 = compute_atmospheric_placements("ancient_ruins", (0, 0, 50, 50), seed=42)
        p2 = compute_atmospheric_placements("ancient_ruins", (0, 0, 50, 50), seed=42)
        assert p1 == p2

    def test_valid_volume_types(self):
        placements = compute_atmospheric_placements(
            "enchanted_glade", (0, 0, 100, 100)
        )
        for p in placements:
            assert p["volume_type"] in ATMOSPHERIC_VOLUMES


# ---------------------------------------------------------------------------
# Volume mesh spec
# ---------------------------------------------------------------------------


class TestComputeVolumeMeshSpec:
    def test_box_mesh(self):
        spec = compute_volume_mesh_spec("ground_fog")
        assert len(spec["vertices"]) == 8
        assert len(spec["faces"]) == 6
        assert spec["shape"] == "box"

    def test_sphere_mesh(self):
        spec = compute_volume_mesh_spec("fireflies")
        assert len(spec["vertices"]) == 12
        assert len(spec["faces"]) == 20
        assert spec["shape"] == "sphere"

    def test_cone_mesh(self):
        spec = compute_volume_mesh_spec("god_rays")
        assert len(spec["vertices"]) > 0
        assert spec["shape"] == "cone"

    def test_vertices_are_3d(self):
        for vol_type in ATMOSPHERIC_VOLUMES:
            spec = compute_volume_mesh_spec(vol_type)
            for v in spec["vertices"]:
                assert len(v) == 3

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Unknown volume type"):
            compute_volume_mesh_spec("nonexistent")

    def test_position_offset(self):
        spec = compute_volume_mesh_spec("ground_fog", position=(10, 20, 5))
        # All vertices should be near the given position
        for v in spec["vertices"]:
            # At least one coordinate should be close to the offset
            assert abs(v[0] - 10) < 50 or abs(v[1] - 20) < 50

    def test_scale_multiplier(self):
        s1 = compute_volume_mesh_spec("dust_motes", scale=1.0)
        s2 = compute_volume_mesh_spec("dust_motes", scale=2.0)
        assert s2["transform"]["scale"] == 2.0

    def test_face_indices_valid(self):
        for vol_type in ATMOSPHERIC_VOLUMES:
            spec = compute_volume_mesh_spec(vol_type)
            n = len(spec["vertices"])
            for face in spec["faces"]:
                for idx in face:
                    assert 0 <= idx < n, \
                        f"Volume '{vol_type}' has face index {idx} >= {n} vertices"


# ---------------------------------------------------------------------------
# Performance estimation
# ---------------------------------------------------------------------------


class TestPerformanceEstimation:
    def test_empty_placements(self):
        result = estimate_atmosphere_performance([])
        assert result["total_volumes"] == 0
        assert result["estimated_cost"] == 0

    def test_basic_budget(self):
        placements = [
            {"volume_type": "ground_fog"},
            {"volume_type": "dust_motes", "particle_type": "point"},
        ]
        result = estimate_atmosphere_performance(placements)
        assert result["total_volumes"] == 2
        assert result["particle_volumes"] == 1
        assert result["estimated_cost"] > 0

    def test_distortion_adds_cost(self):
        base = [{"volume_type": "ground_fog"}]
        distort = [{"volume_type": "void_shimmer", "distortion": True}]
        r_base = estimate_atmosphere_performance(base)
        r_dist = estimate_atmosphere_performance(distort)
        assert r_dist["estimated_cost"] > r_base["estimated_cost"]

    def test_recommendation_levels(self):
        # Low cost
        low = estimate_atmosphere_performance([{"volume_type": "fog"}])
        assert low["recommendation"] in ("excellent", "good")

        # High cost: many particle + distortion volumes
        many = [
            {"volume_type": "v", "particle_type": "point", "distortion": True}
            for _ in range(50)
        ]
        high = estimate_atmosphere_performance(many)
        assert "reduce" in high["recommendation"] or "excessive" in high["recommendation"]

    def test_volume_type_counts(self):
        placements = [
            {"volume_type": "ground_fog"},
            {"volume_type": "ground_fog"},
            {"volume_type": "fireflies"},
        ]
        result = estimate_atmosphere_performance(placements)
        counts = result["volume_type_counts"]
        assert counts["ground_fog"] == 2
        assert counts["fireflies"] == 1
