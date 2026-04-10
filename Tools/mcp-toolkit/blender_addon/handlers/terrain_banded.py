"""Bundle G — Banded Noise Refactor.

Wraps the existing ``_terrain_noise`` backend (fBm, ridged multifractal,
domain warp) to produce a *banded* heightmap: separable macro / meso /
micro / strata bands that can be re-composed with tunable weights. This
gives authoring code a single object containing all frequency bands plus
the final composite, so iteration does not require regenerating noise.

Design rules (TERRAIN_AGENT_PROTOCOL.md):
    - Z-up, world meters. ``composite`` is world-meter elevation.
    - Pure numpy. No bpy. No mutation of ``_terrain_noise``.
    - Deterministic per seed: identical ``(seed, shape, scale, origin)``
      input produces bit-identical output.
    - The new pass ``banded_macro`` writes ``composite`` to
      ``state.mask_stack.height`` and stores per-band metadata in
      ``state.side_effects`` (bands are not dedicated mask channels).

The five bands in §12.1 of the ultra plan are collapsed here into four
re-composable bands + a domain-warp field:
    macro_band   -- fBm + ridged multifractal, 8 octaves, period ~1km
    meso_band    -- domain-warped fBm, 4 octaves, period ~150m
    micro_band   -- ridged multifractal, 2 octaves, period ~30m
    strata_band  -- near-horizontal sedimentary layering
    warp_band    -- scalar magnitude of the domain-warp field applied
                    to the composite (informational; not re-composed)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

import numpy as np

# Wrap (never mutate) the existing noise backend.
from ._terrain_noise import (
    domain_warp_array,
    ridged_multifractal_array,
    _make_noise_generator,
    generate_heightmap,  # re-exported for back-compat / tests
)

# ---------------------------------------------------------------------------
# Band weight presets
# ---------------------------------------------------------------------------

# Tuple order is (macro, meso, micro, strata). Weights sum to ~1.0 but
# ``compose_banded_heightmap`` does not require that; the composite is the
# literal weighted sum so callers can over- or under-drive bands freely.
BAND_WEIGHTS: Dict[str, Tuple[float, float, float, float]] = {
    "dark_fantasy_default": (0.55, 0.28, 0.12, 0.05),
    "mountains":           (0.62, 0.24, 0.10, 0.04),
    "plains":              (0.30, 0.45, 0.15, 0.10),
    "canyon":              (0.45, 0.25, 0.10, 0.20),
}

# Period (in world meters) of the lowest-frequency octave of each band.
# The noise backend samples coords as ``coord / scale`` so a "period" p
# in meters corresponds to a scale of p for the first octave.
_BAND_PERIOD_M: Dict[str, float] = {
    "macro": 1000.0,
    "meso": 150.0,
    "micro": 30.0,
    "strata": 200.0,  # strata layer vertical wavelength (in meters)
}

# Per-band seed offsets: combined with the caller seed so bands are
# independent yet deterministic.
_BAND_SEED_OFFSETS: Dict[str, int] = {
    "macro": 0,
    "meso": 104_729,
    "micro": 15_485_863,
    "strata": 2_038_074_743,
    "warp": 99_991,
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class BandedHeightmap:
    """Separable frequency-band heightmap plus its composite.

    All arrays have identical ``(H, W)`` shape. ``composite`` is in
    world meters (after weighted blending). Each band is normalized to
    roughly ``[-1, 1]`` *before* weights are applied; the composite
    scale in meters is set by ``metadata['vertical_scale_m']``.
    """

    macro_band: np.ndarray
    meso_band: np.ndarray
    micro_band: np.ndarray
    strata_band: np.ndarray
    warp_band: np.ndarray
    composite: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> Tuple[int, int]:
        return self.composite.shape

    def band(self, name: str) -> np.ndarray:
        try:
            return getattr(self, f"{name}_band")
        except AttributeError as exc:
            raise KeyError(f"unknown band '{name}'") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coord_grids(
    width: int,
    height: int,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    period_m: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build world-meter coord grids normalized to a band's sampling period.

    Rows correspond to world-Y, columns to world-X. ``xs`` and ``ys``
    are in noise-space units where 1.0 corresponds to ``period_m`` meters.
    """
    period_m = max(period_m, 1e-6)
    xs_1d = (np.arange(width, dtype=np.float64) * cell_size + world_origin_x) / period_m
    ys_1d = (np.arange(height, dtype=np.float64) * cell_size + world_origin_y) / period_m
    xs, ys = np.meshgrid(xs_1d, ys_1d)
    return xs, ys


def _fbm_array(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    octaves: int,
    persistence: float,
    lacunarity: float,
    seed: int,
) -> np.ndarray:
    """Vectorized fBm using the shared noise backend. Returns array in ~[-1, 1]."""
    gen = _make_noise_generator(seed)
    result = np.zeros_like(xs, dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0
    for _ in range(max(1, octaves)):
        result += gen.noise2_array(xs * frequency, ys * frequency) * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    if max_val > 0.0:
        result /= max_val
    return result


def _normalize_band(arr: np.ndarray) -> np.ndarray:
    """Center a band to zero-mean and divide by its std to give ~unit variance.

    This gives the band weights a stable meaning across seeds. Constant
    inputs are returned untouched.
    """
    mean = float(arr.mean())
    std = float(arr.std())
    if std < 1e-12:
        return arr - mean
    return (arr - mean) / std


# ---------------------------------------------------------------------------
# Addendum 1 D.7 — Anisotropic breakup & anti-grain smoothing
# ---------------------------------------------------------------------------


def compute_anisotropic_breakup(
    band: np.ndarray,
    strength: float = 0.3,
    angle_deg: float = 45.0,
    seed: int = 0,
) -> np.ndarray:
    """Apply directional noise breakup to a height band.

    Stretches noise along a dominant direction to simulate wind/water
    erosion patterns. Strength 0 = no breakup, 1 = maximum distortion.
    """
    if strength <= 0 or band.size == 0:
        return band
    rows, cols = band.shape
    rng = np.random.default_rng(seed)
    angle_rad = np.radians(angle_deg)
    # Create directional noise field
    noise = rng.standard_normal((rows, cols)).astype(np.float64)
    # Apply directional blur via rolling
    shift_r = max(1, int(rows * 0.02 * strength))
    shift_c = max(1, int(cols * 0.02 * strength))
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    stretched = np.roll(noise, int(shift_r * cos_a), axis=0)
    stretched = np.roll(stretched, int(shift_c * sin_a), axis=1)
    # Blend with original
    result = band + stretched * strength * float(np.std(band)) * 0.1
    return result


def apply_anti_grain_smoothing(
    band: np.ndarray,
    strength: float = 0.5,
) -> np.ndarray:
    """Remove high-frequency grain artifacts from a height band.

    Uses a gentle box filter to smooth sub-cell noise without losing
    macro features. Strength 0 = no smoothing, 1 = maximum.
    """
    if strength <= 0 or band.size == 0:
        return band
    kernel_size = max(1, int(1 + strength * 2))
    if kernel_size < 2:
        return band
    try:
        from scipy.ndimage import uniform_filter
        return uniform_filter(band.astype(np.float64), size=kernel_size).astype(band.dtype)
    except ImportError:
        # Pure numpy fallback: simple averaging
        padded = np.pad(band.astype(np.float64), kernel_size // 2, mode='reflect')
        result = np.zeros_like(band, dtype=np.float64)
        for dr in range(kernel_size):
            for dc in range(kernel_size):
                result += padded[dr:dr + band.shape[0], dc:dc + band.shape[1]]
        return (result / (kernel_size * kernel_size)).astype(band.dtype)


# ---------------------------------------------------------------------------
# Band generators
# ---------------------------------------------------------------------------


def _generate_macro_band(
    width: int,
    height: int,
    *,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    scale: float,
    seed: int,
) -> np.ndarray:
    """Continental macro band: fBm + ridged multifractal, 8 octaves, ~1km period."""
    period = _BAND_PERIOD_M["macro"] * max(scale, 1e-6) / 100.0
    xs, ys = _coord_grids(width, height, world_origin_x, world_origin_y, cell_size, period)

    macro_seed = (seed + _BAND_SEED_OFFSETS["macro"]) & 0xFFFFFFFF
    fbm = _fbm_array(xs, ys, octaves=8, persistence=0.5, lacunarity=2.0, seed=macro_seed)
    ridged = ridged_multifractal_array(
        xs, ys,
        octaves=8,
        lacunarity=2.0,
        gain=0.5,
        offset=1.0,
        seed=(macro_seed ^ 0xA5A5A5A5) & 0xFFFFFFFF,
    )
    # Blend fBm continental with ridged mountain ranges.
    combined = 0.6 * fbm + 0.4 * (ridged * 2.0 - 1.0)
    return _normalize_band(combined)


def _generate_meso_band(
    width: int,
    height: int,
    *,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    scale: float,
    seed: int,
) -> np.ndarray:
    """Domain-warped fBm, 4 octaves, ~150m period."""
    period = _BAND_PERIOD_M["meso"] * max(scale, 1e-6) / 100.0
    xs, ys = _coord_grids(width, height, world_origin_x, world_origin_y, cell_size, period)

    meso_seed = (seed + _BAND_SEED_OFFSETS["meso"]) & 0xFFFFFFFF
    warp_seed = (seed + _BAND_SEED_OFFSETS["warp"]) & 0xFFFFFFFF
    wxs, wys = domain_warp_array(
        xs, ys,
        warp_strength=0.4,
        warp_scale=1.2,
        seed=warp_seed,
    )
    fbm = _fbm_array(wxs, wys, octaves=4, persistence=0.5, lacunarity=2.0, seed=meso_seed)
    return _normalize_band(fbm)


def _generate_micro_band(
    width: int,
    height: int,
    *,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    scale: float,
    seed: int,
) -> np.ndarray:
    """Ridged multifractal, 2 octaves, ~30m period."""
    period = _BAND_PERIOD_M["micro"] * max(scale, 1e-6) / 100.0
    xs, ys = _coord_grids(width, height, world_origin_x, world_origin_y, cell_size, period)

    micro_seed = (seed + _BAND_SEED_OFFSETS["micro"]) & 0xFFFFFFFF
    ridged = ridged_multifractal_array(
        xs, ys,
        octaves=2,
        lacunarity=2.0,
        gain=0.5,
        offset=1.0,
        seed=micro_seed,
    )
    # Map ridged [0,1] into [-1,1] before normalization so signs behave.
    return _normalize_band(ridged * 2.0 - 1.0)


def _generate_strata_band(
    width: int,
    height: int,
    *,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    scale: float,
    seed: int,
    biome: str,
) -> np.ndarray:
    """Horizontal sedimentary strata: sine layering modulated by biome noise.

    Produces near-horizontal bands (varying along world-Y) with a gentle
    fBm modulation along X so the layers are not perfectly ruler-straight.
    """
    period = _BAND_PERIOD_M["strata"]
    y_coords = (np.arange(height, dtype=np.float64) * cell_size + world_origin_y)
    x_coords = (np.arange(width, dtype=np.float64) * cell_size + world_origin_x)

    # Base horizontal sine layering.
    strata_seed = (seed + _BAND_SEED_OFFSETS["strata"]) & 0xFFFFFFFF
    # Biome-dependent layer frequency multiplier.
    biome_mult = 1.0
    if "canyon" in biome:
        biome_mult = 1.6
    elif "plain" in biome:
        biome_mult = 0.7

    freq = (2.0 * np.pi / period) * biome_mult
    base_sin = np.sin(freq * y_coords)                         # shape (H,)
    layers = np.broadcast_to(base_sin[:, None], (height, width)).astype(np.float64)

    # Gentle X-modulation so strata wobble slightly.
    mod_period = period * 4.0
    xs_mod = x_coords / mod_period
    ys_mod = y_coords / mod_period
    mxs, mys = np.meshgrid(xs_mod, ys_mod)
    wobble = _fbm_array(mxs, mys, octaves=3, persistence=0.5, lacunarity=2.0, seed=strata_seed)
    layered = layers + 0.15 * wobble

    return _normalize_band(layered)


def _generate_warp_field(
    width: int,
    height: int,
    *,
    world_origin_x: float,
    world_origin_y: float,
    cell_size: float,
    scale: float,
    seed: int,
) -> np.ndarray:
    """Domain warp magnitude field — informational, not re-composed.

    Returns the displacement magnitude of the domain warp vector at each
    cell, normalized. Used by downstream bundles that want to know where
    the terrain was "pushed" by warping.
    """
    period = _BAND_PERIOD_M["meso"] * max(scale, 1e-6) / 100.0
    xs, ys = _coord_grids(width, height, world_origin_x, world_origin_y, cell_size, period)
    warp_seed = (seed + _BAND_SEED_OFFSETS["warp"]) & 0xFFFFFFFF
    wxs, wys = domain_warp_array(xs, ys, warp_strength=0.4, warp_scale=1.2, seed=warp_seed)
    mag = np.sqrt((wxs - xs) ** 2 + (wys - ys) ** 2)
    return _normalize_band(mag)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_banded_heightmap(
    width: int,
    height: int,
    *,
    scale: float = 100.0,
    world_origin_x: float = 0.0,
    world_origin_y: float = 0.0,
    cell_size: float = 1.0,
    seed: int = 0,
    biome: str = "dark_fantasy_default",
    vertical_scale_m: float = 120.0,
    anisotropic_breakup_strength: float = 0.0,
    anti_grain_smoothing: float = 0.0,
) -> BandedHeightmap:
    """Generate a banded heightmap with separable frequency bands.

    Parameters
    ----------
    width, height : int
        Output cell dimensions (columns, rows).
    scale : float
        Noise sampling scale. Bands derive their period from their own
        preset but are proportional to this value, so changing ``scale``
        rescales all bands in lockstep.
    world_origin_x, world_origin_y : float
        World-space origin of cell (0,0) — used so adjacent tiles sample
        the same continuous noise field (no seams).
    cell_size : float
        World meters per cell.
    seed : int
        Master seed. Each band derives an independent sub-seed.
    biome : str
        Key into ``BAND_WEIGHTS`` for the composite blend. Also modulates
        strata frequency.
    vertical_scale_m : float
        World-meter multiplier applied to the blended composite.
    anisotropic_breakup_strength : float
        Directional noise breakup applied to each band before compositing.
        0.0 = disabled (default), up to 1.0 = maximum distortion.
    anti_grain_smoothing : float
        Box-filter smoothing applied to each band before compositing.
        0.0 = disabled (default), up to 1.0 = maximum smoothing.

    Returns
    -------
    BandedHeightmap
        With ``composite`` in world meters.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    biome_key = biome if biome in BAND_WEIGHTS else "dark_fantasy_default"

    macro = _generate_macro_band(
        width, height,
        world_origin_x=world_origin_x, world_origin_y=world_origin_y,
        cell_size=cell_size, scale=scale, seed=seed,
    )
    meso = _generate_meso_band(
        width, height,
        world_origin_x=world_origin_x, world_origin_y=world_origin_y,
        cell_size=cell_size, scale=scale, seed=seed,
    )
    micro = _generate_micro_band(
        width, height,
        world_origin_x=world_origin_x, world_origin_y=world_origin_y,
        cell_size=cell_size, scale=scale, seed=seed,
    )
    strata = _generate_strata_band(
        width, height,
        world_origin_x=world_origin_x, world_origin_y=world_origin_y,
        cell_size=cell_size, scale=scale, seed=seed, biome=biome_key,
    )
    warp = _generate_warp_field(
        width, height,
        world_origin_x=world_origin_x, world_origin_y=world_origin_y,
        cell_size=cell_size, scale=scale, seed=seed,
    )

    # Addendum 1 D.7: apply anisotropic breakup and anti-grain smoothing
    # to every composable band (not warp — it is informational only).
    if anisotropic_breakup_strength > 0:
        band_seed_base = seed & 0xFFFFFFFF
        macro = compute_anisotropic_breakup(
            macro, strength=anisotropic_breakup_strength, seed=band_seed_base)
        meso = compute_anisotropic_breakup(
            meso, strength=anisotropic_breakup_strength, seed=band_seed_base + 1)
        micro = compute_anisotropic_breakup(
            micro, strength=anisotropic_breakup_strength, seed=band_seed_base + 2)
        strata = compute_anisotropic_breakup(
            strata, strength=anisotropic_breakup_strength, seed=band_seed_base + 3)

    if anti_grain_smoothing > 0:
        macro = apply_anti_grain_smoothing(macro, strength=anti_grain_smoothing)
        meso = apply_anti_grain_smoothing(meso, strength=anti_grain_smoothing)
        micro = apply_anti_grain_smoothing(micro, strength=anti_grain_smoothing)
        strata = apply_anti_grain_smoothing(strata, strength=anti_grain_smoothing)

    weights = BAND_WEIGHTS[biome_key]
    bands = BandedHeightmap(
        macro_band=macro,
        meso_band=meso,
        micro_band=micro,
        strata_band=strata,
        warp_band=warp,
        composite=np.zeros_like(macro),  # filled below
        metadata={
            "biome": biome_key,
            "weights": weights,
            "scale": scale,
            "cell_size": cell_size,
            "world_origin": (world_origin_x, world_origin_y),
            "seed": int(seed),
            "vertical_scale_m": float(vertical_scale_m),
            "band_periods_m": dict(_BAND_PERIOD_M),
        },
    )
    bands.composite = compose_banded_heightmap(bands, weights) * vertical_scale_m
    return bands


def compose_banded_heightmap(
    bands: BandedHeightmap,
    weights: Tuple[float, float, float, float],
) -> np.ndarray:
    """Re-composite a heightmap from bands with new weights (macro, meso, micro, strata).

    This does not touch ``bands.composite`` — callers are expected to
    decide whether to re-assign it. Returns a dimensionless array; the
    vertical-scale multiplier lives in ``metadata['vertical_scale_m']``
    and is the caller's responsibility.
    """
    if len(weights) != 4:
        raise ValueError("weights must have 4 entries (macro, meso, micro, strata)")
    w_macro, w_meso, w_micro, w_strata = weights
    return (
        w_macro * bands.macro_band
        + w_meso * bands.meso_band
        + w_micro * bands.micro_band
        + w_strata * bands.strata_band
    )


# ---------------------------------------------------------------------------
# Pass registration
# ---------------------------------------------------------------------------


def pass_banded_macro(state, region):  # type: ignore[no-untyped-def]
    """Alternative to ``pass_macro_world`` that produces a banded heightmap.

    Writes the composite into ``state.mask_stack.height`` and stores the
    per-band numpy arrays in ``state.side_effects`` as metadata (since
    the mask stack has no dedicated channels for raw bands).

    Contract
    --------
    Consumes: (nothing required)
    Produces: ``height``
    Respects protected zones: yes (cells under an erosion-forbid zone
        keep their prior height)
    Requires scene read: no (baseline terrain generation)
    """
    # Local imports keep this module importable outside Blender.
    from .terrain_semantics import PassResult, ValidationIssue
    from ._terrain_world import _protected_mask, _region_slice

    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: list = []

    try:
        r_slice, c_slice = _region_slice(state, region)
    except Exception as exc:  # pragma: no cover - defensive
        issues.append(
            ValidationIssue(
                code="BANDED_REGION_INVALID",
                severity="hard",
                message=f"region slice failed: {exc}",
            )
        )
        return PassResult(
            pass_name="banded_macro",
            status="failed",
            duration_seconds=time.perf_counter() - t0,
            issues=issues,
        )

    h_full, w_full = stack.height.shape
    bands = generate_banded_heightmap(
        w_full,
        h_full,
        scale=100.0,
        world_origin_x=stack.world_origin_x,
        world_origin_y=stack.world_origin_y,
        cell_size=stack.cell_size,
        seed=int(state.intent.seed),
        biome=getattr(state.intent, "noise_profile", "dark_fantasy_default"),
    )

    # Apply to height, respecting protected zones.
    protected = _protected_mask(state, stack.height.shape, "banded_macro")
    new_height = stack.height.copy()
    # Region mask: only write inside (r_slice, c_slice).
    region_mask = np.zeros_like(stack.height, dtype=bool)
    region_mask[r_slice, c_slice] = True
    writable = region_mask & ~protected
    new_height[writable] = bands.composite[writable]

    stack.set("height", new_height, "banded_macro")

    # Stash band arrays as side-effect metadata. ``side_effects`` is a
    # list[str] per §5.8; we record a marker string and attach the real
    # arrays via a lightweight attribute on the state for downstream use.
    side_effect_token = f"banded_macro:bands@{id(bands):x}"
    if not hasattr(state, "banded_cache"):
        # Attribute-based cache; TerrainPipelineState is a dataclass but
        # Python dataclasses allow new attributes at runtime.
        try:
            state.banded_cache = {}  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        state.banded_cache[side_effect_token] = bands  # type: ignore[attr-defined]
    except Exception:
        pass

    return PassResult(
        pass_name="banded_macro",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=(),
        produced_channels=("height",),
        side_effects=[side_effect_token],
        metrics={
            "height_min": float(new_height.min()),
            "height_max": float(new_height.max()),
            "height_mean": float(new_height.mean()),
            "biome": bands.metadata["biome"],
            "weights": list(bands.metadata["weights"]),
            "band_macro_std": float(bands.macro_band.std()),
            "band_meso_std": float(bands.meso_band.std()),
            "band_micro_std": float(bands.micro_band.std()),
            "band_strata_std": float(bands.strata_band.std()),
        },
    )


def register_bundle_g_passes() -> None:
    """Register the banded-noise pass on the TerrainPassController.

    Kept separate from ``register_default_passes`` so Bundle G remains
    opt-in until the wider pipeline decides to adopt banded output as
    the default macro source.
    """
    from .terrain_pipeline import TerrainPassController
    from .terrain_semantics import PassDefinition

    TerrainPassController.register_pass(
        PassDefinition(
            name="banded_macro",
            func=pass_banded_macro,
            requires_channels=(),
            produces_channels=("height",),
            seed_namespace="banded_macro",
            requires_scene_read=False,
            may_modify_geometry=False,
            respects_protected_zones=True,
            supports_region_scope=True,
        )
    )


__all__ = [
    "BAND_WEIGHTS",
    "BandedHeightmap",
    "compute_anisotropic_breakup",
    "apply_anti_grain_smoothing",
    "generate_banded_heightmap",
    "compose_banded_heightmap",
    "pass_banded_macro",
    "register_bundle_g_passes",
    # Re-export so legacy callers can still reach the old backend via
    # ``from blender_addon.handlers.terrain_banded import generate_heightmap``.
    "generate_heightmap",
]
