"""Bundle I — terrain_stratigraphy.

Stratigraphic rock layering: each tile has an ordered stack of
``StratigraphyLayer`` with hardness, thickness, dip, and azimuth. The pass
populates ``stack.strata_orientation`` (H, W, 3 unit vector) and
``stack.rock_hardness`` (H, W float32) based on which layer the cell's
elevation falls into. A ``apply_differential_erosion`` helper returns a
height delta where softer layers erode faster — harder caprock survives,
producing mesas and layered cliffs.

Pure numpy, no bpy. Z-up, world meters. All seeding is deterministic via
``derive_pass_seed``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
    ValidationIssue,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StratigraphyLayer:
    """One rock stratum in a stratigraphic stack.

    hardness : float in [0, 1] — 0 = loose sediment, 1 = indurated caprock
    thickness_m : world-meter vertical thickness of the layer
    dip_rad : angle from horizontal (0 = flat layer, pi/4 = 45° tilted)
    azimuth_rad : compass bearing of dip direction (0 = +X, pi/2 = +Y)
    color_hex : optional visualizer tag, not used by the passes themselves
    """

    layer_id: str
    hardness: float
    thickness_m: float
    dip_rad: float = 0.0
    azimuth_rad: float = 0.0
    color_hex: str = "#888888"

    def __post_init__(self) -> None:
        if not (0.0 <= self.hardness <= 1.0):
            raise ValueError(
                f"StratigraphyLayer.hardness must be in [0,1], got {self.hardness}"
            )
        if self.thickness_m <= 0.0:
            raise ValueError(
                f"StratigraphyLayer.thickness_m must be > 0, got {self.thickness_m}"
            )


@dataclass
class StratigraphyStack:
    """Ordered stratigraphic column, bottom-to-top.

    ``base_elevation_m`` is the world-Z elevation (meters) of the bottom
    of layer 0. ``layers[0]`` is the oldest / deepest rock; subsequent
    layers sit on top of it.
    """

    base_elevation_m: float = 0.0
    layers: List[StratigraphyLayer] = field(default_factory=list)

    def total_thickness(self) -> float:
        return float(sum(L.thickness_m for L in self.layers))

    def layer_for_elevation(self, elevation_m: float) -> Optional[StratigraphyLayer]:
        """Return the stratum whose world-Z band contains ``elevation_m``.

        Cells above the top of the stack return the topmost layer; cells
        below the base return the bottom layer. This makes the function
        total — every elevation maps to some layer.
        """
        if not self.layers:
            return None
        z = elevation_m - self.base_elevation_m
        if z <= 0.0:
            return self.layers[0]
        running = 0.0
        for layer in self.layers:
            running += layer.thickness_m
            if z <= running:
                return layer
        return self.layers[-1]


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------


def compute_strata_orientation(
    stack: TerrainMaskStack,
    strat_stack: StratigraphyStack,
) -> np.ndarray:
    """Populate ``stack.strata_orientation`` (H, W, 3 unit vector).

    The orientation vector is the bedding-plane normal in world space,
    derived from the dip + azimuth of the layer each cell belongs to.
    Horizontal strata (dip = 0) yield ``(0, 0, 1)``; dipped strata tilt
    proportionally in the azimuth direction.
    """
    if stack.height is None:
        raise ValueError("compute_strata_orientation requires stack.height")
    if not strat_stack.layers:
        raise ValueError("StratigraphyStack must have at least one layer")

    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape
    orientation = np.zeros((H, W, 3), dtype=np.float32)

    # Build a per-layer band lookup once (fast path). We vectorize by
    # classifying each cell's (elev - base) into a layer index via
    # cumulative thicknesses.
    thicks = np.array([L.thickness_m for L in strat_stack.layers], dtype=np.float64)
    bounds = np.concatenate(([0.0], np.cumsum(thicks)))  # length N+1
    dips = np.array([L.dip_rad for L in strat_stack.layers], dtype=np.float64)
    azs = np.array([L.azimuth_rad for L in strat_stack.layers], dtype=np.float64)

    z = (h - strat_stack.base_elevation_m).clip(min=0.0)
    # np.searchsorted gives the index of the first bound > z. Subtract 1
    # and clip to [0, N-1] so cells above the top use the top layer.
    idx = np.searchsorted(bounds, z, side="right") - 1
    idx = np.clip(idx, 0, len(strat_stack.layers) - 1)

    cell_dip = dips[idx]
    cell_az = azs[idx]

    # Bedding-plane normal: start with +Z, rotate by dip around axis
    # perpendicular to azimuth. Equivalent closed form:
    #   n = (sin(dip)*cos(az), sin(dip)*sin(az), cos(dip))
    sin_d = np.sin(cell_dip)
    cos_d = np.cos(cell_dip)
    nx = sin_d * np.cos(cell_az)
    ny = sin_d * np.sin(cell_az)
    nz = cos_d

    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    norm = np.where(norm < 1e-9, 1.0, norm)
    orientation[..., 0] = (nx / norm).astype(np.float32)
    orientation[..., 1] = (ny / norm).astype(np.float32)
    orientation[..., 2] = (nz / norm).astype(np.float32)

    stack.set("strata_orientation", orientation, "stratigraphy")
    return orientation


def compute_rock_hardness(
    stack: TerrainMaskStack,
    strat_stack: StratigraphyStack,
) -> np.ndarray:
    """Populate ``stack.rock_hardness`` from elevation → layer mapping.

    Returns a (H, W) float32 array in [0, 1]. Cells at elevations
    inside harder layers carry higher values, so downstream passes
    (erosion, cliffs) can modulate their rates.
    """
    if stack.height is None:
        raise ValueError("compute_rock_hardness requires stack.height")
    if not strat_stack.layers:
        raise ValueError("StratigraphyStack must have at least one layer")

    h = np.asarray(stack.height, dtype=np.float64)
    thicks = np.array([L.thickness_m for L in strat_stack.layers], dtype=np.float64)
    bounds = np.concatenate(([0.0], np.cumsum(thicks)))
    hardness_vals = np.array(
        [L.hardness for L in strat_stack.layers], dtype=np.float64
    )

    z = (h - strat_stack.base_elevation_m).clip(min=0.0)
    idx = np.searchsorted(bounds, z, side="right") - 1
    idx = np.clip(idx, 0, len(strat_stack.layers) - 1)

    hardness = hardness_vals[idx].astype(np.float32)
    stack.set("rock_hardness", hardness, "stratigraphy")
    return hardness


def apply_differential_erosion(stack: TerrainMaskStack) -> np.ndarray:
    """Compute a height delta where softer layers erode faster.

    Harder cells survive (delta ≈ 0). Softer cells lose elevation
    proportional to ``(1 - hardness)``. This is returned — it is NOT
    applied in place — so the caller can choose to add it to
    ``stack.height`` via ``stack.set``.

    Returns a (H, W) float64 array of signed meter deltas (negative = erosion).
    """
    if stack.rock_hardness is None:
        raise ValueError(
            "apply_differential_erosion requires stack.rock_hardness "
            "(call compute_rock_hardness first)"
        )
    if stack.height is None:
        raise ValueError("apply_differential_erosion requires stack.height")

    hardness = np.asarray(stack.rock_hardness, dtype=np.float64)
    H, W = hardness.shape

    # Per-cell susceptibility
    soft = 1.0 - np.clip(hardness, 0.0, 1.0)

    # Scale by local height-above-minimum so valleys don't deepen further
    h = np.asarray(stack.height, dtype=np.float64)
    hmin = float(h.min()) if h.size else 0.0
    relief = np.clip(h - hmin, 0.0, None)
    rel_span = float(relief.max()) if relief.max() > 0 else 1.0
    relief_norm = relief / rel_span

    # Max erosion amount: up to 5% of local relief for fully soft cells
    max_drop = 0.05 * rel_span
    delta = -soft * relief_norm * max_drop
    return delta


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


def _default_strat_stack_from_hints(hints: dict) -> StratigraphyStack:
    """Build a default 4-layer stack if intent.composition_hints doesn't provide one."""
    user_layers = hints.get("stratigraphy_layers")
    if user_layers:
        layers = [StratigraphyLayer(**L) for L in user_layers]
        base = float(hints.get("stratigraphy_base_elevation_m", 0.0))
        return StratigraphyStack(base_elevation_m=base, layers=layers)

    # Default column: shale → sandstone → limestone (caprock) → soil
    return StratigraphyStack(
        base_elevation_m=float(hints.get("stratigraphy_base_elevation_m", -50.0)),
        layers=[
            StratigraphyLayer("shale", hardness=0.25, thickness_m=30.0),
            StratigraphyLayer("sandstone", hardness=0.55, thickness_m=40.0),
            StratigraphyLayer("limestone_caprock", hardness=0.90, thickness_m=30.0),
            StratigraphyLayer("soil", hardness=0.15, thickness_m=200.0),
        ],
    )


def pass_stratigraphy(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle I pass: populate rock_hardness + strata_orientation.

    Consumes: height
    Produces: rock_hardness, strata_orientation
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: List[ValidationIssue] = []

    hints = state.intent.composition_hints if state.intent else {}
    strat_stack = _default_strat_stack_from_hints(dict(hints))

    hardness = compute_rock_hardness(stack, strat_stack)
    _orientation = compute_strata_orientation(stack, strat_stack)

    metrics = {
        "layer_count": len(strat_stack.layers),
        "hardness_mean": float(hardness.mean()),
        "hardness_min": float(hardness.min()),
        "hardness_max": float(hardness.max()),
        "strata_total_thickness_m": float(strat_stack.total_thickness()),
    }

    return PassResult(
        pass_name="stratigraphy",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("rock_hardness", "strata_orientation"),
        metrics=metrics,
        issues=issues,
    )


__all__ = [
    "StratigraphyLayer",
    "StratigraphyStack",
    "compute_strata_orientation",
    "compute_rock_hardness",
    "apply_differential_erosion",
    "pass_stratigraphy",
]
