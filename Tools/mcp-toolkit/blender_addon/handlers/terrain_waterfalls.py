"""Bundle C — Waterfall Hydrology Chain.

Builds waterfall hydrologic chains from terrain heightmaps + drainage:
    source → lip → plunge path → impact pool → outflow → mist/foam/wet rock

This module is pure numpy. Blender geometry construction happens later in
a separate bundle — here we only solve the chain topology and populate
mask-stack channels (``waterfall_lip_candidate``, ``foam``, ``mist``,
``wet_rock``).

Rules honored (see TERRAIN_AGENT_PROTOCOL.md):
    - Z-up, world-meter heights
    - All signals written to TerrainMaskStack
    - Deterministic via derive_pass_seed
    - Passes register via register_bundle_c_passes(); Bundle A defaults untouched
    - No bpy / bmesh imports
"""

from __future__ import annotations

import logging
import math
import time

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field  # noqa: E402
from typing import Any, List, Optional, Tuple  # noqa: E402

import numpy as np  # noqa: E402

from .terrain_semantics import (  # noqa: E402
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# D8 neighborhood (row, col) — matches _water_network convention
# N, NE, E, SE, S, SW, W, NW
# ---------------------------------------------------------------------------
_D8_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
)
_SQRT2 = math.sqrt(2.0)
_D8_DISTANCES: Tuple[float, ...] = (
    1.0, _SQRT2, 1.0, _SQRT2, 1.0, _SQRT2, 1.0, _SQRT2,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LipCandidate:
    """A candidate waterfall-lip cell in world space."""

    world_position: Tuple[float, float, float]
    upstream_drainage: float
    downstream_drop_m: float
    flow_direction_rad: float
    confidence_score: float
    grid_rc: Optional[Tuple[int, int]] = None


@dataclass
class ImpactPool:
    """Plunge-pool produced at the base of a waterfall drop."""

    world_position: Tuple[float, float, float]
    radius_m: float
    max_depth_m: float
    outflow_direction_rad: float


@dataclass
class WaterfallChain:
    """Full solved hydrologic chain: lip → plunge → pool → outflow."""

    chain_id: str
    lip: LipCandidate
    plunge_path: Tuple[Tuple[float, float, float], ...]
    pool: ImpactPool
    outflow: Tuple[Tuple[float, float, float], ...]
    mist_radius_m: float
    foam_intensity: float
    total_drop_m: float
    drop_segments: Tuple[float, ...] = field(default_factory=tuple)


@dataclass
class WaterfallVolumetricProfile:
    """Volumetric mesh spec for a waterfall sheet.

    Waterfalls MUST be 3D volumetric meshes (thick tapered prism, rounded front),
    never flat planes. This profile defines the cross-section geometry.
    """

    thickness_top_m: float = 0.3
    thickness_bottom_m: float = 0.8
    front_curvature_segments: int = 6
    min_verts_per_meter: int = 48
    taper_exponent: float = 1.4
    spray_offset_m: float = 0.15


# ---------------------------------------------------------------------------
# Helper math
# ---------------------------------------------------------------------------


def _grid_to_world(
    stack: TerrainMaskStack, row: int, col: int,
) -> Tuple[float, float, float]:
    wx = float(stack.world_origin_x) + (col + 0.5) * float(stack.cell_size)
    wy = float(stack.world_origin_y) + (row + 0.5) * float(stack.cell_size)
    wz = float(stack.height[row, col])
    return wx, wy, wz


def _world_to_grid(
    stack: TerrainMaskStack, x: float, y: float,
) -> Tuple[int, int]:
    c = int((x - float(stack.world_origin_x)) / float(stack.cell_size))
    r = int((y - float(stack.world_origin_y)) / float(stack.cell_size))
    rows, cols = stack.height.shape
    r = max(0, min(rows - 1, r))
    c = max(0, min(cols - 1, c))
    return r, c


def _steepest_descent_step(
    height: np.ndarray, r: int, c: int,
) -> Optional[Tuple[int, int, int]]:
    """Return ((next_r, next_c, d8_index)) of the steepest-descent neighbor.

    Returns None if ``(r, c)`` is a pit (no lower neighbor).
    """
    rows, cols = height.shape
    h0 = height[r, c]
    best_drop = 0.0
    best_idx = -1
    best_next = None
    for d, ((dr, dc), dist) in enumerate(zip(_D8_OFFSETS, _D8_DISTANCES)):
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols):
            continue
        drop = (h0 - height[nr, nc]) / dist
        if drop > best_drop:
            best_drop = drop
            best_idx = d
            best_next = (nr, nc)
    if best_next is None:
        return None
    nr, nc = best_next
    return nr, nc, best_idx


def _d8_to_angle(d8_index: int) -> float:
    """Convert D8 index to a flow angle in radians (world-space)."""
    dr, dc = _D8_OFFSETS[d8_index]
    # dc is +x east, dr is +y north in world coords — tile grid row increases
    # with world_y here (origin at bottom). Use atan2(dy, dx).
    return math.atan2(float(dr), float(dc))


# ---------------------------------------------------------------------------
# Lip detection
# ---------------------------------------------------------------------------


def _ensure_drainage(stack: TerrainMaskStack) -> np.ndarray:
    """Return an unconditional drainage array (fallback if stack has none).

    If the stack does not yet have ``drainage`` populated, we compute a
    simple proxy: accumulated inverse-slope weighted count per D8 descent.
    This keeps Bundle C usable before the erosion pass runs.
    """
    drainage = stack.drainage
    if drainage is not None:
        return np.asarray(drainage, dtype=np.float64)
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    acc = np.ones_like(h, dtype=np.float64)
    order = np.argsort(-h, axis=None)
    for flat_idx in order:
        r, c = divmod(int(flat_idx), cols)
        step = _steepest_descent_step(h, r, c)
        if step is None:
            continue
        nr, nc, _ = step
        acc[nr, nc] += acc[r, c]
    return acc


def detect_waterfall_lip_candidates(
    stack: TerrainMaskStack,
    min_drainage: float = 500.0,
    min_drop_m: float = 4.0,
) -> List[LipCandidate]:
    """Scan the mask stack for cells with high drainage + steep downstream drop.

    A lip candidate is a cell whose D8 descent has a drop >= ``min_drop_m``
    AND whose upstream drainage >= ``min_drainage``. Each returned lip
    stores its world position, confidence, and flow direction.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    drainage = _ensure_drainage(stack)
    rows, cols = h.shape
    if rows < 3 or cols < 3:
        return []

    _cs = float(stack.cell_size)

    candidates: List[LipCandidate] = []
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            if drainage[r, c] < min_drainage:
                continue
            step = _steepest_descent_step(h, r, c)
            if step is None:
                continue
            nr, nc, d8 = step
            drop = float(h[r, c] - h[nr, nc])
            # Scale drop to world meters (height is already world-m, cell step is cs)
            if drop < min_drop_m:
                continue
            wx, wy, wz = _grid_to_world(stack, r, c)
            angle = _d8_to_angle(d8)
            # Confidence = normalized combination of drop + drainage
            drainage_score = min(1.0, float(drainage[r, c]) / (max(min_drainage, 1.0) * 4.0))
            drop_score = min(1.0, drop / (max(min_drop_m, 0.1) * 4.0))
            confidence = 0.5 * drainage_score + 0.5 * drop_score
            candidates.append(
                LipCandidate(
                    world_position=(wx, wy, wz),
                    upstream_drainage=float(drainage[r, c]),
                    downstream_drop_m=drop,
                    flow_direction_rad=angle,
                    confidence_score=float(confidence),
                    grid_rc=(r, c),
                )
            )

    # Deduplicate: if two candidates are immediate D8 neighbors keep the one
    # with the higher confidence score — avoids stacking detections along a
    # single drop's lip row.
    candidates.sort(key=lambda lc: lc.confidence_score, reverse=True)
    kept: List[LipCandidate] = []
    claimed: set[Tuple[int, int]] = set()
    for lc in candidates:
        if lc.grid_rc is None:
            kept.append(lc)
            continue
        r, c = lc.grid_rc
        if any((r + dr, c + dc) in claimed for dr, dc in _D8_OFFSETS + ((0, 0),)):
            continue
        kept.append(lc)
        claimed.add((r, c))
    return kept


# ---------------------------------------------------------------------------
# Waterfall solver
# ---------------------------------------------------------------------------


def solve_waterfall_from_river(
    stack: TerrainMaskStack,
    lip: LipCandidate,
    river_network: Optional[Any] = None,
) -> WaterfallChain:
    """Solve a full waterfall chain from a lip candidate downward.

    Steps:
        1. Trace plunge path: steepest descent until slope plateaus.
        2. Mark pool center at the plunge-path bottom.
        3. Compute pool radius from accumulated drop + drainage.
        4. Trace outflow via steepest descent out of the pool.
        5. Record multi-tier drop segments if the chain has sub-plateaus.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    if lip.grid_rc is None:
        r, c = _world_to_grid(stack, lip.world_position[0], lip.world_position[1])
    else:
        r, c = lip.grid_rc

    plunge_path: List[Tuple[float, float, float]] = []
    drop_segments: List[float] = []
    segment_start_z = float(h[r, c])
    plunge_path.append(_grid_to_world(stack, r, c))

    # Trace plunge path while drop-per-step is steep (> half lip drop).
    steep_threshold = max(1.0, lip.downstream_drop_m * 0.5)
    cur_r, cur_c = r, c
    last_drop = lip.downstream_drop_m
    max_iter = max(rows, cols) * 2
    iters = 0
    plateau_hits = 0
    while iters < max_iter:
        iters += 1
        step = _steepest_descent_step(h, cur_r, cur_c)
        if step is None:
            break
        nr, nc, _ = step
        drop = float(h[cur_r, cur_c] - h[nr, nc])
        if drop < 0.5:
            plateau_hits += 1
            if plateau_hits >= 2:
                # Plateau — close current segment
                seg = segment_start_z - float(h[cur_r, cur_c])
                if seg > 0.1:
                    drop_segments.append(seg)
                break
        else:
            plateau_hits = 0

        if drop < steep_threshold * 0.3 and last_drop >= steep_threshold:
            # Sub-plateau between tiers
            seg = segment_start_z - float(h[cur_r, cur_c])
            if seg > 0.1:
                drop_segments.append(seg)
            segment_start_z = float(h[cur_r, cur_c])

        cur_r, cur_c = nr, nc
        plunge_path.append(_grid_to_world(stack, cur_r, cur_c))
        last_drop = drop

        # Stop if we've descended far enough past the lip
        if (lip.world_position[2] - float(h[cur_r, cur_c])) >= lip.downstream_drop_m * 3.0:
            seg = segment_start_z - float(h[cur_r, cur_c])
            if seg > 0.1:
                drop_segments.append(seg)
            break

    if not drop_segments:
        total = max(0.0, lip.world_position[2] - float(h[cur_r, cur_c]))
        drop_segments.append(max(total, lip.downstream_drop_m))
    total_drop = float(sum(drop_segments))

    # Pool at the end of plunge path
    pool_r, pool_c = cur_r, cur_c
    pool_world = _grid_to_world(stack, pool_r, pool_c)
    pool_radius = max(3.0, min(20.0, math.sqrt(max(total_drop, 1.0)) * 2.5))
    pool_depth = max(1.0, min(8.0, total_drop * 0.35))

    # Outflow: trace out of the pool along steepest descent, up to 16 cells
    outflow: List[Tuple[float, float, float]] = [pool_world]
    or_r, or_c = pool_r, pool_c
    outflow_angle = 0.0
    for _ in range(32):
        step = _steepest_descent_step(h, or_r, or_c)
        if step is None:
            break
        nr, nc, d8 = step
        drop = float(h[or_r, or_c] - h[nr, nc])
        if drop < 0.01:
            break
        or_r, or_c = nr, nc
        outflow.append(_grid_to_world(stack, or_r, or_c))
        outflow_angle = _d8_to_angle(d8)

    if len(outflow) < 2:
        # Synthesize a minimal outflow 1 cell downslope in the lip direction
        dx = math.cos(lip.flow_direction_rad) * cs
        dy = math.sin(lip.flow_direction_rad) * cs
        outflow.append(
            (
                pool_world[0] + dx,
                pool_world[1] + dy,
                pool_world[2] - 0.5,
            )
        )
        outflow_angle = lip.flow_direction_rad

    pool = ImpactPool(
        world_position=pool_world,
        radius_m=float(pool_radius),
        max_depth_m=float(pool_depth),
        outflow_direction_rad=float(outflow_angle),
    )

    mist_radius = max(pool_radius * 2.0, total_drop * 1.2)
    foam_intensity = min(1.0, total_drop / 30.0 + 0.3)

    chain_id = f"wf_{int(lip.world_position[0] * 100)}_{int(lip.world_position[1] * 100)}"

    return WaterfallChain(
        chain_id=chain_id,
        lip=lip,
        plunge_path=tuple(plunge_path),
        pool=pool,
        outflow=tuple(outflow),
        mist_radius_m=float(mist_radius),
        foam_intensity=float(foam_intensity),
        total_drop_m=total_drop,
        drop_segments=tuple(drop_segments),
    )


# ---------------------------------------------------------------------------
# Carving + channel writes
# ---------------------------------------------------------------------------


def carve_impact_pool(
    stack: TerrainMaskStack,
    chain: WaterfallChain,
) -> np.ndarray:
    """Return a HEIGHT DELTA mask (NOT applied) for carving the plunge pool.

    Negative values = lower terrain. Caller applies delta with region-scope
    and protected-zone policy.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    delta = np.zeros_like(h, dtype=np.float64)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    pool_r, pool_c = _world_to_grid(
        stack, chain.pool.world_position[0], chain.pool.world_position[1]
    )
    radius_cells = max(1, int(math.ceil(chain.pool.radius_m / cs)))
    depth = float(chain.pool.max_depth_m)

    r0 = max(0, pool_r - radius_cells)
    r1 = min(rows, pool_r + radius_cells + 1)
    c0 = max(0, pool_c - radius_cells)
    c1 = min(cols, pool_c + radius_cells + 1)
    for rr in range(r0, r1):
        for cc in range(c0, c1):
            dr = rr - pool_r
            dc = cc - pool_c
            dist = math.sqrt(dr * dr + dc * dc) * cs
            if dist > chain.pool.radius_m:
                continue
            # Parabolic bowl: deepest at center, 0 at rim
            norm = dist / max(chain.pool.radius_m, 1e-6)
            delta[rr, cc] = -(depth * (1.0 - norm * norm))
    return delta


def build_outflow_channel(
    stack: TerrainMaskStack,
    chain: WaterfallChain,
) -> np.ndarray:
    """Return a HEIGHT DELTA mask carving a shallow outflow channel."""
    h = np.asarray(stack.height, dtype=np.float64)
    delta = np.zeros_like(h, dtype=np.float64)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    width_cells = max(1, int(math.ceil(max(1.5, chain.pool.radius_m * 0.4) / cs)))
    depth = max(0.3, chain.pool.max_depth_m * 0.25)

    for (wx, wy, _wz) in chain.outflow:
        r, c = _world_to_grid(stack, wx, wy)
        for dr in range(-width_cells, width_cells + 1):
            for dc in range(-width_cells, width_cells + 1):
                rr = r + dr
                cc = c + dc
                if not (0 <= rr < rows and 0 <= cc < cols):
                    continue
                dist = math.sqrt(dr * dr + dc * dc) * cs
                if dist > width_cells * cs:
                    continue
                norm = dist / max(width_cells * cs, 1e-6)
                carve = -depth * (1.0 - norm)
                if carve < delta[rr, cc]:
                    delta[rr, cc] = carve
    return delta


def generate_mist_zone(
    chain: WaterfallChain,
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Populate a mist field around the plunge pool. Falls off radially."""
    h = np.asarray(stack.height, dtype=np.float64)
    mist = np.zeros_like(h, dtype=np.float32)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    pool_r, pool_c = _world_to_grid(
        stack, chain.pool.world_position[0], chain.pool.world_position[1]
    )
    radius_cells = max(1, int(math.ceil(chain.mist_radius_m / cs)))
    r0 = max(0, pool_r - radius_cells)
    r1 = min(rows, pool_r + radius_cells + 1)
    c0 = max(0, pool_c - radius_cells)
    c1 = min(cols, pool_c + radius_cells + 1)
    for rr in range(r0, r1):
        for cc in range(c0, c1):
            dr = rr - pool_r
            dc = cc - pool_c
            dist = math.sqrt(dr * dr + dc * dc) * cs
            if dist > chain.mist_radius_m:
                continue
            norm = dist / max(chain.mist_radius_m, 1e-6)
            val = float(max(0.0, 1.0 - norm))
            if val > mist[rr, cc]:
                mist[rr, cc] = val
    return mist


def generate_foam_mask(
    chain: WaterfallChain,
    stack: TerrainMaskStack,
) -> np.ndarray:
    """Populate foam intensity around plunge-pool impact + plunge path."""
    h = np.asarray(stack.height, dtype=np.float64)
    foam = np.zeros_like(h, dtype=np.float32)
    rows, cols = h.shape
    cs = float(stack.cell_size)

    # Foam peaks at pool center
    pool_r, pool_c = _world_to_grid(
        stack, chain.pool.world_position[0], chain.pool.world_position[1]
    )
    radius_cells = max(1, int(math.ceil(chain.pool.radius_m / cs)))
    r0 = max(0, pool_r - radius_cells)
    r1 = min(rows, pool_r + radius_cells + 1)
    c0 = max(0, pool_c - radius_cells)
    c1 = min(cols, pool_c + radius_cells + 1)
    for rr in range(r0, r1):
        for cc in range(c0, c1):
            dr = rr - pool_r
            dc = cc - pool_c
            dist = math.sqrt(dr * dr + dc * dc) * cs
            if dist > chain.pool.radius_m:
                continue
            norm = dist / max(chain.pool.radius_m, 1e-6)
            val = float(chain.foam_intensity * max(0.0, 1.0 - norm))
            if val > foam[rr, cc]:
                foam[rr, cc] = val
    return foam


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_waterfall_system(
    chains: List[WaterfallChain],
) -> List[ValidationIssue]:
    """Ensure each chain has lip, plunge_path, pool, outflow."""
    issues: List[ValidationIssue] = []
    for i, c in enumerate(chains):
        tag = c.chain_id or f"chain_{i}"
        if c.lip is None:
            issues.append(ValidationIssue(
                code="WATERFALL_NO_LIP", severity="hard",
                affected_feature=tag, message="chain missing lip",
            ))
        if not c.plunge_path or len(c.plunge_path) < 2:
            issues.append(ValidationIssue(
                code="WATERFALL_NO_PLUNGE", severity="hard",
                affected_feature=tag, message="chain missing plunge path",
            ))
        if c.pool is None or c.pool.radius_m <= 0.0:
            issues.append(ValidationIssue(
                code="WATERFALL_NO_POOL", severity="hard",
                affected_feature=tag, message="chain missing pool",
            ))
        if not c.outflow or len(c.outflow) < 2:
            issues.append(ValidationIssue(
                code="WATERFALL_NO_OUTFLOW", severity="hard",
                affected_feature=tag, message="chain missing outflow",
            ))
        if c.lip is not None and c.pool is not None:
            if c.lip.world_position[2] <= c.pool.world_position[2]:
                issues.append(ValidationIssue(
                    code="WATERFALL_INVERTED", severity="hard",
                    affected_feature=tag,
                    message="lip not above pool",
                ))
    return issues


def validate_waterfall_volumetric(
    chain: WaterfallChain,
    profile: Optional[WaterfallVolumetricProfile] = None,
) -> List[ValidationIssue]:
    """Validate that a waterfall chain meets volumetric mesh requirements."""
    if profile is None:
        profile = WaterfallVolumetricProfile()
    issues: List[ValidationIssue] = []

    tag = chain.chain_id or "unknown_chain"

    # Check vertex density: total_drop_m * min_verts_per_meter
    expected_verts = int(chain.total_drop_m * profile.min_verts_per_meter)
    if expected_verts < profile.min_verts_per_meter:
        issues.append(ValidationIssue(
            code="WATERFALL_LOW_VERT_DENSITY",
            severity="soft",
            affected_feature=tag,
            message=(
                f"Waterfall drop {chain.total_drop_m:.1f}m expects >= {expected_verts} verts "
                f"(min {profile.min_verts_per_meter}/m), chain may look flat"
            ),
        ))

    # Check thickness tapering is non-zero
    if profile.thickness_top_m <= 0 or profile.thickness_bottom_m <= 0:
        issues.append(ValidationIssue(
            code="WATERFALL_ZERO_THICKNESS",
            severity="hard",
            affected_feature=tag,
            message="Waterfall volumetric profile has zero thickness — will render as flat plane",
        ))

    # Check front curvature has enough segments for non-coplanar face
    if profile.front_curvature_segments < 3:
        issues.append(ValidationIssue(
            code="WATERFALL_COPLANAR_FRONT",
            severity="hard",
            affected_feature=tag,
            message=(
                f"front_curvature_segments={profile.front_curvature_segments} < 3, "
                "front face will be coplanar (flat)"
            ),
        ))

    return issues


# ---------------------------------------------------------------------------
# Pass function
# ---------------------------------------------------------------------------


def _region_slice(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> Tuple[slice, slice]:
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


def pass_waterfalls(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle C waterfall pass.

    Contract
    --------
    Consumes: height (drainage optional — fallback computed)
    Produces: waterfall_lip_candidate, foam, mist, wet_rock
    Respects protected zones: yes (per-cell on carves)
    Requires scene read: yes
    """
    from .terrain_pipeline import derive_pass_seed  # noqa: F401 — imported for seeding
    from ._water_network_ext import compute_wet_rock_mask

    t0 = time.perf_counter()
    stack = state.mask_stack
    h_shape = stack.height.shape
    r_slice, c_slice = _region_slice(state, region)

    derived_seed = derive_pass_seed(
        state.intent.seed, "waterfalls",
        stack.tile_x, stack.tile_y, region,
    )
    _ = np.random.default_rng(derived_seed)

    # 1. Detect lip candidates
    lips = detect_waterfall_lip_candidates(stack)

    # 2. Build lip-candidate mask
    lip_mask = np.zeros(h_shape, dtype=np.float32)
    for lc in lips:
        if lc.grid_rc is None:
            continue
        r, c = lc.grid_rc
        lip_mask[r, c] = float(lc.confidence_score)

    # 3. Solve full chain per lip candidate (cap at 16 to bound work)
    # FIX pipeline-break #1: wire water_network from state instead of None
    _water_net = getattr(state, "water_network", None)
    chains: List[WaterfallChain] = []
    for lc in lips[:16]:
        try:
            chain = solve_waterfall_from_river(stack, lc, river_network=_water_net)
        except Exception as exc:
            logger.debug("Waterfall solver failed for lip %s: %s", lc, exc)
            continue
        chains.append(chain)

    # 3b. Accumulate pool/outflow height deltas (non-destructive)
    pool_delta = np.zeros(h_shape, dtype=np.float64)
    for chain in chains:
        pool_delta += carve_impact_pool(stack, chain)
        pool_delta += build_outflow_channel(stack, chain)

    # 4. Accumulate foam + mist masks across chains
    foam = np.zeros(h_shape, dtype=np.float32)
    mist = np.zeros(h_shape, dtype=np.float32)
    for chain in chains:
        foam = np.maximum(foam, generate_foam_mask(chain, stack))
        mist = np.maximum(mist, generate_mist_zone(chain, stack))

    # 5. Wet-rock mask (uses existing water surfaces + pools)
    # FIX pipeline-break #2: wire water_network so wet-rock seeds from network nodes
    wet_rock = compute_wet_rock_mask(stack, _water_net, radius_m=3.0)
    for chain in chains:
        # add pool contribution
        pool_foam_contribution = generate_foam_mask(chain, stack)
        wet_rock = np.maximum(wet_rock, pool_foam_contribution.astype(np.float32) * 0.8)

    # 6. Region scope: zero outside the region (leave pre-existing values alone)
    if region is not None:
        scoped = np.zeros_like(foam)
        scoped[r_slice, c_slice] = foam[r_slice, c_slice]
        foam = scoped
        scoped = np.zeros_like(mist)
        scoped[r_slice, c_slice] = mist[r_slice, c_slice]
        mist = scoped
        scoped = np.zeros_like(lip_mask)
        scoped[r_slice, c_slice] = lip_mask[r_slice, c_slice]
        lip_mask = scoped
        scoped = np.zeros_like(wet_rock)
        scoped[r_slice, c_slice] = wet_rock[r_slice, c_slice]
        wet_rock = scoped
        scoped = np.zeros_like(pool_delta)
        scoped[r_slice, c_slice] = pool_delta[r_slice, c_slice]
        pool_delta = scoped

    stack.set("waterfall_pool_delta", pool_delta.astype(np.float32), "waterfalls")

    # FIX pipeline-break #5: apply pool_delta to height (carve pools into terrain)
    # Only carve where delta is negative (lowering terrain), within region scope.
    carve_mask = pool_delta < 0.0
    if np.any(carve_mask):
        stack.height = np.where(carve_mask, stack.height + pool_delta, stack.height)

    stack.set("waterfall_lip_candidate", lip_mask, "waterfalls")
    stack.set("foam", foam, "waterfalls")
    stack.set("mist", mist, "waterfalls")
    stack.set("wet_rock", wet_rock, "waterfalls")

    issues = validate_waterfall_system(chains)
    hard = [i for i in issues if i.is_hard()]
    status = "ok" if not hard else "warning"

    return PassResult(
        pass_name="waterfalls",
        status=status,
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=(
            "waterfall_lip_candidate",
            "waterfall_pool_delta",
            "foam",
            "mist",
            "wet_rock",
        ),
        metrics={
            "lip_count": len(lips),
            "chain_count": len(chains),
            "total_drop_m": float(sum(c.total_drop_m for c in chains)),
            "max_tier_count": max((len(c.drop_segments) for c in chains), default=0),
            "seed_used": int(derived_seed),
            "region_scoped": region is not None,
        },
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Pass registration
# ---------------------------------------------------------------------------


def register_bundle_c_passes() -> None:
    """Register the Bundle C waterfall pass. Call from test fixtures only."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="waterfalls",
            func=pass_waterfalls,
            requires_channels=("height",),
            produces_channels=(
                "waterfall_lip_candidate",
                "waterfall_pool_delta",
                "foam",
                "mist",
                "wet_rock",
            ),
            seed_namespace="waterfalls",
            requires_scene_read=True,
            may_modify_geometry=True,  # FIX #5: pass now applies pool_delta to height
            description="Bundle C — waterfall hydrology chain + foam/mist/wet_rock masks",
        )
    )


__all__ = [
    "LipCandidate",
    "ImpactPool",
    "WaterfallChain",
    "detect_waterfall_lip_candidates",
    "solve_waterfall_from_river",
    "carve_impact_pool",
    "build_outflow_channel",
    "generate_mist_zone",
    "generate_foam_mask",
    "validate_waterfall_system",
    "pass_waterfalls",
    "register_bundle_c_passes",
]
