"""Terrain chunking for open-world streaming with LOD support.

Splits large heightmaps into streamable chunks, generates LOD levels via
bilinear downsampling, computes neighbor references for edge stitching,
and exports metadata for Unity's terrain streaming system.

All functions are pure Python/numpy with NO bpy dependency — fully testable
outside Blender.

Provides:
  - compute_terrain_chunks: Main chunking + LOD pipeline
  - compute_chunk_lod: Single-chunk LOD downsample
  - compute_streaming_distances: Per-LOD streaming distance recommendations
  - export_chunks_metadata: JSON export for Unity integration
"""

from __future__ import annotations

import json
import math
from typing import Any


# ---------------------------------------------------------------------------
# LOD downsample
# ---------------------------------------------------------------------------


def compute_chunk_lod(
    heightmap_chunk: list[list[float]],
    target_resolution: int,
) -> list[list[float]]:
    """Downsample a heightmap chunk to the given target resolution.

    Uses bilinear interpolation for smooth LOD transitions.  If the input
    is already at or below the target resolution, it is returned as-is.

    Args:
        heightmap_chunk: 2D array of height values (rows x cols).
        target_resolution: Desired output resolution (both width and height).

    Returns:
        Downsampled 2D height array of size ``target_resolution x target_resolution``.
    """
    src_rows = len(heightmap_chunk)
    if src_rows == 0:
        return []
    src_cols = len(heightmap_chunk[0])

    if target_resolution <= 0:
        return []

    if src_rows <= target_resolution and src_cols <= target_resolution:
        # Already at or below target — return copy
        return [list(row) for row in heightmap_chunk]

    result: list[list[float]] = []

    for tr in range(target_resolution):
        row_out: list[float] = []
        # Map target row to source row (floating point)
        src_r = tr * (src_rows - 1) / max(target_resolution - 1, 1)

        for tc in range(target_resolution):
            # Map target col to source col
            src_c = tc * (src_cols - 1) / max(target_resolution - 1, 1)

            # Bilinear interpolation
            r0 = int(math.floor(src_r))
            r1 = min(r0 + 1, src_rows - 1)
            c0 = int(math.floor(src_c))
            c1 = min(c0 + 1, src_cols - 1)

            fr = src_r - r0
            fc = src_c - c0

            v00 = heightmap_chunk[r0][c0]
            v01 = heightmap_chunk[r0][c1]
            v10 = heightmap_chunk[r1][c0]
            v11 = heightmap_chunk[r1][c1]

            # Bilinear blend
            top = v00 * (1.0 - fc) + v01 * fc
            bot = v10 * (1.0 - fc) + v11 * fc
            val = top * (1.0 - fr) + bot * fr

            row_out.append(val)
        result.append(row_out)

    return result


# ---------------------------------------------------------------------------
# Streaming distance computation
# ---------------------------------------------------------------------------


def compute_streaming_distances(
    chunk_world_size: float,
    lod_levels: int,
) -> dict[int, float]:
    """Compute recommended streaming distances per LOD level.

    Each LOD level covers a distance band that doubles:
      - LOD 0: ``0`` to ``chunk_world_size * 2``
      - LOD 1: ``chunk_world_size * 2`` to ``chunk_world_size * 4``
      - LOD 2: ``chunk_world_size * 4`` to ``chunk_world_size * 8``
      - LOD 3: ``chunk_world_size * 8`` to ``chunk_world_size * 16``

    The returned values are the *outer boundary* of each LOD band.

    Args:
        chunk_world_size: World-space size of a single chunk (square).
        lod_levels: Number of LOD levels.

    Returns:
        Dict mapping LOD index to maximum streaming distance.
    """
    distances: dict[int, float] = {}
    for i in range(lod_levels):
        distances[i] = chunk_world_size * (2 ** (i + 1))
    return distances


# ---------------------------------------------------------------------------
# Main chunking pipeline
# ---------------------------------------------------------------------------


def compute_terrain_chunks(
    heightmap: list[list[float]],
    chunk_size: int = 64,
    overlap: int = 1,
    lod_levels: int = 4,
    world_scale: float = 1.0,
    world_origin: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Split a terrain heightmap into streamable chunks with LOD.

    Divides the heightmap into a grid of ``chunk_size x chunk_size`` tiles
    (plus ``overlap`` border samples on each edge for seamless stitching),
    then generates ``lod_levels`` downsampled versions of each chunk.

    Args:
        heightmap: 2D array of height values. Must be at least
            ``chunk_size x chunk_size``.
        chunk_size: Number of samples per chunk side (before overlap).
            Must be a power of 2 for clean LOD halving.
        overlap: Number of border samples shared with adjacent chunks
            for seam-free stitching.
        lod_levels: Number of LOD levels per chunk.  LOD 0 is full
            resolution; each subsequent level halves the resolution.
        world_scale: Multiplier from heightmap samples to world units.
        world_origin: Optional world-space origin of the heightmap region.

    Returns:
        Dict with:
          ``chunks``: list of chunk dicts, each containing:
            - ``grid_x``, ``grid_y``: Grid position
            - ``heightmap``: 2D sub-array (with overlap border)
            - ``bounds``: ``(min_x, min_y, max_x, max_y)`` in world space
            - ``lods``: list of LOD dicts with ``resolution``, ``heightmap``,
              ``vertex_count``
            - ``neighbor_chunks``: dict with ``north``, ``south``, ``east``,
              ``west`` neighbor grid coords (or ``None``)
          ``metadata``: summary information about the full terrain.
    """
    total_rows = len(heightmap)
    if total_rows == 0:
        return {"chunks": [], "metadata": _empty_metadata()}
    total_cols = len(heightmap[0])
    if total_cols == 0:
        return {"chunks": [], "metadata": _empty_metadata()}

    if world_origin is None:
        origin_x, origin_y = 0.0, 0.0
    else:
        if len(world_origin) != 2:
            raise ValueError("world_origin must be a 2-tuple of (x, y)")
        origin_x = float(world_origin[0])
        origin_y = float(world_origin[1])

    # Number of chunks in each direction
    grid_cols = max(1, total_cols // chunk_size)
    grid_rows = max(1, total_rows // chunk_size)

    chunk_world_size = chunk_size * world_scale

    chunks: list[dict[str, Any]] = []
    total_verts_lod0 = 0

    for gy in range(grid_rows):
        for gx in range(grid_cols):
            # Source sample region (with overlap clamped to heightmap bounds)
            r_start = gy * chunk_size - overlap
            r_end = (gy + 1) * chunk_size + overlap
            c_start = gx * chunk_size - overlap
            c_end = (gx + 1) * chunk_size + overlap

            # Clamp to array bounds
            r_start_clamped = max(0, r_start)
            r_end_clamped = min(total_rows, r_end)
            c_start_clamped = max(0, c_start)
            c_end_clamped = min(total_cols, c_end)

            # Extract sub-array
            sub_heightmap: list[list[float]] = []
            for r in range(r_start_clamped, r_end_clamped):
                row = heightmap[r][c_start_clamped:c_end_clamped]
                sub_heightmap.append(list(row))

            # World-space bounds (without overlap — the chunk's logical area)
            min_x = origin_x + gx * chunk_world_size
            min_y = origin_y + gy * chunk_world_size
            max_x = origin_x + (gx + 1) * chunk_world_size
            max_y = origin_y + (gy + 1) * chunk_world_size

            # Generate LOD levels
            lods: list[dict[str, Any]] = []
            for lod in range(lod_levels):
                # Target resolution: chunk_size / 2^lod (minimum 2)
                target_res = max(2, chunk_size >> lod)
                if lod == 0:
                    # LOD0 uses the full sub-heightmap (may include overlap)
                    lod_hmap = [list(row) for row in sub_heightmap]
                    lod_res = len(sub_heightmap)
                    if lod_res > 0:
                        lod_res_cols = len(sub_heightmap[0])
                    else:
                        lod_res_cols = 0
                    vert_count = lod_res * lod_res_cols
                else:
                    lod_hmap = compute_chunk_lod(sub_heightmap, target_res)
                    lod_res = len(lod_hmap)
                    lod_res_cols = len(lod_hmap[0]) if lod_res > 0 else 0
                    vert_count = lod_res * lod_res_cols

                lods.append(
                    {
                        "lod_level": lod,
                        "resolution": target_res if lod > 0 else (
                            len(sub_heightmap[0]) if sub_heightmap else 0
                        ),
                    "heightmap": lod_hmap,
                    "vertex_count": vert_count,
                }
            )

            if lods:
                total_verts_lod0 += lods[0]["vertex_count"]

            # Neighbor references
            neighbors: dict[str, tuple[int, int] | None] = {
                "north": (gx, gy - 1) if gy > 0 else None,
                "south": (gx, gy + 1) if gy < grid_rows - 1 else None,
                "west": (gx - 1, gy) if gx > 0 else None,
                "east": (gx + 1, gy) if gx < grid_cols - 1 else None,
            }

            chunks.append(
                {
                    "grid_x": gx,
                    "grid_y": gy,
                    "heightmap": sub_heightmap,
                    "bounds": (min_x, min_y, max_x, max_y),
                    "world_origin": (origin_x, origin_y),
                    "lods": lods,
                    "neighbor_chunks": neighbors,
                }
            )

    streaming_dist = compute_streaming_distances(chunk_world_size, lod_levels)

    metadata: dict[str, Any] = {
        "total_chunks": len(chunks),
        "grid_size": (grid_cols, grid_rows),
        "chunk_world_size": chunk_world_size,
        "world_origin": (origin_x, origin_y),
        "total_vertices_lod0": total_verts_lod0,
        "streaming_distance_lod": streaming_dist,
        "chunk_size_samples": chunk_size,
        "overlap": overlap,
        "lod_levels": lod_levels,
        "heightmap_size": (total_cols, total_rows),
    }

    return {"chunks": chunks, "metadata": metadata}


# ---------------------------------------------------------------------------
# Metadata export
# ---------------------------------------------------------------------------


def export_chunks_metadata(
    chunks_result: dict[str, Any],
    output_format: str = "json",
) -> str:
    """Export chunk layout as JSON for Unity terrain streaming system.

    Strips the heavy heightmap data and exports only the structural
    metadata: grid positions, bounds, LOD info, neighbor refs, and
    streaming distances.

    Args:
        chunks_result: Output from :func:`compute_terrain_chunks`.
        output_format: Currently only ``'json'`` is supported.

    Returns:
        JSON string (pretty-printed) with chunk layout metadata.
    """
    metadata = chunks_result.get("metadata", {})

    # Build lightweight chunk entries (no heightmap data)
    chunk_entries: list[dict[str, Any]] = []
    for chunk in chunks_result.get("chunks", []):
        lod_summary = []
        for lod in chunk.get("lods", []):
            lod_summary.append(
                {
                    "lod_level": lod["lod_level"],
                    "resolution": lod["resolution"],
                    "vertex_count": lod["vertex_count"],
                }
            )

        chunk_entries.append(
            {
                "grid_x": chunk["grid_x"],
                "grid_y": chunk["grid_y"],
                "bounds": chunk["bounds"],
                "lod_count": len(lod_summary),
                "lods": lod_summary,
                "neighbor_chunks": chunk["neighbor_chunks"],
            }
        )

    export_data = {
        "terrain_metadata": metadata,
        "chunks": chunk_entries,
    }

    # Convert streaming_distance_lod keys from int to str for JSON compat
    if "streaming_distance_lod" in export_data["terrain_metadata"]:
        sd = export_data["terrain_metadata"]["streaming_distance_lod"]
        export_data["terrain_metadata"]["streaming_distance_lod"] = {
            str(k): v for k, v in sd.items()
        }

    return json.dumps(export_data, indent=2)


def validate_tile_seams(
    tile_a: list[list[float]],
    tile_b: list[list[float]],
    direction: str = "east",
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Validate that two adjacent tiles share matching seam samples.

    Args:
        tile_a: First tile heightmap.
        tile_b: Adjacent tile heightmap.
        direction: Relative direction of tile_b from tile_a.
        tolerance: Maximum allowed absolute delta for a seam sample.

    Returns:
        Dict describing seam agreement.
    """
    if len(tile_a) == 0 or len(tile_b) == 0:
        return {
            "match": False,
            "direction": direction,
            "sample_count": 0,
            "max_delta": None,
            "mean_delta": None,
            "error": "empty tile input",
        }
    if len(tile_a[0]) == 0 or len(tile_b[0]) == 0:
        return {
            "match": False,
            "direction": direction,
            "sample_count": 0,
            "max_delta": None,
            "mean_delta": None,
            "error": "empty tile input",
        }

    rows_a = len(tile_a)
    cols_a = len(tile_a[0])
    rows_b = len(tile_b)
    cols_b = len(tile_b[0])

    if direction in {"east", "west"}:
        if rows_a != rows_b:
            return {
                "match": False,
                "direction": direction,
                "sample_count": 0,
                "max_delta": None,
                "mean_delta": None,
                "error": "row count mismatch",
            }
        seam_pairs = [
            (float(tile_a[row][cols_a - 1]), float(tile_b[row][0]))
            for row in range(rows_a)
        ]
    elif direction in {"north", "south"}:
        if cols_a != cols_b:
            return {
                "match": False,
                "direction": direction,
                "sample_count": 0,
                "max_delta": None,
                "mean_delta": None,
                "error": "column count mismatch",
            }
        seam_pairs = [
            (float(tile_a[rows_a - 1][col]), float(tile_b[0][col]))
            for col in range(cols_a)
        ]
    else:
        raise ValueError("direction must be one of: east, west, north, south")

    deltas = [abs(a - b) for a, b in seam_pairs]
    max_delta = max(deltas) if deltas else 0.0
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    return {
        "match": max_delta <= tolerance,
        "direction": direction,
        "sample_count": len(deltas),
        "max_delta": max_delta,
        "mean_delta": mean_delta,
        "tolerance": tolerance,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_metadata() -> dict[str, Any]:
    """Return an empty metadata dict for degenerate inputs."""
    return {
        "total_chunks": 0,
        "grid_size": (0, 0),
        "chunk_world_size": 0.0,
        "world_origin": (0.0, 0.0),
        "total_vertices_lod0": 0,
        "streaming_distance_lod": {},
        "chunk_size_samples": 0,
        "overlap": 0,
        "lod_levels": 0,
        "heightmap_size": (0, 0),
    }
