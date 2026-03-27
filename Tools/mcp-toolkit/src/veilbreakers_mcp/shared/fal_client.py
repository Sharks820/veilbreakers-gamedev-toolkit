"""fal.ai concept art generation and image analysis utilities.

Provides:
    generate_concept_art      - FLUX wrapper for AI concept art generation
    extract_color_palette     - Pillow quantize to extract dominant colors
    compose_style_board       - Compose reference board from images + palette
    test_silhouette_readability - Test shape readability at game distances

Gracefully handles missing fal-client package.
"""

from __future__ import annotations

import io
import math
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont


def _get_pixel_data(img: Image.Image):
    """Get pixel data from an image, compatible with Pillow 12+/14+.

    Uses get_flattened_data() when available (Pillow 14+), falls back to
    getdata() for older versions.
    """
    if hasattr(img, "get_flattened_data"):
        return img.get_flattened_data()
    return img.getdata()

try:
    import fal_client as _fal  # type: ignore[import-untyped]

    _FAL_AVAILABLE = True
except ImportError:
    _FAL_AVAILABLE = False


# ---------------------------------------------------------------------------
# 1. Concept Art Generation (fal.ai FLUX)
# ---------------------------------------------------------------------------


def generate_concept_art(
    prompt: str,
    style: str = "fantasy",
    width: int = 1024,
    height: int = 1024,
    output_dir: str = ".",
    fal_key: str | None = None,
) -> dict:
    """Generate concept art using fal.ai FLUX model.

    Args:
        prompt: Text description of the concept art to generate.
        style: Art style prefix (e.g. "fantasy", "sci-fi", "stylized").
        width: Output image width in pixels.
        height: Output image height in pixels.
        output_dir: Directory to save the output image.
        fal_key: fal.ai API key. If None/empty, returns unavailable status.

    Returns:
        Dict with status, message, and optionally image_path.
    """
    if not fal_key:
        return {
            "status": "unavailable",
            "message": "FAL_KEY not configured. Set fal_key to enable AI concept art generation.",
        }

    # Ensure fal-client can find the key via its env var
    prev_fal_key = os.environ.get("FAL_KEY")
    os.environ["FAL_KEY"] = fal_key

    if not _FAL_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "fal-client package not installed. Run: pip install fal-client",
        }

    import os

    try:
        styled_prompt = f"{style} style, {prompt}"

        result = _fal.subscribe(
            "fal-ai/flux/dev",
            arguments={
                "prompt": styled_prompt,
                "image_size": {"width": width, "height": height},
                "num_images": 1,
            },
        )

        images = result.get("images", [])
        if not images:
            return {
                "status": "error",
                "message": "No images returned from fal.ai",
            }

        image_url = images[0].get("url", "")

        # Validate URL scheme -- only allow HTTPS from fal.ai CDN
        if not image_url.startswith("https://"):
            return {
                "status": "error",
                "message": f"Unexpected image URL scheme: {image_url[:40]}",
            }

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "concept_art.png")

        # Download image via httpx (fal-client has no download method)
        import httpx
        resp = httpx.get(image_url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)

        return {
            "status": "success",
            "image_path": output_path,
            "prompt": styled_prompt,
            "width": width,
            "height": height,
        }

    except (ConnectionError, TimeoutError, OSError, ValueError, KeyError) as exc:
        return {
            "status": "error",
            "message": str(exc),
        }
    finally:
        # Restore original FAL_KEY
        if prev_fal_key is not None:
            os.environ["FAL_KEY"] = prev_fal_key
        elif "FAL_KEY" in os.environ:
            del os.environ["FAL_KEY"]


# ---------------------------------------------------------------------------
# 2. Color Palette Extraction
# ---------------------------------------------------------------------------


def extract_color_palette(
    image_path_or_bytes: str | bytes,
    num_colors: int = 8,
    swatch_size: int = 64,
) -> dict:
    """Extract dominant colors from an image using Pillow quantize.

    Args:
        image_path_or_bytes: File path or raw PNG/JPEG bytes.
        num_colors: Number of dominant colors to extract (1-256).
        swatch_size: Width and height of each color swatch in the output PNG.

    Returns:
        Dict with colors list (each has rgb, hex, percentage), swatch_bytes (PNG).
    """
    if isinstance(image_path_or_bytes, bytes):
        img = Image.open(io.BytesIO(image_path_or_bytes)).convert("RGB")
    else:
        img = Image.open(image_path_or_bytes).convert("RGB")

    # Quantize to extract dominant colors
    quantized = img.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()
    if palette_data is None:
        return {"colors": [], "swatch_bytes": b""}

    # Count pixels per palette index
    pixel_counts: dict[int, int] = {}
    total_pixels = quantized.size[0] * quantized.size[1]
    for pixel in _get_pixel_data(quantized):
        pixel_counts[pixel] = pixel_counts.get(pixel, 0) + 1

    # Build color list sorted by frequency
    colors: list[dict[str, Any]] = []
    for idx in sorted(pixel_counts, key=lambda k: pixel_counts[k], reverse=True):
        if len(colors) >= num_colors:
            break
        r = palette_data[idx * 3]
        g = palette_data[idx * 3 + 1]
        b = palette_data[idx * 3 + 2]
        hex_str = f"#{r:02x}{g:02x}{b:02x}"
        percentage = round(pixel_counts[idx] / total_pixels * 100, 1)
        colors.append({
            "rgb": [r, g, b],
            "hex": hex_str,
            "percentage": percentage,
        })

    # Generate swatch image
    swatch_width = swatch_size * len(colors)
    swatch_height = swatch_size
    swatch_img = Image.new("RGB", (max(1, swatch_width), swatch_height), (0, 0, 0))
    draw = ImageDraw.Draw(swatch_img)

    for i, color in enumerate(colors):
        x0 = i * swatch_size
        x1 = x0 + swatch_size
        rgb = tuple(color["rgb"])
        draw.rectangle([x0, 0, x1, swatch_height], fill=rgb)

    swatch_buf = io.BytesIO()
    swatch_img.save(swatch_buf, format="PNG")
    swatch_bytes = swatch_buf.getvalue()

    return {
        "colors": colors,
        "swatch_bytes": swatch_bytes,
    }


# ---------------------------------------------------------------------------
# 3. Style Board Composition
# ---------------------------------------------------------------------------


def compose_style_board(
    images: Sequence[str | bytes],
    palette_colors: list[dict] | None = None,
    title: str = "Style Board",
    annotations: list[str] | None = None,
    board_width: int = 2048,
) -> bytes:
    """Compose multiple images and a color palette into a reference board PNG.

    Args:
        images: List of file paths or PNG bytes for reference images.
        palette_colors: List of dicts with "rgb" key ([r, g, b]) for palette strip.
        title: Title text for the board header.
        annotations: Optional text labels for each image.
        board_width: Total width of the output board in pixels.

    Returns:
        PNG bytes of the composed style board.
    """
    # Load images
    loaded: list[Image.Image] = []
    for src in images:
        if isinstance(src, bytes):
            loaded.append(Image.open(io.BytesIO(src)).convert("RGB"))
        else:
            loaded.append(Image.open(src).convert("RGB"))

    if not loaded:
        # Return minimal board
        board = Image.new("RGB", (board_width, 200), (30, 30, 30))
        buf = io.BytesIO()
        board.save(buf, format="PNG")
        return buf.getvalue()

    # Layout: images arranged in a row, scaled to fit board_width
    num_images = len(loaded)
    header_height = 60
    palette_height = 80 if palette_colors else 0
    padding = 10

    # Calculate per-image width
    available_width = board_width - (num_images + 1) * padding
    img_width = max(1, available_width // num_images)

    # Scale images to uniform width, preserving aspect ratio
    scaled: list[Image.Image] = []
    max_img_height = 0
    for img in loaded:
        ratio = img_width / img.width
        new_height = max(1, int(img.height * ratio))
        scaled.append(img.resize((img_width, new_height), Image.Resampling.LANCZOS))
        max_img_height = max(max_img_height, new_height)

    total_height = header_height + max_img_height + palette_height + padding * 3

    board = Image.new("RGB", (board_width, total_height), (30, 30, 30))
    draw = ImageDraw.Draw(board)

    # Draw title
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except (IOError, OSError):
        font = ImageFont.load_default()

    draw.text((padding, padding), title, fill=(255, 255, 255), font=font)

    # Place images
    y_offset = header_height + padding
    for i, img in enumerate(scaled):
        x_offset = padding + i * (img_width + padding)
        board.paste(img, (x_offset, y_offset))

        # Annotation
        if annotations and i < len(annotations):
            draw.text(
                (x_offset, y_offset + img.height + 2),
                annotations[i],
                fill=(200, 200, 200),
                font=font,
            )

    # Draw palette strip
    if palette_colors:
        palette_y = header_height + max_img_height + padding * 2
        swatch_w = min(60, (board_width - padding * 2) // max(1, len(palette_colors)))
        for i, color in enumerate(palette_colors):
            rgb = tuple(color.get("rgb", [128, 128, 128]))
            x0 = padding + i * swatch_w
            draw.rectangle(
                [x0, palette_y, x0 + swatch_w - 2, palette_y + palette_height - 10],
                fill=rgb,
            )

    buf = io.BytesIO()
    board.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4. Silhouette Readability Test
# ---------------------------------------------------------------------------


def test_silhouette_readability(
    image_path_or_bytes: str | bytes,
    threshold: int = 128,
    min_contrast_ratio: float = 0.3,
    distances: list[float] | None = None,
) -> dict:
    """Test shape readability at game distances via silhouette analysis.

    Converts the image to a binary silhouette (dark pixels below threshold
    vs. background), then analyzes whether the shape is recognizable by
    checking foreground/background contrast ratio and shape compactness
    at multiple simulated view distances.

    Args:
        image_path_or_bytes: File path or PNG/JPEG bytes.
        threshold: Grayscale threshold for silhouette extraction (0-255).
        min_contrast_ratio: Minimum fg/bg pixel ratio to consider readable.
        distances: Simulated distance multipliers (1.0 = full, 0.5 = half-res, etc.).

    Returns:
        Dict with readable (bool), distances (list of per-distance results),
        overall_contrast_ratio, silhouette_coverage.
    """
    if distances is None:
        distances = [1.0, 0.5, 0.25]

    if isinstance(image_path_or_bytes, bytes):
        img = Image.open(io.BytesIO(image_path_or_bytes)).convert("L")
    else:
        img = Image.open(image_path_or_bytes).convert("L")

    width, height = img.size
    total_pixels = width * height

    # Overall silhouette analysis at full resolution
    fg_count = sum(1 for p in _get_pixel_data(img) if p < threshold)
    bg_count = total_pixels - fg_count

    coverage = fg_count / total_pixels if total_pixels > 0 else 0.0
    contrast_ratio = min(fg_count, bg_count) / max(fg_count, bg_count) if max(fg_count, bg_count) > 0 else 0.0

    distance_results: list[dict] = []
    all_readable = True

    for dist in distances:
        # Simulate distance by downscaling
        scale = max(0.01, dist)
        new_w = max(4, int(width * scale))
        new_h = max(4, int(height * scale))
        scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        scaled_total = new_w * new_h
        scaled_fg = sum(1 for p in _get_pixel_data(scaled) if p < threshold)
        scaled_bg = scaled_total - scaled_fg

        dist_coverage = scaled_fg / scaled_total if scaled_total > 0 else 0.0
        dist_contrast = (
            min(scaled_fg, scaled_bg) / max(scaled_fg, scaled_bg)
            if max(scaled_fg, scaled_bg) > 0
            else 0.0
        )

        # Shape is readable if:
        # 1. There's meaningful foreground (coverage > 5%)
        # 2. Contrast ratio meets minimum threshold
        dist_readable = dist_coverage > 0.05 and dist_contrast >= min_contrast_ratio

        if not dist_readable:
            all_readable = False

        distance_results.append({
            "distance": dist,
            "resolution": f"{new_w}x{new_h}",
            "coverage": round(dist_coverage, 4),
            "contrast_ratio": round(dist_contrast, 4),
            "readable": dist_readable,
        })

    return {
        "readable": all_readable,
        "distances": distance_results,
        "overall_contrast_ratio": round(contrast_ratio, 4),
        "silhouette_coverage": round(coverage, 4),
    }
