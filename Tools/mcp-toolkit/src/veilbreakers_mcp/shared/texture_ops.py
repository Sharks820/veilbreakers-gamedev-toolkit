"""Pillow-based texture editing operations for surgical texture manipulation.

All mask-based edits use Gaussian-feathered edges for seamless blending.
This module runs on the MCP server side (not inside Blender).

Functions:
    generate_uv_mask       - Create feathered mask from UV polygon coordinates
    generate_uv_mask_image - Same as above but returns PIL Image for chaining
    apply_hsv_adjustment   - Shift hue/saturation/value on masked region
    blend_seams            - Smooth color transitions at UV island boundaries
    make_tileable          - Cross-fade edges so texture tiles seamlessly
    render_wear_map        - Produce grayscale wear/damage map from curvature data
    inpaint_texture        - AI texture inpainting via fal.ai FLUX Fill endpoint
"""

from __future__ import annotations

import base64
import colorsys
import io
import math
from typing import Sequence

from PIL import Image, ImageDraw, ImageFilter

try:
    import fal_client as _fal  # type: ignore[import-untyped]

    _FAL_AVAILABLE = True
except ImportError:
    _FAL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

UVCoord = tuple[float, float]
UVPolygon = Sequence[UVCoord]
PixelCoord = tuple[int, int]


# ---------------------------------------------------------------------------
# 1. UV Mask Generation
# ---------------------------------------------------------------------------

def _uv_to_pixel(u: float, v: float, size: int) -> tuple[int, int]:
    """Convert UV coordinate (0-1) to pixel coordinate.

    UV space has (0,0) at bottom-left; image space has (0,0) at top-left.
    """
    px = int(u * size)
    py = int((1.0 - v) * size)
    # Clamp to valid pixel range
    px = max(0, min(px, size - 1))
    py = max(0, min(py, size - 1))
    return (px, py)


def generate_uv_mask_image(
    polygons: Sequence[UVPolygon],
    texture_size: int,
    feather_radius: int = 5,
) -> Image.Image:
    """Generate a feathered UV mask as a PIL Image (L-mode).

    Args:
        polygons: List of UV polygons, each a sequence of (u, v) coordinates in 0-1 range.
        texture_size: Width and height of the output mask in pixels.
        feather_radius: Gaussian blur radius for edge feathering.
            0 = hard edges, >0 = soft falloff for seamless blending.

    Returns:
        PIL Image in L mode (grayscale). 255 inside polygons, 0 outside,
        with Gaussian-feathered edges producing gradient values at boundaries.
    """
    # Create sharp binary mask
    sharp_mask = Image.new("L", (texture_size, texture_size), 0)
    draw = ImageDraw.Draw(sharp_mask)

    for poly in polygons:
        pixel_coords = [_uv_to_pixel(u, v, texture_size) for u, v in poly]
        if len(pixel_coords) >= 3:
            draw.polygon(pixel_coords, fill=255)

    if feather_radius <= 0:
        return sharp_mask

    # Feathered edge approach:
    # 1. Erode the sharp mask to get a "core" that stays fully white
    # 2. Blur the original sharp mask for soft edges
    # 3. Composite: core interior at full 255, blurred falloff at edges
    #
    # Erosion via MinFilter applied repeatedly:
    eroded = sharp_mask.copy()
    for _ in range(feather_radius):
        eroded = eroded.filter(ImageFilter.MinFilter(3))

    # Blur the original sharp mask to create soft falloff
    blurred = sharp_mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))

    # Composite: where eroded is white (interior), use full 255;
    # elsewhere, use the blurred (soft) values
    result = Image.composite(sharp_mask, blurred, eroded)

    return result


def generate_uv_mask(
    polygons: Sequence[UVPolygon],
    texture_size: int,
    feather_radius: int = 5,
) -> bytes:
    """Generate a feathered UV mask as PNG bytes.

    See generate_uv_mask_image for parameter details.

    Returns:
        PNG-encoded bytes of the L-mode mask image.
    """
    mask = generate_uv_mask_image(polygons, texture_size, feather_radius)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 2. HSV Color Adjustment
# ---------------------------------------------------------------------------

def apply_hsv_adjustment(
    image_bytes: bytes,
    mask_bytes: bytes,
    hue_shift: float = 0.0,
    saturation_scale: float = 1.0,
    value_scale: float = 1.0,
) -> bytes:
    """Apply HSV color adjustment to masked region with alpha blending.

    CRITICAL: Partial mask values (1-254) produce smooth blending between
    original and adjusted pixels. This is what makes feathered mask edges
    seamless -- no hard color discontinuities.

    Args:
        image_bytes: Source image as PNG bytes.
        mask_bytes: Mask image (L-mode) as PNG bytes. 255 = full effect, 0 = no effect.
        hue_shift: Amount to rotate hue (0.0-1.0 wraps). 0.5 = opposite color.
        saturation_scale: Multiplier for saturation. 1.0 = unchanged.
        value_scale: Multiplier for value/brightness. 1.0 = unchanged.

    Returns:
        PNG bytes of the adjusted image.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    mask = Image.open(io.BytesIO(mask_bytes)).convert("L")

    if img.size != mask.size:
        mask = mask.resize(img.size, Image.Resampling.LANCZOS)

    width, height = img.size

    # Try numpy path for large images, fall back to pixel-by-pixel
    try:
        import numpy as np
        return _hsv_adjust_numpy(img, mask, hue_shift, saturation_scale, value_scale)
    except ImportError:
        pass

    # Pixel-by-pixel fallback
    result = img.copy()
    img_pixels = img.load()
    mask_pixels = mask.load()
    result_pixels = result.load()

    for y in range(height):
        for x in range(width):
            m = mask_pixels[x, y]
            if m == 0:
                continue  # Unmasked: keep original (bit-identical)

            r, g, b = img_pixels[x, y]
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            # Apply adjustments
            h = (h + hue_shift) % 1.0
            s = max(0.0, min(1.0, s * saturation_scale))
            v = max(0.0, min(1.0, v * value_scale))

            rn, gn, bn = colorsys.hsv_to_rgb(h, s, v)
            adjusted = (round(rn * 255), round(gn * 255), round(bn * 255))

            if m == 255:
                result_pixels[x, y] = adjusted
            else:
                # Alpha blend for seamless feathered edges
                alpha = m / 255.0
                result_pixels[x, y] = (
                    round(r * (1 - alpha) + adjusted[0] * alpha),
                    round(g * (1 - alpha) + adjusted[1] * alpha),
                    round(b * (1 - alpha) + adjusted[2] * alpha),
                )

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


def _hsv_adjust_numpy(
    img: Image.Image,
    mask: Image.Image,
    hue_shift: float,
    saturation_scale: float,
    value_scale: float,
) -> bytes:
    """Numpy-accelerated HSV adjustment with mask-based alpha blending."""
    import numpy as np

    img_arr = np.array(img, dtype=np.float64) / 255.0
    mask_arr = np.array(mask, dtype=np.float64) / 255.0

    # Find pixels where mask > 0
    active = mask_arr > 0

    if not np.any(active):
        # No masked pixels -- return original
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Extract RGB for active pixels
    r = img_arr[:, :, 0]
    g = img_arr[:, :, 1]
    b = img_arr[:, :, 2]

    # Vectorized RGB to HSV
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Hue calculation
    h = np.zeros_like(cmax)
    # Where delta > 0
    d_pos = delta > 1e-10
    # Red is max
    red_max = d_pos & (cmax == r)
    h[red_max] = ((g[red_max] - b[red_max]) / delta[red_max]) % 6.0
    # Green is max
    green_max = d_pos & (cmax == g)
    h[green_max] = ((b[green_max] - r[green_max]) / delta[green_max]) + 2.0
    # Blue is max
    blue_max = d_pos & (cmax == b)
    h[blue_max] = ((r[blue_max] - g[blue_max]) / delta[blue_max]) + 4.0

    h = (h / 6.0) % 1.0  # Normalize to 0-1

    # Saturation
    s = np.where(cmax > 1e-10, delta / cmax, 0.0)

    # Value
    v = cmax

    # Apply adjustments only to active pixels
    h_adj = h.copy()
    s_adj = s.copy()
    v_adj = v.copy()

    h_adj[active] = (h[active] + hue_shift) % 1.0
    s_adj[active] = np.clip(s[active] * saturation_scale, 0.0, 1.0)
    v_adj[active] = np.clip(v[active] * value_scale, 0.0, 1.0)

    # Vectorized HSV to RGB
    c = v_adj * s_adj
    h6 = h_adj * 6.0
    x = c * (1.0 - np.abs(h6 % 2.0 - 1.0))
    m = v_adj - c

    r_out = np.zeros_like(h)
    g_out = np.zeros_like(h)
    b_out = np.zeros_like(h)

    # Sector 0: 0 <= h6 < 1
    sel = (h6 >= 0) & (h6 < 1)
    r_out[sel] = c[sel]; g_out[sel] = x[sel]; b_out[sel] = 0
    # Sector 1
    sel = (h6 >= 1) & (h6 < 2)
    r_out[sel] = x[sel]; g_out[sel] = c[sel]; b_out[sel] = 0
    # Sector 2
    sel = (h6 >= 2) & (h6 < 3)
    r_out[sel] = 0; g_out[sel] = c[sel]; b_out[sel] = x[sel]
    # Sector 3
    sel = (h6 >= 3) & (h6 < 4)
    r_out[sel] = 0; g_out[sel] = x[sel]; b_out[sel] = c[sel]
    # Sector 4
    sel = (h6 >= 4) & (h6 < 5)
    r_out[sel] = x[sel]; g_out[sel] = 0; b_out[sel] = c[sel]
    # Sector 5
    sel = (h6 >= 5) & (h6 < 6)
    r_out[sel] = c[sel]; g_out[sel] = 0; b_out[sel] = x[sel]

    r_out += m
    g_out += m
    b_out += m

    # Build adjusted image array
    adjusted = np.stack([r_out, g_out, b_out], axis=-1)

    # Alpha blend: result = (1 - alpha) * original + alpha * adjusted
    alpha_3d = mask_arr[:, :, np.newaxis]
    result = (1.0 - alpha_3d) * img_arr + alpha_3d * adjusted

    # Convert back to uint8
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)

    result_img = Image.fromarray(result, "RGB")
    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 3. Seam Blending
# ---------------------------------------------------------------------------

def blend_seams(
    image_bytes: bytes,
    seam_pixels: Sequence[PixelCoord],
    blend_radius: int = 6,
) -> bytes:
    """Blend color transitions at UV seam boundaries.

    Creates a smooth gradient across seam pixels using Gaussian blurring
    weighted by a distance mask from the seam.

    Args:
        image_bytes: Source image as PNG bytes.
        seam_pixels: List of (x, y) pixel coordinates along the seam.
        blend_radius: Gaussian blur radius for blending. Higher = wider blend zone.

    Returns:
        PNG bytes of the blended image.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    # Create seam mask: white at seam pixels, black elsewhere
    seam_mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(seam_mask)
    for x, y in seam_pixels:
        if 0 <= x < width and 0 <= y < height:
            draw.point((x, y), fill=255)

    # Dilate the seam mask slightly so the blend zone extends on both sides
    dilated_mask = seam_mask.copy()
    for _ in range(blend_radius):
        dilated_mask = dilated_mask.filter(ImageFilter.MaxFilter(3))

    # Blur the dilated mask to create a smooth falloff gradient
    blend_mask = dilated_mask.filter(ImageFilter.GaussianBlur(radius=blend_radius))

    # Create blurred version of the image
    blurred_img = img.filter(ImageFilter.GaussianBlur(radius=blend_radius))

    # Composite: blend between original and blurred using the smooth seam mask
    # Where mask is bright (near seam), use blurred; where dark, keep original
    result = Image.composite(blurred_img, img, blend_mask)

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4. Tileable Texture Generation
# ---------------------------------------------------------------------------

def make_tileable(
    image_bytes: bytes,
    overlap_pct: float = 0.15,
) -> bytes:
    """Make a texture tileable via symmetric mirror-blend at edges.

    For each axis, pixels in the overlap zone are blended with their
    mirror-partner from the opposite edge using the formula:

        result[x] = t(x) * src[x] + (1 - t(x)) * src[W - 1 - x]

    The weight t transitions smoothly from 0.5 at edge (x=0) to 1.0 at
    the interior boundary (x=overlap). The formula is symmetric:
    at x=0: result = 0.5*src[0] + 0.5*src[W-1], and at x=W-1:
    result = 0.5*src[W-1] + 0.5*src[0] -- identical values, guaranteeing
    seamless tiling.

    Both edge zones are computed simultaneously from unmodified source data
    to ensure perfect symmetry.

    Args:
        image_bytes: Source image as PNG bytes.
        overlap_pct: Fraction of width/height for the cross-fade zone (0.05-0.5).

    Returns:
        PNG bytes of the tileable image.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size

    try:
        import numpy as np
    except ImportError:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    src = np.array(img, dtype=np.float64)
    result = src.copy()
    overlap_w = max(2, int(width * overlap_pct))
    overlap_h = max(2, int(height * overlap_pct))

    # --- Horizontal mirror-blend ---
    # Weight: 0.5 at edge -> 1.0 at interior, cosine-smoothed
    raw_h = np.linspace(0.0, 1.0, overlap_w)
    t_h = 0.5 + 0.5 * (0.5 - 0.5 * np.cos(np.pi * raw_h))

    # Left zone: x = 0..overlap-1, partner = W-1-x
    left_idx = np.arange(overlap_w)
    left_mirror = width - 1 - left_idx

    # Right zone: x = W-overlap..W-1, partner = W-1-x
    right_idx = np.arange(width - overlap_w, width)
    right_mirror = width - 1 - right_idx

    t_left = t_h.reshape(1, -1, 1)
    t_right = t_h[::-1].reshape(1, -1, 1)

    # Compute both zones from original src simultaneously
    result[:, left_idx, :] = (
        t_left * src[:, left_idx, :] + (1.0 - t_left) * src[:, left_mirror, :]
    )
    result[:, right_idx, :] = (
        t_right * src[:, right_idx, :] + (1.0 - t_right) * src[:, right_mirror, :]
    )

    # --- Vertical mirror-blend ---
    raw_v = np.linspace(0.0, 1.0, overlap_h)
    t_v = 0.5 + 0.5 * (0.5 - 0.5 * np.cos(np.pi * raw_v))

    top_idx = np.arange(overlap_h)
    top_mirror = height - 1 - top_idx

    bottom_idx = np.arange(height - overlap_h, height)
    bottom_mirror = height - 1 - bottom_idx

    t_top = t_v.reshape(-1, 1, 1)
    t_bottom = t_v[::-1].reshape(-1, 1, 1)

    # Use horizontally-blended result as source for vertical pass
    hsrc = result.copy()
    result[top_idx, :, :] = (
        t_top * hsrc[top_idx, :, :] + (1.0 - t_top) * hsrc[top_mirror, :, :]
    )
    result[bottom_idx, :, :] = (
        t_bottom * hsrc[bottom_idx, :, :] + (1.0 - t_bottom) * hsrc[bottom_mirror, :, :]
    )

    result = np.clip(result, 0, 255).astype(np.uint8)
    result_img = Image.fromarray(result, "RGB")

    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 5. Wear Map Rendering
# ---------------------------------------------------------------------------

def render_wear_map(
    curvature_data: dict[int, float],
    texture_size: int,
    uv_data: list | None = None,
) -> bytes:
    """Render a grayscale wear/damage map from mesh curvature data.

    Convex areas (positive curvature) map to bright pixels (edges that wear),
    concave areas (negative curvature) map to dark pixels.

    Args:
        curvature_data: Mapping of vertex_index -> curvature value.
            Positive = convex (bright), negative = concave (dark).
        texture_size: Width and height of the output image.
        uv_data: Optional list of face UV data. Each face is a list of
            (vertex_index, u, v) tuples. If None, renders a simple
            visualization grid.

    Returns:
        PNG bytes of L-mode (grayscale) wear map.
    """
    if not curvature_data:
        # Empty curvature: return mid-gray
        img = Image.new("L", (texture_size, texture_size), 128)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # Normalize curvature to 0-255 range
    # Map: min_curv -> 0 (dark/concave), max_curv -> 255 (bright/convex)
    values = list(curvature_data.values())
    min_c = min(values)
    max_c = max(values)
    c_range = max_c - min_c if max_c != min_c else 1.0

    def _curv_to_brightness(c: float) -> int:
        normalized = (c - min_c) / c_range
        return max(0, min(255, round(normalized * 255)))

    img = Image.new("L", (texture_size, texture_size), 0)

    if uv_data is not None:
        # Render curvature into UV space using face polygons
        try:
            import numpy as np
            _render_wear_numpy(img, curvature_data, uv_data, texture_size, _curv_to_brightness, min_c, c_range)
        except ImportError:
            _render_wear_pil(img, curvature_data, uv_data, texture_size, _curv_to_brightness)
    else:
        # No UV data: render a simple grid visualization
        # Distribute vertices evenly across the image
        n = len(curvature_data)
        cols = max(1, int(math.sqrt(n)))
        draw = ImageDraw.Draw(img)
        for i, (vid, curv) in enumerate(sorted(curvature_data.items())):
            row = i // cols
            col = i % cols
            cell_w = texture_size // cols
            cell_h = texture_size // max(1, (n + cols - 1) // cols)
            x0 = col * cell_w
            y0 = row * cell_h
            brightness = _curv_to_brightness(curv)
            draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=brightness)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_wear_pil(
    img: Image.Image,
    curvature_data: dict[int, float],
    uv_data: list,
    texture_size: int,
    curv_to_brightness,
) -> None:
    """Render wear map to UV space using PIL polygon filling."""
    draw = ImageDraw.Draw(img)

    for face in uv_data:
        if len(face) < 3:
            continue

        # Calculate average curvature for the face
        total_curv = 0.0
        count = 0
        pixel_coords = []

        for vertex_index, u, v in face:
            px, py = _uv_to_pixel(u, v, texture_size)
            pixel_coords.append((px, py))
            if vertex_index in curvature_data:
                total_curv += curvature_data[vertex_index]
                count += 1

        if count > 0:
            avg_curv = total_curv / count
            brightness = curv_to_brightness(avg_curv)
            draw.polygon(pixel_coords, fill=brightness)


def _render_wear_numpy(
    img: Image.Image,
    curvature_data: dict[int, float],
    uv_data: list,
    texture_size: int,
    curv_to_brightness,
    min_c: float = 0.0,
    c_range: float = 1.0,
) -> None:
    """Render wear map with per-vertex interpolation using numpy.

    For each face, uses a bounding-box-sized mask (not full image) with
    distance-weighted interpolation of vertex curvature values.
    """
    import numpy as np

    arr = np.array(img, dtype=np.float64)

    for face in uv_data:
        if len(face) < 3:
            continue

        # Extract vertex data
        verts = []
        curv_vals = []
        for vertex_index, u, v in face:
            px, py = _uv_to_pixel(u, v, texture_size)
            verts.append((px, py))
            curv_vals.append(curvature_data.get(vertex_index, 0.0))

        # Get bounding box
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        x_min = max(0, min(xs))
        x_max = min(texture_size - 1, max(xs))
        y_min = max(0, min(ys))
        y_max = min(texture_size - 1, max(ys))

        if x_min >= x_max or y_min >= y_max:
            continue

        # Create a bbox-sized mask instead of full-image mask (major perf win)
        bbox_w = x_max - x_min + 1
        bbox_h = y_max - y_min + 1
        offset_verts = [(vx - x_min, vy - y_min) for vx, vy in verts]
        poly_mask = Image.new("L", (bbox_w, bbox_h), 0)
        ImageDraw.Draw(poly_mask).polygon(offset_verts, fill=255)
        mask_arr = np.array(poly_mask)

        # Vectorized distance-weighted interpolation for all masked pixels
        # Build coordinate grids for the bounding box
        yy, xx = np.mgrid[0:bbox_h, 0:bbox_w]  # local coords
        # Filter to only masked pixels
        masked = mask_arr > 0
        if not np.any(masked):
            continue

        # Absolute pixel coordinates for masked pixels
        ax = xx[masked] + x_min  # 1-D array of x coords
        ay = yy[masked] + y_min  # 1-D array of y coords

        # Vertex positions and curvature as arrays
        verts_arr = np.array(verts, dtype=np.float64)  # (N_verts, 2)
        curv_arr = np.array(curv_vals, dtype=np.float64)  # (N_verts,)

        # Distance from each masked pixel to each vertex
        # ax/ay shape: (N_pixels,), verts_arr shape: (N_verts, 2)
        dx = ax[:, np.newaxis] - verts_arr[np.newaxis, :, 0]  # (N_pixels, N_verts)
        dy = ay[:, np.newaxis] - verts_arr[np.newaxis, :, 1]
        dists = np.sqrt(dx * dx + dy * dy) + 1e-6

        weights = 1.0 / dists  # (N_pixels, N_verts)
        total_weight = weights.sum(axis=1)  # (N_pixels,)
        weighted_curv = (weights * curv_arr[np.newaxis, :]).sum(axis=1)

        interp_curv = weighted_curv / total_weight
        # Vectorized brightness: normalize and scale to 0-255
        brightness = np.clip(np.round(((interp_curv - min_c) / c_range) * 255), 0, 255)

        arr[ay, ax] = brightness

    result = np.clip(arr, 0, 255).astype(np.uint8)
    img.paste(Image.fromarray(result, "L"))


# ---------------------------------------------------------------------------
# 6. AI Inpainting via fal.ai FLUX Fill
# ---------------------------------------------------------------------------

def _image_bytes_to_data_uri(image_bytes: bytes, media_type: str = "image/png") -> str:
    """Encode image bytes as a base64 data URI for the fal.ai API."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{media_type};base64,{b64}"


def _ensure_png_bytes(image_bytes: bytes) -> bytes:
    """Ensure image bytes are PNG-encoded (re-encode if necessary)."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.format == "PNG":
        return image_bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _ensure_mask_rgb_png(mask_bytes: bytes) -> bytes:
    """Ensure mask is an RGB PNG (fal.ai expects RGB, not L-mode).

    The mask convention: white (255,255,255) = regions to inpaint,
    black (0,0,0) = regions to keep.
    """
    mask = Image.open(io.BytesIO(mask_bytes))
    if mask.mode != "RGB":
        mask = mask.convert("RGB")
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


def inpaint_texture(
    image_bytes: bytes,
    mask_bytes: bytes,
    prompt: str,
    fal_key: str | None = None,
    strength: float = 0.95,
) -> dict:
    """AI-powered texture inpainting via fal.ai FLUX Fill endpoint.

    Sends the source image and mask to fal.ai's FLUX Fill (inpainting)
    model, which generates content matching the prompt in the masked
    regions while preserving unmasked areas.

    Args:
        image_bytes: Source image as PNG/JPEG bytes.
        mask_bytes: Inpainting mask as PNG bytes (L-mode or RGB).
            White = regions to fill, black = regions to keep.
        prompt: Text description of desired texture content for
            the masked region (e.g., "rusty metal texture",
            "worn leather with scratches").
        fal_key: fal.ai API key. If None or empty, returns
            unavailable status with instructions.
        strength: Inpainting strength (0.0-1.0). Higher values give
            the model more creative freedom. Default 0.95.

    Returns:
        Dict with:
            status: "success", "unavailable", or "error"
            message: Human-readable status description
            image_bytes: (on success) PNG bytes of the inpainted result
            prompt: (on success) The prompt that was used
            width: (on success) Result image width
            height: (on success) Result image height
    """
    # Validate inputs exist
    if not image_bytes:
        return {"status": "error", "message": "No image data provided"}
    if not mask_bytes:
        return {"status": "error", "message": "No mask data provided"}
    if not prompt or not prompt.strip():
        return {"status": "error", "message": "No prompt provided"}

    if not fal_key:
        return {
            "status": "unavailable",
            "message": "fal.ai API key not configured. Set FAL_KEY environment variable to enable AI inpainting.",
        }

    if not _FAL_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "fal-client package not installed. Run: pip install fal-client",
        }

    import os

    try:
        # Ensure images are proper PNG format
        image_png = _ensure_png_bytes(image_bytes)
        mask_png = _ensure_mask_rgb_png(mask_bytes)

        # Get source image dimensions for the response
        src_img = Image.open(io.BytesIO(image_png))
        src_width, src_height = src_img.size

        # Build data URIs for the fal.ai API
        image_uri = _image_bytes_to_data_uri(image_png)
        mask_uri = _image_bytes_to_data_uri(mask_png)

        # Set the API key in the environment for fal-client
        # (fal-client reads FAL_KEY from env)
        prev_key = os.environ.get("FAL_KEY")
        os.environ["FAL_KEY"] = fal_key

        try:
            result = _fal.subscribe(
                "fal-ai/flux/dev/inpainting",
                arguments={
                    "prompt": prompt,
                    "image_url": image_uri,
                    "mask_url": mask_uri,
                    "strength": max(0.0, min(1.0, strength)),
                    "image_size": {
                        "width": src_width,
                        "height": src_height,
                    },
                    "num_images": 1,
                    "num_inference_steps": 28,
                },
            )
        finally:
            # Restore previous FAL_KEY state
            if prev_key is not None:
                os.environ["FAL_KEY"] = prev_key
            else:
                os.environ.pop("FAL_KEY", None)

        # Extract result image URL
        images = result.get("images", [])
        if not images:
            return {
                "status": "error",
                "message": "No images returned from fal.ai inpainting endpoint",
            }

        image_url = images[0].get("url", "")

        # Validate URL scheme -- only allow HTTPS from fal.ai CDN
        if not image_url.startswith("https://"):
            return {
                "status": "error",
                "message": f"Unexpected image URL scheme: {image_url[:40]}",
            }

        # Download the result image
        result_bytes = _fal.download(image_url)

        # Re-encode as PNG to ensure consistent format
        result_img = Image.open(io.BytesIO(result_bytes)).convert("RGB")
        buf = io.BytesIO()
        result_img.save(buf, format="PNG")
        result_png = buf.getvalue()

        return {
            "status": "success",
            "message": "Inpainting completed successfully",
            "image_bytes": result_png,
            "prompt": prompt,
            "width": result_img.width,
            "height": result_img.height,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"fal.ai inpainting failed: {exc}",
        }
