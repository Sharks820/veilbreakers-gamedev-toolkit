"""Visual regression detection between screenshot pairs.

Uses Pillow to compute pixel-level differences between a reference image
and a current image, highlighting changed regions in a diff overlay.

Functions:
    compare_screenshots          - Compare two screenshots, return match/diff stats
    generate_diff_image          - Generate a highlighted diff image
    capture_regression_baseline  - Copy screenshots to a baseline directory
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

logger = logging.getLogger(__name__)


# Noise threshold per channel (0-255) -- below this, differences are
# treated as insignificant (monitor gamma, JPEG artifacts, etc.)
_NOISE_THRESHOLD = 10


def compare_screenshots(
    reference_path: str,
    current_path: str,
    threshold: float = 0.01,
) -> dict:
    """Compare a reference screenshot against a current screenshot.

    Args:
        reference_path: Path to the reference (baseline) image.
        current_path: Path to the current (test) image.
        threshold: Maximum acceptable fraction of changed pixels (0.01 = 1%).

    Returns:
        Dict with keys:
            match (bool): True if diff_percentage <= threshold.
            diff_percentage (float): Fraction of pixels that changed (0.0 - 1.0).
            diff_image_path (str | None): Path to the generated diff image,
                or None if images match.
            reference_size (tuple): (width, height) of the reference image.
            current_size (tuple): (width, height) of the current image.
    """
    logger.info("Comparing screenshots: %s vs %s (threshold=%.4f)", reference_path, current_path, threshold)
    ref_img = Image.open(reference_path).convert("RGB")
    cur_img = Image.open(current_path).convert("RGB")

    ref_size = ref_img.size
    cur_size = cur_img.size

    # Resize current to match reference if sizes differ
    if cur_img.size != ref_img.size:
        logger.warning("Screenshot sizes differ (ref=%s, cur=%s), resizing current", ref_size, cur_size)
        original_cur = cur_img
        cur_img = cur_img.resize(ref_img.size, Image.Resampling.LANCZOS)
        original_cur.close()

    # Compute pixel-level difference
    diff = ImageChops.difference(ref_img, cur_img)

    # Count pixels that exceed the noise threshold
    width, height = ref_img.size
    total_pixels = width * height
    changed_pixels = 0

    diff_arr = np.array(diff, dtype=np.uint8)  # shape (H, W, 3)
    # A pixel is "changed" if any channel exceeds the noise threshold
    changed_pixels = int(np.any(diff_arr > _NOISE_THRESHOLD, axis=2).sum())

    diff_percentage = changed_pixels / total_pixels if total_pixels > 0 else 0.0
    match = diff_percentage <= threshold

    # Generate diff image only if there are differences
    diff_image_path = None
    if not match:
        diff_image_path = _diff_output_path(reference_path)
        generate_diff_image(reference_path, current_path, diff_image_path)

    ref_img.close()
    cur_img.close()

    return {
        "match": match,
        "diff_percentage": round(diff_percentage, 6),
        "diff_image_path": diff_image_path,
        "reference_size": ref_size,
        "current_size": cur_size,
    }


def capture_regression_baseline(
    screenshot_paths: list[str],
    baseline_dir: str,
) -> dict:
    """Copy screenshots to a baseline directory for future regression comparisons.

    Each screenshot is stored as ``baseline_{angle_id}.png`` using the order of
    *screenshot_paths*.  Existing baselines for the same angle ID are silently
    overwritten.

    Args:
        screenshot_paths: Ordered list of screenshot file paths (one per angle).
        baseline_dir: Directory to store baseline images.  Created if absent.

    Returns:
        Dict with keys:
            baseline_count (int): Number of files successfully copied.
            baseline_dir (str): Absolute path to the baseline directory.
            paths (list[str]): Absolute paths of each baseline file written.
    """
    baseline_dir_path = Path(baseline_dir)
    baseline_dir_path.mkdir(parents=True, exist_ok=True)

    written_paths: list[str] = []
    for angle_id, src in enumerate(screenshot_paths):
        if not os.path.isfile(src):
            logger.warning("capture_regression_baseline: source not found: %s", src)
            continue
        dest = str(baseline_dir_path / f"baseline_{angle_id}.png")
        shutil.copy2(src, dest)
        written_paths.append(dest)
        logger.debug("Baseline captured: %s -> %s", src, dest)

    return {
        "baseline_count": len(written_paths),
        "baseline_dir": str(baseline_dir_path.resolve()),
        "paths": written_paths,
    }


def _diff_output_path(reference_path: str) -> str:
    """Derive the diff output path from the reference path.

    Inserts '_diff' before the file extension.
    """
    dot_idx = reference_path.rfind(".")
    if dot_idx == -1:
        return reference_path + "_diff"
    return reference_path[:dot_idx] + "_diff" + reference_path[dot_idx:]


def generate_diff_image(
    reference_path: str,
    current_path: str,
    output_path: str,
) -> str:
    """Generate a highlighted diff image showing changed regions.

    Changed pixels are overlaid in semi-transparent red on top of
    the reference image. Unchanged pixels are shown dimmed.

    Args:
        reference_path: Path to the reference image.
        current_path: Path to the current image.
        output_path: Path to save the diff image.

    Returns:
        The output_path where the diff image was saved.
    """
    logger.info("Generating diff image: %s", output_path)
    ref_img = Image.open(reference_path).convert("RGB")
    cur_img = Image.open(current_path).convert("RGB")

    # Resize current to match reference if sizes differ
    if cur_img.size != ref_img.size:
        original_cur = cur_img
        cur_img = cur_img.resize(ref_img.size, Image.Resampling.LANCZOS)
        original_cur.close()

    # Compute difference
    diff = ImageChops.difference(ref_img, cur_img)

    # Create output image: dimmed reference as base
    output = ref_img.copy()
    # Dim the base image
    output = Image.blend(output, Image.new("RGB", output.size, (0, 0, 0)), 0.5)

    # Create red overlay for changed pixels using numpy
    diff_arr = np.array(diff, dtype=np.uint8)  # shape (H, W, 3)
    changed_mask = np.any(diff_arr > _NOISE_THRESHOLD, axis=2)  # (H, W) bool

    # Build RGBA overlay: red (255,0,0,180) where changed, transparent elsewhere
    h, w = changed_mask.shape
    overlay_arr = np.zeros((h, w, 4), dtype=np.uint8)
    overlay_arr[changed_mask, 0] = 255   # R
    overlay_arr[changed_mask, 3] = 180   # A
    overlay = Image.fromarray(overlay_arr, "RGBA")

    # Composite overlay onto dimmed reference
    output = output.convert("RGBA")
    output = Image.alpha_composite(output, overlay)
    output = output.convert("RGB")

    output.save(output_path)

    ref_img.close()
    cur_img.close()

    return output_path
