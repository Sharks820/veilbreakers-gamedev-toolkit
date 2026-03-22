"""Dark fantasy palette validation and asset budget constants.

Validates albedo textures against the VeilBreakers dark fantasy aesthetic
rules: saturation caps, color temperature bias, value range, and roughness
map variation.

Also exports per-asset-type polygon budgets used by both the Blender-side
game_check action and the Unity-side poly budget editor script.

Exports:
    validate_palette       -- Validate an albedo texture against dark fantasy rules.
    validate_roughness_map -- Validate roughness map has sufficient variation.
    PALETTE_RULES          -- Default dark fantasy palette rule constants.
    ASSET_TYPE_BUDGETS     -- Per-asset-type polygon budget ranges.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore
    logger.warning("numpy not installed; palette validation unavailable")

from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PALETTE_RULES: dict[str, Any] = {
    "saturation_cap": 0.55,
    "value_range": (0.15, 0.75),
    "warm_temp_threshold": 0.55,
    "cool_bias_target": 0.6,
    "roughness_min_variance": 0.05,
    "metallic_max_mean": 0.3,
}

ASSET_TYPE_BUDGETS: dict[str, dict[str, int]] = {
    "hero":     {"min": 30000, "max": 50000},
    "mob":      {"min": 8000,  "max": 15000},
    "weapon":   {"min": 3000,  "max": 8000},
    "prop":     {"min": 500,   "max": 6000},
    "building": {"min": 5000,  "max": 15000},
}


# ---------------------------------------------------------------------------
# Hue classification helpers
# ---------------------------------------------------------------------------

def _is_warm_hue(hue_360: float) -> bool:
    """Check if a hue (0-360 degrees) falls in the warm range.

    Warm hues: 0-60 (red through yellow) and 300-360 (magenta through red).
    """
    return hue_360 <= 60.0 or hue_360 >= 300.0


def _is_cool_hue(hue_360: float) -> bool:
    """Check if a hue (0-360 degrees) falls in the cool range.

    Cool hues: 120-240 (green through blue).
    """
    return 120.0 <= hue_360 <= 240.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_palette(
    image_path: str,
    rules: dict | None = None,
    sample_pixels: int = 10000,
) -> dict:
    """Validate an albedo texture against dark fantasy palette rules.

    Checks:
        1. Mean saturation must be <= saturation_cap (default 0.55).
        2. Pixel values must mostly fall within value_range (0.15-0.75).
        3. Cool-toned pixels must outnumber warm pixels by cool_bias_target ratio.

    Args:
        image_path: Path to input albedo texture.
        rules: Optional override for PALETTE_RULES dict.
        sample_pixels: Number of pixels to sample for performance.
            Use 0 or negative to sample all pixels.

    Returns:
        Dict with:
            passed: bool -- True if no errors found.
            issues: list of {rule, value, threshold, severity}.
            stats: {mean_saturation, mean_value, cool_ratio, warm_ratio,
                    value_below_min_pct, value_above_max_pct, total_sampled}.
    """
    logger.info("Validating palette for: %s", image_path)
    if not _HAS_NUMPY:
        return {"error": "numpy is required for this operation but is not installed"}

    active_rules = {**PALETTE_RULES, **(rules or {})}
    sat_cap = active_rules["saturation_cap"]
    val_min, val_max = active_rules["value_range"]
    cool_target = active_rules["cool_bias_target"]

    # Load image
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img, dtype=np.float32) / 255.0
    total_pixels = arr.shape[0] * arr.shape[1]

    # Flatten to list of (R, G, B) pixels
    flat = arr.reshape(-1, 3)

    # Sample pixels for performance
    if sample_pixels > 0 and total_pixels > sample_pixels:
        rng = np.random.RandomState(42)
        indices = rng.choice(total_pixels, size=sample_pixels, replace=False)
        flat = flat[indices]

    n_sampled = len(flat)

    # Convert to HSV for each pixel
    # Using vectorized approach
    r, g, b = flat[:, 0], flat[:, 1], flat[:, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Hue (in 0-360)
    hue = np.zeros(n_sampled, dtype=np.float32)
    d_pos = delta > 1e-10
    # Red is max
    red_max = d_pos & (cmax == r)
    hue[red_max] = (((g[red_max] - b[red_max]) / delta[red_max]) % 6.0) * 60.0
    # Green is max
    green_max = d_pos & (cmax == g)
    hue[green_max] = (((b[green_max] - r[green_max]) / delta[green_max]) + 2.0) * 60.0
    # Blue is max
    blue_max = d_pos & (cmax == b)
    hue[blue_max] = (((r[blue_max] - g[blue_max]) / delta[blue_max]) + 4.0) * 60.0

    # Saturation (0-1)
    saturation = np.where(cmax > 1e-10, delta / cmax, 0.0)

    # Value (0-1)
    value = cmax

    # --- Compute stats ---
    mean_sat = float(np.mean(saturation))
    mean_val = float(np.mean(value))

    # Classify warm vs cool pixels (only those with enough saturation to have discernible hue)
    chromatic = saturation > 0.05
    n_chromatic = int(np.sum(chromatic))

    if n_chromatic > 0:
        warm_mask = chromatic & ((hue <= 60.0) | (hue >= 300.0))
        cool_mask = chromatic & (hue >= 120.0) & (hue <= 240.0)
        n_warm = int(np.sum(warm_mask))
        n_cool = int(np.sum(cool_mask))
        warm_ratio = n_warm / n_chromatic
        cool_ratio = n_cool / n_chromatic
    else:
        warm_ratio = 0.0
        cool_ratio = 1.0  # Achromatic passes cool bias

    # Value range violations
    below_min = float(np.mean(value < val_min))
    above_max = float(np.mean(value > val_max))

    stats = {
        "mean_saturation": round(mean_sat, 4),
        "mean_value": round(mean_val, 4),
        "cool_ratio": round(cool_ratio, 4),
        "warm_ratio": round(warm_ratio, 4),
        "value_below_min_pct": round(below_min * 100, 2),
        "value_above_max_pct": round(above_max * 100, 2),
        "total_sampled": n_sampled,
    }

    # --- Check rules ---
    issues: list[dict] = []

    # Rule 1: Saturation cap
    if mean_sat > sat_cap:
        issues.append({
            "rule": "saturation_cap",
            "value": round(mean_sat, 4),
            "threshold": sat_cap,
            "severity": "error",
        })

    # Rule 2: Value range -- warn if significant portion outside range
    if below_min > 0.3:
        issues.append({
            "rule": "value_too_dark",
            "value": round(below_min * 100, 2),
            "threshold": 30.0,
            "severity": "warning" if below_min < 0.5 else "error",
        })

    if above_max > 0.3:
        issues.append({
            "rule": "value_too_bright",
            "value": round(above_max * 100, 2),
            "threshold": 30.0,
            "severity": "warning" if above_max < 0.5 else "error",
        })

    # Rule 3: Cool bias -- warn if warm pixels dominate
    if cool_ratio < cool_target and n_chromatic > 0:
        issues.append({
            "rule": "warm_temperature_bias",
            "value": round(cool_ratio, 4),
            "threshold": cool_target,
            "severity": "warning",
        })

    has_errors = any(i["severity"] == "error" for i in issues)
    return {
        "passed": not has_errors,
        "issues": issues,
        "stats": stats,
    }


def validate_roughness_map(
    image_path: str,
    min_variance: float = 0.05,
) -> dict:
    """Validate roughness map has sufficient variation (not flat).

    A flat roughness map (uniform gray) produces unrealistic materials.
    Real surfaces have roughness variation from wear, dirt, and surface
    changes.

    Args:
        image_path: Path to roughness map texture.
        min_variance: Minimum acceptable variance of pixel values
            (normalized 0-1). Default 0.05.

    Returns:
        Dict with:
            passed: bool -- True if variance is sufficient.
            variance: float -- Actual variance of the roughness map.
            min_variance: float -- Threshold used.
            severity: str -- "error" if flat, None if passed.
    """
    logger.info("Validating roughness map: %s", image_path)
    if not _HAS_NUMPY:
        return {"error": "numpy is required for this operation but is not installed"}

    img = Image.open(image_path).convert("L")
    arr = np.array(img, dtype=np.float32) / 255.0

    variance = float(np.var(arr))

    if variance < min_variance:
        return {
            "passed": False,
            "variance": round(variance, 6),
            "min_variance": min_variance,
            "severity": "error",
        }

    return {
        "passed": True,
        "variance": round(variance, 6),
        "min_variance": min_variance,
        "severity": None,
    }
