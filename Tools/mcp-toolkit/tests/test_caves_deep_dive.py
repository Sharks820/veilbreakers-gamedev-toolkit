"""Sub-phase 6E — tests for cave deep-dive features.

Tests Perlin worm paths, marching cubes mesh, stalactites, water pools,
lighting zones, portals, entrance asymmetry, and the unified analyze_deep_cave.

All tests are pure-numpy (no bpy) and deterministic via seed control.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Registry isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pass_registry():
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    TerrainPassController.clear_registry()
    yield
    TerrainPassController.clear_registry()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_state(
    *,
    tile_size: int = 48,
    seed: int = 1234,
    mode: str = "mixed",
    cave_candidates=(),
):
    from blender_addon.handlers.terrain_masks import compute_base_masks
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    N = tile_size + 1
    if mode == "flat_mid":
        height = np.full((N, N), 50.0, dtype=np.float64)
    elif mode == "mixed":
        xs = np.linspace(0.0, 1.0, N)
        ys = np.linspace(0.0, 1.0, N)
        xg, yg = np.meshgrid(xs, ys)
        height = 20.0 + 30.0 * np.sin(xg * 6.0) + 15.0 * np.cos(yg * 4.0)
    else:
        height = np.full((N, N), 30.0, dtype=np.float64)

    rng = np.random.default_rng(seed)
    height = height + rng.normal(0.0, 0.02, size=height.shape)

    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    compute_base_masks(
        height,
        cell_size=1.0,
        tile_coords=(0, 0),
        stack=stack,
        pass_name="structural_masks",
    )

    region_bounds = BBox(0.0, 0.0, float(N), float(N))

    scene_read = TerrainSceneRead(
        timestamp=time.time(),
        major_landforms=("plateau",),
        focal_point=(N * 0.5, N * 0.5, float(height.mean())),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=tuple(cave_candidates),
        protected_zones_in_region=(),
        edit_scope=region_bounds,
        success_criteria=("caves_placed",),
        reviewer="test",
    )

    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region_bounds,
        tile_size=tile_size,
        cell_size=1.0,
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _make_cave_structure(archetype_str="lava_tube", seed=42):
    """Build a minimal CaveStructure for testing deep-dive functions."""
    from blender_addon.handlers.terrain_caves import (
        CaveArchetype,
        CaveStructure,
        make_archetype_spec,
    )

    arch = CaveArchetype(archetype_str)
    spec = make_archetype_spec(arch)
    return CaveStructure(
        cave_id=f"test_cave_{archetype_str}",
        archetype=arch,
        spec=spec,
        entrance_world_pos=(20.0, 20.0, 30.0),
        path_world=[(20.0, 20.0, 30.0), (25.0, 22.0, 28.0), (30.0, 24.0, 26.0)],
        tier="hero",
    )


# ===========================================================================
# Perlin worm path tests
# ===========================================================================


class TestPerlinWormPath:
    """Tests for generate_perlin_worm_path."""

    def test_returns_nonempty_path(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        path = generate_perlin_worm_path((10.0, 10.0, 50.0), seed=1)
        assert len(path) >= 10

    def test_starts_at_entrance(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        entrance = (15.0, 25.0, 40.0)
        path = generate_perlin_worm_path(entrance, seed=7)
        assert path[0] == pytest.approx(entrance)

    def test_deterministic_same_seed(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        a = generate_perlin_worm_path((10.0, 10.0, 50.0), seed=99)
        b = generate_perlin_worm_path((10.0, 10.0, 50.0), seed=99)
        assert len(a) == len(b)
        for pa, pb in zip(a, b):
            assert pa == pytest.approx(pb)

    def test_different_seeds_differ(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        a = generate_perlin_worm_path((10.0, 10.0, 50.0), seed=1)
        b = generate_perlin_worm_path((10.0, 10.0, 50.0), seed=2)
        # At least some points should differ
        diffs = sum(1 for pa, pb in zip(a, b) if pa != pytest.approx(pb, abs=0.01))
        assert diffs > 0

    def test_path_length_scales_with_parameter(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        short = generate_perlin_worm_path((0, 0, 0), length_m=10.0, seed=5)
        long = generate_perlin_worm_path((0, 0, 0), length_m=80.0, seed=5)
        # Longer path should span more distance
        short_span = np.linalg.norm(
            np.array(short[-1]) - np.array(short[0])
        )
        long_span = np.linalg.norm(
            np.array(long[-1]) - np.array(long[0])
        )
        assert long_span > short_span

    def test_vertical_bias_descends(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        path = generate_perlin_worm_path(
            (10.0, 10.0, 100.0),
            length_m=40.0,
            seed=42,
            vertical_bias=-0.5,
        )
        # End Z should be lower than start Z on average
        assert path[-1][2] < path[0][2]

    def test_segment_count_controls_resolution(self):
        from blender_addon.handlers.terrain_caves import generate_perlin_worm_path

        path10 = generate_perlin_worm_path(
            (0, 0, 0), segment_count=10, seed=1
        )
        path30 = generate_perlin_worm_path(
            (0, 0, 0), segment_count=30, seed=1
        )
        assert len(path10) == 11  # segments + 1
        assert len(path30) == 31


class TestPerlin1D:
    """Tests for the internal _perlin_1d noise function."""

    def test_returns_bounded_value(self):
        from blender_addon.handlers.terrain_caves import _perlin_1d

        for t in [0.0, 0.5, 1.0, 2.5, 10.0]:
            v = _perlin_1d(t, seed=42)
            assert -1.5 <= v <= 1.5  # approximate bound

    def test_deterministic(self):
        from blender_addon.handlers.terrain_caves import _perlin_1d

        a = _perlin_1d(1.23, seed=7)
        b = _perlin_1d(1.23, seed=7)
        assert a == pytest.approx(b)

    def test_varies_with_t(self):
        from blender_addon.handlers.terrain_caves import _perlin_1d

        vals = [_perlin_1d(t * 0.7 + 0.1, seed=42) for t in range(20)]
        # Not all the same — sample at varied t values
        unique = set(round(v, 4) for v in vals)
        assert len(unique) > 1


# ===========================================================================
# Marching cubes mesh tests
# ===========================================================================


class TestMarchingCubesMesh:
    """Tests for marching_cubes_cave_mesh and _build_cave_volume_field."""

    def test_volume_field_negative_inside(self):
        from blender_addon.handlers.terrain_caves import _build_cave_volume_field

        path = [(10, 10, 10), (15, 10, 10), (20, 10, 10)]
        field, origin, voxel = _build_cave_volume_field(
            path, worm_radius_m=3.0, grid_resolution=1.0
        )
        assert field.ndim == 3
        # At the path center the field should be negative
        # Find the voxel closest to (15, 10, 10)
        cx = int(round((15 - origin[0]) / voxel))
        cy = int(round((10 - origin[1]) / voxel))
        cz = int(round((10 - origin[2]) / voxel))
        cx = min(cx, field.shape[2] - 1)
        cy = min(cy, field.shape[1] - 1)
        cz = min(cz, field.shape[0] - 1)
        assert field[cz, cy, cx] < 0.0

    def test_volume_field_positive_far_away(self):
        from blender_addon.handlers.terrain_caves import _build_cave_volume_field

        path = [(10, 10, 10)]
        field, origin, voxel = _build_cave_volume_field(
            path, worm_radius_m=2.0, grid_resolution=1.0, padding_m=8.0
        )
        # Corner of the grid should be positive (far from path)
        assert field[0, 0, 0] > 0.0

    def test_mesh_has_vertices_and_triangles(self):
        from blender_addon.handlers.terrain_caves import marching_cubes_cave_mesh

        path = [(10, 10, 10), (15, 12, 9), (20, 14, 8), (25, 16, 7)]
        mesh = marching_cubes_cave_mesh(
            path, worm_radius_m=3.0, grid_resolution=1.5
        )
        assert mesh.vertex_count > 0
        assert mesh.triangle_count > 0
        assert mesh.vertices.shape == (mesh.vertex_count, 3)
        assert mesh.triangles.shape == (mesh.triangle_count, 3)

    def test_mesh_empty_path_returns_empty(self):
        from blender_addon.handlers.terrain_caves import marching_cubes_cave_mesh

        mesh = marching_cubes_cave_mesh([], worm_radius_m=3.0)
        assert mesh.vertex_count == 0
        assert mesh.triangle_count == 0

    def test_mesh_deterministic(self):
        from blender_addon.handlers.terrain_caves import marching_cubes_cave_mesh

        path = [(0, 0, 0), (5, 3, -1), (10, 6, -2)]
        a = marching_cubes_cave_mesh(path, worm_radius_m=2.5, grid_resolution=1.5)
        b = marching_cubes_cave_mesh(path, worm_radius_m=2.5, grid_resolution=1.5)
        assert a.vertex_count == b.vertex_count
        assert a.triangle_count == b.triangle_count
        np.testing.assert_array_equal(a.vertices, b.vertices)

    def test_mesh_triangle_indices_valid(self):
        from blender_addon.handlers.terrain_caves import marching_cubes_cave_mesh

        path = [(0, 0, 0), (5, 0, 0), (10, 0, 0)]
        mesh = marching_cubes_cave_mesh(path, worm_radius_m=3.0, grid_resolution=2.0)
        if mesh.triangle_count > 0:
            assert mesh.triangles.min() >= 0
            assert mesh.triangles.max() < mesh.vertex_count


# ===========================================================================
# Stalactite placement tests
# ===========================================================================


class TestStalactites:
    """Tests for place_stalactites."""

    def test_returns_formations(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(0, 0, 50), (5, 2, 48), (10, 4, 46), (15, 6, 44), (20, 8, 42)]
        formations = place_stalactites(path, seed=42, worm_radius_m=3.0)
        assert len(formations) > 0

    def test_formations_have_valid_fields(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(0, 0, 50), (10, 5, 45), (20, 10, 40)]
        formations = place_stalactites(path, seed=7)
        for f in formations:
            assert f.direction in ("down", "up")
            assert f.length_m > 0
            assert f.base_radius_m > 0
            assert f.mineral_type in ("calcite", "iron_oxide", "wet_calcite")
            assert isinstance(f.drip_active, bool)

    def test_deterministic_same_seed(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(0, 0, 50), (10, 5, 45), (20, 10, 40)]
        a = place_stalactites(path, seed=123)
        b = place_stalactites(path, seed=123)
        assert len(a) == len(b)
        for fa, fb in zip(a, b):
            assert fa.position == pytest.approx(fb.position)
            assert fa.direction == fb.direction

    def test_density_zero_returns_empty(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(0, 0, 50), (10, 5, 45)]
        formations = place_stalactites(path, seed=1, density=0.0)
        assert len(formations) == 0

    def test_empty_path_returns_empty(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        formations = place_stalactites([], seed=1)
        assert len(formations) == 0

    def test_max_count_respected(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(i * 2, 0, 50 - i) for i in range(50)]
        formations = place_stalactites(
            path, seed=42, density=1.0, max_count=5
        )
        assert len(formations) <= 5

    def test_stalactites_above_centreline(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(i * 3, 0, 50.0) for i in range(10)]
        formations = place_stalactites(path, seed=42, worm_radius_m=3.0)
        stalactites = [f for f in formations if f.direction == "down"]
        for s in stalactites:
            # Stalactite tip should be above centreline Z
            assert s.position[2] > 50.0 - 0.1

    def test_stalagmites_below_centreline(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(i * 3, 0, 50.0) for i in range(10)]
        formations = place_stalactites(path, seed=42, worm_radius_m=3.0)
        stalagmites = [f for f in formations if f.direction == "up"]
        for s in stalagmites:
            # Stalagmite tip should be below centreline Z
            assert s.position[2] < 50.0 + 0.1

    def test_high_damp_increases_wet_calcite(self):
        from blender_addon.handlers.terrain_caves import place_stalactites

        path = [(i * 2, 0, 50 - i * 0.5) for i in range(20)]
        dry = place_stalactites(path, seed=42, damp_intensity=0.0)
        wet = place_stalactites(path, seed=42, damp_intensity=1.0)
        dry_wet_count = sum(1 for f in dry if f.mineral_type == "wet_calcite")
        wet_wet_count = sum(1 for f in wet if f.mineral_type == "wet_calcite")
        # Wet environment should have more wet_calcite
        assert wet_wet_count >= dry_wet_count


# ===========================================================================
# Water pool tests
# ===========================================================================


class TestWaterPools:
    """Tests for detect_cave_water_pools."""

    def test_detects_pool_at_z_minimum(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        # Path with a clear V-shaped dip
        path = [
            (0, 0, 50), (5, 0, 48), (10, 0, 44),
            (15, 0, 48), (20, 0, 50),
        ]
        pools = detect_cave_water_pools(path, seed=42, min_pool_depth_m=0.1)
        assert len(pools) >= 1
        # Pool should be near the dip at (10, 0, 44)
        assert any(abs(p.center[0] - 10.0) < 1.0 for p in pools)

    def test_no_pool_on_flat_path(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        path = [(i * 5, 0, 50.0) for i in range(5)]
        pools = detect_cave_water_pools(path, seed=42)
        assert len(pools) == 0

    def test_no_pool_on_monotone_descent(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        path = [(i * 5, 0, 50.0 - i * 2.0) for i in range(5)]
        pools = detect_cave_water_pools(path, seed=42)
        assert len(pools) == 0

    def test_pool_has_valid_fields(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        path = [(0, 0, 50), (5, 0, 45), (10, 0, 50)]
        pools = detect_cave_water_pools(path, seed=42, min_pool_depth_m=0.1)
        for p in pools:
            assert p.radius_m > 0
            assert p.depth_m > 0
            assert p.surface_z >= p.center[2]
            assert isinstance(p.is_connected, bool)

    def test_pool_deterministic(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        path = [(0, 0, 50), (5, 0, 40), (10, 0, 50)]
        a = detect_cave_water_pools(path, seed=77)
        b = detect_cave_water_pools(path, seed=77)
        assert len(a) == len(b)
        for pa, pb in zip(a, b):
            assert pa.center == pytest.approx(pb.center)

    def test_short_path_returns_empty(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        pools = detect_cave_water_pools([(0, 0, 0), (1, 0, 0)], seed=42)
        assert len(pools) == 0

    def test_multiple_dips_produce_multiple_pools(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        # Two clear dips
        path = [
            (0, 0, 50), (5, 0, 42), (10, 0, 50),
            (15, 0, 43), (20, 0, 50),
        ]
        pools = detect_cave_water_pools(path, seed=42, min_pool_depth_m=0.1)
        assert len(pools) == 2

    def test_flow_direction_set_when_continuing_descent(self):
        from blender_addon.handlers.terrain_caves import detect_cave_water_pools

        # Dip at index 2, then continues descending at index 4
        path = [
            (0, 0, 50), (5, 0, 48), (10, 0, 44),
            (15, 0, 48), (20, 0, 43),
        ]
        pools = detect_cave_water_pools(path, seed=42, min_pool_depth_m=0.1)
        flowing = [p for p in pools if p.flow_direction is not None]
        assert len(flowing) >= 1


# ===========================================================================
# Lighting zone tests
# ===========================================================================


class TestCaveLighting:
    """Tests for compute_cave_lighting_zones."""

    def test_returns_zones_for_each_path_point(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 5, 0, 50 - i) for i in range(10)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        assert len(zones) == len(path)

    def test_entrance_zone_is_brightest(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 5, 0, 50) for i in range(10)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        assert zones[0].light_intensity > zones[-1].light_intensity
        assert zones[0].zone_type == "entrance"

    def test_intensity_decreases_along_path(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 5, 0, 50) for i in range(10)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        intensities = [z.light_intensity for z in zones]
        # Should be monotonically non-increasing
        for i in range(1, len(intensities)):
            assert intensities[i] <= intensities[i - 1] + 1e-6

    def test_deep_zones_have_low_intensity(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 10, 0, 50) for i in range(20)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        deep = zones[-1]
        assert deep.light_intensity < 0.05
        assert deep.zone_type in ("dark", "deep_dark")

    def test_god_rays_only_at_entrance(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 5, 0, 50) for i in range(10)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        god_ray_zones = [z for z in zones if z.has_god_rays]
        for z in god_ray_zones:
            assert z.zone_type == "entrance"

    def test_color_temperature_shifts_warmer_deeper(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        path = [(i * 5, 0, 50) for i in range(10)]
        zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42
        )
        assert zones[0].color_temperature_k > zones[-1].color_temperature_k

    def test_bioluminescence_possible_in_deep_zones(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            compute_cave_lighting_zones,
        )

        # Long path into darkness, sea grotto (higher bio chance)
        path = [(i * 8, 0, 50) for i in range(30)]
        zones = compute_cave_lighting_zones(
            path,
            entrance_pos=path[0],
            seed=42,
            archetype=CaveArchetype.SEA_GROTTO,
        )
        # At least one deep zone should have bioluminescence (probabilistic,
        # but with 30 deep points and 40% chance, very likely with this seed)
        bio_zones = [z for z in zones if z.bioluminescence > 0]
        assert len(bio_zones) >= 1

    def test_empty_path_returns_empty(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        zones = compute_cave_lighting_zones(
            [], entrance_pos=(0, 0, 0), seed=42
        )
        assert len(zones) == 0

    def test_single_point_returns_entrance_zone(self):
        from blender_addon.handlers.terrain_caves import compute_cave_lighting_zones

        zones = compute_cave_lighting_zones(
            [(5, 5, 50)], entrance_pos=(5, 5, 50), seed=42
        )
        assert len(zones) == 1
        assert zones[0].zone_type == "entrance"

    def test_fissure_archetype_has_faster_falloff(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            compute_cave_lighting_zones,
        )

        path = [(i * 5, 0, 50) for i in range(15)]
        fissure_zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42,
            archetype=CaveArchetype.FISSURE,
        )
        grotto_zones = compute_cave_lighting_zones(
            path, entrance_pos=path[0], seed=42,
            archetype=CaveArchetype.SEA_GROTTO,
        )
        # At the same depth, fissure should be darker
        mid = len(path) // 2
        assert fissure_zones[mid].light_intensity < grotto_zones[mid].light_intensity


# ===========================================================================
# Portal placement tests
# ===========================================================================


class TestCavePortals:
    """Tests for place_cave_portals."""

    def test_end_exit_always_present(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        path = [(i * 5, 0, 50 - i) for i in range(10)]
        portals = place_cave_portals(path, "cave_test", seed=42)
        exit_portals = [p for p in portals if p.portal_type == "cave_exit"]
        assert len(exit_portals) >= 1

    def test_karst_gets_vertical_shaft(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            place_cave_portals,
        )

        # Path that descends then goes horizontal
        path = [(0, 0, 50), (0, 0, 40), (0, 0, 30), (5, 0, 30), (10, 0, 30)]
        portals = place_cave_portals(
            path, "karst_test", seed=42,
            archetype=CaveArchetype.KARST_SINKHOLE,
        )
        shaft_portals = [p for p in portals if p.portal_type == "vertical_shaft"]
        assert len(shaft_portals) >= 1
        # Shaft should be at deepest Z point
        deepest_z = min(p[2] for p in path)
        assert any(abs(s.position[2] - deepest_z) < 1.0 for s in shaft_portals)

    def test_portal_ids_contain_cave_id(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        path = [(i * 5, 0, 50) for i in range(6)]
        portals = place_cave_portals(path, "my_cave_42", seed=42)
        for p in portals:
            assert "my_cave_42" in p.portal_id

    def test_short_path_returns_empty(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        portals = place_cave_portals([(0, 0, 0)], "short", seed=42)
        assert len(portals) == 0

    def test_deterministic(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        path = [(i * 5, 0, 50 - i) for i in range(10)]
        a = place_cave_portals(path, "test", seed=99)
        b = place_cave_portals(path, "test", seed=99)
        assert len(a) == len(b)
        for pa, pb in zip(a, b):
            assert pa.portal_id == pb.portal_id
            assert pa.position == pytest.approx(pb.position)

    def test_no_secret_when_disabled(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        path = [(i * 5, 0, 50) for i in range(20)]
        portals = place_cave_portals(
            path, "test", seed=42, allow_secret=False
        )
        secret = [p for p in portals if p.discovery_difficulty == "secret"]
        assert len(secret) == 0

    def test_portal_valid_fields(self):
        from blender_addon.handlers.terrain_caves import place_cave_portals

        path = [(i * 5, 0, 50 - i) for i in range(10)]
        portals = place_cave_portals(path, "test", seed=42)
        for p in portals:
            assert p.width_m > 0
            assert p.height_m > 0
            assert p.portal_type in (
                "cave_exit", "cave_link", "vertical_shaft", "underwater"
            )
            assert p.discovery_difficulty in ("visible", "hidden", "secret")
            assert isinstance(p.is_blocked, bool)


# ===========================================================================
# Asymmetric entrance tests
# ===========================================================================


class TestAsymmetricEntrance:
    """Tests for generate_asymmetric_entrance."""

    def test_returns_valid_entrance(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        spec = make_archetype_spec(CaveArchetype.LAVA_TUBE)
        entrance = generate_asymmetric_entrance((10, 10, 50), spec, seed=42)
        assert entrance.left_height_m > 0
        assert entrance.right_height_m > 0
        assert entrance.width_m > 0
        assert entrance.center == (10, 10, 50)

    def test_left_right_heights_differ(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        spec = make_archetype_spec(CaveArchetype.FISSURE)
        entrance = generate_asymmetric_entrance((0, 0, 0), spec, seed=42)
        # Heights should differ (asymmetry)
        assert entrance.left_height_m != pytest.approx(
            entrance.right_height_m, abs=0.01
        )

    def test_irregularity_points_nonempty(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        spec = make_archetype_spec(CaveArchetype.SEA_GROTTO)
        entrance = generate_asymmetric_entrance((0, 0, 0), spec, seed=7)
        assert len(entrance.irregularity_points) >= 6
        for angle, factor in entrance.irregularity_points:
            assert 0.0 <= angle <= math.pi + 0.01
            assert factor > 0

    def test_overhang_for_grotto(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        spec = make_archetype_spec(CaveArchetype.SEA_GROTTO)
        entrance = generate_asymmetric_entrance((0, 0, 0), spec, seed=42)
        # Sea grotto always gets overhang
        assert entrance.overhang_depth_m > 0

    def test_deterministic(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        spec = make_archetype_spec(CaveArchetype.LAVA_TUBE)
        a = generate_asymmetric_entrance((5, 5, 50), spec, seed=123)
        b = generate_asymmetric_entrance((5, 5, 50), spec, seed=123)
        assert a.left_height_m == pytest.approx(b.left_height_m)
        assert a.overhang_depth_m == pytest.approx(b.overhang_depth_m)
        assert len(a.irregularity_points) == len(b.irregularity_points)

    def test_all_archetypes_produce_valid_entrance(self):
        from blender_addon.handlers.terrain_caves import (
            CaveArchetype,
            generate_asymmetric_entrance,
            make_archetype_spec,
        )

        for arch in CaveArchetype:
            spec = make_archetype_spec(arch)
            entrance = generate_asymmetric_entrance((0, 0, 0), spec, seed=42)
            assert entrance.left_height_m > 0
            assert entrance.right_height_m > 0
            assert entrance.overhang_side in ("left", "right", "center")


# ===========================================================================
# Unified deep-dive analysis tests
# ===========================================================================


class TestAnalyzeDeepCave:
    """Tests for analyze_deep_cave composition function."""

    def test_returns_all_components(self):
        from blender_addon.handlers.terrain_caves import analyze_deep_cave

        state = _build_state(cave_candidates=((20.0, 20.0, 30.0),))
        cave = _make_cave_structure("lava_tube")
        result = analyze_deep_cave(cave, state.mask_stack, seed=42)

        assert result.cave_id == cave.cave_id
        assert len(result.worm_path) > 0
        assert result.mesh is not None
        assert result.mesh.vertex_count > 0
        assert len(result.stalactites) >= 0
        assert isinstance(result.water_pools, list)
        assert len(result.lighting_zones) > 0
        assert len(result.portals) > 0
        assert result.asymmetric_entrance is not None

    def test_without_mesh_generation(self):
        from blender_addon.handlers.terrain_caves import analyze_deep_cave

        state = _build_state()
        cave = _make_cave_structure("fissure")
        result = analyze_deep_cave(
            cave, state.mask_stack, seed=42, generate_mesh=False
        )
        assert result.mesh is None
        # Other components still present
        assert len(result.worm_path) > 0
        assert result.asymmetric_entrance is not None

    def test_all_archetypes_produce_analysis(self):
        from blender_addon.handlers.terrain_caves import CaveArchetype, analyze_deep_cave

        state = _build_state()
        for arch in CaveArchetype:
            cave = _make_cave_structure(arch.value)
            result = analyze_deep_cave(
                cave, state.mask_stack, seed=42, generate_mesh=False
            )
            assert result.cave_id.endswith(arch.value)
            assert len(result.worm_path) > 0
            assert len(result.lighting_zones) > 0

    def test_deterministic(self):
        from blender_addon.handlers.terrain_caves import analyze_deep_cave

        state = _build_state()
        cave = _make_cave_structure("glacial_melt")
        a = analyze_deep_cave(cave, state.mask_stack, seed=77, generate_mesh=False)
        b = analyze_deep_cave(cave, state.mask_stack, seed=77, generate_mesh=False)
        assert len(a.worm_path) == len(b.worm_path)
        assert len(a.stalactites) == len(b.stalactites)
        assert len(a.portals) == len(b.portals)

    def test_mesh_resolution_affects_detail(self):
        from blender_addon.handlers.terrain_caves import analyze_deep_cave

        state = _build_state()
        cave = _make_cave_structure("lava_tube")
        coarse = analyze_deep_cave(
            cave, state.mask_stack, seed=42, mesh_resolution=3.0
        )
        fine = analyze_deep_cave(
            cave, state.mask_stack, seed=42, mesh_resolution=1.0
        )
        # Fine resolution should produce more vertices
        if coarse.mesh and fine.mesh:
            assert fine.mesh.vertex_count >= coarse.mesh.vertex_count
