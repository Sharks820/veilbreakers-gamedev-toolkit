"""Visual regression detection between screenshot pairs.

Uses Pillow to compute pixel-level differences between a reference image
and a current image, highlighting changed regions in a diff overlay.

Functions:
    compare_screenshots  - Compare two screenshots, return match/diff stats
    generate_diff_image  - Generate a highlighted diff image
"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw


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
    ref_img = Image.open(reference_path).convert("RGB")
    cur_img = Image.open(current_path).convert("RGB")

    ref_size = ref_img.size
    cur_size = cur_img.size

    # Resize current to match reference if sizes differ
    if cur_img.size != ref_img.size:
        original_cur = cur_img
        cur_img = cur_img.resize(ref_img.size, Image.LANCZOS)
        original_cur.close()

    # Compute pixel-level difference
    diff = ImageChops.difference(ref_img, cur_img)

    # Count pixels that exceed the noise threshold
    width, height = ref_img.size
    total_pixels = width * height
    changed_pixels = 0

    diff_bytes = diff.tobytes()
    # RGB = 3 bytes per pixel; check if any channel exceeds noise threshold
    for i in range(0, len(diff_bytes), 3):
        if (diff_bytes[i] > _NOISE_THRESHOLD
                or diff_bytes[i + 1] > _NOISE_THRESHOLD
                or diff_bytes[i + 2] > _NOISE_THRESHOLD):
            changed_pixels += 1

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
    ref_img = Image.open(reference_path).convert("RGB")
    cur_img = Image.open(current_path).convert("RGB")

    # Resize current to match reference if sizes differ
    if cur_img.size != ref_img.size:
        original_cur = cur_img
        cur_img = cur_img.resize(ref_img.size, Image.LANCZOS)
        original_cur.close()

    # Compute difference
    diff = ImageChops.difference(ref_img, cur_img)

    # Create output image: dimmed reference as base
    output = ref_img.copy()
    # Dim the base image
    output = Image.blend(output, Image.new("RGB", output.size, (0, 0, 0)), 0.5)

    # Create red overlay for changed pixels
    overlay = Image.new("RGBA", ref_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    diff_bytes = diff.tobytes()
    width = ref_img.size[0]

    # RGB = 3 bytes per pixel
    pixel_idx = 0
    for i in range(0, len(diff_bytes), 3):
        if (diff_bytes[i] > _NOISE_THRESHOLD
                or diff_bytes[i + 1] > _NOISE_THRESHOLD
                or diff_bytes[i + 2] > _NOISE_THRESHOLD):
            x = pixel_idx % width
            y = pixel_idx // width
            overlay_draw.point((x, y), fill=(255, 0, 0, 180))
        pixel_idx += 1

    # Composite overlay onto dimmed reference
    output = output.convert("RGBA")
    output = Image.alpha_composite(output, overlay)
    output = output.convert("RGB")

    output.save(output_path)

    ref_img.close()
    cur_img.close()

    return output_path
