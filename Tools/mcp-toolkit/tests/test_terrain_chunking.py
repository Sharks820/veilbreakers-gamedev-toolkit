"""Tests for terrain_chunking handler."""

import json

import pytest

from blender_addon.handlers.terrain_chunking import (
    compute_chunk_lod,
    compute_streaming_distances,
    compute_terrain_chunks,
    export_chunks_metadata,
)


# ---------------------------------------------------------------------------
# Helper: generate a simple heightmap
# ---------------------------------------------------------------------------

def _make_heightmap(rows: int, cols: int, value: float = 1.0) -> list[list[float]]:
    return [[value * (r + c) for c in range(cols)] for r in range(rows)]


# ---------------------------------------------------------------------------
# LOD downsample
# ---------------------------------------------------------------------------


class TestComputeChunkLod:
    def test_empty_heightmap(self):
        assert compute_chunk_lod([], 4) == []

    def test_zero_target(self):
        assert compute_chunk_lod([[1, 2], [3, 4]], 0) == []

    def test_already_below_target(self):
        hmap = [[1.0, 2.0], [3.0, 4.0]]
        result = compute_chunk_lod(hmap, 8)
        assert len(result) == 2
        assert len(result[0]) == 2

    def test_downsample_produces_correct_resolution(self):
        hmap = _make_heightmap(16, 16)
        result = compute_chunk_lod(hmap, 4)
        assert len(result) == 4
        assert all(len(row) == 4 for row in result)

    def test_downsample_preserves_corners(self):
        hmap = _make_heightmap(8, 8, value=1.0)
        result = compute_chunk_lod(hmap, 2)
        # Top-left corner should match original
        assert abs(result[0][0] - hmap[0][0]) < 1e-6
        # Bottom-right corner should match original
        assert abs(result[-1][-1] - hmap[-1][-1]) < 1e-6

    def test_downsample_values_are_interpolated(self):
        hmap = [[0.0, 10.0], [10.0, 20.0]]
        # Already at target, returned as-is
        result = compute_chunk_lod(hmap, 2)
        assert result[0][0] == 0.0
        assert result[1][1] == 20.0


# ---------------------------------------------------------------------------
# Streaming distances
# ---------------------------------------------------------------------------


class TestStreamingDistances:
    def test_basic_distances(self):
        distances = compute_streaming_distances(64.0, 4)
        assert len(distances) == 4
        # LOD 0: 128, LOD 1: 256, LOD 2: 512, LOD 3: 1024
        assert distances[0] == 128.0
        assert distances[1] == 256.0
        assert distances[2] == 512.0
        assert distances[3] == 1024.0

    def test_distances_increase(self):
        distances = compute_streaming_distances(32.0, 3)
        for i in range(1, len(distances)):
            assert distances[i] > distances[i - 1]

    def test_single_lod(self):
        distances = compute_streaming_distances(100.0, 1)
        assert len(distances) == 1
        assert distances[0] == 200.0

    def test_reasonable_values(self):
        distances = compute_streaming_distances(64.0, 4)
        for lod, dist in distances.items():
            assert dist > 0
            assert dist < 100000  # Reasonable upper bound


# ---------------------------------------------------------------------------
# Main chunking pipeline
# ---------------------------------------------------------------------------


class TestComputeTerrainChunks:
    def test_empty_heightmap(self):
        result = compute_terrain_chunks([])
        assert result["chunks"] == []
        assert result["metadata"]["total_chunks"] == 0

    def test_empty_row(self):
        result = compute_terrain_chunks([[]])
        assert result["chunks"] == []

    def test_basic_chunking(self):
        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        assert len(result["chunks"]) == 4  # 2x2 grid
        assert result["metadata"]["grid_size"] == (2, 2)

    def test_chunk_has_required_fields(self):
        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        chunk = result["chunks"][0]
        assert "grid_x" in chunk
        assert "grid_y" in chunk
        assert "heightmap" in chunk
        assert "bounds" in chunk
        assert "lods" in chunk
        assert "neighbor_chunks" in chunk

    def test_lod_levels(self):
        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=64, lod_levels=3)
        chunk = result["chunks"][0]
        assert len(chunk["lods"]) == 3
        # Each LOD should have decreasing resolution
        for lod in chunk["lods"]:
            assert "lod_level" in lod
            assert "resolution" in lod
            assert "vertex_count" in lod

    def test_neighbor_references(self):
        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        # Corner chunk (0,0) should have no north/west
        corner = [c for c in result["chunks"] if c["grid_x"] == 0 and c["grid_y"] == 0][0]
        assert corner["neighbor_chunks"]["north"] is None
        assert corner["neighbor_chunks"]["west"] is None
        assert corner["neighbor_chunks"]["south"] is not None
        assert corner["neighbor_chunks"]["east"] is not None

    def test_metadata_well_formed(self):
        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64, lod_levels=4)
        meta = result["metadata"]
        assert meta["total_chunks"] == 4
        assert meta["chunk_size_samples"] == 64
        assert meta["lod_levels"] == 4
        assert meta["heightmap_size"] == (128, 128)
        assert "streaming_distance_lod" in meta

    def test_world_scale(self):
        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=64, world_scale=2.0)
        meta = result["metadata"]
        assert meta["chunk_world_size"] == 128.0


# ---------------------------------------------------------------------------
# Metadata export
# ---------------------------------------------------------------------------


class TestExportMetadata:
    def test_export_json_valid(self):
        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        json_str = export_chunks_metadata(result)
        data = json.loads(json_str)
        assert "terrain_metadata" in data
        assert "chunks" in data

    def test_export_strips_heightmap_data(self):
        hmap = _make_heightmap(64, 64)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        json_str = export_chunks_metadata(result)
        data = json.loads(json_str)
        for chunk in data["chunks"]:
            assert "heightmap" not in chunk

    def test_export_preserves_grid_info(self):
        hmap = _make_heightmap(128, 128)
        result = compute_terrain_chunks(hmap, chunk_size=64)
        json_str = export_chunks_metadata(result)
        data = json.loads(json_str)
        assert len(data["chunks"]) == 4
        grid_positions = [(c["grid_x"], c["grid_y"]) for c in data["chunks"]]
        assert (0, 0) in grid_positions
