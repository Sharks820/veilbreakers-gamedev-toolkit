"""Canonical world-space terrain helpers + Bundle A pass functions.

This module is the terrain authority for tiled world generation. It keeps the
logic pure-Python / numpy-only so it can be tested without Blender.

Bundle A adds four pass functions consumed by ``TerrainPassController``:

    pass_macro_world        — seed the mask stack height channel
    pass_structural_masks   — populate slope/curvature/ridge/basin/saliency
    pass_erosion            — populate erosion / wetness / drainage / talus
    pass_validation_minimal — emit a minimal PassResult with sanity metrics

Existing helpers (``sample_world_height``, ``generate_world_heightmap``,
``extract_tile``, ``validate_tile_seams``, ``erode_world_heightmap``,
``world_region_dimensions``) remain unchanged for backward compat.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import numpy as np

from ._terrain_erosion import (
    apply_hydraulic_erosion,
    apply_hydraulic_erosion_masks,
    apply_thermal_erosion,
    apply_thermal_erosion_masks,
)
from ._terrain_noise import generate_heightmap
from .terrain_advanced import compute_flow_map
from .terrain_semantics import (
    BBox,
    PassResult,
    TerrainPipelineState,
    ValidationIssue,
)


def _sample_single_height(
    world_x: float,
    world_y: float,
    *,
    scale: float,
    cell_size: float,
    seed: int,
    terrain_type: str,
    normalize: bool,
    **kwargs: Any,
) -> float:
    """Evaluate a single deterministic terrain sample without building a full window."""
    sample = generate_heightmap(
        1,
        1,
        scale=scale,
        world_origin_x=world_x,
        world_origin_y=world_y,
        cell_size=cell_size,
        seed=seed,
        terrain_type=terrain_type,
        normalize=normalize,
        **kwargs,
    )
    return float(np.asarray(sample, dtype=np.float64)[0, 0])


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
    if width == 1 and height == 1:
        return _sample_single_height(
            world_x,
            world_y,
            scale=scale,
            cell_size=cell_size,
            seed=seed,
            terrain_type=terrain_type,
            normalize=normalize,
            **kwargs,
        )
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
    """Extract a tile from a world array using shared edge vertices."""
    hmap = np.asarray(world_heightmap, dtype=np.float64)
    if hmap.ndim < 2:
        raise ValueError("world_heightmap must have at least 2 dimensions")

    row_start = tile_y * tile_size
    col_start = tile_x * tile_size
    row_end = row_start + tile_size + 1
    col_end = col_start + tile_size + 1

    tile = hmap[row_start:row_end, col_start:col_end, ...]
    expected = (tile_size + 1, tile_size + 1)
    if tile.shape[:2] != expected:
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
    channel_count = 1

    for (tx, ty), tile in tiles.items():
        tile_arr = np.asarray(tile, dtype=np.float64)
        if tile_arr.ndim < 2:
            issues.append(f"tile ({tx}, {ty}) must have at least 2 dimensions")
            continue
        channel_count = max(channel_count, int(np.prod(tile_arr.shape[2:]) or 1))

        east = tiles.get((tx + 1, ty))
        if east is not None:
            east_arr = np.asarray(east, dtype=np.float64)
            if east_arr.shape[:2] != tile_arr.shape[:2] or east_arr.shape[2:] != tile_arr.shape[2:]:
                issues.append(f"tile ({tx}, {ty}) east neighbor shape mismatch")
            else:
                delta = np.max(np.abs(tile_arr[:, -1, ...] - east_arr[:, 0, ...]))
                max_delta = max(max_delta, float(delta))
                if delta > atol:
                    issues.append(f"east seam mismatch at ({tx}, {ty}) -> ({tx + 1}, {ty}): {delta:.8f}")

        north = tiles.get((tx, ty + 1))
        if north is not None:
            north_arr = np.asarray(north, dtype=np.float64)
            if north_arr.shape[:2] != tile_arr.shape[:2] or north_arr.shape[2:] != tile_arr.shape[2:]:
                issues.append(f"tile ({tx}, {ty}) north neighbor shape mismatch")
            else:
                delta = np.max(np.abs(tile_arr[-1, :, ...] - north_arr[0, :, ...]))
                max_delta = max(max_delta, float(delta))
                if delta > atol:
                    issues.append(f"north seam mismatch at ({tx}, {ty}) -> ({tx}, {ty + 1}): {delta:.8f}")

    return {
        "seam_ok": not issues,
        "max_edge_delta": max_delta,
        "issues": issues,
        "tile_count": len(tiles),
        "channel_count": channel_count,
    }


def erode_world_heightmap(
    heightmap: np.ndarray,
    *,
    hydraulic_iterations: int = 1000,
    thermal_iterations: int = 0,
    seed: int = 0,
    talus_angle: float = 40.0,
    cell_size: float = 1.0,
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
                cell_size=cell_size,
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


# ---------------------------------------------------------------------------
# Bundle A pass functions
# ---------------------------------------------------------------------------


def _region_slice(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> tuple[slice, slice]:
    """Resolve a BBox to (row_slice, col_slice) for the current mask stack."""
    stack = state.mask_stack
    if region is None:
        h = stack.height
        return slice(0, h.shape[0]), slice(0, h.shape[1])
    return region.to_cell_slice(
        world_origin_x=stack.world_origin_x,
        world_origin_y=stack.world_origin_y,
        cell_size=stack.cell_size,
        grid_shape=stack.height.shape,
    )


def _protected_mask(
    state: TerrainPipelineState,
    shape: tuple[int, int],
    pass_name: str,
) -> np.ndarray:
    """Build a boolean mask of cells under a protected zone that forbids this pass."""
    stack = state.mask_stack
    mask = np.zeros(shape, dtype=bool)
    if not state.intent.protected_zones:
        return mask

    rows, cols = shape
    ys = stack.world_origin_y + (np.arange(rows) + 0.5) * stack.cell_size
    xs = stack.world_origin_x + (np.arange(cols) + 0.5) * stack.cell_size
    xg, yg = np.meshgrid(xs, ys)

    for zone in state.intent.protected_zones:
        if zone.permits(pass_name):
            continue
        inside = (
            (xg >= zone.bounds.min_x)
            & (xg <= zone.bounds.max_x)
            & (yg >= zone.bounds.min_y)
            & (yg <= zone.bounds.max_y)
        )
        mask |= inside
    return mask


def pass_macro_world(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Pass 1: generate or confirm the base height field on the mask stack.

    For Bundle A the height is normally populated at state construction
    time. This pass is idempotent — it verifies the height channel is
    present and records metrics. Future bundles may extend it to call
    ``generate_world_heightmap`` against the authoring intent.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: list[ValidationIssue] = []

    if stack.height is None or stack.height.size == 0:
        issues.append(
            ValidationIssue(
                code="MACRO_NO_HEIGHT",
                severity="hard",
                message="mask stack has no height channel",
            )
        )
        return PassResult(
            pass_name="macro_world",
            status="failed",
            duration_seconds=time.perf_counter() - t0,
            issues=issues,
        )

    # Ensure height is tracked as populated by this pass
    stack.populated_by_pass.setdefault("height", "macro_world")

    return PassResult(
        pass_name="macro_world",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        produced_channels=("height",),
        metrics={
            "height_min": float(stack.height.min()),
            "height_max": float(stack.height.max()),
            "height_mean": float(stack.height.mean()),
            "shape": tuple(stack.height.shape),
        },
    )


def pass_structural_masks(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Pass 2: populate slope, curvature, concavity, convexity, ridge, basin, saliency."""
    t0 = time.perf_counter()
    # Lazy import to dodge potential circularity during module load
    from . import terrain_masks

    stack = state.mask_stack
    terrain_masks.compute_base_masks(
        stack.height,
        stack.cell_size,
        (stack.tile_x, stack.tile_y),
        stack=stack,
        pass_name="structural_masks",
    )

    return PassResult(
        pass_name="structural_masks",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=(
            "slope",
            "curvature",
            "concavity",
            "convexity",
            "ridge",
            "basin",
            "saliency_macro",
        ),
        metrics={
            "max_slope_deg": float(np.degrees(stack.slope.max())),
            "mean_slope_deg": float(np.degrees(stack.slope.mean())),
            "ridge_fraction": float(stack.ridge.mean()),
            "basin_count": int(np.unique(stack.basin).size - (1 if 0 in stack.basin else 0)),
        },
    )


def pass_erosion(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Pass 3: run hydraulic + thermal erosion, populate erosion masks.

    Respects protected zones via a hero_exclusion mask derived from the
    intent's protected_zones list. Supports region scoping — only cells
    inside ``region`` are mutated; cells outside are restored from the
    pre-pass height snapshot.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    intent = state.intent

    seed = (intent.seed + 17) & 0xFFFFFFFF
    profile = intent.erosion_profile or "temperate"

    profile_params = {
        "temperate": dict(iterations=400, talus_angle=40.0),
        "arid": dict(iterations=200, talus_angle=45.0),
        "alpine": dict(iterations=600, talus_angle=35.0),
    }.get(profile, dict(iterations=400, talus_angle=40.0))

    h_before = stack.height.copy()

    # Combine hero_exclusion + protected-zone mask
    protected = _protected_mask(state, stack.height.shape, "erosion")
    if stack.hero_exclusion is not None:
        combined_exclusion = protected | stack.hero_exclusion.astype(bool)
    else:
        combined_exclusion = protected

    hero_arg = combined_exclusion if combined_exclusion.any() else None

    hydro = apply_hydraulic_erosion_masks(
        h_before,
        iterations=profile_params["iterations"],
        seed=seed,
        hero_exclusion=hero_arg,
    )
    thermal = apply_thermal_erosion_masks(
        hydro.height,
        iterations=6,
        talus_angle=profile_params["talus_angle"],
        cell_size=stack.cell_size,
    )

    new_height = thermal.height

    # Region scoping: restore cells outside the region from the pre-pass snapshot.
    r_slice, c_slice = _region_slice(state, region)
    if region is not None:
        scoped = h_before.copy()
        scoped[r_slice, c_slice] = new_height[r_slice, c_slice]
        new_height = scoped

        # Also scope the mask channels
        def _scope(arr: np.ndarray) -> np.ndarray:
            out = np.zeros_like(arr)
            out[r_slice, c_slice] = arr[r_slice, c_slice]
            return out

        erosion_amount_out = _scope(hydro.erosion_amount)
        deposition_amount_out = _scope(hydro.deposition_amount)
        wetness_out = _scope(hydro.wetness)
        drainage_out = _scope(hydro.drainage)
        bank_instability_out = _scope(hydro.bank_instability)
        talus_out = _scope(thermal.talus)
    else:
        erosion_amount_out = hydro.erosion_amount
        deposition_amount_out = hydro.deposition_amount
        wetness_out = hydro.wetness
        drainage_out = hydro.drainage
        bank_instability_out = hydro.bank_instability
        talus_out = thermal.talus

    # Enforce protected zones: revert those cells to the pre-pass snapshot
    if protected.any():
        new_height = np.where(protected, h_before, new_height)
        erosion_amount_out = np.where(protected, 0.0, erosion_amount_out)
        deposition_amount_out = np.where(protected, 0.0, deposition_amount_out)
        wetness_out = np.where(protected, 0.0, wetness_out)
        drainage_out = np.where(protected, 0.0, drainage_out)
        bank_instability_out = np.where(protected, 0.0, bank_instability_out)
        talus_out = np.where(protected, 0.0, talus_out)

    stack.set("height", new_height, "erosion")
    stack.set("erosion_amount", erosion_amount_out, "erosion")
    stack.set("deposition_amount", deposition_amount_out, "erosion")
    stack.set("wetness", wetness_out, "erosion")
    stack.set("drainage", drainage_out, "erosion")
    stack.set("bank_instability", bank_instability_out, "erosion")
    stack.set("talus", talus_out, "erosion")

    return PassResult(
        pass_name="erosion",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=(
            "erosion_amount",
            "deposition_amount",
            "wetness",
            "drainage",
            "bank_instability",
            "talus",
        ),
        metrics={
            "profile": profile,
            "hydraulic_iterations": profile_params["iterations"],
            "thermal_iterations": 6,
            "total_erosion": float(erosion_amount_out.sum()),
            "total_deposition": float(deposition_amount_out.sum()),
            "total_talus": float(talus_out.sum()),
            "protected_cells": int(protected.sum()),
            "region_scoped": region is not None,
        },
    )


def pass_validation_minimal(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Pass 4: emit a minimal validation report over the mask stack.

    Checks:
      - height channel is finite everywhere
      - slope channel exists
      - no NaN/inf in any populated channel
    Any violation downgrades status to "failed".
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: list[ValidationIssue] = []

    if not np.all(np.isfinite(stack.height)):
        issues.append(
            ValidationIssue(
                code="HEIGHT_NONFINITE",
                severity="hard",
                message="height channel contains NaN or inf",
            )
        )

    for ch in ("slope", "curvature", "wetness", "drainage"):
        arr = stack.get(ch)
        if arr is None:
            continue
        arr_np = np.asarray(arr)
        if arr_np.size == 0:
            continue
        if not np.all(np.isfinite(arr_np)):
            issues.append(
                ValidationIssue(
                    code=f"{ch.upper()}_NONFINITE",
                    severity="hard",
                    message=f"{ch} channel contains NaN or inf",
                )
            )

    status = "failed" if any(i.is_hard() for i in issues) else "ok"

    return PassResult(
        pass_name="validation_minimal",
        status=status,
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height", "slope"),
        issues=issues,
        metrics={
            "populated_channels": sorted(stack.populated_by_pass.keys()),
            "hard_issues": sum(1 for i in issues if i.is_hard()),
        },
    )
