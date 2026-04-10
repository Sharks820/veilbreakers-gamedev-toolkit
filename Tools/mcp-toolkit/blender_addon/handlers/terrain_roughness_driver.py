"""Bundle K — terrain_roughness_driver.

Drives ``roughness_variation`` from wetness (wet surfaces = low roughness)
and erosion amount (high-erosion surfaces = high roughness, broken up).
Also folds in ambient_occlusion_bake as a slight roughness increase in
deep concavities (dust accumulation).
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


def compute_roughness_from_wetness_wear(stack: TerrainMaskStack) -> np.ndarray:
    """Return a (H, W) float32 roughness_variation mask in [0, 1].

    Model
    -----
    base = 0.55
    wet cells pull toward 0.15
    eroded cells push toward 0.85 (weathered, broken)
    deposition cells push toward 0.70 (silted, loose)
    AO concavity adds +0.05 (dust catches in crevices)

    Starts from any existing roughness_variation if present (additive
    refinement instead of overwriting).
    """
    if stack.height is None:
        raise ValueError("compute_roughness_from_wetness_wear requires stack.height")

    h = np.asarray(stack.height)
    rows, cols = h.shape

    existing = stack.get("roughness_variation")
    if existing is None:
        base = np.full((rows, cols), 0.55, dtype=np.float64)
    else:
        base = np.asarray(existing, dtype=np.float64).copy()

    wet = stack.get("wetness")
    if wet is not None:
        wet_arr = np.clip(np.asarray(wet, dtype=np.float64), 0.0, 1.0)
        base = base * (1.0 - wet_arr) + 0.15 * wet_arr

    erosion = stack.get("erosion_amount")
    if erosion is not None:
        er = np.asarray(erosion, dtype=np.float64)
        er_max = float(er.max()) if er.size else 0.0
        if er_max > 1e-9:
            er_norm = np.clip(er / er_max, 0.0, 1.0)
            base = base * (1.0 - 0.6 * er_norm) + 0.85 * 0.6 * er_norm

    deposition = stack.get("deposition_amount")
    if deposition is not None:
        dep = np.asarray(deposition, dtype=np.float64)
        dep_max = float(dep.max()) if dep.size else 0.0
        if dep_max > 1e-9:
            dep_norm = np.clip(dep / dep_max, 0.0, 1.0)
            base = base * (1.0 - 0.3 * dep_norm) + 0.70 * 0.3 * dep_norm

    ao = stack.get("ambient_occlusion_bake")
    if ao is not None:
        ao_arr = np.clip(np.asarray(ao, dtype=np.float64), 0.0, 1.0)
        # AO stored as 1=lit, 0=occluded (convention). Dust concentrates in low-AO.
        dust = 1.0 - ao_arr
        base = base + 0.05 * dust

    return np.clip(base, 0.0, 1.0).astype(np.float32)


def pass_roughness_driver(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle K pass: wetness/wear-driven roughness.

    Consumes: height (+ optional wetness, erosion_amount, deposition_amount,
              ambient_occlusion_bake, roughness_variation)
    Produces: roughness_variation
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    rough = compute_roughness_from_wetness_wear(stack)
    stack.set("roughness_variation", rough, "roughness_driver")

    return PassResult(
        pass_name="roughness_driver",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("roughness_variation",),
        metrics={
            "rough_min": float(rough.min()),
            "rough_max": float(rough.max()),
            "rough_mean": float(rough.mean()),
            "wet_driven": stack.get("wetness") is not None,
            "erosion_driven": stack.get("erosion_amount") is not None,
        },
        issues=[],
    )


def register_bundle_k_roughness_driver_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="roughness_driver",
            func=pass_roughness_driver,
            requires_channels=("height",),
            produces_channels=("roughness_variation",),
            seed_namespace="roughness_driver",
            requires_scene_read=False,
            description="Bundle K: wetness/wear-driven roughness variation",
        )
    )


__all__ = [
    "compute_roughness_from_wetness_wear",
    "pass_roughness_driver",
    "register_bundle_k_roughness_driver_pass",
]
