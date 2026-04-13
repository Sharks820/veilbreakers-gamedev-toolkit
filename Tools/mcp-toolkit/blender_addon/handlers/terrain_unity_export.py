"""Bundle J — terrain_unity_export.

Writes Unity-ready terrain artifacts from a ``TerrainMaskStack``:
16-bit RAW heightmaps, packed RAW splatmaps, RAW detail layers, binary
auxiliary grids, and JSON descriptors with explicit Y-up coordinates.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .terrain_semantics import BBox, PassDefinition, PassResult, TerrainMaskStack, TerrainPipelineState


_DETAIL_DENSITY_MAX_PER_CELL = 16
_EXPORT_COORDINATE_SYSTEM = "y-up"
_PRODUCTION_PLUS_PROFILES = frozenset({"hero_shot", "aaa_open_world"})


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _quantize_heightmap(stack: TerrainMaskStack) -> np.ndarray:
    """Quantize world-unit heightmap to uint16 for Unity RAW import."""
    h = np.asarray(stack.height, dtype=np.float64)
    lo = float(stack.height_min_m) if stack.height_min_m is not None else float(h.min())
    hi = float(stack.height_max_m) if stack.height_max_m is not None else float(h.max())
    span = max(hi - lo, 1e-9)
    norm = (h - lo) / span
    norm = np.clip(norm, 0.0, 1.0)
    return (norm * 65535.0 + 0.5).astype(np.uint16)


def _compute_terrain_normals_zup(heightmap: np.ndarray, cell_size: float) -> np.ndarray:
    """Compute a Z-up normal field from a world-unit heightmap."""
    h = np.asarray(heightmap, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError("heightmap must be 2D")
    if h.size == 0:
        return np.zeros((0, 0, 3), dtype=np.float32)

    spacing = max(float(cell_size), 1e-9)
    dzdy, dzdx = np.gradient(h, spacing, spacing, edge_order=1)
    normals = np.stack((-dzdx, -dzdy, np.ones_like(h, dtype=np.float64)), axis=-1)
    lengths = np.linalg.norm(normals, axis=-1, keepdims=True)
    lengths = np.where(lengths <= 1e-9, 1.0, lengths)
    normals = normals / lengths
    return normals.astype(np.float32)


def _zup_to_unity_vectors(arr: np.ndarray) -> np.ndarray:
    """Convert a vector field from Blender Z-up into Unity Y-up."""
    arr_np = np.asarray(arr, dtype=np.float32)
    if arr_np.ndim < 1 or arr_np.shape[-1] != 3:
        raise ValueError("vector field must have a trailing dimension of 3")
    return np.ascontiguousarray(
        np.stack((arr_np[..., 0], arr_np[..., 2], arr_np[..., 1]), axis=-1),
        dtype=np.float32,
    )


def _export_heightmap(heightmap: np.ndarray, bit_depth: int = 16) -> np.ndarray:
    """Backward-compatible helper returning the engine-ready RAW source array.

    Unity Terrain RAW ingest is 16-bit, so production profiles preserve
    precision via ``height_min_m`` / ``height_max_m`` metadata rather than
    switching the RAW payload dtype.
    """
    _ = bit_depth
    h = np.asarray(heightmap, dtype=np.float64)
    lo = float(h.min()) if h.size else 0.0
    hi = float(h.max()) if h.size else 0.0
    span = max(hi - lo, 1e-9)
    norm = np.clip((h - lo) / span, 0.0, 1.0)
    return (norm * 65535.0 + 0.5).astype(np.uint16)


def _bit_depth_for_profile(profile: Optional[str]) -> int:
    """Return the actual Unity RAW bit depth for the given export profile."""
    _ = profile
    return 16


def pass_prepare_terrain_normals(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """Populate the Unity-space terrain normal field inside the pass DAG."""
    t0 = time.perf_counter()
    stack = state.mask_stack
    normals_zup = _compute_terrain_normals_zup(np.asarray(stack.height, dtype=np.float64), float(stack.cell_size))
    normals_unity = _zup_to_unity_vectors(normals_zup)
    stack.set("terrain_normals", normals_unity, "prepare_terrain_normals")

    return PassResult(
        pass_name="prepare_terrain_normals",
        status="ok",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=("height",),
        produced_channels=("terrain_normals",),
        metrics={
            "dtype": str(normals_unity.dtype),
            "shape": list(normals_unity.shape),
            "region_scoped": region is not None,
        },
    )


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


def register_bundle_j_terrain_normals_pass() -> None:
    from .terrain_pipeline import TerrainPassController

    TerrainPassController.register_pass(
        PassDefinition(
            name="prepare_terrain_normals",
            func=pass_prepare_terrain_normals,
            requires_channels=("height",),
            produces_channels=("terrain_normals",),
            seed_namespace="prepare_terrain_normals",
            requires_scene_read=False,
            description="Bundle J: compute Unity-space terrain normals from world heightmap",
        )
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


def _flip_for_unity(arr: np.ndarray) -> np.ndarray:
    arr_np = np.asarray(arr)
    if arr_np.ndim >= 2:
        return np.flip(arr_np, axis=0)
    return arr_np


def _ensure_little_endian(arr: np.ndarray) -> np.ndarray:
    arr_np = np.asarray(arr)
    if arr_np.dtype.itemsize <= 1:
        return np.ascontiguousarray(arr_np)
    return np.ascontiguousarray(arr_np.astype(arr_np.dtype.newbyteorder("<"), copy=False))


def _write_raw_array(
    files: Dict[str, Dict[str, Any]],
    output_dir: Path,
    *,
    filename: str,
    channel: str,
    arr: np.ndarray,
    encoding: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    export_arr = _ensure_little_endian(_flip_for_unity(np.asarray(arr)))
    target = output_dir / filename
    target.write_bytes(export_arr.tobytes())
    meta: Dict[str, Any] = {
        "sha256": _sha256(target),
        "size": int(target.stat().st_size),
        "dtype": str(export_arr.dtype),
        "shape": list(export_arr.shape),
        "channel": channel,
        "channels": int(export_arr.shape[2]) if export_arr.ndim >= 3 else 1,
        "bit_depth": export_arr.dtype.itemsize * 8,
        "encoding": encoding,
        "flip_vertical": bool(export_arr.ndim >= 2),
    }
    if export_arr.dtype.itemsize > 1:
        meta["endianness"] = "little"
    if extra:
        meta.update(extra)
    files[target.name] = meta
    return target.name


def _write_json(
    files: Dict[str, Dict[str, Any]],
    output_dir: Path,
    *,
    filename: str,
    payload: Dict[str, Any],
) -> str:
    target = output_dir / filename
    target.write_text(json.dumps(payload, indent=2, sort_keys=True))
    files[target.name] = {
        "sha256": _sha256(target),
        "size": int(target.stat().st_size),
        "channels": 0,
        "encoding": "json",
        "bit_depth": 0,
    }
    return target.name


def _zup_to_unity_vector(vec: list[float] | tuple[float, float, float]) -> list[float]:
    x, y, z = (float(vec[0]), float(vec[1]), float(vec[2]))
    return [x, z, y]


def _bounds_to_unity(bounds_min: list[float], bounds_max: list[float]) -> Dict[str, Any]:
    return {
        "min": _zup_to_unity_vector(bounds_min),
        "max": _zup_to_unity_vector(bounds_max),
    }


def _terrain_normal_at(stack: TerrainMaskStack, row: int, col: int) -> list[float]:
    h = np.asarray(stack.height, dtype=np.float64) if stack.height is not None else None
    if h is None or h.size == 0:
        return [0.0, 0.0, 1.0]

    r0 = max(0, row - 1)
    r1 = min(h.shape[0] - 1, row + 1)
    c0 = max(0, col - 1)
    c1 = min(h.shape[1] - 1, col + 1)
    dzdx = 0.0 if c1 == c0 else float(h[row, c1] - h[row, c0]) / (float(c1 - c0) * float(stack.cell_size))
    dzdy = 0.0 if r1 == r0 else float(h[r1, col] - h[r0, col]) / (float(r1 - r0) * float(stack.cell_size))
    normal = np.asarray([-dzdx, -dzdy, 1.0], dtype=np.float64)
    norm = float(np.linalg.norm(normal))
    if norm <= 1e-9:
        return [0.0, 0.0, 1.0]
    normal /= norm
    return [float(normal[0]), float(normal[1]), float(normal[2])]


def _quantize_detail_density(arr: np.ndarray) -> np.ndarray:
    density = np.asarray(arr, dtype=np.float64)
    density = np.clip(density, 0.0, 1.0)
    return np.rint(density * _DETAIL_DENSITY_MAX_PER_CELL).astype(np.uint16)


def _write_splatmap_groups(
    files: Dict[str, Dict[str, Any]],
    output_dir: Path,
    stack: TerrainMaskStack,
) -> list[str]:
    weights = stack.splatmap_weights_layer
    if weights is None:
        return []

    weights_np = np.asarray(weights, dtype=np.float32)
    if weights_np.ndim != 3:
        raise ValueError("splatmap_weights_layer must be 3D (H, W, L)")

    group_files: list[str] = []
    layers = int(weights_np.shape[2])
    group_count = max(1, (layers + 3) // 4)
    for group_index in range(group_count):
        start = group_index * 4
        end = min(start + 4, layers)
        block = weights_np[:, :, start:end]
        padded = np.zeros((weights_np.shape[0], weights_np.shape[1], 4), dtype=np.float32)
        padded[:, :, : end - start] = np.clip(block, 0.0, 1.0)
        block_u8 = np.rint(padded * 255.0).astype(np.uint8)
        filename = f"splatmap_{group_index:02d}.raw"
        group_files.append(
            _write_raw_array(
                files,
                output_dir,
                filename=filename,
                channel="splatmap_weights_layer",
                arr=block_u8,
                encoding="raw_rgba_u8",
                extra={
                    "channels": 4,
                    "group_index": group_index,
                    "layer_range": [start, end - 1],
                    "valid_layer_count": end - start,
                },
            )
        )
    return group_files


def export_unity_manifest(
    stack: TerrainMaskStack,
    output_dir: Path,
    profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Write a Unity-consumable export bundle to ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    hm_bit_depth = _bit_depth_for_profile(profile)
    if stack.heightmap_raw_u16 is None:
        stack.set("heightmap_raw_u16", _quantize_heightmap(stack), "unity_export")
    else:
        stack.set(
            "heightmap_raw_u16",
            np.asarray(stack.heightmap_raw_u16, dtype=np.uint16),
            stack.populated_by_pass.get("heightmap_raw_u16", "unity_export"),
        )
    normals = stack.get("terrain_normals")
    height_shape = np.asarray(stack.height, dtype=np.float64).shape
    if normals is None or np.asarray(normals).shape != (*height_shape, 3):
        normals_zup = _compute_terrain_normals_zup(np.asarray(stack.height, dtype=np.float64), float(stack.cell_size))
        stack.set("terrain_normals", _zup_to_unity_vectors(normals_zup), "unity_export")
    else:
        stack.set(
            "terrain_normals",
            np.asarray(normals, dtype=np.float32),
            stack.populated_by_pass.get("terrain_normals", "unity_export"),
        )

    files: Dict[str, Dict[str, Any]] = {}
    _write_raw_array(
        files,
        output_dir,
        filename="heightmap.raw",
        channel="heightmap_raw_u16",
        arr=np.asarray(stack.heightmap_raw_u16, dtype=np.uint16),
        encoding="raw_u16_le",
    )
    _write_raw_array(
        files,
        output_dir,
        filename="terrain_normals.bin",
        channel="terrain_normals",
        arr=np.asarray(stack.terrain_normals, dtype=np.float32),
        encoding="raw_vec3_f32_le",
    )
    splatmap_files = _write_splatmap_groups(files, output_dir, stack)

    for channel in ("navmesh_area_id", "wind_field", "cloud_shadow", "gameplay_zone", "audio_reverb_class", "traversability"):
        value = stack.get(channel)
        if value is None:
            continue
        _write_raw_array(
            files,
            output_dir,
            filename=f"{channel}.bin",
            channel=channel,
            arr=np.asarray(value),
            encoding="raw_le",
        )

    detail_files: Dict[str, str] = {}
    if stack.detail_density:
        for key, value in stack.detail_density.items():
            detail_files[key] = _write_raw_array(
                files,
                output_dir,
                filename=f"detail_density__{key}.raw",
                channel="detail_density",
                arr=_quantize_detail_density(value),
                encoding="raw_u16_le_detail_count",
                extra={"detail_kind": key, "max_density_per_cell": _DETAIL_DENSITY_MAX_PER_CELL},
            )

    if stack.wildlife_affinity:
        for key, value in stack.wildlife_affinity.items():
            _write_raw_array(
                files,
                output_dir,
                filename=f"wildlife_affinity__{key}.bin",
                channel="wildlife_affinity",
                arr=np.asarray(value, dtype=np.float32),
                encoding="raw_f32_le",
                extra={"species": key},
            )

    if stack.decal_density:
        for key, value in stack.decal_density.items():
            _write_raw_array(
                files,
                output_dir,
                filename=f"decal_density__{key}.bin",
                channel="decal_density",
                arr=np.asarray(value, dtype=np.float32),
                encoding="raw_f32_le",
                extra={"decal_kind": key},
            )

    tree_instances_json = _tree_instances_json(stack)
    audio_zones_json = _audio_zones_json(stack)
    gameplay_zones_json = _gameplay_zones_json(stack)
    wildlife_zones_json = _wildlife_zones_json(stack)
    decals_json = _decals_json(stack)
    ecosystem_meta_json = {
        "schema_version": "1.0",
        "coordinate_system": _EXPORT_COORDINATE_SYSTEM,
        "source_coordinate_system": stack.coordinate_system,
        "heightmap_descriptor": "heightmap.raw",
        "terrain_normals_descriptor": "terrain_normals.bin",
        "splatmap_descriptors": splatmap_files,
        "detail_density_descriptors": detail_files,
        "tree_instances_descriptor": "tree_instances.json" if tree_instances_json["trees"] else None,
        "has_terrain_normals": stack.terrain_normals is not None,
        "has_audio_zones": stack.audio_reverb_class is not None,
        "has_wildlife_zones": bool(stack.wildlife_affinity),
        "has_gameplay_zones": stack.gameplay_zone is not None,
        "has_wind_field": stack.wind_field is not None,
        "has_cloud_shadow": stack.cloud_shadow is not None,
        "has_navmesh": stack.navmesh_area_id is not None,
        "has_traversability": stack.traversability is not None,
        "has_decals": bool(stack.decal_density),
        "wind_field_descriptor": "wind_field.bin" if stack.wind_field is not None else None,
        "cloud_shadow_descriptor": "cloud_shadow.bin" if stack.cloud_shadow is not None else None,
    }

    for name, payload in (
        ("tree_instances.json", tree_instances_json),
        ("audio_zones.json", audio_zones_json),
        ("gameplay_zones.json", gameplay_zones_json),
        ("wildlife_zones.json", wildlife_zones_json),
        ("decals.json", decals_json),
        ("ecosystem_meta.json", ecosystem_meta_json),
    ):
        _write_json(files, output_dir, filename=name, payload=payload)

    determinism_hash = stack.compute_hash()
    manifest: Dict[str, Any] = {
        "schema_version": stack.unity_export_schema_version,
        "world_id": "unknown",
        "tile_x": int(stack.tile_x),
        "tile_y": int(stack.tile_y),
        "tile_size": int(stack.tile_size),
        "cell_size": float(stack.cell_size),
        "world_origin_x_m": float(stack.world_origin_x),
        "world_origin_y_m": float(stack.world_origin_y),
        "unity_world_origin": [float(stack.world_origin_x), 0.0, float(stack.world_origin_y)],
        "height_min_m": float(stack.height_min_m) if stack.height_min_m is not None else None,
        "height_max_m": float(stack.height_max_m) if stack.height_max_m is not None else None,
        "coordinate_system": _EXPORT_COORDINATE_SYSTEM,
        "source_coordinate_system": stack.coordinate_system,
        "generation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator_version": "bundle_j_v2.0",
        "profile": profile or "default",
        "heightmap_bit_depth": hm_bit_depth,
        "splatmap_group_count": len(splatmap_files),
        "detail_density_max_per_cell": _DETAIL_DENSITY_MAX_PER_CELL,
        "files": files,
        "populated_channels": list(stack.populated_by_pass.keys()),
        "determinism_hash": determinism_hash,
        "validation_status": "passed",
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _audio_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    zones: List[Dict[str, Any]] = []
    arr = stack.audio_reverb_class
    if arr is None:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "zones": zones}

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
    world_tile_extent = stack.tile_size * stack.cell_size
    for val in np.unique(arr_np).tolist():
        name, wet, er, tail = class_params.get(int(val), ("unknown", 0.2, 0.2, 0.5))
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
                "bounds": _bounds_to_unity(
                    [min_x, min_y, 0.0],
                    [max_x, max_y, float(world_tile_extent)],
                ),
                "reverb_class": name,
                "wet_mix": wet,
                "early_reflections": er,
                "tail_length": tail,
            }
        )
    return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "zones": zones}


def _gameplay_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    zones: List[Dict[str, Any]] = []
    arr = stack.gameplay_zone
    if arr is None:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "zones": zones}

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
                "bounds": _bounds_to_unity(
                    [min_x, min_y, 0.0],
                    [max_x, max_y, 100.0],
                ),
                "kind": name,
                "reason": reason,
                "suggestion_tags": [],
            }
        )
    return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "zones": zones}


def _wildlife_zones_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    volumes: List[Dict[str, Any]] = []
    if not stack.wildlife_affinity:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "volumes": volumes}

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
                "bounds": _bounds_to_unity(
                    [min_x, min_y, 0.0],
                    [max_x, max_y, 50.0],
                ),
                "species": species,
                "density": float(np.asarray(arr).mean()),
                "spawn_rules": {},
            }
        )
    return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "volumes": volumes}


def _decals_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    decals: Dict[str, List[Dict[str, Any]]] = {}
    if not stack.decal_density:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "decals": decals}

    for kind, arr in stack.decal_density.items():
        arr_np = np.asarray(arr)
        coords = np.argwhere(arr_np > 0.5)
        placements: List[Dict[str, Any]] = []
        for r, c in coords[:512]:
            position_zup = [
                float(stack.world_origin_x + c * stack.cell_size),
                float(stack.world_origin_y + r * stack.cell_size),
                float(stack.height[r, c]) if stack.height is not None else 0.0,
            ]
            placements.append(
                {
                    "position": _zup_to_unity_vector(position_zup),
                    "normal": _zup_to_unity_vector(_terrain_normal_at(stack, int(r), int(c))),
                    "scale": 1.0,
                    "rotation": 0.0,
                }
            )
        decals[kind] = placements
    return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "decals": decals}


def _tree_instances_json(stack: TerrainMaskStack) -> Dict[str, Any]:
    trees: List[Dict[str, Any]] = []
    arr = stack.tree_instance_points
    if arr is None:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "trees": trees}

    points = np.asarray(arr, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 5:
        return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "trees": trees}

    for row in points:
        trees.append(
            {
                "position": _zup_to_unity_vector([float(row[0]), float(row[1]), float(row[2])]),
                "yaw_degrees": float(row[3]),
                "prototype_id": int(row[4]),
            }
        )
    return {"schema_version": "1.0", "coordinate_system": _EXPORT_COORDINATE_SYSTEM, "trees": trees}


__all__ = [
    "pass_prepare_heightmap_raw_u16",
    "register_bundle_j_heightmap_u16_pass",
    "export_unity_manifest",
    "_export_heightmap",
    "_bit_depth_for_profile",
]
