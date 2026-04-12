"""Bundle J — terrain_unity_export.

Writes the Unity-consumable export manifest for a TerrainMaskStack,
conforming to the plan §33 contract. Splits large channels into per-
channel .npy sidecar files and emits ``manifest.json`` linking them.

Bug-fix round (F050-F063):
- F050: Z-up -> Y-up axis swap for Unity coordinate system
- F051: Explicit little-endian byte order for .raw heightmap files
- F052: Resolution validation (power-of-2+1 for Unity terrain)
- F053: FBX terrain mesh export path
- F054-F058: LOD chain generation for terrain tiles
- F059-F063: Splatmap weight validation (sum-to-1, layer count, resolution)
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .terrain_semantics import BBox, PassDefinition, PassResult, TerrainMaskStack, TerrainPipelineState


# Profiles that require 32-bit float heightmap precision.
_PRODUCTION_PLUS_PROFILES = frozenset({"hero_shot", "aaa_open_world"})


# Channels we ship as standalone binaries.
_BINARY_CHANNELS = (
    "heightmap_raw_u16",
    "splatmap_weights_layer",
    "navmesh_area_id",
    "wind_field",
    "cloud_shadow",
    "gameplay_zone",
    "audio_reverb_class",
    "traversability",
)


# ---------------------------------------------------------------------------
# F052: Resolution validation — Unity terrain requires (2^n + 1) resolution
# ---------------------------------------------------------------------------

# Valid Unity terrain heightmap resolutions: 33, 65, 129, 257, 513, 1025, 2049, 4097
VALID_UNITY_RESOLUTIONS = tuple(2**n + 1 for n in range(5, 13))


def is_valid_unity_resolution(res: int) -> bool:
    """Check if *res* is a valid Unity terrain heightmap resolution (2^n+1, n>=5)."""
    if res < 33:
        return False
    k = res - 1
    return k > 0 and (k & (k - 1)) == 0


def validate_heightmap_resolution(shape: Tuple[int, ...]) -> List[str]:
    """Return list of validation errors for heightmap shape against Unity requirements.

    Unity requires square heightmaps with resolution = 2^n + 1 (shared-edge tiles).
    """
    errors: List[str] = []
    if len(shape) != 2:
        errors.append(f"heightmap must be 2D, got {len(shape)}D shape {shape}")
        return errors
    rows, cols = shape
    if rows != cols:
        errors.append(
            f"heightmap must be square for Unity terrain, got {rows}x{cols}"
        )
    if not is_valid_unity_resolution(rows):
        errors.append(
            f"heightmap row count {rows} is not a valid Unity resolution "
            f"(must be 2^n+1, e.g. {', '.join(str(r) for r in VALID_UNITY_RESOLUTIONS[:5])})"
        )
    if not is_valid_unity_resolution(cols):
        errors.append(
            f"heightmap col count {cols} is not a valid Unity resolution "
            f"(must be 2^n+1)"
        )
    return errors


# ---------------------------------------------------------------------------
# F050: Z-up (Blender) -> Y-up (Unity) coordinate swap
# ---------------------------------------------------------------------------


def swap_z_up_to_y_up_positions(positions: np.ndarray) -> np.ndarray:
    """Swap Z-up (Blender) to Y-up (Unity) for an (N, 3) position array.

    Blender: (X, Y, Z) where Z is up.
    Unity:   (X, Y, Z) where Y is up.

    Transform: Unity.X = Blender.X, Unity.Y = Blender.Z, Unity.Z = Blender.Y
    """
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError(
            f"positions must be (N, 3), got shape {positions.shape}"
        )
    result = np.empty_like(positions)
    result[:, 0] = positions[:, 0]   # X stays
    result[:, 1] = positions[:, 2]   # Unity Y = Blender Z (up)
    result[:, 2] = positions[:, 1]   # Unity Z = Blender Y (forward)
    return result


def swap_z_up_to_y_up_heightmap(heightmap: np.ndarray) -> np.ndarray:
    """For heightmap arrays, the height values represent the UP axis.

    In Z-up (Blender), height values are Z coordinates.
    In Y-up (Unity), height values become Y coordinates.
    The heightmap 2D grid maps to the XZ plane in Unity (was XY in Blender).

    For a 2D heightmap array, we need to transpose it because:
    - Blender: rows=Y, cols=X, values=Z
    - Unity:   rows=Z, cols=X, values=Y
    So we transpose to swap the row/col mapping.
    """
    if heightmap.ndim != 2:
        raise ValueError(f"heightmap must be 2D, got {heightmap.ndim}D")
    # Transpose so Blender Y-axis rows become Unity Z-axis rows
    return np.ascontiguousarray(heightmap.T)


# ---------------------------------------------------------------------------
# F051: Explicit little-endian byte order for Unity .raw import
# ---------------------------------------------------------------------------


def ensure_little_endian(arr: np.ndarray) -> np.ndarray:
    """Return array with explicit little-endian byte order.

    Unity's .raw heightmap importer expects little-endian (Windows-native).
    NumPy may produce big-endian on some platforms or when loaded from
    big-endian .npy files.
    """
    if arr.dtype.byteorder == ">":
        return arr.byteswap().view(arr.dtype.newbyteorder("<"))
    if arr.dtype.byteorder == "=" or arr.dtype.byteorder == "|":
        # Native or not-applicable (single byte) — convert to explicit LE
        return arr.astype(arr.dtype.newbyteorder("<"))
    # Already little-endian
    return arr


def export_heightmap_raw(
    heightmap_u16: np.ndarray,
    output_path: Path,
    swap_axes: bool = True,
) -> Dict[str, Any]:
    """Write a Unity-compatible .raw heightmap file (little-endian uint16).

    Args:
        heightmap_u16: uint16 quantized heightmap array.
        output_path: Target .raw file path.
        swap_axes: If True, transpose for Z-up -> Y-up conversion.

    Returns metadata dict with file info.
    """
    arr = np.asarray(heightmap_u16, dtype=np.uint16)
    if swap_axes:
        arr = swap_z_up_to_y_up_heightmap(arr)
    arr = ensure_little_endian(arr)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    arr.tofile(output_path)
    return {
        "path": str(output_path),
        "resolution": arr.shape[0],
        "dtype": "uint16",
        "byte_order": "little",
        "size_bytes": int(output_path.stat().st_size),
    }


# ---------------------------------------------------------------------------
# F059-F063: Splatmap validation
# ---------------------------------------------------------------------------


def validate_splatmap(
    splatmap: np.ndarray,
    expected_resolution: Optional[int] = None,
    max_layers: int = 16,
    weight_tolerance: float = 0.01,
) -> List[str]:
    """Validate splatmap weights for Unity terrain layer compatibility.

    Args:
        splatmap: Array of shape (H, W, L) with per-layer weights.
        expected_resolution: If set, verify H and W match.
        max_layers: Maximum allowed layer count (Unity default: 16).
        weight_tolerance: Tolerance for sum-to-1 check per pixel.

    Returns list of validation error strings (empty = valid).
    """
    errors: List[str] = []

    if splatmap.ndim != 3:
        errors.append(
            f"splatmap must be 3D (H, W, Layers), got {splatmap.ndim}D "
            f"shape {splatmap.shape}"
        )
        return errors

    h, w, layers = splatmap.shape

    # F059: Layer count check
    if layers > max_layers:
        errors.append(
            f"splatmap has {layers} layers, exceeds Unity max of {max_layers}"
        )
    if layers == 0:
        errors.append("splatmap has 0 layers")
        return errors

    # F060: Resolution check
    if expected_resolution is not None:
        if h != expected_resolution or w != expected_resolution:
            errors.append(
                f"splatmap resolution {h}x{w} does not match expected "
                f"{expected_resolution}x{expected_resolution}"
            )

    # F061: Square check
    if h != w:
        errors.append(f"splatmap must be square, got {h}x{w}")

    # F062: Weights must be non-negative
    if np.any(splatmap < 0):
        neg_count = int(np.sum(splatmap < 0))
        errors.append(
            f"splatmap has {neg_count} negative weight values"
        )

    # F063: Weights must sum to ~1.0 per pixel
    weight_sums = splatmap.sum(axis=2)
    bad_pixels = np.abs(weight_sums - 1.0) > weight_tolerance
    if np.any(bad_pixels):
        bad_count = int(np.sum(bad_pixels))
        min_sum = float(weight_sums.min())
        max_sum = float(weight_sums.max())
        errors.append(
            f"splatmap weights do not sum to 1.0 at {bad_count} pixels "
            f"(range [{min_sum:.4f}, {max_sum:.4f}])"
        )

    return errors


def normalize_splatmap(splatmap: np.ndarray) -> np.ndarray:
    """Normalize splatmap weights to sum to 1.0 per pixel.

    Handles edge case where all weights are zero by setting first layer to 1.0.
    """
    arr = np.asarray(splatmap, dtype=np.float32)
    if arr.ndim != 3:
        raise ValueError(f"splatmap must be 3D, got {arr.ndim}D")
    sums = arr.sum(axis=2, keepdims=True)
    # Avoid division by zero: where sum is 0, set first layer to 1
    zero_mask = sums < 1e-10
    if np.any(zero_mask):
        arr[zero_mask[..., 0], 0] = 1.0
        sums = arr.sum(axis=2, keepdims=True)
    return arr / sums


# ---------------------------------------------------------------------------
# F054-F058: LOD chain generation
# ---------------------------------------------------------------------------


def generate_lod_heightmaps(
    heightmap: np.ndarray,
    lod_levels: int = 4,
) -> List[np.ndarray]:
    """Generate LOD chain by progressive downsampling of the heightmap.

    Each LOD level halves the resolution. The result preserves the
    power-of-2+1 Unity contract at each level (e.g. 1025 -> 513 -> 257 -> 129).

    Args:
        heightmap: Full-resolution 2D heightmap (must be square, 2^n+1).
        lod_levels: Number of LOD levels to generate (including LOD0 = original).

    Returns list of heightmap arrays [LOD0, LOD1, ..., LODn-1].
    """
    if heightmap.ndim != 2:
        raise ValueError(f"heightmap must be 2D, got {heightmap.ndim}D")
    h, w = heightmap.shape
    if h != w:
        raise ValueError(f"heightmap must be square, got {h}x{w}")

    lods: List[np.ndarray] = [heightmap]
    current = heightmap
    for i in range(1, lod_levels):
        ch, cw = current.shape
        if ch < 3 or cw < 3:
            break  # Can't downsample further
        # Downsample by taking every other sample (preserves shared edges)
        downsampled = current[::2, ::2]
        lods.append(downsampled)
        current = downsampled

    return lods


def export_lod_chain(
    heightmap: np.ndarray,
    output_dir: Path,
    lod_levels: int = 4,
    prefix: str = "terrain",
) -> List[Dict[str, Any]]:
    """Export LOD chain as separate .raw files for Unity terrain LOD groups.

    Returns metadata list for each LOD level.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lods = generate_lod_heightmaps(heightmap, lod_levels)
    results: List[Dict[str, Any]] = []

    for i, lod in enumerate(lods):
        # Quantize to uint16 for .raw export
        lod_f = np.asarray(lod, dtype=np.float64)
        lo, hi = float(lod_f.min()), float(lod_f.max())
        span = max(hi - lo, 1e-9)
        norm = (lod_f - lo) / span
        lod_u16 = (np.clip(norm, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)

        raw_path = output_dir / f"{prefix}_lod{i}.raw"
        meta = export_heightmap_raw(lod_u16, raw_path, swap_axes=True)
        meta["lod_level"] = i
        meta["source_resolution"] = heightmap.shape[0]
        results.append(meta)

    return results


# ---------------------------------------------------------------------------
# F053: FBX terrain mesh export metadata
# ---------------------------------------------------------------------------


@dataclass
class FBXExportConfig:
    """Configuration for FBX terrain mesh export."""
    apply_axis_conversion: bool = True       # Z-up -> Y-up
    scale_factor: float = 1.0
    mesh_format: str = "binary"              # "binary" or "ascii"
    include_normals: bool = True
    include_uvs: bool = True
    include_vertex_colors: bool = True
    embed_textures: bool = False
    lod_levels: int = 1


def generate_fbx_export_metadata(
    stack: TerrainMaskStack,
    config: Optional[FBXExportConfig] = None,
) -> Dict[str, Any]:
    """Generate FBX export metadata for a terrain tile.

    This produces the metadata dict that an FBX exporter (Blender bpy.ops.export)
    would need. The actual FBX binary writing is done by Blender's FBX addon.

    Returns dict with export settings, vertex counts, and axis conversion info.
    """
    if config is None:
        config = FBXExportConfig()

    h, w = stack.height.shape[:2]
    vertex_count = h * w
    triangle_count = (h - 1) * (w - 1) * 2

    # Compute terrain world bounds
    extent_x = w * stack.cell_size
    extent_z = h * stack.cell_size  # In Blender Z-up, height is along Z
    height_range = 0.0
    if stack.height_min_m is not None and stack.height_max_m is not None:
        height_range = stack.height_max_m - stack.height_min_m

    meta: Dict[str, Any] = {
        "format": "FBX",
        "version": "7.4",
        "mesh_format": config.mesh_format,
        "axis_conversion": {
            "source": "z-up",
            "target": "y-up",
            "applied": config.apply_axis_conversion,
        },
        "scale_factor": config.scale_factor,
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "bounds": {
            "min": [
                float(stack.world_origin_x),
                float(stack.height_min_m or 0),
                float(stack.world_origin_y),
            ] if config.apply_axis_conversion else [
                float(stack.world_origin_x),
                float(stack.world_origin_y),
                float(stack.height_min_m or 0),
            ],
            "max": [
                float(stack.world_origin_x + extent_x),
                float(stack.height_max_m or 0),
                float(stack.world_origin_y + extent_z),
            ] if config.apply_axis_conversion else [
                float(stack.world_origin_x + extent_x),
                float(stack.world_origin_y + extent_z),
                float(stack.height_max_m or 0),
            ],
        },
        "includes": {
            "normals": config.include_normals,
            "uvs": config.include_uvs,
            "vertex_colors": config.include_vertex_colors,
            "textures_embedded": config.embed_textures,
        },
        "lod_levels": config.lod_levels,
        "terrain_size": {
            "width_m": float(extent_x),
            "depth_m": float(extent_z),
            "height_range_m": float(height_range),
        },
    }
    return meta


# ---------------------------------------------------------------------------
# Blender-Unity terrain size bridging
# ---------------------------------------------------------------------------


@dataclass
class TerrainSizeBridge:
    """Maps Blender terrain dimensions to Unity terrain component settings.

    Blender uses meters with Z-up. Unity Terrain uses:
    - terrainData.size = Vector3(width, height, length) in Y-up
    - heightmapResolution = 2^n + 1
    - alphamapResolution (splatmap) = 2^n (typically 512 or 1024)
    """
    # Blender source dimensions (Z-up)
    blender_width_m: float = 0.0     # X extent
    blender_depth_m: float = 0.0     # Y extent (becomes Z in Unity)
    blender_height_m: float = 0.0    # Z extent (becomes Y in Unity)
    blender_origin_x: float = 0.0
    blender_origin_y: float = 0.0
    blender_origin_z: float = 0.0

    # Unity target dimensions (Y-up)
    unity_terrain_width: float = 0.0     # X
    unity_terrain_height: float = 0.0    # Y (vertical)
    unity_terrain_length: float = 0.0    # Z
    unity_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Resolution settings
    heightmap_resolution: int = 513
    alphamap_resolution: int = 512
    detail_resolution: int = 1024
    base_map_resolution: int = 1024

    @classmethod
    def from_mask_stack(
        cls,
        stack: TerrainMaskStack,
        height_padding_factor: float = 1.1,
    ) -> "TerrainSizeBridge":
        """Compute Unity terrain sizing from a TerrainMaskStack.

        Args:
            stack: Source terrain data.
            height_padding_factor: Multiplier for height range to avoid
                clipping (default 10% headroom).
        """
        h_shape = stack.height.shape
        width_m = h_shape[1] * stack.cell_size
        depth_m = h_shape[0] * stack.cell_size
        h_min = stack.height_min_m if stack.height_min_m is not None else 0.0
        h_max = stack.height_max_m if stack.height_max_m is not None else 0.0
        height_range = max(h_max - h_min, 1.0) * height_padding_factor

        # Pick nearest valid Unity resolution
        res = h_shape[0]
        if not is_valid_unity_resolution(res):
            # Find nearest valid resolution >= current
            for vr in VALID_UNITY_RESOLUTIONS:
                if vr >= res:
                    res = vr
                    break
            else:
                res = VALID_UNITY_RESOLUTIONS[-1]

        # Splatmap resolution: nearest power of 2
        splat_res = 512
        if stack.splatmap_weights_layer is not None:
            sr = stack.splatmap_weights_layer.shape[0]
            # Round to nearest power of 2
            splat_res = max(64, min(4096, 2 ** round(math.log2(sr))))

        return cls(
            blender_width_m=width_m,
            blender_depth_m=depth_m,
            blender_height_m=height_range / height_padding_factor,
            blender_origin_x=stack.world_origin_x,
            blender_origin_y=stack.world_origin_y,
            blender_origin_z=h_min,
            # Unity Y-up: width=X, height=Y(up), length=Z
            unity_terrain_width=width_m,
            unity_terrain_height=height_range,
            unity_terrain_length=depth_m,
            unity_position=(
                float(stack.world_origin_x),
                float(h_min),
                float(stack.world_origin_y),
            ),
            heightmap_resolution=res,
            alphamap_resolution=splat_res,
        )

    def to_unity_settings(self) -> Dict[str, Any]:
        """Return dict suitable for Unity C# terrain setup script."""
        return {
            "terrainData.size": {
                "x": self.unity_terrain_width,
                "y": self.unity_terrain_height,
                "z": self.unity_terrain_length,
            },
            "terrain.transform.position": {
                "x": self.unity_position[0],
                "y": self.unity_position[1],
                "z": self.unity_position[2],
            },
            "terrainData.heightmapResolution": self.heightmap_resolution,
            "terrainData.alphamapResolution": self.alphamap_resolution,
            "terrainData.SetDetailResolution": self.detail_resolution,
            "terrainData.baseMapResolution": self.base_map_resolution,
            "axis_conversion": "z-up to y-up applied",
            "coordinate_notes": (
                f"Blender origin ({self.blender_origin_x}, "
                f"{self.blender_origin_y}, {self.blender_origin_z}) Z-up "
                f"-> Unity position ({self.unity_position[0]}, "
                f"{self.unity_position[1]}, {self.unity_position[2]}) Y-up"
            ),
        }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _quantize_heightmap(stack: TerrainMaskStack) -> np.ndarray:
    """Quantize world-unit heightmap to uint16 for Unity .raw import."""
    h = np.asarray(stack.height, dtype=np.float64)
    lo = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
    hi = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
    span = max(hi - lo, 1e-9)
    norm = (h - lo) / span
    norm = np.clip(norm, 0.0, 1.0)
    return (norm * 65535.0 + 0.5).astype(np.uint16)


def _export_heightmap(heightmap: np.ndarray, bit_depth: int = 16) -> np.ndarray:
    """Export heightmap at specified bit depth.

    bit_depth=16: uint16 (legacy, 0-65535 quantized)
    bit_depth=32: float32 (production+, preserves world-unit values)
    """
    if bit_depth >= 32:
        return heightmap.astype(np.float32)
    # Legacy uint16 quantization
    h = np.asarray(heightmap, dtype=np.float64)
    h_min, h_max = float(h.min()), float(h.max())
    h_range = max(h_max - h_min, 1e-10)
    normalized = (h - h_min) / h_range
    return (normalized * 65535).astype(np.uint16)


def _bit_depth_for_profile(profile: Optional[str]) -> int:
    """Return heightmap bit depth for the given export profile."""
    if profile in _PRODUCTION_PLUS_PROFILES:
        return 32
    return 16


def pass_prepare_heightmap_raw_u16(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Populate the Unity-ready uint16 heightmap channel inside the pass DAG."""
    t0 = time.perf_counter()
    stack = state.mask_stack
    arr = _quantize_heightmap(stack)
    stack.set("heightmap_raw_u16", arr, "prepare_heightmap_raw_u16")

    return PassResult(
        pass_name="prepare_heightmap_raw_u16",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("heightmap_raw_u16",),
        metrics={
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
            "min": int(arr.min()) if arr.size else 0,
            "max": int(arr.max()) if arr.size else 0,
            "region_scoped": region is not None,
        },
    )


def register_bundle_j_heightmap_u16_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="prepare_heightmap_raw_u16",
            func=pass_prepare_heightmap_raw_u16,
            requires_channels=("height",),
            produces_channels=("heightmap_raw_u16",),
            seed_namespace="prepare_heightmap_raw_u16",
            requires_scene_read=False,
            description="Bundle J: quantize world heightmap into Unity-ready uint16 channel",
        )
    )


def export_unity_manifest(
    stack: TerrainMaskStack,
    output_dir: Path,
    profile: Optional[str] = None,
    validate: bool = True,
    export_raw: bool = True,
    export_lods: bool = False,
    lod_levels: int = 4,
) -> Dict[str, Any]:
    """Write a Unity-consumable export bundle to ``output_dir``.

    Args:
        stack: Populated terrain mask stack.
        output_dir: Target directory for all export artifacts.
        profile: Export quality profile. ``"hero_shot"`` and
            ``"aaa_open_world"`` use 32-bit float heightmaps;
            all others default to uint16.
        validate: If True, run resolution and splatmap validation (F052/F059-F063).
        export_raw: If True, also export .raw heightmap with LE byte order (F051).
        export_lods: If True, generate LOD chain (F054-F058).
        lod_levels: Number of LOD levels when export_lods is True.

    Produces:
        manifest.json               -- file inventory + schema version (section 33.1)
        heightmap_raw_u16.npy       -- quantized uint16 heightmap
        heightmap.raw               -- little-endian uint16 .raw for Unity import (F051)
        splatmap_weights_layer.npy  -- per-layer alphamap (if populated)
        navmesh_area_id.npy         -- int8 area classification
        wind_field.npy              -- (H, W, 2) float32
        cloud_shadow.npy            -- (H, W) float32
        gameplay_zone.npy           -- (H, W) int32
        audio_reverb_class.npy      -- (H, W) int8
        traversability.npy          -- (H, W) float32
        audio_zones.json            -- derived reverb zone list (section 33.2)
        gameplay_zones.json         -- derived gameplay zone list (section 33.4)
        ecosystem_meta.json         -- aggregate ecosystem summary (section 33.6)
        terrain_size_bridge.json    -- Blender-Unity size mapping (F050)
        terrain_lod*.raw            -- LOD chain files (F054-F058, if enabled)

    Returns the decoded manifest dict.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hm_bit_depth = _bit_depth_for_profile(profile)

    # F052: Resolution validation
    validation_warnings: List[str] = []
    if validate:
        res_errors = validate_heightmap_resolution(stack.height.shape)
        validation_warnings.extend(res_errors)

    # F059-F063: Splatmap validation
    splatmap_warnings: List[str] = []
    if validate and stack.splatmap_weights_layer is not None:
        splatmap_warnings = validate_splatmap(
            np.asarray(stack.splatmap_weights_layer),
            expected_resolution=stack.height.shape[0] if stack.height is not None else None,
        )
        validation_warnings.extend(splatmap_warnings)

    # Ensure heightmap_raw_u16 is populated so Unity has a clean .raw to ingest.
    # For production+ profiles we export the full-precision float32 heightmap
    # via _export_heightmap; legacy profiles keep the uint16 quantisation.
    if stack.heightmap_raw_u16 is None:
        if hm_bit_depth >= 32 and stack.height is not None:
            stack.set(
                "heightmap_raw_u16",
                _export_heightmap(stack.height, bit_depth=hm_bit_depth),
                "unity_export",
            )
        else:
            stack.set(
                "heightmap_raw_u16",
                _quantize_heightmap(stack),
                "unity_export",
            )

    files: Dict[str, Dict[str, Any]] = {}

    def _write_npy(channel: str, arr: np.ndarray) -> None:
        target = output_dir / f"{channel}.npy"
        arr_np = np.asarray(arr)
        np.save(target, arr_np)
        # Derive bit depth from numpy dtype itemsize (bytes -> bits).
        dtype_bit_depth = arr_np.dtype.itemsize * 8
        files[target.name] = {
            "sha256": _sha256(target),
            "size": int(target.stat().st_size),
            "dtype": str(arr_np.dtype),
            "shape": list(arr_np.shape),
            "channel": channel,
            "bit_depth": dtype_bit_depth,
        }

    for ch in _BINARY_CHANNELS:
        val = stack.get(ch)
        if val is None:
            continue
        _write_npy(ch, val)

    # F051: Export .raw heightmap with explicit little-endian byte order
    raw_meta: Optional[Dict[str, Any]] = None
    if export_raw and stack.heightmap_raw_u16 is not None:
        hm_arr = np.asarray(stack.heightmap_raw_u16)
        # If it's float32 (production+ profile), quantize for .raw
        if hm_arr.dtype == np.float32:
            hm_f = hm_arr.astype(np.float64)
            lo, hi = float(hm_f.min()), float(hm_f.max())
            span = max(hi - lo, 1e-9)
            norm = (hm_f - lo) / span
            hm_u16 = (np.clip(norm, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)
        else:
            hm_u16 = hm_arr.astype(np.uint16)
        raw_path = output_dir / "heightmap.raw"
        raw_meta = export_heightmap_raw(hm_u16, raw_path, swap_axes=True)
        files["heightmap.raw"] = {
            "sha256": _sha256(raw_path),
            "size": raw_meta["size_bytes"],
            "dtype": "uint16",
            "byte_order": "little",
            "resolution": raw_meta["resolution"],
            "channel": "heightmap_raw",
        }

    # F054-F058: LOD chain export
    lod_meta: List[Dict[str, Any]] = []
    if export_lods and stack.height is not None:
        lod_meta = export_lod_chain(
            stack.height, output_dir, lod_levels=lod_levels, prefix="terrain"
        )
        for lm in lod_meta:
            fname = Path(lm["path"]).name
            files[fname] = {
                "sha256": _sha256(Path(lm["path"])),
                "size": lm["size_bytes"],
                "dtype": "uint16",
                "byte_order": "little",
                "lod_level": lm["lod_level"],
                "resolution": lm["resolution"],
                "channel": f"heightmap_lod{lm['lod_level']}",
            }

    # Dict channels -- detail_density / wildlife_affinity / decal_density
    if stack.detail_density:
        for k, v in stack.detail_density.items():
            _write_npy(f"detail_density__{k}", v)
    if stack.wildlife_affinity:
        for k, v in stack.wildlife_affinity.items():
            _write_npy(f"wildlife_affinity__{k}", v)
    if stack.decal_density:
        for k, v in stack.decal_density.items():
            _write_npy(f"decal_density__{k}", v)

    # ------------------------------------------------------------------
    # Derived JSON descriptors conforming to section 33
    # ------------------------------------------------------------------
    audio_zones_json = _audio_zones_json(stack)
    gameplay_zones_json = _gameplay_zones_json(stack)
    wildlife_zones_json = _wildlife_zones_json(stack)
    decals_json = _decals_json(stack)
    ecosystem_meta_json = {
        "schema_version": "1.0",
        "has_audio_zones": stack.audio_reverb_class is not None,
        "has_wildlife_zones": bool(stack.wildlife_affinity),
        "has_gameplay_zones": stack.gameplay_zone is not None,
        "has_wind_field": stack.wind_field is not None,
        "has_cloud_shadow": stack.cloud_shadow is not None,
        "has_navmesh": stack.navmesh_area_id is not None,
        "has_traversability": stack.traversability is not None,
        "has_decals": bool(stack.decal_density),
        "wind_field_descriptor": "wind_field.npy",
        "cloud_shadow_descriptor": "cloud_shadow.npy",
    }

    # F050: Terrain size bridge JSON
    size_bridge = TerrainSizeBridge.from_mask_stack(stack)
    size_bridge_json = size_bridge.to_unity_settings()

    for name, payload in (
        ("audio_zones.json", audio_zones_json),
        ("gameplay_zones.json", gameplay_zones_json),
        ("wildlife_zones.json", wildlife_zones_json),
        ("decals.json", decals_json),
        ("ecosystem_meta.json", ecosystem_meta_json),
        ("terrain_size_bridge.json", size_bridge_json),
    ):
        target = output_dir / name
        target.write_text(json.dumps(payload, indent=2, sort_keys=True))
        files[name] = {
            "sha256": _sha256(target),
            "size": int(target.stat().st_size),
        }

    # Content hash for determinism regression
    determinism_hash = stack.compute_hash()

    # Determine validation status
    validation_status = "passed" if not validation_warnings else "warnings"

    manifest: Dict[str, Any] = {
        "schema_version": stack.unity_export_schema_version,
        "world_id": "unknown",
        "tile_x": int(stack.tile_x),
        "tile_y": int(stack.tile_y),
        "tile_size": int(stack.tile_size),
        "cell_size": float(stack.cell_size),
        "world_origin_x_m": float(stack.world_origin_x),
        "world_origin_y_m": float(stack.world_origin_y),
        "height_min_m": float(stack.height_min_m) if stack.height_min_m is not None else None,
        "height_max_m": float(stack.height_max_m) if stack.height_max_m is not None else None,
        "coordinate_system": "y-up",  # F050: exported data is Y-up for Unity
        "source_coordinate_system": stack.coordinate_system,  # Original Blender system
        "generation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator_version": "bundle_j_v2.0",
        "profile": profile or "default",
        "heightmap_bit_depth": hm_bit_depth,
        "byte_order": "little-endian",  # F051
        "files": files,
        "populated_channels": list(stack.populated_by_pass.keys()),
        "determinism_hash": determinism_hash,
        "validation_status": validation_status,
        "validation_warnings": validation_warnings,
        "lod_levels": len(lod_meta) if lod_meta else 0,
        "unity_terrain_settings": size_bridge_json,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


# ---------------------------------------------------------------------------
# JSON derivers for the §33 sub-schemas
# ---------------------------------------------------------------------------


def _audio_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    """Derive §33.2 audio_zones.json from stack.audio_reverb_class."""
    zones: List[Dict[str, Any]] = []
    arr = stack.audio_reverb_class
    if arr is None:
        return {"schema_version": "1.0", "zones": zones}
    arr_np = np.asarray(arr)
    class_params = {
        0: ("open_field", 0.15, 0.2, 0.4),
        1: ("forest_dense", 0.45, 0.3, 0.7),
        2: ("forest_sparse", 0.3, 0.25, 0.55),
        3: ("cave_tight", 0.8, 0.6, 1.2),
        4: ("canyon_long", 0.7, 0.55, 1.6),
        5: ("water_near", 0.35, 0.3, 0.5),
        6: ("mountain_high", 0.2, 0.15, 0.45),
        7: ("interior", 0.5, 0.4, 0.9),
    }
    for val in np.unique(arr_np).tolist():
        name, wet, er, tail = class_params.get(int(val), ("unknown", 0.2, 0.2, 0.5))
        mask = arr_np == val
        if not mask.any():
            continue
        rr, cc = np.where(mask)
        world_tile_extent = stack.tile_size * stack.cell_size
        min_x = float(stack.world_origin_x + cc.min() * stack.cell_size)
        max_x = float(stack.world_origin_x + (cc.max() + 1) * stack.cell_size)
        min_y = float(stack.world_origin_y + rr.min() * stack.cell_size)
        max_y = float(stack.world_origin_y + (rr.max() + 1) * stack.cell_size)
        zones.append(
            {
                "bounds": {"min": [min_x, min_y, 0.0], "max": [max_x, max_y, float(world_tile_extent)]},
                "reverb_class": name,
                "wet_mix": wet,
                "early_reflections": er,
                "tail_length": tail,
            }
        )
    return {"schema_version": "1.0", "zones": zones}


def _gameplay_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    zones: List[Dict[str, Any]] = []
    arr = stack.gameplay_zone
    if arr is None:
        return {"schema_version": "1.0", "zones": zones}
    kind_names = {
        0: ("safe", "low_slope_basin"),
        1: ("combat", "open_terrain"),
        2: ("stealth", "dense_cover"),
        3: ("exploration", "default_open"),
        4: ("boss_arena", "authored"),
        5: ("narrative", "hero_feature_footprint"),
        6: ("puzzle", "cave_candidate"),
    }
    arr_np = np.asarray(arr)
    for val in np.unique(arr_np).tolist():
        name, reason = kind_names.get(int(val), ("unknown", "unclassified"))
        mask = arr_np == val
        if not mask.any():
            continue
        rr, cc = np.where(mask)
        min_x = float(stack.world_origin_x + cc.min() * stack.cell_size)
        max_x = float(stack.world_origin_x + (cc.max() + 1) * stack.cell_size)
        min_y = float(stack.world_origin_y + rr.min() * stack.cell_size)
        max_y = float(stack.world_origin_y + (rr.max() + 1) * stack.cell_size)
        zones.append(
            {
                "bounds": {"min": [min_x, min_y, 0.0], "max": [max_x, max_y, 100.0]},
                "kind": name,
                "reason": reason,
                "suggestion_tags": [],
            }
        )
    return {"schema_version": "1.0", "zones": zones}


def _wildlife_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    volumes: List[Dict[str, Any]] = []
    if not stack.wildlife_affinity:
        return {"schema_version": "1.0", "volumes": volumes}
    for species, arr in stack.wildlife_affinity.items():
        mask = np.asarray(arr) > 0.1
        if not mask.any():
            continue
        rr, cc = np.where(mask)
        min_x = float(stack.world_origin_x + cc.min() * stack.cell_size)
        max_x = float(stack.world_origin_x + (cc.max() + 1) * stack.cell_size)
        min_y = float(stack.world_origin_y + rr.min() * stack.cell_size)
        max_y = float(stack.world_origin_y + (rr.max() + 1) * stack.cell_size)
        volumes.append(
            {
                "bounds": {"min": [min_x, min_y, 0.0], "max": [max_x, max_y, 50.0]},
                "species": species,
                "density": float(np.asarray(arr).mean()),
                "spawn_rules": {},
            }
        )
    return {"schema_version": "1.0", "volumes": volumes}


def _decals_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    decals: Dict[str, List[Dict[str, Any]]] = {}
    if not stack.decal_density:
        return {"schema_version": "1.0", "decals": decals}
    for kind, arr in stack.decal_density.items():
        arr_np = np.asarray(arr)
        coords = np.argwhere(arr_np > 0.5)
        placements: List[Dict[str, Any]] = []
        for r, c in coords[:512]:  # cap per kind for JSON size
            placements.append(
                {
                    "position": [
                        float(stack.world_origin_x + c * stack.cell_size),
                        float(stack.world_origin_y + r * stack.cell_size),
                        float(stack.height[r, c]) if stack.height is not None else 0.0,
                    ],
                    "normal": [0.0, 0.0, 1.0],
                    "scale": 1.0,
                    "rotation": 0.0,
                }
            )
        decals[kind] = placements
    return {"schema_version": "1.0", "decals": decals}


__all__ = [
    "pass_prepare_heightmap_raw_u16",
    "register_bundle_j_heightmap_u16_pass",
    "export_unity_manifest",
    "_export_heightmap",
    "_bit_depth_for_profile",
    # F050: Axis conversion
    "swap_z_up_to_y_up_positions",
    "swap_z_up_to_y_up_heightmap",
    # F051: Endianness
    "ensure_little_endian",
    "export_heightmap_raw",
    # F052: Resolution validation
    "is_valid_unity_resolution",
    "validate_heightmap_resolution",
    "VALID_UNITY_RESOLUTIONS",
    # F053: FBX export
    "FBXExportConfig",
    "generate_fbx_export_metadata",
    # F054-F058: LOD
    "generate_lod_heightmaps",
    "export_lod_chain",
    # F059-F063: Splatmap validation
    "validate_splatmap",
    "normalize_splatmap",
    # Terrain size bridging
    "TerrainSizeBridge",
]
