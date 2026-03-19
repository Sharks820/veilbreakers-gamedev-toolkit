"""Standalone texture validation utilities for game asset pipelines.

Provides power-of-two checks, texture file validation, and compression
format recommendations without requiring Blender.

Functions:
    check_power_of_two    - True if an integer is a power of 2
    validate_texture_file - Validate width/height, aspect ratio, format
    recommend_compression - Recommend BC1/BC4/BC5/BC7 based on channel type
"""

from __future__ import annotations

import os
from typing import Any

from PIL import Image


# ---------------------------------------------------------------------------
# Power-of-two check
# ---------------------------------------------------------------------------


def check_power_of_two(n: int) -> bool:
    """Return True if *n* is a power of two.

    Args:
        n: Integer to check.

    Returns:
        True if n is a positive power of 2 (1, 2, 4, 8, ...).
    """
    return isinstance(n, int) and n > 0 and (n & (n - 1)) == 0


# ---------------------------------------------------------------------------
# Texture file validation
# ---------------------------------------------------------------------------

_SUPPORTED_FORMATS = frozenset({
    "PNG", "JPEG", "TARGA", "BMP", "TIFF", "EXR", "HDR",
    # Pillow format names
    "TGA",
})

# Map Pillow format strings to normalized names
_FORMAT_NORMALIZE: dict[str, str] = {
    "JPEG": "JPEG",
    "PNG": "PNG",
    "TGA": "TARGA",
    "TARGA": "TARGA",
    "BMP": "BMP",
    "TIFF": "TIFF",
    "EXR": "EXR",
    "HDR": "HDR",
}


def validate_texture_file(filepath: str) -> dict:
    """Validate a texture file for game engine compatibility.

    Checks:
    - File exists and is loadable as an image
    - Width and height are powers of two
    - Dimensions are within 256-8192 range
    - Aspect ratio (width:height or height:width)
    - Image format

    Args:
        filepath: Path to the texture file.

    Returns:
        Dict with keys: filepath, width, height, format, is_power_of_two,
        aspect_ratio, issues (list of strings), valid (bool).
    """
    result: dict[str, Any] = {
        "filepath": filepath,
        "width": 0,
        "height": 0,
        "format": "unknown",
        "is_power_of_two": False,
        "aspect_ratio": 0.0,
        "issues": [],
        "valid": False,
    }

    if not os.path.isfile(filepath):
        result["issues"].append(f"File not found: {filepath}")
        return result

    try:
        img = Image.open(filepath)
        width, height = img.size
        fmt = img.format or "unknown"
        img.close()
    except Exception as exc:
        result["issues"].append(f"Cannot open image: {exc}")
        return result

    result["width"] = width
    result["height"] = height
    result["format"] = _FORMAT_NORMALIZE.get(fmt, fmt)
    result["aspect_ratio"] = round(width / height, 4) if height > 0 else 0.0

    issues: list[str] = []

    # Power-of-two check
    pot = check_power_of_two(width) and check_power_of_two(height)
    result["is_power_of_two"] = pot
    if not pot:
        issues.append(
            f"Non-power-of-two resolution ({width}x{height}). "
            "Game engines require power-of-two textures for mipmapping."
        )

    # Size range check
    if width < 256 or height < 256:
        issues.append(
            f"Low resolution ({width}x{height}). "
            "Minimum recommended size is 256x256."
        )

    if width > 8192 or height > 8192:
        issues.append(
            f"Oversized resolution ({width}x{height}). "
            "Maximum recommended size is 8192x8192."
        )

    result["issues"] = issues
    result["valid"] = len(issues) == 0

    return result


# ---------------------------------------------------------------------------
# Compression recommendation
# ---------------------------------------------------------------------------

# Mapping from channel_type to recommended BC format
_COMPRESSION_MAP: dict[str, dict[str, Any]] = {
    "albedo": {
        "format": "BC7",
        "description": "High-quality RGBA compression for base color maps",
        "bpp": 8,
        "quality": "high",
    },
    "base_color": {
        "format": "BC7",
        "description": "High-quality RGBA compression for base color maps",
        "bpp": 8,
        "quality": "high",
    },
    "normal": {
        "format": "BC5",
        "description": "Two-channel compression for tangent-space normal maps (RG only)",
        "bpp": 8,
        "quality": "high",
    },
    "roughness": {
        "format": "BC4",
        "description": "Single-channel compression for roughness/smoothness maps",
        "bpp": 4,
        "quality": "medium",
    },
    "metallic": {
        "format": "BC4",
        "description": "Single-channel compression for metallic maps",
        "bpp": 4,
        "quality": "medium",
    },
    "ao": {
        "format": "BC4",
        "description": "Single-channel compression for ambient occlusion maps",
        "bpp": 4,
        "quality": "medium",
    },
    "height": {
        "format": "BC4",
        "description": "Single-channel compression for height/displacement maps",
        "bpp": 4,
        "quality": "medium",
    },
    "emissive": {
        "format": "BC1",
        "description": "RGB compression for emissive maps (no alpha needed)",
        "bpp": 4,
        "quality": "low",
    },
    "mask": {
        "format": "BC4",
        "description": "Single-channel compression for mask textures",
        "bpp": 4,
        "quality": "medium",
    },
    "opacity": {
        "format": "BC4",
        "description": "Single-channel compression for opacity/alpha maps",
        "bpp": 4,
        "quality": "medium",
    },
}


def recommend_compression(filepath: str, channel_type: str) -> dict:
    """Recommend a BCn compression format for a texture file.

    Args:
        filepath: Path to the texture file (used for size estimation).
        channel_type: Semantic channel type. One of: albedo, base_color,
            normal, roughness, metallic, ao, height, emissive, mask, opacity.

    Returns:
        Dict with keys: channel_type, recommended_format, description,
        bpp, quality, estimated_compressed_size_kb (if file is readable).
    """
    channel_lower = channel_type.lower()
    rec = _COMPRESSION_MAP.get(channel_lower)

    if rec is None:
        # Default to BC7 for unknown channel types
        rec = {
            "format": "BC7",
            "description": "High-quality RGBA compression (default for unknown channel type)",
            "bpp": 8,
            "quality": "high",
        }

    result: dict[str, Any] = {
        "channel_type": channel_type,
        "recommended_format": rec["format"],
        "description": rec["description"],
        "bpp": rec["bpp"],
        "quality": rec["quality"],
    }

    # Estimate compressed size if we can read the file
    try:
        img = Image.open(filepath)
        width, height = img.size
        img.close()
        # Compressed size = (width * height * bpp) / 8 bytes
        compressed_bytes = (width * height * rec["bpp"]) / 8
        result["estimated_compressed_size_kb"] = round(compressed_bytes / 1024, 1)
        result["width"] = width
        result["height"] = height
    except Exception:
        pass

    return result
