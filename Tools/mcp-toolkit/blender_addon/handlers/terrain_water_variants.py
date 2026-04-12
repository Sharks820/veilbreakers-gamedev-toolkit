"""Bundle O — Water Variants.

Adds author-intent depth for water features beyond the base river/waterfall
system: braided channels, estuaries, karst springs, perched lakes, hot
springs, wetlands, tidal zones and seasonal state transitions.

Pure numpy. No bpy imports. Follows the terrain agent protocol — every
mutation routes through a pass, every channel lands on the mask stack.

Contract summary for ``pass_water_variants``
--------------------------------------------
Consumes: ``height``, ``slope`` (optional), ``wetness`` (optional)
Produces: ``water_surface``, ``wetness``
Respects protected zones: yes (per-cell mask)
Requires scene read: yes

Seasonal mutations (``apply_seasonal_water_state``) are **in-place** on
the mask stack — the caller is responsible for checkpointing before the
call if the prior state is needed.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

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
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BraidedChannels:
    """A braided-river decomposition of a main channel."""

    channel_paths: List[np.ndarray]  # each (N, 2) float32 world-meter polyline
    main_channel_idx: int
    total_width_m: float


@dataclass
class Estuary:
    """A river-meets-sea zone with a salinity gradient."""

    mouth_pos: Tuple[float, float, float]
    width_m: float
    salinity_gradient: float  # 0 = fresh, 1 = saline


@dataclass
class KarstSpring:
    world_pos: Tuple[float, float, float]
    discharge_rate: float  # m^3/s (authoring, not simulation)
    temperature_c: float


@dataclass
class PerchedLake:
    basin_pos: Tuple[float, float, float]
    area_m2: float
    elevation_m: float
    seepage_rate: float


@dataclass
class HotSpring:
    world_pos: Tuple[float, float, float]
    temperature_c: float
    mineral_deposit_radius_m: float


@dataclass
class Wetland:
    bounds: BBox
    depth_m: float
    vegetation_density: float
    radius_m: float = 50.0
    world_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)


class SeasonalState(enum.Enum):
    DRY = "dry"
    NORMAL = "normal"
    WET = "wet"
    FROZEN = "frozen"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_polyline(path) -> np.ndarray:
    arr = np.asarray(path, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 2)
    if arr.shape[-1] < 2:
        raise ValueError("river_path must have shape (N, 2) or (N, 3)")
    return arr[:, :2].astype(np.float32)


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


# ---------------------------------------------------------------------------
# Braided channels
# ---------------------------------------------------------------------------


def generate_braided_channels(
    stack: TerrainMaskStack,
    river_path,
    count: int = 3,
    seed: int = 0,
) -> BraidedChannels:
    """Split a main channel into ``count`` braided sub-channels.

    Each sub-channel is a lateral perturbation of the main channel by a
    deterministic offset.
    """
    if count < 1:
        raise ValueError("count must be >= 1")
    main = _as_polyline(river_path)
    if main.shape[0] < 2:
        raise ValueError("river_path needs at least 2 points")
    rng = np.random.default_rng(seed)

    # Compute per-vertex tangents and left-normals.
    tangents = np.zeros_like(main)
    tangents[:-1] = main[1:] - main[:-1]
    tangents[-1] = tangents[-2]
    lengths = np.linalg.norm(tangents, axis=1, keepdims=True)
    lengths = np.where(lengths < 1e-6, 1.0, lengths)
    tangents = tangents / lengths
    normals = np.stack([-tangents[:, 1], tangents[:, 0]], axis=1)

    channel_cell = float(stack.cell_size)
    # Total braid width is a function of cell size and count.
    total_width_m = float(count) * channel_cell * 3.0

    channels: List[np.ndarray] = []
    # Symmetric offsets around the main path in the [-w, +w] range.
    for k in range(count):
        if count == 1:
            t = 0.0
        else:
            t = (k / (count - 1)) * 2.0 - 1.0  # [-1, 1]
        base_offset = t * (total_width_m * 0.5)
        wiggle = rng.standard_normal(main.shape[0]) * (channel_cell * 0.25)
        offsets = (base_offset + wiggle)[:, None] * normals
        sub = (main + offsets).astype(np.float32)
        channels.append(sub)

    # Main channel is the one closest to the original (smallest |t|).
    if count == 1:
        main_idx = 0
    else:
        ts = np.array([abs((k / (count - 1)) * 2.0 - 1.0) for k in range(count)])
        main_idx = int(np.argmin(ts))
    return BraidedChannels(
        channel_paths=channels,
        main_channel_idx=main_idx,
        total_width_m=total_width_m,
    )


# ---------------------------------------------------------------------------
# Estuary
# ---------------------------------------------------------------------------


def detect_estuary(
    stack: TerrainMaskStack,
    river_path,
    sea_level_m: float,
) -> Optional[Estuary]:
    """Identify a river-meets-sea zone.

    Walks the river path from source to mouth; the first vertex whose
    sampled height is at or below ``sea_level_m`` becomes the estuary
    mouth. Returns ``None`` if the river never reaches the sea.
    """
    path = _as_polyline(river_path)
    rows, cols = stack.height.shape
    for i in range(path.shape[0]):
        x_m, y_m = float(path[i, 0]), float(path[i, 1])
        c = int(np.floor((x_m - stack.world_origin_x) / stack.cell_size))
        r = int(np.floor((y_m - stack.world_origin_y) / stack.cell_size))
        if not (0 <= r < rows and 0 <= c < cols):
            continue
        z = float(stack.height[r, c])
        if z <= sea_level_m:
            # Width proxy: distance across the next N vertices projected
            # onto the normal of the mouth tangent. We settle for a
            # cell-size-scaled authoring value.
            width_m = float(stack.cell_size) * 6.0
            # Salinity gradient across the mouth — authored hint.
            return Estuary(
                mouth_pos=(x_m, y_m, z),
                width_m=width_m,
                salinity_gradient=1.0,
            )
    return None


# ---------------------------------------------------------------------------
# Karst springs
# ---------------------------------------------------------------------------


def detect_karst_springs(
    stack: TerrainMaskStack,
    karst_features,
) -> List[KarstSpring]:
    """Return one spring per soluble-rock karst feature.

    ``karst_features`` can be either an (H, W) boolean mask of soluble-
    rock cells, or an iterable of (x, y) world-coordinate tuples. Both
    forms are valid authoring inputs.
    """
    springs: List[KarstSpring] = []
    if karst_features is None:
        return springs

    arr = np.asarray(karst_features)
    if arr.dtype == bool or (arr.ndim == 2 and arr.shape == stack.height.shape):
        mask = arr.astype(bool)
        rs, cs = np.where(mask)
        # Sample a deterministic subset: every cell is a candidate but
        # we only emit springs at local maxima of the wetness/flow to
        # keep the density sane. Simplification: downsample by stride.
        if rs.size == 0:
            return springs
        stride = max(1, int(np.sqrt(rs.size) // 3) or 1)
        for idx in range(0, rs.size, stride):
            r, c = int(rs[idx]), int(cs[idx])
            x = stack.world_origin_x + (c + 0.5) * stack.cell_size
            y = stack.world_origin_y + (r + 0.5) * stack.cell_size
            z = float(stack.height[r, c])
            springs.append(
                KarstSpring(
                    world_pos=(float(x), float(y), z),
                    discharge_rate=0.25,
                    temperature_c=10.0,
                )
            )
        return springs

    # Iterable of points
    for pt in arr:
        x, y = float(pt[0]), float(pt[1])
        c = int(np.floor((x - stack.world_origin_x) / stack.cell_size))
        r = int(np.floor((y - stack.world_origin_y) / stack.cell_size))
        rows, cols = stack.height.shape
        if not (0 <= r < rows and 0 <= c < cols):
            continue
        z = float(stack.height[r, c])
        springs.append(
            KarstSpring(
                world_pos=(x, y, z),
                discharge_rate=0.25,
                temperature_c=10.0,
            )
        )
    return springs


# ---------------------------------------------------------------------------
# Perched lakes
# ---------------------------------------------------------------------------


def detect_perched_lakes(stack: TerrainMaskStack) -> List[PerchedLake]:
    """Find basins elevated above the regional watertable.

    A perched lake is a local height minimum (basin) whose surrounding
    ring of cells has a LOWER mean altitude — i.e. the basin is
    structurally above its surroundings. This is the signature of a
    hanging valley / perched lake bed.
    """
    h = stack.height.astype(np.float64)
    rows, cols = h.shape
    lakes: List[PerchedLake] = []
    if rows < 5 or cols < 5:
        return lakes

    # Detect 3x3 local minima.
    interior = h[1:-1, 1:-1]
    neighbors = np.stack(
        [
            h[0:-2, 0:-2],
            h[0:-2, 1:-1],
            h[0:-2, 2:],
            h[1:-1, 0:-2],
            h[1:-1, 2:],
            h[2:, 0:-2],
            h[2:, 1:-1],
            h[2:, 2:],
        ],
        axis=0,
    )
    is_min = np.all(interior <= neighbors, axis=0)

    rs, cs = np.where(is_min)
    if rs.size == 0:
        return lakes

    ring_radius = 3
    for r, c in zip(rs + 1, cs + 1):
        r0 = max(0, r - ring_radius)
        r1 = min(rows, r + ring_radius + 1)
        c0 = max(0, c - ring_radius)
        c1 = min(cols, c + ring_radius + 1)
        ring = h[r0:r1, c0:c1]
        if ring.size < 9:
            continue
        # Ring = outer border of the window (exclude the centre cell).
        mask = np.ones_like(ring, dtype=bool)
        mask[r - r0, c - c0] = False
        ring_mean = float(ring[mask].mean())
        basin_z = float(h[r, c])
        if ring_mean >= basin_z:
            # Regular valley, not perched.
            continue
        x = stack.world_origin_x + (c + 0.5) * stack.cell_size
        y = stack.world_origin_y + (r + 0.5) * stack.cell_size
        area = float(stack.cell_size * stack.cell_size)
        lakes.append(
            PerchedLake(
                basin_pos=(float(x), float(y), basin_z),
                area_m2=area,
                elevation_m=basin_z,
                seepage_rate=0.05,
            )
        )
    return lakes


# ---------------------------------------------------------------------------
# Hot springs
# ---------------------------------------------------------------------------


def detect_hot_springs(
    stack: TerrainMaskStack,
    volcanic_activity_mask: Optional[np.ndarray] = None,
) -> List[HotSpring]:
    """Place hot springs at volcanic-activity hotspots.

    ``volcanic_activity_mask`` is an (H, W) float32 mask in [0, 1].
    Springs are placed at cells above the 80th percentile of activity.
    Returns an empty list if no mask is provided.
    """
    if volcanic_activity_mask is None:
        return []
    mask = np.asarray(volcanic_activity_mask, dtype=np.float32)
    if mask.shape != stack.height.shape:
        raise ValueError(
            f"volcanic_activity_mask shape {mask.shape} != height shape {stack.height.shape}"
        )
    if mask.size == 0 or float(mask.max()) <= 0.0:
        return []
    threshold = float(np.quantile(mask, 0.8))
    # Ensure strict positivity to avoid scattering springs over a dead mask.
    threshold = max(threshold, 1e-3)
    rs, cs = np.where(mask >= threshold)
    if rs.size == 0:
        return []
    springs: List[HotSpring] = []
    # Avoid absurd density: stride-sample.
    stride = max(1, int(rs.size // 16) or 1)
    for idx in range(0, rs.size, stride):
        r, c = int(rs[idx]), int(cs[idx])
        x = stack.world_origin_x + (c + 0.5) * stack.cell_size
        y = stack.world_origin_y + (r + 0.5) * stack.cell_size
        z = float(stack.height[r, c])
        temp_c = 45.0 + 40.0 * float(mask[r, c])
        springs.append(
            HotSpring(
                world_pos=(float(x), float(y), z),
                temperature_c=float(temp_c),
                mineral_deposit_radius_m=float(stack.cell_size) * 2.0,
            )
        )
    return springs


# ---------------------------------------------------------------------------
# Wetlands
# ---------------------------------------------------------------------------


def detect_wetlands(stack: TerrainMaskStack) -> List[Wetland]:
    """Find contiguous regions of low slope + high wetness."""
    wetness = stack.get("wetness")
    if wetness is None:
        return []
    slope = stack.get("slope")
    if slope is None:
        slope = np.zeros_like(wetness)

    w = np.asarray(wetness, dtype=np.float32)
    s = np.asarray(slope, dtype=np.float32)

    w_thr = max(0.35, float(np.quantile(w, 0.7))) if w.size else 1.0
    s_thr = max(0.2, float(np.quantile(s, 0.3))) if s.size else 0.0
    candidate = (w >= w_thr) & (s <= s_thr)
    if not np.any(candidate):
        return []

    # Connected-components via a simple flood fill (8-connected).
    rows, cols = candidate.shape
    visited = np.zeros_like(candidate, dtype=bool)
    wetlands: List[Wetland] = []
    for r0 in range(rows):
        for c0 in range(cols):
            if not candidate[r0, c0] or visited[r0, c0]:
                continue
            stack_list = [(r0, c0)]
            cells: List[Tuple[int, int]] = []
            while stack_list:
                r, c = stack_list.pop()
                if (
                    r < 0
                    or r >= rows
                    or c < 0
                    or c >= cols
                    or visited[r, c]
                    or not candidate[r, c]
                ):
                    continue
                visited[r, c] = True
                cells.append((r, c))
                stack_list.extend(
                    [
                        (r - 1, c),
                        (r + 1, c),
                        (r, c - 1),
                        (r, c + 1),
                        (r - 1, c - 1),
                        (r - 1, c + 1),
                        (r + 1, c - 1),
                        (r + 1, c + 1),
                    ]
                )
            if len(cells) < 3:
                continue
            rs_arr = np.array([p[0] for p in cells])
            cs_arr = np.array([p[1] for p in cells])
            min_r, max_r = int(rs_arr.min()), int(rs_arr.max())
            min_c, max_c = int(cs_arr.min()), int(cs_arr.max())
            bounds = BBox(
                min_x=stack.world_origin_x + min_c * stack.cell_size,
                min_y=stack.world_origin_y + min_r * stack.cell_size,
                max_x=stack.world_origin_x + (max_c + 1) * stack.cell_size,
                max_y=stack.world_origin_y + (max_r + 1) * stack.cell_size,
            )
            mean_w = float(w[rs_arr, cs_arr].mean())
            wetlands.append(
                Wetland(
                    bounds=bounds,
                    depth_m=float(0.2 + 0.8 * mean_w),
                    vegetation_density=float(min(1.0, mean_w + 0.2)),
                )
            )
    return wetlands


# ---------------------------------------------------------------------------
# Seasonal water state — in-place mutation
# ---------------------------------------------------------------------------


def apply_seasonal_water_state(
    stack: TerrainMaskStack,
    state: SeasonalState,
) -> None:
    """Mutate wetness / water_surface / tidal in-place per seasonal state.

    **IMPORTANT:** This function edits ``stack`` in place. Callers that
    need to recover the prior state must checkpoint via
    ``TerrainPassController`` before invoking.
    """
    if not isinstance(state, SeasonalState):
        raise TypeError(f"state must be SeasonalState, got {type(state).__name__}")

    shape = stack.height.shape
    wetness = stack.get("wetness")
    if wetness is None:
        wetness = np.zeros(shape, dtype=np.float32)
    wetness = np.asarray(wetness, dtype=np.float32).copy()

    water_surface = stack.get("water_surface")
    if water_surface is None:
        water_surface = np.zeros(shape, dtype=np.float32)
    water_surface = np.asarray(water_surface, dtype=np.float32).copy()

    tidal = stack.get("tidal")
    if tidal is None:
        tidal = np.zeros(shape, dtype=np.float32)
    tidal = np.asarray(tidal, dtype=np.float32).copy()

    if state is SeasonalState.DRY:
        wetness *= 0.3
        water_surface *= 0.5
    elif state is SeasonalState.NORMAL:
        pass  # no-op; canonical state
    elif state is SeasonalState.WET:
        wetness = np.clip(wetness * 1.5 + 0.2, 0.0, 1.0)
        water_surface = np.clip(water_surface + 0.15, 0.0, 1.0)
    elif state is SeasonalState.FROZEN:
        # Frozen: surface water becomes ice; tidal is locked to max.
        water_surface = np.clip(water_surface + 0.1, 0.0, 1.0)
        wetness *= 0.6
        tidal[:] = 1.0

    stack.set("wetness", wetness, "water_variants_seasonal")
    stack.set("water_surface", water_surface, "water_variants_seasonal")
    stack.set("tidal", tidal, "water_variants_seasonal")


# ---------------------------------------------------------------------------
# Pass entry point
# ---------------------------------------------------------------------------


def pass_water_variants(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Populate water_surface + wetness from water-variant heuristics.

    Contract
    --------
    Consumes: height (+ optional slope / wetness)
    Produces: water_surface, wetness
    Respects protected zones: yes (per-cell mask)
    Requires scene read: yes
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: List[ValidationIssue] = []
    r_slice, c_slice = _region_slice(state, region)
    protected = _protected_mask(state, stack.height.shape, "water_variants")

    seed = derive_pass_seed(
        state.intent.seed,
        "water_variants",
        state.tile_x,
        state.tile_y,
        region,
    )
    rng = np.random.default_rng(seed)

    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape

    existing_ws = stack.get("water_surface")
    water_surface = (
        np.asarray(existing_ws, dtype=np.float32).copy()
        if existing_ws is not None
        else np.zeros(h.shape, dtype=np.float32)
    )
    existing_wet = stack.get("wetness")
    wetness = (
        np.asarray(existing_wet, dtype=np.float32).copy()
        if existing_wet is not None
        else np.zeros(h.shape, dtype=np.float32)
    )

    # Author wetness as a function of normalized depth (basins = wetter).
    region_h = h[r_slice, c_slice]
    h_min = float(region_h.min())
    h_max = float(region_h.max())
    if h_max - h_min > 1e-9:
        depth_norm = 1.0 - (region_h - h_min) / (h_max - h_min)
    else:
        depth_norm = np.zeros_like(region_h)
    jitter = rng.uniform(-0.05, 0.05, size=region_h.shape).astype(np.float32)
    authored_wetness = np.clip(depth_norm.astype(np.float32) * 0.6 + jitter, 0.0, 1.0)
    authored_ws = (authored_wetness > 0.75).astype(np.float32)

    # Merge into the output arrays, respecting protected cells.
    region_protected = protected[r_slice, c_slice]
    wetness_region = wetness[r_slice, c_slice]
    ws_region = water_surface[r_slice, c_slice]
    wetness_region = np.where(region_protected, wetness_region, authored_wetness)
    ws_region = np.where(region_protected, ws_region, authored_ws)
    wetness[r_slice, c_slice] = wetness_region
    water_surface[r_slice, c_slice] = ws_region

    stack.set("water_surface", water_surface, "water_variants")
    stack.set("wetness", wetness, "water_variants")

    return PassResult(
        pass_name="water_variants",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("water_surface", "wetness"),
        metrics={
            "wet_cells": int(np.count_nonzero(wetness > 0.3)),
            "surface_cells": int(np.count_nonzero(water_surface > 0.5)),
            "rows": rows,
            "cols": cols,
        },
        issues=issues,
        seed_used=seed,
    )


def register_water_variants_pass() -> None:
    TerrainPassController.register_pass(
        PassDefinition(
            name="water_variants",
            func=pass_water_variants,
            requires_channels=("height",),
            produces_channels=("water_surface", "wetness"),
            seed_namespace="water_variants",
            requires_scene_read=True,
            description="Bundle O — braided rivers, estuaries, karst, perched lakes, wetlands.",
        )
    )


def get_geyser_specs(
    stack: TerrainMaskStack,
    *,
    max_geysers: int = 4,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for geyser meshes at detected hot-spring sites.

    Calls ``detect_hot_springs`` to find sites, then ``generate_geyser``
    from terrain_features to produce standalone meshes for Blender placement.

    Returns a list of dicts with ``mesh_spec`` and ``world_pos`` keys.
    """
    from .terrain_features import generate_geyser

    springs = detect_hot_springs(stack)
    if not springs:
        return []

    rng = np.random.default_rng(seed)
    results = []
    for hs in springs[:max_geysers]:
        spec = generate_geyser(
            pool_radius=rng.uniform(2.0, 5.0),
            pool_depth=rng.uniform(0.3, 0.8),
            vent_height=rng.uniform(0.5, 2.0),
            mineral_rim_width=rng.uniform(0.5, 1.5),
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": hs.world_pos})
    return results


def get_swamp_specs(
    stack: TerrainMaskStack,
    *,
    max_swamps: int = 3,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for swamp terrain at detected wetland sites.

    Calls ``detect_wetlands`` to find sites, then ``generate_swamp_terrain``
    from terrain_features to produce standalone meshes for Blender placement.

    Returns a list of dicts with ``mesh_spec`` and ``world_pos`` keys.
    """
    from .terrain_features import generate_swamp_terrain

    wetlands = detect_wetlands(stack)
    if not wetlands:
        return []

    rng = np.random.default_rng(seed)
    results = []
    for wl in wetlands[:max_swamps]:
        spec = generate_swamp_terrain(
            size=wl.radius_m * 2.0,
            water_level=rng.uniform(0.2, 0.5),
            hummock_count=int(rng.integers(6, 18)),
            island_count=int(rng.integers(2, 6)),
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": wl.world_pos})
    return results


__all__ = [
    "BraidedChannels",
    "Estuary",
    "KarstSpring",
    "PerchedLake",
    "HotSpring",
    "Wetland",
    "SeasonalState",
    "generate_braided_channels",
    "detect_estuary",
    "detect_karst_springs",
    "detect_perched_lakes",
    "detect_hot_springs",
    "detect_wetlands",
    "apply_seasonal_water_state",
    "pass_water_variants",
    "register_water_variants_pass",
    "get_geyser_specs",
    "get_swamp_specs",
]
