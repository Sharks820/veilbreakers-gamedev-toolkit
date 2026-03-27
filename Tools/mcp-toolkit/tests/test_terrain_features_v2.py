"""Tests for terrain_features v2 generators (natural arch, geyser, sinkhole,
floating rocks, ice formation, lava flow).

All modules are pure logic (no bpy/bmesh). Tests verify mesh spec structure,
determinism, edge cases, and feature correctness.
"""

import math

import pytest


# ===================================================================
# Natural Arch Tests
# ===================================================================


class TestGenerateNaturalArch:
    """Test natural arch terrain generation."""

    def test_basic_arch(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(span_width=8, arch_height=6, thickness=2, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 4

    def test_arch_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(span_width=10, arch_height=8, thickness=3, seed=42)
        assert result["dimensions"]["span_width"] == 10
        assert result["dimensions"]["arch_height"] == 8
        assert result["dimensions"]["thickness"] == 3

    def test_arch_has_two_pillars(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(seed=42)
        assert len(result["pillars"]) == 2
        for pillar in result["pillars"]:
            assert "position" in pillar
            assert pillar["width"] > 0
            assert pillar["height"] > 0

    def test_arch_pillars_on_opposite_sides(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(span_width=8, seed=42)
        pillars = result["pillars"]
        # One pillar should be on the negative X side, one on positive
        x_positions = [p["position"][0] for p in pillars]
        assert min(x_positions) < 0
        assert max(x_positions) > 0

    def test_arch_apex(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(arch_height=6, seed=42)
        assert result["arch_apex"][2] == 6.0  # Z = arch_height

    def test_arch_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_arch_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        r1 = generate_natural_arch(seed=42)
        r2 = generate_natural_arch(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_arch_different_seeds_differ(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        r1 = generate_natural_arch(seed=42)
        r2 = generate_natural_arch(seed=99)
        assert r1["mesh"]["vertices"] != r2["mesh"]["vertices"]

    def test_arch_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_arch_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(span_width=12, arch_height=10, thickness=3, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000

    def test_arch_roughness_zero(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(roughness=0.0, seed=42)
        assert result["vertex_count"] > 0

    def test_arch_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_natural_arch

        result = generate_natural_arch(seed=42)
        assert "arch_stone" in result["materials"]
        assert "pillar_stone" in result["materials"]
        assert "moss" in result["materials"]


# ===================================================================
# Geyser Tests
# ===================================================================


class TestGenerateGeyser:
    """Test geyser terrain generation."""

    def test_basic_geyser(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(pool_radius=3, pool_depth=0.5, vent_height=1, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 5

    def test_geyser_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(pool_radius=4, pool_depth=0.8, vent_height=2, mineral_rim_width=1.0, seed=42)
        assert result["dimensions"]["pool_radius"] == 4
        assert result["dimensions"]["pool_depth"] == 0.8
        assert result["dimensions"]["vent_height"] == 2
        assert result["dimensions"]["mineral_rim_width"] == 1.0

    def test_geyser_vent(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(vent_height=1.5, seed=42)
        assert result["vent"]["height"] == 1.5
        assert result["vent"]["position"][2] == 1.5
        assert result["vent"]["base_radius"] > 0

    def test_geyser_pool(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(pool_radius=3, pool_depth=0.5, seed=42)
        assert result["pool"]["radius"] == 3
        assert result["pool"]["depth"] == 0.5

    def test_geyser_terraces(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(seed=42)
        assert len(result["terraces"]) == 3  # 3 terrace tiers
        for terrace in result["terraces"]:
            assert "tier" in terrace
            assert terrace["inner_radius"] > 0
            assert terrace["outer_radius"] > terrace["inner_radius"]

    def test_geyser_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_geyser_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        r1 = generate_geyser(seed=42)
        r2 = generate_geyser(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_geyser_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_geyser_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(seed=42)
        assert "mineral_deposit" in result["materials"]
        assert "pool_water" in result["materials"]
        assert "vent_rock" in result["materials"]
        assert "sulfur_crust" in result["materials"]

    def test_geyser_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_geyser

        result = generate_geyser(pool_radius=5, mineral_rim_width=1.5, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000


# ===================================================================
# Sinkhole Tests
# ===================================================================


class TestGenerateSinkhole:
    """Test sinkhole terrain generation."""

    def test_basic_sinkhole(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(radius=5, depth=8, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 5

    def test_sinkhole_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(radius=7, depth=10, wall_roughness=0.3, rubble_density=0.5, seed=42)
        assert result["dimensions"]["radius"] == 7
        assert result["dimensions"]["depth"] == 10
        assert result["dimensions"]["wall_roughness"] == 0.3
        assert result["dimensions"]["rubble_density"] == 0.5

    def test_sinkhole_with_cave(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(has_bottom_cave=True, seed=42)
        assert result["cave"] is not None
        assert "position" in result["cave"]
        assert result["cave"]["width"] > 0
        assert result["cave"]["height"] > 0

    def test_sinkhole_no_cave(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(has_bottom_cave=False, seed=42)
        assert result["cave"] is None

    def test_sinkhole_rim(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(radius=5, seed=42)
        assert result["rim"]["radius"] == 5
        assert len(result["rim"]["vertices"]) > 0

    def test_sinkhole_rubble(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(rubble_density=0.5, seed=42)
        assert len(result["rubble"]) > 0
        for piece in result["rubble"]:
            assert "position" in piece
            assert piece["size"] > 0

    def test_sinkhole_zero_rubble(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(rubble_density=0.0, seed=42)
        assert len(result["rubble"]) == 0

    def test_sinkhole_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_sinkhole_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        r1 = generate_sinkhole(seed=42)
        r2 = generate_sinkhole(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_sinkhole_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_sinkhole_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(seed=42)
        assert "dirt_wall" in result["materials"]
        assert "exposed_rock" in result["materials"]
        assert "rubble" in result["materials"]

    def test_sinkhole_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_sinkhole

        result = generate_sinkhole(radius=8, depth=12, rubble_density=0.8, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000


# ===================================================================
# Floating Rocks Tests
# ===================================================================


class TestGenerateFloatingRocks:
    """Test floating rocks terrain generation."""

    def test_basic_floating_rocks(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=5, base_height=4, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 4

    def test_floating_rocks_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=3, base_height=5, max_size=4, chain_links=3, seed=42)
        assert result["dimensions"]["count"] == 3
        assert result["dimensions"]["base_height"] == 5
        assert result["dimensions"]["max_size"] == 4
        assert result["dimensions"]["chain_links"] == 3

    def test_floating_rocks_count(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=7, seed=42)
        assert len(result["rocks"]) == 7

    def test_floating_rocks_above_ground(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(base_height=4, seed=42)
        for rock in result["rocks"]:
            assert rock["center"][2] >= 4.0  # All rocks at or above base_height

    def test_floating_rocks_size(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(max_size=3, seed=42)
        for rock in result["rocks"]:
            assert rock["size"] <= 3.0
            assert rock["size"] > 0

    def test_floating_rocks_chains(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=3, chain_links=2, seed=42)
        assert len(result["chains"]) == 3  # One chain per rock
        for chain in result["chains"]:
            assert "anchor" in chain
            assert "rock_attach" in chain
            assert len(chain["links"]) == 2
            assert chain["anchor"][2] == 0.0  # Anchor at ground level

    def test_floating_rocks_no_chains(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(chain_links=0, seed=42)
        assert len(result["chains"]) == 0

    def test_floating_rocks_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_floating_rocks_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        r1 = generate_floating_rocks(seed=42)
        r2 = generate_floating_rocks(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_floating_rocks_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_floating_rocks_single(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=1, seed=42)
        assert len(result["rocks"]) == 1
        assert result["vertex_count"] > 0

    def test_floating_rocks_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(count=8, max_size=4, chain_links=3, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000

    def test_floating_rocks_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_floating_rocks

        result = generate_floating_rocks(seed=42)
        assert "rock_surface" in result["materials"]
        assert "rock_underside" in result["materials"]
        assert "chain_metal" in result["materials"]


# ===================================================================
# Ice Formation Tests
# ===================================================================


class TestGenerateIceFormation:
    """Test ice formation terrain generation."""

    def test_basic_ice_formation(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(width=6, height=4, depth=3, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 5

    def test_ice_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(width=8, height=5, depth=4, stalactite_count=10, seed=42)
        assert result["dimensions"]["width"] == 8
        assert result["dimensions"]["height"] == 5
        assert result["dimensions"]["depth"] == 4
        assert result["dimensions"]["stalactite_count"] == 10
        assert result["dimensions"]["ice_wall"] is True

    def test_ice_stalactites(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(stalactite_count=8, seed=42)
        assert len(result["stalactites"]) == 8
        for stl in result["stalactites"]:
            assert "tip_position" in stl
            assert stl["length"] > 0
            assert stl["base_radius"] > 0

    def test_ice_zero_stalactites(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(stalactite_count=0, ice_wall=False, seed=42)
        assert len(result["stalactites"]) == 0

    def test_ice_wall_present(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(ice_wall=True, seed=42)
        assert result["wall_info"] is not None
        assert result["wall_info"]["width"] > 0
        assert result["wall_info"]["height"] > 0
        assert len(result["wall_info"]["refraction_zones"]) > 0

    def test_ice_no_wall(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(ice_wall=False, seed=42)
        assert result["wall_info"] is None

    def test_ice_stalactites_hang_from_top(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(height=4, stalactite_count=5, seed=42)
        for stl in result["stalactites"]:
            # Tip position Z should be less than height (hanging down)
            assert stl["tip_position"][2] < 4.0

    def test_ice_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_ice_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        r1 = generate_ice_formation(seed=42)
        r2 = generate_ice_formation(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_ice_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_ice_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(seed=42)
        assert "clear_ice" in result["materials"]
        assert "frosted_ice" in result["materials"]
        assert "blue_ice" in result["materials"]
        assert "ice_wall_refraction" in result["materials"]
        assert "icicle_tip" in result["materials"]

    def test_ice_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_ice_formation

        result = generate_ice_formation(width=10, height=6, stalactite_count=15, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000


# ===================================================================
# Lava Flow Tests
# ===================================================================


class TestGenerateLavaFlow:
    """Test lava flow terrain generation."""

    def test_basic_lava_flow(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=30, width=4, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
        assert len(result["materials"]) == 4

    def test_lava_dimensions(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=40, width=5, edge_crust_width=1.5, flow_segments=25, seed=42)
        assert result["dimensions"]["length"] == 40
        assert result["dimensions"]["width"] == 5
        assert result["dimensions"]["edge_crust_width"] == 1.5
        assert result["dimensions"]["flow_segments"] == 25

    def test_lava_flow_path(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=30, flow_segments=20, seed=42)
        assert len(result["flow_path"]) == 21  # segments + 1
        # Path should span from 0 to length
        assert result["flow_path"][0][0] == pytest.approx(0.0)
        assert result["flow_path"][-1][0] == pytest.approx(30.0)

    def test_lava_flow_sinuous(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=30, seed=42)
        # The flow should deviate in Y (not a straight line)
        y_values = [p[1] for p in result["flow_path"]]
        assert max(y_values) > 0 or min(y_values) < 0  # Not all zero

    def test_lava_heat_zones(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(seed=42)
        assert len(result["heat_zones"]) > 0
        for zone in result["heat_zones"]:
            assert "center" in zone
            assert 0.0 < zone["temperature"] <= 1.0
            assert zone["radius"] > 0

    def test_lava_materials_list(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(seed=42)
        assert "hot_lava" in result["materials"]
        assert "cooling_crust" in result["materials"]
        assert "solid_rock" in result["materials"]
        assert "ember_glow" in result["materials"]

    def test_lava_material_zones_present(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(seed=42)
        mat_set = set(result["material_indices"])
        # Should have multiple material zones
        assert len(mat_set) >= 2

    def test_lava_material_indices_match_faces(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(seed=42)
        assert len(result["material_indices"]) == result["face_count"]

    def test_lava_deterministic(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        r1 = generate_lava_flow(seed=42)
        r2 = generate_lava_flow(seed=42)
        assert r1["vertex_count"] == r2["vertex_count"]
        assert r1["face_count"] == r2["face_count"]
        assert r1["mesh"]["vertices"] == r2["mesh"]["vertices"]

    def test_lava_mesh_valid_indices(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(seed=42)
        num_verts = len(result["mesh"]["vertices"])
        for face in result["mesh"]["faces"]:
            for vi in face:
                assert 0 <= vi < num_verts

    def test_lava_poly_budget(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=50, width=6, flow_segments=30, seed=42)
        assert result["vertex_count"] < 5000
        assert result["face_count"] < 5000

    def test_lava_short_flow(self):
        from blender_addon.handlers.terrain_features import generate_lava_flow

        result = generate_lava_flow(length=5, flow_segments=5, seed=42)
        assert result["vertex_count"] > 0
        assert result["face_count"] > 0
