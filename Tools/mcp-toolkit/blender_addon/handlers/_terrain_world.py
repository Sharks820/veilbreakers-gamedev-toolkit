"""Canonical world-space terrain helpers.

This module is the terrain authority for tiled world generation. It keeps the
logic pure-Python / numpy-only so it can be tested without Blender.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ._terrain_erosion import apply_hydraulic_erosion, apply_thermal_erosion
from ._terrain_noise import generate_heightmap
from .terrain_advanced import compute_flow_map


def sample_world_height(
    world_x: float,
    world_y: float,
    *,
    width: int = 1,
    height: int = 1,
    scale: float = 100.0,
    cell_size: float = 1.0,
    seed: int = 0,
    terrain_type: str = "mountains",
    normalize: bool = False,
    **kwargs: Any,
) -> float:
    """Sample a deterministic height at a world coordinate."""
    hmap = generate_world_heightmap(
        width=width,
        height=height,
        scale=scale,
        world_origin_x=world_x,
        world_origin_y=world_y,
        cell_size=cell_size,
        seed=seed,
        terrain_type=terrain_type,
        normalize=normalize,
        **kwargs,
    )
    return float(np.asarray(hmap, dtype=np.float64)[0, 0])


def generate_world_heightmap(
    width: int,
    height: int,
    *,
    scale: float = 100.0,
    world_origin_x: float = 0.0,
    world_origin_y: float = 0.0,
    cell_size: float = 1.0,
    seed: int = 0,
    terrain_type: str = "mountains",
    normalize: bool = False,
    world_center_x: float | None = None,
    world_center_y: float | None = None,
    **kwargs: Any,
) -> np.ndarray:
    """Generate a rectangular world-space heightmap window.

    The default ``normalize=False`` path keeps the world-space sample contract
    deterministic and tile-safe. Callers that need legacy behavior can opt into
    ``normalize=True``.
    """
    return generate_heightmap(
        width,
        height,
        scale=scale,
        world_origin_x=world_origin_x,
        world_origin_y=world_origin_y,
        cell_size=cell_size,
        normalize=normalize,
        seed=seed,
        terrain_type=terrain_type,
        world_center_x=world_center_x,
        world_center_y=world_center_y,
        **kwargs,
    )


def extract_tile(
    world_heightmap: np.ndarray,
    tile_x: int,
    tile_y: int,
    tile_size: int,
) -> np.ndarray:
    """Extract a tile from a world heightmap using shared edge vertices."""
    hmap = np.asarray(world_heightmap, dtype=np.float64)
    if hmap.ndim != 2:
        raise ValueError("world_heightmap must be a 2D array")

    row_start = tile_y * tile_size
    col_start = tile_x * tile_size
    row_end = row_start + tile_size + 1
    col_end = col_start + tile_size + 1

    tile = hmap[row_start:row_end, col_start:col_end]
    expected = (tile_size + 1, tile_size + 1)
    if tile.shape != expected:
        raise ValueError(
            f"Tile ({tile_x}, {tile_y}) with size {tile_size} is out of bounds "
            f"for world heightmap shape {hmap.shape}; got {tile.shape}, expected {expected}."
        )
    return tile.copy()


def validate_tile_seams(
    tiles: dict[tuple[int, int], np.ndarray],
    *,
    atol: float = 1e-6,
) -> dict[str, Any]:
    """Validate shared-edge equality for a set of extracted tiles."""
    issues: list[str] = []
    max_delta = 0.0

    for (tx, ty), tile in tiles.items():
        tile_arr = np.asarray(tile, dtype=np.float64)
        if tile_arr.ndim != 2:
            issues.append(f"tile ({tx}, {ty}) is not 2D")
            continue

        east = tiles.get((tx + 1, ty))
        if east is not None:
            east_arr = np.asarray(east, dtype=np.float64)
            if east_arr.shape != tile_arr.shape:
                issues.append(f"tile ({tx}, {ty}) east neighbor shape mismatch")
            else:
                delta = np.max(np.abs(tile_arr[:, -1] - east_arr[:, 0]))
                max_delta = max(max_delta, float(delta))
                if delta > atol:
                    issues.append(f"east seam mismatch at ({tx}, {ty}) -> ({tx + 1}, {ty}): {delta:.8f}")

        north = tiles.get((tx, ty + 1))
        if north is not None:
            north_arr = np.asarray(north, dtype=np.float64)
            if north_arr.shape != tile_arr.shape:
                issues.append(f"tile ({tx}, {ty}) north neighbor shape mismatch")
            else:
                delta = np.max(np.abs(tile_arr[-1, :] - north_arr[0, :]))
                max_delta = max(max_delta, float(delta))
                if delta > atol:
                    issues.append(f"north seam mismatch at ({tx}, {ty}) -> ({tx}, {ty + 1}): {delta:.8f}")

    return {
        "seam_ok": not issues,
        "max_edge_delta": max_delta,
        "issues": issues,
        "tile_count": len(tiles),
    }


def erode_world_heightmap(
    heightmap: np.ndarray,
    *,
    hydraulic_iterations: int = 1000,
    thermal_iterations: int = 0,
    seed: int = 0,
    talus_angle: float = 40.0,
) -> dict[str, Any]:
    """Erode a world heightmap as a single region, then return metadata.

    The erosion backends operate on arbitrary numeric ranges. This wrapper
    keeps the full world region intact, applies erosion in the source domain,
    and returns the eroded world heightmap plus flow metadata.
    """
    hmap = np.asarray(heightmap, dtype=np.float64)
    if hmap.ndim != 2:
        raise ValueError("heightmap must be 2D")
    if hmap.size == 0:
        return {
            "heightmap": hmap.copy(),
            "flow_map": {
                "flow_direction": [],
                "flow_accumulation": [],
                "drainage_basins": [],
                "num_basins": 0,
                "max_accumulation": 0.0,
                "resolution": (0, 0),
            },
            "source_min": 0.0,
            "source_max": 0.0,
            "height_range": 0.0,
        }

    source_min = float(hmap.min())
    source_max = float(hmap.max())
    height_range = source_max - source_min
    if height_range <= 1e-12:
        return {
            "heightmap": hmap.copy(),
            "flow_map": {
                "flow_direction": np.zeros_like(hmap, dtype=np.int32).tolist(),
                "flow_accumulation": np.ones_like(hmap, dtype=np.float64).tolist(),
                "drainage_basins": np.zeros_like(hmap, dtype=np.int32).tolist(),
                "num_basins": 0,
                "max_accumulation": 1.0,
                "resolution": hmap.shape,
            },
            "source_min": source_min,
            "source_max": source_max,
            "height_range": 0.0,
        }

    eroded = hmap

    if hydraulic_iterations > 0:
        eroded = apply_hydraulic_erosion(
            eroded,
            iterations=hydraulic_iterations,
            seed=seed,
            height_range=height_range,
        )

    if thermal_iterations > 0:
        eroded = np.asarray(
            apply_thermal_erosion(
                eroded,
                iterations=thermal_iterations,
                talus_angle=talus_angle,
            ),
            dtype=np.float64,
        )

    # Compute flow on the eroded world-region heightfield before splitting.
    flow_map = compute_flow_map(eroded)

    return {
        "heightmap": eroded,
        "flow_map": flow_map,
        "source_min": source_min,
        "source_max": source_max,
        "height_range": height_range,
    }


def world_region_dimensions(
    tile_count_x: int,
    tile_count_y: int,
    tile_size: int,
) -> tuple[int, int]:
    """Return world sample dimensions for a tiled region."""
    if tile_count_x < 1 or tile_count_y < 1 or tile_size < 1:
        raise ValueError("tile_count_x, tile_count_y, and tile_size must be positive")
    return tile_count_y * tile_size + 1, tile_count_x * tile_size + 1
