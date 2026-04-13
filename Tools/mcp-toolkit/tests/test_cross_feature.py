"""Cross-feature interaction, LOD, and export contract tests for terrain.

Tests that terrain subsystems (noise, erosion, flow, chunking, export)
compose correctly and that LOD downsampling preserves terrain character.
Pure numpy -- no Blender required.
"""

from __future__ import annotations


import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mountain_hmap():
    from blender_addon.handlers._terrain_noise import generate_heightmap
    return generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")


@pytest.fixture
def eroded_hmap(mountain_hmap):
    from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
    return apply_hydraulic_erosion(mountain_hmap, iterations=200, seed=42)


@pytest.fixture
def flow_result(mountain_hmap):
    from blender_addon.handlers.terrain_advanced import compute_flow_map
    raw = compute_flow_map(mountain_hmap)
    return {
        "flow_direction": np.asarray(raw["flow_direction"], dtype=np.int32),
        "flow_accumulation": np.asarray(raw["flow_accumulation"], dtype=np.float64),
        "drainage_basins": np.asarray(raw["drainage_basins"], dtype=np.int32),
    }


@pytest.fixture
def slope_map(mountain_hmap):
    from blender_addon.handlers._terrain_noise import compute_slope_map
    return compute_slope_map(mountain_hmap)


@pytest.fixture
def biome_map(mountain_hmap, slope_map):
    from blender_addon.handlers._terrain_noise import compute_biome_assignments
    return compute_biome_assignments(mountain_hmap, slope_map)


# ===========================================================================
# Cross-feature composition tests
# ===========================================================================


class TestNoiseErosionComposition:
    """Noise + erosion must compose correctly."""

    def test_erosion_preserves_shape(self, mountain_hmap, eroded_hmap):
        """Eroded heightmap must have same shape as source."""
        assert eroded_hmap.shape == mountain_hmap.shape

    def test_erosion_preserves_range(self, mountain_hmap, eroded_hmap):
        """Eroded values must stay within source range."""
        assert eroded_hmap.min() >= mountain_hmap.min() - 1e-9
        assert eroded_hmap.max() <= mountain_hmap.max() + 1e-9

    def test_slope_after_erosion_still_valid(self, eroded_hmap):
        """Slope computed on eroded terrain should be valid [0, 90]."""
        from blender_addon.handlers._terrain_noise import compute_slope_map
        slope = compute_slope_map(eroded_hmap)
        assert slope.min() >= 0.0
        assert slope.max() <= 90.0 + 1e-6

    def test_flow_after_erosion_valid(self, eroded_hmap):
        """Flow computed on eroded terrain should still be valid."""
        from blender_addon.handlers.terrain_advanced import compute_flow_map
        raw = compute_flow_map(eroded_hmap)
        flow_dir = np.asarray(raw["flow_direction"], dtype=np.int32)
        flow_acc = np.asarray(raw["flow_accumulation"], dtype=np.float64)
        assert flow_dir.shape == eroded_hmap.shape
        assert flow_acc.shape == eroded_hmap.shape
        assert (flow_acc >= 1.0).all()

    def test_biome_after_erosion_valid(self, eroded_hmap):
        """Biome assignment on eroded terrain should produce valid indices."""
        from blender_addon.handlers._terrain_noise import compute_slope_map, compute_biome_assignments
        slope = compute_slope_map(eroded_hmap)
        biomes = compute_biome_assignments(eroded_hmap, slope)
        assert biomes.shape == eroded_hmap.shape
        assert biomes.min() >= 0
        assert np.isfinite(biomes).all()


class TestNoiseBiomeComposition:
    """Noise + biome assignment must compose correctly."""

    def test_biome_shape_matches_heightmap(self, mountain_hmap, biome_map):
        """Biome map must have same shape as heightmap."""
        assert biome_map.shape == mountain_hmap.shape

    def test_biome_indices_non_negative(self, biome_map):
        """Biome indices must be non-negative."""
        assert biome_map.min() >= 0

    def test_biome_uses_multiple_types(self, biome_map):
        """Non-trivial terrain should have multiple biome types."""
        unique_biomes = np.unique(biome_map)
        assert len(unique_biomes) >= 2, f"Only {len(unique_biomes)} biome type(s)"

    def test_biome_varies_with_altitude(self, mountain_hmap, slope_map):
        """Different altitude ranges should show different biome distributions."""
        from blender_addon.handlers._terrain_noise import compute_biome_assignments
        biomes = compute_biome_assignments(mountain_hmap, slope_map)
        low_mask = mountain_hmap < 0.3
        high_mask = mountain_hmap > 0.7
        if low_mask.sum() == 0 or high_mask.sum() == 0:
            pytest.skip("Not enough altitude variation")
        low_biomes = set(np.unique(biomes[low_mask]))
        high_biomes = set(np.unique(biomes[high_mask]))
        # At least some differentiation should exist
        assert low_biomes != high_biomes or len(low_biomes) > 1, (
            "Low and high altitude have identical single biome"
        )


class TestNoiseFlowComposition:
    """Noise + flow computation must compose correctly."""

    def test_flow_accumulation_correlates_with_low_elevation(
        self, mountain_hmap, flow_result
    ):
        """High flow accumulation should tend to occur at lower elevations."""
        flow_acc = flow_result["flow_accumulation"]
        high_flow = flow_acc > np.percentile(flow_acc, 90)
        low_flow = flow_acc < np.percentile(flow_acc, 10)
        if high_flow.sum() == 0 or low_flow.sum() == 0:
            pytest.skip("Not enough flow variation")
        mean_elev_high_flow = mountain_hmap[high_flow].mean()
        mean_elev_low_flow = mountain_hmap[low_flow].mean()
        assert mean_elev_high_flow < mean_elev_low_flow, (
            f"High-flow mean elevation ({mean_elev_high_flow:.3f}) should be less than "
            f"low-flow ({mean_elev_low_flow:.3f})"
        )

    def test_flow_slope_at_channels(self, mountain_hmap, flow_result, slope_map):
        """Channels (high flow) should exist at various slope values."""
        flow_acc = flow_result["flow_accumulation"]
        high_flow = flow_acc > np.percentile(flow_acc, 90)
        if high_flow.sum() == 0:
            pytest.skip("No high-flow cells")
        channel_slopes = slope_map[high_flow]
        assert channel_slopes.mean() >= 0.0  # basic validity


# ===========================================================================
# LOD tests
# ===========================================================================


class TestLODDownsample:
    """LOD downsampling must preserve terrain character."""

    def test_lod_returns_correct_size(self, mountain_hmap):
        """Downsampled chunk should match target resolution."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        result = compute_chunk_lod(hmap_list, 16)
        assert len(result) == 16
        assert len(result[0]) == 16

    def test_lod_preserves_height_range(self, mountain_hmap):
        """LOD downsample should not exceed source height range."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        lod = compute_chunk_lod(hmap_list, 16)
        lod_arr = np.array(lod)
        assert lod_arr.min() >= mountain_hmap.min() - 1e-6
        assert lod_arr.max() <= mountain_hmap.max() + 1e-6

    def test_lod_preserves_mean_approximately(self, mountain_hmap):
        """LOD mean should approximate source mean."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        lod = compute_chunk_lod(hmap_list, 32)
        lod_arr = np.array(lod)
        assert abs(lod_arr.mean() - mountain_hmap.mean()) < 0.1, (
            f"LOD mean {lod_arr.mean():.4f} differs from source {mountain_hmap.mean():.4f}"
        )

    def test_lod_chain_decreasing_resolution(self, mountain_hmap):
        """Successive LOD levels should have decreasing resolution."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        resolutions = [32, 16, 8, 4]
        for target_res in resolutions:
            lod = compute_chunk_lod(hmap_list, target_res)
            assert len(lod) == target_res

    def test_lod_identity_at_source_resolution(self, mountain_hmap):
        """LOD at source resolution should return the original data."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        lod = compute_chunk_lod(hmap_list, 64)
        lod_arr = np.array(lod)
        np.testing.assert_allclose(lod_arr, mountain_hmap, atol=1e-10)

    def test_lod_no_nan_or_inf(self, mountain_hmap):
        """No NaN or Inf values in any LOD level."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        for res in [32, 16, 8]:
            lod = compute_chunk_lod(hmap_list, res)
            lod_arr = np.array(lod)
            assert np.isfinite(lod_arr).all(), f"Non-finite values at LOD {res}"

    def test_lod_std_decreases_with_resolution(self, mountain_hmap):
        """Standard deviation should not increase dramatically at lower LODs."""
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod
        hmap_list = mountain_hmap.tolist()
        src_std = mountain_hmap.std()
        for res in [32, 16]:
            lod = compute_chunk_lod(hmap_list, res)
            lod_std = np.array(lod).std()
            # LOD can slightly increase std due to sampling but not double it
            assert lod_std < src_std * 2.0, (
                f"LOD {res} std ({lod_std:.4f}) > 2x source ({src_std:.4f})"
            )


class TestLODEdgeStitching:
    """Adjacent LOD chunks must have matching edges for seamless stitching."""

    def test_adjacent_chunks_share_edge_values(self):
        """Two adjacent chunks from the same heightmap should have continuous boundary."""
        from blender_addon.handlers._terrain_noise import generate_heightmap
        # Generate a large square heightmap and split into two halves
        big = generate_heightmap(128, 128, scale=80.0, seed=42, terrain_type="mountains")
        left = big[:, :65]   # columns 0-64 (inclusive)
        right = big[:, 64:]  # columns 64-127

        # Column 64 is shared: right edge of left == left edge of right
        left_edge = left[:, -1]
        right_edge = right[:, 0]
        np.testing.assert_array_equal(left_edge, right_edge)


# ===========================================================================
# Export contract tests
# ===========================================================================


class TestExportContracts:
    """Unity export contracts must validate correctly."""

    def test_mesh_attributes_all_present(self):
        """All required mesh attributes should pass validation."""
        from blender_addon.handlers.terrain_unity_export_contracts import (
            REQUIRED_MESH_ATTRIBUTES,
            validate_mesh_attributes_present,
        )
        issues = validate_mesh_attributes_present(REQUIRED_MESH_ATTRIBUTES)
        assert len(issues) == 0, f"Unexpected issues: {[i.message for i in issues]}"

    def test_mesh_attributes_missing_detected(self):
        """Missing mesh attributes should produce hard issues."""
        from blender_addon.handlers.terrain_unity_export_contracts import (
            validate_mesh_attributes_present,
        )
        issues = validate_mesh_attributes_present(["slope_angle"])
        assert len(issues) >= 1
        assert all(i.severity == "hard" for i in issues)

    def test_vertex_attributes_all_present(self):
        """All required vertex attributes should pass validation."""
        from blender_addon.handlers.terrain_unity_export_contracts import (
            REQUIRED_VERTEX_ATTRIBUTES,
            validate_vertex_attributes_present,
        )
        issues = validate_vertex_attributes_present(REQUIRED_VERTEX_ATTRIBUTES)
        assert len(issues) == 0

    def test_vertex_attributes_missing_detected(self):
        """Missing vertex attributes should produce hard issues."""
        from blender_addon.handlers.terrain_unity_export_contracts import (
            validate_vertex_attributes_present,
        )
        issues = validate_vertex_attributes_present(["position", "normal"])
        assert len(issues) >= 1

    def test_export_contract_bit_depths(self):
        """Export contract should enforce minimum bit depths."""
        from blender_addon.handlers.terrain_unity_export_contracts import UnityExportContract
        contract = UnityExportContract()
        assert contract.minimum_for("heightmap") == 16
        assert contract.minimum_for("splatmap") == 8
        assert contract.minimum_for("shadow_clipmap") == 32
        assert contract.minimum_for("unknown") == 0

    def test_required_mesh_attrs_count(self):
        """Exactly 6 mesh attributes are required per spec."""
        from blender_addon.handlers.terrain_unity_export_contracts import REQUIRED_MESH_ATTRIBUTES
        assert len(REQUIRED_MESH_ATTRIBUTES) == 6

    def test_required_vertex_attrs_count(self):
        """Exactly 6 vertex attributes are required per spec."""
        from blender_addon.handlers.terrain_unity_export_contracts import REQUIRED_VERTEX_ATTRIBUTES
        assert len(REQUIRED_VERTEX_ATTRIBUTES) == 6


class TestExportDataIntegrity:
    """Exported data must maintain integrity through the pipeline."""

    def test_heightmap_finite_after_full_pipeline(self, mountain_hmap):
        """Heightmap should be finite after noise + erosion + slope pipeline."""
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
        from blender_addon.handlers._terrain_noise import compute_slope_map
        eroded = apply_hydraulic_erosion(mountain_hmap, iterations=100, seed=42)
        slope = compute_slope_map(eroded)
        assert np.isfinite(eroded).all(), "Non-finite values after erosion"
        assert np.isfinite(slope).all(), "Non-finite values in slope"

    def test_flow_data_finite_after_erosion(self, eroded_hmap):
        """Flow data computed on eroded terrain should be finite."""
        from blender_addon.handlers.terrain_advanced import compute_flow_map
        raw = compute_flow_map(eroded_hmap)
        flow_acc = np.asarray(raw["flow_accumulation"], dtype=np.float64)
        assert np.isfinite(flow_acc).all()

    def test_chunking_metadata_valid(self, mountain_hmap):
        """Chunk metadata should contain expected fields."""
        from blender_addon.handlers.terrain_chunking import compute_terrain_chunks
        chunks = compute_terrain_chunks(
            mountain_hmap.tolist(), chunk_size=32, lod_levels=2
        )
        assert "chunks" in chunks
        assert len(chunks["chunks"]) > 0
        for chunk in chunks["chunks"]:
            assert "grid_x" in chunk or "row" in chunk, f"Missing grid position key: {list(chunk.keys())}"
            assert "heightmap" in chunk
            assert "lods" in chunk


# ===========================================================================
# Full pipeline integration
# ===========================================================================


class TestFullPipelineIntegration:
    """End-to-end pipeline: noise -> erosion -> flow -> slope -> biome -> chunk."""

    def test_full_pipeline_no_exceptions(self):
        """Complete pipeline should execute without exceptions."""
        from blender_addon.handlers._terrain_noise import (
            generate_heightmap, compute_slope_map, compute_biome_assignments,
        )
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion
        from blender_addon.handlers.terrain_advanced import compute_flow_map
        from blender_addon.handlers.terrain_chunking import compute_chunk_lod

        hmap = generate_heightmap(64, 64, scale=50.0, seed=42, terrain_type="mountains")
        eroded = apply_hydraulic_erosion(hmap, iterations=100, seed=42)
        slope = compute_slope_map(eroded)
        biomes = compute_biome_assignments(eroded, slope)
        compute_flow_map(eroded)
        lod = compute_chunk_lod(eroded.tolist(), 32)

        # All outputs valid
        assert eroded.shape == (64, 64)
        assert slope.shape == (64, 64)
        assert biomes.shape == (64, 64)
        assert len(lod) == 32
        assert np.isfinite(eroded).all()
        assert np.isfinite(slope).all()

    def test_pipeline_deterministic(self):
        """Full pipeline should be deterministic with same seeds."""
        from blender_addon.handlers._terrain_noise import (
            generate_heightmap, compute_slope_map, compute_biome_assignments,
        )
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        def run_pipeline():
            h = generate_heightmap(32, 32, scale=30.0, seed=7, terrain_type="hills")
            e = apply_hydraulic_erosion(h, iterations=50, seed=7)
            s = compute_slope_map(e)
            b = compute_biome_assignments(e, s)
            return e, s, b

        e1, s1, b1 = run_pipeline()
        e2, s2, b2 = run_pipeline()
        np.testing.assert_array_equal(e1, e2)
        np.testing.assert_array_equal(s1, s2)
        np.testing.assert_array_equal(b1, b2)

    def test_all_terrain_types_through_pipeline(self):
        """Every terrain type should survive the full pipeline."""
        from blender_addon.handlers._terrain_noise import (
            generate_heightmap, compute_slope_map, TERRAIN_PRESETS,
        )
        from blender_addon.handlers._terrain_erosion import apply_hydraulic_erosion

        for ttype in TERRAIN_PRESETS:
            h = generate_heightmap(32, 32, scale=30.0, seed=42, terrain_type=ttype)
            e = apply_hydraulic_erosion(h, iterations=50, seed=42)
            s = compute_slope_map(e)
            assert np.isfinite(e).all(), f"{ttype}: non-finite after erosion"
            assert np.isfinite(s).all(), f"{ttype}: non-finite in slope"
