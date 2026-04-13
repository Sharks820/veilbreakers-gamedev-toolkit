"""Bundle I — terrain_karst.

Karst hydrology: detects soluble-rock regions (using rock_hardness as a
proxy for limestone) and spawns karst features — sinkholes, cenotes,
disappearing streams, poljes. ``carve_karst_features`` returns a height
delta for the caller to apply.

Pure numpy, no bpy. Z-up, world meters.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .terrain_pipeline import derive_pass_seed
from .terrain_semantics import (
    BBox,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class KarstFeature:
    """One karst landform instance."""

    feature_id: str
    kind: str  # "sinkhole" | "disappearing_stream" | "cenote" | "polje"
    world_pos: Tuple[float, float, float]
    radius_m: float

    def __post_init__(self) -> None:
        valid = ("sinkhole", "disappearing_stream", "cenote", "polje")
        if self.kind not in valid:
            raise ValueError(
                f"KarstFeature.kind must be one of {valid}, got {self.kind!r}"
            )
        if self.radius_m <= 0.0:
            raise ValueError(
                f"KarstFeature.radius_m must be > 0, got {self.radius_m}"
            )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_karst_candidates(
    stack: TerrainMaskStack,
    hardness_threshold: float = 0.5,
) -> List[KarstFeature]:
    """Return karst candidate features from soluble-rock regions.

    Heuristic: cells with ``rock_hardness`` in the moderate range
    [0.4, hardness_threshold+0.1] are limestone-like and can develop
    karst. Places one feature per distinct low-elevation cluster.
    """
    if stack.rock_hardness is None:
        return []
    if stack.height is None:
        return []

    hardness = np.asarray(stack.rock_hardness, dtype=np.float64)
    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape

    # Karst-prone mask: limestone-ish hardness (not too hard, not too soft)
    karst_mask = (hardness >= 0.4) & (hardness <= hardness_threshold + 0.15)
    if not karst_mask.any():
        return []

    # Pick local minima within the mask as sinkhole / cenote seeds
    features: List[KarstFeature] = []
    # Use a simple grid subsample to avoid O(N) feature explosion
    step = max(4, H // 16)
    fid = 0
    for r in range(step, H - step, step):
        for c in range(step, W - step, step):
            if not karst_mask[r, c]:
                continue
            window = h[r - 2 : r + 3, c - 2 : c + 3]
            if h[r, c] > float(window.min()) + 0.1:
                continue  # not a local minimum
            # Decide feature kind from neighborhood
            rng_hardness = hardness[r, c]
            if rng_hardness > hardness_threshold:
                kind = "cenote"
            elif h[r, c] < (float(h.min()) + 0.25 * float(h.ptp() or 1.0)):
                kind = "polje"
            else:
                kind = "sinkhole"
            wx = stack.world_origin_x + c * stack.cell_size
            wy = stack.world_origin_y + r * stack.cell_size
            wz = float(h[r, c])
            radius = float(stack.cell_size * 2.0)
            features.append(
                KarstFeature(
                    feature_id=f"karst_{fid}",
                    kind=kind,
                    world_pos=(wx, wy, wz),
                    radius_m=radius,
                )
            )
            fid += 1
    return features


# ---------------------------------------------------------------------------
# Carving
# ---------------------------------------------------------------------------


def carve_karst_features(
    stack: TerrainMaskStack,
    features: List[KarstFeature],
) -> np.ndarray:
    """Return a height delta carving the given karst features.

    Sinkholes + cenotes: cone-shaped depressions.
    Poljes: flat-floored shallow basins.
    Disappearing streams: no direct delta (handled by hydrology bundle).
    """
    if stack.height is None:
        raise ValueError("carve_karst_features requires stack.height")
    h = np.asarray(stack.height, dtype=np.float64)
    H, W = h.shape
    delta = np.zeros((H, W), dtype=np.float64)

    if not features:
        return delta

    for f in features:
        cx = int(round((f.world_pos[0] - stack.world_origin_x) / stack.cell_size))
        cy = int(round((f.world_pos[1] - stack.world_origin_y) / stack.cell_size))
        rad_cells = max(1, int(round(f.radius_m / stack.cell_size)))

        r0 = max(0, cy - rad_cells)
        r1 = min(H, cy + rad_cells + 1)
        c0 = max(0, cx - rad_cells)
        c1 = min(W, cx + rad_cells + 1)

        for r in range(r0, r1):
            for c in range(c0, c1):
                d = math.hypot(r - cy, c - cx)
                if d > rad_cells:
                    continue
                t = 1.0 - d / rad_cells
                if f.kind in ("sinkhole", "cenote"):
                    # Cone depression
                    depth = f.radius_m * 0.5 * t
                elif f.kind == "polje":
                    # Flat bottom
                    depth = f.radius_m * 0.25 * (1.0 if t > 0.3 else t / 0.3)
                else:
                    depth = 0.0
                delta[r, c] = min(delta[r, c], -depth)
    return delta


# ---------------------------------------------------------------------------
# Pass
# ---------------------------------------------------------------------------


def pass_karst(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle I pass: detect + carve karst features.

    Consumes: height, rock_hardness
    Produces: height (mutated)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    hints = dict(state.intent.composition_hints) if state.intent else {}
    hardness_threshold = float(hints.get("karst_hardness_threshold", 0.6))
    enabled = bool(hints.get("karst_enabled", True))

    features: List[KarstFeature] = []
    delta_mean = 0.0
    produced: tuple = ()
    if enabled and stack.rock_hardness is not None:
        features = detect_karst_candidates(stack, hardness_threshold)
        if features:
            delta = carve_karst_features(stack, features)
            stack.set("karst_delta", delta.astype(np.float32), "karst")
            delta_mean = float(np.abs(delta).mean())
            produced = ("karst_delta",)

    # derive_pass_seed for determinism (not used here, but required by contract)
    _ = derive_pass_seed(
        state.intent.seed, "karst", state.tile_x, state.tile_y, region
    )

    return PassResult(
        pass_name="karst",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=produced,
        metrics={
            "feature_count": len(features),
            "mean_delta_m": delta_mean,
            "hardness_threshold": hardness_threshold,
            "enabled": enabled,
        },
        issues=[],
    )


def get_sinkhole_specs(
    stack: TerrainMaskStack,
    *,
    max_sinkholes: int = 5,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for sinkhole meshes at karst-detected sites.

    Calls ``detect_karst_candidates`` to find sinkhole/cenote locations,
    then ``generate_sinkhole`` from terrain_features to produce standalone
    meshes for Blender placement.

    Returns a list of dicts with ``mesh_spec`` and ``world_pos`` keys.
    """
    from .terrain_features import generate_sinkhole

    features = detect_karst_candidates(stack)
    sinkholes = [f for f in features if f.kind in ("sinkhole", "cenote")]
    if not sinkholes:
        return []

    rng = np.random.default_rng(seed)
    results = []
    for f in sinkholes[:max_sinkholes]:
        spec = generate_sinkhole(
            radius=f.radius_m,
            depth=f.radius_m * 1.2,
            wall_roughness=rng.uniform(0.3, 0.7),
            has_bottom_cave=f.kind == "cenote",
            rubble_density=rng.uniform(0.2, 0.5),
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": f.world_pos})
    return results


__all__ = [
    "KarstFeature",
    "detect_karst_candidates",
    "carve_karst_features",
    "pass_karst",
    "get_sinkhole_specs",
]
