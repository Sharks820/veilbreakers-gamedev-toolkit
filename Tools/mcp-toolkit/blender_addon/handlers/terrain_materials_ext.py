"""Bundle B supplement — material ceiling extensions.

Extends ``terrain_materials_v2`` with height-blended (gamma) layer weights,
texel-density coherency checks, micro-normal metadata, and cliff silhouette
area validation. Does NOT modify the original Bundle B module.

Per Addendum 1.B.2 of docs/terrain_ultra_implementation_plan_2026-04-08.md.

No bpy imports — headless-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from .terrain_materials_v2 import MaterialChannel
from .terrain_semantics import ValidationIssue


# ---------------------------------------------------------------------------
# Extended material channel
# ---------------------------------------------------------------------------


@dataclass
class MaterialChannelExt:
    """Wraps a Bundle B ``MaterialChannel`` and adds ceiling-extension fields.

    Addendum 1.B.2 requires that each material layer declare:
      * ``height_blend_gamma`` — non-linear blend curve between layers
      * ``texel_density_m``   — texture cm-per-m for coherency checks
      * ``micro_normal_texture`` — optional detail normal path
      * ``micro_normal_strength`` — detail normal mix strength
      * ``respects_displacement`` — whether the layer honors POM/displacement
    """

    base: MaterialChannel
    height_blend_gamma: float = 1.0
    texel_density_m: float = 64.0
    micro_normal_texture: Optional[str] = None
    micro_normal_strength: float = 0.8
    respects_displacement: bool = True

    @property
    def channel_id(self) -> str:
        return self.base.channel_id


# ---------------------------------------------------------------------------
# Texel-density coherency
# ---------------------------------------------------------------------------


def validate_texel_density_coherency(
    channels: Sequence[MaterialChannelExt],
    max_ratio: float = 2.0,
) -> List[ValidationIssue]:
    """Flag channels whose texel density exceeds ``max_ratio`` vs the min.

    Two adjacent blended layers with wildly different texel density cause
    visible texture-resolution discontinuities (Addendum 1.B.2).
    """
    issues: List[ValidationIssue] = []
    if len(channels) < 2:
        return issues

    densities = [float(c.texel_density_m) for c in channels]
    min_d = min(densities)
    if min_d <= 0:
        issues.append(
            ValidationIssue(
                code="MAT_TEXEL_DENSITY_INVALID",
                severity="hard",
                affected_feature="materials",
                message=f"Non-positive texel_density_m detected: {densities}",
            )
        )
        return issues

    for ch, d in zip(channels, densities):
        if d / min_d > max_ratio:
            issues.append(
                ValidationIssue(
                    code="MAT_TEXEL_DENSITY_INCOHERENT",
                    severity="soft",
                    affected_feature=ch.channel_id,
                    message=(
                        f"channel {ch.channel_id!r} texel_density_m={d:.1f} "
                        f">{max_ratio}x min={min_d:.1f}"
                    ),
                    remediation="Retexture to match neighboring layers",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Height-blended layer weights (gamma)
# ---------------------------------------------------------------------------


def compute_height_blended_weights(
    base_weights: np.ndarray,
    heights: np.ndarray,
    channel_gammas: Sequence[float],
) -> np.ndarray:
    """Apply per-layer gamma curves to base splatmap weights.

    Shape contract:
        base_weights: (H, W, L)
        heights:      (H, W) — world-meter elevation
        channel_gammas: length L

    A gamma > 1 biases the layer toward higher local heights (think: snow
    on peaks), gamma < 1 biases it toward valleys. Weights are renormalized
    to sum to 1 per cell. Heights are normalized to [0,1] **per-call** for
    the gamma curve only — we do not clip the raw world heights (Rule 10).
    """
    base = np.asarray(base_weights, dtype=np.float32)
    if base.ndim != 3:
        raise ValueError(f"base_weights must be (H,W,L), got {base.shape}")
    h, w, L = base.shape
    if len(channel_gammas) != L:
        raise ValueError(
            f"channel_gammas len={len(channel_gammas)} != num layers {L}"
        )

    heights = np.asarray(heights, dtype=np.float64)
    if heights.shape != (h, w):
        raise ValueError(
            f"heights shape {heights.shape} != ({h},{w})"
        )

    h_min = float(heights.min())
    h_max = float(heights.max())
    span = max(h_max - h_min, 1e-9)
    # Local 0..1 normalization for the gamma curve only — does NOT mutate
    # or clamp the underlying world heights.
    h01 = (heights - h_min) / span  # bounded in [0,1] by construction

    out = np.zeros_like(base, dtype=np.float32)
    for idx, g in enumerate(channel_gammas):
        g = max(float(g), 1e-6)
        if g >= 1.0:
            # Peak-biased: strong at high h01, weak at low
            curve = np.power(h01, g)
        else:
            # Valley-biased: strong at low h01, weak at high. Use the
            # inverted curve so that at h01=1 a low-gamma layer collapses
            # to 0 and a high-gamma layer dominates (physical intent).
            curve = np.power(1.0 - h01, 1.0 / g)
        out[:, :, idx] = base[:, :, idx] * curve.astype(np.float32)

    total = out.sum(axis=2)
    # Where total is zero (e.g., gamma collapsed all layers at h01==0),
    # fall back to the unmodified base weights to stay well-defined.
    empty = total <= 1e-9
    if empty.any():
        out[empty, :] = base[empty, :]
        total = out.sum(axis=2)
    total = np.where(total <= 1e-9, 1.0, total)
    out /= total[:, :, None]
    return out.astype(np.float32)


# ---------------------------------------------------------------------------
# Cliff silhouette area
# ---------------------------------------------------------------------------


# Minimum pixel-coverage fractions for hero / secondary cliff silhouettes
# (Addendum 1.B.2: cliffs must dominate the frame, not disappear).
HERO_CLIFF_MIN_FRAC = 0.08
SECONDARY_CLIFF_MIN_FRAC = 0.03


def validate_cliff_silhouette_area(
    cliff_pixel_coverage_fraction: float,
    *,
    tier: str = "secondary",
) -> List[ValidationIssue]:
    """Reject hero cliffs < 8% pixel coverage, secondary cliffs < 3%.

    ``tier`` must be ``"hero"`` or ``"secondary"``. Returns a hard issue
    when the silhouette is too small to read on screen.
    """
    issues: List[ValidationIssue] = []
    frac = float(cliff_pixel_coverage_fraction)
    tier = (tier or "secondary").lower()
    if tier == "hero":
        threshold = HERO_CLIFF_MIN_FRAC
    elif tier == "secondary":
        threshold = SECONDARY_CLIFF_MIN_FRAC
    else:
        issues.append(
            ValidationIssue(
                code="CLIFF_SILHOUETTE_UNKNOWN_TIER",
                severity="hard",
                affected_feature="cliff",
                message=f"Unknown cliff tier {tier!r}",
            )
        )
        return issues

    if frac < threshold:
        issues.append(
            ValidationIssue(
                code="CLIFF_SILHOUETTE_TOO_SMALL",
                severity="hard",
                affected_feature="cliff",
                message=(
                    f"{tier} cliff pixel coverage {frac:.3f} < "
                    f"threshold {threshold:.3f}"
                ),
                remediation=(
                    "Scale cliff formation up, re-anchor camera, or tag as "
                    "non-hero feature."
                ),
            )
        )
    return issues


__all__ = [
    "MaterialChannelExt",
    "validate_texel_density_coherency",
    "compute_height_blended_weights",
    "validate_cliff_silhouette_area",
    "HERO_CLIFF_MIN_FRAC",
    "SECONDARY_CLIFF_MIN_FRAC",
]
