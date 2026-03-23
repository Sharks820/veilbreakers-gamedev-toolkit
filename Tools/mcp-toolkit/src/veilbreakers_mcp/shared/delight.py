"""Albedo de-lighting algorithm using luminance channel analysis.

Removes baked-in lighting artifacts from AI-generated textures (e.g. Tripo3D
output) by estimating the lighting contribution via Gaussian-blurred luminance
and dividing it out, producing a flat-lit albedo suitable for PBR workflows.

Exports:
    delight_albedo  -- Remove baked-in lighting from an albedo texture.
"""

from __future__ import annotations

import os

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
    np = None  # type: ignore

from PIL import Image, ImageFilter


# ---------------------------------------------------------------------------
# ITU-R BT.601 luminance weights
# ---------------------------------------------------------------------------

_LUMA_R = 0.299
_LUMA_G = 0.587
_LUMA_B = 0.114


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def delight_albedo(
    image_path: str,
    output_path: str,
    blur_radius_pct: float = 0.12,
    strength: float = 0.75,
    clamp_min: float = 0.0,
    clamp_max: float = 1.0,
) -> dict:
    """Remove baked-in lighting from an albedo texture.

    Uses luminance channel analysis with Gaussian blur to estimate
    and divide out lighting, producing a flat-lit albedo suitable
    for PBR workflows.

    Algorithm:
        1. Convert to luminance (ITU-R BT.601 weights)
        2. Gaussian blur luminance to estimate lighting field
        3. Compute correction: target_luminance / lighting_estimate
        4. Apply per-channel correction blended by strength
        5. Clamp output values

    Args:
        image_path: Path to input albedo texture.
        output_path: Path to save de-lit result.
        blur_radius_pct: Gaussian blur radius as fraction of image
            dimension (0.0-1.0). Default 0.12 (12% of max dimension).
        strength: Blend strength between original and corrected (0.0-1.0).
            0.0 = no correction, 1.0 = full correction.
        clamp_min: Minimum output value clamp (0.0-1.0 range).
        clamp_max: Maximum output value clamp (0.0-1.0 range).

    Returns:
        Dict with keys:
            input, output, blur_radius, strength,
            mean_luminance_before, mean_luminance_after,
            correction_applied (bool).
    """
    if not _HAS_NUMPY:
        return {"error": "numpy is required for this operation but is not installed"}

    # Load image
    img = Image.open(image_path).convert("RGB")
    width, height = img.size

    # Convert to numpy float32 normalized to 0-1
    arr = np.array(img, dtype=np.float32) / 255.0

    # Calculate luminance using ITU-R BT.601 weights
    luminance = (
        _LUMA_R * arr[:, :, 0]
        + _LUMA_G * arr[:, :, 1]
        + _LUMA_B * arr[:, :, 2]
    )

    mean_lum_before = float(np.mean(luminance))

    # Edge case: all-black or all-white images -- skip correction
    if mean_lum_before < 0.005 or mean_lum_before > 0.995:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        except (OSError, ValueError):
            pass  # dirname may be empty for bare filenames
        img.save(output_path)
        return {
            "input": image_path,
            "output": output_path,
            "blur_radius": 0,
            "strength": strength,
            "mean_luminance_before": mean_lum_before,
            "mean_luminance_after": mean_lum_before,
            "correction_applied": False,
        }

    # Clip luminance minimum to avoid division by zero
    luminance = np.clip(luminance, 0.01, None)

    # Calculate blur radius in pixels
    blur_radius = int(max(width, height) * blur_radius_pct)
    # Edge case: very small images
    blur_radius = max(1, blur_radius)

    # Create luminance PIL Image, apply GaussianBlur
    lum_img = Image.fromarray(
        (luminance * 255).astype(np.uint8), mode="L"
    )
    blurred_lum_img = lum_img.filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )

    # Convert blurred luminance back to numpy float32
    lighting_estimate = (
        np.array(blurred_lum_img, dtype=np.float32) / 255.0
    )
    # Clip to avoid division by zero
    lighting_estimate = np.clip(lighting_estimate, 0.01, None)

    # Target luminance: mean of original
    target_luminance = float(np.mean(luminance))

    # Correction factor per pixel
    correction = target_luminance / lighting_estimate

    # Apply correction per channel
    corrected = np.empty_like(arr)
    for c in range(3):
        corrected[:, :, c] = arr[:, :, c] * correction

    # Blend with strength: result = (1-strength)*original + strength*corrected
    result = (1.0 - strength) * arr + strength * corrected

    # Clamp to valid range
    result = np.clip(result, clamp_min, clamp_max)

    # Convert back to uint8
    result_uint8 = (result * 255.0).astype(np.uint8)

    # Save result
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    except (OSError, ValueError):
        pass  # dirname may be empty for bare filenames
    result_img = Image.fromarray(result_uint8, "RGB")
    result_img.save(output_path)

    # Compute output luminance for metadata
    out_lum = (
        _LUMA_R * result[:, :, 0]
        + _LUMA_G * result[:, :, 1]
        + _LUMA_B * result[:, :, 2]
    )
    mean_lum_after = float(np.mean(out_lum))

    return {
        "input": image_path,
        "output": output_path,
        "blur_radius": blur_radius,
        "strength": strength,
        "mean_luminance_before": mean_lum_before,
        "mean_luminance_after": mean_lum_after,
        "correction_applied": True,
    }
