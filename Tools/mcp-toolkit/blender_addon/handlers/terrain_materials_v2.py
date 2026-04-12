"""Bundle B — Slope/altitude/curvature/wetness-driven material rules.

Replaces biome-name keyed material assignment with vectorised per-cell
splatmap weights driven by the mask stack. DOES NOT modify the legacy
``terrain_materials`` module — it coexists as ``_v2`` so old tests stay
green while Bundle B callers opt in.

Agent protocol compliance:
- Rule 3: writes ``splatmap_weights_layer`` + ``material_weights`` to
  the ``TerrainMaskStack``
- Rule 6: altitude gates are world meters on the Z axis (stack.height)
- Rule 7: ``splatmap_weights_layer`` is the Unity consumer channel
- Rule 10: no ``np.clip(..., 0, 1)`` on world heights (only on weights)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MaterialChannel:
    """A single material layer in the splatmap.

    Each channel declares an envelope over slope / altitude / curvature /
    wetness. The weight for each cell is the product of smoothstep ramps
    inside each envelope. All thresholds are world-unit (radians for
    slope, world meters for altitude).
    """

    channel_id: str
    base_color_hex: str = "#808080"
    roughness: float = 0.8
    metallic: float = 0.0
    triplanar: bool = False
    # Slope envelope (radians)
    slope_min_rad: float = 0.0
    slope_max_rad: float = math.pi / 2.0
    slope_falloff_rad: float = math.radians(5.0)
    # Altitude envelope (world meters, Z up)
    altitude_min_m: float = -1e9
    altitude_max_m: float = 1e9
    altitude_falloff_m: float = 5.0
    # Curvature envelope (unitless, signed Laplacian)
    curvature_min: float = -1e9
    curvature_max: float = 1e9
    # Wetness envelope (0..1)
    wetness_min: float = 0.0
    wetness_max: float = 1.0
    # Base multiplier — higher = channel "wins" in overlap regions
    base_weight: float = 1.0


@dataclass
class MaterialRuleSet:
    """Ordered tuple of MaterialChannel layers + a default fallback layer.

    The ``default_channel_id`` identifies the layer that picks up cells
    where every rule returned zero weight. It must be present in
    ``channels``.
    """

    channels: Tuple[MaterialChannel, ...] = field(default_factory=tuple)
    default_channel_id: str = "ground"

    def __post_init__(self) -> None:
        ids = [c.channel_id for c in self.channels]
        if len(ids) != len(set(ids)):
            raise ValueError(f"MaterialRuleSet channel_ids must be unique: {ids}")
        if self.default_channel_id not in ids:
            raise ValueError(
                f"default_channel_id={self.default_channel_id!r} "
                f"not in channels {ids}"
            )

    def index_of(self, channel_id: str) -> int:
        for i, c in enumerate(self.channels):
            if c.channel_id == channel_id:
                return i
        raise KeyError(channel_id)


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------


def default_dark_fantasy_rules() -> MaterialRuleSet:
    """Return the default Bundle B rule set: 5 channels.

    ground   — low slope, any altitude (the fallback)
    cliff    — high slope, triplanar
    scree    — moderate slope, low altitude, near the base of cliffs
    wet_rock — any slope with wetness > 0.3
    snow     — altitude > snow line
    """
    channels = (
        MaterialChannel(
            channel_id="ground",
            base_color_hex="#5a4e3a",
            roughness=0.9,
            triplanar=False,
            slope_min_rad=0.0,
            slope_max_rad=math.radians(30.0),
            slope_falloff_rad=math.radians(8.0),
            base_weight=1.0,
        ),
        MaterialChannel(
            channel_id="cliff",
            base_color_hex="#3c3630",
            roughness=0.85,
            triplanar=True,
            slope_min_rad=math.radians(40.0),
            slope_max_rad=math.pi / 2.0,
            slope_falloff_rad=math.radians(10.0),
            base_weight=1.2,
        ),
        MaterialChannel(
            channel_id="scree",
            base_color_hex="#6b6055",
            roughness=0.95,
            triplanar=False,
            slope_min_rad=math.radians(25.0),
            slope_max_rad=math.radians(45.0),
            slope_falloff_rad=math.radians(6.0),
            altitude_max_m=200.0,
            altitude_falloff_m=20.0,
            base_weight=0.8,
        ),
        MaterialChannel(
            channel_id="wet_rock",
            base_color_hex="#2c2a28",
            roughness=0.35,
            triplanar=True,
            slope_min_rad=math.radians(15.0),
            slope_max_rad=math.pi / 2.0,
            slope_falloff_rad=math.radians(8.0),
            wetness_min=0.3,
            wetness_max=1.0,
            base_weight=1.5,
        ),
        MaterialChannel(
            channel_id="snow",
            base_color_hex="#e8ecef",
            roughness=0.6,
            triplanar=False,
            slope_min_rad=0.0,
            slope_max_rad=math.radians(50.0),
            slope_falloff_rad=math.radians(8.0),
            altitude_min_m=250.0,
            altitude_falloff_m=30.0,
            base_weight=1.3,
        ),
    )
    return MaterialRuleSet(channels=channels, default_channel_id="ground")


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------


def _smoothstep_band(
    value: np.ndarray,
    lo: float,
    hi: float,
    falloff: float,
) -> np.ndarray:
    """Return a [0,1] mask that is 1 inside [lo, hi] and ramps to 0 over falloff."""
    f = max(float(falloff), 1e-9)
    # Ramp up on the low side, ramp down on the high side
    up = np.clip((value - (lo - f)) / f, 0.0, 1.0)
    down = np.clip(((hi + f) - value) / f, 0.0, 1.0)
    return up * down


def compute_slope_material_weights(
    stack: TerrainMaskStack,
    rules: Optional[MaterialRuleSet] = None,
) -> np.ndarray:
    """Return (H, W, L) float32 splatmap weights, normalized to sum=1.

    Fully vectorized — no Python per-cell loops. Computes each channel's
    envelope in parallel using numpy broadcast, then normalizes weights
    across the layer axis.
    """
    if rules is None:
        rules = default_dark_fantasy_rules()

    slope = stack.get("slope")
    if slope is None:
        raise KeyError("compute_slope_material_weights requires 'slope' on the stack")
    slope = np.asarray(slope, dtype=np.float64)
    height = np.asarray(stack.height, dtype=np.float64)

    curvature = stack.get("curvature")
    if curvature is None:
        curvature = np.zeros_like(slope)
    else:
        curvature = np.asarray(curvature, dtype=np.float64)

    wetness = stack.get("wetness")
    if wetness is None:
        wetness = np.zeros_like(slope)
    else:
        wetness = np.asarray(wetness, dtype=np.float64)

    L = len(rules.channels)
    H, W = slope.shape
    weights = np.zeros((H, W, L), dtype=np.float32)

    for idx, ch in enumerate(rules.channels):
        slope_w = _smoothstep_band(
            slope, ch.slope_min_rad, ch.slope_max_rad, ch.slope_falloff_rad
        )
        alt_w = _smoothstep_band(
            height, ch.altitude_min_m, ch.altitude_max_m, ch.altitude_falloff_m
        )
        curv_w = np.where(
            (curvature >= ch.curvature_min) & (curvature <= ch.curvature_max),
            1.0,
            0.0,
        )
        wet_w = np.where(
            (wetness >= ch.wetness_min) & (wetness <= ch.wetness_max),
            1.0,
            0.0,
        )
        combined = ch.base_weight * slope_w * alt_w * curv_w * wet_w
        weights[:, :, idx] = combined.astype(np.float32)

    # Fallback: any cell whose total weight is 0 gets 1.0 on the default layer
    total = weights.sum(axis=2)
    default_idx = rules.index_of(rules.default_channel_id)
    empty = total <= 1e-9
    if empty.any():
        weights[empty, default_idx] = 1.0
        total = weights.sum(axis=2)

    # Normalize weights to sum to 1 per cell
    weights /= total[:, :, None]

    return weights.astype(np.float32)


# ---------------------------------------------------------------------------
# Pass wiring
# ---------------------------------------------------------------------------


def pass_materials(
    state: TerrainPipelineState,
    region: Optional[BBox],
    *,
    rules: Optional[MaterialRuleSet] = None,
) -> PassResult:
    """Bundle B materials pass.

    Contract
    --------
    Consumes: slope, height, curvature (optional), wetness (optional)
    Produces: splatmap_weights_layer, material_weights
    Respects protected zones: yes (region mask only)
    Requires scene read: no
    """
    from .terrain_pipeline import derive_pass_seed

    t0 = time.perf_counter()
    stack = state.mask_stack

    seed = derive_pass_seed(
        state.intent.seed,
        "materials_v2",
        state.tile_x,
        state.tile_y,
        region,
    )

    if rules is None:
        rules = default_dark_fantasy_rules()

    new_weights = compute_slope_material_weights(stack, rules)

    # Region scoping: preserve existing weights outside the region
    if region is not None:
        existing = stack.get("splatmap_weights_layer")
        r_slice, c_slice = region.to_cell_slice(
            world_origin_x=stack.world_origin_x,
            world_origin_y=stack.world_origin_y,
            cell_size=stack.cell_size,
            grid_shape=stack.height.shape,
        )
        if existing is not None and np.asarray(existing).shape == new_weights.shape:
            merged = np.asarray(existing, dtype=np.float32).copy()
            merged[r_slice, c_slice, :] = new_weights[r_slice, c_slice, :]
            new_weights = merged
        else:
            # No prior weights — zero outside region, new weights inside
            merged = np.zeros_like(new_weights)
            merged[r_slice, c_slice, :] = new_weights[r_slice, c_slice, :]
            # Leave outside cells as zero-sum (downstream code can treat
            # that as "not authored yet")
            new_weights = merged

    stack.set("splatmap_weights_layer", new_weights, "materials_v2")
    stack.set("material_weights", new_weights, "materials_v2")

    # Aggregate metrics
    per_layer_coverage = new_weights.mean(axis=(0, 1))
    dominant = int(per_layer_coverage.argmax())
    metrics = {
        "layer_count": int(new_weights.shape[2]),
        "layer_ids": [c.channel_id for c in rules.channels],
        "dominant_layer": rules.channels[dominant].channel_id,
        "dominant_coverage": float(per_layer_coverage[dominant]),
        "seed_used": seed,
    }
    for i, c in enumerate(rules.channels):
        metrics[f"coverage_{c.channel_id}"] = float(per_layer_coverage[i])

    return PassResult(
        pass_name="materials_v2",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("slope", "height"),
        produced_channels=("splatmap_weights_layer", "material_weights"),
        metrics=metrics,
    )


def register_bundle_b_material_passes() -> None:
    """Register the Bundle B materials pass on TerrainPassController."""
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="materials_v2",
            func=pass_materials,
            requires_channels=("slope", "height"),
            produces_channels=("splatmap_weights_layer", "material_weights"),
            seed_namespace="materials_v2",
            requires_scene_read=False,
            may_modify_geometry=False,
            description="Bundle B — slope/altitude/wetness-driven splatmap materials.",
        )
    )


# ---------------------------------------------------------------------------
# DAG-to-Blender bridge — apply splatmap weights to mesh vertex colors
# ---------------------------------------------------------------------------


def dag_weights_to_rgba(
    weights: np.ndarray,
    rules: Optional[MaterialRuleSet] = None,
) -> np.ndarray:
    """Convert (H, W, L) DAG splatmap weights to (H, W, 4) RGBA for Blender.

    Maps L-channel weights to the 4-channel splatmap used by the Blender
    terrain material shader:
        R = ground channel weight
        G = scree + partial cliff (slope proxy)
        B = cliff channel weight
        A = wet_rock + snow (special proxy)

    Unknown channel IDs are distributed evenly across R/G/B.

    Args:
        weights: (H, W, L) float32 splatmap weights from v2 engine.
        rules: MaterialRuleSet defining channel IDs. If None, uses default.

    Returns:
        (H, W, 4) float32 RGBA array, normalized to sum=1 per cell.
    """
    if rules is None:
        rules = default_dark_fantasy_rules()

    w = np.asarray(weights, dtype=np.float32)
    H, W, L = w.shape
    rgba = np.zeros((H, W, 4), dtype=np.float32)

    # Map each channel to RGBA based on its ID
    channel_map = {
        "ground": 0,   # R
        "scree": 1,    # G (slope proxy)
        "cliff": 2,    # B
        "wet_rock": 3,  # A (special)
        "snow": 3,      # A (special)
    }

    for idx, ch in enumerate(rules.channels):
        rgba_idx = channel_map.get(ch.channel_id)
        if rgba_idx is not None:
            rgba[:, :, rgba_idx] += w[:, :, idx]
        else:
            # Unknown channel — distribute to ground (R)
            rgba[:, :, 0] += w[:, :, idx]

    # Normalize
    total = rgba.sum(axis=2, keepdims=True)
    total = np.where(total < 1e-9, 1.0, total)
    rgba /= total

    return rgba


def apply_dag_splatmap_to_mesh(
    stack_or_weights: "np.ndarray | TerrainMaskStack",
    object_name: str,
    *,
    rules: Optional[MaterialRuleSet] = None,
    biome_name: str = "thornwood_forest",
    vcol_layer_name: str = "VB_TerrainSplatmap",
) -> dict:
    """Apply DAG splatmap weights from the mask stack to a Blender mesh.

    Bridges the terrain pipeline DAG output to Blender's vertex color system
    and creates/assigns the biome terrain material. This is the missing link
    between ``pass_materials`` (which writes to the mask stack) and the
    Blender scene.

    Args:
        stack_or_weights: Either a TerrainMaskStack (reads "splatmap_weights_layer")
            or a raw (H, W, L) numpy array of weights.
        object_name: Blender object name to apply to.
        rules: MaterialRuleSet for channel mapping. Default = dark fantasy 5-channel.
        biome_name: Biome for material creation.
        vcol_layer_name: Vertex color attribute name.

    Returns:
        Dict with status, channel coverage stats.

    Raises:
        RuntimeError: If bpy is not available.
        KeyError: If stack has no splatmap_weights_layer.
    """
    try:
        import bpy
    except ImportError:
        raise RuntimeError("apply_dag_splatmap_to_mesh requires Blender (bpy)")

    # Extract weights
    if isinstance(stack_or_weights, np.ndarray):
        raw_weights = stack_or_weights
    else:
        # It's a TerrainMaskStack
        raw_weights = stack_or_weights.get("splatmap_weights_layer")
        if raw_weights is None:
            raise KeyError(
                "No 'splatmap_weights_layer' on mask stack. "
                "Run pass_materials first."
            )
        raw_weights = np.asarray(raw_weights, dtype=np.float32)

    # Convert to RGBA
    rgba = dag_weights_to_rgba(raw_weights, rules)

    # Get Blender object
    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object '{object_name}' not found")
    if obj.type != "MESH":
        raise ValueError(f"Object '{object_name}' is not a mesh")
    mesh = obj.data

    # Create/get vertex color layer
    if vcol_layer_name not in mesh.color_attributes:
        mesh.color_attributes.new(
            name=vcol_layer_name, type="FLOAT_COLOR", domain="CORNER"
        )
    vcol = mesh.color_attributes[vcol_layer_name]

    # Map vertex positions to grid cells and write vertex colors
    H, W = rgba.shape[:2]
    verts = mesh.vertices
    if len(verts) == 0:
        return {"status": "success", "vertices_painted": 0}

    # Build bounding box for vertex -> grid mapping
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_range = max(x_max - x_min, 1e-9)
    y_range = max(y_max - y_min, 1e-9)

    # Pre-compute per-vertex RGBA from grid
    vert_colors = []
    for v in verts:
        u = (v.co.x - x_min) / x_range
        v_coord = (v.co.y - y_min) / y_range
        ri = int(max(0, min(H - 1, v_coord * (H - 1))))
        ci = int(max(0, min(W - 1, u * (W - 1))))
        vert_colors.append(tuple(float(x) for x in rgba[ri, ci]))

    # Write per-loop vertex colors
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index
            vcol.data[li].color = vert_colors[vi]

    mesh.update()

    # Create and assign terrain material
    from .terrain_materials import create_biome_terrain_material
    create_biome_terrain_material(biome_name, object_name)

    # Coverage stats
    per_channel = rgba.mean(axis=(0, 1))
    return {
        "status": "success",
        "object_name": object_name,
        "vertices_painted": len(verts),
        "grid_shape": (H, W),
        "coverage_R_ground": float(per_channel[0]),
        "coverage_G_slope": float(per_channel[1]),
        "coverage_B_cliff": float(per_channel[2]),
        "coverage_A_special": float(per_channel[3]),
    }


__all__ = [
    "MaterialChannel",
    "MaterialRuleSet",
    "default_dark_fantasy_rules",
    "compute_slope_material_weights",
    "pass_materials",
    "register_bundle_b_material_passes",
    "dag_weights_to_rgba",
    "apply_dag_splatmap_to_mesh",
]
