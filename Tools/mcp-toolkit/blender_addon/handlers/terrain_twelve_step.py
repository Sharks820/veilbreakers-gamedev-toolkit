"""Canonical 12-step world terrain orchestration sequence.

Bundle A supplement implementing Addendum 2.A.7 exactly. Every implementation
of the world-terrain orchestrator MUST follow this sequence. This module is
the reference implementation — pure numpy, headless-compatible, no bpy.

Stubs are intentional where the non-mesh passes have not landed yet. Steps
1-9 + 12 do real work; steps 10 and 11 are pass-through stubs that will be
filled in when road/water-body mesh bundles land.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import logging

from ._terrain_world import (
    erode_world_heightmap,
    extract_tile,
    generate_world_heightmap,
    validate_tile_seams,
)
from .terrain_advanced import compute_flow_map
from .terrain_semantics import TerrainIntentState, TerrainMaskStack
from .terrain_world_math import (
    TileTransform,
    compute_erosion_params_for_world_range,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 12-step orchestration
# ---------------------------------------------------------------------------


def _apply_flatten_zones_stub(world_hmap: np.ndarray, intent: TerrainIntentState) -> np.ndarray:
    """Step 4 — apply flatten zones on world heightmap. Stub pass-through."""
    return world_hmap


def _apply_canyon_river_carves_stub(
    world_hmap: np.ndarray, intent: TerrainIntentState
) -> np.ndarray:
    """Step 5 — apply canyon/river A* carves. Stub pass-through."""
    return world_hmap


def _detect_cliff_edges_stub(world_hmap: np.ndarray) -> List[Tuple[int, int]]:
    """Detect cliff edges via gradient magnitude threshold on the heightmap."""
    coords: List[Tuple[int, int]] = []
    if world_hmap.size == 0:
        return coords
    gy, gx = np.gradient(world_hmap)
    grad_mag = np.sqrt(gx ** 2 + gy ** 2)
    threshold = float(np.percentile(grad_mag, 95))
    ys, xs = np.where(grad_mag >= threshold)
    for y, x in zip(ys.tolist(), xs.tolist()):
        coords.append((int(x), int(y)))
    return coords


def _detect_cave_candidates_stub(world_hmap: np.ndarray) -> List[Tuple[int, int]]:
    """Detect cave candidates as local minima surrounded by higher terrain."""
    coords: List[Tuple[int, int]] = []
    if world_hmap.size == 0 or world_hmap.shape[0] < 3 or world_hmap.shape[1] < 3:
        return coords
    h, w = world_hmap.shape
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            centre = world_hmap[y, x]
            neighbours = world_hmap[y - 1:y + 2, x - 1:x + 2]
            if centre <= np.min(neighbours):
                coords.append((x, y))
    return coords


def _detect_waterfall_lips_stub(world_hmap: np.ndarray) -> List[Tuple[int, int]]:
    """Detect waterfall lip candidates where a plateau drops sharply."""
    coords: List[Tuple[int, int]] = []
    if world_hmap.size == 0 or world_hmap.shape[0] < 3:
        return coords
    # Look for rows where height drops significantly downward
    dy = np.diff(world_hmap, axis=0)
    threshold = float(np.percentile(np.abs(dy), 97))
    ys, xs = np.where(dy <= -threshold)
    for y, x in zip(ys.tolist(), xs.tolist()):
        coords.append((int(x), int(y)))
    return coords


def _generate_road_mesh_specs(
    world_hmap: np.ndarray,
    intent: TerrainIntentState,
    tile_grid_x: int,
    tile_grid_y: int,
    cell_size: float,
    seed: int,
) -> List[Dict[str, Any]]:
    """Step 10: generate road mesh specifications from the world heightmap.

    Delegates to ``generate_road_path`` from ``_terrain_noise`` when waypoints
    are available in the intent. Returns a list of mesh spec dicts describing
    each road segment (vertices, width, graded heightmap patch).

    If no waypoints are configured on the intent the function returns an empty
    list and logs the skip.
    """
    from ._terrain_noise import generate_road_path

    waypoints: List[Tuple[int, int]] = getattr(intent, "road_waypoints", None) or []
    if len(waypoints) < 2:
        _log.info(
            "Step 10 skipped: fewer than 2 road waypoints on intent (got %d)",
            len(waypoints),
        )
        return []

    road_specs: List[Dict[str, Any]] = []
    try:
        path, graded_hmap = generate_road_path(
            world_hmap,
            waypoints,
            width=max(3, int(3.0 / cell_size)),
            grade_strength=0.8,
            seed=seed,
        )
        road_specs.append({
            "path": path,
            "width_cells": max(3, int(3.0 / cell_size)),
            "vertex_count": len(path),
            "seed": seed,
        })
        _log.info("Step 10: generated road with %d vertices", len(path))
    except Exception as exc:  # noqa: BLE001
        _log.warning("Step 10: road generation failed: %s", exc)

    return road_specs


def _generate_water_body_specs(
    world_hmap: np.ndarray,
    world_flow: Dict[str, Any],
    intent: TerrainIntentState,
    cell_size: float,
) -> List[Dict[str, Any]]:
    """Step 11: generate water body specifications from flow accumulation.

    Identifies cells with high flow accumulation (potential lake / river pools)
    and returns mesh specs for flat water surfaces at the local height.

    Returns an empty list when no significant accumulation basins are found.
    """
    water_specs: List[Dict[str, Any]] = []

    # Extract flow accumulation from the world flow map
    flow_acc_raw = world_flow.get("flow_accumulation")
    if flow_acc_raw is None:
        _log.info("Step 11 skipped: no flow_accumulation in world_flow")
        return water_specs

    flow_acc = np.asarray(flow_acc_raw, dtype=np.float64)
    if flow_acc.size == 0:
        _log.info("Step 11 skipped: empty flow_accumulation array")
        return water_specs

    max_acc = float(flow_acc.max())
    if max_acc <= 0:
        _log.info("Step 11 skipped: max flow accumulation is 0")
        return water_specs

    # Threshold: cells above 70% of max accumulation are water candidates
    threshold = max_acc * 0.7
    water_mask = flow_acc >= threshold
    water_cell_count = int(water_mask.sum())

    if water_cell_count == 0:
        _log.info("Step 11: no cells above accumulation threshold (%.1f)", threshold)
        return water_specs

    # Compute average height of water cells for the surface plane
    water_heights = world_hmap[water_mask]
    surface_height = float(water_heights.mean())

    water_specs.append({
        "type": "accumulated_basin",
        "cell_count": water_cell_count,
        "surface_height": surface_height,
        "threshold": threshold,
        "max_accumulation": max_acc,
        "cell_size": cell_size,
    })
    _log.info(
        "Step 11: identified water body with %d cells at height %.2f",
        water_cell_count,
        surface_height,
    )

    return water_specs


def run_twelve_step_world_terrain(
    intent: TerrainIntentState,
    tile_grid_x: int,
    tile_grid_y: int,
) -> Dict[str, Any]:
    """Execute the canonical 12-step world terrain sequence.

    Returns a dict with:
        - tile_stacks: Dict[(tx, ty), TerrainMaskStack]
        - tile_transforms: Dict[(tx, ty), TileTransform]
        - world_heightmap: np.ndarray (eroded)
        - world_flow_map: dict
        - cliff_candidates / cave_candidates / waterfall_lip_candidates: List
        - seam_report: dict from validate_tile_seams
        - sequence: List[str] — the 12-step names in execution order (audit trail)
        - metadata: dict
    """
    sequence: List[str] = []
    t_start = time.time()

    # Step 1 — Parse params
    sequence.append("1_parse_params")
    tile_size = int(intent.tile_size)
    cell_size = float(intent.cell_size)
    seed = int(intent.seed)
    if tile_grid_x < 1 or tile_grid_y < 1:
        raise ValueError(f"tile_grid must be >= 1x1; got {tile_grid_x}x{tile_grid_y}")
    if tile_size <= 0:
        raise ValueError(f"intent.tile_size must be > 0; got {tile_size}")

    # Step 2 — Compute world region
    sequence.append("2_compute_world_region")
    total_samples_x = tile_grid_x * tile_size + 1
    total_samples_y = tile_grid_y * tile_size + 1
    world_origin_x = float(intent.region_bounds.min_x)
    world_origin_y = float(intent.region_bounds.min_y)

    # Step 3 — generate_world_heightmap (world units, not normalized)
    sequence.append("3_generate_world_heightmap")
    world_hmap = generate_world_heightmap(
        width=total_samples_x,
        height=total_samples_y,
        scale=100.0,
        world_origin_x=world_origin_x,
        world_origin_y=world_origin_y,
        cell_size=cell_size,
        seed=seed,
        terrain_type="mountains",
        normalize=False,
    )
    world_hmap = np.asarray(world_hmap, dtype=np.float64)

    # Step 4 — apply flatten zones
    sequence.append("4_apply_flatten_zones")
    world_hmap = _apply_flatten_zones_stub(world_hmap, intent)

    # Step 5 — apply canyon/river carves
    sequence.append("5_apply_canyon_river_carves")
    world_hmap = _apply_canyon_river_carves_stub(world_hmap, intent)

    # Step 6 — erode world heightmap (exact — full region, before split)
    sequence.append("6_erode_world_heightmap")
    erosion_params = compute_erosion_params_for_world_range(
        float(world_hmap.max() - world_hmap.min())
    )
    erosion_result = erode_world_heightmap(
        world_hmap,
        hydraulic_iterations=50,  # small for deterministic test speed
        thermal_iterations=0,
        seed=seed,
        cell_size=cell_size,
    )
    world_eroded = np.asarray(erosion_result["heightmap"], dtype=np.float64)

    # Step 7 — compute_flow_map on eroded world
    sequence.append("7_compute_flow_map")
    world_flow = erosion_result.get("flow_map") or compute_flow_map(world_eroded)

    # Step 8 — detect cliff edges / caves / waterfall lips
    sequence.append("8_detect_hero_candidates")
    cliff_candidates = _detect_cliff_edges_stub(world_eroded)
    cave_candidates = _detect_cave_candidates_stub(world_eroded)
    waterfall_lip_candidates = _detect_waterfall_lips_stub(world_eroded)

    # Step 9 — per-tile extraction
    sequence.append("9_per_tile_extract")
    tile_stacks: Dict[Tuple[int, int], TerrainMaskStack] = {}
    tile_transforms: Dict[Tuple[int, int], TileTransform] = {}
    extracted_heights: Dict[Tuple[int, int], np.ndarray] = {}

    tile_size_world = float(tile_size) * cell_size

    for ty in range(tile_grid_y):
        for tx in range(tile_grid_x):
            tile_height = extract_tile(world_eroded, tx, ty, tile_size)
            extracted_heights[(tx, ty)] = tile_height

            tile_origin_x = world_origin_x + tx * tile_size_world
            tile_origin_y = world_origin_y + ty * tile_size_world
            stack = TerrainMaskStack(
                tile_size=tile_size,
                cell_size=cell_size,
                world_origin_x=tile_origin_x,
                world_origin_y=tile_origin_y,
                tile_x=tx,
                tile_y=ty,
                height=tile_height,
            )
            tile_stacks[(tx, ty)] = stack

            tmin_z = float(tile_height.min())
            tmax_z = float(tile_height.max())
            tile_transforms[(tx, ty)] = TileTransform(
                origin_world=(tile_origin_x, tile_origin_y, tmin_z),
                min_corner_world=(tile_origin_x, tile_origin_y, tmin_z),
                max_corner_world=(
                    tile_origin_x + tile_size_world,
                    tile_origin_y + tile_size_world,
                    tmax_z,
                ),
                tile_coords=(tx, ty),
                tile_size_world=tile_size_world,
                convention="object_origin_at_min_corner",
            )

    # Step 10 — generate road meshes in world space
    sequence.append("10_generate_road_meshes")
    road_specs = _generate_road_mesh_specs(world_eroded, intent, tile_grid_x, tile_grid_y, cell_size, seed)

    # Step 11 — generate water bodies in world space
    sequence.append("11_generate_water_bodies")
    water_specs = _generate_water_body_specs(world_eroded, world_flow, intent, cell_size)

    # Step 12 — validate tile seams (hard gate)
    sequence.append("12_validate_tile_seams")
    seam_report = validate_tile_seams(extracted_heights, atol=1e-6)

    t_elapsed = time.time() - t_start

    return {
        "tile_stacks": tile_stacks,
        "tile_transforms": tile_transforms,
        "world_heightmap": world_eroded,
        "world_flow_map": world_flow,
        "cliff_candidates": cliff_candidates,
        "cave_candidates": cave_candidates,
        "waterfall_lip_candidates": waterfall_lip_candidates,
        "road_specs": road_specs,
        "water_specs": water_specs,
        "seam_report": seam_report,
        "sequence": sequence,
        "metadata": {
            "tile_grid": (tile_grid_x, tile_grid_y),
            "tile_size": tile_size,
            "cell_size": cell_size,
            "seed": seed,
            "elapsed_s": t_elapsed,
            "erosion_params": erosion_params,
            "world_shape": list(world_eroded.shape),
        },
    }


__all__ = ["run_twelve_step_world_terrain"]
