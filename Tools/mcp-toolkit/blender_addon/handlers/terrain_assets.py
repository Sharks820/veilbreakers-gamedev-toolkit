"""Bundle E — Scatter Intelligence.

Context-aware asset scattering for the VeilBreakers terrain pipeline.

This module:
    - Defines ``AssetRole`` and ``AssetContextRule`` — the declarative
      contract used to describe "where can this asset live?"
    - Computes per-cell viability masks from a TerrainMaskStack via
      ``compute_viability`` (vectorised numpy, no Python loops).
    - Generates deterministic placements with Poisson-disk blue noise
      constrained to viable regions.
    - Clusters rocks around cliff bases, waterfall impact pools, and
      cave mouths — the "scatter intelligence" that lifts scatter from
      uniform noise to Witcher 3 / Horizon ZD density + intent.
    - Exposes a ``pass_scatter_intelligent`` TerrainPipelineState pass
      that wires everything into the Bundle A orchestrator.

AAA contract rules (THIS MODULE MUST SURVIVE REFACTORS):
    1. Height sampling for placements MUST read ``stack.height[row, col]``
       directly. Never call into scene-space sampling helpers — the mask
       stack is the authoritative elevation source.
    2. World coordinates are Z-UP. A placement is ``(world_x, world_y,
       world_z)`` where ``world_z`` is the elevation from the height
       channel in metres.
    3. All RNG uses ``derive_pass_seed`` so scatter is deterministic.
    4. Protected zones are honoured via the standard protected-mask
       helper on the state.
    5. ``tree_instance_points`` is written as an ``(N, 5)`` ndarray of
       ``(x, y, z, rot, prototype_id)`` — the Unity contract.

NO bpy / bmesh imports. Pure Python + numpy so Bundle E is fully unit
testable outside Blender.
"""

from __future__ import annotations

import enum
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .terrain_pipeline import TerrainPassController, derive_pass_seed
from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Asset roles
# ---------------------------------------------------------------------------


class AssetRole(enum.Enum):
    GROUND_COVER = "ground_cover"
    VEGETATION_LARGE = "vegetation_large"
    VEGETATION_SMALL = "vegetation_small"
    ROCK_CLIFF_BASE = "rock_cliff_base"
    ROCK_WATERFALL_POOL = "rock_waterfall_pool"
    ROCK_CAVE_DEBRIS = "rock_cave_debris"
    DEBRIS_SMALL = "debris_small"
    HERO_PROP = "hero_prop"
    AUDIO_SOURCE = "audio_source"


# ---------------------------------------------------------------------------
# Rule dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ViabilityFunction:
    """A named scoring function over (stack, cell_coords) → 0..1.

    Used for custom viability evaluators beyond the declarative
    ``AssetContextRule`` bounds (e.g. "proximity to waterfall lip").
    """

    name: str
    func: Callable[[TerrainMaskStack, Tuple[int, int]], float]

    def __call__(self, stack: TerrainMaskStack, cell_coords: Tuple[int, int]) -> float:
        return float(self.func(stack, cell_coords))


@dataclass(frozen=True)
class AssetContextRule:
    """Declarative constraints describing where an asset may be scattered."""

    asset_id: str
    role: AssetRole
    min_slope_rad: float = 0.0
    max_slope_rad: float = math.pi * 0.5
    min_altitude_m: float = -1.0e9
    max_altitude_m: float = 1.0e9
    wetness_min: float = 0.0
    wetness_max: float = 1.0
    required_masks: Tuple[str, ...] = ()
    forbidden_masks: Tuple[str, ...] = ()
    cluster_radius_m: float = 2.0
    exclusion_radius_m: float = 0.0


@dataclass(frozen=True)
class ClusterRule:
    """Spatial cluster descriptor for rock/debris placements near a feature."""

    cluster_center_source: str  # e.g. "cliff_base", "waterfall_pool", "cave_mouth"
    count_min: int = 3
    count_max: int = 8
    radius_m: float = 3.0
    size_falloff: float = 1.0


# ---------------------------------------------------------------------------
# Default asset catalogue
# ---------------------------------------------------------------------------


_DEFAULT_ROLE_MAP: Dict[str, AssetRole] = {
    "grass_clump": AssetRole.GROUND_COVER,
    "moss_patch": AssetRole.GROUND_COVER,
    "fern": AssetRole.GROUND_COVER,
    "oak_tree": AssetRole.VEGETATION_LARGE,
    "pine_tree": AssetRole.VEGETATION_LARGE,
    "dead_tree": AssetRole.VEGETATION_LARGE,
    "sapling": AssetRole.VEGETATION_SMALL,
    "bush": AssetRole.VEGETATION_SMALL,
    "cliff_boulder": AssetRole.ROCK_CLIFF_BASE,
    "talus_rock": AssetRole.ROCK_CLIFF_BASE,
    "waterfall_rock": AssetRole.ROCK_WATERFALL_POOL,
    "pool_pebble": AssetRole.ROCK_WATERFALL_POOL,
    "cave_rubble": AssetRole.ROCK_CAVE_DEBRIS,
    "cave_stalagmite": AssetRole.ROCK_CAVE_DEBRIS,
    "twig_debris": AssetRole.DEBRIS_SMALL,
    "bone_pile": AssetRole.DEBRIS_SMALL,
    "shrine": AssetRole.HERO_PROP,
    "monolith": AssetRole.HERO_PROP,
    "ambient_wind": AssetRole.AUDIO_SOURCE,
    "ambient_birds": AssetRole.AUDIO_SOURCE,
}


def classify_asset_role(
    asset_id: str,
    overrides: Optional[Dict[str, AssetRole]] = None,
) -> AssetRole:
    """Map an asset_id to its AssetRole. Unknown assets default to DEBRIS_SMALL."""
    if overrides and asset_id in overrides:
        return overrides[asset_id]
    if asset_id in _DEFAULT_ROLE_MAP:
        return _DEFAULT_ROLE_MAP[asset_id]
    # Heuristic fallbacks
    aid = asset_id.lower()
    if "tree" in aid:
        return AssetRole.VEGETATION_LARGE
    if "bush" in aid or "shrub" in aid or "sapling" in aid:
        return AssetRole.VEGETATION_SMALL
    if "grass" in aid or "moss" in aid or "fern" in aid:
        return AssetRole.GROUND_COVER
    if "rock" in aid or "boulder" in aid or "stone" in aid:
        return AssetRole.ROCK_CLIFF_BASE
    if "audio" in aid or "ambient" in aid or "sound" in aid:
        return AssetRole.AUDIO_SOURCE
    return AssetRole.DEBRIS_SMALL


def build_asset_context_rules() -> List[AssetContextRule]:
    """Default rule set tuned for VeilBreakers dark fantasy scatter."""
    deg = math.pi / 180.0
    return [
        # Ground cover — flat to gentle slopes, any altitude
        AssetContextRule(
            asset_id="grass_clump",
            role=AssetRole.GROUND_COVER,
            min_slope_rad=0.0,
            max_slope_rad=25.0 * deg,
            min_altitude_m=-10.0,
            max_altitude_m=1200.0,
            wetness_min=0.1,
            wetness_max=0.9,
            cluster_radius_m=0.8,
        ),
        AssetContextRule(
            asset_id="moss_patch",
            role=AssetRole.GROUND_COVER,
            min_slope_rad=0.0,
            max_slope_rad=60.0 * deg,
            wetness_min=0.5,
            wetness_max=1.0,
            cluster_radius_m=0.6,
        ),
        # Large vegetation — moderate slopes, mid altitude, not too wet
        AssetContextRule(
            asset_id="oak_tree",
            role=AssetRole.VEGETATION_LARGE,
            min_slope_rad=0.0,
            max_slope_rad=25.0 * deg,
            min_altitude_m=0.0,
            max_altitude_m=800.0,
            wetness_min=0.2,
            wetness_max=0.85,
            cluster_radius_m=4.0,
            exclusion_radius_m=2.5,
        ),
        AssetContextRule(
            asset_id="pine_tree",
            role=AssetRole.VEGETATION_LARGE,
            min_slope_rad=0.0,
            max_slope_rad=35.0 * deg,
            min_altitude_m=100.0,
            max_altitude_m=1600.0,
            wetness_min=0.15,
            wetness_max=0.8,
            cluster_radius_m=3.5,
        ),
        AssetContextRule(
            asset_id="dead_tree",
            role=AssetRole.VEGETATION_LARGE,
            min_slope_rad=0.0,
            max_slope_rad=30.0 * deg,
            wetness_min=0.0,
            wetness_max=0.4,
            cluster_radius_m=6.0,
        ),
        # Small vegetation
        AssetContextRule(
            asset_id="bush",
            role=AssetRole.VEGETATION_SMALL,
            min_slope_rad=0.0,
            max_slope_rad=40.0 * deg,
            wetness_min=0.15,
            wetness_max=0.9,
            cluster_radius_m=1.2,
        ),
        # Cliff-base rocks — require cliff_candidate adjacency
        AssetContextRule(
            asset_id="cliff_boulder",
            role=AssetRole.ROCK_CLIFF_BASE,
            min_slope_rad=0.0,
            max_slope_rad=45.0 * deg,
            required_masks=("cliff_candidate",),
            cluster_radius_m=2.0,
        ),
        AssetContextRule(
            asset_id="talus_rock",
            role=AssetRole.ROCK_CLIFF_BASE,
            min_slope_rad=20.0 * deg,
            max_slope_rad=60.0 * deg,
            required_masks=("talus",),
            cluster_radius_m=1.0,
        ),
        # Waterfall rocks
        AssetContextRule(
            asset_id="waterfall_rock",
            role=AssetRole.ROCK_WATERFALL_POOL,
            required_masks=("waterfall_lip_candidate",),
            cluster_radius_m=1.5,
        ),
        # Cave debris
        AssetContextRule(
            asset_id="cave_rubble",
            role=AssetRole.ROCK_CAVE_DEBRIS,
            required_masks=("cave_candidate",),
            cluster_radius_m=1.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Viability computation
# ---------------------------------------------------------------------------


def compute_viability(
    rule: AssetContextRule,
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Return a (H, W) float32 viability score in [0, 1] for the rule.

    Vectorised — no Python loops over cells. A cell is viable (score > 0)
    iff all declared bounds are satisfied and every ``required_masks``
    channel is > 0 and every ``forbidden_masks`` channel is 0.
    """
    height = np.asarray(stack.height, dtype=np.float32)
    if height.ndim != 2:
        raise ValueError(f"stack.height must be 2D (got {height.shape})")
    h, w = height.shape

    viable = np.ones((h, w), dtype=np.float32)

    # Altitude bounds (height channel is the authoritative elevation source)
    viable *= (height >= rule.min_altitude_m).astype(np.float32)
    viable *= (height <= rule.max_altitude_m).astype(np.float32)

    # Slope bounds
    slope = stack.get("slope")
    if slope is not None:
        slope_arr = np.asarray(slope, dtype=np.float32)
        viable *= (slope_arr >= rule.min_slope_rad).astype(np.float32)
        viable *= (slope_arr <= rule.max_slope_rad).astype(np.float32)
    else:
        # If slope required but absent, only zero-bound rules stay viable
        if rule.max_slope_rad < math.pi * 0.5 - 1e-6 or rule.min_slope_rad > 1e-6:
            viable[:] = 0.0
            return viable

    # Wetness bounds (optional channel)
    wetness = stack.get("wetness")
    if wetness is not None:
        w_arr = np.asarray(wetness, dtype=np.float32)
        viable *= (w_arr >= rule.wetness_min).astype(np.float32)
        viable *= (w_arr <= rule.wetness_max).astype(np.float32)

    # Required masks — every listed channel must be > 0
    for ch in rule.required_masks:
        arr = stack.get(ch)
        if arr is None:
            viable[:] = 0.0
            return viable
        viable *= (np.asarray(arr, dtype=np.float32) > 0.0).astype(np.float32)

    # Forbidden masks — every listed channel must be 0
    for ch in rule.forbidden_masks:
        arr = stack.get(ch)
        if arr is None:
            continue
        viable *= (np.asarray(arr, dtype=np.float32) == 0.0).astype(np.float32)

    return np.clip(viable, 0.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Poisson-disk sampling constrained to a viability mask
# ---------------------------------------------------------------------------


def _cell_to_world(
    stack: TerrainMaskStack,
    row: int,
    col: int,
) -> Tuple[float, float, float]:
    """Convert a (row, col) grid cell to world meters (x, y, z) — Z-up.

    Height is read *directly* from ``stack.height[row, col]`` per the
    Bundle E contract. Do not replace with scene-space sampling.
    """
    x = stack.world_origin_x + (col + 0.5) * stack.cell_size
    y = stack.world_origin_y + (row + 0.5) * stack.cell_size
    z = float(stack.height[row, col])
    return (float(x), float(y), z)


def _poisson_in_mask(
    viability: np.ndarray,
    cell_size_m: float,
    min_distance_m: float,
    seed: int,
    max_attempts: int = 20,
    region_mask: Optional[np.ndarray] = None,
) -> List[Tuple[int, int]]:
    """Poisson-disk sample inside the cells where ``viability > 0``.

    Returns list of (row, col) grid indices. Honors an optional boolean
    ``region_mask`` that restricts sampling to a subregion.
    """
    h, w = viability.shape
    candidates = np.argwhere(viability > 0.0)
    if candidates.size == 0 or min_distance_m <= 0:
        return []
    if region_mask is not None:
        mask = region_mask[candidates[:, 0], candidates[:, 1]]
        candidates = candidates[mask]
        if candidates.size == 0:
            return []

    rng = np.random.default_rng(seed)
    rng.shuffle(candidates)

    min_dist_sq_m = float(min_distance_m) * float(min_distance_m)
    accepted: List[Tuple[int, int]] = []
    accepted_xy: List[Tuple[float, float]] = []

    # Spatial hash grid for O(1) neighbour rejection. Neighbourhood radius
    # must cover min_distance_m — compute from ratio of min_dist to cell_sz.
    cell_sz = max(min_distance_m / math.sqrt(2), cell_size_m * 0.5)
    neigh_radius = int(math.ceil(min_distance_m / cell_sz)) + 1
    grid: Dict[Tuple[int, int], List[int]] = {}

    def _gkey(x: float, y: float) -> Tuple[int, int]:
        return (int(x / cell_sz), int(y / cell_sz))

    for rc in candidates:
        r, c = int(rc[0]), int(rc[1])
        x = (c + 0.5) * cell_size_m
        y = (r + 0.5) * cell_size_m
        gk = _gkey(x, y)
        conflict = False
        for dgx in range(-neigh_radius, neigh_radius + 1):
            for dgy in range(-neigh_radius, neigh_radius + 1):
                for idx in grid.get((gk[0] + dgx, gk[1] + dgy), ()):
                    ax, ay = accepted_xy[idx]
                    if (x - ax) ** 2 + (y - ay) ** 2 < min_dist_sq_m:
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                break
        if conflict:
            continue
        accepted.append((r, c))
        accepted_xy.append((x, y))
        grid.setdefault(gk, []).append(len(accepted_xy) - 1)

    return accepted


# ---------------------------------------------------------------------------
# Protected-zone mask helper (local copy; avoids cyclic import)
# ---------------------------------------------------------------------------


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


def _region_mask(
    stack: TerrainMaskStack,
    region: Optional[BBox],
) -> Optional[np.ndarray]:
    if region is None:
        return None
    h, w = stack.height.shape
    ys = stack.world_origin_y + (np.arange(h) + 0.5) * stack.cell_size
    xs = stack.world_origin_x + (np.arange(w) + 0.5) * stack.cell_size
    xg, yg = np.meshgrid(xs, ys)
    return (
        (xg >= region.min_x)
        & (xg <= region.max_x)
        & (yg >= region.min_y)
        & (yg <= region.max_y)
    )


# ---------------------------------------------------------------------------
# Public placement functions
# ---------------------------------------------------------------------------


def place_assets_by_zone(
    stack: TerrainMaskStack,
    intent: TerrainIntentState,
    rules: List[AssetContextRule],
    *,
    region: Optional[BBox] = None,
    protected: Optional[np.ndarray] = None,
) -> Dict[str, List[Tuple[float, float, float]]]:
    """Return asset_id → [(world_x, world_y, world_z), ...] placements.

    Deterministic: uses ``derive_pass_seed`` with each rule's asset_id as
    the seed namespace.
    """
    h, w = stack.height.shape
    results: Dict[str, List[Tuple[float, float, float]]] = {}

    reg_mask = _region_mask(stack, region)
    if protected is not None:
        # Protected cells are excluded from scatter regardless of rule
        if reg_mask is None:
            reg_mask = np.ones((h, w), dtype=bool)
        reg_mask = reg_mask & (~protected)

    for rule in rules:
        viability = compute_viability(rule, stack)
        if not np.any(viability > 0.0):
            results[rule.asset_id] = []
            continue
        seed = derive_pass_seed(
            intent.seed,
            f"scatter::{rule.asset_id}",
            stack.tile_x,
            stack.tile_y,
            region,
        )
        cells = _poisson_in_mask(
            viability=viability,
            cell_size_m=stack.cell_size,
            min_distance_m=max(rule.cluster_radius_m, stack.cell_size),
            seed=seed,
            region_mask=reg_mask,
        )
        pts: List[Tuple[float, float, float]] = [
            _cell_to_world(stack, r, c) for (r, c) in cells
        ]
        results[rule.asset_id] = pts
    return results


def _cluster_around(
    stack: TerrainMaskStack,
    center_mask: np.ndarray,
    intent: TerrainIntentState,
    *,
    namespace: str,
    min_per_center: int,
    max_per_center: int,
    radius_m: float,
    region: Optional[BBox] = None,
) -> List[Tuple[float, float, float]]:
    """Cluster rock placements around every "hot" cell in ``center_mask``.

    Hot cells are found via simple connected-component-ish thinning
    (take every cell where the mask > 0, then downsample by
    ``radius_m / cell_size`` stride).
    """
    if center_mask is None:
        return []
    h, w = stack.height.shape
    cell_size = float(stack.cell_size)
    if cell_size <= 0:
        return []

    cm = np.asarray(center_mask)
    if cm.shape != (h, w):
        return []
    hot_rows, hot_cols = np.where(cm > 0.0)
    if hot_rows.size == 0:
        return []

    reg_mask = _region_mask(stack, region)
    if reg_mask is not None:
        keep = reg_mask[hot_rows, hot_cols]
        hot_rows = hot_rows[keep]
        hot_cols = hot_cols[keep]
        if hot_rows.size == 0:
            return []

    seed = derive_pass_seed(
        intent.seed, f"cluster::{namespace}",
        stack.tile_x, stack.tile_y, region,
    )
    rng = np.random.default_rng(seed)

    # Downsample centres so clusters don't overlap wildly
    stride = max(1, int(math.ceil(radius_m / cell_size)))
    seen = set()
    centres: List[Tuple[int, int]] = []
    for r, c in zip(hot_rows.tolist(), hot_cols.tolist()):
        key = (r // stride, c // stride)
        if key in seen:
            continue
        seen.add(key)
        centres.append((r, c))

    out: List[Tuple[float, float, float]] = []
    radius_cells = max(1.0, radius_m / cell_size)
    for cr, cc in centres:
        n = int(rng.integers(min_per_center, max_per_center + 1))
        for _ in range(n):
            angle = float(rng.uniform(0.0, 2.0 * math.pi))
            dist = float(rng.uniform(0.0, radius_cells))
            dr = int(round(math.sin(angle) * dist))
            dc = int(round(math.cos(angle) * dist))
            rr = max(0, min(h - 1, cr + dr))
            cc2 = max(0, min(w - 1, cc + dc))
            out.append(_cell_to_world(stack, rr, cc2))
    return out


def cluster_rocks_for_cliffs(
    stack: TerrainMaskStack,
    cliff_candidate: np.ndarray,
    intent: TerrainIntentState,
    *,
    region: Optional[BBox] = None,
) -> List[Tuple[float, float, float]]:
    """Cluster boulders around cliff-base cells."""
    return _cluster_around(
        stack, cliff_candidate, intent,
        namespace="cliff_base",
        min_per_center=4,
        max_per_center=9,
        radius_m=3.0,
        region=region,
    )


def cluster_rocks_for_waterfalls(
    stack: TerrainMaskStack,
    waterfall_lip_candidate: np.ndarray,
    intent: TerrainIntentState,
    *,
    region: Optional[BBox] = None,
) -> List[Tuple[float, float, float]]:
    """Cluster rocks around waterfall impact pools."""
    return _cluster_around(
        stack, waterfall_lip_candidate, intent,
        namespace="waterfall_pool",
        min_per_center=5,
        max_per_center=12,
        radius_m=2.5,
        region=region,
    )


def scatter_debris_for_caves(
    stack: TerrainMaskStack,
    cave_candidate: np.ndarray,
    intent: TerrainIntentState,
    *,
    region: Optional[BBox] = None,
) -> List[Tuple[float, float, float]]:
    """Scatter rubble around cave mouths."""
    return _cluster_around(
        stack, cave_candidate, intent,
        namespace="cave_debris",
        min_per_center=3,
        max_per_center=8,
        radius_m=2.0,
        region=region,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_asset_density_and_overlap(
    placements: Dict[str, List[Tuple[float, float, float]]],
    rules: List[AssetContextRule],
    *,
    max_density_per_m2: float = 2.0,
    area_m2: Optional[float] = None,
) -> List[ValidationIssue]:
    """Check for over-dense and overlapping placements.

    - Flags any asset whose density (count / area) exceeds
      ``max_density_per_m2``.
    - Flags per-rule internal overlaps (two placements closer than
      ``cluster_radius_m``).
    """
    rule_map = {r.asset_id: r for r in rules}
    issues: List[ValidationIssue] = []

    for asset_id, pts in placements.items():
        if not pts:
            continue
        n = len(pts)
        if area_m2 is not None and area_m2 > 0:
            density = n / area_m2
            if density > max_density_per_m2:
                issues.append(
                    ValidationIssue(
                        code="SCATTER_OVERDENSE",
                        severity="soft",
                        affected_feature=asset_id,
                        message=(
                            f"{asset_id}: density {density:.3f}/m^2 > "
                            f"max {max_density_per_m2}"
                        ),
                    )
                )

        rule = rule_map.get(asset_id)
        if rule is None:
            continue
        radius = max(rule.cluster_radius_m, 1e-6)
        radius_sq = radius * radius
        arr = np.asarray(pts, dtype=np.float64)
        if arr.shape[0] < 2:
            continue
        # O(n^2) is fine — asset counts are bounded per tile
        dx = arr[:, 0:1] - arr[:, 0:1].T
        dy = arr[:, 1:2] - arr[:, 1:2].T
        dist_sq = dx * dx + dy * dy
        np.fill_diagonal(dist_sq, np.inf)
        too_close = np.argwhere(dist_sq < radius_sq)
        if too_close.size > 0:
            i, j = int(too_close[0, 0]), int(too_close[0, 1])
            issues.append(
                ValidationIssue(
                    code="SCATTER_OVERLAP",
                    severity="soft",
                    affected_feature=asset_id,
                    location=(float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2])),
                    message=(
                        f"{asset_id}: placements {i} and {j} closer than "
                        f"cluster_radius_m={radius}"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Unity-ready materialisation
# ---------------------------------------------------------------------------


_TREE_LIKE_ROLES = (
    AssetRole.VEGETATION_LARGE,
    AssetRole.VEGETATION_SMALL,
)


def _build_tree_instance_array(
    placements: Dict[str, List[Tuple[float, float, float]]],
    rules: List[AssetContextRule],
    rng: np.random.Generator,
) -> np.ndarray:
    """Flatten tree-like placements into a (N, 5) ndarray for Unity."""
    rule_map = {r.asset_id: r for r in rules}
    rows: List[Tuple[float, float, float, float, float]] = []
    proto_lookup: Dict[str, int] = {}
    for asset_id, pts in placements.items():
        rule = rule_map.get(asset_id)
        if rule is None or rule.role not in _TREE_LIKE_ROLES:
            continue
        if asset_id not in proto_lookup:
            proto_lookup[asset_id] = len(proto_lookup)
        proto_id = float(proto_lookup[asset_id])
        for (x, y, z) in pts:
            rot = float(rng.uniform(0.0, 2.0 * math.pi))
            rows.append((float(x), float(y), float(z), rot, proto_id))
    if not rows:
        return np.zeros((0, 5), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)


def _build_detail_density(
    placements: Dict[str, List[Tuple[float, float, float]]],
    rules: List[AssetContextRule],
    stack: TerrainMaskStack,
) -> Dict[str, np.ndarray]:
    """Return per-ground-cover-type (H, W) float32 density maps."""
    h, w = stack.height.shape
    rule_map = {r.asset_id: r for r in rules}
    detail: Dict[str, np.ndarray] = {}
    for asset_id, pts in placements.items():
        rule = rule_map.get(asset_id)
        if rule is None or rule.role != AssetRole.GROUND_COVER:
            continue
        arr = np.zeros((h, w), dtype=np.float32)
        for (x, y, _z) in pts:
            c = int((x - stack.world_origin_x) / stack.cell_size)
            r = int((y - stack.world_origin_y) / stack.cell_size)
            if 0 <= r < h and 0 <= c < w:
                arr[r, c] += 1.0
        detail[asset_id] = arr
    return detail


# ---------------------------------------------------------------------------
# Pass function
# ---------------------------------------------------------------------------


def pass_scatter_intelligent(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle E primary pass — context-aware scatter + clustering.

    Requires: scene_read, height channel (slope/wetness/cliff/waterfall/cave
    channels used opportunistically when present).
    Produces: ``tree_instance_points`` and ``detail_density`` on the mask
    stack. Writes the full placement dict to ``state._bundle_e_placements``
    as a side-effect for downstream consumers.
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    intent = state.intent
    rules = build_asset_context_rules()

    protected = _protected_mask(state, stack.height.shape, "scatter_intelligent")

    placements = place_assets_by_zone(
        stack, intent, rules,
        region=region,
        protected=protected,
    )

    # Cluster-add rocks/debris where hero-candidate masks exist.
    cliff_mask = stack.get("cliff_candidate")
    if cliff_mask is not None:
        placements.setdefault("cliff_boulder", [])
        placements["cliff_boulder"].extend(
            cluster_rocks_for_cliffs(stack, np.asarray(cliff_mask), intent, region=region)
        )

    wl_mask = stack.get("waterfall_lip_candidate")
    if wl_mask is not None:
        placements.setdefault("waterfall_rock", [])
        placements["waterfall_rock"].extend(
            cluster_rocks_for_waterfalls(stack, np.asarray(wl_mask), intent, region=region)
        )

    cave_mask = stack.get("cave_candidate")
    if cave_mask is not None:
        placements.setdefault("cave_rubble", [])
        placements["cave_rubble"].extend(
            scatter_debris_for_caves(stack, np.asarray(cave_mask), intent, region=region)
        )

    # Materialise Unity-ready channels
    seed = derive_pass_seed(
        intent.seed, "scatter_intelligent_rot",
        stack.tile_x, stack.tile_y, region,
    )
    rng = np.random.default_rng(seed)
    tree_points = _build_tree_instance_array(placements, rules, rng)
    detail = _build_detail_density(placements, rules, stack)

    stack.set("tree_instance_points", tree_points, "scatter_intelligent")
    # detail_density is a dict channel; set directly
    stack.detail_density = detail
    stack.populated_by_pass["detail_density"] = "scatter_intelligent"

    # Expose full placement dict as a side-effect for downstream bundles.
    # TerrainPipelineState is a mutable dataclass — setattr is fine.
    setattr(state, "_bundle_e_placements", placements)
    state.side_effects.append(
        f"scatter_intelligent: {sum(len(v) for v in placements.values())} placements "
        f"across {len(placements)} asset types"
    )

    # Validate density on the full region
    region_area = (
        (region.width * region.height) if region is not None
        else (stack.tile_size * stack.cell_size) ** 2
    )
    issues = validate_asset_density_and_overlap(
        placements, rules, area_m2=region_area,
    )

    status = "warning" if any(i.is_hard() for i in issues) else "ok"
    return PassResult(
        pass_name="scatter_intelligent",
        status=status,
        duration_seconds=time.perf_counter() - t0,
        produced_channels=("tree_instance_points",),
        consumed_channels=("height",),
        metrics={
            "num_asset_types": len(placements),
            "num_placements": int(sum(len(v) for v in placements.values())),
            "num_tree_instances": int(tree_points.shape[0]),
            "num_detail_layers": len(detail),
        },
        warnings=[i for i in issues if not i.is_hard()],
        issues=[i for i in issues if i.is_hard()],
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_bundle_e_passes() -> None:
    """Register Bundle E passes with the TerrainPassController."""
    TerrainPassController.register_pass(
        PassDefinition(
            name="scatter_intelligent",
            func=pass_scatter_intelligent,
            requires_channels=("height",),
            produces_channels=("tree_instance_points",),
            seed_namespace="scatter_intelligent",
            requires_scene_read=True,
            may_modify_geometry=False,
            may_add_geometry=True,
            supports_region_scope=True,
            description="Context-aware asset scatter with cluster intelligence.",
        )
    )


__all__ = [
    "AssetRole",
    "ViabilityFunction",
    "AssetContextRule",
    "ClusterRule",
    "classify_asset_role",
    "build_asset_context_rules",
    "compute_viability",
    "place_assets_by_zone",
    "cluster_rocks_for_cliffs",
    "cluster_rocks_for_waterfalls",
    "scatter_debris_for_caves",
    "validate_asset_density_and_overlap",
    "pass_scatter_intelligent",
    "register_bundle_e_passes",
]
