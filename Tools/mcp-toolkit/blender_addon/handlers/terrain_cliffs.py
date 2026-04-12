"""Bundle B — Cliff anatomy analysis (pure numpy, no bpy).

Replaces the legacy "steep terrain == cliff" heuristic with a registered
cliff structure: lip polyline + face mask + ledges + talus field. All
analysis is pure-numpy so it can be tested outside Blender.

See docs/terrain_ultra_implementation_plan_2026-04-08.md §7 (Bundle B).

Agent protocol compliance:
- Rule 1: all mutation lives behind ``pass_cliffs`` + ``register_bundle_b_passes``
- Rule 3: every intermediate signal (``cliff_candidate``) is written to
  ``TerrainMaskStack`` via ``stack.set(...)``
- Rule 4: uses ``derive_pass_seed`` — never ``hash()`` / ``random.random()``
- Rule 6: Z-up world meters (``stack.height`` is world-Z in meters)
- Rule 7: populates Unity-visible mask channels for round-trip export
- Rule 10: never ``np.clip(..., 0, 1)`` on world heights
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

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
# Cliff dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TalusField:
    """Scree / talus field at the base of a cliff.

    ``mask`` is a boolean (H, W) array covering cells assigned to the
    talus apron. ``angle_of_repose_radians`` defaults to ~34° which is
    the typical angle for angular rock debris.
    """

    mask: np.ndarray
    angle_of_repose_radians: float = math.radians(34.0)
    average_particle_size_m: float = 0.4


@dataclass
class CliffStructure:
    """A single registered cliff anatomy.

    A cliff is no longer "steep terrain" — it is an explicit structure
    with a lip polyline, a face mask, 0-3 horizontal ledges, and a talus
    apron. Bundle B builds these from the candidate mask; future bundles
    (hero insertion) consume them to place authored geometry.
    """

    cliff_id: str
    lip_polyline: np.ndarray  # (N, 2) int32: (row, col) cells along upper edge
    face_mask: np.ndarray      # (H, W) bool: cliff face cells
    ledges: List[np.ndarray] = field(default_factory=list)  # list of (H, W) bool
    talus_mask: Optional[np.ndarray] = None  # (H, W) bool scree apron
    world_bounds: Optional[BBox] = None
    tier: str = "secondary"
    # Derived metrics (populated by carve_cliff_system)
    max_height_m: float = 0.0
    min_height_m: float = 0.0
    cell_count: int = 0


# ---------------------------------------------------------------------------
# Candidate mask
# ---------------------------------------------------------------------------


def build_cliff_candidate_mask(
    stack: TerrainMaskStack,
    *,
    slope_threshold_deg: float = 55.0,
    ridge_weight: float = 0.5,
    min_cluster_size: int = 20,
    saliency_threshold: float = 0.3,
) -> np.ndarray:
    """Return a boolean (H, W) mask of cliff candidate cells.

    A cell is a candidate iff:
      - slope > ``slope_threshold_deg``
      - not inside the hero_exclusion mask (if present)
      - saliency_macro > ``saliency_threshold`` (if present; fallback: slope-only)

    Ridge weighting biases cells that sit on ridge lines upward by
    ``ridge_weight`` (not used as a hard filter — the slope gate is
    authoritative).
    """
    slope = stack.get("slope")
    if slope is None:
        raise KeyError("build_cliff_candidate_mask requires 'slope' on the stack")
    slope = np.asarray(slope, dtype=np.float64)

    threshold_rad = math.radians(float(slope_threshold_deg))
    mask = slope > threshold_rad

    # Saliency gate (if present)
    saliency = stack.get("saliency_macro")
    if saliency is not None:
        sal = np.asarray(saliency, dtype=np.float64)
        if sal.shape == mask.shape:
            mask &= sal > float(saliency_threshold)

    # Ridge bias — accept all cells whose slope is close to threshold
    # AND which sit on a ridge line; we express this by OR-ing in any
    # ridge cell that is within 80% of the threshold.
    ridge = stack.get("ridge")
    if ridge is not None and ridge_weight > 0.0:
        rid = np.asarray(ridge, dtype=bool)
        if rid.shape == mask.shape:
            near_thresh = slope > (threshold_rad * 0.8)
            mask |= rid & near_thresh

    # Exclude hero exclusion zones (reserved for authored hero meshes)
    hero_excl = stack.get("hero_exclusion")
    if hero_excl is not None:
        excl = np.asarray(hero_excl, dtype=bool)
        if excl.shape == mask.shape:
            mask &= ~excl

    # Drop clusters smaller than min_cluster_size
    if min_cluster_size > 1 and mask.any():
        labels = _label_connected_components(mask)
        unique, counts = np.unique(labels, return_counts=True)
        small = unique[(counts < int(min_cluster_size)) & (unique != 0)]
        if small.size:
            mask = np.where(np.isin(labels, small), False, mask)

    return mask.astype(bool)


def _label_connected_components(mask: np.ndarray) -> np.ndarray:
    """8-connected connected-component labeling.

    Returns an int32 array where each component has a distinct label
    (0 = background). Pure numpy + python BFS (no scipy dependency).
    """
    m = np.asarray(mask, dtype=bool)
    labels = np.zeros(m.shape, dtype=np.int32)
    if not m.any():
        return labels

    rows, cols = m.shape
    next_id = 1
    # Iterate in row-major; BFS each unvisited True cell
    for r0 in range(rows):
        for c0 in range(cols):
            if not m[r0, c0] or labels[r0, c0] != 0:
                continue
            stack_bfs = [(r0, c0)]
            seed_id = next_id
            next_id += 1
            while stack_bfs:
                r, c = stack_bfs.pop()
                if r < 0 or r >= rows or c < 0 or c >= cols:
                    continue
                if not m[r, c] or labels[r, c] != 0:
                    continue
                labels[r, c] = seed_id
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        stack_bfs.append((r + dr, c + dc))
    return labels


# ---------------------------------------------------------------------------
# Carve cliff system
# ---------------------------------------------------------------------------


def carve_cliff_system(
    state: TerrainPipelineState,
    region: Optional[BBox],
    *,
    candidate_mask: Optional[np.ndarray] = None,
    max_cliff_count: int = 20,
    min_component_size: int = 20,
) -> List[CliffStructure]:
    """Analyse the candidate mask into discrete CliffStructure instances.

    Pure-numpy: no Blender geometry is created here. This identifies
    connected cliff regions, extracts a lip polyline (upper edge), face
    mask (all component cells), and computes metadata. Ledges and talus
    are added by dedicated functions.
    """
    stack = state.mask_stack
    height = np.asarray(stack.height, dtype=np.float64)
    rows, cols = height.shape

    if candidate_mask is None:
        candidate_mask = build_cliff_candidate_mask(stack)

    candidate_mask = np.asarray(candidate_mask, dtype=bool)

    # Optional region scoping — drop candidates outside the region
    if region is not None:
        r_slice, c_slice = _region_to_slice(stack, region)
        region_mask = np.zeros_like(candidate_mask, dtype=bool)
        region_mask[r_slice, c_slice] = True
        candidate_mask = candidate_mask & region_mask

    labels = _label_connected_components(candidate_mask)
    unique = [int(u) for u in np.unique(labels) if u != 0]

    # Sort components by cell count descending so the largest cliffs come first
    component_sizes = [(lid, int((labels == lid).sum())) for lid in unique]
    component_sizes.sort(key=lambda x: x[1], reverse=True)

    cliffs: List[CliffStructure] = []
    for idx, (lid, size) in enumerate(component_sizes):
        if size < min_component_size:
            continue
        if len(cliffs) >= max_cliff_count:
            break
        face_mask = labels == lid
        lip_polyline = _extract_lip_polyline(face_mask, height)
        face_heights = height[face_mask]
        # World bounds for the component (x=col*cell_size, y=row*cell_size)
        rr, cc = np.where(face_mask)
        min_x = float(stack.world_origin_x + cc.min() * stack.cell_size)
        max_x = float(stack.world_origin_x + (cc.max() + 1) * stack.cell_size)
        min_y = float(stack.world_origin_y + rr.min() * stack.cell_size)
        max_y = float(stack.world_origin_y + (rr.max() + 1) * stack.cell_size)
        bounds = BBox(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

        cliff = CliffStructure(
            cliff_id=f"cliff_{state.tile_x}_{state.tile_y}_{idx:02d}",
            lip_polyline=lip_polyline,
            face_mask=face_mask.copy(),
            ledges=[],
            talus_mask=None,
            world_bounds=bounds,
            tier="hero" if idx == 0 else "secondary",
            max_height_m=float(face_heights.max()) if face_heights.size else 0.0,
            min_height_m=float(face_heights.min()) if face_heights.size else 0.0,
            cell_count=int(size),
        )
        cliffs.append(cliff)

    return cliffs


def _region_to_slice(
    stack: TerrainMaskStack,
    region: BBox,
) -> Tuple[slice, slice]:
    return region.to_cell_slice(
        world_origin_x=stack.world_origin_x,
        world_origin_y=stack.world_origin_y,
        cell_size=stack.cell_size,
        grid_shape=stack.height.shape,
    )


def _extract_lip_polyline(
    face_mask: np.ndarray,
    height: np.ndarray,
) -> np.ndarray:
    """Return an ordered (N, 2) int32 array of (row, col) lip cells.

    The lip is the set of face cells whose 4-neighborhood contains at
    least one NON-face cell that is HIGHER or equal to the face cell
    itself — i.e. the upper boundary of the cliff component.

    For simplicity we return all lip cells sorted by (row, col). Bundle
    B extension may reorder them into a contour walk.
    """
    m = np.asarray(face_mask, dtype=bool)
    h = np.asarray(height, dtype=np.float64)
    rows, cols = m.shape
    if not m.any():
        return np.zeros((0, 2), dtype=np.int32)

    # Pad face mask with False so border cells get a non-face neighbor
    padded_mask = np.pad(m, 1, mode="constant", constant_values=False)
    padded_h = np.pad(h, 1, mode="edge")

    is_lip = np.zeros_like(m, dtype=bool)
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        neighbor_mask = padded_mask[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        neighbor_h = padded_h[1 + dr : 1 + dr + rows, 1 + dc : 1 + dc + cols]
        # Lip condition: I'm a face cell AND neighbor is NOT face AND neighbor
        # is at or above my own height (i.e. I sit just below the top rim).
        is_lip |= m & (~neighbor_mask) & (neighbor_h >= h - 1e-9)

    if not is_lip.any():
        # Fallback: use the top-most row of the face mask
        rr, cc = np.where(m)
        min_r = int(rr.min())
        lip_cols = cc[rr == min_r]
        return np.stack([np.full_like(lip_cols, min_r), lip_cols], axis=1).astype(np.int32)

    rr, cc = np.where(is_lip)
    pts = np.stack([rr, cc], axis=1).astype(np.int32)
    order = np.lexsort((pts[:, 1], pts[:, 0]))
    return pts[order]


# ---------------------------------------------------------------------------
# Ledges
# ---------------------------------------------------------------------------


def add_cliff_ledges(
    cliff: CliffStructure,
    count: Optional[int] = None,
    height: Optional[np.ndarray] = None,
) -> CliffStructure:
    """Populate ``cliff.ledges`` with 1..3 horizontal interruptions.

    Ledge count scales with cliff height:
      - < 10m:  0 ledges
      - 10-20m: 1 ledge
      - 20-30m: 2 ledges
      - > 30m:  3 ledges

    When ``count`` is provided, it overrides the auto-count (still clamped
    to [0, 3]). ``height`` is the world heightmap used to place ledges at
    proportional elevations within the cliff's vertical range.
    """
    if height is None:
        return cliff  # cannot compute ledge bands without heights

    h = np.asarray(height, dtype=np.float64)
    face = cliff.face_mask
    if not face.any():
        cliff.ledges = []
        return cliff

    h_min = float(h[face].min())
    h_max = float(h[face].max())
    span = h_max - h_min

    if count is None:
        if span < 10.0:
            count = 0
        elif span < 20.0:
            count = 1
        elif span < 30.0:
            count = 2
        else:
            count = 3
    count = max(0, min(3, int(count)))

    ledges: List[np.ndarray] = []
    if count == 0 or span <= 0.0:
        cliff.ledges = ledges
        return cliff

    # Place ledges at evenly-spaced fractions of the cliff height
    fractions = [(i + 1) / (count + 1) for i in range(count)]
    band_half = max(0.75, span / (count * 4.0))  # ledge band thickness
    rr, cc = np.where(face)
    row_min = int(rr.min())
    row_max = int(rr.max())
    for frac in fractions:
        target = h_min + frac * span
        band = face & (h >= target - band_half) & (h <= target + band_half)
        if not band.any():
            # Fallback: near-vertical cliff — no face cells at intermediate
            # heights. Slice a horizontal row of the face mask at the
            # proportional row offset from the top.
            target_row = int(round(row_min + frac * (row_max - row_min)))
            band = np.zeros_like(face, dtype=bool)
            band[target_row, :] = face[target_row, :]
        if band.any():
            ledges.append(band)

    cliff.ledges = ledges
    return cliff


# ---------------------------------------------------------------------------
# Talus field
# ---------------------------------------------------------------------------


def build_talus_field(
    cliff: CliffStructure,
    stack: TerrainMaskStack,
    *,
    angle_of_repose_deg: float = 34.0,
    apron_cells: int = 3,
) -> TalusField:
    """Create a scree apron at the base of a cliff.

    The apron is the set of non-face cells within ``apron_cells`` of the
    face mask whose height is BELOW the cliff's minimum face height —
    i.e. the ground that the scree would pile onto. The apron is
    guaranteed non-overlapping with ``cliff.face_mask``.
    """
    face = np.asarray(cliff.face_mask, dtype=bool)
    h = np.asarray(stack.height, dtype=np.float64)

    if not face.any():
        empty = np.zeros_like(face, dtype=bool)
        return TalusField(
            mask=empty,
            angle_of_repose_radians=math.radians(float(angle_of_repose_deg)),
        )

    # Dilate the face mask by ``apron_cells`` cells
    dilated = face.copy()
    for _ in range(max(1, int(apron_cells))):
        padded = np.pad(dilated, 1, mode="constant", constant_values=False)
        neighbors = (
            padded[:-2, 1:-1]
            | padded[2:, 1:-1]
            | padded[1:-1, :-2]
            | padded[1:-1, 2:]
            | padded[:-2, :-2]
            | padded[:-2, 2:]
            | padded[2:, :-2]
            | padded[2:, 2:]
        )
        dilated = dilated | neighbors

    apron = dilated & ~face

    # Keep only apron cells whose height is <= cliff's minimum face height
    # (i.e. actually at the base, not floating above).
    min_face_h = float(h[face].min())
    apron &= h <= (min_face_h + 1.0)

    cliff.talus_mask = apron
    return TalusField(
        mask=apron,
        angle_of_repose_radians=math.radians(float(angle_of_repose_deg)),
    )


# ---------------------------------------------------------------------------
# Hero cliff mesh generation
# ---------------------------------------------------------------------------


def _cliff_face_mesh_spec(
    cliff: CliffStructure,
    stack: TerrainMaskStack,
    *,
    overhang_fraction: float = 0.15,
    roughness: float = 0.3,
    seed: int = 0,
) -> dict:
    """Generate a mesh spec dict for a single cliff face.

    Builds a vertical wall from the cliff's bounding box and height range.
    The wall has:
      - Irregular surface roughness derived from the seed
      - Slight overhang at the top (top leans outward by ``overhang_fraction``
        of the cliff height)
      - Per-face material zones: 0=base_rock, 1=mid_rock, 2=top_overhang

    Returns dict with ``vertices``, ``faces``, ``material_indices``,
    ``cliff_id``, ``world_bounds``.
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    h = np.asarray(stack.height, dtype=np.float64)

    bounds = cliff.world_bounds
    if bounds is None:
        return {"vertices": [], "faces": [], "material_indices": [], "cliff_id": cliff.cliff_id}

    z_min = cliff.min_height_m
    z_max = cliff.max_height_m
    z_span = z_max - z_min
    if z_span < 0.5:
        return {"vertices": [], "faces": [], "material_indices": [], "cliff_id": cliff.cliff_id}

    # Resolution based on cliff extent
    x_span = bounds.max_x - bounds.min_x
    y_span = bounds.max_y - bounds.min_y
    res_h = max(4, int(max(x_span, y_span) / stack.cell_size))
    res_v = max(4, int(z_span / 2.0))

    # We generate the cliff face along the longest horizontal axis.
    # If x_span >= y_span, cliff face runs along X; otherwise along Y.
    along_x = x_span >= y_span
    if along_x:
        u_min, u_max = bounds.min_x, bounds.max_x
        v_base = (bounds.min_y + bounds.max_y) / 2.0
    else:
        u_min, u_max = bounds.min_y, bounds.max_y
        v_base = (bounds.min_x + bounds.max_x) / 2.0

    overhang_m = z_span * float(overhang_fraction)
    vertices: list = []
    faces: list = []
    mat_indices: list = []

    for k in range(res_v + 1):
        kt = k / res_v
        z = z_min + kt * z_span

        # Overhang: top 30% leans outward
        lean = 0.0
        if kt > 0.7:
            lean_t = (kt - 0.7) / 0.3
            lean = -overhang_m * lean_t

        for i in range(res_h + 1):
            it = i / res_h
            u = u_min + it * (u_max - u_min)

            # Surface roughness
            noise = float(rng.standard_normal()) * roughness * 0.5

            if along_x:
                vx = u
                vy = v_base + lean + noise
                vz = z
            else:
                vx = v_base + lean + noise
                vy = u
                vz = z

            vertices.append((float(vx), float(vy), float(vz)))

    # Build quad faces
    for k in range(res_v):
        kt = k / res_v
        for i in range(res_h):
            v0 = k * (res_h + 1) + i
            v1 = v0 + 1
            v2 = v0 + (res_h + 1) + 1
            v3 = v0 + (res_h + 1)
            faces.append((v0, v1, v2, v3))

            # Material zone by height fraction
            if kt > 0.7:
                mat_indices.append(2)  # overhang
            elif kt > 0.3:
                mat_indices.append(1)  # mid rock
            else:
                mat_indices.append(0)  # base rock

    return {
        "vertices": vertices,
        "faces": faces,
        "material_indices": mat_indices,
        "cliff_id": cliff.cliff_id,
        "world_bounds": {
            "min_x": bounds.min_x,
            "min_y": bounds.min_y,
            "max_x": bounds.max_x,
            "max_y": bounds.max_y,
        },
        "z_range": (z_min, z_max),
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


def _ledge_mesh_spec(
    cliff: CliffStructure,
    stack: TerrainMaskStack,
    ledge_index: int,
    *,
    ledge_depth: float = 1.0,
    seed: int = 0,
) -> dict:
    """Generate a mesh spec for a single horizontal ledge on a cliff.

    Ledge geometry is a flat shelf protruding from the cliff face at the
    ledge's vertical position. Returns a dict with vertices/faces or empty
    if the ledge mask is empty.
    """
    if ledge_index >= len(cliff.ledges):
        return {"vertices": [], "faces": []}

    ledge_mask = cliff.ledges[ledge_index]
    if not ledge_mask.any():
        return {"vertices": [], "faces": []}

    h = np.asarray(stack.height, dtype=np.float64)
    bounds = cliff.world_bounds
    if bounds is None:
        return {"vertices": [], "faces": []}

    rng = np.random.default_rng(int(seed + ledge_index * 997) & 0xFFFFFFFF)

    # Get average height of the ledge band
    ledge_z = float(h[ledge_mask].mean())

    rr, cc = np.where(ledge_mask)
    if len(rr) == 0:
        return {"vertices": [], "faces": []}

    # Build a simple shelf strip along the ledge
    # Sort by column for a left-to-right strip
    order = np.argsort(cc)
    rr = rr[order]
    cc = cc[order]

    # Subsample to reasonable resolution
    stride = max(1, len(rr) // 20)
    indices = list(range(0, len(rr), stride))
    if indices[-1] != len(rr) - 1:
        indices.append(len(rr) - 1)

    vertices: list = []
    faces: list = []

    for idx in indices:
        wx = stack.world_origin_x + float(cc[idx]) * stack.cell_size
        wy = stack.world_origin_y + float(rr[idx]) * stack.cell_size
        noise = float(rng.standard_normal()) * 0.1

        # Inner edge (against cliff) and outer edge (protruding)
        vertices.append((wx, wy + noise, ledge_z))
        vertices.append((wx, wy - ledge_depth + noise, ledge_z))

    for i in range(len(indices) - 1):
        v0 = i * 2
        v1 = v0 + 1
        v2 = v0 + 3
        v3 = v0 + 2
        faces.append((v0, v1, v2, v3))

    return {
        "vertices": vertices,
        "faces": faces,
        "ledge_z": ledge_z,
        "vertex_count": len(vertices),
        "face_count": len(faces),
    }


def insert_hero_cliff_meshes(
    state: TerrainPipelineState,
    cliffs: List[CliffStructure],
) -> List[str]:
    """Generate mesh specs for hero-tier cliffs and record on side_effects.

    For each hero cliff, generates:
      - A cliff face mesh spec (vertical wall with overhang + roughness)
      - A ledge mesh spec per ledge
      - A talus scatter region spec

    Mesh specs are appended to ``state.side_effects`` as structured dicts
    (prefixed with ``cliff_mesh_spec:``). String intents are also returned
    for backward-compatible pipeline integration tests.
    """
    from .terrain_pipeline import derive_pass_seed  # lazy to dodge circular import

    intents: List[str] = []
    for cliff in cliffs:
        if cliff.tier != "hero":
            continue

        seed = derive_pass_seed(
            state.intent.seed,
            f"cliff_mesh_{cliff.cliff_id}",
            state.tile_x,
            state.tile_y,
            None,
        )

        # Generate the main cliff face
        face_spec = _cliff_face_mesh_spec(
            cliff, state.mask_stack,
            overhang_fraction=0.15,
            roughness=0.3,
            seed=seed,
        )
        if face_spec["vertices"]:
            state.side_effects.append(
                f"cliff_mesh_spec:{cliff.cliff_id}:face:"
                f"verts={face_spec['vertex_count']}:faces={face_spec['face_count']}"
            )

        # Generate ledge meshes
        for li in range(len(cliff.ledges)):
            ledge_spec = _ledge_mesh_spec(
                cliff, state.mask_stack, li,
                ledge_depth=1.0,
                seed=seed,
            )
            if ledge_spec["vertices"]:
                state.side_effects.append(
                    f"cliff_mesh_spec:{cliff.cliff_id}:ledge_{li}:"
                    f"verts={ledge_spec['vertex_count']}"
                )

        # Record talus scatter region (not geometry — downstream scatters rocks)
        if cliff.talus_mask is not None and cliff.talus_mask.any():
            talus_cells = int(cliff.talus_mask.sum())
            state.side_effects.append(
                f"cliff_talus_scatter:{cliff.cliff_id}:cells={talus_cells}"
            )

        intent = (
            f"insert_hero_cliff_mesh:{cliff.cliff_id}:"
            f"cells={cliff.cell_count}:"
            f"z={cliff.min_height_m:.2f}..{cliff.max_height_m:.2f}"
        )
        state.side_effects.append(intent)
        intents.append(intent)
    return intents


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_cliff_readability(
    cliff: CliffStructure,
    stack: TerrainMaskStack,
    *,
    min_lip_length: int = 3,
    min_face_cells: int = 20,
    require_ledges: bool = False,
) -> List[ValidationIssue]:
    """Return a list of ValidationIssue covering lip / face / ledge presence."""
    issues: List[ValidationIssue] = []

    if cliff.face_mask is None or int(cliff.face_mask.sum()) < int(min_face_cells):
        issues.append(
            ValidationIssue(
                code="CLIFF_FACE_TOO_SMALL",
                severity="hard",
                affected_feature=cliff.cliff_id,
                message=(
                    f"cliff face only has "
                    f"{0 if cliff.face_mask is None else int(cliff.face_mask.sum())} cells "
                    f"(< {min_face_cells})"
                ),
            )
        )

    if cliff.lip_polyline is None or cliff.lip_polyline.shape[0] < int(min_lip_length):
        issues.append(
            ValidationIssue(
                code="CLIFF_LIP_MISSING",
                severity="hard",
                affected_feature=cliff.cliff_id,
                message=(
                    f"cliff lip polyline has "
                    f"{0 if cliff.lip_polyline is None else int(cliff.lip_polyline.shape[0])} "
                    f"points (< {min_lip_length})"
                ),
            )
        )

    if require_ledges and not cliff.ledges:
        issues.append(
            ValidationIssue(
                code="CLIFF_NO_LEDGES",
                severity="soft",
                affected_feature=cliff.cliff_id,
                message="cliff has no horizontal ledges",
            )
        )

    if cliff.talus_mask is not None and cliff.face_mask is not None:
        overlap = int((cliff.talus_mask & cliff.face_mask).sum())
        if overlap > 0:
            issues.append(
                ValidationIssue(
                    code="CLIFF_TALUS_OVERLAPS_FACE",
                    severity="hard",
                    affected_feature=cliff.cliff_id,
                    message=f"talus mask overlaps face mask in {overlap} cells",
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Pass wiring
# ---------------------------------------------------------------------------


def pass_cliffs(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle B cliffs pass.

    Contract
    --------
    Consumes: slope, saliency_macro (optional), ridge (optional)
    Produces: cliff_candidate
    Respects protected zones: yes (via hero_exclusion + candidate filter)
    Requires scene read: no
    """
    from .terrain_pipeline import derive_pass_seed  # lazy to dodge circular import

    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: List[ValidationIssue] = []

    seed = derive_pass_seed(
        state.intent.seed,
        "cliffs",
        state.tile_x,
        state.tile_y,
        region,
    )

    # 1. Build the candidate mask
    candidate = build_cliff_candidate_mask(stack)

    # Region scope: only cliffs whose centre lies inside ``region`` count
    if region is not None:
        r_slice, c_slice = _region_to_slice(stack, region)
        region_mask = np.zeros_like(candidate, dtype=bool)
        region_mask[r_slice, c_slice] = True
        candidate = candidate & region_mask

    # 2. Protected zones — mask out forbidden cells
    if state.intent.protected_zones:
        protected = _protected_mask_for_cliffs(state, candidate.shape)
        candidate = candidate & ~protected

    # 3. Populate cliff_candidate on the stack
    stack.set("cliff_candidate", candidate.astype(bool), "cliffs")

    # 4. Carve the structure list
    cliffs = carve_cliff_system(state, region, candidate_mask=candidate)

    # 5. Add ledges + talus per cliff
    for cliff in cliffs:
        add_cliff_ledges(cliff, height=stack.height)
        build_talus_field(cliff, stack)

    # 6. Record intent for hero mesh insertion (no geometry yet)
    insert_hero_cliff_meshes(state, cliffs)

    # 7. Record structures as side effects (so downstream bundles can find them)
    for cliff in cliffs:
        state.side_effects.append(
            f"cliff_structure:{cliff.cliff_id}:"
            f"face_cells={cliff.cell_count}:"
            f"ledges={len(cliff.ledges)}:"
            f"tier={cliff.tier}"
        )

    # 8. Validate each cliff
    for cliff in cliffs:
        issues.extend(validate_cliff_readability(cliff, stack))

    hard_issues = [i for i in issues if i.is_hard()]
    status = "ok" if not hard_issues else "warning"

    return PassResult(
        pass_name="cliffs",
        status=status,
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("slope", "saliency_macro"),
        produced_channels=("cliff_candidate",),
        metrics={
            "candidate_cells": int(candidate.sum()),
            "cliff_count": len(cliffs),
            "hero_cliff_count": sum(1 for c in cliffs if c.tier == "hero"),
            "total_ledges": sum(len(c.ledges) for c in cliffs),
            "seed_used": seed,
        },
        issues=issues,
        side_effects=[
            f"cliff:{c.cliff_id}" for c in cliffs
        ],
    )


def _protected_mask_for_cliffs(
    state: TerrainPipelineState,
    shape: Tuple[int, int],
) -> np.ndarray:
    """Build a protected-zone mask for the cliffs pass."""
    stack = state.mask_stack
    mask = np.zeros(shape, dtype=bool)
    if not state.intent.protected_zones:
        return mask
    rows, cols = shape
    ys = stack.world_origin_y + (np.arange(rows) + 0.5) * stack.cell_size
    xs = stack.world_origin_x + (np.arange(cols) + 0.5) * stack.cell_size
    xg, yg = np.meshgrid(xs, ys)
    for zone in state.intent.protected_zones:
        if zone.permits("cliffs"):
            continue
        inside = (
            (xg >= zone.bounds.min_x)
            & (xg <= zone.bounds.max_x)
            & (yg >= zone.bounds.min_y)
            & (yg <= zone.bounds.max_y)
        )
        mask |= inside
    return mask


def register_bundle_b_passes() -> None:
    """Register the Bundle B cliff pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="cliffs",
            func=pass_cliffs,
            requires_channels=("slope",),
            produces_channels=("cliff_candidate",),
            seed_namespace="cliffs",
            requires_scene_read=False,
            may_modify_geometry=False,
            description="Bundle B — cliff anatomy (lip + face + ledges + talus).",
        )
    )


__all__ = [
    "CliffStructure",
    "TalusField",
    "build_cliff_candidate_mask",
    "carve_cliff_system",
    "add_cliff_ledges",
    "build_talus_field",
    "insert_hero_cliff_meshes",
    "validate_cliff_readability",
    "pass_cliffs",
    "register_bundle_b_passes",
    "_cliff_face_mesh_spec",
    "_ledge_mesh_spec",
]
