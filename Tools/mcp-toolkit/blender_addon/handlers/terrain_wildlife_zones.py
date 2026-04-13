"""Bundle J — terrain_wildlife_zones.

Computes per-species spawn affinity maps from the TerrainMaskStack and
populates ``stack.wildlife_affinity`` — a ``dict[str, np.ndarray]`` of
(H, W) float32 densities in [0, 1].

Pure numpy. No bpy. Deterministic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SpeciesAffinityRule:
    """Affinity scoring rule for a single species.

    Attributes
    ----------
    species : str
        Species identifier (e.g. ``"deer"``, ``"wolf"``).
    preferred_slope : Tuple[float, float]
        (min_deg, max_deg). Outside the window => zero affinity.
    preferred_altitude : Tuple[float, float]
        (min_m, max_m) world-meter altitude window. Outside => zero affinity.
    preferred_biomes : Tuple[int, ...]
        Allowed biome IDs. Empty tuple means biome doesn't restrict.
    required_water_proximity_m : Optional[float]
        If set, affinity falls off beyond this radius from any water cell.
    exclusion_radius_m : float
        Minimum distance to any hero_exclusion / protected cell.
    """

    species: str
    preferred_slope: Tuple[float, float] = (0.0, 35.0)
    preferred_altitude: Tuple[float, float] = (0.0, 2500.0)
    preferred_biomes: Tuple[int, ...] = ()
    required_water_proximity_m: Optional[float] = None
    exclusion_radius_m: float = 0.0


def _window_score(values: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Return 1.0 inside [lo, hi], linearly falling to 0 within a 20% margin."""
    span = max(hi - lo, 1e-6)
    margin = span * 0.2
    score = np.ones_like(values, dtype=np.float64)
    # Below lo: falloff over (lo - margin, lo)
    below = values < lo
    score[below] = np.clip((values[below] - (lo - margin)) / margin, 0.0, 1.0)
    above = values > hi
    score[above] = np.clip(((hi + margin) - values[above]) / margin, 0.0, 1.0)
    return score


def _distance_to_mask(mask: np.ndarray, cell_size: float) -> np.ndarray:
    """Approximate Euclidean distance from every cell to the nearest True cell.

    Pure numpy BFS-ish chamfer approximation that avoids scipy dependency.
    For terrain-scale tiles this is acceptable cost.
    """
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype=np.float64)
    INF = np.float64(1e12)
    dist = np.where(mask, 0.0, INF)
    # Two-pass chamfer 3x3
    h, w = mask.shape
    # Forward pass
    for r in range(h):
        for c in range(w):
            if dist[r, c] == 0.0:
                continue
            best = dist[r, c]
            if r > 0:
                best = min(best, dist[r - 1, c] + 1.0)
                if c > 0:
                    best = min(best, dist[r - 1, c - 1] + np.sqrt(2.0))
                if c < w - 1:
                    best = min(best, dist[r - 1, c + 1] + np.sqrt(2.0))
            if c > 0:
                best = min(best, dist[r, c - 1] + 1.0)
            dist[r, c] = best
    # Backward pass
    for r in range(h - 1, -1, -1):
        for c in range(w - 1, -1, -1):
            if dist[r, c] == 0.0:
                continue
            best = dist[r, c]
            if r < h - 1:
                best = min(best, dist[r + 1, c] + 1.0)
                if c > 0:
                    best = min(best, dist[r + 1, c - 1] + np.sqrt(2.0))
                if c < w - 1:
                    best = min(best, dist[r + 1, c + 1] + np.sqrt(2.0))
            if c < w - 1:
                best = min(best, dist[r, c + 1] + 1.0)
            dist[r, c] = best
    dist *= float(cell_size)
    dist[dist >= INF * 0.5] = np.inf
    return dist


def compute_wildlife_affinity(
    stack: TerrainMaskStack,
    rules: List[SpeciesAffinityRule],
) -> Dict[str, np.ndarray]:
    """Compute per-species affinity arrays and populate stack.wildlife_affinity."""
    if stack.height is None:
        raise ValueError("compute_wildlife_affinity requires stack.height")

    h = np.asarray(stack.height, dtype=np.float64)

    slope = stack.slope
    if slope is None:
        gy, gx = np.gradient(h, float(stack.cell_size))
        slope = np.arctan(np.sqrt(gx * gx + gy * gy))
    slope_deg = np.degrees(np.asarray(slope, dtype=np.float64))

    biome = (
        np.asarray(stack.biome_id, dtype=np.int32)
        if stack.biome_id is not None
        else None
    )

    water_mask = None
    if stack.water_surface is not None:
        water_mask = np.asarray(stack.water_surface) > 0.0
    elif stack.wetness is not None:
        water_mask = np.asarray(stack.wetness) > 0.5

    exclusion_mask = None
    if stack.hero_exclusion is not None:
        exclusion_mask = np.asarray(stack.hero_exclusion).astype(bool)

    # Pre-compute distance fields only if some rule asks for them.
    need_water_dist = any(r.required_water_proximity_m is not None for r in rules)
    need_excl_dist = any(r.exclusion_radius_m > 0.0 for r in rules)

    water_dist = (
        _distance_to_mask(water_mask, stack.cell_size)
        if need_water_dist and water_mask is not None
        else None
    )
    excl_dist = (
        _distance_to_mask(exclusion_mask, stack.cell_size)
        if need_excl_dist and exclusion_mask is not None
        else None
    )

    affinity_maps: Dict[str, np.ndarray] = {}
    for rule in rules:
        lo_s, hi_s = rule.preferred_slope
        lo_a, hi_a = rule.preferred_altitude

        score = _window_score(slope_deg, lo_s, hi_s) * _window_score(h, lo_a, hi_a)

        if rule.preferred_biomes and biome is not None:
            allowed = np.isin(biome, np.asarray(rule.preferred_biomes, dtype=np.int32))
            score = score * allowed.astype(np.float64)

        if rule.required_water_proximity_m is not None:
            if water_dist is None:
                # No water at all -> zero affinity
                score = np.zeros_like(score)
            else:
                radius = float(rule.required_water_proximity_m)
                falloff = np.clip(1.0 - water_dist / max(radius, 1e-6), 0.0, 1.0)
                score = score * falloff

        if rule.exclusion_radius_m > 0.0 and excl_dist is not None:
            excl_ok = (excl_dist >= rule.exclusion_radius_m).astype(np.float64)
            score = score * excl_ok

        affinity_maps[rule.species] = score.astype(np.float32)

    if stack.wildlife_affinity is None:
        stack.wildlife_affinity = {}
    stack.wildlife_affinity.update(affinity_maps)
    stack.populated_by_pass["wildlife_affinity"] = "wildlife_zones"
    return affinity_maps


DEFAULT_WILDLIFE_RULES: Tuple[SpeciesAffinityRule, ...] = (
    SpeciesAffinityRule(
        species="deer",
        preferred_slope=(0.0, 25.0),
        preferred_altitude=(0.0, 1500.0),
        required_water_proximity_m=50.0,
    ),
    SpeciesAffinityRule(
        species="wolf",
        preferred_slope=(0.0, 40.0),
        preferred_altitude=(100.0, 2000.0),
    ),
    SpeciesAffinityRule(
        species="eagle",
        preferred_slope=(15.0, 80.0),
        preferred_altitude=(800.0, 4000.0),
    ),
)


def pass_wildlife_zones(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle J pass: compute wildlife affinity maps.

    Consumes: height (+ optional slope / biome_id / water_surface / hero_exclusion)
    Produces: wildlife_affinity (dict channel)
    """
    t0 = time.perf_counter()
    stack = state.mask_stack

    rules_hint = state.intent.composition_hints.get("wildlife_rules") if state.intent else None
    rules = list(rules_hint) if isinstance(rules_hint, (list, tuple)) else list(DEFAULT_WILDLIFE_RULES)

    affinity = compute_wildlife_affinity(stack, rules)

    metrics = {
        species: {
            "peak": float(arr.max()),
            "mean": float(arr.mean()),
            "coverage_frac": float((arr > 0.1).mean()),
        }
        for species, arr in affinity.items()
    }

    issues: List[ValidationIssue] = []
    if not affinity:
        issues.append(
            ValidationIssue(
                code="WILDLIFE_NO_RULES",
                severity="soft",
                message="no species rules supplied; wildlife_affinity empty",
            )
        )

    return PassResult(
        pass_name="wildlife_zones",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("wildlife_affinity",),
        metrics=metrics,
        issues=issues,
    )


def register_bundle_j_wildlife_zones_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="wildlife_zones",
            func=pass_wildlife_zones,
            requires_channels=("height",),
            # dict channels are not validated by the controller's scalar
            # produces_channels contract — keep this empty on purpose.
            produces_channels=(),
            seed_namespace="wildlife_zones",
            requires_scene_read=False,
            description="Bundle J: compute per-species wildlife affinity maps",
        )
    )


__all__ = [
    "SpeciesAffinityRule",
    "DEFAULT_WILDLIFE_RULES",
    "compute_wildlife_affinity",
    "pass_wildlife_zones",
    "register_bundle_j_wildlife_zones_pass",
]
