"""Bundle O — Vegetation Depth.

Four-layer vegetation stratification (canopy / understory / shrub /
ground cover) with edge effects, disturbance patches, clearings,
fallen logs, cultivated zones and allelopathic exclusion.

Writes ``stack.detail_density`` (dict channel) — this is the Unity
contract that the ``TerrainData.SetDetailLayer`` importer reads.

Pure numpy. No bpy imports.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .terrain_pipeline import TerrainPassController, derive_pass_seed
from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Enums + dataclasses
# ---------------------------------------------------------------------------


class VegetationLayer(enum.Enum):
    CANOPY = "canopy"
    UNDERSTORY = "understory"
    SHRUB = "shrub"
    GROUND_COVER = "ground_cover"


@dataclass
class VegetationLayers:
    """Four stratified density arrays, all (H, W) float32 in [0, 1]."""

    canopy_density: np.ndarray
    understory_density: np.ndarray
    shrub_density: np.ndarray
    ground_cover_density: np.ndarray

    def as_dict(self) -> Dict[str, np.ndarray]:
        return {
            "canopy": self.canopy_density,
            "understory": self.understory_density,
            "shrub": self.shrub_density,
            "ground_cover": self.ground_cover_density,
        }


@dataclass
class DisturbancePatch:
    bounds: BBox
    kind: str  # "fire" | "windthrow" | "flood"
    age_years: float
    recovery_progress: float  # 0 = fresh, 1 = fully recovered


@dataclass
class Clearing:
    center: Tuple[float, float]
    radius_m: float
    kind: str  # "natural" | "human"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _region_slice(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> Tuple[slice, slice]:
    stack = state.mask_stack
    shape = stack.height.shape
    if region is None:
        return slice(0, shape[0]), slice(0, shape[1])
    return region.to_cell_slice(
        stack.world_origin_x,
        stack.world_origin_y,
        stack.cell_size,
        shape,
    )


def _protected_mask(
    state: TerrainPipelineState,
    shape: Tuple[int, int],
    pass_name: str,
) -> np.ndarray:
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


def _normalize(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr.astype(np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr, dtype=np.float32)
    return ((arr - lo) / (hi - lo)).astype(np.float32)


# ---------------------------------------------------------------------------
# 4-layer vegetation
# ---------------------------------------------------------------------------


def compute_vegetation_layers(
    stack: TerrainMaskStack,
    biome: str = "dark_fantasy_default",
) -> VegetationLayers:
    """Stratify vegetation into four layers driven by terrain signals.

    Drivers
    -------
    - canopy: low slope + moderate altitude + not too wet
    - understory: canopy proxy but denser in wetter + lower altitude
    - shrub: moderate slope (up to ~0.6), lower canopy areas
    - ground_cover: near-ubiquitous at low slopes, boosted by wetness

    If optional channels (slope, wetness, wind_field) are absent, they
    default to zeros — vegetation still produces a valid (but bland)
    stratification.
    """
    h = np.asarray(stack.height, dtype=np.float32)
    shape = h.shape
    slope = stack.get("slope")
    wetness = stack.get("wetness")
    wind = stack.get("wind_field")

    slope_n = _normalize(np.asarray(slope)) if slope is not None else np.zeros(shape, dtype=np.float32)
    wet_n = _normalize(np.asarray(wetness)) if wetness is not None else np.zeros(shape, dtype=np.float32)
    alt_n = _normalize(h)

    if wind is not None:
        wind_arr = np.asarray(wind, dtype=np.float32)
        if wind_arr.ndim == 3:
            wind_mag = np.linalg.norm(wind_arr, axis=-1)
        else:
            wind_mag = np.abs(wind_arr)
        wind_n = _normalize(wind_mag)
    else:
        wind_n = np.zeros(shape, dtype=np.float32)

    # Biome scalar tweaks
    biome_scale = {
        "dark_fantasy_default": (1.0, 1.0, 1.0, 1.0),
        "tundra": (0.3, 0.4, 0.6, 0.9),
        "swamp": (0.8, 1.1, 1.0, 1.2),
        "desert": (0.1, 0.2, 0.3, 0.4),
    }
    cs, us, ss, gs = biome_scale.get(biome, (1.0, 1.0, 1.0, 1.0))

    # Canopy: low slope, mid altitude, moderate wetness. Tall trees shun
    # exposed windy ridges.
    canopy = (
        (1.0 - slope_n)
        * (1.0 - np.abs(alt_n - 0.4) * 1.2).clip(0.0, 1.0)
        * (1.0 - wind_n * 0.6)
    ).clip(0.0, 1.0) * cs

    # Understory: thrives below canopy, esp. where wetter and lower.
    understory = (
        canopy * 0.7 + wet_n * 0.4 + (1.0 - alt_n) * 0.2
    ).clip(0.0, 1.0) * us

    # Shrubs: moderate slopes, transitional zones between canopy and rock.
    shrub = (
        (1.0 - np.abs(slope_n - 0.35) * 1.6).clip(0.0, 1.0)
        * (1.0 - canopy * 0.5)
    ).clip(0.0, 1.0) * ss

    # Ground cover: almost everywhere on gentle slopes, amplified by wetness.
    ground_cover = (
        ((1.0 - slope_n).clip(0.0, 1.0) * 0.7 + wet_n * 0.4)
    ).clip(0.0, 1.0) * gs

    return VegetationLayers(
        canopy_density=canopy.astype(np.float32),
        understory_density=understory.astype(np.float32),
        shrub_density=shrub.astype(np.float32),
        ground_cover_density=ground_cover.astype(np.float32),
    )


# ---------------------------------------------------------------------------
# Disturbance patches
# ---------------------------------------------------------------------------


def detect_disturbance_patches(
    stack: TerrainMaskStack,
    seed: int,
    kinds: Tuple[str, ...] = ("fire", "windthrow", "flood"),
) -> List[DisturbancePatch]:
    """Deterministically place authored disturbance patches on the tile.

    Patches are axis-aligned rectangles sized relative to the tile; the
    count per kind is scaled by the tile area. Determinism is guaranteed
    by the ``seed`` input — same seed always returns the same list.
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    rows, cols = stack.height.shape
    world_w = cols * stack.cell_size
    world_h = rows * stack.cell_size
    patches: List[DisturbancePatch] = []
    per_kind = max(1, int(np.sqrt(rows * cols) // 24) or 1)
    for kind in kinds:
        for _ in range(per_kind):
            cx = rng.uniform(
                stack.world_origin_x, stack.world_origin_x + world_w
            )
            cy = rng.uniform(
                stack.world_origin_y, stack.world_origin_y + world_h
            )
            half_w = rng.uniform(world_w * 0.03, world_w * 0.1)
            half_h = rng.uniform(world_h * 0.03, world_h * 0.1)
            bounds = BBox(
                min_x=float(max(stack.world_origin_x, cx - half_w)),
                min_y=float(max(stack.world_origin_y, cy - half_h)),
                max_x=float(min(stack.world_origin_x + world_w, cx + half_w)),
                max_y=float(min(stack.world_origin_y + world_h, cy + half_h)),
            )
            age = float(rng.uniform(0.5, 40.0))
            recovery = float(min(1.0, age / 40.0))
            patches.append(
                DisturbancePatch(
                    bounds=bounds,
                    kind=str(kind),
                    age_years=age,
                    recovery_progress=recovery,
                )
            )
    return patches


# ---------------------------------------------------------------------------
# Clearings
# ---------------------------------------------------------------------------


def place_clearings(
    stack: TerrainMaskStack,
    intent,
    count_per_km2: float = 2.0,
    seed: int = 0,
) -> List[Clearing]:
    """Poisson-disk sampled clearings; no two centers overlap.

    ``intent`` is the ``TerrainIntentState`` — used to derive the pass
    seed when ``seed`` is the default. Kinds alternate natural / human.
    """
    rows, cols = stack.height.shape
    world_w = cols * stack.cell_size
    world_h = rows * stack.cell_size
    area_km2 = (world_w * world_h) / 1_000_000.0
    target = max(1, int(round(count_per_km2 * max(area_km2, 0.001))))

    # Derive deterministic seed via pass seed helper.
    namespace = "vegetation_clearings"
    base_seed = int(seed) if seed else int(getattr(intent, "seed", 0) or 0)
    pass_seed = derive_pass_seed(
        base_seed,
        namespace,
        int(stack.tile_x),
        int(stack.tile_y),
        None,
    )
    rng = np.random.default_rng(pass_seed)

    min_radius = float(max(stack.cell_size * 3.0, 5.0))
    max_radius = float(max(min_radius * 2.0, 15.0))
    clearings: List[Clearing] = []
    attempts = 0
    max_attempts = target * 40
    while len(clearings) < target and attempts < max_attempts:
        attempts += 1
        cx = float(rng.uniform(stack.world_origin_x, stack.world_origin_x + world_w))
        cy = float(rng.uniform(stack.world_origin_y, stack.world_origin_y + world_h))
        radius = float(rng.uniform(min_radius, max_radius))
        # Poisson-disk: reject if too close to an existing clearing.
        ok = True
        for existing in clearings:
            dx = cx - existing.center[0]
            dy = cy - existing.center[1]
            dist = float(np.hypot(dx, dy))
            if dist < (radius + existing.radius_m):
                ok = False
                break
        if not ok:
            continue
        kind = "natural" if (len(clearings) % 2 == 0) else "human"
        clearings.append(Clearing(center=(cx, cy), radius_m=radius, kind=kind))
    return clearings


# ---------------------------------------------------------------------------
# Fallen logs
# ---------------------------------------------------------------------------


def place_fallen_logs(
    stack: TerrainMaskStack,
    forest_mask: np.ndarray,
    seed: int,
) -> List[Tuple[float, float, float]]:
    """Poisson-disk scatter of fallen logs restricted to forest cells.

    Returns list of (x, y, rotation_radians) tuples. Only cells inside
    ``forest_mask`` (True) are eligible.
    """
    mask = np.asarray(forest_mask, dtype=bool)
    if mask.shape != stack.height.shape:
        raise ValueError(
            f"forest_mask shape {mask.shape} != height shape {stack.height.shape}"
        )
    rs, cs = np.where(mask)
    if rs.size == 0:
        return []
    pass_seed = derive_pass_seed(
        int(seed),
        "vegetation_logs",
        int(stack.tile_x),
        int(stack.tile_y),
        None,
    )
    rng = np.random.default_rng(pass_seed)

    # Target ~1 log per 40 cells inside the forest.
    target = max(1, rs.size // 40)
    chosen: List[Tuple[float, float, float]] = []
    min_dist = float(stack.cell_size) * 2.5
    attempts = 0
    while len(chosen) < target and attempts < target * 30:
        attempts += 1
        idx = int(rng.integers(0, rs.size))
        r, c = int(rs[idx]), int(cs[idx])
        x = stack.world_origin_x + (c + 0.5) * stack.cell_size
        y = stack.world_origin_y + (r + 0.5) * stack.cell_size
        ok = True
        for ex, ey, _ in chosen:
            if np.hypot(ex - x, ey - y) < min_dist:
                ok = False
                break
        if not ok:
            continue
        rot = float(rng.uniform(0.0, 2.0 * np.pi))
        chosen.append((float(x), float(y), rot))
    return chosen


# ---------------------------------------------------------------------------
# Edge effects
# ---------------------------------------------------------------------------


def apply_edge_effects(
    vegetation: VegetationLayers,
    biome_boundary_mask: np.ndarray,
) -> VegetationLayers:
    """Denser understory/shrub near biome boundaries.

    ``biome_boundary_mask`` is a boolean (H, W) array marking cells ON
    the boundary between biomes. A distance-falloff kernel boosts
    understory density within a few cells of any boundary cell.
    """
    mask = np.asarray(biome_boundary_mask, dtype=bool)
    if mask.shape != vegetation.canopy_density.shape:
        raise ValueError("biome_boundary_mask shape must match vegetation layers")

    # Compute distance-to-boundary via iterative dilation (BFS) so we
    # don't need scipy. 4 rings is sufficient for the edge-effect range.
    rings = np.zeros_like(mask, dtype=np.int32)
    current = mask.copy()
    rings[current] = 1
    for step in range(2, 6):
        # Dilate by 1 cell (4-connected).
        shifted = np.zeros_like(current)
        shifted[1:, :] |= current[:-1, :]
        shifted[:-1, :] |= current[1:, :]
        shifted[:, 1:] |= current[:, :-1]
        shifted[:, :-1] |= current[:, 1:]
        new = shifted & (rings == 0)
        rings[new] = step
        current = shifted | current

    # boost falloff: 1.0 at ring 1 -> 0 at ring 5.
    boost = np.where(rings > 0, (6 - rings).astype(np.float32) / 5.0, 0.0)
    boost = boost.clip(0.0, 1.0)

    return VegetationLayers(
        canopy_density=vegetation.canopy_density.copy(),
        understory_density=np.clip(
            vegetation.understory_density + boost * 0.4, 0.0, 1.0
        ).astype(np.float32),
        shrub_density=np.clip(
            vegetation.shrub_density + boost * 0.3, 0.0, 1.0
        ).astype(np.float32),
        ground_cover_density=vegetation.ground_cover_density.copy(),
    )


# ---------------------------------------------------------------------------
# Cultivated zones
# ---------------------------------------------------------------------------


def apply_cultivated_zones(
    vegetation: VegetationLayers,
    cultivation_mask: np.ndarray,
) -> VegetationLayers:
    """Override natural vegetation with farmland densities."""
    mask = np.asarray(cultivation_mask, dtype=bool)
    if mask.shape != vegetation.canopy_density.shape:
        raise ValueError("cultivation_mask shape must match vegetation layers")

    canopy = vegetation.canopy_density.copy()
    understory = vegetation.understory_density.copy()
    shrub = vegetation.shrub_density.copy()
    ground = vegetation.ground_cover_density.copy()

    canopy[mask] = 0.05  # sparse hedgerow trees
    understory[mask] = 0.02
    shrub[mask] = 0.05
    ground[mask] = 1.0  # crops = dense ground layer

    return VegetationLayers(
        canopy_density=canopy,
        understory_density=understory,
        shrub_density=shrub,
        ground_cover_density=ground,
    )


# ---------------------------------------------------------------------------
# Allelopathic exclusion
# ---------------------------------------------------------------------------


def apply_allelopathic_exclusion(
    vegetation: VegetationLayers,
    species_a_mask: np.ndarray,
    species_b_mask: np.ndarray,
) -> VegetationLayers:
    """Reduce species A (canopy) density where species B is dense.

    Models allelopathy: walnut/eucalyptus suppressing understory rivals.
    """
    a = np.asarray(species_a_mask, dtype=np.float32)
    b = np.asarray(species_b_mask, dtype=np.float32)
    if a.shape != vegetation.canopy_density.shape:
        raise ValueError("species_a_mask shape mismatch")
    if b.shape != vegetation.canopy_density.shape:
        raise ValueError("species_b_mask shape mismatch")

    suppression = np.clip(b, 0.0, 1.0)
    canopy = vegetation.canopy_density * (1.0 - suppression * 0.8)
    canopy = canopy.astype(np.float32)
    return VegetationLayers(
        canopy_density=canopy,
        understory_density=vegetation.understory_density.copy(),
        shrub_density=vegetation.shrub_density.copy(),
        ground_cover_density=vegetation.ground_cover_density.copy(),
    )


# ---------------------------------------------------------------------------
# Pass entry point
# ---------------------------------------------------------------------------


def pass_vegetation_depth(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Write 4-layer vegetation density into ``stack.detail_density``.

    Contract
    --------
    Consumes: height (+ optional slope, wetness, wind_field)
    Produces: detail_density (dict with canopy/understory/shrub/ground_cover)
    Respects protected zones: yes
    Requires scene read: yes
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: List[ValidationIssue] = []
    r_slice, c_slice = _region_slice(state, region)
    protected = _protected_mask(state, stack.height.shape, "vegetation_depth")

    seed = derive_pass_seed(
        state.intent.seed,
        "vegetation_depth",
        state.tile_x,
        state.tile_y,
        region,
    )

    biome = getattr(state.intent, "biome_rules", None) or "dark_fantasy_default"
    layers = compute_vegetation_layers(stack, biome=biome)

    existing = stack.detail_density or {}
    merged: Dict[str, np.ndarray] = {k: np.asarray(v).copy() for k, v in existing.items()}

    keys = ("canopy", "understory", "shrub", "ground_cover")
    sources = (
        layers.canopy_density,
        layers.understory_density,
        layers.shrub_density,
        layers.ground_cover_density,
    )

    for key, src in zip(keys, sources):
        prev = merged.get(key)
        if prev is None or prev.shape != src.shape:
            prev = np.zeros_like(src)
        target = prev.copy()
        region_src = src[r_slice, c_slice]
        region_protected = protected[r_slice, c_slice]
        region_prev = prev[r_slice, c_slice]
        region_out = np.where(region_protected, region_prev, region_src).astype(np.float32)
        target[r_slice, c_slice] = region_out
        merged[key] = target.astype(np.float32)

    stack.detail_density = merged
    stack.populated_by_pass["detail_density"] = "vegetation_depth"

    total_density = float(
        sum(float(arr.mean()) for arr in merged.values() if arr.size)
    )

    return PassResult(
        pass_name="vegetation_depth",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("detail_density",),
        metrics={
            "layers": len(merged),
            "mean_density_sum": total_density,
            "biome": biome,
        },
        issues=issues,
        seed_used=seed,
    )


def register_vegetation_depth_pass() -> None:
    TerrainPassController.register_pass(
        PassDefinition(
            name="vegetation_depth",
            func=pass_vegetation_depth,
            requires_channels=("height",),
            produces_channels=("detail_density",),
            seed_namespace="vegetation_depth",
            requires_scene_read=True,
            description="Bundle O — 4-layer vegetation stratification.",
        )
    )


__all__ = [
    "VegetationLayer",
    "VegetationLayers",
    "DisturbancePatch",
    "Clearing",
    "compute_vegetation_layers",
    "detect_disturbance_patches",
    "place_clearings",
    "place_fallen_logs",
    "apply_edge_effects",
    "apply_cultivated_zones",
    "apply_allelopathic_exclusion",
    "pass_vegetation_depth",
    "register_vegetation_depth_pass",
]
