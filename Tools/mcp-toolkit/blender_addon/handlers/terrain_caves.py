"""Bundle F — Cave archetype analysis (pure numpy, no bpy).

Replaces the single generic semicircular-arch cave generator with five
distinct archetypes, each with its own entrance framing, path geometry,
collapse debris pattern, and damp interior mask. All analysis is pure
numpy / python so it can be tested outside Blender.

See docs/terrain_ultra_implementation_plan_2026-04-08.md §11 (Bundle F).

Agent protocol compliance:
- Rule 1: all mutation lives behind ``pass_caves`` + ``register_bundle_f_passes``
- Rule 2: pass declares ``requires_scene_read=True``
- Rule 3: every intermediate signal (``cave_candidate``, ``wet_rock``) is
  written to ``TerrainMaskStack`` via ``stack.set(...)``
- Rule 4: uses ``derive_pass_seed`` — never ``hash()`` / ``random.random()``
- Rule 5: protected zones masked per-cell before any carve
- Rule 6: Z-up world meters (``stack.height`` is world-Z in meters)
- Rule 7: ``cave_candidate`` + ``wet_rock`` are Unity-visible mask channels
- Rule 10: never ``np.clip(..., 0, 1)`` on world heights; the carve returns a
  delta array that callers add to height, but this pass does NOT mutate
  ``stack.height`` directly — it populates masks + records intent.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Archetype enum + spec
# ---------------------------------------------------------------------------


class CaveArchetype(str, Enum):
    """Five plausible cave archetypes for a dark-fantasy terrain pipeline.

    LAVA_TUBE        — long tubular corridor, low ceiling irregularity,
                       smooth floor; formed by drained basaltic flow.
    FISSURE          — narrow tall vertical crack, high ceiling irregularity,
                       debris-strewn floor; tectonic origin.
    KARST_SINKHOLE   — vertical drop + horizontal chamber at base; heavy
                       collapse debris and strong dampness from groundwater.
    GLACIAL_MELT     — meandering low arch carved by meltwater; wet floor,
                       rounded walls, cold ambient.
    SEA_GROTTO       — wide low arch carved by wave action at coast; tidal
                       damp band, boulder pile at mouth.
    """

    LAVA_TUBE = "lava_tube"
    FISSURE = "fissure"
    KARST_SINKHOLE = "karst_sinkhole"
    GLACIAL_MELT = "glacial_melt"
    SEA_GROTTO = "sea_grotto"


@dataclass
class CaveArchetypeSpec:
    """All archetype-driven parameters for a single cave instance.

    Values are in world meters; factors in 0..1.
    """

    archetype: CaveArchetype
    entrance_width_m: float
    entrance_height_m: float
    interior_length_m: float
    taper_ratio: float = 0.6
    ceiling_irregularity: float = 0.4
    floor_debris_density: float = 0.3
    damp_intensity: float = 0.5
    ambient_light_factor: float = 0.3
    # Supplementary (Gap 14, plan §1.B.6)
    occlusion_shelf_depth: float = 0.0
    sculpt_mode: bool = False


# Default archetype parameter tables (tuned for AAA readability, not generic).
_ARCHETYPE_DEFAULTS: Dict[CaveArchetype, Dict[str, float]] = {
    CaveArchetype.LAVA_TUBE: dict(
        entrance_width_m=6.0,
        entrance_height_m=3.5,
        interior_length_m=45.0,
        taper_ratio=0.85,
        ceiling_irregularity=0.2,
        floor_debris_density=0.15,
        damp_intensity=0.15,
        ambient_light_factor=0.2,
        occlusion_shelf_depth=1.5,
    ),
    CaveArchetype.FISSURE: dict(
        entrance_width_m=2.5,
        entrance_height_m=7.0,
        interior_length_m=20.0,
        taper_ratio=0.4,
        ceiling_irregularity=0.8,
        floor_debris_density=0.6,
        damp_intensity=0.35,
        ambient_light_factor=0.35,
        occlusion_shelf_depth=0.6,
    ),
    CaveArchetype.KARST_SINKHOLE: dict(
        entrance_width_m=9.0,
        entrance_height_m=12.0,
        interior_length_m=18.0,
        taper_ratio=0.5,
        ceiling_irregularity=0.7,
        floor_debris_density=0.85,
        damp_intensity=0.9,
        ambient_light_factor=0.55,
        occlusion_shelf_depth=2.5,
    ),
    CaveArchetype.GLACIAL_MELT: dict(
        entrance_width_m=5.0,
        entrance_height_m=3.0,
        interior_length_m=30.0,
        taper_ratio=0.65,
        ceiling_irregularity=0.35,
        floor_debris_density=0.2,
        damp_intensity=0.8,
        ambient_light_factor=0.5,
        occlusion_shelf_depth=1.2,
    ),
    CaveArchetype.SEA_GROTTO: dict(
        entrance_width_m=10.0,
        entrance_height_m=4.5,
        interior_length_m=22.0,
        taper_ratio=0.55,
        ceiling_irregularity=0.45,
        floor_debris_density=0.55,
        damp_intensity=0.95,
        ambient_light_factor=0.6,
        occlusion_shelf_depth=2.0,
    ),
}


def make_archetype_spec(
    archetype: CaveArchetype,
    **overrides: float,
) -> CaveArchetypeSpec:
    """Return a ``CaveArchetypeSpec`` preloaded with the archetype defaults."""
    params: Dict[str, float] = dict(_ARCHETYPE_DEFAULTS[archetype])
    params.update({k: v for k, v in overrides.items() if v is not None})
    return CaveArchetypeSpec(archetype=archetype, **params)


# ---------------------------------------------------------------------------
# Cave structure — analogous to CliffStructure in Bundle B
# ---------------------------------------------------------------------------


@dataclass
class CaveStructure:
    """A registered cave anatomy. Analogous to ``CliffStructure``."""

    cave_id: str
    archetype: CaveArchetype
    spec: CaveArchetypeSpec
    entrance_world_pos: Tuple[float, float, float]
    path_world: List[Tuple[float, float, float]] = field(default_factory=list)
    interior_mask: Optional[np.ndarray] = None
    damp_mask: Optional[np.ndarray] = None
    height_delta: Optional[np.ndarray] = None
    entrance_frame: Optional[Dict] = None
    debris_points: List[Tuple[float, float, float]] = field(default_factory=list)
    tier: str = "secondary"
    cell_count: int = 0


# ---------------------------------------------------------------------------
# Helpers — world <-> grid coordinate math
# ---------------------------------------------------------------------------


def _world_to_cell(
    stack: TerrainMaskStack, x: float, y: float
) -> Tuple[int, int]:
    """Return (row, col) for a world-space (x, y) position."""
    col = int(round((x - stack.world_origin_x) / stack.cell_size))
    row = int(round((y - stack.world_origin_y) / stack.cell_size))
    rows, cols = stack.height.shape
    col = max(0, min(cols - 1, col))
    row = max(0, min(rows - 1, row))
    return row, col


def _cell_to_world(
    stack: TerrainMaskStack, row: int, col: int
) -> Tuple[float, float]:
    x = stack.world_origin_x + (col + 0.5) * stack.cell_size
    y = stack.world_origin_y + (row + 0.5) * stack.cell_size
    return x, y


def _region_to_slice(
    stack: TerrainMaskStack, region: BBox
) -> Tuple[slice, slice]:
    return region.to_cell_slice(
        world_origin_x=stack.world_origin_x,
        world_origin_y=stack.world_origin_y,
        cell_size=stack.cell_size,
        grid_shape=stack.height.shape,
    )


def _protected_mask_for_caves(
    state: TerrainPipelineState,
    shape: Tuple[int, int],
) -> np.ndarray:
    """Per-cell mask of cells forbidden by protected zones for the 'caves' pass."""
    stack = state.mask_stack
    mask = np.zeros(shape, dtype=bool)
    if not state.intent.protected_zones:
        return mask
    rows, cols = shape
    ys = stack.world_origin_y + (np.arange(rows) + 0.5) * stack.cell_size
    xs = stack.world_origin_x + (np.arange(cols) + 0.5) * stack.cell_size
    xg, yg = np.meshgrid(xs, ys)
    for zone in state.intent.protected_zones:
        if zone.permits("caves"):
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
# Archetype selection
# ---------------------------------------------------------------------------


def pick_cave_archetype(
    stack: TerrainMaskStack,
    world_pos: Tuple[float, float, float],
    seed: int,
) -> CaveArchetype:
    """Select the most plausible archetype for a location.

    Uses (in order of priority):
      - altitude relative to heightmap range
      - slope at the sample
      - wetness (if populated)
      - basin/concavity (if populated)
      - deterministic RNG tiebreak from ``seed``

    Heuristics:
      - very wet + low altitude + basin  → SEA_GROTTO (coastal)
      - very wet + mid altitude          → GLACIAL_MELT
      - strong basin + mid altitude      → KARST_SINKHOLE
      - steep slope + dry                → FISSURE
      - mid altitude + dry + moderate    → LAVA_TUBE
    """
    x, y, _z = world_pos
    row, col = _world_to_cell(stack, x, y)

    h = float(stack.height[row, col])
    h_min = float(stack.height_min_m if stack.height_min_m is not None else stack.height.min())
    h_max = float(stack.height_max_m if stack.height_max_m is not None else stack.height.max())
    span = max(1e-6, h_max - h_min)
    altitude_norm = (h - h_min) / span  # 0..1

    def _sample(channel: str, default: float = 0.0) -> float:
        arr = stack.get(channel)
        if arr is None:
            return float(default)
        arr_np = np.asarray(arr)
        if arr_np.shape != stack.height.shape:
            return float(default)
        return float(arr_np[row, col])

    slope_rad = _sample("slope", 0.0)
    wetness = _sample("wetness", 0.0)
    basin = _sample("basin", 0.0)
    concavity = _sample("concavity", 0.0)

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    jitter = float(rng.uniform(-0.05, 0.05))

    # Score each archetype; highest score wins.
    scores: Dict[CaveArchetype, float] = {
        CaveArchetype.SEA_GROTTO: (
            (1.0 - altitude_norm) * 1.2
            + wetness * 1.5
            + (0.6 if basin > 0.1 else 0.0)
            - (0.8 if altitude_norm > 0.35 else 0.0)
        ),
        CaveArchetype.GLACIAL_MELT: (
            altitude_norm * 0.9
            + wetness * 1.1
            + (0.3 if 0.45 < altitude_norm < 0.9 else 0.0)
        ),
        CaveArchetype.KARST_SINKHOLE: (
            (basin * 1.4)
            + (concavity * 0.6)
            + (0.4 if 0.2 < altitude_norm < 0.7 else 0.0)
            - wetness * 0.3
        ),
        CaveArchetype.FISSURE: (
            slope_rad * 0.9
            + (0.5 if altitude_norm > 0.4 else 0.1)
            - wetness * 0.6
        ),
        CaveArchetype.LAVA_TUBE: (
            (0.6 if 0.25 < altitude_norm < 0.75 else 0.0)
            + (0.3 if slope_rad < math.radians(25.0) else 0.0)
            - wetness * 0.5
            - basin * 0.4
        ),
    }

    # Add a small deterministic jitter so ties resolve per-seed
    for k in list(scores.keys()):
        scores[k] += jitter * (hash(k.value) % 7) * 0.01

    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0]


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------


def generate_cave_path(
    stack: TerrainMaskStack,
    archetype: CaveArchetype,
    entrance_pos: Tuple[float, float, float],
    seed: int,
) -> List[Tuple[float, float, float]]:
    """Return a world-meter polyline for the cave interior path.

    Path shape depends on archetype:
      - LAVA_TUBE: nearly straight, gentle meander
      - FISSURE: short, mostly vertical drop then short horizontal
      - KARST_SINKHOLE: vertical plunge then a horizontal chamber arm
      - GLACIAL_MELT: strong meander
      - SEA_GROTTO: short, wide, shallow
    """
    spec = make_archetype_spec(archetype)
    length = float(spec.interior_length_m)
    x0, y0, z0 = entrance_pos

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    # Pick a heading from RNG, in [0, 2π)
    heading = float(rng.uniform(0.0, 2.0 * math.pi))
    dx = math.cos(heading)
    dy = math.sin(heading)

    # Number of samples per meter adapted to length.
    n_samples = max(6, int(round(length / 2.0)))
    points: List[Tuple[float, float, float]] = []

    if archetype == CaveArchetype.FISSURE:
        # Short horizontal run + vertical drop
        for i in range(n_samples):
            t = i / float(n_samples - 1)
            hx = x0 + dx * length * 0.4 * t
            hy = y0 + dy * length * 0.4 * t
            hz = z0 - t * spec.entrance_height_m * 0.8
            points.append((hx, hy, hz))
    elif archetype == CaveArchetype.KARST_SINKHOLE:
        # Vertical plunge first, then horizontal chamber arm
        drop = spec.entrance_height_m
        plunge_samples = max(3, n_samples // 3)
        for i in range(plunge_samples):
            t = i / float(plunge_samples - 1) if plunge_samples > 1 else 1.0
            points.append((x0, y0, z0 - drop * t))
        # Horizontal arm at the bottom of the plunge
        arm_samples = n_samples - plunge_samples
        for i in range(arm_samples):
            t = (i + 1) / float(arm_samples)
            hx = x0 + dx * length * t
            hy = y0 + dy * length * t
            points.append((hx, hy, z0 - drop))
    elif archetype == CaveArchetype.GLACIAL_MELT:
        # Meander: perpendicular sinusoidal offset
        perp_x = -dy
        perp_y = dx
        for i in range(n_samples):
            t = i / float(n_samples - 1)
            offset = math.sin(t * math.pi * 2.0) * length * 0.12
            hx = x0 + dx * length * t + perp_x * offset
            hy = y0 + dy * length * t + perp_y * offset
            hz = z0 - t * spec.entrance_height_m * 0.3
            points.append((hx, hy, hz))
    elif archetype == CaveArchetype.SEA_GROTTO:
        # Short, shallow, slight meander
        perp_x = -dy
        perp_y = dx
        for i in range(n_samples):
            t = i / float(n_samples - 1)
            offset = math.sin(t * math.pi) * length * 0.08
            hx = x0 + dx * length * t + perp_x * offset
            hy = y0 + dy * length * t + perp_y * offset
            hz = z0 - t * spec.entrance_height_m * 0.15
            points.append((hx, hy, hz))
    else:  # LAVA_TUBE (and default)
        perp_x = -dy
        perp_y = dx
        for i in range(n_samples):
            t = i / float(n_samples - 1)
            offset = math.sin(t * math.pi * 1.5) * length * 0.05
            hx = x0 + dx * length * t + perp_x * offset
            hy = y0 + dy * length * t + perp_y * offset
            hz = z0 - t * spec.entrance_height_m * 0.1
            points.append((hx, hy, hz))

    return points


# ---------------------------------------------------------------------------
# Volume carving (delta, not mutation)
# ---------------------------------------------------------------------------


def carve_cave_volume(
    stack: TerrainMaskStack,
    path: List[Tuple[float, float, float]],
    spec: CaveArchetypeSpec,
) -> np.ndarray:
    """Return a negative height delta + populate ``stack.cave_candidate``.

    The delta is a ``(H, W)`` float64 array of non-positive values to be
    ADDED to the heightmap by a downstream geometry pass. We intentionally
    DO NOT mutate ``stack.height`` — Rule 10 on world-meter heights is
    honored and the pipeline keeps non-destructive editing.

    The cave_candidate mask on the stack is updated in-place (OR-ed) with
    the cells covered by the carve footprint.
    """
    height = np.asarray(stack.height, dtype=np.float64)
    rows, cols = height.shape
    delta = np.zeros_like(height, dtype=np.float64)

    if not path:
        return delta

    # Cave footprint radius in cells = half entrance width
    radius_m = max(1.0, float(spec.entrance_width_m) * 0.5)
    depth_m = max(0.5, float(spec.entrance_height_m))
    cell = max(1e-6, float(stack.cell_size))
    radius_cells = max(1, int(math.ceil(radius_m / cell)))

    # Existing mask starts from whatever is on the stack
    existing = stack.get("cave_candidate")
    if existing is not None and np.asarray(existing).shape == height.shape:
        interior_mask = np.asarray(existing, dtype=bool).copy()
    else:
        interior_mask = np.zeros((rows, cols), dtype=bool)

    rr_grid, cc_grid = np.mgrid[0:rows, 0:cols]

    for (wx, wy, _wz) in path:
        row, col = _world_to_cell(stack, wx, wy)
        dr = rr_grid - row
        dc = cc_grid - col
        dist2 = dr * dr + dc * dc
        radius2 = radius_cells * radius_cells
        footprint = dist2 <= radius2
        if not footprint.any():
            continue
        interior_mask |= footprint
        # Taper depth by distance from the path centre (sqrt makes it smooth)
        dist_norm = np.sqrt(dist2) / max(1.0, float(radius_cells))
        taper = np.maximum(0.0, 1.0 - dist_norm) * float(spec.taper_ratio)
        local_delta = -(taper * depth_m)
        # Keep the deepest (most negative) delta per cell
        delta = np.where(footprint & (local_delta < delta), local_delta, delta)

    stack.set("cave_candidate", interior_mask.astype(bool), "caves")
    return delta


# ---------------------------------------------------------------------------
# Entrance framing
# ---------------------------------------------------------------------------


def build_cave_entrance_frame(
    stack: TerrainMaskStack,
    entrance_pos: Tuple[float, float, float],
    spec: CaveArchetypeSpec,
) -> Dict:
    """Return entrance metadata describing the visual framing.

    Metadata includes:
      - two or three framing rocks (left, right, optional lintel)
      - lip_height: meters above entrance floor
      - vegetation_screen: bool — whether to scatter vines/moss
      - occlusion_shelf: overhead shadow-shelf geometry intent
    """
    x, y, z = entrance_pos
    half_w = spec.entrance_width_m * 0.5
    framing_count = 2
    if spec.archetype in (
        CaveArchetype.LAVA_TUBE,
        CaveArchetype.KARST_SINKHOLE,
        CaveArchetype.SEA_GROTTO,
    ):
        framing_count = 3  # left + right + lintel

    framing_rocks: List[Dict] = [
        {
            "role": "left_jamb",
            "world_pos": (x - half_w, y, z),
            "radius_m": max(0.6, half_w * 0.5),
        },
        {
            "role": "right_jamb",
            "world_pos": (x + half_w, y, z),
            "radius_m": max(0.6, half_w * 0.5),
        },
    ]
    if framing_count >= 3:
        framing_rocks.append(
            {
                "role": "lintel",
                "world_pos": (x, y, z + spec.entrance_height_m * 0.9),
                "radius_m": max(0.5, spec.entrance_width_m * 0.4),
            }
        )

    vegetation_screen = spec.damp_intensity > 0.4 and spec.archetype not in (
        CaveArchetype.FISSURE,
    )

    return {
        "archetype": spec.archetype.value,
        "world_pos": (x, y, z),
        "lip_height_m": float(spec.entrance_height_m),
        "lip_width_m": float(spec.entrance_width_m),
        "framing_rocks": framing_rocks,
        "framing_count": framing_count,
        "vegetation_screen": bool(vegetation_screen),
        "occlusion_shelf": {
            "depth_m": float(spec.occlusion_shelf_depth),
            "width_m": float(spec.entrance_width_m * 1.2),
            "above_entrance_m": float(spec.entrance_height_m * 0.9),
        },
    }


# ---------------------------------------------------------------------------
# Debris scatter
# ---------------------------------------------------------------------------


def scatter_collapse_debris(
    stack: TerrainMaskStack,
    path: List[Tuple[float, float, float]],
    spec: CaveArchetypeSpec,
    seed: int,
) -> List[Tuple[float, float, float]]:
    """Return a deterministic list of debris positions along the path.

    Uses ``derive_pass_seed``-style integer seed (supplied by the caller).
    Debris count scales with ``floor_debris_density * interior_length_m``.
    """
    from .terrain_pipeline import derive_pass_seed  # lazy to avoid cycles

    if not path:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    count = int(round(spec.floor_debris_density * spec.interior_length_m * 0.8))
    count = max(0, min(200, count))
    if count == 0:
        return []

    points: List[Tuple[float, float, float]] = []
    path_arr = np.asarray(path, dtype=np.float64)
    n_path = path_arr.shape[0]

    for _ in range(count):
        # Pick a random path segment
        idx = int(rng.integers(0, max(1, n_path - 1)))
        t = float(rng.uniform(0.0, 1.0))
        p0 = path_arr[idx]
        p1 = path_arr[min(n_path - 1, idx + 1)]
        base = p0 + (p1 - p0) * t
        # Lateral jitter within entrance_width
        jitter = rng.normal(0.0, spec.entrance_width_m * 0.35, size=2)
        points.append(
            (
                float(base[0] + jitter[0]),
                float(base[1] + jitter[1]),
                float(base[2]),
            )
        )

    return points


# ---------------------------------------------------------------------------
# Damp mask
# ---------------------------------------------------------------------------


def generate_damp_mask(
    stack: TerrainMaskStack,
    path: List[Tuple[float, float, float]],
    spec: CaveArchetypeSpec,
) -> np.ndarray:
    """Populate ``stack.wet_rock`` around the cave interior and return it.

    The damp field is a radial falloff around every path sample, scaled
    by ``spec.damp_intensity``. Existing ``wet_rock`` values on the stack
    are combined (max-merged) so multiple caves in one tile coexist.
    """
    height = np.asarray(stack.height, dtype=np.float64)
    rows, cols = height.shape
    damp = np.zeros((rows, cols), dtype=np.float32)

    if not path:
        return damp

    cell = max(1e-6, float(stack.cell_size))
    radius_m = max(2.0, float(spec.entrance_width_m) * 1.8)
    radius_cells = max(2, int(math.ceil(radius_m / cell)))
    rr_grid, cc_grid = np.mgrid[0:rows, 0:cols]

    for (wx, wy, _wz) in path:
        row, col = _world_to_cell(stack, wx, wy)
        dr = rr_grid - row
        dc = cc_grid - col
        dist = np.sqrt(dr * dr + dc * dc)
        local = np.maximum(
            0.0, 1.0 - (dist / float(radius_cells))
        ) * float(spec.damp_intensity)
        damp = np.maximum(damp, local.astype(np.float32))

    existing = stack.get("wet_rock")
    if existing is not None:
        existing_np = np.asarray(existing, dtype=np.float32)
        if existing_np.shape == damp.shape:
            damp = np.maximum(damp, existing_np)

    stack.set("wet_rock", damp, "caves")
    return damp


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_cave_entrance(
    entrance: Dict,
    stack: TerrainMaskStack,
    *,
    min_framing_elements: int = 2,
    require_damp: bool = True,
) -> List[ValidationIssue]:
    """Return validation issues for an entrance dict.

    Checks:
      - framing rock count meets minimum
      - lip height is plausible (> 1m)
      - damp mask populated (if require_damp)
      - occlusion shelf has positive depth (soft)
    """
    issues: List[ValidationIssue] = []
    cave_id = entrance.get("archetype", "unknown")

    framing = entrance.get("framing_rocks", [])
    if len(framing) < int(min_framing_elements):
        issues.append(
            ValidationIssue(
                code="CAVE_NO_FRAMING",
                severity="hard",
                affected_feature=cave_id,
                message=(
                    f"cave entrance has only {len(framing)} framing elements "
                    f"(< {min_framing_elements})"
                ),
            )
        )

    lip = float(entrance.get("lip_height_m", 0.0))
    if lip < 1.0:
        issues.append(
            ValidationIssue(
                code="CAVE_LIP_TOO_SHORT",
                severity="hard",
                affected_feature=cave_id,
                message=f"cave lip height {lip:.2f}m < 1.0m minimum",
            )
        )

    if require_damp:
        wet = stack.get("wet_rock")
        if wet is None or not np.asarray(wet).any():
            issues.append(
                ValidationIssue(
                    code="CAVE_NO_DAMP_MASK",
                    severity="soft",
                    affected_feature=cave_id,
                    message="wet_rock channel empty; cave has no damp signal",
                )
            )

    shelf = entrance.get("occlusion_shelf", {})
    if float(shelf.get("depth_m", 0.0)) <= 0.0:
        issues.append(
            ValidationIssue(
                code="CAVE_NO_OCCLUSION_SHELF",
                severity="soft",
                affected_feature=cave_id,
                message="cave entrance has no occlusion shelf (depth_m=0)",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Pass wiring
# ---------------------------------------------------------------------------


def _find_entrance_candidates(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> List[Tuple[float, float, float]]:
    """Source entrance candidates from the attached scene read.

    Falls back to scanning ``cave_candidate`` mask if scene_read has none.
    """
    scene_read = state.intent.scene_read
    out: List[Tuple[float, float, float]] = []
    if scene_read is not None and scene_read.cave_candidates:
        for pos in scene_read.cave_candidates:
            if region is not None:
                if not region.contains_point(pos[0], pos[1]):
                    continue
            out.append(tuple(pos))
    return out


def pass_caves(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle F caves pass.

    Contract
    --------
    Consumes: height, slope (optional), basin (optional), wetness (optional)
    Produces: cave_candidate, wet_rock
    Respects protected zones: yes
    Requires scene read: yes
    """
    from .terrain_pipeline import derive_pass_seed  # lazy import

    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: List[ValidationIssue] = []

    base_seed = derive_pass_seed(
        state.intent.seed,
        "caves",
        state.tile_x,
        state.tile_y,
        region,
    )

    # Seed the stack.cave_candidate if unset (pure-bool zero array).
    if stack.get("cave_candidate") is None:
        stack.set(
            "cave_candidate",
            np.zeros_like(stack.height, dtype=bool),
            "caves",
        )
    if stack.get("wet_rock") is None:
        stack.set(
            "wet_rock",
            np.zeros_like(stack.height, dtype=np.float32),
            "caves",
        )

    # Protected zone per-cell mask (applied to cave_candidate after carve)
    protected = _protected_mask_for_caves(state, stack.height.shape)

    entrance_candidates = _find_entrance_candidates(state, region)
    caves: List[CaveStructure] = []
    debris_total = 0

    for idx, ent in enumerate(entrance_candidates):
        # Per-cave seed so debris/picks are stable
        cave_seed = (base_seed ^ ((idx + 1) * 2654435761)) & 0xFFFFFFFF

        # Protected zone check — skip caves whose entrance cell is forbidden
        row, col = _world_to_cell(stack, ent[0], ent[1])
        if protected[row, col]:
            continue

        archetype = pick_cave_archetype(stack, ent, cave_seed)
        spec = make_archetype_spec(archetype)
        path = generate_cave_path(stack, archetype, ent, cave_seed)

        # Carve (delta, not mutation) + update cave_candidate
        delta = carve_cave_volume(stack, path, spec)

        # Apply protected mask to cave_candidate after carve
        cc = np.asarray(stack.get("cave_candidate"), dtype=bool)
        cc = cc & ~protected
        stack.set("cave_candidate", cc, "caves")

        # Framing + debris + damp
        frame = build_cave_entrance_frame(stack, ent, spec)
        debris = scatter_collapse_debris(stack, path, spec, cave_seed)
        damp = generate_damp_mask(stack, path, spec)

        cave = CaveStructure(
            cave_id=f"cave_{state.tile_x}_{state.tile_y}_{idx:02d}",
            archetype=archetype,
            spec=spec,
            entrance_world_pos=tuple(ent),
            path_world=list(path),
            interior_mask=None,
            damp_mask=damp,
            height_delta=delta,
            entrance_frame=frame,
            debris_points=debris,
            tier="hero" if idx == 0 else "secondary",
            cell_count=int(cc.sum()),
        )
        caves.append(cave)
        debris_total += len(debris)

        # Record on side_effects so downstream bundles discover it
        state.side_effects.append(
            f"cave_structure:{cave.cave_id}:"
            f"archetype={archetype.value}:"
            f"debris={len(debris)}:"
            f"tier={cave.tier}"
        )

        # Validate this entrance
        issues.extend(validate_cave_entrance(frame, stack))

    # Accumulate height deltas from all caves into a single channel.
    # Per the pass contract we do NOT mutate stack.height — we record intent.
    accumulated_delta = np.zeros_like(stack.height, dtype=np.float32)
    for cave in caves:
        if cave.height_delta is not None:
            accumulated_delta += cave.height_delta
    stack.set("cave_height_delta", accumulated_delta, "caves")

    hard_issues = [i for i in issues if i.is_hard()]
    status = "ok" if not hard_issues else "warning"

    return PassResult(
        pass_name="caves",
        status=status,
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height", "slope", "basin", "wetness"),
        produced_channels=("cave_candidate", "wet_rock", "cave_height_delta"),
        metrics={
            "cave_count": len(caves),
            "hero_cave_count": sum(1 for c in caves if c.tier == "hero"),
            "debris_points_total": debris_total,
            "seed_used": base_seed,
            "archetypes": {a.value: sum(1 for c in caves if c.archetype == a) for a in CaveArchetype},
        },
        issues=issues,
        side_effects=[f"cave:{c.cave_id}" for c in caves],
    )


def register_bundle_f_passes() -> None:
    """Register the Bundle F caves pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="caves",
            func=pass_caves,
            requires_channels=("height",),
            produces_channels=("cave_candidate", "wet_rock"),
            seed_namespace="caves",
            requires_scene_read=True,
            may_modify_geometry=False,
            description="Bundle F — cave archetypes (5 types + framing + debris + damp).",
        )
    )


def get_cave_entrance_specs(
    stack: "TerrainMaskStack",
    *,
    max_entrances: int = 4,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for cave entrance meshes at cave-candidate sites.

    Reads the ``cave_candidate`` channel (produced by ``pass_caves``) to
    locate entrance positions, then calls ``generate_cave_entrance_mesh``
    from ``_terrain_depth`` to build standalone archway geometry.

    Returns a list of dicts with ``mesh_spec`` and ``world_pos`` keys.
    """
    import numpy as _np
    from ._terrain_depth import generate_cave_entrance_mesh

    cc = stack.get("cave_candidate")
    if cc is None:
        return []

    rng = _np.random.default_rng(seed)
    candidates = _np.argwhere(_np.asarray(cc) > 0.5)
    if len(candidates) == 0:
        return []

    indices = rng.choice(len(candidates), size=min(max_entrances, len(candidates)), replace=False)
    results = []
    for idx in indices:
        r, c = int(candidates[idx][0]), int(candidates[idx][1])
        wx = stack.world_origin_x + c * stack.cell_size
        wy = stack.world_origin_y + r * stack.cell_size
        wz = float(stack.height[r, c])
        spec = generate_cave_entrance_mesh(
            width=rng.uniform(3.0, 6.0),
            height=rng.uniform(3.0, 5.0),
            depth=rng.uniform(2.0, 4.0),
            arch_segments=12,
            terrain_edge_height=wz,
            style="natural",
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": (wx, wy, wz)})
    return results


# ---------------------------------------------------------------------------
# Sub-phase 6E: Cave Deep-Dive
#   Perlin worm paths, marching cubes mesh, stalactites, water pools,
#   lighting zones, portals, entrance asymmetry.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Perlin worm cave path generator
# ---------------------------------------------------------------------------


def _hash_int(x: int) -> int:
    """Deterministic integer hash (Robert Jenkins 32-bit mix)."""
    x = ((x >> 16) ^ x) * 0x45D9F3B
    x = ((x >> 16) ^ x) * 0x45D9F3B
    x = (x >> 16) ^ x
    return x & 0x7FFFFFFF


def _perlin_1d(t: float, seed: int, octaves: int = 3) -> float:
    """Simple 1D value noise for worm path perturbation.

    Uses a seeded hash-based approach (no external perlin lib needed).
    Returns a value in approximately [-1, 1].
    """
    value = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_amp = 0.0
    for o in range(octaves):
        # Hash-based pseudo-random gradient
        n = int(math.floor(t * frequency))
        frac = (t * frequency) - n
        # Smoothstep
        frac_s = frac * frac * (3.0 - 2.0 * frac)
        # Two hash values using robust integer mixing
        h0 = _hash_int(n * 73856093 ^ seed * 19349663 ^ o * 83492791) / 0x7FFFFFFF * 2.0 - 1.0
        h1 = _hash_int((n + 1) * 73856093 ^ seed * 19349663 ^ o * 83492791) / 0x7FFFFFFF * 2.0 - 1.0
        value += (h0 + (h1 - h0) * frac_s) * amplitude
        max_amp += amplitude
        amplitude *= 0.5
        frequency *= 2.0
    return value / max(1e-6, max_amp)


def generate_perlin_worm_path(
    entrance_pos: Tuple[float, float, float],
    *,
    length_m: float = 40.0,
    segment_count: int = 20,
    seed: int = 42,
    worm_radius_m: float = 3.0,
    vertical_bias: float = -0.3,
    horizontal_wander: float = 0.6,
) -> List[Tuple[float, float, float]]:
    """Generate a 3D cave path using Perlin worm technique.

    The worm advances in small steps, with heading perturbed by layered
    noise so it meanders naturally through rock. The result is a smooth
    polyline in world-space meters (Z-up).

    Parameters
    ----------
    entrance_pos : world (x, y, z)
    length_m : total path length in meters
    segment_count : number of polyline segments
    seed : deterministic seed
    worm_radius_m : tunnel radius (informational, not used for carving here)
    vertical_bias : negative = descends, positive = ascends
    horizontal_wander : strength of lateral noise [0..1]

    Returns
    -------
    List of (x, y, z) world-space points.
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    # Initial heading from seed
    heading = float(rng.uniform(0.0, 2.0 * math.pi))
    pitch = float(rng.uniform(-0.2, -0.05))  # slight downward default

    step_len = length_m / max(1, segment_count)
    x, y, z = entrance_pos
    points: List[Tuple[float, float, float]] = [(x, y, z)]

    seed_h = int(rng.integers(0, 2**31))
    seed_p = int(rng.integers(0, 2**31))
    seed_r = int(rng.integers(0, 2**31))

    for i in range(segment_count):
        t = float(i) / max(1, segment_count)

        # Perlin noise perturbation on heading and pitch
        dh = _perlin_1d(t * 4.0, seed_h) * horizontal_wander * 0.8
        dp = _perlin_1d(t * 3.0, seed_p) * 0.3 + vertical_bias * 0.1
        # Slight roll noise for asymmetry
        dr = _perlin_1d(t * 2.5, seed_r) * 0.15

        heading += dh * step_len * 0.1
        pitch = max(-1.2, min(0.3, pitch + dp * step_len * 0.05))

        dx = math.cos(heading) * math.cos(pitch) * step_len
        dy = math.sin(heading) * math.cos(pitch) * step_len
        dz = math.sin(pitch) * step_len + dr * step_len * 0.2

        x += dx
        y += dy
        z += dz
        points.append((x, y, z))

    return points


# ---------------------------------------------------------------------------
# Marching-cubes isosurface mesh from 3D cave volume
# ---------------------------------------------------------------------------


@dataclass
class CaveMeshSpec:
    """Lightweight mesh specification for a cave volume surface.

    Stores vertices and triangle indices produced by marching cubes.
    """
    vertices: np.ndarray   # (N, 3) float64 world-space
    triangles: np.ndarray  # (M, 3) int32 vertex indices
    normals: Optional[np.ndarray] = None  # (N, 3) if computed
    vertex_count: int = 0
    triangle_count: int = 0


# Marching cubes edge table (simplified — 15 canonical cube configs)
# Full 256-entry table is standard; here we use a numpy-based approach.

def _build_cave_volume_field(
    path: List[Tuple[float, float, float]],
    worm_radius_m: float = 3.0,
    grid_resolution: float = 1.0,
    padding_m: float = 5.0,
) -> Tuple[np.ndarray, Tuple[float, float, float], float]:
    """Build a 3D scalar field where negative = inside cave, positive = rock.

    Parameters
    ----------
    path : polyline of cave centreline
    worm_radius_m : tunnel radius
    grid_resolution : voxel size in meters
    padding_m : extra space around path bounding box

    Returns
    -------
    (field_3d, origin_xyz, voxel_size)
    field_3d : (Nz, Ny, Nx) float64 array, negative inside cave
    origin_xyz : world-space origin of the grid corner
    voxel_size : cell size in meters
    """
    if not path:
        empty = np.ones((2, 2, 2), dtype=np.float64)
        return empty, (0.0, 0.0, 0.0), grid_resolution

    path_arr = np.asarray(path, dtype=np.float64)
    mins = path_arr.min(axis=0) - padding_m
    maxs = path_arr.max(axis=0) + padding_m

    nx = max(2, int(math.ceil((maxs[0] - mins[0]) / grid_resolution)))
    ny = max(2, int(math.ceil((maxs[1] - mins[1]) / grid_resolution)))
    nz = max(2, int(math.ceil((maxs[2] - mins[2]) / grid_resolution)))

    # Cap grid size to prevent memory blowout
    max_dim = 64
    nx = min(nx, max_dim)
    ny = min(ny, max_dim)
    nz = min(nz, max_dim)

    # Build coordinate grids
    xs = mins[0] + np.arange(nx) * grid_resolution
    ys = mins[1] + np.arange(ny) * grid_resolution
    zs = mins[2] + np.arange(nz) * grid_resolution

    # Start with "all rock" (positive)
    field = np.ones((nz, ny, nx), dtype=np.float64)

    # For each path segment, carve a tube
    for px, py, pz in path:
        # Vectorized distance from this path point
        dx = xs[np.newaxis, np.newaxis, :] - px
        dy = ys[np.newaxis, :, np.newaxis] - py
        dz = zs[:, np.newaxis, np.newaxis] - pz
        dist = np.sqrt(dx * dx + dy * dy + dz * dz)
        # Signed distance: negative inside the worm radius
        sdf = (dist - worm_radius_m) / max(0.1, worm_radius_m)
        field = np.minimum(field, sdf)

    return field, (float(mins[0]), float(mins[1]), float(mins[2])), grid_resolution


def marching_cubes_cave_mesh(
    path: List[Tuple[float, float, float]],
    *,
    worm_radius_m: float = 3.0,
    grid_resolution: float = 1.0,
    iso_level: float = 0.0,
) -> CaveMeshSpec:
    """Generate a triangle mesh of the cave interior surface using marching cubes.

    This is a simplified but functional marching cubes implementation that
    extracts the isosurface at ``iso_level`` from a 3D signed distance field
    built around the cave path polyline.

    Parameters
    ----------
    path : cave centreline polyline
    worm_radius_m : tunnel radius
    grid_resolution : voxel size (meters)
    iso_level : isosurface threshold (0.0 = surface boundary)

    Returns
    -------
    CaveMeshSpec with vertices and triangle indices.
    """
    field, origin, voxel = _build_cave_volume_field(
        path, worm_radius_m, grid_resolution
    )
    nz, ny, nx = field.shape

    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    edge_cache: Dict[Tuple[int, int, int, int, int, int], int] = {}

    def _interp_vertex(
        x1: int, y1: int, z1: int, x2: int, y2: int, z2: int
    ) -> int:
        """Interpolate vertex on edge between two voxel corners."""
        key = (
            min(x1, x2), min(y1, y2), min(z1, z2),
            max(x1, x2), max(y1, y2), max(z1, z2),
        )
        if key in edge_cache:
            return edge_cache[key]

        v1 = field[z1, y1, x1]
        v2 = field[z2, y2, x2]
        denom = v2 - v1
        if abs(denom) < 1e-10:
            t = 0.5
        else:
            t = (iso_level - v1) / denom
        t = max(0.0, min(1.0, t))

        wx = origin[0] + (x1 + t * (x2 - x1)) * voxel
        wy = origin[1] + (y1 + t * (y2 - y1)) * voxel
        wz = origin[2] + (z1 + t * (z2 - z1)) * voxel

        idx = len(vertices)
        vertices.append((wx, wy, wz))
        edge_cache[key] = idx
        return idx

    # Simplified marching cubes: for each voxel cube, check which corners
    # are inside/outside and emit triangles for faces that cross the iso.
    # We use a face-based approach (6 faces per cube) rather than the full
    # 256-entry lookup table, which is simpler and sufficient for our needs.
    for z in range(nz - 1):
        for y in range(ny - 1):
            for x in range(nx - 1):
                # 8 corner values
                corners = [
                    field[z, y, x],
                    field[z, y, x + 1],
                    field[z, y + 1, x],
                    field[z, y + 1, x + 1],
                    field[z + 1, y, x],
                    field[z + 1, y, x + 1],
                    field[z + 1, y + 1, x],
                    field[z + 1, y + 1, x + 1],
                ]

                # Classify corners
                inside = [c < iso_level for c in corners]
                n_inside = sum(inside)

                # Skip if all inside or all outside
                if n_inside == 0 or n_inside == 8:
                    continue

                # Corner positions: (x,y,z) offsets for each of 8 corners
                cpos = [
                    (x, y, z), (x + 1, y, z),
                    (x, y + 1, z), (x + 1, y + 1, z),
                    (x, y, z + 1), (x + 1, y, z + 1),
                    (x, y + 1, z + 1), (x + 1, y + 1, z + 1),
                ]

                # 12 edges of the cube
                edges = [
                    (0, 1), (2, 3), (4, 5), (6, 7),  # x-aligned
                    (0, 2), (1, 3), (4, 6), (5, 7),  # y-aligned
                    (0, 4), (1, 5), (2, 6), (3, 7),  # z-aligned
                ]

                # Find edges that cross the isosurface
                crossing_verts = []
                for e0, e1 in edges:
                    if inside[e0] != inside[e1]:
                        vi = _interp_vertex(*cpos[e0], *cpos[e1])
                        crossing_verts.append(vi)

                # Triangulate crossing vertices (fan from first)
                if len(crossing_verts) >= 3:
                    for i in range(1, len(crossing_verts) - 1):
                        triangles.append(
                            (crossing_verts[0], crossing_verts[i], crossing_verts[i + 1])
                        )

    if not vertices:
        verts_arr = np.zeros((0, 3), dtype=np.float64)
        tris_arr = np.zeros((0, 3), dtype=np.int32)
    else:
        verts_arr = np.array(vertices, dtype=np.float64)
        tris_arr = np.array(triangles, dtype=np.int32) if triangles else np.zeros((0, 3), dtype=np.int32)

    return CaveMeshSpec(
        vertices=verts_arr,
        triangles=tris_arr,
        vertex_count=len(vertices),
        triangle_count=len(triangles),
    )


# ---------------------------------------------------------------------------
# Stalactite / stalagmite placement
# ---------------------------------------------------------------------------


@dataclass
class StalactiteSpec:
    """A single stalactite or stalagmite placement."""
    position: Tuple[float, float, float]  # world-space tip position
    direction: str  # "down" (stalactite) or "up" (stalagmite)
    length_m: float
    base_radius_m: float
    drip_active: bool = False  # whether this stalactite has active drip
    mineral_type: str = "calcite"  # calcite, iron_oxide, wet_calcite


def place_stalactites(
    path: List[Tuple[float, float, float]],
    *,
    seed: int = 42,
    worm_radius_m: float = 3.0,
    density: float = 0.5,
    max_count: int = 100,
    damp_intensity: float = 0.5,
) -> List[StalactiteSpec]:
    """Place stalactites (ceiling) and stalagmites (floor) along a cave path.

    Stalactites hang from the ceiling (above centreline), stalagmites grow
    from the floor (below centreline). Placement uses noise-based spacing
    so formations cluster naturally.

    Parameters
    ----------
    path : cave centreline polyline
    seed : deterministic seed
    worm_radius_m : tunnel radius for offset calculation
    density : placement density 0..1
    max_count : hard cap on formations
    damp_intensity : dampness factor influences drip probability

    Returns
    -------
    List of StalactiteSpec instances.
    """
    if not path or density <= 0:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    path_arr = np.asarray(path, dtype=np.float64)
    n_pts = path_arr.shape[0]

    # Target count based on path length and density
    if n_pts < 2:
        return []
    lengths = np.sqrt(np.sum(np.diff(path_arr, axis=0) ** 2, axis=1))
    total_length = float(lengths.sum())
    target_count = min(max_count, max(1, int(total_length * density * 0.8)))

    formations: List[StalactiteSpec] = []

    for _ in range(target_count):
        # Pick a random position along the path
        t = float(rng.uniform(0.1, 0.95))  # avoid entrance/exit
        idx = min(n_pts - 2, int(t * (n_pts - 1)))
        frac = t * (n_pts - 1) - idx
        base = path_arr[idx] + (path_arr[min(n_pts - 1, idx + 1)] - path_arr[idx]) * frac

        # Determine ceiling vs floor
        is_ceiling = bool(rng.random() < 0.6)  # 60% stalactites
        direction = "down" if is_ceiling else "up"

        # Offset from centreline
        z_offset = worm_radius_m * (0.7 + rng.uniform(0.0, 0.25))
        if is_ceiling:
            pos = (float(base[0]), float(base[1]), float(base[2] + z_offset))
        else:
            pos = (float(base[0]), float(base[1]), float(base[2] - z_offset))

        # Size varies with noise
        length = float(rng.uniform(0.3, 1.8))
        base_radius = length * float(rng.uniform(0.08, 0.2))

        # Drip probability scales with dampness
        drip = bool(rng.random() < damp_intensity * 0.4) if is_ceiling else False

        # Mineral type
        mineral_roll = float(rng.random())
        if damp_intensity > 0.6 and mineral_roll < 0.4:
            mineral = "wet_calcite"
        elif mineral_roll < 0.15:
            mineral = "iron_oxide"
        else:
            mineral = "calcite"

        formations.append(StalactiteSpec(
            position=pos,
            direction=direction,
            length_m=length,
            base_radius_m=base_radius,
            drip_active=drip,
            mineral_type=mineral,
        ))

    return formations


# ---------------------------------------------------------------------------
# Water pool detection and placement
# ---------------------------------------------------------------------------


@dataclass
class CaveWaterPool:
    """A water pool inside a cave, at a low point along the path."""
    center: Tuple[float, float, float]  # world-space center
    radius_m: float
    depth_m: float
    surface_z: float  # water surface elevation
    is_connected: bool = False  # connected to underground stream
    flow_direction: Optional[Tuple[float, float]] = None  # (dx, dy) if flowing


def detect_cave_water_pools(
    path: List[Tuple[float, float, float]],
    *,
    seed: int = 42,
    damp_intensity: float = 0.5,
    min_pool_depth_m: float = 0.3,
    worm_radius_m: float = 3.0,
) -> List[CaveWaterPool]:
    """Detect natural water pool locations at low points along a cave path.

    Pools form where the path descends then ascends (local Z minima).
    Pool size scales with the depth of the depression and dampness.

    Parameters
    ----------
    path : cave centreline
    seed : deterministic seed
    damp_intensity : overall dampness (higher = more/bigger pools)
    min_pool_depth_m : minimum Z depression to qualify as a pool
    worm_radius_m : tunnel radius for pool radius calculation

    Returns
    -------
    List of CaveWaterPool instances.
    """
    if len(path) < 3:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    path_arr = np.asarray(path, dtype=np.float64)
    zs = path_arr[:, 2]
    n = len(zs)

    pools: List[CaveWaterPool] = []

    # Find local Z minima (lower than both neighbours)
    for i in range(1, n - 1):
        if zs[i] < zs[i - 1] and zs[i] < zs[i + 1]:
            # Depth is the min of the two "walls" above this minimum
            left_wall = zs[i - 1] - zs[i]
            right_wall = zs[i + 1] - zs[i]
            pool_depth = min(left_wall, right_wall)

            if pool_depth < min_pool_depth_m:
                continue

            # Scale by dampness
            effective_depth = pool_depth * min(1.0, damp_intensity + 0.3)
            radius = worm_radius_m * (0.5 + effective_depth * 0.3)
            radius = min(radius, worm_radius_m * 1.5)

            surface_z = float(zs[i]) + effective_depth * 0.8

            # Flow direction: if adjacent pools exist or path continues descending
            flow = None
            if i < n - 2 and zs[i + 2] < zs[i]:
                dx = float(path_arr[i + 1, 0] - path_arr[i, 0])
                dy = float(path_arr[i + 1, 1] - path_arr[i, 1])
                norm = math.sqrt(dx * dx + dy * dy)
                if norm > 1e-6:
                    flow = (dx / norm, dy / norm)

            connected = bool(rng.random() < damp_intensity * 0.5)

            pools.append(CaveWaterPool(
                center=(float(path_arr[i, 0]), float(path_arr[i, 1]), float(zs[i])),
                radius_m=float(radius),
                depth_m=float(effective_depth),
                surface_z=float(surface_z),
                is_connected=connected,
                flow_direction=flow,
            ))

    return pools


# ---------------------------------------------------------------------------
# Cave lighting zones
# ---------------------------------------------------------------------------


@dataclass
class CaveLightZone:
    """A lighting zone inside a cave with ambient light falloff."""
    position: Tuple[float, float, float]
    zone_type: str  # "entrance", "twilight", "dark", "deep_dark"
    light_intensity: float  # 0..1, 1.0 = full daylight
    radius_m: float
    color_temperature_k: float  # Kelvin, ~6500 = daylight, ~2000 = warm
    has_god_rays: bool = False
    bioluminescence: float = 0.0  # 0..1 glow from cave organisms


def compute_cave_lighting_zones(
    path: List[Tuple[float, float, float]],
    *,
    entrance_pos: Tuple[float, float, float],
    seed: int = 42,
    archetype: Optional[CaveArchetype] = None,
) -> List[CaveLightZone]:
    """Compute lighting zones along a cave path with realistic light falloff.

    Light intensity drops exponentially from the entrance. Zones are
    classified as entrance (bright), twilight (dim), dark, and deep_dark.

    Bio-luminescence can appear in damp deep sections.

    Parameters
    ----------
    path : cave centreline
    entrance_pos : cave mouth position
    seed : deterministic seed
    archetype : optional archetype for tuning

    Returns
    -------
    List of CaveLightZone instances along the path.
    """
    if not path:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    path_arr = np.asarray(path, dtype=np.float64)
    entrance = np.asarray(entrance_pos[:3], dtype=np.float64)
    n = len(path_arr)

    # Cumulative distance from entrance along path
    if n < 2:
        return [CaveLightZone(
            position=tuple(path_arr[0]),
            zone_type="entrance",
            light_intensity=0.9,
            radius_m=5.0,
            color_temperature_k=6500.0,
            has_god_rays=True,
        )]

    dists = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        seg = np.linalg.norm(path_arr[i] - path_arr[i - 1])
        dists[i] = dists[i - 1] + seg
    total_len = dists[-1]

    zones: List[CaveLightZone] = []

    # Falloff parameters
    # Light halves every ~8 meters from entrance
    half_life_m = 8.0
    if archetype == CaveArchetype.SEA_GROTTO:
        half_life_m = 12.0  # wider opening lets more light in
    elif archetype == CaveArchetype.FISSURE:
        half_life_m = 5.0   # narrow = fast light drop

    for i in range(n):
        d = dists[i]
        # Exponential falloff
        intensity = math.exp(-0.693 * d / half_life_m)  # ln(2) ~ 0.693
        intensity = max(0.0, min(1.0, intensity))

        # Zone classification
        if intensity > 0.5:
            zone_type = "entrance"
        elif intensity > 0.15:
            zone_type = "twilight"
        elif intensity > 0.02:
            zone_type = "dark"
        else:
            zone_type = "deep_dark"

        # Color temperature shifts warmer deeper in
        temp_k = 6500.0 - (1.0 - intensity) * 4000.0
        temp_k = max(2000.0, temp_k)

        # God rays only at entrance
        god_rays = (i == 0 or (i == 1 and intensity > 0.6))

        # Bioluminescence in deep sections of wet caves
        bio = 0.0
        if zone_type in ("dark", "deep_dark"):
            bio_chance = 0.2
            if archetype in (CaveArchetype.SEA_GROTTO, CaveArchetype.GLACIAL_MELT):
                bio_chance = 0.4
            if rng.random() < bio_chance:
                bio = float(rng.uniform(0.05, 0.3))

        # Zone radius decreases deeper in (tunnel narrows)
        t_norm = d / max(1.0, total_len)
        radius = max(2.0, 5.0 * (1.0 - t_norm * 0.4))

        zones.append(CaveLightZone(
            position=(float(path_arr[i, 0]), float(path_arr[i, 1]), float(path_arr[i, 2])),
            zone_type=zone_type,
            light_intensity=float(intensity),
            radius_m=float(radius),
            color_temperature_k=float(temp_k),
            has_god_rays=god_rays,
            bioluminescence=bio,
        ))

    return zones


# ---------------------------------------------------------------------------
# Portal placement (cave-to-cave / cave-to-surface connections)
# ---------------------------------------------------------------------------


@dataclass
class CavePortal:
    """A portal connecting two cave regions or a cave to the surface."""
    portal_id: str
    position: Tuple[float, float, float]  # world-space
    portal_type: str  # "cave_exit", "cave_link", "vertical_shaft", "underwater"
    target_hint: Optional[str] = None  # id of target cave or "surface"
    width_m: float = 3.0
    height_m: float = 3.0
    is_blocked: bool = False  # debris/collapse blocks passage
    discovery_difficulty: str = "visible"  # "visible", "hidden", "secret"


def place_cave_portals(
    path: List[Tuple[float, float, float]],
    cave_id: str,
    *,
    seed: int = 42,
    archetype: Optional[CaveArchetype] = None,
    allow_secret: bool = True,
) -> List[CavePortal]:
    """Place portals along a cave path — exits, links, and shafts.

    Rules:
    - The path end always gets a potential exit (cave_exit or cave_link).
    - Karst sinkholes get a vertical shaft at their deepest point.
    - Sea grottos may have an underwater portal.
    - Secret passages are placed with low probability at path midpoints.

    Parameters
    ----------
    path : cave centreline
    cave_id : identifier for this cave (for naming portals)
    seed : deterministic seed
    archetype : cave type for type-specific portals
    allow_secret : whether to place hidden/secret portals

    Returns
    -------
    List of CavePortal instances.
    """
    if len(path) < 2:
        return []

    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    path_arr = np.asarray(path, dtype=np.float64)
    portals: List[CavePortal] = []

    # End-of-path portal
    end_pos = tuple(path_arr[-1])
    if archetype == CaveArchetype.KARST_SINKHOLE:
        # Vertical shaft at deepest Z
        z_min_idx = int(np.argmin(path_arr[:, 2]))
        shaft_pos = tuple(path_arr[z_min_idx])
        portals.append(CavePortal(
            portal_id=f"{cave_id}_shaft_0",
            position=shaft_pos,
            portal_type="vertical_shaft",
            target_hint="surface",
            width_m=2.5,
            height_m=float(abs(path_arr[0, 2] - path_arr[z_min_idx, 2])),
            is_blocked=bool(rng.random() < 0.3),
            discovery_difficulty="visible",
        ))
    elif archetype == CaveArchetype.SEA_GROTTO:
        # Possible underwater portal
        if rng.random() < 0.5:
            portals.append(CavePortal(
                portal_id=f"{cave_id}_underwater_0",
                position=end_pos,
                portal_type="underwater",
                target_hint=None,
                width_m=4.0,
                height_m=2.5,
                is_blocked=False,
                discovery_difficulty="hidden",
            ))

    # Default end exit
    portals.append(CavePortal(
        portal_id=f"{cave_id}_exit_0",
        position=end_pos,
        portal_type="cave_exit",
        target_hint="surface",
        width_m=float(rng.uniform(2.0, 4.0)),
        height_m=float(rng.uniform(2.0, 3.5)),
        is_blocked=bool(rng.random() < 0.2),
        discovery_difficulty="visible",
    ))

    # Secret passage at midpoint (optional)
    if allow_secret and len(path) >= 6:
        mid_idx = len(path) // 2
        if rng.random() < 0.25:
            mid_pos = tuple(path_arr[mid_idx])
            portals.append(CavePortal(
                portal_id=f"{cave_id}_secret_0",
                position=mid_pos,
                portal_type="cave_link",
                target_hint=None,
                width_m=float(rng.uniform(1.5, 2.5)),
                height_m=float(rng.uniform(1.5, 2.0)),
                is_blocked=False,
                discovery_difficulty="secret",
            ))

    return portals


# ---------------------------------------------------------------------------
# Entrance asymmetry
# ---------------------------------------------------------------------------


@dataclass
class AsymmetricEntrance:
    """Asymmetric cave entrance geometry for natural appearance.

    Instead of a symmetric arch, the entrance has different left/right
    heights, an irregular top edge, and optional overhang.
    """
    center: Tuple[float, float, float]
    left_height_m: float
    right_height_m: float
    width_m: float
    overhang_depth_m: float  # 0 = no overhang
    overhang_side: str  # "left", "right", "center"
    irregularity_points: List[Tuple[float, float]]  # (angle_rad, radius_factor) pairs
    rock_shelf_left: bool
    rock_shelf_right: bool


def generate_asymmetric_entrance(
    entrance_pos: Tuple[float, float, float],
    spec: CaveArchetypeSpec,
    *,
    seed: int = 42,
) -> AsymmetricEntrance:
    """Generate an asymmetric cave entrance for natural appearance.

    Real cave entrances are never perfectly symmetric. This produces
    different left/right heights, irregular top-edge profile, and
    optional overhang.

    Parameters
    ----------
    entrance_pos : world-space entrance center
    spec : archetype specification
    seed : deterministic seed

    Returns
    -------
    AsymmetricEntrance with left/right height asymmetry and irregularity.
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)

    base_h = spec.entrance_height_m
    base_w = spec.entrance_width_m

    # Asymmetric height: left and right differ by up to 30%
    asym_factor = float(rng.uniform(0.1, 0.3))
    if rng.random() < 0.5:
        left_h = base_h * (1.0 + asym_factor * 0.5)
        right_h = base_h * (1.0 - asym_factor * 0.5)
    else:
        left_h = base_h * (1.0 - asym_factor * 0.5)
        right_h = base_h * (1.0 + asym_factor * 0.5)

    # Overhang
    overhang = 0.0
    overhang_side = "center"
    if spec.archetype in (CaveArchetype.SEA_GROTTO, CaveArchetype.LAVA_TUBE):
        overhang = float(rng.uniform(0.5, 2.0))
        overhang_side = str(rng.choice(["left", "right", "center"]))
    elif rng.random() < 0.3:
        overhang = float(rng.uniform(0.2, 1.0))
        overhang_side = str(rng.choice(["left", "right"]))

    # Irregularity profile: angular sample points around the entrance arch
    n_irreg = int(rng.integers(6, 14))
    irregularity: List[Tuple[float, float]] = []
    for i in range(n_irreg):
        angle = float(i) / n_irreg * math.pi  # 0 to pi (semicircle)
        factor = 1.0 + float(rng.uniform(-0.15, 0.15)) * spec.ceiling_irregularity
        irregularity.append((angle, factor))

    # Rock shelves (flat ledges on sides)
    shelf_left = bool(rng.random() < 0.35)
    shelf_right = bool(rng.random() < 0.35)

    return AsymmetricEntrance(
        center=entrance_pos,
        left_height_m=float(left_h),
        right_height_m=float(right_h),
        width_m=float(base_w),
        overhang_depth_m=float(overhang),
        overhang_side=overhang_side,
        irregularity_points=irregularity,
        rock_shelf_left=shelf_left,
        rock_shelf_right=shelf_right,
    )


# ---------------------------------------------------------------------------
# Extended pass: deep cave analysis
# ---------------------------------------------------------------------------


@dataclass
class DeepCaveAnalysis:
    """Complete deep-dive analysis result for a single cave."""
    cave_id: str
    worm_path: List[Tuple[float, float, float]]
    mesh: Optional[CaveMeshSpec]
    stalactites: List[StalactiteSpec]
    water_pools: List[CaveWaterPool]
    lighting_zones: List[CaveLightZone]
    portals: List[CavePortal]
    asymmetric_entrance: Optional[AsymmetricEntrance]


def analyze_deep_cave(
    cave: CaveStructure,
    stack: TerrainMaskStack,
    *,
    seed: int = 42,
    generate_mesh: bool = True,
    mesh_resolution: float = 1.5,
) -> DeepCaveAnalysis:
    """Run full deep-dive analysis on a single CaveStructure.

    Composes all sub-phase 6E features: Perlin worm path, marching cubes
    mesh, stalactites, water pools, lighting zones, portals, and entrance
    asymmetry into a single cohesive result.

    Parameters
    ----------
    cave : existing CaveStructure from pass_caves
    stack : terrain mask stack for context
    seed : deterministic seed
    generate_mesh : whether to run marching cubes (can be slow)
    mesh_resolution : voxel size for mesh generation

    Returns
    -------
    DeepCaveAnalysis with all computed features.
    """
    spec = cave.spec
    entrance = cave.entrance_world_pos

    # 1. Perlin worm path (replaces/extends the basic path)
    worm_path = generate_perlin_worm_path(
        entrance,
        length_m=spec.interior_length_m,
        segment_count=max(10, int(spec.interior_length_m / 2.0)),
        seed=seed,
        worm_radius_m=spec.entrance_width_m * 0.4,
        vertical_bias=-0.3 if spec.archetype != CaveArchetype.FISSURE else -0.6,
        horizontal_wander=0.6 if spec.archetype == CaveArchetype.GLACIAL_MELT else 0.4,
    )

    # 2. Marching cubes mesh
    mesh = None
    if generate_mesh and len(worm_path) >= 3:
        mesh = marching_cubes_cave_mesh(
            worm_path,
            worm_radius_m=spec.entrance_width_m * 0.4,
            grid_resolution=mesh_resolution,
        )

    # 3. Stalactites
    stalactites = place_stalactites(
        worm_path,
        seed=seed ^ 0xDEAD,
        worm_radius_m=spec.entrance_width_m * 0.4,
        density=0.5 * spec.damp_intensity + 0.2,
        damp_intensity=spec.damp_intensity,
    )

    # 4. Water pools
    pools = detect_cave_water_pools(
        worm_path,
        seed=seed ^ 0xBEEF,
        damp_intensity=spec.damp_intensity,
        worm_radius_m=spec.entrance_width_m * 0.4,
    )

    # 5. Lighting zones
    lighting = compute_cave_lighting_zones(
        worm_path,
        entrance_pos=entrance,
        seed=seed ^ 0xCAFE,
        archetype=spec.archetype,
    )

    # 6. Portals
    portals = place_cave_portals(
        worm_path,
        cave.cave_id,
        seed=seed ^ 0xF00D,
        archetype=spec.archetype,
    )

    # 7. Asymmetric entrance
    asym_entrance = generate_asymmetric_entrance(
        entrance,
        spec,
        seed=seed ^ 0xA55E,
    )

    return DeepCaveAnalysis(
        cave_id=cave.cave_id,
        worm_path=worm_path,
        mesh=mesh,
        stalactites=stalactites,
        water_pools=pools,
        lighting_zones=lighting,
        portals=portals,
        asymmetric_entrance=asym_entrance,
    )


__all__ = [
    "CaveArchetype",
    "CaveArchetypeSpec",
    "CaveStructure",
    "CaveMeshSpec",
    "StalactiteSpec",
    "CaveWaterPool",
    "CaveLightZone",
    "CavePortal",
    "AsymmetricEntrance",
    "DeepCaveAnalysis",
    "make_archetype_spec",
    "pick_cave_archetype",
    "generate_cave_path",
    "generate_perlin_worm_path",
    "carve_cave_volume",
    "build_cave_entrance_frame",
    "scatter_collapse_debris",
    "generate_damp_mask",
    "validate_cave_entrance",
    "marching_cubes_cave_mesh",
    "place_stalactites",
    "detect_cave_water_pools",
    "compute_cave_lighting_zones",
    "place_cave_portals",
    "generate_asymmetric_entrance",
    "analyze_deep_cave",
    "pass_caves",
    "register_bundle_f_passes",
    "get_cave_entrance_specs",
]
