"""Tests for terrain depth generators.

Validates that the 5 terrain depth generators produce valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Correct dimensions and metadata
- Seed determinism
- Category = terrain_depth for all generators
- Cliff edge detection finds steep regions
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from blender_addon.handlers._terrain_depth import (
    generate_cliff_face_mesh,
    generate_cave_entrance_mesh,
    generate_biome_transition_mesh,
    generate_waterfall_mesh,
    generate_terrain_bridge_mesh,
    detect_cliff_edges,
)


# ---------------------------------------------------------------------------
# Helper validation
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a mesh spec dict has all required fields and valid data."""
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "uvs" in result, f"{name}: missing 'uvs'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    assert len(verts) >= min_verts, (
        f"{name}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{name}: expected >= {min_faces} faces, got {len(faces)}"
    )

    # All vertices are 3-tuples of numbers
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    # All face indices reference valid vertices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Metadata required keys
    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{name}: metadata missing 'dimensions'"


# ---------------------------------------------------------------------------
# Cliff face tests
# ---------------------------------------------------------------------------


class TestCliffFaceMesh:
    """Tests for generate_cliff_face_mesh."""

    def test_returns_valid_meshspec(self):
        result = generate_cliff_face_mesh()
        validate_mesh_spec(result, "cliff_face")

    def test_vertices_span_requested_width(self):
        result = generate_cliff_face_mesh(width=20.0)
        xs = [v[0] for v in result["vertices"]]
        x_span = max(xs) - min(xs)
        assert x_span >= 18.0, f"X span {x_span} too small for width=20"
        assert x_span <= 22.0, f"X span {x_span} too large for width=20"

    def test_vertices_span_requested_height(self):
        result = generate_cliff_face_mesh(height=15.0)
        ys = [v[1] for v in result["vertices"]]
        y_span = max(ys) - min(ys)
        assert y_span >= 14.0, f"Y span {y_span} too small for height=15"

    def test_vertical_geometry_y_span_over_10m(self):
        """Cliff face must be vertical, not flat -- y-span > 10m."""
        result = generate_cliff_face_mesh()
        ys = [v[1] for v in result["vertices"]]
        y_span = max(ys) - min(ys)
        assert y_span > 10.0, f"Cliff face y-span {y_span} <= 10m, not vertical"

    def test_different_seeds_different_vertices(self):
        r1 = generate_cliff_face_mesh(seed=42)
        r2 = generate_cliff_face_mesh(seed=99)
        # At least some vertices should differ
        diffs = sum(
            1 for a, b in zip(r1["vertices"], r2["vertices"])
            if abs(a[2] - b[2]) > 1e-6
        )
        assert diffs > 0, "Different seeds produced identical geometry"

    def test_metadata_category_terrain_depth(self):
        result = generate_cliff_face_mesh()
        assert result["metadata"].get("category") == "terrain_depth"

    def test_custom_dimensions(self):
        result = generate_cliff_face_mesh(width=30.0, height=25.0)
        xs = [v[0] for v in result["vertices"]]
        ys = [v[1] for v in result["vertices"]]
        assert max(xs) - min(xs) >= 28.0
        assert max(ys) - min(ys) >= 24.0

    def test_style_parameter(self):
        """Style parameter should be stored in metadata."""
        result = generate_cliff_face_mesh(style="sandstone")
        assert result["metadata"].get("style") == "sandstone"


# ---------------------------------------------------------------------------
# Cave entrance tests
# ---------------------------------------------------------------------------


class TestCaveEntranceMesh:
    """Tests for generate_cave_entrance_mesh."""

    def test_returns_valid_meshspec(self):
        result = generate_cave_entrance_mesh()
        validate_mesh_spec(result, "cave_entrance")

    def test_default_dimensions_opening(self):
        """Default opening should be at least 3m wide and 3m tall."""
        result = generate_cave_entrance_mesh(width=4.0, height=4.0)
        dims = result["metadata"]["dimensions"]
        assert dims["width"] >= 3.0, f"Width {dims['width']} < 3m"
        assert dims["height"] >= 3.0, f"Height {dims['height']} < 3m"

    def test_accepts_terrain_edge_height(self):
        """terrain_edge_height should shift the bottom edge."""
        r1 = generate_cave_entrance_mesh(terrain_edge_height=0.0)
        r2 = generate_cave_entrance_mesh(terrain_edge_height=5.0)
        ys_1 = [v[1] for v in r1["vertices"]]
        ys_2 = [v[1] for v in r2["vertices"]]
        assert min(ys_2) > min(ys_1), "terrain_edge_height=5 should raise bottom"

    def test_metadata_category_terrain_depth(self):
        result = generate_cave_entrance_mesh()
        assert result["metadata"].get("category") == "terrain_depth"

    def test_depth_parameter(self):
        """Depth should affect z-extent of the tunnel."""
        result = generate_cave_entrance_mesh(depth=5.0)
        zs = [v[2] for v in result["vertices"]]
        z_span = max(zs) - min(zs)
        assert z_span >= 4.0, f"Z span {z_span} too small for depth=5"

    def test_different_seeds(self):
        r1 = generate_cave_entrance_mesh(seed=10)
        r2 = generate_cave_entrance_mesh(seed=20)
        v1_flat = [c for v in r1["vertices"] for c in v]
        v2_flat = [c for v in r2["vertices"] for c in v]
        diffs = sum(1 for a, b in zip(v1_flat, v2_flat) if abs(a - b) > 1e-6)
        assert diffs > 0, "Different seeds produced identical geometry"


# ---------------------------------------------------------------------------
# Biome transition tests
# ---------------------------------------------------------------------------


class TestBiomeTransitionMesh:
    """Tests for generate_biome_transition_mesh."""

    def test_returns_valid_meshspec(self):
        result = generate_biome_transition_mesh()
        validate_mesh_spec(result, "biome_transition")

    def test_accepts_biome_parameters(self):
        result = generate_biome_transition_mesh(biome_a="desert", biome_b="tundra")
        meta = result["metadata"]
        assert meta.get("biome_a") == "desert"
        assert meta.get("biome_b") == "tundra"

    def test_width_matches_zone_width(self):
        result = generate_biome_transition_mesh(zone_width=10.0)
        xs = [v[0] for v in result["vertices"]]
        x_span = max(xs) - min(xs)
        assert x_span >= 9.0, f"X span {x_span} too small for zone_width=10"
        assert x_span <= 11.0, f"X span {x_span} too large for zone_width=10"

    def test_metadata_contains_biome_names(self):
        result = generate_biome_transition_mesh(biome_a="forest", biome_b="swamp")
        meta = result["metadata"]
        assert "biome_a" in meta
        assert "biome_b" in meta
        assert meta["biome_a"] == "forest"
        assert meta["biome_b"] == "swamp"

    def test_metadata_category_terrain_depth(self):
        result = generate_biome_transition_mesh()
        assert result["metadata"].get("category") == "terrain_depth"

    def test_vertex_groups_blend_weights(self):
        """Metadata should include vertex_groups for biome blending."""
        result = generate_biome_transition_mesh()
        meta = result["metadata"]
        assert "vertex_groups" in meta, "Missing vertex_groups for blend weights"
        vg = meta["vertex_groups"]
        # Weights should span 0..1
        assert min(vg) >= 0.0 - 1e-6
        assert max(vg) <= 1.0 + 1e-6

    def test_depth_matches_zone_depth(self):
        result = generate_biome_transition_mesh(zone_depth=20.0)
        zs = [v[2] for v in result["vertices"]]
        z_span = max(zs) - min(zs)
        assert z_span >= 18.0, f"Z span {z_span} too small for zone_depth=20"


# ---------------------------------------------------------------------------
# Waterfall tests
# ---------------------------------------------------------------------------


class TestWaterfallMesh:
    """Tests for generate_waterfall_mesh."""

    def test_returns_valid_meshspec(self):
        result = generate_waterfall_mesh()
        validate_mesh_spec(result, "waterfall")

    def test_total_height_matches_requested(self):
        result = generate_waterfall_mesh(height=10.0)
        ys = [v[1] for v in result["vertices"]]
        y_span = max(ys) - min(ys)
        # Should roughly cover the requested height
        assert y_span >= 9.0, f"Y span {y_span} too small for height=10"

    def test_at_least_3_cascade_steps(self):
        """Default steps=4, so cascade_steps in metadata should be >= 3."""
        result = generate_waterfall_mesh(steps=4)
        meta = result["metadata"]
        assert meta.get("cascade_steps", 0) >= 3, "Not enough cascade steps"

    def test_metadata_category_terrain_depth(self):
        result = generate_waterfall_mesh()
        assert result["metadata"].get("category") == "terrain_depth"

    def test_pool_at_base(self):
        """Pool should exist at the bottom -- check for pool_radius in metadata."""
        result = generate_waterfall_mesh(pool_radius=2.0)
        meta = result["metadata"]
        assert meta.get("has_pool", False), "Waterfall should have a pool at base"

    def test_different_seeds(self):
        r1 = generate_waterfall_mesh(seed=1)
        r2 = generate_waterfall_mesh(seed=2)
        v1_flat = [c for v in r1["vertices"] for c in v]
        v2_flat = [c for v in r2["vertices"] for c in v]
        diffs = sum(1 for a, b in zip(v1_flat, v2_flat) if abs(a - b) > 1e-6)
        assert diffs > 0, "Different seeds produced identical geometry"

    def test_custom_step_count(self):
        result = generate_waterfall_mesh(steps=6)
        assert result["metadata"].get("cascade_steps") == 6


# ---------------------------------------------------------------------------
# Terrain bridge tests
# ---------------------------------------------------------------------------


class TestTerrainBridgeMesh:
    """Tests for generate_terrain_bridge_mesh."""

    def test_returns_valid_meshspec(self):
        result = generate_terrain_bridge_mesh()
        validate_mesh_spec(result, "terrain_bridge")

    def test_accepts_start_end_positions(self):
        result = generate_terrain_bridge_mesh(
            start_pos=(0, 0, 0), end_pos=(20, 0, 0)
        )
        validate_mesh_spec(result, "terrain_bridge_custom_pos")

    def test_span_approximates_endpoint_distance(self):
        start = (0, 0, 0)
        end = (10, 0, 0)
        result = generate_terrain_bridge_mesh(start_pos=start, end_pos=end)
        xs = [v[0] for v in result["vertices"]]
        zs = [v[2] for v in result["vertices"]]
        # The bridge should span roughly the distance between endpoints
        x_span = max(xs) - min(xs)
        # For a 10-unit span along x, the bridge length should be close
        assert x_span >= 8.0, f"Bridge x-span {x_span} too short for 10-unit distance"

    def test_supports_stone_arch_style(self):
        result = generate_terrain_bridge_mesh(style="stone_arch")
        validate_mesh_spec(result, "bridge_stone_arch")

    def test_supports_rope_style(self):
        result = generate_terrain_bridge_mesh(style="rope")
        validate_mesh_spec(result, "bridge_rope")

    def test_supports_drawbridge_style(self):
        result = generate_terrain_bridge_mesh(style="drawbridge")
        validate_mesh_spec(result, "bridge_drawbridge")

    def test_metadata_category_terrain_depth(self):
        result = generate_terrain_bridge_mesh()
        assert result["metadata"].get("category") == "terrain_depth"

    def test_rotated_bridge(self):
        """Bridge between non-axis-aligned points should still be valid."""
        result = generate_terrain_bridge_mesh(
            start_pos=(0, 0, 0), end_pos=(5, 0, 5)
        )
        validate_mesh_spec(result, "bridge_rotated")

    def test_elevated_endpoints(self):
        """Bridge with elevated endpoints should still produce valid geometry."""
        result = generate_terrain_bridge_mesh(
            start_pos=(0, 5, 0), end_pos=(10, 5, 0)
        )
        validate_mesh_spec(result, "bridge_elevated")
        ys = [v[1] for v in result["vertices"]]
        # Deck surface should be near y=5, arch ribs may dip below
        # but the mean should be close to the elevation
        mean_y = sum(ys) / len(ys)
        assert mean_y >= 3.0, f"Mean Y {mean_y} too low for y=5 elevation"
        assert max(ys) >= 4.5, "Max Y should be near bridge elevation"


# ---------------------------------------------------------------------------
# Cross-generator tests
# ---------------------------------------------------------------------------


class TestAllGenerators:
    """Tests that apply to all 5 generators."""

    @pytest.mark.parametrize("gen_fn,kwargs", [
        (generate_cliff_face_mesh, {}),
        (generate_cave_entrance_mesh, {}),
        (generate_biome_transition_mesh, {}),
        (generate_waterfall_mesh, {}),
        (generate_terrain_bridge_mesh, {}),
    ])
    def test_face_indices_valid(self, gen_fn, kwargs):
        result = gen_fn(**kwargs)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"{gen_fn.__name__}: face {fi} index {idx} >= {n_verts}"
                )

    @pytest.mark.parametrize("gen_fn,kwargs", [
        (generate_cliff_face_mesh, {}),
        (generate_cave_entrance_mesh, {}),
        (generate_biome_transition_mesh, {}),
        (generate_waterfall_mesh, {}),
        (generate_terrain_bridge_mesh, {}),
    ])
    def test_category_terrain_depth(self, gen_fn, kwargs):
        result = gen_fn(**kwargs)
        assert result["metadata"].get("category") == "terrain_depth"


# ---------------------------------------------------------------------------
# Cliff edge detection tests
# ---------------------------------------------------------------------------


class TestDetectCliffEdges:
    """Tests for detect_cliff_edges pure-logic function."""

    def test_detect_cliff_edges_steep_area(self):
        """Heightmap with a known steep column should produce at least 1 cliff."""
        # Create a heightmap with a dramatic cliff edge.
        # np.gradient uses central differences so we need a large height
        # change per cell to exceed the slope threshold in degrees.
        hmap = np.full((32, 32), 1.0, dtype=np.float64)
        # Steep drop: 1.0 -> 0.0 in a single cell column
        hmap[:, 16:] = 0.0

        # Use a low threshold since normalized heightmaps produce modest
        # slopes once converted into world-space spacing for a 100 m terrain.
        placements = detect_cliff_edges(
            hmap, slope_threshold_deg=5.0, min_cluster_size=2, terrain_size=100.0
        )
        assert len(placements) >= 1, "No cliff edges detected on steep heightmap"

    def test_detect_cliff_edges_returns_placement_keys(self):
        """Each placement dict should have position, rotation, width, height."""
        hmap = np.full((32, 32), 1.0, dtype=np.float64)
        hmap[:, 16:] = 0.0

        placements = detect_cliff_edges(
            hmap, slope_threshold_deg=5.0, min_cluster_size=2, terrain_size=100.0
        )
        assert len(placements) >= 1
        p = placements[0]
        assert "position" in p, "Missing 'position' key"
        assert "rotation" in p, "Missing 'rotation' key"
        assert "width" in p, "Missing 'width' key"
        assert "height" in p, "Missing 'height' key"
        assert "cell_count" in p, "Missing 'cell_count' key"
        assert len(p["position"]) == 3
        assert len(p["rotation"]) == 3

    def test_detect_cliff_edges_flat_returns_empty(self):
        """Completely flat heightmap should produce no cliff placements."""
        hmap = np.full((32, 32), 0.5, dtype=np.float64)
        placements = detect_cliff_edges(
            hmap, slope_threshold_deg=60.0, min_cluster_size=4, terrain_size=100.0
        )
        assert len(placements) == 0, f"Flat terrain produced {len(placements)} cliffs"

    def test_detect_cliff_edges_min_cluster_filter(self):
        """Small clusters below min_cluster_size should be filtered out."""
        hmap = np.full((32, 32), 0.5, dtype=np.float64)
        # Create a tiny 1-pixel cliff (below min_cluster_size=4)
        hmap[15, 15] = 0.0

        placements = detect_cliff_edges(
            hmap, slope_threshold_deg=20.0, min_cluster_size=4, terrain_size=100.0
        )
        # The single steep cell should not form a qualifying cluster
        assert len(placements) == 0, "Single-cell cliff should be filtered"

    def test_detect_cliff_edges_positive_dimensions(self):
        """Cliff width and height should be positive values."""
        hmap = np.full((32, 32), 1.0, dtype=np.float64)
        hmap[:, 16:] = 0.0

        placements = detect_cliff_edges(
            hmap, slope_threshold_deg=5.0, min_cluster_size=2, terrain_size=100.0
        )
        for p in placements:
            assert p["width"] > 0, f"Cliff width {p['width']} <= 0"
            assert p["height"] > 0, f"Cliff height {p['height']} <= 0"

    def test_detect_cliff_edges_accepts_rectangular_terrain_extent(self):
        """Rectangular terrain extents should use independent width and height."""
        hmap = np.full((32, 32), 1.0, dtype=np.float64)
        hmap[:, 16:] = 0.0

        placements = detect_cliff_edges(
            hmap,
            slope_threshold_deg=5.0,
            min_cluster_size=2,
            terrain_size=(160.0, 80.0),
        )

        assert len(placements) >= 1
        for p in placements:
            assert -80.0 <= p["position"][0] <= 80.0
            assert -40.0 <= p["position"][1] <= 40.0
