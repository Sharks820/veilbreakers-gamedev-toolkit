"""Bundle L — terrain_god_ray_hints.

Identifies plausible god-ray / light-shaft source locations: narrow
valleys, canyon mouths, and cave openings where directional sunlight
through atmospheric haze forms visible beams. Hints are exported as
JSON for the Unity consumer (light probe placement).

Pure numpy, no bpy, deterministic.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainMaskStack,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# GodRayHint dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GodRayHint:
    """A plausible god-ray source location + direction."""

    source_pos: Tuple[float, float, float]
    direction_rad: float
    intensity: float
    source_feature_id: str

    def to_dict(self) -> dict:
        return {
            "source_pos": list(self.source_pos),
            "direction_rad": float(self.direction_rad),
            "intensity": float(self.intensity),
            "source_feature_id": str(self.source_feature_id),
        }


# ---------------------------------------------------------------------------
# Core detector
# ---------------------------------------------------------------------------


def _normalize_sun_dir(sun_dir_rad: Tuple[float, float]) -> Tuple[float, float]:
    """Return (azimuth, altitude) in radians. Altitude clamped to (0, pi/2]."""
    az = float(sun_dir_rad[0])
    alt = float(sun_dir_rad[1])
    if alt <= 0.0:
        alt = 1e-3
    return az, alt


def compute_god_ray_hints(
    stack: TerrainMaskStack,
    sun_dir_rad: Tuple[float, float],
    cloud_shadow: np.ndarray,
) -> List[GodRayHint]:
    """Detect plausible god-ray source locations.

    Algorithm
    ---------
    1. Compute local concavity (basin laplacian).
    2. Intersect concave cells with any ``cave_candidate`` and/or
       ``waterfall_lip_candidate`` masks — these are the highest-priority
       sources.
    3. Additionally score high-concavity valley cells that are partially
       under cloud shadow (light-dark transition boundary).
    4. Return the top-N scored cells as hints, with direction pointing
       from the sun azimuth.

    Parameters
    ----------
    stack:
        Mask stack. Uses ``height``, optionally ``cave_candidate``,
        ``waterfall_lip_candidate``.
    sun_dir_rad:
        (azimuth, altitude) in radians. Altitude must be > 0.
    cloud_shadow:
        float [0..1] mask matching ``stack.height`` shape.

    Returns
    -------
    list[GodRayHint]
        Up to 16 hints, sorted by descending intensity.
    """
    if stack.height is None:
        raise ValueError("compute_god_ray_hints requires stack.height")
    h = np.asarray(stack.height, dtype=np.float64)
    cs = np.asarray(cloud_shadow, dtype=np.float32)
    if cs.shape != h.shape:
        raise ValueError(
            f"cloud_shadow shape {cs.shape} must match height shape {h.shape}"
        )

    az, _alt = _normalize_sun_dir(sun_dir_rad)

    lap = (
        np.roll(h, 1, 0)
        + np.roll(h, -1, 0)
        + np.roll(h, 1, 1)
        + np.roll(h, -1, 1)
        - 4.0 * h
    ) / (float(stack.cell_size) ** 2)
    # Concavity score [0..1]
    p_hi = float(np.percentile(lap, 95.0))
    if p_hi < 1e-6:
        conc_score = np.zeros_like(lap, dtype=np.float32)
    else:
        conc_score = np.clip(lap / p_hi, 0.0, 1.0).astype(np.float32)

    # Feature-kind source bonuses.
    cave = stack.get("cave_candidate")
    wfall = stack.get("waterfall_lip_candidate")
    cave_mask = (
        np.asarray(cave, dtype=np.float32)
        if cave is not None
        else np.zeros_like(h, dtype=np.float32)
    )
    wfall_mask = (
        np.asarray(wfall, dtype=np.float32)
        if wfall is not None
        else np.zeros_like(h, dtype=np.float32)
    )

    # Light-dark boundary score: edge of cloud shadow = strong candidate.
    cs_grad_r = np.abs(cs - np.roll(cs, 1, 0))
    cs_grad_c = np.abs(cs - np.roll(cs, 1, 1))
    cs_edge = np.clip(cs_grad_r + cs_grad_c, 0.0, 1.0)

    # Composite intensity
    intensity = (
        0.5 * conc_score
        + 0.6 * cave_mask
        + 0.5 * wfall_mask
        + 0.3 * cs_edge
    ).astype(np.float32)

    # Non-max suppression: select local maxima above the 90th percentile.
    thresh = float(np.percentile(intensity, 90.0))
    if thresh < 1e-6:
        thresh = float(intensity.max() * 0.5)
    candidates: list[Tuple[float, int, int, str]] = []
    rows, cols = intensity.shape
    for r in range(1, rows - 1):
        for c in range(1, cols - 1):
            v = float(intensity[r, c])
            if v < thresh:
                continue
            window = intensity[r - 1 : r + 2, c - 1 : c + 2]
            if v < float(window.max()) - 1e-9:
                continue
            if cave_mask[r, c] > 0.5:
                fkind = "cave_entrance"
            elif wfall_mask[r, c] > 0.5:
                fkind = "waterfall_lip"
            else:
                fkind = "valley"
            candidates.append((v, r, c, fkind))

    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    top = candidates[:16]
    hints: list[GodRayHint] = []
    ox = float(stack.world_origin_x)
    oy = float(stack.world_origin_y)
    cell = float(stack.cell_size)
    for idx, (v, r, c, fkind) in enumerate(top):
        wx = ox + (c + 0.5) * cell
        wy = oy + (r + 0.5) * cell
        wz = float(h[r, c])
        hints.append(
            GodRayHint(
                source_pos=(wx, wy, wz),
                direction_rad=float(az),
                intensity=float(v),
                source_feature_id=f"{fkind}_{idx:03d}",
            )
        )
    return hints


def export_god_ray_hints_json(
    hints: List[GodRayHint],
    output_path: Path,
) -> None:
    """Serialise hints to a JSON file (deterministic ordering)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "hint_count": len(hints),
        "hints": [h.to_dict() for h in hints],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Pass wrapper
# ---------------------------------------------------------------------------


def pass_god_ray_hints(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Bundle L pass: compute god-ray hints.

    Contract
    --------
    Consumes: ``height``, optional ``cave_candidate``,
              ``waterfall_lip_candidate``, ``cloud_shadow``
    Produces: (no mask channel — hints are a side-effect json artifact)
    Respects protected zones: no (read-only)
    Requires scene read: no
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    hints_cfg = state.intent.composition_hints if state.intent else {}
    sun_az = float(hints_cfg.get("sun_azimuth_rad", math.radians(135.0)))
    sun_alt = float(hints_cfg.get("sun_altitude_rad", math.radians(35.0)))

    cs = stack.get("cloud_shadow")
    if cs is None:
        cs = np.zeros_like(stack.height, dtype=np.float32)

    hints = compute_god_ray_hints(stack, (sun_az, sun_alt), np.asarray(cs))

    return PassResult(
        pass_name="god_ray_hints",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height", "cloud_shadow"),
        produced_channels=(),
        metrics={
            "hint_count": len(hints),
            "max_intensity": float(max((h.intensity for h in hints), default=0.0)),
            "sun_azimuth_rad": sun_az,
            "sun_altitude_rad": sun_alt,
        },
        side_effects=[f"god_ray_hints:{len(hints)}"],
    )


def register_bundle_l_god_ray_hints_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="god_ray_hints",
            func=pass_god_ray_hints,
            requires_channels=("height",),
            produces_channels=(),
            seed_namespace="god_ray_hints",
            requires_scene_read=False,
            description="Bundle L: god-ray / light-shaft hint detection",
        )
    )


__all__ = [
    "GodRayHint",
    "compute_god_ray_hints",
    "export_god_ray_hints_json",
    "pass_god_ray_hints",
    "register_bundle_l_god_ray_hints_pass",
]
