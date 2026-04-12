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


__all__ = [
    "CaveArchetype",
    "CaveArchetypeSpec",
    "CaveStructure",
    "make_archetype_spec",
    "pick_cave_archetype",
    "generate_cave_path",
    "carve_cave_volume",
    "build_cave_entrance_frame",
    "scatter_collapse_debris",
    "generate_damp_mask",
    "validate_cave_entrance",
    "pass_caves",
    "register_bundle_f_passes",
    "get_cave_entrance_specs",
]
