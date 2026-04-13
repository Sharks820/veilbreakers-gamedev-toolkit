"""Splatmap exporter: rasterize per-vertex RGBA weights to a PNG image.

Channel convention matches terrain_materials.py:
    R=grass, G=rock, B=dirt, A=special

Provides pure-logic rasterization and a bpy-dependent handler for
reading vertex color data from Blender terrain meshes.

Exports:
    rasterize_splatmap     -- Pure-logic rasterization to raw bytes.
    export_splatmap_to_png -- Pure-logic PNG export.
    handle_export_splatmap -- bpy-dependent handler.
"""

from __future__ import annotations

import os
import struct
import zlib


# ---------------------------------------------------------------------------
# Pure-logic functions (testable without bpy)
# ---------------------------------------------------------------------------


def rasterize_splatmap(
    vertex_colors: list[tuple[float, float, float, float]],
    grid_rows: int,
    grid_cols: int,
    target_resolution: int = 512,
) -> bytes:
    """Rasterize per-vertex RGBA splatmap weights to raw RGBA bytes.

    Parameters
    ----------
    vertex_colors : list of (R, G, B, A) float tuples
        Per-vertex splatmap weights in [0, 1] range.
    grid_rows : int
        Number of rows in the terrain grid.
    grid_cols : int
        Number of columns in the terrain grid.
    target_resolution : int
        Output image dimension (square).

    Returns
    -------
    bytes
        Raw RGBA pixel data (uint8, 0-255), row-major, top-to-bottom.

    Raises
    ------
    ValueError
        If vertex_colors length doesn't match grid_rows * grid_cols.
    """
    expected = grid_rows * grid_cols
    if len(vertex_colors) != expected:
        raise ValueError(
            f"Vertex count {len(vertex_colors)} doesn't match "
            f"grid {grid_rows}x{grid_cols} = {expected}"
        )

    try:
        import numpy as np

        # Reshape to grid
        data = np.array(vertex_colors, dtype=np.float64).reshape(grid_rows, grid_cols, 4)

        # Resize to target resolution using bilinear-like interpolation
        if grid_rows != target_resolution or grid_cols != target_resolution:
            from numpy import interp as _interp  # noqa: F401

            resized = np.zeros((target_resolution, target_resolution, 4), dtype=np.float64)
            for ch in range(4):
                for row in range(target_resolution):
                    src_row = row * (grid_rows - 1) / max(target_resolution - 1, 1)
                    r0 = int(src_row)
                    r1 = min(r0 + 1, grid_rows - 1)
                    fr = src_row - r0
                    for col in range(target_resolution):
                        src_col = col * (grid_cols - 1) / max(target_resolution - 1, 1)
                        c0 = int(src_col)
                        c1 = min(c0 + 1, grid_cols - 1)
                        fc = src_col - c0
                        val = (
                            data[r0, c0, ch] * (1 - fr) * (1 - fc)
                            + data[r0, c1, ch] * (1 - fr) * fc
                            + data[r1, c0, ch] * fr * (1 - fc)
                            + data[r1, c1, ch] * fr * fc
                        )
                        resized[row, col, ch] = val
            data = resized

        # Normalize each pixel so channels sum to 1.0
        sums = data.sum(axis=2, keepdims=True)
        sums[sums == 0] = 1.0  # avoid division by zero
        data = data / sums

        # Convert to uint8
        pixels = np.clip(data * 255.0, 0, 255).astype(np.uint8)
        return pixels.tobytes()

    except ImportError:
        # Fallback: nearest-neighbor sampling without numpy
        result = bytearray()
        for row in range(target_resolution):
            src_row = min(int(row * grid_rows / target_resolution), grid_rows - 1)
            for col in range(target_resolution):
                src_col = min(int(col * grid_cols / target_resolution), grid_cols - 1)
                r, g, b, a = vertex_colors[src_row * grid_cols + src_col]
                total = r + g + b + a
                if total > 0:
                    r, g, b, a = r / total, g / total, b / total, a / total
                else:
                    r, g, b, a = 0.25, 0.25, 0.25, 0.25
                result.extend([
                    max(0, min(255, int(r * 255))),
                    max(0, min(255, int(g * 255))),
                    max(0, min(255, int(b * 255))),
                    max(0, min(255, int(a * 255))),
                ])
        return bytes(result)


def export_splatmap_to_png(
    vertex_colors: list[tuple[float, float, float, float]],
    grid_rows: int,
    grid_cols: int,
    output_path: str,
    target_resolution: int = 512,
) -> str:
    """Rasterize splatmap and write to PNG file.

    Parameters
    ----------
    vertex_colors : list of (R, G, B, A) float tuples
    grid_rows, grid_cols : int
        Terrain grid dimensions.
    output_path : str
        Path to write the PNG file.
    target_resolution : int
        Output image dimension.

    Returns
    -------
    str
        The output_path where the PNG was written.
    """
    raw_bytes = rasterize_splatmap(vertex_colors, grid_rows, grid_cols, target_resolution)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        from PIL import Image

        img = Image.frombytes("RGBA", (target_resolution, target_resolution), raw_bytes)
        img.save(output_path, "PNG")
    except ImportError:
        # Minimal PNG encoder using struct + zlib
        _write_minimal_png(output_path, raw_bytes, target_resolution, target_resolution)

    return output_path


def _write_minimal_png(
    path: str,
    rgba_bytes: bytes,
    width: int,
    height: int,
) -> None:
    """Write a minimal RGBA PNG file without PIL."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    # PNG signature
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT chunk (raw RGBA with filter byte 0 per row)
    raw_rows = bytearray()
    stride = width * 4
    for row in range(height):
        raw_rows.append(0)  # filter byte: None
        start = row * stride
        raw_rows.extend(rgba_bytes[start : start + stride])

    compressed = zlib.compress(bytes(raw_rows), 9)
    idat = _chunk(b"IDAT", compressed)

    # IEND chunk
    iend = _chunk(b"IEND", b"")

    with open(path, "wb") as fh:
        fh.write(signature + ihdr + idat + iend)


# ---------------------------------------------------------------------------
# bpy-dependent handler
# ---------------------------------------------------------------------------


def handle_export_splatmap(params: dict) -> dict:
    """Handler: export splatmap from terrain vertex colors to PNG.

    Reads the ``VB_TerrainSplatmap`` vertex color layer from the
    specified terrain object.

    Params
    ------
    terrain_name : str
        Name of the terrain object in Blender.
    output_path : str
        Path to write the PNG file.
    target_resolution : int, optional
        Output image dimension (default 512).

    Returns
    -------
    dict with output_path, resolution, terrain_name, channel_convention.
    """
    import bpy

    terrain_name = params.get("terrain_name", "Terrain")
    output_path = params.get("output_path", "splatmap.png")
    target_resolution = int(params.get("target_resolution", 512))

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        return {"error": f"Terrain object '{terrain_name}' not found"}
    if obj.type != "MESH":
        return {"error": f"Object '{terrain_name}' is not a MESH"}

    mesh = obj.data
    vc_layer = mesh.vertex_colors.get("VB_TerrainSplatmap") or mesh.color_attributes.get("VB_TerrainSplatmap")
    if vc_layer is None:
        return {"error": f"No 'VB_TerrainSplatmap' vertex color layer on '{terrain_name}'"}

    # Detect grid dimensions
    try:
        from blender_addon.handlers.environment import _detect_grid_dims
        import bmesh

        bm = bmesh.new()
        bm.from_mesh(mesh)
        grid_rows, grid_cols = _detect_grid_dims(bm)
        bm.free()
    except Exception:
        vert_count = len(mesh.vertices)
        import math
        side = int(math.sqrt(vert_count))
        grid_rows = grid_cols = max(side, 2)

    # Read vertex colors (per-loop -> per-vertex average)
    vert_colors: dict[int, list[tuple[float, float, float, float]]] = {}
    for loop_idx, loop in enumerate(mesh.loops):
        vi = loop.vertex_index
        color = vc_layer.data[loop_idx].color
        vert_colors.setdefault(vi, []).append(tuple(color[:4]))

    # Average per-vertex
    avg_colors: list[tuple[float, float, float, float]] = []
    for vi in range(len(mesh.vertices)):
        colors = vert_colors.get(vi, [(0.25, 0.25, 0.25, 0.25)])
        n = len(colors)
        avg = tuple(sum(c[ch] for c in colors) / n for ch in range(4))
        avg_colors.append(avg)

    export_splatmap_to_png(avg_colors, grid_rows, grid_cols, output_path, target_resolution)

    return {
        "output_path": output_path,
        "resolution": target_resolution,
        "terrain_name": terrain_name,
        "channel_convention": "RGBA: grass/rock/dirt/special",
    }
