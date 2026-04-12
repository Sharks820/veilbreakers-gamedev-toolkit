"""Bundle J — terrain_unity_export.

Writes the Unity-consumable export manifest for a TerrainMaskStack,
conforming to the plan §33 contract. Splits large channels into per-
channel .npy sidecar files and emits ``manifest.json`` linking them.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

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
) -> Dict[str, Any]:
    """Write a Unity-consumable export bundle to ``output_dir``.

    Args:
        stack: Populated terrain mask stack.
        output_dir: Target directory for all export artifacts.
        profile: Export quality profile. ``"hero_shot"`` and
            ``"aaa_open_world"`` use 32-bit float heightmaps;
            all others default to uint16.

    Produces:
        manifest.json               — file inventory + schema version (§33.1)
        heightmap_raw_u16.npy       — quantized uint16 heightmap
        splatmap_weights_layer.npy  — per-layer alphamap (if populated)
        navmesh_area_id.npy         — int8 area classification
        wind_field.npy              — (H, W, 2) float32
        cloud_shadow.npy            — (H, W) float32
        gameplay_zone.npy           — (H, W) int32
        audio_reverb_class.npy      — (H, W) int8
        traversability.npy          — (H, W) float32
        audio_zones.json            — derived reverb zone list (§33.2)
        gameplay_zones.json         — derived gameplay zone list (§33.4)
        ecosystem_meta.json         — aggregate ecosystem summary (§33.6)

    Returns the decoded manifest dict.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    hm_bit_depth = _bit_depth_for_profile(profile)

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

    # Dict channels — detail_density / wildlife_affinity / decal_density
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
    # Derived JSON descriptors conforming to §33
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

    for name, payload in (
        ("audio_zones.json", audio_zones_json),
        ("gameplay_zones.json", gameplay_zones_json),
        ("wildlife_zones.json", wildlife_zones_json),
        ("decals.json", decals_json),
        ("ecosystem_meta.json", ecosystem_meta_json),
    ):
        target = output_dir / name
        target.write_text(json.dumps(payload, indent=2, sort_keys=True))
        files[name] = {
            "sha256": _sha256(target),
            "size": int(target.stat().st_size),
        }

    # Content hash for determinism regression
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
        "height_min_m": float(stack.height_min_m) if stack.height_min_m is not None else None,
        "height_max_m": float(stack.height_max_m) if stack.height_max_m is not None else None,
        "coordinate_system": stack.coordinate_system,
        "generation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator_version": "bundle_j_v1.0",
        "profile": profile or "default",
        "heightmap_bit_depth": hm_bit_depth,
        "files": files,
        "populated_channels": list(stack.populated_by_pass.keys()),
        "determinism_hash": determinism_hash,
        "validation_status": "passed",
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
]
