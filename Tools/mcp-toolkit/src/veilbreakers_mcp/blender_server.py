import atexit
import json
import logging
import math
import os
import re
import threading
from pathlib import Path
from collections import deque
from typing import Literal, Any

import numpy as np

from mcp.server.fastmcp import FastMCP, Image
from veilbreakers_mcp.shared.blender_client import BlenderConnection, BlenderCommandError
from veilbreakers_mcp.shared.config import Settings
from veilbreakers_mcp.shared.security import validate_code
from veilbreakers_mcp.shared.image_utils import compose_contact_sheet, resize_screenshot
from veilbreakers_mcp.shared.texture_ops import (
    apply_hsv_adjustment,
    blend_seams,
    generate_uv_mask,
    make_tileable,
    render_wear_map,
    inpaint_texture,
)
from veilbreakers_mcp.shared.texture_validation import validate_texture_file
from veilbreakers_mcp.shared.esrgan_runner import upscale_texture
from veilbreakers_mcp.shared.tripo_client import TripoGenerator
from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner
from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
from veilbreakers_mcp.shared.fal_client import (
    generate_concept_art,
    extract_color_palette,
    compose_style_board,
    test_silhouette_readability,
)
from veilbreakers_mcp.shared.delight import delight_albedo
from veilbreakers_mcp.shared.palette_validator import validate_palette as _validate_palette
from veilbreakers_mcp.shared.tripo_post_processor import post_process_tripo_model
from veilbreakers_mcp.shared.visual_validation import aaa_verify_map
from veilbreakers_mcp.shared.screenshot_diff import compare_screenshots, capture_regression_baseline

logger = logging.getLogger("veilbreakers_mcp")

settings = Settings()
mcp = FastMCP(
    "veilbreakers-blender",
    instructions="""\
VeilBreakers Blender MCP — 16 compound tools (162 actions) for AAA dark fantasy 3D game asset creation.

## Tool Architecture
Each tool uses a compound pattern: one tool name, `action` param selects the operation.
Tools connect via TCP to Blender (localhost:9876). The Blender addon must be running.
Most mutations return viewport screenshots for visual verification.

## Core Pipeline (MUST follow this order)
1. **Create/Import** — `blender_object` create, `asset_pipeline` generate_3d/import_model, or `blender_quality` generators
2. **Repair** — `blender_mesh` action=repair (remove doubles, fix normals, fill holes)
3. **UV Unwrap** — `blender_uv` action=unwrap (xatlas) or unwrap_blender (smart_project)
4. **Texture** — `blender_texture` action=create_pbr, then bake/validate
5. **Rig** — `blender_rig` action=apply_template (humanoid/quadruped), then auto_weight
6. **Animate** — `blender_animation` action=generate_walk/attack/idle/reaction
7. **Export** — `blender_export` format=fbx or gltf. Run `blender_mesh` action=game_check FIRST.

## Key Tools
- **blender_execute**: Direct Blender Python (bpy/bmesh/mathutils). Use for anything not covered by other tools.
- **blender_quality**: 32 AAA procedural generators — weapons (sword/axe/mace/bow/shield/staff), armor (pauldron/chestplate/gauntlet), creatures, riggable props (door/chain/flag/chest), clothing, vegetation, materials.
- **asset_pipeline**: Full orchestration — compose_map (terrain→water→roads→locations→vegetation), compose_interior (rooms→doors→props), generate_3d (Tripo AI), import_and_process (import + full pipeline).
- **blender_worldbuilding**: Procedural dungeons, caves, towns, castles, ruins, boss arenas, multi-floor dungeons.
- **blender_viewport**: ALWAYS use action=contact_sheet after creating/modifying objects for visual QA.

## Quality Rules
- Run `blender_mesh` action=game_check before ANY export (checks poly count, UVs, normals)
- Use `blender_viewport` action=contact_sheet for multi-angle visual review after generation
- Use seeds for reproducible terrain/worldbuilding generation
- Batch when possible: `asset_pipeline` action=batch_process, `blender_animation` action=batch_export
""",
)

_connection: BlenderConnection | None = None
_connection_lock = threading.Lock()


def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is not None:
        return _connection
    with _connection_lock:
        # Double-checked locking: re-test inside the lock.
        if _connection is None:
            logger.info("Connecting to Blender at %s:%s", settings.blender_host, settings.blender_port)
            _connection = BlenderConnection(
                host=settings.blender_host,
                port=settings.blender_port,
                timeout=settings.blender_timeout,
            )
            # No eager connect() -- the server uses connection-per-command,
            # so _sync_send() calls reconnect() before each command.
            # An eager connect() would open a socket that the server handles
            # as a real client connection, wasting a server thread.
    return _connection


def _cleanup_connection():
    global _connection
    with _connection_lock:
        if _connection is not None:
            _connection.disconnect()
            _connection = None


atexit.register(_cleanup_connection)


async def _with_screenshot(
    blender: BlenderConnection,
    result: dict,
    capture: bool = True,
    object_name: str | None = None,
) -> list:
    """Return structured result + viewport screenshot for mutation tools.

    When *object_name* is provided the camera is auto-framed on that object
    before the screenshot is taken (CAM-001 through CAM-007).
    """
    parts: list = [json.dumps(result, indent=2, default=str)]
    if capture:
        try:
            if object_name:
                # Auto-frame camera on the object before capturing
                try:
                    await blender.send_command("auto_frame_camera", {"object_name": object_name})
                except Exception as frame_err:
                    logger.debug("Auto-frame failed for %s: %s", object_name, frame_err)
            screenshot_bytes = await blender.capture_viewport_bytes()
            # Reduce screenshot payload to prevent 20MB API limit hits
            screenshot_bytes = resize_screenshot(screenshot_bytes, max_size=512)
            parts.append(Image(data=screenshot_bytes, format="png"))
        except (OSError, IOError, BlenderCommandError, ConnectionError) as e:
            parts.append(f"[Screenshot capture failed: {e}]")
    return parts


_AAA_CAMERA_ANGLES: list[tuple[int, int, str]] = [
    (0, 0, "front"),
    (180, 0, "back"),
    (90, 0, "left"),
    (270, 0, "right"),
    (0, 90, "top"),
    (45, 30, "ne_45"),
    (135, 30, "nw_45"),
    (225, 30, "sw_45"),
    (315, 30, "se_45"),
    (0, 18, "ground_level"),
]


def _normalize_validation_profiles(raw_profiles: Any) -> list[str]:
    """Normalize optional validation-profile input into stable lowercase names."""
    if raw_profiles is None:
        return []
    if isinstance(raw_profiles, str):
        candidates = [raw_profiles]
    elif isinstance(raw_profiles, (list, tuple, set)):
        candidates = list(raw_profiles)
    else:
        return []

    profiles: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        profile = str(candidate or "").strip().lower()
        if not profile or profile in seen:
            continue
        seen.add(profile)
        profiles.append(profile)
    return profiles


def _iter_nested_strings(value: Any):
    """Yield string leaves from nested dict/list payloads for keyword inference."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            yield stripped.lower()
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_nested_strings(nested)
        return
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _iter_nested_strings(nested)


def _payload_contains_keywords(payload: Any, keywords: tuple[str, ...]) -> bool:
    lowered = tuple(keyword.lower() for keyword in keywords)
    return any(
        any(keyword in text for keyword in lowered)
        for text in _iter_nested_strings(payload)
    )


def _derive_terrain_validation_profiles(
    *,
    map_spec: dict | None = None,
    terrain_result: dict | None = None,
    object_names: list[str] | None = None,
    location_results: list[dict] | None = None,
) -> list[str]:
    """Infer the mandatory terrain-validation profiles for the current map."""
    terrain_result = terrain_result or {}
    map_spec = map_spec or {}
    terrain_cfg = map_spec.get("terrain", {}) if isinstance(map_spec, dict) else {}
    water_cfg = map_spec.get("water", {}) if isinstance(map_spec, dict) else {}
    locations = list(map_spec.get("locations", [])) if isinstance(map_spec, dict) else []
    combined_location_payloads = locations + list(location_results or [])
    terrain_preset = str(terrain_cfg.get("preset", "")).strip().lower()

    profiles = ["terrain_readability"]

    cliff_overlays = max(
        int(terrain_result.get("cliff_overlays", 0) or 0),
        int(terrain_result.get("hero_cliff_overlays", 0) or 0),
    )
    has_cliff_signal = (
        cliff_overlays > 0
        or terrain_preset in {"mountains", "canyon", "volcanic", "coastal", "cliffs"}
        or _payload_contains_keywords(
            [terrain_cfg, combined_location_payloads, object_names or []],
            ("cliff", "cliffside", "ridge", "terrace", "escarpment"),
        )
    )
    if has_cliff_signal:
        profiles.append("terrain_cliff")

    has_waterfall_signal = (
        bool(water_cfg.get("waterfalls"))
        or any(
            isinstance(river, dict)
            and (
                river.get("waterfall")
                or river.get("has_waterfall")
                or str(river.get("type", "")).strip().lower() in {"waterfall", "cascade"}
            )
            for river in water_cfg.get("rivers", [])
        )
        or _payload_contains_keywords(
            [water_cfg, combined_location_payloads, object_names or []],
            ("waterfall", "cascade", "falls"),
        )
    )
    if has_waterfall_signal:
        profiles.append("terrain_waterfall")

    has_river_signal = (
        bool(water_cfg.get("rivers"))
        or _payload_contains_keywords(
            [water_cfg, combined_location_payloads, object_names or []],
            ("river", "stream", "creek", "fjord", "watercourse"),
        )
    )
    if has_river_signal:
        profiles.append("terrain_river")

    has_road_signal = (
        bool(map_spec.get("roads"))
        or _payload_contains_keywords(
            [map_spec.get("roads", []), combined_location_payloads, object_names or []],
            ("road", "path", "trail", "bridge", "causeway"),
        )
    )
    if has_road_signal:
        profiles.append("terrain_road")

    has_cave_signal = (
        any(
            isinstance(location, dict)
            and str(location.get("type", "")).strip().lower() == "cave"
            for location in combined_location_payloads
        )
        or _payload_contains_keywords(
            [combined_location_payloads, object_names or []],
            ("cave", "cavern", "grotto", "sinkhole", "lair"),
        )
    )
    if has_cave_signal:
        profiles.append("terrain_cave")

    return profiles


_TERRAIN_ONLY_SCOPE_TOKENS = frozenset({
    "terrain",
    "terrain_only",
    "terrain-only",
    "wilderness",
    "wilderness_only",
    "wilderness-only",
})
_TERRAIN_ONLY_ALLOWED_LOCATION_TYPES = frozenset({"cave"})


def _map_spec_requests_terrain_only(map_spec: dict | None) -> bool:
    """Return True when compose_map should stay on terrain-only content."""
    if not isinstance(map_spec, dict):
        return False
    if bool(map_spec.get("terrain_only")) or bool(map_spec.get("wilderness_only")):
        return True

    for key in ("content_scope", "generation_scope", "mode"):
        token = str(map_spec.get(key, "")).strip().lower()
        if token in _TERRAIN_ONLY_SCOPE_TOKENS:
            return True

    for tag in map_spec.get("tags", []) or []:
        if str(tag).strip().lower() in _TERRAIN_ONLY_SCOPE_TOKENS:
            return True
    return False


def _filter_map_spec_for_terrain_only(map_spec: dict | None) -> dict:
    """Preserve only terrain-shaping content when terrain-only mode is requested."""
    if not isinstance(map_spec, dict):
        return {}

    filtered_spec = dict(map_spec)
    filtered_locations: list[dict] = []
    for location in map_spec.get("locations", []) or []:
        if not isinstance(location, dict):
            continue
        loc_type = str(location.get("type", "")).strip().lower()
        if loc_type not in _TERRAIN_ONLY_ALLOWED_LOCATION_TYPES:
            continue
        kept_location = dict(location)
        kept_location.pop("interiors", None)
        filtered_locations.append(kept_location)

    filtered_spec["terrain_only"] = True
    filtered_spec["wilderness_only"] = True
    filtered_spec["locations"] = filtered_locations
    filtered_spec["props"] = False
    return filtered_spec


def _blend_path_points_to_terminal_water_level(
    path_points: list[list[float]] | list[tuple[float, float, float]],
    terminal_water_level: float | None,
) -> list[list[float]]:
    """Blend the downstream tail of a river surface to a target terminal level."""
    points = [
        [float(pt[0]), float(pt[1]), float(pt[2])]
        for pt in (path_points or [])
        if isinstance(pt, (list, tuple)) and len(pt) >= 3
    ]
    if terminal_water_level is None or len(points) < 2:
        return points

    target_level = float(terminal_water_level)
    start_idx = max(0, len(points) - max(6, int(len(points) * 0.42)))
    tail_start_level = float(points[start_idx][2])
    for idx in range(start_idx, len(points)):
        blend_t = (idx - start_idx) / max(len(points) - 1 - start_idx, 1)
        blended_level = tail_start_level * (1.0 - blend_t) + target_level * blend_t
        points[idx][2] = min(float(points[idx][2]), blended_level)
    points[-1][2] = min(float(points[-1][2]), target_level)
    return points


def _chaikin_smooth_path_points(
    path_points: list[list[float]] | list[tuple[float, float, float]],
    *,
    passes: int = 1,
    max_points: int | None = 28,
) -> list[list[float]]:
    """Smooth a polyline without changing its endpoints.

    This keeps river surfaces from reading as grid-zigzags after terrain carve
    pathfinding, while still letting the caller preserve the overall path shape.
    """
    points = [
        [float(pt[0]), float(pt[1]), float(pt[2])]
        for pt in (path_points or [])
        if isinstance(pt, (list, tuple)) and len(pt) >= 3
    ]
    if len(points) < 3:
        return points
    passes = max(0, int(passes))
    for _ in range(passes):
        refined = [points[0]]
        for start, end in zip(points, points[1:]):
            q = [
                start[0] * 0.75 + end[0] * 0.25,
                start[1] * 0.75 + end[1] * 0.25,
                start[2] * 0.75 + end[2] * 0.25,
            ]
            r = [
                start[0] * 0.25 + end[0] * 0.75,
                start[1] * 0.25 + end[1] * 0.75,
                start[2] * 0.25 + end[2] * 0.75,
            ]
            refined.extend((q, r))
        refined.append(points[-1])
        points = refined
    if max_points is not None and max_points >= 2 and len(points) > max_points:
        sample_count = max(2, int(max_points))
        keep_indices = {
            int(round(i * (len(points) - 1) / max(sample_count - 1, 1)))
            for i in range(sample_count)
        }
        points = [points[idx] for idx in sorted(keep_indices)]
    return points


def _map_point_to_world_xy(
    position: list[float] | tuple[float, ...],
    *,
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
) -> tuple[float, float]:
    """Convert a map-spec point into Blender world XY."""
    x = float(position[0])
    y = float(position[1])
    origin_x, origin_y = terrain_location or (0.0, 0.0)
    x -= origin_x
    y -= origin_y
    x, y = _normalize_map_point((x, y), terrain_size)
    return x + origin_x, y + origin_y


def _clamp_world_xy(
    x: float,
    y: float,
    *,
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
    margin: float = 0.0,
) -> tuple[float, float]:
    """Clamp a world point inside the terrain bounds with a safety margin."""
    origin_x, origin_y = terrain_location or (0.0, 0.0)
    half = terrain_size * 0.5
    clamped_x = max(origin_x - half + margin, min(origin_x + half - margin, float(x)))
    clamped_y = max(origin_y - half + margin, min(origin_y + half - margin, float(y)))
    return clamped_x, clamped_y


def _offset_polyline_world(
    points: list[tuple[float, float]],
    *,
    offset_distance: float,
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
    margin: float = 0.0,
) -> list[list[float]]:
    """Offset an XY polyline to one side while preserving endpoints order."""
    if len(points) < 2:
        return [[float(pt[0]), float(pt[1]), 0.0] for pt in points]

    offset_points: list[list[float]] = []
    for index, (px, py) in enumerate(points):
        if index == 0:
            ax, ay = points[0]
            bx, by = points[1]
        elif index == len(points) - 1:
            ax, ay = points[index - 1]
            bx, by = points[index]
        else:
            ax, ay = points[index - 1]
            bx, by = points[index + 1]
        dx = bx - ax
        dy = by - ay
        length = max(math.hypot(dx, dy), 1e-6)
        perp_x = -dy / length
        perp_y = dx / length
        ox = px + perp_x * offset_distance
        oy = py + perp_y * offset_distance
        ox, oy = _clamp_world_xy(
            ox,
            oy,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
            margin=margin,
        )
        offset_points.append([ox, oy, 0.0])
    return offset_points


async def _sample_terrain_relief_direction(
    blender: BlenderConnection,
    terrain_name: str,
    *,
    x: float,
    y: float,
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
    sample_radius: float,
    direction_count: int = 8,
) -> dict[str, float]:
    """Estimate the steepest downhill direction around a terrain point."""
    center_z = await _sample_terrain_height(blender, terrain_name, x, y)
    best_drop = -1e9
    best_dir = (0.0, 1.0)
    for direction_index in range(max(direction_count, 4)):
        angle = (math.tau * direction_index) / max(direction_count, 1)
        dx = math.cos(angle) * sample_radius
        dy = math.sin(angle) * sample_radius
        sample_x, sample_y = _clamp_world_xy(
            x + dx,
            y + dy,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
            margin=max(sample_radius * 0.4, 4.0),
        )
        sample_z = await _sample_terrain_height(blender, terrain_name, sample_x, sample_y)
        drop = center_z - sample_z
        if drop > best_drop:
            best_drop = drop
            best_dir = (sample_x - x, sample_y - y)

    dir_len = max(math.hypot(best_dir[0], best_dir[1]), 1e-6)
    outward_x = best_dir[0] / dir_len
    outward_y = best_dir[1] / dir_len

    if best_drop < 0.35:
        origin_x, origin_y = terrain_location or (0.0, 0.0)
        fallback_x = x - origin_x
        fallback_y = y - origin_y
        fallback_len = math.hypot(fallback_x, fallback_y)
        if fallback_len > 1e-6:
            outward_x = fallback_x / fallback_len
            outward_y = fallback_y / fallback_len

    return {
        "x": float(x),
        "y": float(y),
        "z": float(center_z),
        "outward_x": float(outward_x),
        "outward_y": float(outward_y),
        "slope_drop": float(best_drop),
    }


async def _retarget_cave_anchor_to_relief(
    blender: BlenderConnection,
    terrain_name: str,
    *,
    anchor_x: float,
    anchor_y: float,
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
    search_radius: float,
    sample_radius: float,
) -> dict[str, float]:
    """Move a cave anchor onto a nearby stronger cliff/slope signal."""
    best: dict[str, float] | None = None
    ring = search_radius * 0.68
    outer_ring = search_radius * 0.96
    candidate_offsets = [
        (0.0, 0.0),
        (ring, 0.0),
        (-ring, 0.0),
        (0.0, ring),
        (0.0, -ring),
        (ring * 0.72, ring * 0.72),
        (ring * 0.72, -ring * 0.72),
        (-ring * 0.72, ring * 0.72),
        (-ring * 0.72, -ring * 0.72),
        (outer_ring, 0.0),
        (-outer_ring, 0.0),
        (0.0, outer_ring),
        (0.0, -outer_ring),
        (outer_ring * 0.70, outer_ring * 0.70),
        (outer_ring * 0.70, -outer_ring * 0.70),
        (-outer_ring * 0.70, outer_ring * 0.70),
        (-outer_ring * 0.70, -outer_ring * 0.70),
    ]
    for offset_x, offset_y in candidate_offsets:
        candidate_x, candidate_y = _clamp_world_xy(
            anchor_x + offset_x,
            anchor_y + offset_y,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
            margin=max(search_radius * 0.45, 8.0),
        )
        relief = await _sample_terrain_relief_direction(
            blender,
            terrain_name,
            x=candidate_x,
            y=candidate_y,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
            sample_radius=sample_radius,
        )
        radial = math.hypot(
            candidate_x - (terrain_location or (0.0, 0.0))[0],
            candidate_y - (terrain_location or (0.0, 0.0))[1],
        )
        anchor_distance = math.hypot(candidate_x - anchor_x, candidate_y - anchor_y)
        slope_drop = float(relief["slope_drop"])
        ideal_drop = max(sample_radius * 0.42, 3.6)
        slope_score = min(slope_drop, ideal_drop) * 2.2 - max(slope_drop - ideal_drop, 0.0) * 1.3
        outward_x = float(relief["outward_x"])
        outward_y = float(relief["outward_y"])
        side_x = -outward_y
        side_y = outward_x
        outside_probe = await _sample_terrain_height(
            blender,
            terrain_name,
            candidate_x + outward_x * sample_radius * 0.82,
            candidate_y + outward_y * sample_radius * 0.82,
        )
        inside_probe = await _sample_terrain_height(
            blender,
            terrain_name,
            candidate_x - outward_x * sample_radius * 0.56,
            candidate_y - outward_y * sample_radius * 0.56,
        )
        left_probe = await _sample_terrain_height(
            blender,
            terrain_name,
            candidate_x + side_x * sample_radius * 0.44,
            candidate_y + side_y * sample_radius * 0.44,
        )
        right_probe = await _sample_terrain_height(
            blender,
            terrain_name,
            candidate_x - side_x * sample_radius * 0.44,
            candidate_y - side_y * sample_radius * 0.44,
        )
        center_z = float(relief["z"])
        face_prominence = max(center_z - float(outside_probe), 0.0)
        inside_mass = max(float(inside_probe) - center_z, 0.0)
        sidewall_frame = max(((float(left_probe) + float(right_probe)) * 0.5) - center_z, 0.0)
        score = (
            slope_score
            + face_prominence * 1.6
            + inside_mass * 0.45
            + sidewall_frame * 0.70
            - anchor_distance * 0.16
            + radial * 0.03
            + max(float(relief["z"]), 0.0) * 0.02
        )
        relief["score"] = score
        if best is None or score > float(best["score"]):
            best = relief

    if best is None:
        return {
            "x": float(anchor_x),
            "y": float(anchor_y),
            "z": 0.0,
            "outward_x": 0.0,
            "outward_y": 1.0,
            "slope_drop": 0.0,
            "score": 0.0,
        }
    return best


async def _apply_hero_mountain_shaping(
    blender: BlenderConnection,
    *,
    terrain_name: str,
    map_spec: dict[str, Any],
    terrain_size: float,
    terrain_location: tuple[float, float],
    terrain_preset: str,
    height_scale: float,
    cave_anchor: tuple[float, float] | None = None,
) -> list[str]:
    """Add a deliberate ridge-and-valley read for hero terrain compositions."""
    def _simplify_backbone(
        points: list[tuple[float, float]],
        *,
        max_points: int = 5,
    ) -> list[tuple[float, float]]:
        if len(points) <= max_points:
            return list(points)
        chosen: list[tuple[float, float]] = []
        used: set[int] = set()
        for slot in range(max_points):
            raw_index = round(slot * (len(points) - 1) / max(max_points - 1, 1))
            index = max(0, min(int(raw_index), len(points) - 1))
            if index in used:
                continue
            used.add(index)
            chosen.append(points[index])
        if chosen[0] != points[0]:
            chosen.insert(0, points[0])
        if chosen[-1] != points[-1]:
            chosen.append(points[-1])
        return chosen

    preset = str(terrain_preset or "").strip().lower()
    terrain_cfg = map_spec.get("terrain", {}) if isinstance(map_spec, dict) else {}
    water_cfg = map_spec.get("water", {}) if isinstance(map_spec, dict) else {}
    river_specs = list(water_cfg.get("rivers", [])) if isinstance(water_cfg, dict) else []
    has_cave = cave_anchor is not None or any(
        isinstance(location, dict)
        and str(location.get("type", "")).strip().lower() == "cave"
        for location in (map_spec.get("locations", []) if isinstance(map_spec, dict) else [])
    )
    has_hero_water = bool(river_specs) or "water_level" in water_cfg or bool(water_cfg.get("waterfalls"))
    mountain_like_presets = {"mountains", "cliffs", "canyon", "chaotic", "volcanic"}
    hero_supported_presets = mountain_like_presets | {"hills", "coastal", "swamp"}
    if preset not in hero_supported_presets or not (preset in mountain_like_presets or has_cave or has_hero_water):
        return []

    valley_points: list[tuple[float, float]] = []
    if river_specs:
        river = river_specs[0]
        raw_chain = [
            river.get("source", (-terrain_size * 0.35, terrain_size * 0.30)),
            *(river.get("waypoints", []) or []),
            river.get("destination", (terrain_size * 0.22, -terrain_size * 0.18)),
        ]
        for raw_point in raw_chain:
            if isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2:
                valley_points.append(
                    _map_point_to_world_xy(
                        raw_point,
                        terrain_size=terrain_size,
                        terrain_location=terrain_location,
                    )
                )
    if len(valley_points) < 2:
        valley_points = [
            (terrain_location[0] - terrain_size * 0.32, terrain_location[1] + terrain_size * 0.20),
            (terrain_location[0] + terrain_size * 0.18, terrain_location[1] - terrain_size * 0.18),
        ]
    basin_center_raw = water_cfg.get("basin_center") if isinstance(water_cfg, dict) else None
    if isinstance(basin_center_raw, (list, tuple)) and len(basin_center_raw) >= 2:
        basin_point = _map_point_to_world_xy(
            basin_center_raw,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
        )
        if not valley_points or math.hypot(
            basin_point[0] - valley_points[-1][0],
            basin_point[1] - valley_points[-1][1],
        ) > max(terrain_size * 0.05, 8.0):
            valley_points.append(basin_point)
    valley_points = _simplify_backbone(valley_points, max_points=5 if river_specs else 4)

    mid_x = sum(point[0] for point in valley_points) / len(valley_points)
    mid_y = sum(point[1] for point in valley_points) / len(valley_points)
    start_x, start_y = valley_points[0]
    end_x, end_y = valley_points[-1]
    dir_x = end_x - start_x
    dir_y = end_y - start_y
    dir_len = max(math.hypot(dir_x, dir_y), 1e-6)
    perp_x = -dir_y / dir_len
    perp_y = dir_x / dir_len
    ridge_sign = 1.0
    if cave_anchor is not None:
        cave_side = (cave_anchor[0] - mid_x) * perp_x + (cave_anchor[1] - mid_y) * perp_y
        ridge_sign = 1.0 if cave_side >= 0.0 else -1.0

    ridge_offset = max(terrain_size * 0.16, 22.0)
    secondary_offset = ridge_offset * -0.72
    margin = max(terrain_size * 0.06, 10.0)

    primary_ridge = _offset_polyline_world(
        valley_points,
        offset_distance=ridge_offset * ridge_sign,
        terrain_size=terrain_size,
        terrain_location=terrain_location,
        margin=margin,
    )
    secondary_ridge = _offset_polyline_world(
        valley_points[1:] if len(valley_points) > 2 else valley_points,
        offset_distance=secondary_offset * ridge_sign,
        terrain_size=terrain_size,
        terrain_location=terrain_location,
        margin=margin,
    )
    valley_curve: list[list[float]] = []
    for x, y in valley_points:
        try:
            sampled_z = await _sample_terrain_height(blender, terrain_name, x, y)
        except Exception:
            sampled_z = 0.0
        valley_curve.append([float(x), float(y), float(sampled_z)])
    if len(valley_curve) >= 3:
        # Smooth sampled valley heights before using them as spline anchors.
        # Raw terrain samples can oscillate enough to create terrace-like steps
        # once carve/flatten passes stack on top of each other.
        for _ in range(2):
            smoothed_curve: list[list[float]] = []
            for idx, point in enumerate(valley_curve):
                prev_z = valley_curve[max(idx - 1, 0)][2]
                curr_z = point[2]
                next_z = valley_curve[min(idx + 1, len(valley_curve) - 1)][2]
                smooth_z = prev_z * 0.22 + curr_z * 0.56 + next_z * 0.22
                smoothed_curve.append([point[0], point[1], float(smooth_z)])
            valley_curve = smoothed_curve

    shape_steps: list[str] = []
    river_valley_scale = 1.28 if river_specs else 1.0
    primary_depth = max(height_scale * (0.24 if preset in mountain_like_presets else 0.18), 8.5)
    primary_width = max(terrain_size * (0.17 if preset in mountain_like_presets else 0.19), 22.0)
    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": primary_ridge,
        "mode": "raise",
        "depth": primary_depth,
        "width": primary_width,
        "falloff": 0.88,
        "samples_per_segment": 14,
    })
    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": primary_ridge,
        "mode": "smooth",
        "depth": 0.0,
        "width": max(primary_width * 1.22, 26.0),
        "falloff": 0.96,
        "samples_per_segment": 14,
    })
    shape_steps.append("hero_primary_ridge")

    peak_anchor_idx = min(
        max(int(len(primary_ridge) * 0.62), 0),
        max(len(primary_ridge) - 1, 0),
    )
    if primary_ridge:
        peak_center = primary_ridge[peak_anchor_idx]
        peak_spine = [
            [
                float(peak_center[0]) - perp_x * terrain_size * 0.055,
                float(peak_center[1]) - perp_y * terrain_size * 0.055,
                float(peak_center[2]) if len(peak_center) >= 3 else 0.0,
            ],
            [
                float(peak_center[0]) + perp_x * ridge_sign * terrain_size * 0.022,
                float(peak_center[1]) + perp_y * ridge_sign * terrain_size * 0.022,
                (float(peak_center[2]) if len(peak_center) >= 3 else 0.0) + max(height_scale * 0.10, 3.0),
            ],
            [
                float(peak_center[0]) + perp_x * terrain_size * 0.055,
                float(peak_center[1]) + perp_y * terrain_size * 0.055,
                float(peak_center[2]) if len(peak_center) >= 3 else 0.0,
            ],
        ]
        await blender.send_command("terrain_spline_deform", {
            "object_name": terrain_name,
            "spline_points": peak_spine,
            "mode": "raise",
            "depth": max(height_scale * (0.11 if preset in mountain_like_presets else 0.08), 4.2),
            "width": max(terrain_size * 0.16, 22.0),
            "falloff": 0.90,
            "samples_per_segment": 12,
        })
        await blender.send_command("terrain_spline_deform", {
            "object_name": terrain_name,
            "spline_points": peak_spine,
            "mode": "smooth",
            "depth": 0.0,
            "width": max(terrain_size * 0.22, 30.0),
            "falloff": 0.98,
            "samples_per_segment": 12,
        })
        shape_steps.append("hero_peak_massif")

    if len(secondary_ridge) >= 2 and not river_specs:
        await blender.send_command("terrain_spline_deform", {
            "object_name": terrain_name,
            "spline_points": secondary_ridge,
            "mode": "raise",
            "depth": max(height_scale * (0.09 if preset in mountain_like_presets else 0.07), 3.8),
            "width": max(terrain_size * 0.16, 20.0),
            "falloff": 0.94,
            "samples_per_segment": 14,
        })
        await blender.send_command("terrain_spline_deform", {
            "object_name": terrain_name,
            "spline_points": secondary_ridge,
            "mode": "smooth",
            "depth": 0.0,
            "width": max(terrain_size * 0.20, 26.0),
            "falloff": 0.98,
            "samples_per_segment": 14,
        })
        shape_steps.append("hero_secondary_ridge")

    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": valley_curve,
        "mode": "carve",
        "depth": max(height_scale * 0.095, 3.4),
        "width": max(terrain_size * 0.108 * river_valley_scale, 17.0),
        "falloff": 0.92,
        "samples_per_segment": 18,
    })
    shape_steps.append("hero_valley_cut")

    floodplain_curve = [
        [
            float(point[0]),
            float(point[1]),
            float(point[2]) - max(height_scale * 0.028, 0.9),
        ]
        for point in valley_curve
    ]
    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": floodplain_curve,
        "mode": "carve",
        "width": max(terrain_size * 0.14 * river_valley_scale, 24.0 if river_specs else 20.0),
        "depth": max(height_scale * 0.018, 0.75),
        "falloff": 0.96,
        "samples_per_segment": 18,
    })
    shape_steps.append("hero_valley_floor")
    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": floodplain_curve,
        "mode": "smooth",
        "depth": 0.0,
        "width": max(terrain_size * 0.28 * river_valley_scale, 40.0 if river_specs else 30.0),
        "falloff": 0.995,
        "samples_per_segment": 18,
    })
    shape_steps.append("hero_valley_smooth")
    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": valley_curve,
        "mode": "smooth",
        "depth": 0.0,
        "width": max(terrain_size * 0.18 * river_valley_scale, 26.0 if river_specs else 22.0),
        "falloff": 0.985,
        "samples_per_segment": 18,
    })
    shape_steps.append("hero_valley_feather")

    return shape_steps


def _terrain_review_material_key(terrain_preset: str) -> str:
    preset = str(terrain_preset or "").strip().lower()
    if preset in {"cliffs", "mountains", "volcanic", "canyon", "chaotic"}:
        return "cliff_rock"
    if preset in {"coastal"}:
        return "wet_rock"
    if preset in {"swamp"}:
        return "mud"
    return "dirt"


def _terrain_review_biome_name(terrain_preset: str) -> str:
    preset = str(terrain_preset or "").strip().lower()
    if preset in {"mountains", "cliffs", "canyon", "volcanic", "chaotic"}:
        return "mountain_pass_summer"
    if preset == "coastal":
        return "coastal"
    if preset == "swamp":
        return "corrupted_swamp"
    return "grasslands"


def _default_terrain_height_scale(
    *,
    terrain_preset: str,
    terrain_size: float,
    map_spec: dict[str, Any],
) -> float:
    """Return a more readable default terrain height scale for hero-map composition."""
    preset = str(terrain_preset or "").strip().lower()
    base = {
        "mountains": 42.0,
        "hills": 30.0,
        "plains": 10.0,
        "flat": 6.0,
        "coastal": 24.0,
        "swamp": 8.0,
        "cliffs": 40.0,
        "canyon": 38.0,
        "volcanic": 44.0,
        "chaotic": 46.0,
    }.get(preset, 20.0)

    water_cfg = map_spec.get("water", {}) if isinstance(map_spec, dict) else {}
    has_rivers = bool(water_cfg.get("rivers"))
    has_cave = any(
        isinstance(location, dict)
        and str(location.get("type", "")).strip().lower() == "cave"
        for location in (map_spec.get("locations", []) if isinstance(map_spec, dict) else [])
    )
    has_road = bool(map_spec.get("roads")) if isinstance(map_spec, dict) else False

    if preset in {"hills", "coastal"} and (has_rivers or has_cave or has_road):
        base *= 1.22
    if terrain_size >= 300.0:
        base *= 1.08
    return round(base, 3)


def _default_cliff_overlay_setting(
    *,
    terrain_preset: str,
    map_spec: dict[str, Any],
) -> bool:
    """Enable cliff overlays automatically when the requested composition needs them."""
    preset = str(terrain_preset or "").strip().lower()
    if preset in {"mountains", "cliffs", "canyon", "volcanic", "coastal", "chaotic"}:
        return True
    if any(
        isinstance(location, dict)
        and str(location.get("type", "")).strip().lower() == "cave"
        for location in map_spec.get("locations", [])
    ):
        return True
    water_cfg = map_spec.get("water", {})
    if water_cfg.get("waterfalls"):
        return True
    return False


def _distance_point_to_segment_2d(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float, tuple[float, float]]:
    """Return distance, segment t, and closest point from point->segment in 2D."""
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay), 0.0, (ax, ay)
    t = ((px - ax) * abx + (py - ay) * aby) / denom
    t = max(0.0, min(1.0, t))
    qx = ax + abx * t
    qy = ay + aby * t
    return math.hypot(px - qx, py - qy), t, (qx, qy)


def _river_requests_waterfall(river: dict[str, Any]) -> bool:
    """Return True when a river spec explicitly asks for waterfall authoring."""
    if not isinstance(river, dict):
        return False
    if river.get("waterfall") or river.get("has_waterfall"):
        return True
    return str(river.get("type", "")).strip().lower() in {"waterfall", "cascade"}


def _build_water_system_spec_payload(
    water_cfg: dict[str, Any] | None,
    *,
    map_seed: int,
) -> dict[str, Any] | None:
    """Translate compose_map water config into TerrainIntent water-system payload."""
    if not isinstance(water_cfg, dict) or not water_cfg:
        return None
    waterfalls = water_cfg.get("waterfalls", []) or []
    hero_waterfalls = tuple(
        str(entry.get("name")).strip()
        for entry in waterfalls
        if isinstance(entry, dict) and str(entry.get("name", "")).strip()
    )
    return {
        "network_seed": int(water_cfg.get("network_seed", map_seed)),
        "min_drainage_area": float(water_cfg.get("min_drainage_area", 500.0)),
        "river_threshold": float(water_cfg.get("river_threshold", 2000.0)),
        "lake_min_area": float(water_cfg.get("lake_min_area", 100.0)),
        "meander_amplitude": float(water_cfg.get("meander_amplitude", 0.0)),
        "bank_asymmetry": float(water_cfg.get("bank_asymmetry", 0.0)),
        "tidal_range": float(water_cfg.get("tidal_range", 0.0)),
        "hero_waterfalls": hero_waterfalls,
        "braided_channels": bool(water_cfg.get("braided_channels", False)),
        "estuaries": bool(water_cfg.get("estuaries", False)),
        "karst_springs": bool(water_cfg.get("karst_springs", False)),
        "perched_lakes": bool(water_cfg.get("perched_lakes", False)),
        "hot_springs": bool(water_cfg.get("hot_springs", False)),
        "wetlands": bool(water_cfg.get("wetlands", False)),
        "seasonal_state": str(water_cfg.get("seasonal_state", "normal")),
    }


def _derive_waterfall_placement_from_path(
    path_points: list[list[float]] | tuple[tuple[float, float, float], ...] | None,
) -> dict[str, Any] | None:
    """Pick the strongest drop along a carved river path for waterfall placement."""
    if not path_points:
        return None
    normalized: list[list[float]] = []
    for point in path_points:
        if not isinstance(point, (list, tuple)) or len(point) < 3:
            continue
        normalized.append([float(point[0]), float(point[1]), float(point[2])])
    if len(normalized) < 2:
        return None

    best_idx = 0
    best_drop = float("-inf")
    for idx in range(len(normalized) - 1):
        drop = float(normalized[idx][2]) - float(normalized[idx + 1][2])
        if drop > best_drop:
            best_drop = drop
            best_idx = idx

    if best_drop <= 0.05:
        top = normalized[0]
        bottom = normalized[-1]
        best_drop = float(top[2]) - float(bottom[2])
        if best_drop <= 0.05:
            return None
    else:
        top = normalized[best_idx]
        bottom = normalized[best_idx + 1]

    dx = float(bottom[0]) - float(top[0])
    dy = float(bottom[1]) - float(top[1])
    direction_len = math.hypot(dx, dy)
    if direction_len <= 1e-6:
        facing_direction = [0.0, -1.0]
    else:
        facing_direction = [dx / direction_len, dy / direction_len]

    return {
        "top_point": top,
        "bottom_point": bottom,
        "height": float(best_drop),
        "facing_direction": facing_direction,
    }


def _move_point_outside_radius(
    point: list[float],
    *,
    center_x: float,
    center_y: float,
    radius: float,
    reference: tuple[float, float] | None = None,
) -> list[float]:
    """Push a 2D point just outside a circular exclusion radius."""
    px = float(point[0])
    py = float(point[1])
    dx = px - center_x
    dy = py - center_y
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        if reference is not None:
            dx = px - float(reference[0])
            dy = py - float(reference[1])
            dist = math.hypot(dx, dy)
        if dist <= 1e-6:
            dx, dy, dist = 1.0, 0.0, 1.0
    scale = (max(float(radius), 0.0) + 0.75) / dist
    return [center_x + dx * scale, center_y + dy * scale]


def _retarget_road_away_from_caves(
    road: dict[str, Any],
    cave_zones: list[dict[str, float]],
) -> dict[str, Any]:
    """Keep roads from terminating at cave mouths; downgrade them to trails nearby."""
    if not cave_zones:
        return dict(road)

    raw_waypoints = road.get("waypoints", []) or []
    adjusted = [
        [float(waypoint[0]), float(waypoint[1])]
        for waypoint in raw_waypoints
        if isinstance(waypoint, (list, tuple)) and len(waypoint) >= 2
    ]
    if len(adjusted) < 2:
        return dict(road)

    trail_required = False
    for zone in cave_zones:
        center_x = float(zone["center_x"])
        center_y = float(zone["center_y"])
        radius = max(float(zone["radius"]), 1.0)

        for idx, point in enumerate(list(adjusted)):
            reference = None
            if idx > 0:
                reference = (adjusted[idx - 1][0], adjusted[idx - 1][1])
            elif idx + 1 < len(adjusted):
                reference = (adjusted[idx + 1][0], adjusted[idx + 1][1])
            if math.hypot(point[0] - center_x, point[1] - center_y) < radius:
                adjusted[idx] = _move_point_outside_radius(
                    point,
                    center_x=center_x,
                    center_y=center_y,
                    radius=radius,
                    reference=reference,
                )
                trail_required = True

        seg_index = 0
        while seg_index < len(adjusted) - 1:
            ax, ay = adjusted[seg_index]
            bx, by = adjusted[seg_index + 1]
            dist, _t, closest = _distance_point_to_segment_2d(
                center_x,
                center_y,
                ax,
                ay,
                bx,
                by,
            )
            if dist >= radius:
                seg_index += 1
                continue

            trail_required = True
            ox = closest[0] - center_x
            oy = closest[1] - center_y
            offset_len = math.hypot(ox, oy)
            if offset_len <= 1e-6:
                sx = bx - ax
                sy = by - ay
                side_len = math.hypot(sx, sy)
                if side_len <= 1e-6:
                    ox, oy, offset_len = 1.0, 0.0, 1.0
                else:
                    ox = -sy / side_len
                    oy = sx / side_len
                    offset_len = 1.0
            detour_radius = radius + max(float(road.get("width", 3.0)) * 1.2, 2.5)
            detour = [
                center_x + (ox / offset_len) * detour_radius,
                center_y + (oy / offset_len) * detour_radius,
            ]
            adjusted.insert(seg_index + 1, detour)
            seg_index += 2

    road_spec = dict(road)
    road_spec["waypoints"] = adjusted
    if trail_required:
        road_spec["surface"] = "dirt_path"
        road_spec["style"] = "trail"
        road_spec["width"] = min(float(road.get("width", 3.0)), 2.1)
        road_spec["force_mesh_overlay"] = False
        road_spec["allow_bridges"] = False
        road_spec["cave_path_adjusted"] = True
    return road_spec


async def _capture_aaa_screenshots(
    blender: BlenderConnection,
    *,
    angles: int = 10,
    temp_dir: str | None = None,
    prefix: str = "aaa",
    object_name: str | None = None,
    review_profile: str | None = None,
    skip_beauty: bool = False,
) -> dict:
    """Render the shared AAA screenshot set used by visual verification gates."""
    import glob as _glob
    import tempfile as _tempfile

    angle_defs = _AAA_CAMERA_ANGLES[: max(1, min(int(angles), len(_AAA_CAMERA_ANGLES)))]
    if str(review_profile or "").strip().lower() == "terrain":
        terrain_pitch_overrides = {
            "front": 18.0,
            "back": 18.0,
            "left": 17.0,
            "right": 17.0,
            "top": 82.0,
            "ne_45": 24.0,
            "nw_45": 24.0,
            "sw_45": 22.0,
            "se_45": 22.0,
            "ground_level": 14.0,
        }
        angle_defs = [
            (yaw, float(terrain_pitch_overrides.get(label, pitch)), label)
            for yaw, pitch, label in angle_defs
        ]
    safe_prefix = re.sub(r"[^A-Za-z0-9._-]+", "_", str(prefix or "aaa")).strip("_") or "aaa"
    target_dir = temp_dir or os.path.join(_tempfile.gettempdir(), f"vb_{safe_prefix}")
    os.makedirs(target_dir, exist_ok=True)

    for old_png in _glob.glob(os.path.join(target_dir, f"{safe_prefix}_*.png")):
        os.remove(old_png)

    screenshot_paths: list[str] = []
    capture_errors: list[str] = []
    angle_labels: list[str] = []

    if object_name:
        try:
            await blender.send_command("auto_frame_camera", {"object_name": object_name})
        except Exception as exc:
            capture_errors.append(f"{object_name}: auto_frame_camera failed ({exc})")
            return {
                "screenshots": [],
                "capture_errors": capture_errors,
                "angle_labels": [],
                "directory": target_dir,
                "angles": angle_defs,
            }

    for index, (yaw, pitch, label) in enumerate(angle_defs):
        output_path = os.path.join(target_dir, f"{safe_prefix}_{index}_{label}.png")
        angle_labels.append(label)
        try:
            await blender.send_command("render_angle", {
                "yaw": yaw,
                "pitch": pitch,
                "output_path": output_path,
                "object_name": object_name,
                "target_object": object_name,
                "review_profile": review_profile,
                "skip_beauty": skip_beauty,
            })
            if os.path.isfile(output_path):
                screenshot_paths.append(output_path)
            else:
                capture_errors.append(f"{label}: render_angle did not produce a screenshot")
        except Exception as exc:
            capture_errors.append(f"{label}: {exc}")

    existing = [path for path in screenshot_paths if os.path.isfile(path)]
    return {
        "screenshots": existing,
        "capture_errors": capture_errors,
        "angle_labels": angle_labels,
        "directory": target_dir,
        "angles": angle_defs,
    }


async def _run_aaa_visual_verification(
    blender: BlenderConnection,
    *,
    angles: int = 10,
    min_score: int = 60,
    validation_profile: str | None = None,
    capture_baseline: bool = False,
    baseline_dir: str | None = None,
    screenshot_prefix: str = "aaa",
    screenshot_dir: str | None = None,
    object_name: str | None = None,
) -> dict:
    """Capture multi-angle screenshots and run the shared AAA verifier."""
    capture = await _capture_aaa_screenshots(
        blender,
        angles=angles,
        temp_dir=screenshot_dir,
        prefix=screenshot_prefix,
        object_name=object_name,
    )
    existing = capture["screenshots"]
    capture_errors = list(capture["capture_errors"])
    angle_defs = list(capture["angles"])

    if not existing:
        return {
            "status": "error",
            "error": "No screenshots were captured — ensure Blender is connected",
            "hint": "Run Blender with the VeilBreakers addon and try again",
            "capture_errors": capture_errors,
            "screenshots": [],
            "angle_labels": [label for _, _, label in angle_defs],
        }

    verify_result = aaa_verify_map(
        existing,
        min_score=min_score,
        required_angle_count=len(angle_defs),
        angle_labels=[label for _, _, label in angle_defs],
        validation_profile=validation_profile,
    )

    baseline_result = None
    if capture_baseline:
        baseline_target = baseline_dir or os.path.join(capture["directory"], "baselines")
        baseline_result = capture_regression_baseline(existing, baseline_target)

    return {
        "status": "success" if verify_result.get("passed", False) else "failed",
        "verification": verify_result,
        "screenshots": existing,
        "baseline": baseline_result,
        "angle_labels": [label for _, _, label in angle_defs[:len(existing)]],
        "capture_errors": capture_errors,
    }


async def _run_terrain_visual_gate(
    blender: BlenderConnection,
    *,
    map_spec: dict | None = None,
    terrain_result: dict | None = None,
    object_names: list[str] | None = None,
    location_results: list[dict] | None = None,
    validation_profiles: list[str] | None = None,
    min_score: int = 60,
    screenshot_prefix: str = "terrain_gate",
    object_name: str | None = None,
) -> dict:
    """Run mandatory terrain-focused multi-profile verification on one capture set."""
    profiles = _normalize_validation_profiles(validation_profiles)
    if not profiles:
        profiles = _derive_terrain_validation_profiles(
            map_spec=map_spec,
            terrain_result=terrain_result,
            object_names=object_names,
            location_results=location_results,
        )
    if "terrain_readability" not in profiles:
        profiles.insert(0, "terrain_readability")

    capture = await _capture_aaa_screenshots(
        blender,
        angles=len(_AAA_CAMERA_ANGLES),
        prefix=screenshot_prefix,
        object_name=object_name,
        review_profile="terrain",
        skip_beauty=True,
    )
    existing = capture["screenshots"]
    capture_errors = list(capture["capture_errors"])
    angle_labels = [label for _, _, label in capture["angles"]]

    if not existing:
        return {
            "status": "error",
            "passed": False,
            "required_profiles": profiles,
            "failed_profiles": profiles,
            "issues": ["No screenshots were captured — ensure Blender is connected"],
            "capture_errors": capture_errors,
            "screenshots": [],
            "angle_labels": angle_labels,
            "profile_results": [],
        }

    profile_results: list[dict] = []
    failed_profiles: list[str] = []
    issues: list[str] = []
    for profile in profiles:
        verification = aaa_verify_map(
            existing,
            min_score=min_score,
            required_angle_count=len(capture["angles"]),
            angle_labels=angle_labels,
            validation_profile=profile,
        )
        profile_results.append(verification)
        if not verification.get("passed", False):
            failed_profiles.append(profile)
            issues.extend(verification.get("issues", []))

    deduped_issues: list[str] = []
    seen_issue_text: set[str] = set()
    for issue in issues:
        if issue in seen_issue_text:
            continue
        seen_issue_text.add(issue)
        deduped_issues.append(issue)

    return {
        "status": "success" if not failed_profiles else "failed",
        "passed": not failed_profiles,
        "required_profiles": profiles,
        "failed_profiles": failed_profiles,
        "issues": deduped_issues,
        "capture_errors": capture_errors,
        "screenshots": existing,
        "angle_labels": angle_labels,
        "profile_results": profile_results,
    }


def _estimate_location_radius(location: dict) -> float:
    """Estimate a footprint radius for map auto-placement."""
    loc_type = str(location.get("type", "building")).lower()

    if loc_type == "town":
        districts = max(1, int(location.get("districts", 3)))
        grid_size = float(location.get("grid_size", 32))
        return max(18.0, districts * 8.0, grid_size * 0.45)
    if loc_type == "castle":
        outer_size = float(location.get("outer_size", 40))
        tower_count = max(1, int(location.get("tower_count", 4)))
        return max(20.0, outer_size * 0.55, tower_count * 3.0)
    if loc_type in {"dungeon", "cave"}:
        grid_size = float(location.get("grid_size", 64))
        floors = max(1, int(location.get("floors", 1)))
        return max(14.0, grid_size * 0.28, floors * 4.0)
    if loc_type == "boss_arena":
        diameter = float(location.get("diameter", 24.0))
        return max(16.0, diameter * 0.65)
    if loc_type == "ruins":
        return max(14.0, float(location.get("outer_size", 20.0)) * 0.45)
    if loc_type == "building":
        size = str(location.get("building_size", "medium")).lower()
        return {
            "small": 10.0,
            "medium": 14.0,
            "large": 20.0,
            "massive": 28.0,
        }.get(size, 14.0)
    return 14.0


def _normalize_map_point(
    position: list[float] | tuple[float, ...],
    terrain_size: float,
    terrain_location: tuple[float, float] | None = None,
) -> tuple[float, float]:
    """Normalize user map positions into centered Blender-world coordinates."""
    if len(position) < 2:
        raise ValueError("Map position must contain at least two coordinates.")

    x = float(position[0])
    y = float(position[1])
    half = terrain_size / 2.0
    origin_x, origin_y = terrain_location or (0.0, 0.0)

    # Heuristic: shift from 0..size space to centered (-half..+half) space.
    # We only shift when BOTH coords are in [0, size] AND at least one exceeds
    # 60% of terrain_size — this avoids false positives for coords that are
    # already in centered space (e.g. (60,60) on size=100 should stay put).
    threshold = terrain_size * 0.6
    if 0.0 <= x <= terrain_size and 0.0 <= y <= terrain_size and (x > threshold or y > threshold):
        return (x - half + origin_x, y - half + origin_y)
    return (x, y)


def _map_point_to_terrain_cell(
    position: list[float] | tuple[float, ...],
    *,
    terrain_size: float,
    resolution: int,
    terrain_location: tuple[float, float] | None = None,
) -> tuple[int, int]:
    """Convert a world-space map point into a terrain heightmap cell."""
    x, y = float(position[0]), float(position[1])
    if terrain_location is not None:
        x -= terrain_location[0]
        y -= terrain_location[1]
    x, y = _normalize_map_point((x, y), terrain_size)
    half = terrain_size / 2.0
    side = max(2, int(resolution))
    row = int(round(((y + half) / max(terrain_size, 1e-6)) * (side - 1)))
    col = int(round(((x + half) / max(terrain_size, 1e-6)) * (side - 1)))
    row = max(0, min(side - 1, row))
    col = max(0, min(side - 1, col))
    return (row, col)


def _plan_map_location_anchors(map_spec: dict) -> list[dict]:
    """Assign non-overlapping terrain anchors to compose_map locations."""
    terrain_cfg = map_spec.get("terrain", {})
    terrain_size = float(terrain_cfg.get("size", 200.0))
    terrain_location = tuple(terrain_cfg.get("location", (0.0, 0.0)))[:2]
    terrain_origin_x, terrain_origin_y = terrain_location
    half = terrain_size / 2.0
    locations = list(map_spec.get("locations", []))
    placements: list[dict] = []

    def _candidate_is_clear(candidate: tuple[float, float], radius: float) -> bool:
        for existing in placements:
            dx = candidate[0] - existing["anchor"][0]
            dy = candidate[1] - existing["anchor"][1]
            min_distance = existing["radius"] + radius + 8.0
            if (dx * dx + dy * dy) < (min_distance * min_distance):
                return False
        return True

    candidate_points: list[tuple[float, float]] = []
    ring_fractions = (0.18, 0.30, 0.40)
    for ring_idx, fraction in enumerate(ring_fractions):
        radius_x = half * fraction
        radius_y = half * max(0.16, fraction * 0.82)
        count = max(6, len(locations) * 3)
        for i in range(count):
            angle = (2.0 * math.pi * i / count) + (ring_idx * 0.31)
            candidate_points.append((
                round(math.cos(angle) * radius_x + terrain_origin_x, 3),
                round(math.sin(angle) * radius_y + terrain_origin_y, 3),
            ))
    candidate_points.append((terrain_origin_x, terrain_origin_y))

    for index, location in enumerate(locations):
        radius = _estimate_location_radius(location)
        requested = location.get("position")
        anchor: tuple[float, float] | None = None

        if isinstance(requested, (list, tuple)) and len(requested) >= 2:
            if terrain_cfg.get("location") is not None:
                # Explicit world-space anchor. The clamp block below still
                # runs — it uses world-space bounds when terrain_cfg.location
                # is set — so the caller cannot escape the terrain footprint.
                anchor = (float(requested[0]), float(requested[1]))
            else:
                anchor = _normalize_map_point(requested, terrain_size)

        if anchor is None:
            for candidate in candidate_points:
                if _candidate_is_clear(candidate, radius):
                    anchor = candidate
                    break

        if anchor is None:
            search_limit = max(0.0, half - radius)
            radial_step = max(10.0, radius * 0.9)
            ring_count = max(4, int(search_limit / max(radial_step, 1.0)) + 1)
            for ring in range(1, ring_count + 1):
                search_radius = min(search_limit, ring * radial_step)
                samples = max(18, ring * 14)
                for sample_idx in range(samples):
                    angle = (2.0 * math.pi * sample_idx / samples) + (ring * 0.37)
                    candidate = (
                        round(math.cos(angle) * search_radius, 3),
                        round(math.sin(angle) * search_radius * 0.84, 3),
                    )
                    if _candidate_is_clear(candidate, radius):
                        anchor = candidate
                        break
                if anchor is not None:
                    break

        if anchor is None:
            fallback_x = -half * 0.42 + index * max(radius * 1.8, 14.0)
            anchor = (
                round(max(-half + radius, min(half - radius, fallback_x)), 3),
                0.0,
            )

        if terrain_cfg.get("location") is not None:
            min_x = terrain_origin_x - half + radius
            max_x = terrain_origin_x + half - radius
            min_y = terrain_origin_y - half + radius
            max_y = terrain_origin_y + half - radius
        else:
            min_x = -half + radius
            max_x = half - radius
            min_y = -half + radius
            max_y = half - radius

        clamped = (
            max(min_x, min(max_x, anchor[0])),
            max(min_y, min(max_y, anchor[1])),
        )
        placements.append({
            "name": location.get("name", f"Location_{index}"),
            "type": location.get("type", "building"),
            "anchor": clamped,
            "radius": radius,
            "source": location,
        })

    return placements


def _resolve_map_generation_budget(map_spec: dict) -> dict:
    """Return a practical generation budget for the local iteration target."""
    terrain_cfg = map_spec.get("terrain", {})
    terrain_size = float(terrain_cfg.get("size", 200.0))
    requested_profile = str(
        map_spec.get("performance_budget")
        or map_spec.get("budget_profile")
        or map_spec.get("quality_tier")
        or ""
    ).strip().lower()
    location_count = len(map_spec.get("locations", []))

    presets = {
        "cinematic": {
            "profile": "cinematic",
            "terrain_resolution_cap": 512,
            "vegetation_max_instances": 8000,
            "prop_density_scale": 1.0,
        },
        "balanced_pc": {
            "profile": "balanced_pc",
            "terrain_resolution_cap": 384,
            "vegetation_max_instances": 4500,
            "prop_density_scale": 0.9,
        },
        "large_world": {
            "profile": "large_world",
            "terrain_resolution_cap": 256,
            "vegetation_max_instances": 2500,
            "prop_density_scale": 0.7,
        },
    }

    if requested_profile in presets:
        budget = dict(presets[requested_profile])
    elif terrain_size >= 360.0 or location_count >= 8:
        budget = dict(presets["large_world"])
    else:
        budget = dict(presets["balanced_pc"])

    budget["terrain_size"] = terrain_size
    budget["location_count"] = location_count
    return budget


def _derive_site_profile(location: dict, map_spec: dict) -> str:
    """Infer a building site profile from freeform location and map briefs."""
    parts = []
    for source in (map_spec, location):
        for key in ("layout_brief", "visual_brief", "style_brief", "description", "prompt", "brief", "theme"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip().lower())

    combined = " ".join(parts)
    tokens = set(combined.replace(",", " ").replace(".", " ").split())

    if tokens & {"harbor", "harbour", "port", "river", "canal", "dock", "docks", "waterfront", "coast", "coastal", "bay"}:
        return "waterfront"
    if tokens & {"cliff", "cliffside", "cliffs", "ridge", "terrace", "terraces", "terraced", "slope", "hillside", "mountain"}:
        return "cliffside"
    if tokens & {"fort", "fortified", "citadel", "garrison", "barracks", "keep"}:
        return "fortified"
    if tokens & {"abbey", "cathedral", "temple", "shrine", "monastery", "academy", "school"}:
        return "monastery"
    if tokens & {"forge", "smith", "workshop", "industrial"}:
        return "forgeyard"
    if tokens & {"market", "merchant", "trade", "bazaar", "guild"}:
        return "market"
    return ""


def _build_location_generation_params(
    location: dict,
    *,
    map_spec: dict,
    map_seed: int,
    index: int,
) -> dict:
    """Build high-level generation params while preserving map/location intent."""
    loc_type = str(location.get("type", "town")).lower()
    params = {
        "name": location.get("name", f"{loc_type.title()}_{index}"),
        "seed": map_seed + 200 + index,
    }

    layout_brief = ""
    for key in ("layout_brief", "description", "prompt", "brief"):
        value = location.get(key)
        if isinstance(value, str) and value.strip():
            layout_brief = value.strip()
            break
    if not layout_brief:
        map_layout = map_spec.get("layout_brief")
        if isinstance(map_layout, str) and map_layout.strip():
            layout_brief = map_layout.strip()

    site_profile = str(location.get("site_profile") or _derive_site_profile(location, map_spec)).strip().lower()
    style_value = location.get("style")
    preset_value = location.get("preset")

    if layout_brief:
        params["layout_brief"] = layout_brief
    if site_profile:
        params["site_profile"] = site_profile
    if isinstance(style_value, str) and style_value.strip():
        params["style"] = style_value.strip().lower()
    if isinstance(preset_value, str) and preset_value.strip():
        params["preset"] = preset_value.strip()
    if "weathering_level" in location:
        params["weathering_level"] = location.get("weathering_level")

    if loc_type == "town":
        params["num_districts"] = location.get("districts", 3)
        params["width"] = location.get("grid_size", 32)
        params["height"] = location.get("grid_size", 32)
    elif loc_type == "castle":
        params["outer_size"] = location.get("outer_size", 40)
        params["tower_count"] = location.get("tower_count", 4)
        if "keep_size" in location:
            params["keep_size"] = location.get("keep_size")
    elif loc_type in ("dungeon", "cave"):
        params["width"] = location.get("grid_size", 64)
        params["height"] = location.get("grid_size", 64)
        if loc_type == "dungeon" and location.get("floors"):
            params["num_floors"] = location["floors"]
    elif loc_type == "ruins":
        params["damage_level"] = location.get("damage_level", 0.7)
        params["width"] = location.get("width", location.get("outer_size", 18))
        params["depth"] = location.get("depth", location.get("outer_size", 14))
        params["floors"] = location.get("floors", 2)
    elif loc_type == "boss_arena":
        params["arena_type"] = location.get("arena_type", "circular")
    elif loc_type == "settlement":
        params["settlement_type"] = location.get("settlement_type", "town")
        params["radius"] = location.get("radius", 50.0)
        if "center" in location:
            params["center"] = location["center"]
        if "building_count" in location:
            params["building_count_override"] = location["building_count"]
    elif loc_type == "building":
        params["building_size"] = location.get("building_size", "medium")
        params["width"] = location.get("width", 12)
        params["depth"] = location.get("depth", 9)
        params["floors"] = location.get("floors", 2)

    return params


def _world_quality_prefixes(result_names: list[str]) -> list[str]:
    """Normalize non-empty scene object prefixes for world validation."""
    prefixes = []
    seen: set[str] = set()
    for name in result_names:
        clean = str(name or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        prefixes.append(clean)
    return prefixes


def _should_validate_world_mesh(
    name: str,
    obj_type: str,
    prefixes: list[str],
) -> bool:
    """Return True when a generated mesh merits world-quality validation."""
    if obj_type != "MESH":
        return False
    if "_LOD" in name or "Terrain" in name:
        return False
    if "_Window_" in name or "_Facade_" in name:
        return False
    return any(name == prefix or name.startswith(f"{prefix}_") for prefix in prefixes)


def _world_quality_family(name: str) -> str:
    """Collapse repeated mesh variants into a stable validation family."""
    family = re.sub(r"_Interior_\d+", "_Interior", name)
    family = re.sub(r"_(\d+)(?=$|_)", "_#", family)
    return family


def _default_vegetation_rules_for_biome(biome_name: str, density: float) -> list[dict]:
    biome = str(biome_name or "").strip().lower()
    if biome == "thornwood_forest":
        return [
            {
                "vegetation_type": "tree_healthy",
                "min_alt": 0.10,
                "max_alt": 0.70,
                "min_slope": 0.0,
                "max_slope": 24.0,
                "scale_range": (1.0, 1.9),
                "density": 0.28 * density,
            },
            {
                "vegetation_type": "tree_boundary",
                "min_alt": 0.12,
                "max_alt": 0.78,
                "min_slope": 0.0,
                "max_slope": 28.0,
                "scale_range": (0.95, 1.8),
                "density": 0.18 * density,
            },
            {
                "vegetation_type": "tree_blighted",
                "min_alt": 0.22,
                "max_alt": 0.88,
                "min_slope": 0.0,
                "max_slope": 32.0,
                "scale_range": (0.8, 1.45),
                "density": 0.06 * density,
            },
            {
                "vegetation_type": "shrub",
                "min_alt": 0.06,
                "max_alt": 0.64,
                "min_slope": 0.0,
                "max_slope": 34.0,
                "scale_range": (0.7, 1.2),
                "density": 0.38 * density,
            },
            {
                "vegetation_type": "grass",
                "min_alt": 0.0,
                "max_alt": 0.48,
                "min_slope": 0.0,
                "max_slope": 30.0,
                "scale_range": (0.55, 0.98),
                "density": 0.52 * density,
            },
            {
                "vegetation_type": "rock_mossy",
                "min_alt": 0.24,
                "max_alt": 1.0,
                "min_slope": 14.0,
                "max_slope": 90.0,
                "scale_range": (0.7, 1.3),
                "density": 0.16 * density,
            },
        ]
    if biome == "deep_forest":
        return [
            {
                "vegetation_type": "tree_boundary",
                "min_alt": 0.08,
                "max_alt": 0.82,
                "min_slope": 0.0,
                "max_slope": 24.0,
                "scale_range": (1.4, 2.5),
                "density": 0.24 * density,
            },
            {
                "vegetation_type": "tree_blighted",
                "min_alt": 0.16,
                "max_alt": 0.92,
                "min_slope": 0.0,
                "max_slope": 28.0,
                "scale_range": (1.0, 1.9),
                "density": 0.10 * density,
            },
            {
                "vegetation_type": "shrub",
                "min_alt": 0.05,
                "max_alt": 0.58,
                "min_slope": 0.0,
                "max_slope": 30.0,
                "scale_range": (0.7, 1.1),
                "density": 0.26 * density,
            },
            {
                "vegetation_type": "root",
                "min_alt": 0.08,
                "max_alt": 0.76,
                "min_slope": 0.0,
                "max_slope": 38.0,
                "scale_range": (0.8, 1.25),
                "density": 0.16 * density,
            },
            {
                "vegetation_type": "grass",
                "min_alt": 0.0,
                "max_alt": 0.38,
                "min_slope": 0.0,
                "max_slope": 26.0,
                "scale_range": (0.45, 0.82),
                "density": 0.22 * density,
            },
            {
                "vegetation_type": "rock_mossy",
                "min_alt": 0.28,
                "max_alt": 1.0,
                "min_slope": 16.0,
                "max_slope": 90.0,
                "scale_range": (0.8, 1.4),
                "density": 0.18 * density,
            },
        ]
    if biome in {"veil_crack_zone", "corrupted_swamp"}:
        return [
            {
                "vegetation_type": "tree_blighted",
                "min_alt": 0.10,
                "max_alt": 0.82,
                "min_slope": 0.0,
                "max_slope": 28.0,
                "scale_range": (0.9, 1.8),
                "density": 0.20 * density,
            },
            {
                "vegetation_type": "mushroom_cluster",
                "min_alt": 0.02,
                "max_alt": 0.44,
                "min_slope": 0.0,
                "max_slope": 28.0,
                "scale_range": (0.5, 0.95),
                "density": 0.22 * density,
            },
            {
                "vegetation_type": "root",
                "min_alt": 0.08,
                "max_alt": 0.70,
                "min_slope": 0.0,
                "max_slope": 36.0,
                "scale_range": (0.8, 1.3),
                "density": 0.18 * density,
            },
            {
                "vegetation_type": "rock",
                "min_alt": 0.20,
                "max_alt": 1.0,
                "min_slope": 12.0,
                "max_slope": 90.0,
                "scale_range": (0.7, 1.35),
                "density": 0.24 * density,
            },
        ]
    return [
        {
            "vegetation_type": "tree",
            "min_alt": 0.08,
            "max_alt": 0.72,
            "min_slope": 0.0,
            "max_slope": 24.0,
            "scale_range": (0.9, 1.6),
            "density": 0.62 * density,
        },
        {
            "vegetation_type": "bush",
            "min_alt": 0.05,
            "max_alt": 0.55,
            "min_slope": 0.0,
            "max_slope": 30.0,
            "scale_range": (0.55, 1.1),
            "density": 0.78 * density,
        },
        {
            "vegetation_type": "grass",
            "min_alt": 0.0,
            "max_alt": 0.45,
            "min_slope": 0.0,
            "max_slope": 28.0,
            "scale_range": (0.35, 0.78),
            "density": 0.92 * density,
        },
        {
            "vegetation_type": "rock",
            "min_alt": 0.28,
            "max_alt": 1.0,
            "min_slope": 16.0,
            "max_slope": 90.0,
            "scale_range": (0.55, 1.25),
            "density": 0.36 * density,
        },
    ]


def _normalize_vegetation_rules(veg_cfg: dict, biome_name: str = "") -> list[dict]:
    """Convert compose_map vegetation hints into scatter-vegetation rules."""
    density = float(veg_cfg.get("density", 0.5))
    raw_rules = veg_cfg.get("rules")
    if isinstance(raw_rules, list) and raw_rules:
        normalized: list[dict] = []
        for entry in raw_rules:
            if not isinstance(entry, dict):
                continue
            vegetation_type = str(entry.get("vegetation_type") or entry.get("asset") or "tree")
            normalized.append({
                "vegetation_type": vegetation_type,
                "min_alt": float(entry.get("min_alt", 0.0)),
                "max_alt": float(entry.get("max_alt", 1.0)),
                "min_slope": float(entry.get("min_slope", 0.0)),
                "max_slope": float(entry.get("max_slope", 45.0)),
                "scale_range": tuple(entry.get("scale_range", (0.6, 1.2))),
                "density": float(entry.get("density", density)),
            })
        if normalized:
            return normalized
    return _default_vegetation_rules_for_biome(biome_name, density)


def _lighting_preset_for_biome(biome_name: str) -> str:
    biome = str(biome_name or "").strip().lower()
    if biome == "thornwood_forest":
        return "forest_review"
    if biome == "deep_forest":
        return "forest_review"
    if biome.startswith("mountain_pass") or biome in {"coastal", "grasslands"}:
        return "terrain_review"
    if biome in {"veil_crack_zone", "corrupted_swamp", "cemetery"}:
        return "veil_corrupted"
    return "forest_healthy"


async def _collect_mesh_targets(
    blender: BlenderConnection,
    prefixes: list[str],
) -> list[str]:
    """Collect mesh objects that belong to generated world roots."""
    try:
        objects = await blender.send_command("list_objects", {})
    except (OSError, ConnectionError, TimeoutError, BlenderCommandError):
        return []

    targets: list[str] = []
    seen: set[str] = set()
    family_counts: dict[str, int] = {}
    max_targets = 64
    for obj in objects if isinstance(objects, list) else []:
        name = str(obj.get("name", ""))
        obj_type = str(obj.get("type", ""))
        if not _should_validate_world_mesh(name, obj_type, prefixes):
            continue
        family = _world_quality_family(name)
        if family_counts.get(family, 0) >= 1:
            continue
        if name not in seen:
            seen.add(name)
            targets.append(name)
            family_counts[family] = family_counts.get(family, 0) + 1
            if len(targets) >= max_targets:
                break
    return targets


async def _enforce_world_quality(
    blender: BlenderConnection,
    *,
    object_names: list[str],
    poly_budget: int = 90000,
    lod_ratios: list[float] | None = None,
) -> dict:
    """Validate and remediate UV/material/LOD quality for generated world meshes."""
    prefixes = _world_quality_prefixes(object_names)
    mesh_targets = await _collect_mesh_targets(blender, prefixes)
    report: dict[str, Any] = {
        "mesh_targets": mesh_targets,
        "validated_meshes": 0,
        "uv_fixed": [],
        "materials_fixed": [],
        "lod_generated": [],
        "failures": [],
    }

    for mesh_name in mesh_targets:
        report["validated_meshes"] += 1  # type: ignore[operator]
        try:
            game_ready_result = await blender.send_command(
                "mesh_check_game_ready",
                {"object_name": mesh_name, "poly_budget": poly_budget, "platform": "pc"},
            )
            checks = game_ready_result.get("checks", {}) if isinstance(game_ready_result, dict) else {}
            is_game_ready = bool(game_ready_result.get("game_ready", False)) if isinstance(game_ready_result, dict) else False
            has_material = bool(checks.get("materials", {}).get("passed", False))
            if not has_material:
                await blender.send_command(
                    "texture_create_pbr",
                    {"name": mesh_name, "object_name": mesh_name, "texture_size": 1024},
                )
                report["materials_fixed"].append(mesh_name)  # type: ignore[append]

            # Check for smart_material_preset custom property and apply smart material if tagged
            try:
                # PIPE-037: sanitize mesh_name to prevent code injection
                safe_mesh_name = mesh_name.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "").replace("\r", "").replace("\0", "")
                preset_result = await blender.send_command(
                    "execute_code",
                    {"code": (
                        f"import bpy\n"
                        f"obj = bpy.data.objects.get('{safe_mesh_name}')\n"
                        f"result = obj.get('smart_material_preset', '') if obj else ''"
                    )},
                )
                smart_preset = preset_result.get("result", "") if isinstance(preset_result, dict) else ""
                if smart_preset:
                    smart_code_result = await blender.send_command(
                        "texture_smart_material_code",
                        {
                            "material_type": smart_preset,
                            "object_name": mesh_name,
                            "wear_intensity": 0.5,
                            "dirt_intensity": 0.4,
                            "moss_intensity": 0.3,
                            "age": 0.5,
                        },
                    )
                    if isinstance(smart_code_result, dict):
                        code_str = smart_code_result.get("code", "")
                        if code_str:
                            validate_code(code_str)
                            await blender.send_command("execute_code", {"code": code_str})
            except (OSError, ConnectionError, TimeoutError, ValueError, RuntimeError, BlenderCommandError):
                pass

            uv_report = await blender.send_command(
                "uv_analyze",
                {"object_name": mesh_name, "texture_size": 1024},
            )
            needs_uv_fix = (
                not bool(uv_report.get("has_uvs", False))
                or int(uv_report.get("overlap_count", 0)) > 0
                or float(uv_report.get("uv_coverage", 0.0)) < 0.03
            )
            if needs_uv_fix:
                try:
                    await blender.send_command(
                        "uv_unwrap_xatlas",
                        {"object_name": mesh_name, "resolution": 1024, "padding": 4, "rotate_charts": True},
                    )
                except (OSError, ConnectionError, TimeoutError, ValueError, RuntimeError, BlenderCommandError):
                    await blender.send_command(
                        "uv_unwrap_blender",
                        {"object_name": mesh_name, "method": "smart_project", "angle_limit": 66.0},
                    )
                report["uv_fixed"].append(mesh_name)  # type: ignore[append]

            await blender.send_command(
                "pipeline_generate_lods",
                {"object_name": mesh_name, "ratios": lod_ratios or [0.6, 0.3, 0.12]},
            )
            report["lod_generated"].append(mesh_name)  # type: ignore[append]

            # Re-validate after fixes to catch assets that are STILL not game-ready
            if not is_game_ready:
                recheck = await blender.send_command(
                    "mesh_check_game_ready",
                    {"object_name": mesh_name, "poly_budget": poly_budget, "platform": "pc"},
                )
                if isinstance(recheck, dict) and not recheck.get("game_ready", False):
                    _failed = [
                        k for k, v in recheck.get("checks", {}).items()
                        if isinstance(v, dict) and not v.get("passed", True)
                    ]
                    report["failures"].append({  # type: ignore[append]
                        "object_name": mesh_name,
                        "error": f"Still not game-ready after fixes: {', '.join(_failed)}",
                        "failed_checks": _failed,
                    })
        except (OSError, ConnectionError, TimeoutError, ValueError, RuntimeError, BlenderCommandError) as exc:
            report["failures"].append({"object_name": mesh_name, "error": str(exc)})  # type: ignore[append]

    report["status"] = "success" if not report["failures"] else "partial"  # type: ignore[index]
    report["mesh_target_count"] = len(report["mesh_targets"])  # type: ignore[arg-type]
    report["mesh_targets_sample"] = report["mesh_targets"][:20]  # type: ignore[index]
    report["uv_fixed_count"] = len(report["uv_fixed"])  # type: ignore[arg-type]
    report["uv_fixed_sample"] = report["uv_fixed"][:12]  # type: ignore[index]
    report["materials_fixed_count"] = len(report["materials_fixed"])  # type: ignore[arg-type]
    report["materials_fixed_sample"] = report["materials_fixed"][:12]  # type: ignore[index]
    report["lod_generated_count"] = len(report["lod_generated"])  # type: ignore[arg-type]
    report["lod_generated_sample"] = report["lod_generated"][:12]  # type: ignore[index]
    del report["mesh_targets"]  # type: ignore[arg-type]
    del report["uv_fixed"]  # type: ignore[arg-type]
    del report["materials_fixed"]  # type: ignore[arg-type]
    del report["lod_generated"]  # type: ignore[arg-type]
    return report


def _bounds_overlap(a: dict, b: dict, padding: float = 0.0) -> bool:
    """Return True when two 2D room bounds overlap."""
    if "bounds" not in a or "bounds" not in b:
        return False
    a_min = a["bounds"]["min"]
    a_max = a["bounds"]["max"]
    b_min = b["bounds"]["min"]
    b_max = b["bounds"]["max"]
    # PIPE-023: padding adds required clearance between rooms.
    # Positive padding means rooms must be further apart to NOT overlap.
    return not (
        a_max[0] + padding <= b_min[0]
        or b_max[0] + padding <= a_min[0]
        or a_max[1] + padding <= b_min[1]
        or b_max[1] + padding <= a_min[1]
    )


def _derive_room_door_position(
    from_room: dict,
    to_room: dict | None,
    facing: str | None = None,
) -> dict:
    """Compute a usable door marker from one room to another or outside."""
    f_min = from_room["bounds"]["min"]
    f_max = from_room["bounds"]["max"]
    z = 0.0

    if to_room is None:
        resolved_facing = facing or "south"
        if resolved_facing == "north":
            return {"position": ((f_min[0] + f_max[0]) / 2.0, f_max[1], z), "facing": "north"}
        if resolved_facing == "east":
            return {"position": (f_max[0], (f_min[1] + f_max[1]) / 2.0, z), "facing": "east"}
        if resolved_facing == "west":
            return {"position": (f_min[0], (f_min[1] + f_max[1]) / 2.0, z), "facing": "west"}
        return {"position": ((f_min[0] + f_max[0]) / 2.0, f_min[1], z), "facing": "south"}

    t_min = to_room["bounds"]["min"]
    t_max = to_room["bounds"]["max"]
    from_center = ((f_min[0] + f_max[0]) / 2.0, (f_min[1] + f_max[1]) / 2.0)
    to_center = ((t_min[0] + t_max[0]) / 2.0, (t_min[1] + t_max[1]) / 2.0)
    dx = to_center[0] - from_center[0]
    dy = to_center[1] - from_center[1]

    if abs(dx) >= abs(dy):
        if dx >= 0.0:
            y = max(f_min[1], min(f_max[1], (max(f_min[1], t_min[1]) + min(f_max[1], t_max[1])) / 2.0))
            return {"position": (f_max[0], y, z), "facing": "east"}
        y = max(f_min[1], min(f_max[1], (max(f_min[1], t_min[1]) + min(f_max[1], t_max[1])) / 2.0))
        return {"position": (f_min[0], y, z), "facing": "west"}

    if dy >= 0.0:
        x = max(f_min[0], min(f_max[0], (max(f_min[0], t_min[0]) + min(f_max[0], t_max[0])) / 2.0))
        return {"position": (x, f_max[1], z), "facing": "north"}
    x = max(f_min[0], min(f_max[0], (max(f_min[0], t_min[0]) + min(f_max[0], t_max[0])) / 2.0))
    return {"position": (x, f_min[1], z), "facing": "south"}


def _plan_interior_rooms(interior_spec: dict) -> dict:
    """Build room bounds and door markers from compose_interior graph data."""
    rooms = list(interior_spec.get("rooms", []))
    doors = list(interior_spec.get("doors", []))
    if not rooms:
        return {"rooms": [], "doors": [], "building_bounds": {"min": (0.0, 0.0), "max": (0.0, 0.0)}}

    # SAFE-03: Check if rooms already have pre-computed bounds from building_interior_binding
    all_have_bounds = all(
        room.get("bounds") and room.get("position")
        for room in rooms
    )
    if all_have_bounds:
        placed_rooms = []
        for room in rooms:
            bounds = room["bounds"]
            placed_rooms.append({
                "name": room.get("name", f"room_{len(placed_rooms)}"),
                "type": room.get("type", "generic"),
                "width": float(room.get("width", 6.0)),
                "depth": float(room.get("depth", 6.0)),
                "height": float(room.get("height", 3.5)),
                "bounds": bounds,
            })
        all_mins = [r["bounds"]["min"] for r in placed_rooms]
        all_maxs = [r["bounds"]["max"] for r in placed_rooms]
        bldg_min = (min(m[0] for m in all_mins), min(m[1] for m in all_mins))
        bldg_max = (max(m[0] for m in all_maxs), max(m[1] for m in all_maxs))
        # Process doors for pre-computed path
        door_defs: list[dict] = []
        room_by_name = {r["name"]: r for r in placed_rooms}
        for door in doors:
            if isinstance(door.get("position"), (list, tuple)) and len(door["position"]) >= 2:
                explicit = door["position"]
                z = float(explicit[2]) if len(explicit) > 2 else 0.0
                door_defs.append({"position": (float(explicit[0]), float(explicit[1]), z), "facing": door.get("facing", "south")})
            else:
                src = door.get("from")
                dst = door.get("to")
                if src in room_by_name:
                    door_defs.append(_derive_room_door_position(room_by_name[src], room_by_name.get(dst), door.get("facing")))
        if not door_defs and placed_rooms:
            door_defs.append(_derive_room_door_position(placed_rooms[0], None, "south"))
        return {"rooms": placed_rooms, "doors": door_defs, "building_bounds": {"min": bldg_min, "max": bldg_max}}

    room_lookup = {room.get("name", f"room_{index}"): room for index, room in enumerate(rooms)}
    placed: dict[str, dict] = {}
    adjacency: dict[str, list[tuple[str, dict]]] = {name: [] for name in room_lookup}

    for door in doors:
        src = door.get("from")
        dst = door.get("to")
        if src in adjacency and dst in adjacency:
            adjacency[src].append((dst, door))
            adjacency[dst].append((src, door))

    first_room = rooms[0]
    first_name = first_room.get("name", "room_0")
    first_width = float(first_room.get("width", 6.0))
    first_depth = float(first_room.get("depth", 6.0))
    first_height = float(first_room.get("height", 3.5))
    first_floor = float(first_room.get("floor", 0))  # SAFE-04: floor-aware Z
    first_floor_z = first_floor * first_height
    placed[first_name] = {
        "name": first_name,
        "type": first_room.get("type", "generic"),
        "width": first_width,
        "depth": first_depth,
        "height": first_height,
        "bounds": {"min": (0.0, 0.0, round(first_floor_z, 3)), "max": (first_width, first_depth, round(first_floor_z + first_height, 3))},
    }

    used_sides: dict[str, list[str]] = {first_name: []}
    queue: deque[str] = deque([first_name])
    side_cycle = ("east", "north", "west", "south")

    def candidate_bounds(room_name: str, neighbor_name: str, direction: str) -> dict:
        anchor = placed[room_name]
        target = room_lookup[neighbor_name]
        width = float(target.get("width", 6.0))
        depth = float(target.get("depth", 6.0))
        height = float(target.get("height", 3.5))
        floor = float(target.get("floor", 0))  # SAFE-04: floor-aware Z
        floor_z = floor * height
        a_min = anchor["bounds"]["min"]
        a_max = anchor["bounds"]["max"]

        if direction == "east":
            min_x = a_max[0]
            min_y = ((a_min[1] + a_max[1]) - depth) / 2.0
        elif direction == "west":
            min_x = a_min[0] - width
            min_y = ((a_min[1] + a_max[1]) - depth) / 2.0
        elif direction == "north":
            min_x = ((a_min[0] + a_max[0]) - width) / 2.0
            min_y = a_max[1]
        else:
            min_x = ((a_min[0] + a_max[0]) - width) / 2.0
            min_y = a_min[1] - depth

        return {
            "name": neighbor_name,
            "type": target.get("type", "generic"),
            "width": width,
            "depth": depth,
            "height": height,
            "bounds": {
                "min": (round(min_x, 3), round(min_y, 3), round(floor_z, 3)),
                "max": (round(min_x + width, 3), round(min_y + depth, 3), round(floor_z + height, 3)),
            },
        }

    while queue:
        current = queue.popleft()
        used_sides.setdefault(current, [])
        for neighbor, _door in adjacency.get(current, []):
            if neighbor in placed:
                continue

            chosen = None
            for direction in side_cycle:
                if direction in used_sides[current]:
                    continue
                proposal = candidate_bounds(current, neighbor, direction)
                if not any(_bounds_overlap(proposal, existing) for existing in placed.values()):
                    chosen = (direction, proposal)
                    break

            if chosen is None:
                # Fallback: extend east of the current overall bbox.
                max_x = max(room["bounds"]["max"][0] for room in placed.values())
                current_bounds = candidate_bounds(current, neighbor, "east")
                width = current_bounds["width"]
                depth = current_bounds["depth"]
                height = current_bounds["height"]
                _fb_floor = float(room_lookup[neighbor].get("floor", 0))  # SAFE-04
                _fb_floor_z = _fb_floor * height
                chosen = (
                    "east",
                    {
                        "name": neighbor,
                        "type": room_lookup[neighbor].get("type", "generic"),
                        "width": width,
                        "depth": depth,
                        "height": height,
                        "bounds": {
                            "min": (round(max_x + 1.5, 3), current_bounds["bounds"]["min"][1], round(_fb_floor_z, 3)),
                            "max": (round(max_x + 1.5 + width, 3), current_bounds["bounds"]["min"][1] + depth, round(_fb_floor_z + height, 3)),
                        },
                    },
                )

            direction, proposal = chosen
            placed[neighbor] = proposal
            used_sides[current].append(direction)
            used_sides.setdefault(neighbor, [])
            queue.append(neighbor)

    # Any disconnected rooms get stacked to the east.
    for index, room in enumerate(rooms):
        room_name = room.get("name", f"room_{index}")
        if room_name in placed:
            continue
        width = float(room.get("width", 6.0))
        depth = float(room.get("depth", 6.0))
        height = float(room.get("height", 3.5))
        _dc_floor = float(room.get("floor", 0))  # SAFE-04: floor-aware Z
        _dc_floor_z = _dc_floor * height
        max_x = max(existing["bounds"]["max"][0] for existing in placed.values())
        min_y = min(existing["bounds"]["min"][1] for existing in placed.values())
        y_offset = min_y + index * (depth + 1.0)
        placed[room_name] = {
            "name": room_name,
            "type": room.get("type", "generic"),
            "width": width,
            "depth": depth,
            "height": height,
            "bounds": {
                "min": (round(max_x + 2.0, 3), round(y_offset, 3), round(_dc_floor_z, 3)),
                "max": (round(max_x + 2.0 + width, 3), round(y_offset + depth, 3), round(_dc_floor_z + height, 3)),
            },
        }

    room_defs = [placed[room.get("name", f"room_{index}")] for index, room in enumerate(rooms)]

    bbox_min_x = min(room["bounds"]["min"][0] for room in room_defs)
    bbox_min_y = min(room["bounds"]["min"][1] for room in room_defs)
    bbox_max_x = max(room["bounds"]["max"][0] for room in room_defs)
    bbox_max_y = max(room["bounds"]["max"][1] for room in room_defs)

    door_defs: list[dict] = []
    for door in doors:
        if isinstance(door.get("position"), (list, tuple)) and len(door["position"]) >= 2:
            explicit = door["position"]
            facing = door.get("facing", "south")
            z = float(explicit[2]) if len(explicit) > 2 else 0.0
            door_defs.append({
                "position": (float(explicit[0]), float(explicit[1]), z),
                "facing": facing,
            })
            continue

        src = door.get("from")
        dst = door.get("to")
        if src not in placed:
            continue
        placement = _derive_room_door_position(
            placed[src],
            placed.get(dst) if dst else None,
            door.get("facing"),
        )
        door_defs.append(placement)

    if not door_defs:
        primary_room = room_defs[0]
        door_defs.append(_derive_room_door_position(primary_room, None, "south"))

    margin = 0.8
    building_bounds = {
        "min": (round(bbox_min_x - margin, 3), round(bbox_min_y - margin, 3)),
        "max": (round(bbox_max_x + margin, 3), round(bbox_max_y + margin, 3)),
    }
    return {
        "rooms": room_defs,
        "doors": door_defs,
        "building_bounds": building_bounds,
    }


async def _sample_terrain_height(
    blender: BlenderConnection,
    terrain_name: str,
    x: float,
    y: float,
) -> float:
    """Sample a terrain height in Blender via a safe raycast script."""
    x, y = float(x), float(y)
    if math.isnan(x) or math.isnan(y) or math.isinf(x) or math.isinf(y):
        return 0.0
    # Validate terrain_name to prevent code injection
    if not re.match(r'^[A-Za-z0-9_\-. ]+$', terrain_name):
        logger.warning("Invalid terrain_name rejected: %s", terrain_name)
        return 0.0

    code = f"""
import bpy
from mathutils import Vector
depsgraph = bpy.context.evaluated_depsgraph_get()
obj = bpy.data.objects.get("{terrain_name}")
origin = Vector(({x}, {y}, 10000.0))
direction = Vector((0.0, 0.0, -1.0))
if obj is None:
    print(0.0)
else:
    eval_obj = obj.evaluated_get(depsgraph)
    inv = eval_obj.matrix_world.inverted()
    local_origin = inv @ origin
    local_direction = (inv.to_3x3() @ direction).normalized()
    hit, location, normal, face_index = eval_obj.ray_cast(local_origin, local_direction)
    if hit:
        world_location = eval_obj.matrix_world @ location
        print(float(world_location.z))
    else:
        print(0.0)
""".strip()

    def _extract_execute_code_output(result: Any) -> str:
        output = ""
        if isinstance(result, dict):
            if result.get("output") is not None:
                output = str(result.get("output", ""))
            elif isinstance(result.get("result"), dict):
                output = str(result.get("result", {}).get("output", ""))
        elif result is not None:
            output = str(result)
        return output

    try:
        result = await blender.send_command("execute_code", {"code": code})
        output = _extract_execute_code_output(result).strip()
        return float(output.splitlines()[-1]) if output else 0.0
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        ConnectionError,
        OSError,
        BlenderCommandError,
    ) as exc:
        logger.debug(
            "Failed to query Blender location for terrain %s: %s",
            terrain_name,
            exc,
            exc_info=True,
        )
        return 0.0


async def _capture_current_terrain_heightmap_context(
    blender: BlenderConnection,
    terrain_name: str,
) -> dict[str, Any]:
    """Read the evaluated terrain mesh back into heightmap context."""
    if not re.match(r'^[A-Za-z0-9_\-. ]+$', terrain_name):
        raise ValueError(f"Invalid terrain_name rejected: {terrain_name}")

    code = f"""
import bpy
import json
import math

obj = bpy.data.objects.get({terrain_name!r})
if obj is None:
    print(json.dumps({{"error": "terrain object not found", "terrain_name": {terrain_name!r}}}))
else:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = None
    try:
        try:
            mesh = eval_obj.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        except TypeError:
            mesh = eval_obj.to_mesh()

        verts = list(getattr(mesh, "vertices", []) or [])
        if len(verts) < 4:
            print(json.dumps({{"error": "terrain mesh has insufficient vertices", "vertex_count": len(verts)}}))
        else:
            matrix_world = getattr(eval_obj, "matrix_world", None)
            points = []
            xs = []
            ys = []
            zs = []
            for vert in verts:
                point = vert.co
                if matrix_world is not None:
                    point = matrix_world @ point
                x = float(point.x)
                y = float(point.y)
                z = float(point.z)
                xs.append(x)
                ys.append(y)
                zs.append(z)
                points.append((x, y, z))

            rounded_xs = [round(x, 5) for x in xs]
            rounded_ys = [round(y, 5) for y in ys]
            unique_xs = sorted(set(rounded_xs))
            unique_ys = sorted(set(rounded_ys))
            cols = len(unique_xs)
            rows = len(unique_ys)

            heightmap = None
            if rows >= 2 and cols >= 2 and rows * cols == len(points):
                col_lookup = {{value: idx for idx, value in enumerate(unique_xs)}}
                row_lookup = {{value: idx for idx, value in enumerate(unique_ys)}}
                heightmap = [[0.0 for _ in range(cols)] for _ in range(rows)]
                for x, y, z in points:
                    row_idx = row_lookup[round(y, 5)]
                    col_idx = col_lookup[round(x, 5)]
                    heightmap[row_idx][col_idx] = z
            else:
                side = max(2, int(round(math.sqrt(len(points)))))
                if side * side != len(points):
                    print(json.dumps({{
                        "error": "terrain mesh is not a regular grid",
                        "vertex_count": len(points),
                        "rows": rows,
                        "cols": cols,
                    }}))
                    raise SystemExit(0)
                rows = side
                cols = side
                heightmap = []
                for row_idx in range(rows):
                    start = row_idx * cols
                    heightmap.append([
                        float(points[start + col_idx][2])
                        for col_idx in range(cols)
                    ])

            min_x = min(xs)
            max_x = max(xs)
            min_y = min(ys)
            max_y = max(ys)
            cell_size_x = (max_x - min_x) / max(cols - 1, 1)
            cell_size_y = (max_y - min_y) / max(rows - 1, 1)
            cell_size = max(cell_size_x, cell_size_y, 1e-6)

            print(json.dumps({{
                "heightmap": heightmap,
                "rows": rows,
                "cols": cols,
                "tile_size": max(rows - 1, cols - 1, 1),
                "cell_size": cell_size,
                "world_origin_x": min_x,
                "world_origin_y": min_y,
                "height_min": min(zs),
                "height_max": max(zs),
            }}))
    finally:
        if mesh is not None:
            try:
                eval_obj.to_mesh_clear()
            except Exception:
                pass
""".strip()

    raw = await blender.send_command("execute_code", {"code": code})
    output = ""
    if isinstance(raw, dict):
        if raw.get("output") is not None:
            output = str(raw.get("output", ""))
        elif isinstance(raw.get("result"), dict):
            output = str(raw.get("result", {}).get("output", ""))
    elif raw is not None:
        output = str(raw)
    output = output.strip()
    if not output:
        raise RuntimeError(
            f"Failed to read current terrain heightmap context for '{terrain_name}': empty execute_code output"
        )

    parsed: dict[str, Any] | None = None
    for candidate in reversed([line.strip() for line in output.splitlines() if line.strip()]):
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            parsed = loaded
            break
    if parsed is None:
        raise RuntimeError(
            f"Failed to parse current terrain heightmap context for '{terrain_name}': {output[:240]}"
        )
    if parsed.get("error"):
        raise RuntimeError(str(parsed.get("error")))

    heightmap = parsed.get("heightmap")
    if not isinstance(heightmap, list) or not heightmap:
        raise RuntimeError(
            f"Current terrain heightmap context for '{terrain_name}' did not include a usable heightmap"
        )

    return {
        "heightmap": heightmap,
        "tile_size": int(parsed.get("tile_size", max(len(heightmap) - 1, 1))),
        "cell_size": float(parsed.get("cell_size", 1.0)),
        "world_origin_x": float(parsed.get("world_origin_x", 0.0)),
        "world_origin_y": float(parsed.get("world_origin_y", 0.0)),
        "rows": int(parsed.get("rows", len(heightmap))),
        "cols": int(parsed.get("cols", len(heightmap[0]) if isinstance(heightmap[0], list) else len(heightmap))),
    }


async def _sample_terrain_relief_profile(
    blender: BlenderConnection,
    terrain_name: str,
    x: float,
    y: float,
    *,
    radius: float,
    sample_count: int = 8,
    fallback_vector: tuple[float, float] = (0.0, 1.0),
) -> dict[str, Any]:
    """Sample local terrain relief and return the strongest uphill direction."""
    center_height = await _sample_terrain_height(blender, terrain_name, x, y)
    sample_count = max(int(sample_count), 4)
    radius = max(float(radius), 1e-3)

    weighted_x = 0.0
    weighted_y = 0.0
    highest_height = center_height
    lowest_height = center_height
    samples: list[dict[str, float]] = []

    for index in range(sample_count):
        angle = (math.tau * index) / float(sample_count)
        sample_x = x + math.cos(angle) * radius
        sample_y = y + math.sin(angle) * radius
        sample_height = await _sample_terrain_height(blender, terrain_name, sample_x, sample_y)
        delta = sample_height - center_height
        weighted_x += math.cos(angle) * delta
        weighted_y += math.sin(angle) * delta
        highest_height = max(highest_height, sample_height)
        lowest_height = min(lowest_height, sample_height)
        samples.append({
            "x": float(sample_x),
            "y": float(sample_y),
            "height": float(sample_height),
        })

    uphill_length = math.hypot(weighted_x, weighted_y)
    if uphill_length <= 1e-6:
        fallback_x, fallback_y = fallback_vector
        fallback_length = math.hypot(fallback_x, fallback_y)
        if fallback_length <= 1e-6:
            fallback_x, fallback_y = 0.0, 1.0
            fallback_length = 1.0
        uphill_x = fallback_x / fallback_length
        uphill_y = fallback_y / fallback_length
    else:
        uphill_x = weighted_x / uphill_length
        uphill_y = weighted_y / uphill_length

    return {
        "center_height": float(center_height),
        "highest_height": float(highest_height),
        "lowest_height": float(lowest_height),
        "relief_span": float(highest_height - lowest_height),
        "uphill_vector": [float(uphill_x), float(uphill_y)],
        "downhill_vector": [float(-uphill_x), float(-uphill_y)],
        "samples": samples,
    }


async def _compute_natural_water_level(
    blender: BlenderConnection,
    terrain_name: str,
    basin_center_x: float,
    basin_center_y: float,
    basin_radius: float,
    *,
    terrain_size: float = 200.0,
    ring_sample_count: int = 16,
) -> dict[str, float]:
    """Sample terrain to compute a physically plausible water level.

    Returns a dict with:
      - basin_floor: lowest Z in the basin area
      - spill_height: lowest rim Z (water would overflow here)
      - natural_level: recommended water level between floor and spill
      - rim_min: minimum rim sample height
      - rim_max: maximum rim sample height
    """
    basin_center_x = float(basin_center_x)
    basin_center_y = float(basin_center_y)
    basin_radius = max(float(basin_radius), 4.0)
    ring_sample_count = max(int(ring_sample_count), 8)

    # --- Sample basin interior (radial grid) ---
    interior_heights: list[float] = []
    # Center point
    center_z = await _sample_terrain_height(blender, terrain_name, basin_center_x, basin_center_y)
    interior_heights.append(center_z)
    # Concentric rings at 33% and 66% of radius
    for fraction in (0.33, 0.66):
        ring_r = basin_radius * fraction
        for i in range(8):
            angle = (math.tau * i) / 8.0
            sx = basin_center_x + math.cos(angle) * ring_r
            sy = basin_center_y + math.sin(angle) * ring_r
            h = await _sample_terrain_height(blender, terrain_name, sx, sy)
            interior_heights.append(h)

    basin_floor = min(interior_heights) if interior_heights else center_z

    # --- Sample rim (ring at ~1.1x radius to find the spill point) ---
    rim_heights: list[float] = []
    rim_r = basin_radius * 1.15
    half_terrain = terrain_size * 0.5
    for i in range(ring_sample_count):
        angle = (math.tau * i) / float(ring_sample_count)
        rx = basin_center_x + math.cos(angle) * rim_r
        ry = basin_center_y + math.sin(angle) * rim_r
        # Clamp to terrain bounds
        rx = max(-half_terrain + 2.0, min(half_terrain - 2.0, rx))
        ry = max(-half_terrain + 2.0, min(half_terrain - 2.0, ry))
        h = await _sample_terrain_height(blender, terrain_name, rx, ry)
        rim_heights.append(h)

    if not rim_heights:
        # Fallback: use center_z as both floor and rim
        return {
            "basin_floor": basin_floor,
            "spill_height": center_z,
            "natural_level": center_z,
            "rim_min": center_z,
            "rim_max": center_z,
        }

    rim_min = min(rim_heights)
    rim_max = max(rim_heights)
    spill_height = rim_min  # Water spills at the lowest rim point

    # Natural water level: 70% between floor and spill height
    # (water fills most of the depression but doesn't overflow)
    if spill_height > basin_floor:
        natural_level = basin_floor + (spill_height - basin_floor) * 0.70
    else:
        # Rim is at or below basin floor -- flat terrain, use floor + small offset
        natural_level = basin_floor + 0.3

    return {
        "basin_floor": float(basin_floor),
        "spill_height": float(spill_height),
        "natural_level": float(natural_level),
        "rim_min": float(rim_min),
        "rim_max": float(rim_max),
    }


async def _shape_hero_cave_ridge(
    blender: BlenderConnection,
    terrain_name: str,
    *,
    cave_name: str,
    anchor_x: float,
    anchor_y: float,
    loc_radius: float,
    entrance_width: float,
    entrance_height: float,
    terrain_location: tuple[float, float],
) -> dict[str, Any]:
    """Raise a short ridge/cliff lip to give the cave a readable mountain face."""
    fallback_x = anchor_x - float(terrain_location[0])
    fallback_y = anchor_y - float(terrain_location[1])
    relief = await _sample_terrain_relief_profile(
        blender,
        terrain_name,
        anchor_x,
        anchor_y,
        radius=max(entrance_width * 0.72, loc_radius * 0.55, 9.0),
        sample_count=8,
        fallback_vector=(fallback_x, fallback_y),
    )
    uphill_x, uphill_y = relief["uphill_vector"]
    perp_x, perp_y = -uphill_y, uphill_x
    ridge_offset = max(entrance_width * 0.82, loc_radius * 0.40, 5.2)
    ridge_span = max(entrance_width * 2.9, loc_radius * 1.32, 14.0)
    ridge_height = max(2.2, entrance_height * 0.44, relief["relief_span"] * 0.18)
    ridge_height = min(ridge_height, max(entrance_height * 1.05, loc_radius * 0.30, 10.0))
    ridge_center_x = anchor_x + uphill_x * ridge_offset
    ridge_center_y = anchor_y + uphill_y * ridge_offset

    await blender.send_command("terrain_spline_deform", {
        "object_name": terrain_name,
        "spline_points": [
            [
                ridge_center_x - perp_x * ridge_span * 0.48,
                ridge_center_y - perp_y * ridge_span * 0.48,
                relief["center_height"] + ridge_height * 0.45,
            ],
            [
                ridge_center_x,
                ridge_center_y,
                relief["center_height"] + ridge_height,
            ],
            [
                ridge_center_x + perp_x * ridge_span * 0.48,
                ridge_center_y + perp_y * ridge_span * 0.48,
                relief["center_height"] + ridge_height * 0.45,
            ],
        ],
        "mode": "raise",
        "falloff": 0.78,
        "width": max(ridge_span * 0.74, entrance_width * 1.34),
        "depth": max(ridge_height, 0.85),
        "samples_per_segment": 12,
    })

    ridge_crest_height = await _sample_terrain_height(blender, terrain_name, ridge_center_x, ridge_center_y)
    minimum_target = relief["center_height"] + max(0.35, min(ridge_height * 0.36, 1.4))
    if ridge_crest_height < minimum_target and relief["relief_span"] < max(entrance_height * 0.48, 2.4):
        raise RuntimeError(f"{cave_name}: ridge shaping did not raise the terrain enough")

    relief["ridge_center"] = [float(ridge_center_x), float(ridge_center_y)]
    relief["ridge_crest_height"] = float(ridge_crest_height)
    return relief


async def _temper_hero_peak_outliers(
    blender: BlenderConnection,
    terrain_name: str,
    *,
    percentile: float = 0.992,
    blend: float = 0.76,
    prominence_threshold: float = 5.5,
    passes: int = 2,
) -> dict[str, Any]:
    """Pull isolated terrain spikes back toward local neighborhood height.

    This runs inside Blender via ``execute_code`` so it can operate on the
    current live terrain mesh without requiring a dedicated addon handler.
    It tempers both isolated positive spikes and isolated negative pits.
    """
    percentile = max(0.90, min(float(percentile), 0.9995))
    blend = max(0.05, min(float(blend), 0.98))
    prominence_threshold = max(float(prominence_threshold), 0.25)
    passes = max(1, min(int(passes), 5))

    code = f"""
import bpy, json
obj = bpy.data.objects.get({terrain_name!r})
if obj is None or getattr(obj, "type", "") != "MESH":
    raise ValueError("Terrain mesh not found: " + {terrain_name!r})
mesh = obj.data
mesh.calc_loop_triangles()
neighbor_map = [set() for _ in mesh.vertices]
for poly in mesh.polygons:
    verts = list(poly.vertices)
    count = len(verts)
    for idx, vert_index in enumerate(verts):
        neighbor_map[vert_index].add(verts[(idx - 1) % count])
        neighbor_map[vert_index].add(verts[(idx + 1) % count])
expanded_neighbor_map = []
for index, neighbors in enumerate(neighbor_map):
    expanded = set(neighbors)
    for neighbor_index in tuple(neighbors):
        expanded.update(neighbor_map[neighbor_index])
    expanded.discard(index)
    expanded_neighbor_map.append(expanded)
affected_total = 0
threshold_value = None
threshold_low = None
for _ in range({passes}):
    heights = [float(v.co.z) for v in mesh.vertices]
    if not heights:
        break
    ordered = sorted(heights)
    pos = (len(ordered) - 1) * {percentile}
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    t = pos - lo
    threshold_value = ordered[lo] * (1.0 - t) + ordered[hi] * t
    low_pos = (len(ordered) - 1) * (1.0 - {percentile})
    low_lo = int(low_pos)
    low_hi = min(low_lo + 1, len(ordered) - 1)
    low_t = low_pos - low_lo
    threshold_low = ordered[low_lo] * (1.0 - low_t) + ordered[low_hi] * low_t
    pending = {{}}
    for index, vert in enumerate(mesh.vertices):
        current_z = float(vert.co.z)
        neighbors = expanded_neighbor_map[index] or neighbor_map[index]
        if not neighbors:
            continue
        neighbor_heights = [float(mesh.vertices[n].co.z) for n in neighbors]
        ordered_neighbors = sorted(neighbor_heights)
        local_mean = sum(neighbor_heights) / len(neighbor_heights)
        local_median = ordered_neighbors[len(ordered_neighbors) // 2]
        local_max = max(neighbor_heights)
        local_min = min(neighbor_heights)
        prominence = current_z - local_median
        if current_z > threshold_value:
            if prominence < {prominence_threshold} or current_z <= local_max + {prominence_threshold} * 0.35:
                continue
            pending[index] = local_median + prominence * (1.0 - {blend})
            continue
        if current_z < threshold_low:
            pit_depth = local_median - current_z
            if pit_depth < {prominence_threshold} or current_z >= local_min - {prominence_threshold} * 0.55:
                continue
            pending[index] = local_median - pit_depth * (1.0 - {blend})
    if not pending:
        break
    for index, new_z in pending.items():
        mesh.vertices[index].co.z = new_z
    affected_total += len(pending)
mesh.update()
print(json.dumps({{"affected_vertices": affected_total, "threshold_z": threshold_value, "threshold_low_z": threshold_low}}))
"""
    raw = await blender.send_command("execute_code", {"code": code})
    output = raw.get("output") if isinstance(raw, dict) else raw
    if isinstance(output, str) and output.strip():
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {
        "affected_vertices": 0,
        "threshold_z": None,
    }


async def _stabilize_hero_terrain_patch(
    blender: BlenderConnection,
    terrain_name: str,
    *,
    center_x: float,
    center_y: float,
    radius: float,
    floor_z: float | None = None,
    ceiling_z: float | None = None,
    blend: float = 0.82,
) -> dict[str, Any]:
    """Clamp catastrophic local terrain outliers inside a hero-feature patch."""
    radius = max(float(radius), 0.5)
    blend = max(0.05, min(float(blend), 1.0))
    floor_expr = "None" if floor_z is None else repr(float(floor_z))
    ceiling_expr = "None" if ceiling_z is None else repr(float(ceiling_z))
    code = f"""
import bpy, json, math

def _smoothstep(value):
    x = max(0.0, min(1.0, float(value)))
    return x * x * (3.0 - 2.0 * x)

obj = bpy.data.objects.get({terrain_name!r})
if obj is None or getattr(obj, "type", "") != "MESH":
    raise ValueError("Terrain mesh not found: " + {terrain_name!r})

floor_z = {floor_expr}
ceiling_z = {ceiling_expr}
center_x = float({float(center_x)!r})
center_y = float({float(center_y)!r})
radius = float({radius!r})
blend = float({blend!r})

affected = 0
min_before = None
max_before = None
min_after = None
max_after = None
for vert in obj.data.vertices:
    world = obj.matrix_world @ vert.co
    dx = float(world.x) - center_x
    dy = float(world.y) - center_y
    dist = math.hypot(dx, dy)
    if dist > radius:
        continue
    falloff = 1.0 - _smoothstep(dist / max(radius, 1e-6))
    current_z = float(vert.co.z)
    target_z = current_z
    if floor_z is not None and current_z < floor_z:
        target_z = max(target_z, floor_z + (current_z - floor_z) * (1.0 - blend * falloff))
    if ceiling_z is not None and target_z > ceiling_z:
        target_z = min(target_z, ceiling_z + (target_z - ceiling_z) * (1.0 - blend * falloff))
    if abs(target_z - current_z) <= 1e-6:
        continue
    min_before = current_z if min_before is None else min(min_before, current_z)
    max_before = current_z if max_before is None else max(max_before, current_z)
    vert.co.z = target_z
    min_after = target_z if min_after is None else min(min_after, target_z)
    max_after = target_z if max_after is None else max(max_after, target_z)
    affected += 1

obj.data.update()
print(json.dumps({{
    "affected_vertices": affected,
    "min_before_z": min_before,
    "max_before_z": max_before,
    "min_after_z": min_after,
    "max_after_z": max_after,
}}))
"""
    raw = await blender.send_command("execute_code", {"code": code})
    output = raw.get("output") if isinstance(raw, dict) else raw
    if isinstance(output, str) and output.strip():
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"affected_vertices": 0}


async def _position_generated_object(
    blender: BlenderConnection,
    object_name: str,
    position: tuple[float, float, float],
) -> None:
    """Move a generated object/root to a target position if it exists."""
    await blender.send_command("modify_object", {
        "name": object_name,
        "position": [float(position[0]), float(position[1]), float(position[2])],
    })


@mcp.tool()
async def blender_scene(
    action: Literal["inspect", "clear", "configure", "list_objects", "save_project", "verify_project_save"],
    render_engine: str | None = None,
    fps: int | None = None,
    unit_scale: float | None = None,
    filepath: str | None = None,
    incremental: bool = False,
    copy: bool = False,
    compress: bool = True,
    verify: bool = True,
    compute_hash: bool = False,
    expect_current_file: bool = False,
):
    """Manage Blender scene state."""
    blender = get_blender_connection()
    if action == "inspect":
        result = await blender.send_command("get_scene_info")
        return json.dumps(result, indent=2, default=str)
    elif action == "clear":
        result = await blender.send_command("clear_scene")
        return await _with_screenshot(blender, result)
    elif action == "configure":
        params = {}
        if render_engine is not None:
            params["render_engine"] = render_engine
        if fps is not None:
            params["fps"] = fps
        if unit_scale is not None:
            params["unit_scale"] = unit_scale
        result = await blender.send_command("configure_scene", params)
        return await _with_screenshot(blender, result)
    elif action == "list_objects":
        result = await blender.send_command("list_objects")
        return json.dumps(result, indent=2, default=str)
    elif action == "save_project":
        params = {
            "incremental": incremental,
            "copy": copy,
            "compress": compress,
            "verify": verify,
            "compute_hash": compute_hash,
        }
        if filepath is not None:
            params["filepath"] = filepath
        result = await blender.send_command("save_project", params)
        return json.dumps(result, indent=2, default=str)
    elif action == "verify_project_save":
        params = {
            "compute_hash": compute_hash,
            "expect_current_file": expect_current_file,
        }
        if filepath is not None:
            params["filepath"] = filepath
        result = await blender.send_command("verify_project_save", params)
        return json.dumps(result, indent=2, default=str)
    return "Unknown action"


@mcp.tool()
async def blender_object(
    action: Literal["create", "modify", "delete", "duplicate", "list"],
    name: str | None = None,
    mesh_type: str | None = None,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    scale: list[float] | None = None,
    capture_viewport: bool = True
):
    """Manage Blender objects with visual verification."""
    blender = get_blender_connection()

    if action == "list":
        # Alias for blender_scene list_objects — kept for convenience
        result = await blender.send_command("list_objects")
        return json.dumps(result, indent=2, default=str)

    if action in ("modify", "delete", "duplicate") and not name:
        return f"ERROR: 'name' is required for action '{action}'"
    if action == "create" and not mesh_type:
        return "ERROR: 'mesh_type' is required for action 'create'"

    params = {}
    if name is not None:
        params["name"] = name
    if mesh_type is not None:
        params["mesh_type"] = mesh_type
    if position is not None:
        params["position"] = position
    if rotation is not None:
        params["rotation"] = rotation
    if scale is not None:
        params["scale"] = scale

    cmd_map = {
        "create": "create_object",
        "modify": "modify_object",
        "delete": "delete_object",
        "duplicate": "duplicate_object",
    }
    result = await blender.send_command(cmd_map[action], params)
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_material(
    action: Literal[
        "create", "assign", "modify", "list",
        "create_procedural", "list_presets",
    ],
    name: str | None = None,
    object_name: str | None = None,
    material_key: str | None = None,
    base_color: list[float] | None = None,
    metallic: float | None = None,
    roughness: float | None = None,
    capture_viewport: bool = True
):
    """Manage Blender materials, including procedural AAA preset graphs."""
    blender = get_blender_connection()

    if action == "list":
        result = await blender.send_command("material_list")
        return json.dumps(result, indent=2, default=str)

    if action == "list_presets":
        result = await blender.send_command(
            "material_create_procedural", {"list_available": True}
        )
        return json.dumps(result, indent=2, default=str)

    if action == "create_procedural":
        if not material_key:
            return "ERROR: 'material_key' is required for action 'create_procedural'"
        params = {"material_key": material_key}
        if name is not None:
            params["name"] = name
        if object_name is not None:
            params["object_name"] = object_name
        result = await blender.send_command("material_create_procedural", params)
        return await _with_screenshot(blender, result, capture_viewport)

    if action == "assign" and (not name or not object_name):
        return "ERROR: 'name' and 'object_name' are required for action 'assign'"
    if action in ("modify",) and not name:
        return "ERROR: 'name' is required for action 'modify'"

    params = {}
    if name is not None:
        params["name"] = name
    if object_name is not None:
        params["object_name"] = object_name
    if base_color is not None:
        params["base_color"] = base_color
    if metallic is not None:
        params["metallic"] = metallic
    if roughness is not None:
        params["roughness"] = roughness

    cmd_map = {
        "create": "material_create",
        "assign": "material_assign",
        "modify": "material_modify",
    }
    result = await blender.send_command(cmd_map[action], params)
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_viewport(
    action: Literal[
        "screenshot", "contact_sheet", "set_shading", "navigate",
        "interior_shot", "quick_preview", "orthographic_views",
    ],
    object_name: str | None = None,
    shading_type: str | None = None,
    camera_position: list[float] | None = None,
    camera_target: list[float] | None = None,
    angles: list[list[float]] | None = None,
    resolution: list[int] | None = None,
    max_size: int = 1024,
    room_bounds: list[float] | None = None,
):
    """Visual verification and viewport control.

    action=interior_shot  -- Eye-height (1.7 m) interior camera; supply room_bounds
                             as [min_x, min_y, min_z, max_x, max_y, max_z].
    action=quick_preview  -- Fast 256 px preview screenshot, no beauty setup.
    action=orthographic_views -- Four orthographic shots (front/right/top/iso).
    """
    blender = get_blender_connection()

    if action == "screenshot":
        screenshot_bytes = await blender.capture_viewport_bytes()
        resized = resize_screenshot(screenshot_bytes, max_size=max_size)
        return Image(data=resized, format="png")

    elif action == "contact_sheet":
        if not object_name:
            return "ERROR: 'object_name' is required for contact_sheet"
        params = {"object_name": object_name}
        if angles is not None:
            params["angles"] = angles
        if resolution is not None:
            params["resolution"] = resolution
        result = await blender.send_command("render_contact_sheet", params)
        paths = result.get("paths", [])
        if paths:
            try:
                sheet_bytes = compose_contact_sheet(paths)
                return Image(data=sheet_bytes, format="png")
            finally:
                for p in paths:
                    try:
                        os.unlink(p)
                    except OSError as exc:
                        logger.debug("Failed to delete contact sheet temp file %s: %s", p, exc, exc_info=True)
        return "No images rendered for contact sheet"

    elif action == "set_shading":
        if not shading_type:
            return "ERROR: 'shading_type' is required for set_shading"
        result = await blender.send_command(
            "set_shading", {"shading_type": shading_type}
        )
        return await _with_screenshot(blender, result)

    elif action == "navigate":
        if not camera_position or not camera_target:
            return "ERROR: 'camera_position' and 'camera_target' are required for navigate"
        result = await blender.send_command("navigate_camera", {
            "position": camera_position,
            "target": camera_target,
        })
        return await _with_screenshot(blender, result)

    elif action == "interior_shot":
        # Eye-height camera positioned inside room bounds
        if not object_name and not room_bounds:
            return "ERROR: 'object_name' or 'room_bounds' is required for interior_shot"
        result = await blender.send_command("interior_camera_shot", {
            "object_name": object_name,
            "room_bounds": room_bounds,
            "eye_height": 1.7,
        })
        parts: list = [json.dumps(result, indent=2, default=str)]
        try:
            screenshot_bytes = await blender.capture_viewport_bytes()
            resized = resize_screenshot(screenshot_bytes, max_size=max_size)
            parts.append(Image(data=resized, format="png"))
        except (OSError, IOError, BlenderCommandError, ConnectionError) as e:
            parts.append(f"[Screenshot capture failed: {e}]")
        return parts

    elif action == "quick_preview":
        # Fast 256 px preview — no beauty setup, minimal overhead
        parts = []
        try:
            screenshot_bytes = await blender.capture_viewport_bytes()
            resized = resize_screenshot(screenshot_bytes, max_size=256)
            parts.append(Image(data=resized, format="png"))
        except (OSError, IOError, BlenderCommandError, ConnectionError) as e:
            parts.append(f"[Screenshot capture failed: {e}]")
        return parts

    elif action == "orthographic_views":
        # Four orthographic renders: front / right / top / isometric
        if not object_name:
            return "ERROR: 'object_name' is required for orthographic_views"
        result = await blender.send_command("render_orthographic_views", {
            "object_name": object_name,
            "resolution": resolution or [512, 512],
        })
        paths = result.get("paths", [])
        if paths:
            try:
                sheet_bytes = compose_contact_sheet(paths)
                return Image(data=sheet_bytes, format="png")
            finally:
                for p in paths:
                    try:
                        os.unlink(p)
                    except OSError as exc:
                        logger.debug("Failed to delete ortho temp file %s: %s", p, exc, exc_info=True)
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


@mcp.tool()
async def blender_execute(
    code: str,
    capture_viewport: bool = True,
):
    """Execute validated Python code in Blender."""
    is_safe, violations = validate_code(code)
    if not is_safe:
        return "SECURITY ERROR: Code validation failed:\n" + "\n".join(
            f"  - {v}" for v in violations
        )

    blender = get_blender_connection()
    result = await blender.send_command("execute_code", {"code": code})
    return await _with_screenshot(blender, result, capture_viewport)


@mcp.tool()
async def blender_export(
    export_format: Literal["fbx", "gltf"],
    filepath: str,
    selected_only: bool = False,
    apply_modifiers: bool = True,
) -> str:
    """Export scene or selection to game-ready format."""
    blender = get_blender_connection()
    cmd = f"export_{export_format}"
    result = await blender.send_command(cmd, {
        "filepath": filepath,
        "selected_only": selected_only,
        "apply_modifiers": apply_modifiers,
    })
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def blender_mesh(
    action: Literal[
        "analyze", "repair", "game_check",
        "select", "edit", "boolean", "retopo", "sculpt",
        "sculpt_brush", "dyntopo", "voxel_remesh", "face_sets", "multires",
        "enhance", "bake_normals", "bake_ao", "bake_curvature", "validate_enhance"
    ],
    object_name: str,
    # Existing params (analyze/repair/game_check)
    merge_distance: float = 0.0001,
    max_hole_sides: int = 8,
    poly_budget: int = 50000,
    platform: str = "pc",
    # Selection params
    material_index: int | None = None,
    material_name: str | None = None,
    vertex_group: str | None = None,
    face_normal_direction: list[float] | None = None,
    normal_threshold: float = 0.7,
    loose_parts: bool = False,
    # Position-based selection (GAP-01)
    position_box: dict | None = None,
    position_sphere: dict | None = None,
    position_plane: dict | None = None,
    # Edit params
    operation: str | None = None,
    offset: list[float] | None = None,
    thickness: float = 0.1,
    depth: float = 0.0,
    axis: str = "X",
    separate_type: str = "SELECTED",
    object_names: list[str] | None = None,
    # Transform params (GAP-02)
    angle: float = 0.0,
    center: list[float] | None = None,
    factor: list[float] | float | None = None,
    # Loop cut params (GAP-03)
    edge_index: int | None = None,
    cuts: int = 1,
    # Bevel params (GAP-04)
    width: float = 0.1,
    segments: int = 1,
    profile: float = 0.5,
    clamp_overlap: bool = True,
    # Merge/dissolve params (GAP-05)
    merge_type: str = "CENTER",
    # Boolean params
    cutter_name: str | None = None,
    remove_cutter: bool = True,
    # Retopo params
    target_faces: int = 4000,
    preserve_sharp: bool = True,
    preserve_boundary: bool = True,
    smooth_normals: bool = True,
    use_symmetry: bool = False,
    seed: int = 0,
    # Sculpt params
    strength: float = 0.5,
    iterations: int = 3,
    # Sculpt brush params (sculpt_brush action)
    brush_type: str | None = None,
    radius: float = 50,
    stroke_points: list[list[float]] | None = None,
    use_front_faces_only: bool = False,
    direction: str = "ADD",
    # Dyntopo params (dyntopo action)
    detail_size: float = 12.0,
    detail_mode: str = "RELATIVE_DETAIL",
    # Voxel remesh params (voxel_remesh action)
    voxel_size: float = 0.05,
    adaptivity: float = 0.0,
    # Multires params (multires action)
    subdivisions: int = 1,
    # Enhance params (enhance action) -- AAA geometry enhancement pipeline
    enhance_profile: str = "prop",
    subdiv_levels: int | None = None,
    render_levels: int | None = None,
    bevel_width_override: float | None = None,
    bevel_segments_override: int | None = None,
    sharp_angle: float | None = None,
    crease_value: float | None = None,
    displacement_strength: float | None = None,
    apply_modifiers: bool = False,
    skip_steps: list[str] | None = None,
    # Bake normals params (bake_normals action)
    image_size: int = 2048,
    cage_extrusion: float = 0.02,
    output_name: str | None = None,
    capture_viewport: bool = True
):
    """Mesh topology analysis, repair, editing, booleans, retopology, sculpting, and AAA enhancement.

    Extended with position-based selection (GAP-01), transform operations (GAP-02),
    loop cuts (GAP-03), bevel (GAP-04), merge/dissolve (GAP-05), advanced
    sculpt operations: sculpt_brush (32 brush types), dyntopo (dynamic topology),
    voxel_remesh, face_sets, multires (multiresolution modifier), and AAA geometry
    enhancement pipeline (enhance, bake_normals).
    """
    blender = get_blender_connection()

    if action == "analyze":
        result = await blender.send_command(
            "mesh_analyze_topology", {"object_name": object_name}
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "repair":
        result = await blender.send_command(
            "mesh_auto_repair",
            {
                "object_name": object_name,
                "merge_distance": merge_distance,
                "max_hole_sides": max_hole_sides,
            },
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "game_check":
        result = await blender.send_command(
            "mesh_check_game_ready",
            {
                "object_name": object_name,
                "poly_budget": poly_budget,
                "platform": platform,
            },
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "select":
        params: dict = {"object_name": object_name}
        if material_index is not None:
            params["material_index"] = material_index
        if material_name is not None:
            params["material_name"] = material_name
        if vertex_group is not None:
            params["vertex_group"] = vertex_group
        if face_normal_direction is not None:
            params["face_normal_direction"] = face_normal_direction
            params["normal_threshold"] = normal_threshold
        if loose_parts:
            params["loose_parts"] = loose_parts
        # Position-based selection (GAP-01)
        if position_box is not None:
            params["position_box"] = position_box
        if position_sphere is not None:
            params["position_sphere"] = position_sphere
        if position_plane is not None:
            params["position_plane"] = position_plane
        result = await blender.send_command("mesh_select", params)
        return [json.dumps(result, indent=2, default=str)]

    elif action == "edit":
        params = {"object_name": object_name}
        if operation is not None:
            params["operation"] = operation
        if offset is not None:
            params["offset"] = offset
        params["thickness"] = thickness
        params["depth"] = depth
        params["axis"] = axis
        params["separate_type"] = separate_type
        if object_names is not None:
            params["object_names"] = object_names
        # Transform params (GAP-02)
        params["angle"] = angle
        if center is not None:
            params["center"] = center
        if factor is not None:
            params["factor"] = factor
        # Loop cut params (GAP-03)
        if edge_index is not None:
            params["edge_index"] = edge_index
        params["cuts"] = cuts
        # Bevel params (GAP-04)
        params["width"] = width
        params["segments"] = segments
        params["profile"] = profile
        params["clamp_overlap"] = clamp_overlap
        # Merge/dissolve params (GAP-05)
        params["merge_type"] = merge_type
        result = await blender.send_command("mesh_edit", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "boolean":
        params = {
            "object_name": object_name,
            "operation": operation or "DIFFERENCE",
            "remove_cutter": remove_cutter,
        }
        if cutter_name is not None:
            params["cutter_name"] = cutter_name
        result = await blender.send_command("mesh_boolean", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retopo":
        result = await blender.send_command(
            "mesh_retopologize",
            {
                "object_name": object_name,
                "target_faces": target_faces,
                "preserve_sharp": preserve_sharp,
                "preserve_boundary": preserve_boundary,
                "smooth_normals": smooth_normals,
                "use_symmetry": use_symmetry,
                "seed": seed,
            },
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "sculpt":
        params = {
            "object_name": object_name,
            "strength": strength,
            "iterations": iterations,
        }
        if operation is not None:
            params["operation"] = operation
        result = await blender.send_command("mesh_sculpt", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "sculpt_brush":
        params = {
            "object_name": object_name,
            "strength": strength,
            "radius": radius,
            "use_front_faces_only": use_front_faces_only,
            "direction": direction,
        }
        if brush_type is not None:
            params["brush_type"] = brush_type
        if stroke_points is not None:
            params["stroke_points"] = stroke_points
        result = await blender.send_command("mesh_sculpt_brush", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "dyntopo":
        params = {
            "object_name": object_name,
            "detail_size": detail_size,
            "detail_mode": detail_mode,
        }
        if operation is not None:
            params["action"] = operation
        result = await blender.send_command("mesh_dyntopo", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "voxel_remesh":
        result = await blender.send_command(
            "mesh_voxel_remesh",
            {
                "object_name": object_name,
                "voxel_size": voxel_size,
                "adaptivity": adaptivity,
            },
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "face_sets":
        params = {"object_name": object_name}
        if operation is not None:
            params["action"] = operation
        result = await blender.send_command("mesh_face_sets", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "multires":
        params = {
            "object_name": object_name,
            "subdivisions": subdivisions,
        }
        if operation is not None:
            params["action"] = operation
        result = await blender.send_command("mesh_multires", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "enhance":
        params = {"object_name": object_name, "profile": enhance_profile}
        if subdiv_levels is not None:
            params["subdiv_levels"] = subdiv_levels
        if render_levels is not None:
            params["render_levels"] = render_levels
        if bevel_width_override is not None:
            params["bevel_width"] = bevel_width_override
        if bevel_segments_override is not None:
            params["bevel_segments"] = bevel_segments_override
        if sharp_angle is not None:
            params["sharp_angle"] = sharp_angle
        if crease_value is not None:
            params["crease_value"] = crease_value
        if displacement_strength is not None:
            params["displacement_strength"] = displacement_strength
        params["apply_modifiers"] = apply_modifiers
        if skip_steps is not None:
            params["skip_steps"] = skip_steps
        result = await blender.send_command("mesh_enhance_geometry", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "bake_normals":
        params = {
            "object_name": object_name,
            "image_size": image_size,
            "cage_extrusion": cage_extrusion,
        }
        if output_name is not None:
            params["output_name"] = output_name
        result = await blender.send_command("mesh_bake_detail_normals", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "bake_ao":
        params = {
            "object_name": object_name,
            "image_size": image_size,
        }
        if output_name is not None:
            params["output_name"] = output_name
        result = await blender.send_command("mesh_bake_ao_map", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "bake_curvature":
        params = {
            "object_name": object_name,
            "image_size": image_size,
        }
        if output_name is not None:
            params["output_name"] = output_name
        result = await blender.send_command("mesh_bake_curvature_map", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "validate_enhance":
        result = await blender.send_command(
            "mesh_validate_enhancement", {"object_name": object_name}
        )
        return [json.dumps(result, indent=2, default=str)]

    return ["Unknown action"]


@mcp.tool()
async def blender_uv(
    action: Literal[
        "analyze",
        "unwrap",
        "unwrap_blender",
        "pack",
        "lightmap",
        "equalize",
        "export_layout",
        "set_layer",
        "ensure_xatlas",
    ],
    object_name: str | None = None,
    texture_size: int = 1024,
    padding: int = 4,
    resolution: int = 1024,
    margin: float = 0.001,
    layer_name: str | None = None,
    method: str = "smart_project",
    angle_limit: float = 66.0,
    max_chart_area: float | None = None,
    normal_deviation_weight: float | None = None,
    max_iterations: int | None = None,
    rotate_charts: bool = True,
    target_density: float | None = None,
    size: int = 1024,
    opacity: float = 0.25,
    capture_viewport: bool = True
):
    """UV mapping analysis, unwrapping, packing, and optimization."""
    blender = get_blender_connection()

    if action == "analyze":
        result = await blender.send_command(
            "uv_analyze",
            {"object_name": object_name, "texture_size": texture_size},
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "unwrap":
        params = {
            "object_name": object_name,
            "padding": padding,
            "resolution": resolution,
            "rotate_charts": rotate_charts,
        }
        if max_chart_area is not None:
            params["max_chart_area"] = max_chart_area
        if normal_deviation_weight is not None:
            params["normal_deviation_weight"] = normal_deviation_weight
        if max_iterations is not None:
            params["max_iterations"] = max_iterations
        result = await blender.send_command("uv_unwrap_xatlas", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "unwrap_blender":
        result = await blender.send_command(
            "uv_unwrap_blender",
            {"object_name": object_name, "method": method, "angle_limit": angle_limit},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "pack":
        result = await blender.send_command(
            "uv_pack_islands",
            {"object_name": object_name, "margin": margin},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "lightmap":
        result = await blender.send_command(
            "uv_generate_lightmap",
            {"object_name": object_name, "padding": padding, "resolution": resolution},
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "equalize":
        params_eq: dict = {
            "object_name": object_name,
            "texture_size": texture_size,
        }
        if target_density is not None:
            params_eq["target_density"] = target_density
        result = await blender.send_command("uv_equalize_density", params_eq)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "export_layout":
        result = await blender.send_command(
            "uv_export_layout",
            {"object_name": object_name, "size": size, "opacity": opacity},
        )
        filepath = result.get("filepath")
        if filepath and os.path.isfile(filepath):
            try:
                with open(filepath, "rb") as f:
                    image_data = f.read()
                return [
                    json.dumps(result, indent=2, default=str),
                    Image(data=image_data, format="png"),
                ]
            finally:
                try:
                    os.unlink(filepath)
                except OSError as exc:
                    logger.debug("Failed to delete temp UV layout file %s: %s", filepath, exc, exc_info=True)
        return [json.dumps(result, indent=2, default=str)]

    elif action == "set_layer":
        result = await blender.send_command(
            "uv_set_active_layer",
            {"object_name": object_name, "layer_name": layer_name},
        )
        return [json.dumps(result, indent=2, default=str)]

    elif action == "ensure_xatlas":
        result = await blender.send_command("uv_ensure_xatlas", {})
        return [json.dumps(result, indent=2, default=str)]

    return ["Unknown action"]


# ---------------------------------------------------------------------------
# Compound tool: blender_texture
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_texture(
    action: Literal[
        "create_pbr", "mask_region", "inpaint", "hsv_adjust",
        "blend_seams", "generate_wear", "bake", "upscale",
        "make_tileable", "validate", "delight", "validate_palette",
        "load_extracted_textures", "mix_weathering_over_texture",
    ],
    object_name: str | None = None,
    # PBR creation params
    name: str | None = None,
    texture_dir: str | None = None,
    texture_size: int = 1024,
    # Mask / HSV / blend params
    image_path: str | None = None,
    mask_path: str | None = None,
    material_index: int = 0,
    feather_radius: int = 5,
    hue_shift: float = 0.0,
    saturation_scale: float = 1.0,
    value_scale: float = 1.0,
    blend_radius: int = 6,
    # Inpaint params
    prompt: str | None = None,
    # Bake params
    bake_type: str = "COMBINED",
    source_object: str | None = None,
    image_name: str | None = None,
    margin: int = 16,
    cage_extrusion: float = 0.1,
    samples: int = 32,
    # Upscale params
    scale: int = 4,
    model: str = "realesrgan-x4plus",
    output_path: str | None = None,
    # Tileable params
    overlap_pct: float = 0.15,
    # Delight params
    blur_radius_pct: float = 0.12,
    strength: float = 0.75,
    # Palette validation params
    rules: dict | None = None,
    sample_pixels: int = 10000,
    # Extracted texture params (load_extracted_textures)
    albedo_path: str | None = None,
    albedo_delit_path: str | None = None,
    normal_path: str | None = None,
    orm_path: str | None = None,
    # Weathering overlay params (mix_weathering_over_texture)
    weathering_strength: float = 0.4,
    capture_viewport: bool = True
):
    """Comprehensive texture operations -- Blender-side and MCP-side."""
    blender = get_blender_connection()

    if action == "create_pbr":
        params = {"name": name or "PBR_Material", "texture_size": texture_size}
        if texture_dir:
            params["texture_dir"] = texture_dir
        if object_name:
            params["object_name"] = object_name
        result = await blender.send_command("texture_create_pbr", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "mask_region":
        if not object_name:
            return "ERROR: 'object_name' is required for mask_region"
        # Get UV polygons from Blender for the material slot
        uv_result = await blender.send_command(
            "texture_get_uv_region",
            {"object_name": object_name, "material_index": material_index},
        )
        polygons = uv_result.get("polygons", [])
        mask_bytes = generate_uv_mask(polygons, texture_size, feather_radius)
        return [
            json.dumps({"polygons_count": len(polygons), "texture_size": texture_size}),
            Image(data=mask_bytes, format="png"),
        ]

    elif action == "inpaint":
        if not image_path or not mask_path:
            return "ERROR: 'image_path' and 'mask_path' are required for inpaint"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        with open(mask_path, "rb") as f:
            msk_bytes = f.read()
        result = inpaint_texture(img_bytes, msk_bytes, prompt or "", fal_key=settings.fal_key or None)
        # Save raw image bytes to a temp file so they don't pollute JSON
        if result.get("image_bytes"):
            import tempfile as _tmpfile
            tmp_dir = os.path.join(_tmpfile.gettempdir(), "vb_inpaint")
            os.makedirs(tmp_dir, exist_ok=True)
            out_path = os.path.join(tmp_dir, f"inpaint_{id(result)}.png")
            with open(out_path, "wb") as _f:
                _f.write(result["image_bytes"])
            result["image_path"] = out_path
            del result["image_bytes"]
        return json.dumps(result, indent=2, default=str)

    elif action == "hsv_adjust":
        if not image_path or not mask_path:
            return "ERROR: 'image_path' and 'mask_path' are required for hsv_adjust"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        with open(mask_path, "rb") as f:
            msk_bytes = f.read()
        result_bytes = apply_hsv_adjustment(
            img_bytes, msk_bytes, hue_shift, saturation_scale, value_scale,
        )
        return Image(data=result_bytes, format="png")

    elif action == "blend_seams":
        if not object_name or not image_path:
            return "ERROR: 'object_name' and 'image_path' are required for blend_seams"
        # Get seam pixels from Blender
        seam_result = await blender.send_command(
            "texture_get_seam_pixels",
            {"object_name": object_name, "texture_size": texture_size},
        )
        seam_pixels = [(p[0], p[1]) for p in seam_result.get("seam_pixels", [])]
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        result_bytes = blend_seams(img_bytes, seam_pixels, blend_radius)
        return Image(data=result_bytes, format="png")

    elif action == "generate_wear":
        if not object_name:
            return "ERROR: 'object_name' is required for generate_wear"
        wear_result = await blender.send_command(
            "texture_generate_wear", {"object_name": object_name},
        )
        curvature_data = {
            int(k): v for k, v in wear_result.get("curvature_data", {}).items()
        }
        uv_data = wear_result.get("uv_data")
        wear_bytes = render_wear_map(curvature_data, texture_size, uv_data)
        return [
            json.dumps({
                "object_name": object_name,
                "vertex_count": wear_result.get("vertex_count", 0),
                "texture_size": texture_size,
            }, indent=2, default=str),
            Image(data=wear_bytes, format="png"),
        ]

    elif action == "bake":
        if not object_name or not image_name:
            return "ERROR: 'object_name' and 'image_name' are required for bake"
        params = {
            "object_name": object_name,
            "bake_type": bake_type,
            "image_name": image_name,
            "margin": margin,
            "cage_extrusion": cage_extrusion,
            "samples": samples,
        }
        if source_object:
            params["source_object"] = source_object
        result = await blender.send_command("texture_bake", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "upscale":
        if not image_path:
            return "ERROR: 'image_path' is required for upscale"
        result = await upscale_texture(
            input_path=image_path,
            scale=scale,
            model=model,
            esrgan_path=settings.realesrgan_path,
            output_path=output_path,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "make_tileable":
        if not image_path:
            return "ERROR: 'image_path' is required for make_tileable"
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        result_bytes = make_tileable(img_bytes, overlap_pct)
        return Image(data=result_bytes, format="png")

    elif action == "validate":
        if image_path:
            result = validate_texture_file(image_path)
            return json.dumps(result, indent=2, default=str)
        elif object_name:
            result = await blender.send_command(
                "texture_validate", {"object_name": object_name},
            )
            return await _with_screenshot(blender, result, capture_viewport)
        return "ERROR: 'object_name' or 'image_path' is required for validate"

    elif action == "delight":
        if not image_path:
            return "ERROR: 'image_path' is required for delight"
        if not output_path:
            return "ERROR: 'output_path' is required for delight"
        result = delight_albedo(
            image_path=image_path,
            output_path=output_path,
            blur_radius_pct=blur_radius_pct,
            strength=strength,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "validate_palette":
        if not image_path:
            return "ERROR: 'image_path' is required for validate_palette"
        result = _validate_palette(
            image_path=image_path,
            rules=rules,
            sample_pixels=sample_pixels,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "load_extracted_textures":
        if not object_name:
            return "ERROR: 'object_name' is required for load_extracted_textures"
        if not albedo_path and not albedo_delit_path and not normal_path and not orm_path:
            return "ERROR: at least one texture path (albedo_path, albedo_delit_path, normal_path, orm_path) is required"
        params: dict = {"object_name": object_name}
        if albedo_delit_path:
            params["albedo_delit_path"] = albedo_delit_path
        elif albedo_path:
            params["albedo_path"] = albedo_path
        if normal_path:
            params["normal_path"] = normal_path
        if orm_path:
            params["orm_path"] = orm_path
        result = await blender.send_command("texture_load_extracted_textures", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "mix_weathering_over_texture":
        if not object_name:
            return "ERROR: 'object_name' is required for mix_weathering_over_texture"
        params = {
            "object_name": object_name,
            "weathering_strength": weathering_strength,
        }
        result = await blender.send_command("texture_mix_weathering_over_texture", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: asset_pipeline
# ---------------------------------------------------------------------------

@mcp.tool()
async def asset_pipeline(
    action: Literal[
        "generate_3d", "generate_building", "generate_terrain_mesh",
        "compose_map", "compose_interior",
        "cleanup", "generate_lods", "validate_export",
        "tag_metadata", "batch_process", "catalog_query", "catalog_add",
        "inspect_external_toolchain", "configure_external_toolchain",
        # Equipment operations (Phase 13 -- EQUIP-01/03/04/05)
        "generate_weapon", "split_character", "fit_armor", "render_equipment_icon",
        # Full production pipeline
        "full_pipeline", "generate_and_process",
        # Import local model files (GLB/FBX/OBJ) -- use with Tripo Studio downloads
        "import_model", "import_and_process",
        # Map packaging (Phase 37 -- MESH-16)
        "generate_map_package",
        # AAA visual verification (Phase 39 -- AAA-MAP-01)
        "aaa_verify",
        "screenshot_regression",
        # Performance budget check (Phase 39 -- AAA-MAP-10)
        "performance_check",
        # LOD chain generation (Phase 39 -- AAA-MAP-11)
        "generate_lod_chain",
        # Prop generation via Tripo (compose_map helper)
        "generate_prop",
    ],
    # Common params
    object_name: str | None = None,
    # generate_3d params
    prompt: str | None = None,
    image_path: str | None = None,
    output_dir: str = ".",
    # cleanup params
    poly_budget: int = 50000,
    # generate_lods params
    ratios: list[float] | None = None,
    # validate_export params
    filepath: str | None = None,
    # tag_metadata params
    asset_id: str | None = None,
    output_path: str | None = None,
    # batch_process params
    object_names: list[str] | None = None,
    steps: list[str] | None = None,
    # catalog params
    name: str | None = None,
    asset_type: str | None = None,
    path: str | None = None,
    tags: list[str] | None = None,
    status: str | None = None,
    # equipment params (Phase 13 -- EQUIP-01/03/04/05)
    weapon_type: str | None = None,
    weapon_style: str | None = None,    # style variant for generate_weapon
    weapon_length: float | None = None, # blade/shaft length for generate_weapon
    blade_width: float | None = None,   # blade/head width for generate_weapon
    material_name: str | None = None,   # material to assign for generate_weapon
    parts: list[str] | None = None,
    armor_object_name: str | None = None,
    character_object_name: str | None = None,
    resolution: int = 512,
    camera_distance: float = 2.0,
    camera_angle: str = "front",
    body_types: list[str] | None = None,
    # generate_building params -- architecture presets for Tripo
    building_type: str | None = None,  # tavern, castle, cathedral, tower, house, shop, ruin, gate, bridge, wall_section
    building_style: str = "dark_fantasy",  # dark_fantasy, gothic, medieval, elven, dwarven, corrupted
    building_size: str = "medium",  # small, medium, large, massive
    # generate_terrain_mesh params -- heightmap-to-mesh in Blender
    terrain_preset: str | None = None,  # mountains, hills, plains, canyon, volcanic, coastal, swamp
    terrain_size: float = 100.0,  # world units
    terrain_resolution: int = 128,  # subdivisions
    terrain_height_scale: float = 20.0,
    terrain_erosion: bool = True,
    terrain_seed: int = 42,
    # compose_map params -- full map orchestration
    map_spec: dict | None = None,
    # compose_interior params -- interior room orchestration
    interior_spec: dict | None = None,
    # full_pipeline / generate_and_process params
    material_preset: str = "auto",
    weathering_preset: str = "medium",
    rig_template: str = "auto",
    animations: list[str] | None = None,
    lod_count: int = 3,
    export_format: str = "fbx",
    export_dir: str | None = None,
    capture_viewport: bool = True,
    prefer_external: bool = True,
    review_lighting: bool = True,
    # Tripo post-processing params (for cleanup action after generate_3d)
    has_extracted_textures: bool = False,
    texture_channels: dict | None = None,
    # Pipeline checkpoint params (compose_map resume)
    checkpoint_dir: str | None = None,
    resume: bool = False,
    force_restart: bool = False,
    # Map package export params (generate_map_package)
    map_package_spec: dict | None = None,
    # AAA verification params (aaa_verify / screenshot_regression)
    angles: int = 10,
    min_score: int = 60,
    capture_baseline: bool = False,
    baseline_dir: str | None = None,
    current_screenshots: list[str] | None = None,
    validation_profile: str | None = None,
):
    """Asset pipeline -- 3D generation, map composition, interior building, processing, LODs, catalog, equipment. Use compose_map to build full maps (terrain+water+roads+locations+vegetation+atmosphere). Use compose_interior for walkable interiors (room shells+doors+furniture+props). Use generate_building for Tripo-powered architecture. Use generate_terrain_mesh for procedural terrain."""
    blender = get_blender_connection()

    if action == "generate_3d":
        if not prompt and not image_path:
            return "ERROR: 'prompt' or 'image_path' is required for generate_3d"

        # Route output to VB3DCurrent asset folder when asset_type is set
        _vb3d = settings.unity_project_path
        _asset_dirs = {
            "character": "Assets/Art/3D_Models/Characters",
            "monster": "Assets/Art/3D_Models/Monsters",
            "creature": "Assets/Art/3D_Models/Monsters",
            "prop": "Assets/Art/3D_Models/Props",
            "weapon": "Assets/Art/3D_Models/Weapons",
            "building": "Assets/Art/3D_Models/Props",
            "vegetation": "Assets/Art/3D_Models/Props",
        }
        if _vb3d and asset_type and asset_type in _asset_dirs:
            resolved_dir = str(
                Path(_vb3d) / _asset_dirs[asset_type]
            )
            # Use name subfolder if provided
            if name:
                resolved_dir = str(
                    Path(resolved_dir) / name
                )
            output_dir = resolved_dir
        elif output_dir == "." and _vb3d:
            # Fallback: use a known location inside the Unity project
            # so models don't get lost in the MCP server's CWD
            output_dir = str(
                Path(_vb3d) / "Assets/Art/3D_Models/Tripo_Downloads"
            )
            if name:
                output_dir = str(
                    Path(output_dir) / name
                )
        elif output_dir == ".":
            # Last resort: use temp dir with timestamp so models are findable
            import tempfile
            import time
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = str(
                Path(tempfile.gettempdir()) / f"tripo_models_{ts}"
            )

        # Prefer studio (uses subscription credits), fall back to API key
        studio_cookie = settings.tripo_session_cookie
        studio_token = settings.tripo_studio_token
        api_key = settings.tripo_api_key

        # STY-001: enforce dark fantasy style on all AI-generated assets
        _df_prefix = "dark fantasy medieval weathered Gothic, "
        if prompt and not prompt.startswith(_df_prefix):
            prompt = _df_prefix + prompt

        if studio_cookie or studio_token:
            from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
            gen = TripoStudioClient(
                session_cookie=studio_cookie,
                session_token=studio_token,
            )
            try:
                if image_path:
                    result = await gen.generate_from_image(image_path, output_dir)
                else:
                    result = await gen.generate_from_text(prompt, output_dir)
                result["output_dir"] = output_dir

                # Auto-import all downloaded variants into Blender in a grid
                models = result.get("models", [])
                verified = [m for m in models if m.get("verified")]
                result_warnings = result.setdefault("warnings", [])
                if verified:
                    spacing = 3.0
                    positions = [
                        (0, 0), (-spacing, 0),
                        (spacing, 0), (0, spacing),
                    ]
                    imported_names = []
                    for i, m in enumerate(verified):
                        px, py = positions[i % len(positions)]
                        safe = m["path"].replace("\\", "/").replace('"', '\\"')

                        # Post-process GLB: extract textures, delight, validate, score
                        glb_out_dir = str(
                            Path(m["path"]).parent
                            / f"variant_{i+1}_textures"
                        )
                        try:
                            post_result = await post_process_tripo_model(
                                m["path"], glb_out_dir,
                                asset_type=asset_type or "prop",
                            )
                            m["post_process"] = post_result
                            m["texture_channels"] = post_result.get("channels", {})
                            if post_result.get("albedo_delit"):
                                m["texture_channels"]["albedo_delit"] = post_result["albedo_delit"]
                            if post_result.get("warnings"):
                                result_warnings.extend(
                                    f"variant_{i + 1}_post_process: {warning}"
                                    for warning in post_result["warnings"]
                                )
                            if post_result.get("status") not in (None, "success"):
                                result["status"] = "partial"
                        except Exception as exc:
                            logger.warning("Post-process failed for variant %s: %s", i + 1, exc, exc_info=True)
                            result_warnings.append(f"variant_{i + 1}_post_process_failed: {exc}")
                            result["status"] = "partial"
                            m["texture_channels"] = {}

                        code = (
                            f'import bpy\n'
                            f'bpy.ops.object.select_all(action="DESELECT")\n'
                            f'existing = set(bpy.data.objects[:])\n'
                            f'bpy.ops.import_scene.gltf(filepath="{safe}", merge_vertices=True)\n'
                            f'new_objs = set(bpy.data.objects[:]) - existing\n'
                            f'for obj in new_objs:\n'
                            f'    obj.location.x += {px}\n'
                            f'    obj.location.y += {py}\n'
                            f'names = [o.name for o in new_objs if o.type == "MESH"]\n'
                            f'names'
                        )
                        try:
                            await blender.send_command(
                                "execute_code", {"code": code}
                            )
                            imported_names.append(f"variant_{i+1}")
                        except Exception as exc:
                            logger.warning(
                                "Failed to import variant %s into Blender: %s",
                                i + 1,
                                exc,
                                exc_info=True,
                            )
                            result_warnings.append(f"variant_{i + 1}_import_failed: {exc}")
                            result["status"] = "partial"
                    result["imported_to_blender"] = len(imported_names)
                    if imported_names and len(imported_names) != len(verified):
                        result["status"] = "partial"
                    result["next_steps"] = [
                        "All variants imported to Blender in a grid layout.",
                        "Each model's 'texture_channels' key contains extracted PBR paths (albedo, orm, normal).",
                        "Pick the best variant, then run: asset_pipeline action=cleanup object_name=<name> has_extracted_textures=true texture_channels=<model.texture_channels>",
                        "Or full pipeline: asset_pipeline action=full_pipeline object_name=<name>",
                        "The AAA pipeline will: repair -> retopo -> UV -> wire extracted textures -> weathering -> quality gate.",
                    ]

                _imported_name = imported_names[0] if imported_names else None
                return await _with_screenshot(blender, result, capture_viewport, _imported_name)
            finally:
                await gen.close()
        elif api_key:
            gen = TripoGenerator(api_key=api_key)
            try:
                if image_path:
                    result = await gen.generate_from_image(image_path, output_dir)
                else:
                    result = await gen.generate_from_text(prompt, output_dir)
                result["output_dir"] = output_dir
                result_warnings = result.setdefault("warnings", [])

                # Post-process: extract textures, import into Blender (same as studio path)
                model_path = result.get("model_path") or result.get("pbr_model_path")
                if model_path and result.get("status") == "success":
                    glb_out_dir = str(
                        Path(model_path).parent / "textures"
                    )
                    try:
                        post_result = await post_process_tripo_model(
                            model_path, glb_out_dir,
                            asset_type=asset_type or "prop",
                        )
                        result["post_process"] = post_result
                        result["texture_channels"] = post_result.get("channels", {})
                        if post_result.get("albedo_delit"):
                            result["texture_channels"]["albedo_delit"] = post_result["albedo_delit"]
                        if post_result.get("warnings"):
                            result_warnings.extend(
                                f"post_process: {warning}" for warning in post_result["warnings"]
                            )
                        if post_result.get("status") not in (None, "success"):
                            result["status"] = "partial"
                    except Exception as exc:
                        logger.warning(
                            "Post-process failed for API-key model: %s", exc,
                            exc_info=True,
                        )
                        result_warnings.append(f"post_process_failed: {exc}")
                        result["status"] = "partial"
                        result["texture_channels"] = {}

                    safe = model_path.replace('\\', '/').replace('"', '\\"')
                    code = (
                        f'import bpy\n'
                        f'bpy.ops.object.select_all(action="DESELECT")\n'
                        f'existing = set(bpy.data.objects[:])\n'
                        f'bpy.ops.import_scene.gltf(filepath="{safe}", merge_vertices=True)\n'
                        f'new_objs = set(bpy.data.objects[:]) - existing\n'
                        f'names = [o.name for o in new_objs if o.type == "MESH"]\n'
                        f'names'
                    )
                    try:
                        await blender.send_command("execute_code", {"code": code})
                        result["imported_to_blender"] = 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to import API-key model into Blender: %s",
                            exc, exc_info=True,
                        )
                        result_warnings.append(f"import_failed: {exc}")
                        result["status"] = "partial"

                    result["next_steps"] = [
                        "Model imported to Blender with extracted textures.",
                        "'texture_channels' key contains extracted PBR paths (albedo, orm, normal).",
                        "Run cleanup: asset_pipeline action=cleanup object_name=<name> has_extracted_textures=true texture_channels=<texture_channels>",
                        "Or full pipeline: asset_pipeline action=full_pipeline object_name=<name>",
                    ]

                _api_imported = result.get("object_name")
                return await _with_screenshot(blender, result, capture_viewport, _api_imported)
            finally:
                gen.close()
        else:
            return json.dumps({
                "status": "unavailable",
                "error": "Neither TRIPO_SESSION_COOKIE, TRIPO_STUDIO_TOKEN, nor TRIPO_API_KEY configured",
            })

    elif action == "generate_building":
        # Architecture-specific Tripo generation with dark fantasy prompt engineering
        _BUILDING_PROMPTS = {
            "tavern": "medieval dark fantasy tavern, stone foundation, wooden upper floor, thatched roof, hanging sign, chimney, detailed windows",
            "castle": "dark fantasy castle keep, stone walls, battlements, arrow slits, heavy iron-bound gate, tower turrets",
            "cathedral": "gothic dark fantasy cathedral, pointed arches, flying buttresses, rose window, spire, gargoyles",
            "tower": "dark fantasy wizard tower, stone construction, spiral staircase visible, narrow windows, conical roof",
            "house": "medieval dark fantasy cottage, stone and timber frame, thatched roof, small windows, wooden door",
            "shop": "medieval dark fantasy merchant shop, overhanging upper floor, display window, hanging trade sign",
            "ruin": "crumbling dark fantasy stone ruins, broken walls, overgrown with vines, collapsed roof, ancient architecture",
            "gate": "dark fantasy fortified gatehouse, portcullis, murder holes, twin guard towers, heavy stone walls",
            "bridge": "dark fantasy stone bridge, arched supports, worn stone railings, moss-covered, over dark water",
            "wall_section": "dark fantasy castle wall section, crenellations, walkway, torch sconces, weathered stone blocks",
            "dungeon_entrance": "dark fantasy dungeon entrance, heavy stone doorway, iron bars, skull decorations, descending stairs",
            "shrine": "dark fantasy roadside shrine, carved stone altar, religious symbols, candle holders, weathered and ancient",
            "lighthouse": "dark fantasy coastal lighthouse, crumbling stone tower, spiraling iron staircase, cracked lantern room with eerie green flame, barnacle-encrusted base, jagged cliff perch",
            "water_mill": "dark fantasy water mill, mossy wooden wheel half-submerged in murky stream, sagging timber frame, stone foundation, grain chute, overgrown with creeping vines",
            "mine_complex": "dark fantasy mine entrance complex, reinforced timber supports, ore cart tracks, piled rubble, iron lanterns, collapsed side tunnels, pickaxe racks",
            "aqueduct": "dark fantasy stone aqueduct, towering arched supports, cracked channel with stagnant water, moss and lichen covered, ancient masonry, partially collapsed spans",
            "amphitheater": "dark fantasy ruined amphitheater, tiered stone seating, crumbling stage platform, faded carvings, overgrown with thorny brambles, ritual bloodstains",
            "library": "dark fantasy forbidden library, tall narrow stone building, arched windows with iron shutters, heavy oak doors, chain-bound entrance, arcane symbols etched in lintels",
            "harbor_complex": "dark fantasy harbor complex, rotting wooden docks, stone quay walls, rusted crane mechanism, barnacle-covered pilings, beached hull wreckage, fog-shrouded",
            "sewer_entrance": "dark fantasy sewer entrance, heavy iron grate set in cobblestone, fetid water drainage, rat carvings on archway, corroded metal bars, descending stone steps",
            "catacombs": "dark fantasy catacombs entrance, ornate stone archway with skull motifs, descending stairwell into darkness, iron torch brackets, crumbling burial niches, cold mist seeping out",
            "wizard_tower": "dark fantasy wizard tower, impossibly tall spiraling stone spire, floating crystal at apex, arcane glyphs glowing faintly, observatory dome, chained balconies",
            "dragons_lair": "dark fantasy dragon lair entrance, massive cavern mouth in mountainside, claw-scarred stone, charred bones scattered, heat shimmer, sulfurous vents, melted rock formations",
            "underground_forge": "dark fantasy underground forge entrance, heavy stone doorway with anvil crest, orange glow from within, smoke vents, iron reinforced walls, hammer and tongs motifs",
            "skeleton_landmark": "dark fantasy colossal skeleton landmark, massive ancient beast ribcage arching over terrain, weathered bones half-buried, eerie atmosphere, overgrown with dark moss",
            "war_machine_ruin": "dark fantasy ruined war machine, massive broken siege engine, splintered wooden beams, twisted iron plating, scattered ammunition, overgrown battlefield debris",
            "temple": "dark fantasy ancient temple, massive stone columns, carved frieze depicting dark rituals, cracked obsidian altar, flickering braziers, vine-choked entrance, oppressive atmosphere",
            "graveyard": "dark fantasy graveyard, tilted headstones, wrought iron fence, dead twisted trees, open crypts, fog rolling between graves, crumbling mausoleum in background",
            "covered_bridge": "dark fantasy covered bridge, weathered timber roof over stone arch span, iron lanterns hanging inside, creaking wooden planks, claw marks on walls, mist-shrouded ravine below",
        }
        _STYLE_MODIFIERS = {
            "dark_fantasy": "dark moody atmosphere, weathered stone, iron fixtures, gothic elements",
            "gothic": "pointed arches, ribbed vaults, ornate tracery, gargoyles, dark stone",
            "medieval": "rough-hewn stone, timber beams, iron hinges, practical construction",
            "elven": "elegant curves, living wood elements, nature-integrated, silver accents",
            "dwarven": "heavy stone blocks, geometric patterns, iron reinforcement, underground aesthetic",
            "corrupted": "twisted architecture, dark tendrils, cracked stone, eerie glow, decay",
        }
        _SIZE_HINTS = {
            "small": "small scale, single story",
            "medium": "medium scale, two stories",
            "large": "large imposing structure, three stories",
            "massive": "massive monumental structure, towering scale",
        }

        bt = building_type or "house"
        base_prompt = _BUILDING_PROMPTS.get(bt, f"dark fantasy {bt}")
        style_mod = _STYLE_MODIFIERS.get(building_style, _STYLE_MODIFIERS["dark_fantasy"])
        size_hint = _SIZE_HINTS.get(building_size, _SIZE_HINTS["medium"])
        full_prompt = prompt or f"{base_prompt}, {style_mod}, {size_hint}, game-ready 3D model, clean topology"
        # STY-001: enforce dark fantasy style prefix
        _df_prefix = "dark fantasy medieval weathered Gothic, "
        if not full_prompt.startswith(_df_prefix):
            full_prompt = _df_prefix + full_prompt

        # Route to generate_3d with the composed prompt
        studio_cookie = settings.tripo_session_cookie
        studio_token = settings.tripo_studio_token
        api_key = settings.tripo_api_key

        if not (studio_cookie or studio_token or api_key):
            return json.dumps({
                "status": "unavailable",
                "error": "No Tripo credentials configured. Set TRIPO_SESSION_COOKIE, TRIPO_STUDIO_TOKEN, or TRIPO_API_KEY.",
                "prompt_preview": full_prompt,
                "tip": "You can use this prompt with any 3D generation service.",
            })

        # Set output dir for buildings
        _vb3d = settings.unity_project_path
        if _vb3d:
            output_dir = str(Path(_vb3d) / "Assets/Art/3D_Models/Buildings")
            if name:
                output_dir = str(Path(output_dir) / name)

        if studio_cookie or studio_token:
            from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
            gen = TripoStudioClient(
                session_cookie=studio_cookie,
                session_token=studio_token,
            )
            try:
                if image_path:
                    result = await gen.generate_from_image(image_path, output_dir)
                else:
                    result = await gen.generate_from_text(full_prompt, output_dir)
                result["building_type"] = bt
                result["building_style"] = building_style
                result["prompt_used"] = full_prompt
                result["next_steps"] = [
                    f"Generated {bt} ({building_style} style) via Tripo.",
                    "Pick the best variant, then run: asset_pipeline action=cleanup object_name=<name>",
                    "For terrain placement: use blender_environment action=scatter_props",
                ]
                _bld_studio_name = result.get("object_name")
                return await _with_screenshot(blender, result, capture_viewport, _bld_studio_name)
            finally:
                await gen.close()
        else:
            gen = TripoGenerator(api_key=api_key)
            if image_path:
                result = await gen.generate_from_image(image_path, output_dir)
            else:
                result = await gen.generate_from_text(full_prompt, output_dir)
            result["building_type"] = bt
            result["prompt_used"] = full_prompt
            _bld_api_name = result.get("object_name")
            return await _with_screenshot(blender, result, capture_viewport, _bld_api_name)

    elif action == "generate_prop":
        # Route ALL prop/furniture/vegetation generation through Tripo with
        # curated dark fantasy prompts. Procedural fallback only when Tripo unavailable.
        _PROP_PROMPTS = {
            # --- Furniture & Indoor Props ---
            "barrel": "medieval dark fantasy wooden barrel, iron bands, weathered oak staves, nail details, game-ready 3D model, PBR textures, clean topology",
            "crate": "medieval dark fantasy wooden crate, rough planks, iron corner brackets, rope handles, game-ready 3D model, PBR textures",
            "table": "medieval dark fantasy wooden tavern table, thick oak planks, carved legs, knife marks and mug rings, game-ready 3D model, PBR textures",
            "chair": "medieval dark fantasy wooden chair, rough-hewn oak, worn leather seat, carved back, game-ready 3D model, PBR textures",
            "bed": "medieval dark fantasy bed, heavy wood frame, straw mattress, woolen blanket, carved headboard, game-ready 3D model, PBR textures",
            "bookshelf": "medieval dark fantasy bookshelf, dark wood, leather-bound tomes, scrolls, dust and cobwebs, game-ready 3D model, PBR textures",
            "chest": "medieval dark fantasy treasure chest, iron-bound oak, heavy lock, ornate metalwork, game-ready 3D model, PBR textures",
            "wardrobe": "medieval dark fantasy wardrobe, tall dark wood cabinet, iron hinges, carved panels, game-ready 3D model, PBR textures",
            "shelf": "medieval dark fantasy wall shelf, rough timber brackets, potion bottles, candles, game-ready 3D model, PBR textures",
            "candelabra": "medieval dark fantasy iron candelabra, multiple branches, dripping wax, ornate base, game-ready 3D model, PBR textures",
            "chandelier": "medieval dark fantasy iron chandelier, circular frame, chains, candle holders, game-ready 3D model, PBR textures",
            "anvil": "medieval dark fantasy blacksmith anvil, heavy cast iron, horn and face, hammer marks, soot stains, game-ready 3D model, PBR textures",
            "forge": "medieval dark fantasy stone forge, brick chimney, bellows, glowing coals, iron tools, game-ready 3D model, PBR textures",
            "altar": "dark fantasy ritual stone altar, carved runes, bloodstains, candle holders, obsidian inlays, game-ready 3D model, PBR textures",
            "throne": "dark fantasy throne, carved stone and dark wood, iron accents, skulls, velvet cushion, game-ready 3D model, PBR textures",
            "fireplace": "medieval dark fantasy stone fireplace, carved mantel, iron grate, glowing embers, soot marks, game-ready 3D model, PBR textures",
            "cauldron": "dark fantasy iron cauldron, heavy tripod legs, bubbling contents, ladle, mystic symbols, game-ready 3D model, PBR textures",
            "workbench": "medieval dark fantasy crafting workbench, heavy timber, vise, scattered tools, wood shavings, game-ready 3D model, PBR textures",
            # --- Outdoor Props ---
            "well": "medieval dark fantasy stone well, moss-covered walls, wooden bucket, rope pulley, iron frame, game-ready 3D model, PBR textures",
            "cart": "medieval dark fantasy wooden cart, iron-rimmed wheels, worn planks, hay remnants, game-ready 3D model, PBR textures",
            "market_stall": "medieval dark fantasy market stall, canvas awning, wooden counter, hanging wares, game-ready 3D model, PBR textures",
            "signpost": "medieval dark fantasy wooden signpost, carved directional signs, iron nails, weathered wood, game-ready 3D model, PBR textures",
            "campfire": "dark fantasy campfire, stone ring, burning logs, iron spit, scattered sparks, game-ready 3D model, PBR textures",
            "brazier": "dark fantasy iron brazier, ornate legs, burning coals, warm glow, game-ready 3D model, PBR textures",
            "gravestone": "dark fantasy gravestone, weathered stone, carved epitaph, moss and lichen, slightly tilted, game-ready 3D model, PBR textures",
            "fence": "medieval dark fantasy wooden fence section, rough-hewn posts, iron nails, weathered and leaning, game-ready 3D model, PBR textures",
            "lantern": "medieval dark fantasy hanging lantern, wrought iron frame, amber glass panes, flickering candle, chain, game-ready 3D model, PBR textures",
            "torch_sconce": "medieval dark fantasy wall torch sconce, iron bracket, burning torch, smoke wisps, game-ready 3D model, PBR textures",
            # --- Vegetation (HIGH PRIORITY - replace terrible procedural trees) ---
            "tree_oak": "dark fantasy ancient oak tree, gnarled twisted trunk, thick bark, sprawling branches, dark green foliage, moss and lichen, game-ready 3D model, PBR textures, stylized",
            "tree_dead": "dark fantasy dead tree, bare twisted branches, rotting bark, hollow trunk, dark atmosphere, game-ready 3D model, PBR textures",
            "tree_pine": "dark fantasy dark pine tree, tall straight trunk, dense needle foliage, drooping branches, game-ready 3D model, PBR textures",
            "tree_willow": "dark fantasy weeping willow tree, drooping vine-like branches, gnarled trunk, ethereal atmosphere, game-ready 3D model, PBR textures",
            "tree_corrupted": "dark fantasy corrupted tree, twisted black bark, glowing purple veins, withered leaves, dark tendrils, game-ready 3D model, PBR textures",
            "bush": "dark fantasy thorny bush, dark green leaves, tangled branches, berries, game-ready 3D model, PBR textures",
            "fallen_log": "dark fantasy fallen log, moss-covered rotting wood, mushrooms growing, broken branches, game-ready 3D model, PBR textures",
            "tree_stump": "dark fantasy tree stump, axe-cut top, growth rings visible, moss and fungi, game-ready 3D model, PBR textures",
            "mushroom_cluster": "dark fantasy large mushroom cluster, glowing bioluminescent caps, varied sizes, forest floor base, game-ready 3D model, PBR textures",
            "rock_formation": "dark fantasy rocky outcrop, layered stone, moss patches, dark lichen, cracked surfaces, game-ready 3D model, PBR textures",
            # --- Dungeon Props ---
            "prison_door": "dark fantasy prison cell door, heavy iron bars, rusted lock, stone frame, chains, game-ready 3D model, PBR textures",
            "sarcophagus": "dark fantasy stone sarcophagus, ornate carved lid, ancient symbols, cracked marble, cobwebs, game-ready 3D model, PBR textures",
            "torture_rack": "dark fantasy torture rack, dark wood frame, iron shackles, leather straps, bloodstains, game-ready 3D model, PBR textures",
            "skull_pile": "dark fantasy skull pile, human and beast skulls, bones, dark candles, ritual arrangement, game-ready 3D model, PBR textures",
        }

        prop_type = object_name or "barrel"
        prop_prompt = _PROP_PROMPTS.get(prop_type, f"dark fantasy {prop_type}, medieval style, weathered, game-ready 3D model, PBR textures, clean topology")
        full_prompt = prompt or prop_prompt
        # STY-001: enforce dark fantasy style prefix
        _df_prefix = "dark fantasy medieval weathered Gothic, "
        if not full_prompt.startswith(_df_prefix):
            full_prompt = _df_prefix + full_prompt

        studio_cookie = settings.tripo_session_cookie
        studio_token = settings.tripo_studio_token
        api_key = settings.tripo_api_key

        if not (studio_cookie or studio_token or api_key):
            return json.dumps({
                "error": "No Tripo credentials configured. Set TRIPO_SESSION_COOKIE, TRIPO_STUDIO_TOKEN, or TRIPO_API_KEY.",
                "fallback": f"Using procedural generator for '{prop_type}'. Set Tripo credentials for AAA quality.",
                "prop_type": prop_type,
            }, indent=2)

        # Route to generate_3d with the prop prompt
        if studio_cookie or studio_token:
            from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
            gen = TripoStudioClient(
                session_cookie=studio_cookie or None,
                session_token=studio_token or None,
            )
            try:
                if image_path:
                    result = await gen.generate_from_image(image_path, output_dir)
                else:
                    result = await gen.generate_from_text(full_prompt, output_dir)
                result["prop_type"] = prop_type
                result["prompt_used"] = full_prompt
                result["generation_method"] = "tripo_studio"
                result["next_steps"] = [
                    "Pick best variant, then: asset_pipeline action=cleanup object_name=<name> has_extracted_textures=true",
                    "Run game_check after cleanup to verify quality",
                ]
                _prop_studio_name = result.get("object_name")
                return await _with_screenshot(blender, result, capture_viewport, _prop_studio_name)
            finally:
                await gen.close()
        else:
            gen = TripoGenerator(api_key=api_key)
            if image_path:
                result = await gen.generate_from_image(image_path, output_dir)
            else:
                result = await gen.generate_from_text(full_prompt, output_dir)
            result["prop_type"] = prop_type
            result["prompt_used"] = full_prompt
            result["generation_method"] = "tripo_api"
            _prop_api_name = result.get("object_name")
            return await _with_screenshot(blender, result, capture_viewport, _prop_api_name)

    elif action == "inspect_external_toolchain":
        result = await blender.send_command("toolchain_inspect_external", {
            "prefer_external": prefer_external,
            "review_lighting": review_lighting,
            "project_label": "VeilBreakers",
        })
        return json.dumps(result, indent=2, default=str)

    elif action == "configure_external_toolchain":
        result = await blender.send_command("toolchain_configure_external", {
            "prefer_external": prefer_external,
            "review_lighting": review_lighting,
            "project_label": "VeilBreakers",
        })
        return json.dumps(result, indent=2, default=str)

    elif action == "generate_terrain_mesh":
        # Generate terrain directly in Blender using procedural heightmap + erosion
        preset = terrain_preset or "mountains"
        _TERRAIN_PRESETS = {
            "mountains": {"noise_scale": 0.8, "octaves": 6, "height_mult": 1.0, "erosion_drops": 150000},
            "hills": {"noise_scale": 0.5, "octaves": 4, "height_mult": 0.4, "erosion_drops": 100000},
            "plains": {"noise_scale": 0.3, "octaves": 3, "height_mult": 0.1, "erosion_drops": 50000},
            "canyon": {"noise_scale": 0.9, "octaves": 5, "height_mult": 1.2, "erosion_drops": 200000},
            "volcanic": {"noise_scale": 1.0, "octaves": 5, "height_mult": 1.5, "erosion_drops": 100000},
            "coastal": {"noise_scale": 0.4, "octaves": 4, "height_mult": 0.3, "erosion_drops": 120000},
            "swamp": {"noise_scale": 0.2, "octaves": 3, "height_mult": 0.05, "erosion_drops": 80000},
        }
        cfg = _TERRAIN_PRESETS.get(preset, _TERRAIN_PRESETS["mountains"])

        result = await blender.send_command("env_generate_terrain", {
            "terrain_type": preset,
            "resolution": terrain_resolution,
            "height_scale": terrain_height_scale * cfg["height_mult"],
            "erosion": terrain_erosion,
            "erosion_iterations": cfg["erosion_drops"],
            "seed": terrain_seed,
            "size": terrain_size,
            "use_controller": True,
        })
        if isinstance(result, dict):
            result["preset"] = preset
            result["next_steps"] = [
                f"Terrain generated: {preset} ({terrain_size}x{terrain_size} units, {terrain_resolution} resolution).",
                "Paint textures: blender_environment action=paint_terrain",
                "Add vegetation: blender_environment action=scatter_vegetation",
                "Add props: blender_environment action=scatter_props",
                "Export heightmap for Unity: blender_environment action=export_heightmap",
            ]
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "compose_map":
        # Full map composition pipeline: terrain → water → roads → locations → vegetation → props
        if not map_spec:
            return json.dumps({
                "error": "map_spec is required",
                "example": {
                    "name": "Thornveil Region",
                    "seed": 42,
                    "terrain": {"preset": "hills", "size": 200, "resolution": 256, "height_scale": 20.0},
                    "water": {
                        "rivers": [{"source": [10, 10], "destination": [190, 190], "width": 5}],
                        "water_level": 2.0,
                    },
                    "roads": [{"waypoints": [[50, 80], [100, 100], [150, 60]], "width": 3}],
                    "locations": [
                        {"type": "town", "name": "Village", "districts": 3},
                        {"type": "castle", "name": "Keep"},
                        {"type": "dungeon", "name": "Crypt", "floors": 2},
                    ],
                    "biome": "thornwood_forest",
                    "vegetation": {"density": 0.5},
                    "atmosphere": "foggy",
                },
            }, indent=2)

        spec = map_spec
        terrain_only_requested = _map_spec_requests_terrain_only(spec)
        original_locations = list(spec.get("locations", [])) if isinstance(spec, dict) else []
        original_props_enabled = bool(spec.get("props", True)) if isinstance(spec, dict) else False
        if terrain_only_requested:
            spec = _filter_map_spec_for_terrain_only(spec)
        map_name = spec.get("name", "Map")
        map_seed = spec.get("seed", 42)
        budget = _resolve_map_generation_budget(spec)
        planned_locations = _plan_map_location_anchors(spec)
        planned_cave_locations = [
            planned
            for planned in planned_locations
            if str(planned.get("source", {}).get("type", "")).strip().lower() == "cave"
        ]
        planned_cave_candidates = [
            (float(planned["anchor"][0]), float(planned["anchor"][1]), 0.0)
            for planned in planned_cave_locations
        ]
        steps_completed: list[str] = []
        steps_failed: list[dict] = []
        pipeline_warnings: list[str] = []
        pipeline_degradations: list[str] = []
        created_objects: list[str] = []
        location_results: list[dict] = []
        interior_results: list[dict] = []
        terrain_runtime_diagnostics: dict[str, Any] = {}
        waterfall_runtime_diagnostics: list[dict[str, Any]] = []
        if terrain_only_requested:
            stripped_location_count = max(0, len(original_locations) - len(spec.get("locations", [])))
            if stripped_location_count:
                pipeline_warnings.append(
                    f"terrain_only mode skipped {stripped_location_count} non-terrain locations"
                )
            if original_props_enabled:
                pipeline_warnings.append("terrain_only mode disabled contextual prop scatter")
        hero_cliff_shaped_caves: set[str] = set()
        hero_cave_anchor_overrides: dict[str, dict[str, float]] = {}
        deferred_river_surfaces: list[dict[str, Any]] = []
        deferred_waterfalls: list[dict[str, Any]] = []
        deferred_water_body: dict[str, Any] | None = None
        terrain_visual_verification: dict[str, Any] | None = None
        terrain_cfg = spec.get("terrain", {})
        water_cfg = spec.get("water", {})
        if not isinstance(water_cfg, dict):
            water_cfg = {}
        water_system_spec_payload = _build_water_system_spec_payload(
            water_cfg,
            map_seed=map_seed,
        )
        terrain_result_payload: dict[str, Any] | None = None
        terrain_size = float(terrain_cfg.get("size", 200.0))
        terrain_location = tuple(terrain_cfg.get("location", (0.0, 0.0)))[:2]
        terrain_preset = str(terrain_cfg.get("preset", "hills")).strip().lower()
        auto_export_unity = bool(
            spec.get("auto_export_unity")
            or spec.get("unity_export_approved")
            or spec.get("export_to_unity")
        )
        terrain_resolution = min(
            int(terrain_cfg.get("resolution", 256)),
            int(budget["terrain_resolution_cap"]),
        )

        # --- Checkpoint resume logic (Phase 37) ---
        _CHKPT_LOADED = False
        if checkpoint_dir:
            try:
                from blender_addon.handlers.pipeline_state import (
                    load_pipeline_checkpoint as _load_chkpt,
                    validate_checkpoint_compatibility as _validate_chkpt,
                    delete_pipeline_checkpoint as _delete_chkpt,
                )
            except ImportError as _ps_err:
                return json.dumps({
                    "status": "error",
                    "error": f"pipeline_state unavailable in MCP server process (bpy not installed): {_ps_err}",
                    "hint": "Checkpoint/resume requires the Blender addon environment.",
                })
            if force_restart:
                _delete_chkpt(checkpoint_dir, map_name)
            elif resume:
                ckpt = _load_chkpt(checkpoint_dir, map_name)
                if ckpt is not None:
                    ok, reason = _validate_chkpt(ckpt, spec)
                    if not ok:
                        return json.dumps({
                            "status": "error",
                            "error": f"Checkpoint incompatible: {reason}",
                            "hint": "Set force_restart=True to discard the incompatible checkpoint.",
                        })
                    steps_completed = ckpt.get("steps_completed", [])
                    created_objects = ckpt.get("created_objects", [])
                    location_results = ckpt.get("location_results", [])
                    interior_results = ckpt.get("interior_results", [])
                    deferred_river_surfaces = list(ckpt.get("deferred_river_surfaces", []) or [])
                    deferred_waterfalls = list(ckpt.get("deferred_waterfalls", []) or [])
                    deferred_water_body = ckpt.get("deferred_water_body")
                    _CHKPT_LOADED = True

        def _save_chkpt():
            """Persist current pipeline state to checkpoint file."""
            if not checkpoint_dir:
                return
            try:
                from blender_addon.handlers.pipeline_state import (
                    save_pipeline_checkpoint as _save_cp,
                )
            except ImportError:
                return
            _save_cp(checkpoint_dir, {
                "map_name": map_name,
                "seed": map_seed,
                "location_count": len(spec.get("locations", [])),
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,  # BUG-CHKPT-02: persist failed steps
                "created_objects": created_objects,
                "location_results": location_results,
                "interior_results": interior_results,
                "deferred_river_surfaces": deferred_river_surfaces,
                "deferred_waterfalls": deferred_waterfalls,
                "deferred_water_body": deferred_water_body,
                "params_snapshot": {"terrain_size": terrain_size, "seed": map_seed},
            })

        def _record_pipeline_warning(step: str, error: Exception, *, object_name: str | None = None) -> None:
            target = f" for {object_name}" if object_name else ""
            message = f"{step}{target}: {error}"
            logger.warning("compose_map warning: %s", message)
            pipeline_warnings.append(message)

        def _record_pipeline_degradation(code: str, message: str) -> None:
            if code not in pipeline_degradations:
                pipeline_degradations.append(code)
            if message not in pipeline_warnings:
                pipeline_warnings.append(message)

        async def _verify_basin_depth(
            *,
            basin_center: list[float],
            resolved_water_level: float,
            basin_depth: float,
            basin_radius: float,
            shore_width: float,
            aspect_y: float,
        ) -> None:
            target_floor = float(resolved_water_level) - max(float(basin_depth) * 0.38, 0.9)
            basin_floor_height = await _sample_terrain_height(
                blender,
                terrain_name,
                float(basin_center[0]),
                float(basin_center[1]),
            )
            if basin_floor_height <= target_floor:
                return
            await blender.send_command("env_carve_water_basin", {
                "terrain_name": terrain_name,
                "center": basin_center,
                "water_level": resolved_water_level,
                "radius": basin_radius,
                "depth": max(basin_depth * 1.28, basin_depth + 1.0),
                "shore_width": max(shore_width, basin_radius * 0.82),
                "aspect_y": aspect_y,
            })
            basin_floor_height = await _sample_terrain_height(
                blender,
                terrain_name,
                float(basin_center[0]),
                float(basin_center[1]),
            )
            if basin_floor_height > target_floor:
                raise RuntimeError(
                    f"water basin floor remained too shallow ({basin_floor_height:.2f} > {target_floor:.2f})"
                )

        async def _verify_basin_inlet_depth(
            *,
            river_tail: list[float],
            basin_entry: tuple[float, float],
            resolved_water_level: float,
            basin_depth: float,
            river_width: float,
        ) -> None:
            target_height = float(resolved_water_level) - max(float(basin_depth) * 0.16, 0.45)
            sample_points = [
                (
                    float(river_tail[0]) * (1.0 - t) + float(basin_entry[0]) * t,
                    float(river_tail[1]) * (1.0 - t) + float(basin_entry[1]) * t,
                )
                for t in (0.0, 0.35, 0.7, 1.0)
            ]
            sampled_heights = [
                await _sample_terrain_height(blender, terrain_name, sample_x, sample_y)
                for sample_x, sample_y in sample_points
            ]
            if max(sampled_heights) <= target_height:
                return
            await blender.send_command("terrain_spline_deform", {
                "object_name": terrain_name,
                "spline_points": [
                    [float(river_tail[0]), float(river_tail[1]), target_height],
                    [
                        float(river_tail[0]) * 0.55 + float(basin_entry[0]) * 0.45,
                        float(river_tail[1]) * 0.55 + float(basin_entry[1]) * 0.45,
                        target_height - max(basin_depth * 0.08, 0.15),
                    ],
                    [float(basin_entry[0]), float(basin_entry[1]), target_height - max(basin_depth * 0.12, 0.24)],
                ],
                "mode": "carve",
                "width": max(float(river_width) * 2.8, 12.0),
                "depth": max(float(basin_depth) * 0.90, 1.6),
                "falloff": 0.92,
            })
            resampled = [
                await _sample_terrain_height(blender, terrain_name, sample_x, sample_y)
                for sample_x, sample_y in sample_points
            ]
            inlet_gap = max(resampled) - target_height
            if inlet_gap <= max(float(basin_depth) * 0.20, 1.2):
                return
            if max(resampled) > target_height:
                raise RuntimeError(
                    f"water basin inlet remained too high ({max(resampled):.2f} > {target_height:.2f})"
                )

        async def _verify_basin_rim_containment(
            *,
            rim_points: list[list[float]],
            resolved_water_level: float,
            bank_raise: float,
            basin_radius: float,
        ) -> None:
            """Ensure the basin rim stays above the final water plane outside the inlet gap."""
            if len(rim_points) < 4:
                return

            target_rim_height = float(resolved_water_level) + max(float(bank_raise) * 0.45, 0.75)
            sampled_heights = [
                await _sample_terrain_height(blender, terrain_name, float(point[0]), float(point[1]))
                for point in rim_points[:-1]
            ]
            if min(sampled_heights) >= target_rim_height:
                return

            await blender.send_command("terrain_spline_deform", {
                "object_name": terrain_name,
                "spline_points": rim_points,
                "mode": "raise",
                "depth": max(float(bank_raise) * 1.18, 2.8),
                "width": max(float(basin_radius) * 0.24, 5.8),
                "falloff": 0.90,
            })
            resampled = [
                await _sample_terrain_height(blender, terrain_name, float(point[0]), float(point[1]))
                for point in rim_points[:-1]
            ]
            if min(resampled) < target_rim_height:
                raise RuntimeError(
                    f"water basin rim remained too low ({min(resampled):.2f} < {target_rim_height:.2f})"
                )

        async def _reproject_river_surface_to_terrain(
            surface_points: list[list[float]] | list[tuple[float, float, float]],
            bed_points: list[list[float]] | list[tuple[float, float, float]] | None,
            *,
            min_water_depth: float,
            terminal_water_level: float | None = None,
        ) -> tuple[list[list[float]], list[list[float]]]:
            """Resample a deferred river against the final terrain bed before mesh emission."""
            cleaned_surface = [
                [float(point[0]), float(point[1]), float(point[2])]
                for point in (surface_points or [])
                if isinstance(point, (list, tuple)) and len(point) >= 3
            ]
            cleaned_bed = [
                [float(point[0]), float(point[1]), float(point[2])]
                for point in (bed_points or cleaned_surface)
                if isinstance(point, (list, tuple)) and len(point) >= 3
            ]
            count = min(len(cleaned_surface), len(cleaned_bed))
            if count < 2 or not terrain_name:
                return cleaned_surface, cleaned_bed

            conformed_surface: list[list[float]] = []
            conformed_bed: list[list[float]] = []
            previous_surface_z: float | None = None
            water_depth_floor = max(float(min_water_depth), 0.55)

            for index in range(count):
                sx, sy, sz = cleaned_surface[index]
                bx, by, bz = cleaned_bed[index]
                sample_succeeded = False
                try:
                    sampled_bed_z = float(await _sample_terrain_height(blender, terrain_name, bx, by))
                    sample_succeeded = True
                except Exception as sample_exc:
                    logger.debug(
                        "Deferred river reprojection falling back to stored bed height for %s: %s",
                        terrain_name,
                        sample_exc,
                        exc_info=True,
                    )
                    sampled_bed_z = float(bz)
                # Only reject a zero sample when the raycast likely missed entirely:
                # the stored bed Z is far from zero AND the sample returned exactly 0.
                if (
                    not sample_succeeded
                    or (abs(sampled_bed_z) <= 1e-6 and abs(float(bz)) > 2.0)
                ):
                    sampled_bed_z = float(bz)
                # Place river surface at a fixed offset above the SAMPLED terrain,
                # ensuring it follows the actual carved riverbed geometry.
                surface_z = sampled_bed_z + water_depth_floor
                if previous_surface_z is not None:
                    surface_z = min(surface_z, previous_surface_z - 0.015)
                conformed_bed.append([bx, by, sampled_bed_z])
                conformed_surface.append([sx, sy, surface_z])
                previous_surface_z = surface_z

            if terminal_water_level is not None:
                conformed_surface = _blend_path_points_to_terminal_water_level(
                    conformed_surface,
                    float(terminal_water_level),
                )
            return conformed_surface, conformed_bed

        async def _emit_deferred_water_surfaces() -> None:
            """Create visible water only after all terrain mutations are complete."""
            nonlocal deferred_river_surfaces, deferred_waterfalls, deferred_water_body

            waterfall_heightmap_context: dict[str, Any] | None = None
            if deferred_waterfalls:
                if not terrain_name:
                    raise RuntimeError(
                        "compose_map waterfall emission requires a terrain object name"
                    )
                waterfall_heightmap_context = await _capture_current_terrain_heightmap_context(
                    blender,
                    terrain_name,
                )
                if isinstance(terrain_result_payload, dict):
                    terrain_result_payload.update({
                        "heightmap": waterfall_heightmap_context["heightmap"],
                        "tile_size": waterfall_heightmap_context["tile_size"],
                        "cell_size": waterfall_heightmap_context["cell_size"],
                        "world_origin_x": waterfall_heightmap_context["world_origin_x"],
                        "world_origin_y": waterfall_heightmap_context["world_origin_y"],
                    })

            for pending in deferred_river_surfaces:
                try:
                    river_step = f"river_water_{int(pending['index'])}"
                    if river_step in steps_completed:
                        continue
                    path_points, bed_points = await _reproject_river_surface_to_terrain(
                        pending.get("path_points", []),
                        pending.get("bed_points"),
                        min_water_depth=float(pending.get("min_water_depth", 0.9)),
                        terminal_water_level=(
                            float(pending["terminal_water_level"])
                            if pending.get("terminal_water_level") is not None
                            else None
                        ),
                    )
                    await blender.send_command(
                        "env_create_water",
                        {
                            "name": pending["name"],
                            "terrain_name": terrain_name,
                            "path_points": path_points,
                            "water_level": float(pending["water_level"]),
                            "width": float(pending["width"]),
                            "cross_sections": int(pending.get("cross_sections", 16)),
                            "preview_fast": False,
                            "preserve_path_shape": True,
                            "surface_only": True,
                        },
                    )
                    steps_completed.append(river_step)
                    if pending["name"] not in created_objects:
                        created_objects.append(pending["name"])
                except Exception as river_emit_exc:
                    steps_failed.append(
                        {
                            "step": f"river_water_{pending.get('index', 'unknown')}",
                            "error": str(river_emit_exc),
                        }
                    )

            if deferred_water_body and "water_plane" not in steps_completed:
                try:
                    await blender.send_command(
                        "env_create_water",
                        {
                            "name": deferred_water_body["name"],
                            "terrain_name": terrain_name,
                            "water_level": float(deferred_water_body["water_level"]),
                            "preview_fast": False,
                            "mask_center": deferred_water_body["mask_center"],
                            "mask_radius": float(deferred_water_body["mask_radius"]),
                            "mask_aspect_y": float(deferred_water_body.get("mask_aspect_y", 1.0)),
                            "surface_only": True,
                        },
                    )
                    steps_completed.append("water_plane")
                    if deferred_water_body["name"] not in created_objects:
                        created_objects.append(deferred_water_body["name"])
                except Exception as water_emit_exc:
                    steps_failed.append({"step": "water_plane", "error": str(water_emit_exc)})

            for pending in deferred_waterfalls:
                waterfall_step = str(pending.get("step_key", pending.get("name", "waterfall")))
                if waterfall_step in steps_completed:
                    continue
                try:
                    if waterfall_heightmap_context is None:
                        raise RuntimeError(
                            "compose_map waterfall emission requires controller terrain heightmap context"
                        )
                    waterfall_result = await blender.send_command(
                        "env_generate_waterfall",
                        {
                            "name": pending["name"],
                            "height": float(pending["height"]),
                            "width": float(pending["width"]),
                            "pool_radius": float(pending["pool_radius"]),
                            "num_steps": int(pending.get("num_steps", 3)),
                            "has_cave_behind": bool(pending.get("has_cave_behind", False)),
                            "seed": int(pending.get("seed", map_seed)),
                            "facing_direction": list(pending.get("facing_direction", [0.0, -1.0])),
                            "location": list(pending["location"]),
                            "materialize_object": True,
                            "preview_fast": False,
                            "require_heightmap_context": True,
                            **waterfall_heightmap_context,
                        },
                    )
                    steps_completed.append(waterfall_step)
                    waterfall_name = pending["name"]
                    if isinstance(waterfall_result, dict):
                        waterfall_name = str(
                            waterfall_result.get("name")
                            or waterfall_result.get("object_name")
                            or waterfall_name
                        )
                        waterfall_diag = {
                            "name": waterfall_name,
                            "step": waterfall_step,
                            "authoring_path": str(
                                waterfall_result.get("authoring_path", "unknown")
                            ),
                        }
                        functional_object_names = waterfall_result.get("functional_object_names")
                        if isinstance(functional_object_names, (list, tuple)):
                            waterfall_diag["functional_object_names"] = [
                                str(name)
                                for name in functional_object_names
                                if str(name).strip()
                            ]
                            waterfall_diag["functional_objects_materialized"] = bool(
                                waterfall_result.get("functional_objects_materialized", False)
                            )
                        if waterfall_result.get("warning"):
                            waterfall_diag["warning"] = str(waterfall_result["warning"])
                            warning_message = (
                                f"{waterfall_name}: {waterfall_result['warning']}"
                            )
                            if warning_message not in pipeline_warnings:
                                pipeline_warnings.append(warning_message)
                        waterfall_runtime_diagnostics.append(waterfall_diag)
                    if waterfall_name not in created_objects:
                        created_objects.append(waterfall_name)
                except Exception as waterfall_emit_exc:
                    steps_failed.append({"step": waterfall_step, "error": str(waterfall_emit_exc)})

        async def _generate_roads_after_terrain_mutations() -> None:
            """Generate roads only after caves/locations finish editing terrain."""
            cave_road_zones = []
            for planned in planned_locations:
                if str(planned.get("source", {}).get("type", "")).strip().lower() != "cave":
                    continue
                cave_name = str(planned.get("name") or planned.get("source", {}).get("name") or "")
                override = hero_cave_anchor_overrides.get(cave_name)
                center_x = float(override.get("x", planned["anchor"][0])) if override else float(planned["anchor"][0])
                center_y = float(override.get("y", planned["anchor"][1])) if override else float(planned["anchor"][1])
                cave_road_zones.append(
                    {
                        "center_x": center_x,
                        "center_y": center_y,
                        "radius": max(
                            float(planned.get("radius", 15.0)) * 1.55,
                            float(planned.get("source", {}).get("entrance_width", 0.0)) * 2.3,
                            12.0,
                        ),
                    }
                )

            completed_roads = {s for s in steps_completed if s.startswith("road_")}
            for i, road in enumerate(spec.get("roads", [])):
                if f"road_{i}" in completed_roads:
                    continue
                try:
                    road_spec = _retarget_road_away_from_caves(road, cave_road_zones)
                    road_surface = str(
                        road_spec.get("surface", road_spec.get("style", "trail"))
                    ).strip().lower()
                    low_profile_surface = road_surface in {"trail", "path", "dirt_path", "dirt"}
                    waypoints = [
                        list(
                            _map_point_to_terrain_cell(
                                waypoint,
                                terrain_size=terrain_size,
                                resolution=terrain_resolution,
                                terrain_location=terrain_location,
                            )
                        )
                        for waypoint in road_spec.get("waypoints", [])
                        if isinstance(waypoint, (list, tuple)) and len(waypoint) >= 2
                    ]
                    if len(waypoints) < 2:
                        raise ValueError("Road generation requires at least two waypoints")
                    await blender.send_command(
                        "env_generate_road",
                        {
                            "terrain_name": terrain_name,
                            "waypoints": waypoints,
                            "width": road_spec.get("width", 3),
                            "surface": road_surface,
                            "water_level": water_cfg.get("water_level"),
                            "force_mesh_overlay": bool(road_spec.get("force_mesh_overlay", False)),
                            "allow_bridges": bool(road_spec.get("allow_bridges", not low_profile_surface)),
                            "seed": map_seed + 100 + i,
                        },
                    )
                    steps_completed.append(f"road_{i}")
                except Exception as road_exc:
                    steps_failed.append({"step": f"road_{i}", "error": str(road_exc)})

        # --- Step 1: Clear scene ---
        if "scene_cleared" not in steps_completed:
            try:
                await blender.send_command("clear_scene", {})
                steps_completed.append("scene_cleared")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "scene_clear", "error": str(e)})

        # --- Step 2: Generate terrain ---
        terrain_name = f"{map_name}_Terrain"
        if "terrain_generated" not in steps_completed:
            try:
                _terrain_loc_3d = (
                    (terrain_location[0], terrain_location[1], 0.0)
                    if terrain_location != (0.0, 0.0) else (0.0, 0.0, 0.0)
                )
                terrain_params = {
                    "name": terrain_name,
                    "terrain_type": terrain_preset,
                    "resolution": terrain_resolution,
                    "height_scale": float(
                        terrain_cfg.get(
                            "height_scale",
                            _default_terrain_height_scale(
                                terrain_preset=terrain_preset,
                                terrain_size=terrain_size,
                                map_spec=spec,
                            ),
                        )
                    ),
                    "scale": terrain_size,
                    "seed": map_seed,
                    "erosion": "hydraulic" if terrain_cfg.get("erosion", True) else "none",
                    "erosion_iterations": terrain_cfg.get("erosion_iterations", 5000),
                    "cliff_overlays": bool(
                        terrain_cfg.get(
                            "cliff_overlays",
                            _default_cliff_overlay_setting(
                                terrain_preset=terrain_preset,
                                map_spec=spec,
                            ),
                        )
                    ),
                    "use_controller": True,
                    "object_location": list(_terrain_loc_3d),
                    "water_system_spec": water_system_spec_payload,
                    "scene_read": {
                        "timestamp": 0.0,
                        "reviewer": "compose_map",
                        "cave_candidates": [list(c) for c in planned_cave_candidates],
                    } if planned_cave_candidates else None,
                }
                if isinstance(terrain_cfg.get("flatten_zones"), list) and terrain_cfg.get("flatten_zones"):
                    terrain_params["flatten_zones"] = list(terrain_cfg.get("flatten_zones") or [])
                try:
                    _terrain_result = await blender.send_command(
                        "env_generate_terrain",
                        {**terrain_params, "use_controller": True},
                    )
                except Exception as controller_exc:
                    raise RuntimeError(
                        f"TerrainPassController generation failed: {controller_exc}"
                    ) from controller_exc
                if (
                    isinstance(_terrain_result, dict)
                    and _terrain_result.get("status") not in (None, "success")
                ):
                    raise RuntimeError(
                        _terrain_result.get("error", "env_generate_terrain returned non-success status")
                    )
                terrain_result_payload = _terrain_result if isinstance(_terrain_result, dict) else None
                if (
                    isinstance(terrain_result_payload, dict)
                    and terrain_result_payload.get("controller_used") is False
                ):
                    terrain_result_payload["controller_fallback_used"] = True
                if isinstance(terrain_result_payload, dict):
                    terrain_runtime_diagnostics = {
                        "controller_used": bool(terrain_result_payload.get("controller_used", False)),
                        "water_network_present": bool(
                            terrain_result_payload.get("water_network_present", False)
                        ),
                    }
                    if water_cfg and not terrain_runtime_diagnostics["water_network_present"]:
                        message = (
                            "controller terrain reported water_network_present=False; "
                            "terrain-aware waterfall and river placement will be degraded"
                        )
                        if message not in pipeline_warnings:
                            pipeline_warnings.append(message)
                steps_completed.append("terrain_generated")
                created_objects.append(terrain_name)
                try:
                    await blender.send_command("material_create_procedural", {
                        "object_name": terrain_name,
                        "material_key": _terrain_review_material_key(terrain_cfg.get("preset", "hills")),
                        "name": f"{terrain_name}_Review",
                    })
                    steps_completed.append("terrain_review_material")
                except Exception as material_exc:
                    _record_pipeline_warning("terrain_review_material", material_exc, object_name=terrain_name)
                if "hero_terrain_shaped" not in steps_completed:
                    try:
                        cave_anchor_hint = None
                        if planned_cave_candidates:
                            cave_anchor_hint = (
                                float(planned_cave_candidates[0][0]),
                                float(planned_cave_candidates[0][1]),
                            )
                        hero_steps = await _apply_hero_mountain_shaping(
                            blender,
                            terrain_name=terrain_name,
                            map_spec=spec,
                            terrain_size=terrain_size,
                            terrain_location=terrain_location,
                            terrain_preset=terrain_preset,
                            height_scale=float(terrain_params["height_scale"]),
                            cave_anchor=cave_anchor_hint,
                        )
                        if hero_steps:
                            steps_completed.extend(hero_steps)
                        try:
                            spike_cleanup = await _temper_hero_peak_outliers(
                                blender,
                                terrain_name,
                                percentile=0.991,
                                blend=0.78,
                                prominence_threshold=max(float(terrain_params["height_scale"]) * 0.085, 5.2),
                                passes=2,
                            )
                            if int(spike_cleanup.get("affected_vertices", 0)) > 0:
                                steps_completed.append("hero_peak_cleanup")
                        except Exception as spike_cleanup_exc:
                            _record_pipeline_warning("hero_peak_cleanup", spike_cleanup_exc, object_name=terrain_name)
                        if hero_steps:
                            steps_completed.append("hero_terrain_shaped")
                    except Exception as hero_shape_exc:
                        _record_pipeline_warning("hero_terrain_shaping", hero_shape_exc, object_name=terrain_name)
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "terrain", "error": str(e)})

        # --- Step 2.5: Hero cliff shaping ---
        if "terrain_generated" in steps_completed and terrain_name and planned_cave_locations:
            for i, planned in enumerate(planned_cave_locations):
                cave_source = planned.get("source", {})
                cave_name = str(planned.get("name") or cave_source.get("name") or f"Cave_{i}")
                anchor_x, anchor_y = planned["anchor"]
                loc_radius = float(planned.get("radius", 15.0))
                entrance_width = float(cave_source.get("entrance_width", max(5.5, loc_radius * 0.34)))
                entrance_height = float(cave_source.get("entrance_height", max(4.2, loc_radius * 0.24)))
                try:
                    retargeted_anchor = await _retarget_cave_anchor_to_relief(
                        blender,
                        terrain_name,
                        anchor_x=float(anchor_x),
                        anchor_y=float(anchor_y),
                        terrain_size=terrain_size,
                        terrain_location=terrain_location,
                        search_radius=max(loc_radius * 0.72, entrance_width * 1.55, 12.0),
                        sample_radius=max(entrance_width * 0.88, 7.5),
                    )
                    hero_cave_anchor_overrides[cave_name] = {
                        "x": float(retargeted_anchor["x"]),
                        "y": float(retargeted_anchor["y"]),
                        "z": float(retargeted_anchor["z"]),
                        "outward_x": float(retargeted_anchor.get("outward_x", 0.0)),
                        "outward_y": float(retargeted_anchor.get("outward_y", 1.0)),
                        "slope_drop": float(retargeted_anchor.get("slope_drop", 0.0)),
                    }
                    await _shape_hero_cave_ridge(
                        blender,
                        terrain_name,
                        cave_name=cave_name,
                        anchor_x=float(retargeted_anchor["x"]),
                        anchor_y=float(retargeted_anchor["y"]),
                        loc_radius=loc_radius,
                        entrance_width=entrance_width,
                        entrance_height=entrance_height,
                        terrain_location=terrain_location,
                    )
                    hero_cliff_shaped_caves.add(cave_name)
                    steps_completed.append(f"hero_cliff_{cave_name}")
                except Exception as ridge_exc:
                    override = hero_cave_anchor_overrides.get(cave_name)
                    if override is not None and float(override.get("slope_drop", 0.0)) >= max(entrance_height * 0.28, 1.9):
                        hero_cliff_shaped_caves.add(cave_name)
                        _record_pipeline_warning("hero_cliff_shaping_soft_accept", ridge_exc, object_name=cave_name)
                    else:
                        _record_pipeline_warning("hero_cliff_shaping", ridge_exc, object_name=cave_name)

        if "terrain_generated" not in steps_completed:
            early_result = {
                "status": "partial",
                "map_name": map_name,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "warnings": pipeline_warnings,
                "objects_created": created_objects,
                "locations": location_results,
                "interiors": interior_results,
                "budget_applied": budget,
                "quality_report": {
                    "validated_objects": [],
                    "warnings": [],
                    "failures": [],
                    "skipped": True,
                    "reason": "terrain generation failed before downstream worldbuilding",
                },
                "heightmap_export_path": None,
                "game_check_failures": [],
                "fbx_exported_files": [],
                "resumed_from_checkpoint": _CHKPT_LOADED,
                "checkpoint_dir": checkpoint_dir,
                "terrain_visual_profiles": [],
                "terrain_visual_verification": {
                    "status": "skipped",
                    "passed": False,
                    "required_profiles": [],
                    "failed_profiles": [],
                    "issues": [],
                    "capture_errors": [],
                    "screenshots": [],
                    "angle_labels": [],
                    "profile_results": [],
                    "reason": "terrain generation failed",
                },
                "approved_for_unity_export": False,
                "unity_export_status": "blocked_by_terrain_generation_failure",
                "next_steps": [
                    "Fix the terrain generation failure before attempting rivers, roads, vegetation, or export.",
                    "Do not trust any terrain screenshots from this run; no terrain object was generated.",
                ],
            }
            return await _with_screenshot(
                blender,
                early_result,
                capture_viewport,
                object_name=None,
            )

        # --- Step 3: Water bodies ---
        if water_cfg:
            terminal_water_plane_level: float | None = None
            terminal_river_point: list[float] | None = None
            terminal_prev_point: list[float] | None = None
            terminal_basin_center: list[float] | None = None
            terminal_basin_radius: float | None = None
            terminal_basin_aspect_y = 1.35
            pending_river_surfaces: list[dict[str, Any]] = []
            queued_waterfall_step_keys = {
                str(entry.get("step_key"))
                for entry in deferred_waterfalls
                if isinstance(entry, dict) and entry.get("step_key")
            }
            # Rivers
            for i, river in enumerate(water_cfg.get("rivers", [])):
                if f"river_{i}" in steps_completed:
                    continue
                try:
                    river_width_m = max(float(river.get("width", 5.0)), 4.0)
                    river_depth_m = max(
                        float(river.get("depth", max(river_width_m * 0.9, terrain_size * 0.012, 3.0))),
                        1.6,
                    )
                    source = _map_point_to_terrain_cell(
                        river.get("source", [10, 10]),
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                        terrain_location=terrain_location,
                    )
                    destination = _map_point_to_terrain_cell(
                        river.get("destination", [190, 190]),
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                        terrain_location=terrain_location,
                    )
                    river_waypoints = [
                        list(_map_point_to_terrain_cell(
                            waypoint,
                            terrain_size=terrain_size,
                            resolution=terrain_resolution,
                            terrain_location=terrain_location,
                        ))
                        for waypoint in river.get("waypoints", [])
                        if isinstance(waypoint, (list, tuple)) and len(waypoint) >= 2
                    ]
                    river_result = await blender.send_command("env_carve_river", {
                        "terrain_name": terrain_name,
                        "source": list(source),
                        "destination": list(destination),
                        "waypoints": river_waypoints,
                        "width": max(2, int(round(river_width_m))),
                        "depth": river_depth_m,
                        "seed": map_seed + i,
                    })
                    steps_completed.append(f"river_{i}")
                    river_path_points = []
                    if isinstance(river_result, dict):
                        river_path_points = list(river_result.get("path_points", []) or [])
                    if len(river_path_points) >= 2:
                        river_water_name = f"{map_name}_River_{i}"
                        configured_water_level = water_cfg.get("water_level")
                        explicit_river_water_level = river.get("water_level")
                        min_water_depth = max(river_depth_m * 0.42, 0.9)
                        river_bed_points = []
                        if isinstance(river_result, dict):
                            river_bed_points = list(river_result.get("bed_points", []) or [])
                        if len(river_bed_points) < len(river_path_points):
                            river_bed_points = [
                                [float(point[0]), float(point[1]), float(point[2]) - min_water_depth]
                                for point in river_path_points
                            ]
                        if len(river_path_points) >= 4:
                            river_path_points = _chaikin_smooth_path_points(river_path_points, passes=2)
                        if len(river_bed_points) >= 4:
                            river_bed_points = _chaikin_smooth_path_points(river_bed_points, passes=2)
                        river_water_level = (
                            float(explicit_river_water_level)
                            if explicit_river_water_level is not None
                            else float(river_path_points[-1][2])
                        )
                        if explicit_river_water_level is not None:
                            river_path_points = _blend_path_points_to_terminal_water_level(
                                river_path_points,
                                river_water_level,
                            )
                        terminal_river_point = list(river_path_points[-1])
                        terminal_prev_point = list(river_path_points[-2])
                        terminal_water_plane_level = (
                            float(configured_water_level)
                            if configured_water_level is not None
                            else float(river_path_points[-1][2])
                        )
                        pending_river_surfaces.append({
                            "index": i,
                            "name": river_water_name,
                            "path_points": river_path_points,
                            "bed_points": river_bed_points,
                            "water_level": float(river_water_level),
                            "width": max(river_width_m * 1.18, 3.0),
                            "cross_sections": 16,
                            "min_water_depth": min_water_depth,
                            "terminal_water_level": None,
                        })
                        waterfall_requested = _river_requests_waterfall(river)
                        waterfall_cfg = river.get("waterfall") if isinstance(river.get("waterfall"), dict) else {}
                        if not waterfall_cfg:
                            global_waterfalls = water_cfg.get("waterfalls", []) or []
                            if i < len(global_waterfalls) and isinstance(global_waterfalls[i], dict):
                                waterfall_cfg = global_waterfalls[i]
                        if waterfall_requested or waterfall_cfg:
                            placement = _derive_waterfall_placement_from_path(river_path_points)
                            if placement is not None:
                                waterfall_name = str(
                                    waterfall_cfg.get("name", f"{map_name}_Waterfall_{i}")
                                )
                                waterfall_step = f"waterfall_{i}"
                                if (
                                    waterfall_step not in steps_completed
                                    and waterfall_step not in queued_waterfall_step_keys
                                ):
                                    waterfall_height = max(
                                        float(waterfall_cfg.get("height", placement["height"])),
                                        3.0,
                                    )
                                    waterfall_width = max(
                                        float(waterfall_cfg.get("width", river_width_m * 1.12)),
                                        2.5,
                                    )
                                    deferred_waterfalls.append({
                                        "step_key": waterfall_step,
                                        "name": waterfall_name,
                                        "height": waterfall_height,
                                        "width": waterfall_width,
                                        "pool_radius": max(
                                            float(waterfall_cfg.get("pool_radius", waterfall_width * 1.55)),
                                            waterfall_width * 0.9,
                                        ),
                                        "num_steps": int(
                                            waterfall_cfg.get(
                                                "num_steps",
                                                max(1, min(5, int(round(waterfall_height / 3.0)))),
                                            )
                                        ),
                                        "has_cave_behind": bool(waterfall_cfg.get("has_cave_behind", False)),
                                        "seed": int(waterfall_cfg.get("seed", map_seed + 700 + i)),
                                        "facing_direction": list(
                                            waterfall_cfg.get(
                                                "facing_direction",
                                                placement["facing_direction"],
                                            )
                                        ),
                                        "location": list(
                                            waterfall_cfg.get(
                                                "location",
                                                [
                                                    float(placement["top_point"][0]),
                                                    float(placement["top_point"][1]),
                                                    float(placement["bottom_point"][2]),
                                                ],
                                            )
                                        ),
                                    })
                                    queued_waterfall_step_keys.add(waterfall_step)
                            else:
                                _record_pipeline_degradation(
                                    "waterfall_skipped_low_drop",
                                    f"waterfall_{i} skipped: river drop was too small for placement",
                                )
                except Exception as e:
                    steps_failed.append({"step": f"river_{i}", "error": str(e)})

            for waterfall_index, waterfall_cfg in enumerate(water_cfg.get("waterfalls", []) or []):
                if not isinstance(waterfall_cfg, dict):
                    continue
                waterfall_step = str(
                    waterfall_cfg.get("step_key", f"waterfall_explicit_{waterfall_index}")
                )
                if waterfall_step in steps_completed or waterfall_step in queued_waterfall_step_keys:
                    continue
                location_raw = waterfall_cfg.get("location")
                if not (isinstance(location_raw, (list, tuple)) and len(location_raw) >= 3):
                    continue
                facing_direction = waterfall_cfg.get("facing_direction", (0.0, -1.0))
                deferred_waterfalls.append({
                    "step_key": waterfall_step,
                    "name": str(waterfall_cfg.get("name", f"{map_name}_Waterfall_Explicit_{waterfall_index}")),
                    "height": max(float(waterfall_cfg.get("height", 6.0)), 3.0),
                    "width": max(float(waterfall_cfg.get("width", 4.0)), 2.5),
                    "pool_radius": max(float(waterfall_cfg.get("pool_radius", 6.0)), 2.5),
                    "num_steps": int(waterfall_cfg.get("num_steps", 3)),
                    "has_cave_behind": bool(waterfall_cfg.get("has_cave_behind", False)),
                    "seed": int(waterfall_cfg.get("seed", map_seed + 900 + waterfall_index)),
                    "facing_direction": list(facing_direction),
                    "location": [
                        float(location_raw[0]),
                        float(location_raw[1]),
                        float(location_raw[2]),
                    ],
                })
                queued_waterfall_step_keys.add(waterfall_step)

            # Water level (lakes/ocean)
            if "water_level" in water_cfg and "water_plane" not in steps_completed:
                try:
                    configured_water_level = water_cfg.get("water_level")
                    resolved_water_level = (
                        float(configured_water_level)
                        if configured_water_level is not None
                        else terminal_water_plane_level
                    )
                    if resolved_water_level is None:
                        resolved_water_level = float(water_cfg["water_level"])

                    # --- Terrain-aware water level validation ---
                    # Use the actual terrain mesh to verify the configured water_level
                    # makes physical sense (not floating above terrain or buried underground).
                    _water_validation_center_x = 0.0
                    _water_validation_center_y = 0.0
                    _water_validation_radius = max(terrain_size * 0.062, 12.0)
                    if terminal_river_point is not None:
                        _water_validation_center_x = float(terminal_river_point[0])
                        _water_validation_center_y = float(terminal_river_point[1])
                    elif isinstance(water_cfg.get("basin_center"), (list, tuple)) and len(water_cfg["basin_center"]) >= 2:
                        _water_validation_center_x = float(water_cfg["basin_center"][0])
                        _water_validation_center_y = float(water_cfg["basin_center"][1])
                    if isinstance(water_cfg.get("basin_radius"), (int, float)):
                        _water_validation_radius = max(float(water_cfg["basin_radius"]), _water_validation_radius)
                    try:
                        _natural = await _compute_natural_water_level(
                            blender,
                            terrain_name,
                            _water_validation_center_x,
                            _water_validation_center_y,
                            _water_validation_radius,
                            terrain_size=terrain_size,
                        )
                        _terrain_z_at_center = await _sample_terrain_height(
                            blender, terrain_name,
                            _water_validation_center_x,
                            _water_validation_center_y,
                        )
                        # Reject water level that floats >3m above local terrain
                        # or sits >5m below the basin floor (underground).
                        _above_terrain = resolved_water_level - _terrain_z_at_center
                        _below_floor = _natural["basin_floor"] - resolved_water_level
                        if _above_terrain > 3.0 or _below_floor > 5.0:
                            _old_wl = resolved_water_level
                            resolved_water_level = _natural["natural_level"]
                            logger.warning(
                                "compose_map: overriding water_level %.2f -> %.2f "
                                "(was %.1fm %s terrain at basin center; "
                                "basin_floor=%.2f, spill=%.2f, rim_min=%.2f)",
                                _old_wl,
                                resolved_water_level,
                                abs(_above_terrain) if _above_terrain > 3.0 else abs(_below_floor),
                                "above" if _above_terrain > 3.0 else "below",
                                _natural["basin_floor"],
                                _natural["spill_height"],
                                _natural["rim_min"],
                            )
                            _record_pipeline_degradation(
                                "water_level_overridden",
                                f"water_level overridden: {_old_wl:.2f} -> "
                                f"{resolved_water_level:.2f} (terrain mismatch)",
                            )
                    except Exception as _wl_validation_exc:
                        logger.debug(
                            "compose_map: water level terrain validation skipped: %s",
                            _wl_validation_exc,
                            exc_info=True,
                        )

                    if (
                        terminal_river_point is not None
                        and terminal_prev_point is not None
                        and "water_basin" not in steps_completed
                    ):
                        flow_dx = float(terminal_river_point[0]) - float(terminal_prev_point[0])
                        flow_dy = float(terminal_river_point[1]) - float(terminal_prev_point[1])
                        flow_len = max((flow_dx * flow_dx + flow_dy * flow_dy) ** 0.5, 1e-6)
                        flow_dx /= flow_len
                        flow_dy /= flow_len
                        river_width = max(
                            float((water_cfg.get("rivers") or [{}])[0].get("width", 6.0)),
                            4.0,
                        )
                        basin_radius = max(
                            float(water_cfg.get("basin_radius", max(river_width * 2.6, terrain_size * 0.062, 12.0))),
                            10.0,
                        )
                        basin_depth = max(
                            float(water_cfg.get("basin_depth", max(river_width * 0.34, terrain_size * 0.010, 2.4))),
                            1.2,
                        )
                        basin_center_override = water_cfg.get("basin_center")
                        if isinstance(basin_center_override, (list, tuple)) and len(basin_center_override) >= 2:
                            basin_center = [
                                float(basin_center_override[0]),
                                float(basin_center_override[1]),
                            ]
                        else:
                            basin_center = [
                                float(terminal_river_point[0]) + flow_dx * basin_radius * 0.3,
                                float(terminal_river_point[1]) + flow_dy * basin_radius * 0.24,
                            ]
                        basin_margin = max(basin_radius * 0.92, 18.0)
                        basin_center[0] = max(-terrain_size * 0.5 + basin_margin, min(terrain_size * 0.5 - basin_margin, basin_center[0]))
                        basin_center[1] = max(-terrain_size * 0.5 + basin_margin, min(terrain_size * 0.5 - basin_margin, basin_center[1]))
                        if terminal_prev_point is not None:
                            try:
                                inlet_mid_x = (
                                    float(terminal_river_point[0]) * 0.58
                                    + basin_center[0] * 0.42
                                )
                                inlet_mid_y = (
                                    float(terminal_river_point[1]) * 0.58
                                    + basin_center[1] * 0.42
                                )
                                await blender.send_command("terrain_spline_deform", {
                                    "object_name": terrain_name,
                                    "spline_points": [
                                        [float(terminal_prev_point[0]), float(terminal_prev_point[1]), resolved_water_level - basin_depth * 0.12],
                                        [float(terminal_river_point[0]), float(terminal_river_point[1]), resolved_water_level - basin_depth * 0.18],
                                        [inlet_mid_x, inlet_mid_y, resolved_water_level - basin_depth * 0.24],
                                        [basin_center[0], basin_center[1], resolved_water_level - basin_depth * 0.30],
                                    ],
                                    "mode": "carve",
                                    "width": max(basin_radius * 0.78, river_width * 2.2),
                                    "depth": max(basin_depth * 0.92, 1.4),
                                    "falloff": 0.90,
                                })
                            except Exception as basin_shelf_exc:
                                _record_pipeline_warning("water_basin_inlet", basin_shelf_exc, object_name=terrain_name)
                        lobe_offsets = [
                            (
                                basin_center[0] - flow_dy * basin_radius * 0.58 + flow_dx * basin_radius * 0.14,
                                basin_center[1] + flow_dx * basin_radius * 0.58 + flow_dy * basin_radius * 0.14,
                                basin_radius * 0.62,
                                basin_depth * 0.72,
                            ),
                            (
                                basin_center[0] + flow_dy * basin_radius * 0.42 + flow_dx * basin_radius * 0.28,
                                basin_center[1] - flow_dx * basin_radius * 0.42 + flow_dy * basin_radius * 0.28,
                                basin_radius * 0.48,
                                basin_depth * 0.58,
                            ),
                        ]
                        for lobe_index, (lobe_x, lobe_y, lobe_radius, lobe_depth) in enumerate(lobe_offsets):
                            try:
                                await blender.send_command("env_carve_water_basin", {
                                    "terrain_name": terrain_name,
                                    "center": [lobe_x, lobe_y],
                                    "water_level": resolved_water_level,
                                    "radius": max(lobe_radius, 6.0),
                                    "depth": max(lobe_depth, 1.1),
                                    "shore_width": max(basin_radius * 0.72, 10.0),
                                    "aspect_y": terminal_basin_aspect_y,
                                })
                            except Exception as basin_lobe_exc:
                                _record_pipeline_warning(
                                    f"water_basin_lobe_{lobe_index}",
                                    basin_lobe_exc,
                                    object_name=terrain_name,
                                )
                        await blender.send_command("env_carve_water_basin", {
                            "terrain_name": terrain_name,
                            "center": basin_center,
                            "water_level": resolved_water_level,
                            "radius": basin_radius,
                            "depth": basin_depth,
                            "shore_width": max(float(water_cfg.get("shore_width", basin_radius * 1.55)), basin_radius * 0.72),
                            "aspect_y": terminal_basin_aspect_y,
                        })
                        await _verify_basin_depth(
                            basin_center=basin_center,
                            resolved_water_level=float(resolved_water_level),
                            basin_depth=basin_depth,
                            basin_radius=basin_radius,
                            shore_width=max(float(water_cfg.get("shore_width", basin_radius * 1.55)), basin_radius * 0.72),
                            aspect_y=terminal_basin_aspect_y,
                        )
                        terminal_basin_center = basin_center
                        terminal_basin_radius = basin_radius
                        steps_completed.append("water_basin")
                        rim_angles = np.linspace(0.0, math.tau, 24, endpoint=False)
                        inlet_angle = math.atan2(flow_dy, flow_dx)
                        rim_points: list[list[float]] = []
                        bank_raise = max(basin_depth * 0.30, 2.0)
                        for angle in rim_angles:
                            delta = math.atan2(math.sin(angle - inlet_angle), math.cos(angle - inlet_angle))
                            if abs(delta) <= math.radians(36.0):
                                continue
                            rim_points.append([
                                basin_center[0] + math.cos(angle) * basin_radius * 1.10,
                                basin_center[1] + math.sin(angle) * basin_radius * terminal_basin_aspect_y * 1.08,
                                resolved_water_level + bank_raise * 0.78,
                            ])
                        if len(rim_points) >= 3:
                            rim_points.append(rim_points[0])
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": rim_points,
                                "mode": "raise",
                                "depth": bank_raise,
                                "width": max(basin_radius * 0.22, 5.2),
                                "falloff": 0.90,
                            })
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": rim_points,
                                "mode": "smooth",
                                "depth": 0.0,
                                "width": max(basin_radius * 0.28, 6.4),
                                "falloff": 0.95,
                            })
                            await _verify_basin_rim_containment(
                                rim_points=rim_points,
                                resolved_water_level=float(resolved_water_level),
                                bank_raise=bank_raise,
                                basin_radius=basin_radius,
                            )

                    for pending in pending_river_surfaces:
                        river_path_points = [list(point) for point in pending["path_points"]]
                        river_bed_points = [list(point) for point in pending.get("bed_points", [])]
                        river_water_level = float(pending["water_level"])
                        if terminal_basin_center is not None and len(river_path_points) >= 2:
                            basin_entry_x = terminal_basin_center[0] - flow_dx * basin_radius * 0.78
                            basin_entry_y = terminal_basin_center[1] - flow_dy * basin_radius * 0.78
                            await _verify_basin_inlet_depth(
                                river_tail=river_path_points[-1],
                                basin_entry=(basin_entry_x, basin_entry_y),
                                resolved_water_level=float(resolved_water_level),
                                basin_depth=basin_depth,
                                river_width=float((water_cfg.get("rivers") or [{}])[0].get("width", 6.0)),
                            )
                            river_path_points = _blend_path_points_to_terminal_water_level(
                                river_path_points,
                                resolved_water_level,
                            )
                            connector_start_index = max(0, len(river_path_points) - 3)
                            connector_start = river_path_points[connector_start_index]
                            if len(river_bed_points) < len(river_path_points):
                                river_bed_points = [
                                    [float(point[0]), float(point[1]), float(point[2]) - float(pending.get("min_water_depth", 0.9))]
                                    for point in river_path_points
                                ]
                            connector_bed_start = river_bed_points[min(connector_start_index, len(river_bed_points) - 1)]
                            basin_bed_level = float(resolved_water_level) - max(
                                float(pending.get("min_water_depth", 0.9)),
                                float(basin_depth) * 0.24,
                            )
                            connector_mid_a = [
                                connector_start[0] * 0.38 + basin_entry_x * 0.62,
                                connector_start[1] * 0.38 + basin_entry_y * 0.62,
                                connector_start[2] * 0.36 + float(resolved_water_level) * 0.64,
                            ]
                            connector_mid_b = [
                                river_path_points[-1][0] * 0.20 + basin_entry_x * 0.80,
                                river_path_points[-1][1] * 0.20 + basin_entry_y * 0.80,
                                river_path_points[-1][2] * 0.18 + float(resolved_water_level) * 0.82,
                            ]
                            connector_mid_a_bed = [
                                connector_mid_a[0],
                                connector_mid_a[1],
                                connector_bed_start[2] * 0.40 + basin_bed_level * 0.60,
                            ]
                            connector_mid_b_bed = [
                                connector_mid_b[0],
                                connector_mid_b[1],
                                connector_bed_start[2] * 0.18 + basin_bed_level * 0.82,
                            ]
                            river_path_points = (
                                river_path_points[: connector_start_index + 1]
                                + [connector_mid_a, connector_mid_b, [basin_entry_x, basin_entry_y, resolved_water_level]]
                            )
                            river_bed_points = (
                                river_bed_points[: connector_start_index + 1]
                                + [
                                    connector_mid_a_bed,
                                    connector_mid_b_bed,
                                    [basin_entry_x, basin_entry_y, basin_bed_level],
                                ]
                            )
                            river_water_level = float(resolved_water_level)
                            pending["terminal_water_level"] = float(resolved_water_level)
                        if len(river_path_points) >= 4:
                            river_path_points = _chaikin_smooth_path_points(river_path_points, passes=1)
                        if len(river_bed_points) >= 4:
                            river_bed_points = _chaikin_smooth_path_points(river_bed_points, passes=1)
                        pending["path_points"] = river_path_points
                        pending["bed_points"] = river_bed_points
                        pending["water_level"] = river_water_level

                    deferred_river_surfaces = [
                        existing
                        for existing in deferred_river_surfaces
                        if existing.get("name") not in {pending["name"] for pending in pending_river_surfaces}
                    ]
                    deferred_river_surfaces.extend(pending_river_surfaces)
                    deferred_water_body = {
                        "name": f"{map_name}_Water",
                        "water_level": float(resolved_water_level),
                        "mask_center": terminal_basin_center,
                        "mask_radius": (
                            float(terminal_basin_radius) * 0.96
                            if terminal_basin_radius is not None
                            else 0.0
                        ),
                        "mask_aspect_y": float(terminal_basin_aspect_y),
                    }
                except Exception as e:
                    steps_failed.append({"step": "water_plane", "error": str(e)})

            if pending_river_surfaces and "water_level" not in water_cfg:
                deferred_river_surfaces = [
                    existing
                    for existing in deferred_river_surfaces
                    if existing.get("name") not in {pending["name"] for pending in pending_river_surfaces}
                ]
                deferred_river_surfaces.extend(pending_river_surfaces)

            _save_chkpt()  # checkpoint after water

        # --- Step 5: Place locations ---
        _completed_locs = {s.replace("location_mesh_", "") for s in steps_completed if s.startswith("location_mesh_")}
        _LOC_HANDLERS = {
            "town": "world_generate_town",
            "castle": "world_generate_castle",
            "dungeon": "world_generate_dungeon",
            "cave": "world_generate_cave",
            "ruins": "world_generate_ruins",
            "building": "world_generate_building",
            "boss_arena": "world_generate_boss_arena",
            "settlement": "world_generate_settlement",
            "hearthvale": "world_generate_hearthvale",
            "interior": "world_generate_building",
        }
        for i, planned in enumerate(planned_locations):
            loc = planned["source"]
            loc_name = loc.get("name", str(i))
            if loc_name in _completed_locs:
                continue
            loc_type = loc.get("type", "town")
            handler = _LOC_HANDLERS.get(loc_type)
            if not handler:
                steps_failed.append({"step": f"location_{i}", "error": f"Unknown type: {loc_type}"})
                continue
            try:
                loc_params = _build_location_generation_params(
                    loc,
                    map_spec=spec,
                    map_seed=map_seed,
                    index=i,
                )
                if loc_type == "dungeon" and loc.get("floors"):
                    handler = "world_generate_multi_floor_dungeon"

                anchor_x, anchor_y = planned["anchor"]

                # Compute foundation profile BEFORE generating building
                loc_radius = float(planned.get("radius", 15.0))
                corner_heights = []
                anchor_z = 0.0
                if terrain_name:
                    for dx, dy in [(-loc_radius, -loc_radius), (loc_radius, -loc_radius),
                                   (-loc_radius, loc_radius), (loc_radius, loc_radius),
                                   (0.0, 0.0)]:
                        ch = await _sample_terrain_height(blender, terrain_name, anchor_x + dx, anchor_y + dy)
                        corner_heights.append(ch)
                    anchor_z = max(corner_heights) if corner_heights else 0.0

                    if loc_type != "cave":
                        # ARCH-021: Flatten terrain using flatten_terrain_zone (heightmap-aware)
                        # with spline deform as fallback for non-heightmap terrain objects.
                        _flatten_ok = False
                        try:
                            await blender.send_command("terrain_flatten_zone", {
                                "object_name": terrain_name,
                                "center_x": anchor_x,
                                "center_y": anchor_y,
                                "radius_x": loc_radius,
                                "radius_y": loc_radius,
                                "target_height": anchor_z,
                                "blend_distance": loc_radius * 0.5,
                            })
                            _flatten_ok = True
                        except Exception:
                            pass
                        if not _flatten_ok:
                            # Fallback: spline deform for non-heightmap terrain
                            try:
                                await blender.send_command("terrain_spline_deform", {
                                    "object_name": terrain_name,
                                    "spline_points": [
                                        [anchor_x - loc_radius, anchor_y - loc_radius, anchor_z],
                                        [anchor_x + loc_radius, anchor_y - loc_radius, anchor_z],
                                        [anchor_x + loc_radius, anchor_y + loc_radius, anchor_z],
                                        [anchor_x - loc_radius, anchor_y + loc_radius, anchor_z],
                                    ],
                                    "mode": "flatten",
                                    "falloff": 0.85,
                                    "width": loc_radius * 0.4,
                                })
                            except Exception:
                                pass  # Non-fatal

                        # Auto-compute foundation profile from terrain slope
                        if corner_heights and len(corner_heights) >= 5:
                            _min_h = min(corner_heights[:4])
                            _max_h = max(corner_heights[:4])
                            _height_diff = _max_h - _min_h
                            if _height_diff > 0.3:
                                loc_params["foundation_profile"] = {
                                    "foundation_height": _height_diff + 0.2,
                                    "side_heights": {
                                        # corners: [0]=(-r,-r), [1]=(+r,-r), [2]=(-r,+r), [3]=(+r,+r)
                                        "front": max(0.0, anchor_z - min(corner_heights[0], corner_heights[1])),
                                        "back":  max(0.0, anchor_z - min(corner_heights[2], corner_heights[3])),
                                        "left":  max(0.0, anchor_z - min(corner_heights[0], corner_heights[2])),
                                        "right": max(0.0, anchor_z - min(corner_heights[1], corner_heights[3])),
                                    },
                                    "retaining_sides": [
                                        side for side, h in [
                                            ("front", min(corner_heights[0], corner_heights[1])),
                                            ("back",  min(corner_heights[2], corner_heights[3])),
                                            ("left",  min(corner_heights[0], corner_heights[2])),
                                            ("right", min(corner_heights[1], corner_heights[3])),
                                        ]
                                        if anchor_z - h > 0.5
                                    ],
                                    "stair_wall": "front",
                                    "stair_steps": max(2, int(_height_diff / 0.25)),
                                }

                if loc_type == "cave":
                    cave_name = str(loc.get("name", f"Cave_{i}"))
                    entrance_width = float(loc.get("entrance_width", max(6.2, loc_radius * 0.38)))
                    entrance_height = float(loc.get("entrance_height", max(4.8, loc_radius * 0.28)))
                    entrance_depth = float(loc.get("entrance_depth", max(6.5, loc_radius * 0.48)))
                    anchor_override = hero_cave_anchor_overrides.get(cave_name)
                    if anchor_override is not None:
                        anchor_x = float(anchor_override["x"])
                        anchor_y = float(anchor_override["y"])
                        anchor_z = float(anchor_override.get("z", anchor_z))
                    if cave_name not in hero_cliff_shaped_caves:
                        _record_pipeline_warning(
                            "hero_cliff_shaping_missing",
                            RuntimeError(f"{cave_name}: proceeding from natural relief without a hero ridge raise"),
                            object_name=cave_name,
                        )
                    relief_profile: dict[str, Any] | None = None
                    if terrain_name:
                        retargeted_anchor = anchor_override or await _retarget_cave_anchor_to_relief(
                            blender,
                            terrain_name,
                            anchor_x=anchor_x,
                            anchor_y=anchor_y,
                            terrain_size=terrain_size,
                            terrain_location=terrain_location,
                            search_radius=max(loc_radius * 0.72, entrance_width * 1.55, 12.0),
                            sample_radius=max(entrance_width * 0.88, 7.5),
                        )
                        anchor_x = float(retargeted_anchor["x"])
                        anchor_y = float(retargeted_anchor["y"])
                        anchor_z = float(retargeted_anchor["z"])
                        relief_profile = await _sample_terrain_relief_profile(
                            blender,
                            terrain_name,
                            anchor_x,
                            anchor_y,
                            radius=max(entrance_width * 0.78, loc_radius * 0.54, 9.0),
                            sample_count=8,
                            fallback_vector=(
                                terrain_location[0] - anchor_x,
                                terrain_location[1] - anchor_y,
                            ),
                        )
                        required_relief = max(0.8, entrance_height * 0.12)
                        if (
                            relief_profile["relief_span"] < required_relief
                            and float(retargeted_anchor.get("slope_drop", 0.0)) < max(entrance_height * 0.24, 1.8)
                        ):
                            raise RuntimeError(f"{cave_name}: terrain relief too weak for a cliff cave")
                        tunnel_x, tunnel_y = relief_profile["uphill_vector"]
                    else:
                        approach_x = terrain_location[0] - anchor_x
                        approach_y = terrain_location[1] - anchor_y
                        approach_len = math.hypot(approach_x, approach_y)
                        if approach_len <= 1e-6:
                            approach_x, approach_y, approach_len = 0.0, 1.0, 1.0
                        approach_x /= approach_len
                        approach_y /= approach_len
                        tunnel_x = -approach_x
                        tunnel_y = -approach_y
                    face_x, face_y = -tunnel_x, -tunnel_y
                    perp_x, perp_y = -tunnel_y, tunnel_x
                    if terrain_name:
                        lip_offset = max(entrance_width * 0.24, 3.2)
                        shifted_x, shifted_y = _clamp_world_xy(
                            anchor_x + face_x * lip_offset,
                            anchor_y + face_y * lip_offset,
                            terrain_size=terrain_size,
                            terrain_location=terrain_location,
                            margin=max(loc_radius * 0.42, 10.0),
                        )
                        anchor_x = float(shifted_x)
                        anchor_y = float(shifted_y)
                        anchor_z = await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y)
                        if relief_profile is not None:
                            relief_profile = await _sample_terrain_relief_profile(
                                blender,
                                terrain_name,
                                anchor_x,
                                anchor_y,
                                radius=max(entrance_width * 0.78, loc_radius * 0.54, 9.0),
                                sample_count=8,
                                fallback_vector=(
                                    terrain_location[0] - anchor_x,
                                    terrain_location[1] - anchor_y,
                                ),
                            )
                            tunnel_x, tunnel_y = relief_profile["uphill_vector"]
                            face_x, face_y = -tunnel_x, -tunnel_y
                            perp_x, perp_y = -tunnel_y, tunnel_x
                    entrance_rotation_z = math.atan2(-face_x, face_y)
                    entrance_name = f"{cave_name}_Entrance"
                    chamber_name = f"{cave_name}_Chamber"
                    cave_material_key = str(
                        loc.get(
                            "material_key",
                            "wet_rock"
                            if str(terrain_cfg.get("preset", "")).strip().lower() in {"coastal", "swamp"}
                            else "cliff_rock",
                        )
                    )
                    chamber_material_key = str(loc.get("chamber_material_key", "wet_rock"))

                    if terrain_name:
                        pre_carve_anchor_z = anchor_z
                        cave_apron_center_x = anchor_x + face_x * max(entrance_width * 0.18, 1.5)
                        cave_apron_center_y = anchor_y + face_y * max(entrance_width * 0.18, 1.5)
                        apron_radius_x = max(entrance_width * 0.24, 2.0)
                        apron_radius_y = max(entrance_width * 0.16, 1.4)
                        try:
                            await blender.send_command("terrain_flatten_zone", {
                                "object_name": terrain_name,
                                "center_x": cave_apron_center_x,
                                "center_y": cave_apron_center_y,
                                "radius_x": apron_radius_x,
                                "radius_y": apron_radius_y,
                                "target_height": anchor_z - 0.08,
                                "blend_distance": max(entrance_width * 0.10, 0.7),
                            })
                        except Exception as cave_apron_exc:
                            raise RuntimeError(f"{cave_name}: cave apron flatten failed") from cave_apron_exc

                        tunnel_curve = [
                            [anchor_x + face_x * max(entrance_width * 0.34, 2.4), anchor_y + face_y * max(entrance_width * 0.34, 2.4), anchor_z - 0.04],
                            [anchor_x, anchor_y, anchor_z - 0.34],
                            [anchor_x + tunnel_x * max(entrance_depth * 0.56, 6.0), anchor_y + tunnel_y * max(entrance_depth * 0.56, 6.0), anchor_z - max(entrance_height * 0.60, 4.0)],
                            [anchor_x + tunnel_x * max(entrance_depth * 1.08, 10.0), anchor_y + tunnel_y * max(entrance_depth * 1.08, 10.0), anchor_z - max(entrance_height * 0.96, 6.2)],
                        ]
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": tunnel_curve,
                                "mode": "smooth",
                                "falloff": 0.90,
                                "width": max(entrance_width * 0.56, 3.4),
                            })
                        except Exception as cave_flatten_exc:
                            raise RuntimeError(f"{cave_name}: cave tunnel pre-smooth failed") from cave_flatten_exc
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": tunnel_curve,
                                "mode": "carve",
                                "depth": max(entrance_height * 0.96, entrance_depth * 0.28, 4.6),
                                "falloff": 0.84,
                                "width": max(entrance_width * 0.68, 4.2),
                            })
                        except Exception as cave_carve_exc:
                            raise RuntimeError(f"{cave_name}: cave tunnel carve failed") from cave_carve_exc
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": [
                                    [float(tunnel_curve[1][0]), float(tunnel_curve[1][1]), float(tunnel_curve[1][2]) - 0.38],
                                    [float(tunnel_curve[2][0]), float(tunnel_curve[2][1]), float(tunnel_curve[2][2]) - 0.72],
                                    [float(tunnel_curve[3][0]), float(tunnel_curve[3][1]), float(tunnel_curve[3][2]) - 0.58],
                                ],
                                "mode": "carve",
                                "depth": max(entrance_height * 0.44, 2.6),
                                "falloff": 0.78,
                                "width": max(entrance_width * 0.58, 4.0),
                            })
                        except Exception as cave_alcove_exc:
                            _record_pipeline_warning("cave_alcove_shape", cave_alcove_exc, object_name=cave_name)
                        rim_center_x = anchor_x + tunnel_x * max(entrance_width * 0.14, 1.2)
                        rim_center_y = anchor_y + tunnel_y * max(entrance_width * 0.14, 1.2)
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": [
                                    [
                                        rim_center_x - perp_x * entrance_width * 0.72,
                                        rim_center_y - perp_y * entrance_width * 0.72,
                                        anchor_z + entrance_height * 0.28,
                                    ],
                                    [
                                        rim_center_x,
                                        rim_center_y,
                                        anchor_z + entrance_height * 0.78,
                                    ],
                                    [
                                        rim_center_x + perp_x * entrance_width * 0.72,
                                        rim_center_y + perp_y * entrance_width * 0.72,
                                        anchor_z + entrance_height * 0.28,
                                    ],
                                ],
                                "mode": "raise",
                                "depth": max(entrance_height * 0.54, 3.0),
                                "falloff": 0.80,
                                "width": max(entrance_width * 0.94, 5.0),
                            })
                        except Exception as cave_brow_exc:
                            _record_pipeline_warning("cave_brow_shape", cave_brow_exc, object_name=cave_name)
                        for side_sign in (-1.0, 1.0):
                            side_x = anchor_x + perp_x * entrance_width * 0.62 * side_sign
                            side_y = anchor_y + perp_y * entrance_width * 0.62 * side_sign
                            try:
                                await blender.send_command("terrain_spline_deform", {
                                    "object_name": terrain_name,
                                    "spline_points": [
                                        [
                                            side_x + face_x * entrance_width * 0.08,
                                            side_y + face_y * entrance_width * 0.08,
                                            anchor_z + entrance_height * 0.18,
                                        ],
                                        [
                                            side_x + tunnel_x * entrance_depth * 0.24,
                                            side_y + tunnel_y * entrance_depth * 0.24,
                                            anchor_z + entrance_height * 0.54,
                                        ],
                                    ],
                                    "mode": "raise",
                                    "depth": max(entrance_height * 0.40, 2.4),
                                    "falloff": 0.82,
                                    "width": max(entrance_width * 0.52, 3.8),
                                })
                            except Exception as cave_buttress_exc:
                                _record_pipeline_warning("cave_sidewall_shape", cave_buttress_exc, object_name=cave_name)
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": tunnel_curve[:3],
                                "mode": "smooth",
                                "depth": 0.0,
                                "falloff": 0.94,
                                "width": max(entrance_width * 0.88, 4.8),
                            })
                        except Exception as cave_mouth_smooth_exc:
                            _record_pipeline_warning("cave_mouth_blend", cave_mouth_smooth_exc, object_name=cave_name)
                        try:
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": tunnel_curve[:3],
                                "mode": "carve",
                                "depth": max(entrance_height * 0.70, 4.2),
                                "falloff": 0.82,
                                "width": max(entrance_width * 0.62, 3.8),
                            })
                        except Exception as cave_shadow_core_exc:
                            _record_pipeline_warning("cave_shadow_core", cave_shadow_core_exc, object_name=cave_name)
                        try:
                            anchor_z = await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y)
                        except Exception as cave_resample_exc:
                            raise RuntimeError(f"{cave_name}: cave anchor resample failed") from cave_resample_exc
                        if relief_profile is not None:
                            min_cave_floor = float(relief_profile["center_height"]) - max(entrance_height * 1.10, 8.0)
                            if anchor_z < min_cave_floor:
                                try:
                                    catastrophic_patch = await _stabilize_hero_terrain_patch(
                                        blender,
                                        terrain_name,
                                        center_x=anchor_x,
                                        center_y=anchor_y,
                                        radius=max(entrance_width * 2.25, 24.0),
                                        floor_z=min_cave_floor,
                                        ceiling_z=float(relief_profile["center_height"]) + max(entrance_height * 0.45, 3.6),
                                        blend=0.98,
                                    )
                                    if int(catastrophic_patch.get("affected_vertices", 0)) > 0:
                                        steps_completed.append(f"terrain_catastrophic_clamp_{cave_name}")
                                    anchor_z = max(
                                        min_cave_floor,
                                        await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y),
                                    )
                                except Exception as cave_floor_exc:
                                    _record_pipeline_warning("cave_catastrophic_clamp", cave_floor_exc, object_name=cave_name)
                                    anchor_z = max(anchor_z, min_cave_floor)
                        if relief_profile is not None and anchor_z > relief_profile["center_height"] + 0.35:
                            try:
                                await blender.send_command("terrain_spline_deform", {
                                    "object_name": terrain_name,
                                    "spline_points": tunnel_curve[:3],
                                    "mode": "carve",
                                    "depth": max(entrance_depth * 0.20, 1.2),
                                    "falloff": 0.95,
                                    "width": max(entrance_width * 0.86, 4.2),
                                })
                                anchor_z = await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y)
                            except Exception as cave_retry_exc:
                                _record_pipeline_warning("cave_lip_retry", cave_retry_exc, object_name=cave_name)
                        if relief_profile is not None and anchor_z > relief_profile["center_height"] + 0.35:
                            sink_amount = float(pre_carve_anchor_z) - float(anchor_z)
                            if sink_amount < max(0.45, entrance_height * 0.05):
                                raise RuntimeError(f"{cave_name}: cave deformation did not sink below the cliff lip")
                            _record_pipeline_warning(
                                "cave_lip_soft_accept",
                                RuntimeError(
                                    f"{cave_name}: accepting cave lip after {sink_amount:.2f}m sink even though the anchor remains high"
                                ),
                                object_name=cave_name,
                            )
                        try:
                            cave_patch_fix = await _stabilize_hero_terrain_patch(
                                blender,
                                terrain_name,
                                center_x=anchor_x + tunnel_x * max(entrance_depth * 0.58, 7.0),
                                center_y=anchor_y + tunnel_y * max(entrance_depth * 0.58, 7.0),
                                radius=max(entrance_width * 1.46, 10.0),
                                floor_z=anchor_z - max(entrance_height * 1.04, 6.2),
                                blend=0.92,
                            )
                            if int(cave_patch_fix.get("affected_vertices", 0)) > 0:
                                steps_completed.append(f"terrain_patch_fix_{cave_name}")
                        except Exception as cave_patch_exc:
                            _record_pipeline_warning("cave_patch_fix", cave_patch_exc, object_name=cave_name)
                        try:
                            cave_mouth_clamp = await _stabilize_hero_terrain_patch(
                                blender,
                                terrain_name,
                                center_x=anchor_x,
                                center_y=anchor_y,
                                radius=max(entrance_width * 2.10, 22.0),
                                floor_z=anchor_z - max(entrance_height * 1.40, 12.0),
                                ceiling_z=anchor_z + max(entrance_height * 0.60, 4.4),
                                blend=0.96,
                            )
                            if int(cave_mouth_clamp.get("affected_vertices", 0)) > 0:
                                steps_completed.append(f"terrain_mouth_clamp_{cave_name}")
                        except Exception as cave_mouth_clamp_exc:
                            _record_pipeline_warning("cave_mouth_clamp", cave_mouth_clamp_exc, object_name=cave_name)

                    entrance_result = {
                        "status": "terrain_carved",
                        "terrain_name": terrain_name,
                        "name": entrance_name,
                        "anchor": [round(anchor_x, 3), round(anchor_y, 3), round(anchor_z, 3)],
                        "rotation_z": round(float(entrance_rotation_z), 6),
                        "material_key": cave_material_key,
                        "surface_mode": "terrain_carved",
                    }

                    loc_params["name"] = chamber_name
                    loc_params["width"] = int(max(16, min(int(loc_params.get("width", 24)), 22)))
                    loc_params["height"] = int(max(16, min(int(loc_params.get("height", 24)), 22)))
                    loc_params["cell_size"] = float(loc.get("cell_size", 0.92))
                    loc_params["wall_height"] = float(loc.get("wall_height", max(4.6, loc_radius * 0.18)))

                    loc_result = await blender.send_command(handler, loc_params)

                    chamber_offset = max(entrance_depth * 0.72, loc_radius * 0.40, 6.2)
                    chamber_x = anchor_x + tunnel_x * chamber_offset
                    chamber_y = anchor_y + tunnel_y * chamber_offset
                    chamber_surface_z = anchor_z
                    if terrain_name:
                        try:
                            chamber_surface_z = await _sample_terrain_height(blender, terrain_name, chamber_x, chamber_y)
                        except Exception as chamber_surface_exc:
                            _record_pipeline_warning("cave_chamber_surface_resample", chamber_surface_exc, object_name=chamber_name)
                        try:
                            connector_curve = [
                                [float(tunnel_curve[-2][0]), float(tunnel_curve[-2][1]), float(tunnel_curve[-2][2]) - 0.35],
                                [float(tunnel_curve[-1][0]), float(tunnel_curve[-1][1]), float(tunnel_curve[-1][2]) - 0.45],
                                [
                                    chamber_x,
                                    chamber_y,
                                    chamber_surface_z - max(entrance_height * 0.58, 3.6),
                                ],
                            ]
                            await blender.send_command("terrain_spline_deform", {
                                "object_name": terrain_name,
                                "spline_points": connector_curve,
                                "mode": "carve",
                                "depth": max(entrance_height * 0.52, 2.8),
                                "falloff": 0.90,
                                "width": max(entrance_width * 0.92, 4.4),
                            })
                        except Exception as cave_connector_exc:
                            _record_pipeline_warning("cave_connector_carve", cave_connector_exc, object_name=chamber_name)
                    chamber_burial = max(entrance_height * 0.42, entrance_depth * 0.18, loc_radius * 0.16, 5.8)
                    chamber_position = (
                        chamber_x,
                        chamber_y,
                        chamber_surface_z - chamber_burial,
                    )
                    try:
                        await _position_generated_object(
                            blender,
                            chamber_name,
                            chamber_position,
                        )
                        try:
                            await blender.send_command("material_create_procedural", {
                                "object_name": chamber_name,
                                "material_key": chamber_material_key,
                                "name": f"{chamber_name}_Surface",
                            })
                        except Exception as chamber_mat_exc:
                            _record_pipeline_warning("cave_chamber_material", chamber_mat_exc, object_name=chamber_name)
                        try:
                            await blender.send_command("set_visibility", {
                                "name": chamber_name,
                                "visible": False,
                                "render_visible": False,
                            })
                        except Exception as chamber_hide_exc:
                            _record_pipeline_warning("cave_chamber_hide", chamber_hide_exc, object_name=chamber_name)
                        steps_completed.append(f"location_placed_{loc.get('name', i)}")
                    except Exception as placement_exc:
                        steps_failed.append({
                            "step": f"location_place_{loc.get('name', i)}",
                            "error": str(placement_exc),
                        })
                    steps_completed.append(f"location_mesh_{loc.get('name', i)}")
                    created_objects.append(chamber_name)
                    location_results.append({
                        "name": cave_name,
                        "type": loc_type,
                        "anchor": [round(anchor_x, 3), round(anchor_y, 3), round(anchor_z, 3)],
                        "radius": planned["radius"],
                        "layout_brief": loc_params.get("layout_brief", ""),
                        "site_profile": loc_params.get("site_profile", ""),
                        "supporting_objects": [chamber_name],
                        "result": {
                            "entrance": entrance_result,
                            "chamber": loc_result if isinstance(loc_result, dict) else str(loc_result)[:200],
                        },
                    })
                    continue

                # Generate building WITH foundation profile included
                loc_result = await blender.send_command(handler, loc_params)

                try:
                    await _position_generated_object(
                        blender,
                        loc_params["name"],
                        (anchor_x, anchor_y, anchor_z),
                    )
                    steps_completed.append(f"location_placed_{loc.get('name', i)}")
                except Exception as placement_exc:
                    steps_failed.append({
                        "step": f"location_place_{loc.get('name', i)}",
                        "error": str(placement_exc),
                    })
                # Track that the location mesh was generated (even if positioning failed)
                steps_completed.append(f"location_mesh_{loc.get('name', i)}")
                created_objects.append(loc_params["name"])
                location_results.append({
                    "name": loc_params["name"],
                    "type": loc_type,
                    "anchor": [round(anchor_x, 3), round(anchor_y, 3), round(anchor_z, 3)],
                    "radius": planned["radius"],
                    "layout_brief": loc_params.get("layout_brief", ""),
                    "site_profile": loc_params.get("site_profile", ""),
                    "result": loc_result if isinstance(loc_result, dict) else str(loc_result)[:200],
                })
            except Exception as e:
                steps_failed.append({"step": f"location_{loc.get('name', i)}", "error": str(e)})

        _save_chkpt()  # checkpoint after locations

        # --- Step 6: Biome paint ---
        biome = spec.get("biome")
        if biome:
            if "biome_painted" not in steps_completed:
                try:
                    await blender.send_command("env_paint_terrain", {
                        "name": terrain_name,
                        "height_scale": terrain_cfg.get("height_scale", 20.0),
                    })
                    await blender.send_command("terrain_create_biome_material", {
                        "biome_name": biome,
                        "object_name": terrain_name,
                    })
                    steps_completed.append("biome_painted")
                except Exception as e:
                    steps_failed.append({"step": "biome_paint", "error": str(e)})

            if "lighting_ready" not in steps_completed:
                try:
                    await blender.send_command("setup_dark_fantasy_lighting", {
                        "object_name": terrain_name,
                        "preset": _lighting_preset_for_biome(biome),
                    })
                    steps_completed.append("lighting_ready")
                except Exception as e:
                    steps_failed.append({"step": "lighting", "error": str(e)})
        else:
            if "terrain_review_surface" not in steps_completed:
                try:
                    await blender.send_command("env_paint_terrain", {
                        "name": terrain_name,
                        "height_scale": terrain_cfg.get("height_scale", 20.0),
                    })
                    await blender.send_command("terrain_create_biome_material", {
                        "biome_name": _terrain_review_biome_name(terrain_cfg.get("preset", "hills")),
                        "object_name": terrain_name,
                    })
                    steps_completed.append("terrain_review_surface")
                except Exception as e:
                    _record_pipeline_warning("terrain_review_surface", e, object_name=terrain_name)
        if not biome and "lighting_ready" not in steps_completed:
            try:
                await blender.send_command("setup_dark_fantasy_lighting", {
                    "object_name": terrain_name,
                    "preset": "terrain_review",
                })
                steps_completed.append("lighting_ready")
            except Exception as e:
                _record_pipeline_warning("lighting_review_setup", e, object_name=terrain_name)

        if "biome_painted" in steps_completed or "lighting_ready" in steps_completed:
            _save_chkpt()  # checkpoint after biome+lighting

        # --- Step 6.25: Roads (after terrain mutations and biome surfacing) ---
        await _generate_roads_after_terrain_mutations()
        _save_chkpt()  # checkpoint after roads

        if terrain_name and "hero_final_cleanup" not in steps_completed:
            try:
                final_cleanup = await _temper_hero_peak_outliers(
                    blender,
                    terrain_name,
                    percentile=0.996,
                    blend=0.88,
                    prominence_threshold=4.0,
                    passes=2,
                )
                if int(final_cleanup.get("affected_vertices", 0)) > 0:
                    steps_completed.append("hero_final_cleanup")
                    _save_chkpt()
            except Exception as final_cleanup_exc:
                _record_pipeline_warning("hero_final_cleanup", final_cleanup_exc, object_name=terrain_name)

        # --- Step 6.5: Emit visible water only after terrain is frozen ---
        if deferred_river_surfaces or deferred_water_body or deferred_waterfalls:
            await _emit_deferred_water_surfaces()
            _save_chkpt()

        terrain_visual_profiles = _normalize_validation_profiles(spec.get("terrain_visual_profiles"))
        if not terrain_visual_profiles:
            terrain_visual_profiles = _derive_terrain_validation_profiles(
                map_spec=spec,
                terrain_result=terrain_result_payload,
                object_names=created_objects,
                location_results=location_results,
            )

        # --- Step 7: Base terrain visual verification (before clutter) ---
        if terrain_name and "terrain_base_visual_verified" not in steps_completed:
            terrain_base_verification = await _run_terrain_visual_gate(
                blender,
                map_spec=spec,
                terrain_result=terrain_result_payload,
                object_names=created_objects,
                location_results=location_results,
                validation_profiles=terrain_visual_profiles,
                min_score=int(spec.get("terrain_visual_min_score", 60)),
                screenshot_prefix=f"{map_name}_terrain_base_gate",
                object_name=terrain_name,
            )
            if terrain_base_verification.get("passed", False):
                steps_completed.append("terrain_base_visual_verified")
                _save_chkpt()
            else:
                failed_profiles = terrain_base_verification.get("failed_profiles", terrain_visual_profiles)
                steps_failed.append({
                    "step": "terrain_visual_verification",
                    "error": "Terrain base visual verification failed for "
                    + (", ".join(failed_profiles) if failed_profiles else "terrain_readability"),
                })
                _save_chkpt()
                early_result = {
                    "status": "partial",
                    "map_name": map_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "warnings": pipeline_warnings,
                    "objects_created": created_objects,
                    "locations": location_results,
                    "interiors": interior_results,
                    "budget_applied": budget,
                    "quality_report": {
                        "validated_objects": [],
                        "warnings": [],
                        "failures": [],
                        "skipped": True,
                        "reason": "terrain base visual verification blocked vegetation and props",
                    },
                    "heightmap_export_path": None,
                    "game_check_failures": [],
                    "fbx_exported_files": [],
                    "resumed_from_checkpoint": _CHKPT_LOADED,
                    "checkpoint_dir": checkpoint_dir,
                    "terrain_visual_profiles": terrain_visual_profiles,
                    "terrain_visual_verification": terrain_base_verification,
                    "pipeline_degradations": pipeline_degradations,
                    "terrain_runtime_diagnostics": terrain_runtime_diagnostics,
                    "waterfall_runtime_diagnostics": waterfall_runtime_diagnostics,
                    "approved_for_unity_export": False,
                    "unity_export_status": "blocked_by_base_visual_verification",
                    "next_steps": [
                        "Fix the terrain base before adding vegetation, props, or export.",
                        "Review the terrain screenshots; this run intentionally stopped before clutter dressing.",
                    ],
                }
                return await _with_screenshot(blender, early_result, capture_viewport, object_name=terrain_name)

        # --- Step 8: Vegetation scatter ---
        veg_cfg = spec.get("vegetation", {})
        if veg_cfg and "vegetation_scattered" not in steps_completed:
            try:
                veg_rules = _normalize_vegetation_rules(veg_cfg, str(biome or ""))
                await blender.send_command("env_scatter_vegetation", {
                    "terrain_name": terrain_name,
                    "rules": veg_rules,
                    "min_distance": veg_cfg.get("min_distance", 2.0),
                    "seed": map_seed + 300,
                    "max_instances": min(
                        int(veg_cfg.get("max_instances", 5000)),
                        int(budget["vegetation_max_instances"]),
                    ),
                })
                steps_completed.append("vegetation_scattered")
            except Exception as e:
                steps_failed.append({"step": "vegetation", "error": str(e)})

        if "vegetation_scattered" in steps_completed:
            _save_chkpt()  # checkpoint after vegetation

        # --- Step 9: Prop scatter ---
        if spec.get("props", True) and "props_scattered" not in steps_completed:
            try:
                scatter_buildings = [
                    {
                        "type": loc["type"],
                        "position": loc["anchor"][:2],
                        "footprint": [max(8.0, loc["radius"] * 0.8), max(8.0, loc["radius"] * 0.8)],
                    }
                    for loc in location_results
                ]
                if not scatter_buildings:
                    # No locations = wilderness map, skip contextual prop scatter gracefully
                    steps_completed.append("props_scattered")
                else:
                    await blender.send_command("env_scatter_props", {
                        "area_name": terrain_name,
                        "buildings": scatter_buildings,
                        "prop_density": round(
                            float(spec.get("prop_density", 0.3)) * float(budget["prop_density_scale"]),
                            4,
                        ),
                        "seed": map_seed + 400,
                    })
                    steps_completed.append("props_scattered")
            except Exception as e:
                steps_failed.append({"step": "props", "error": str(e)})

        if "props_scattered" in steps_completed:
            _save_chkpt()  # checkpoint after props

        # --- Step 10: Generate interiors for key buildings ---
        if "interiors_generated" not in steps_completed:
            if not interior_results:  # SAFE-02: Only reset if empty (not loaded from checkpoint)
                interior_results = []
            for loc in spec.get("locations", []):
                if loc.get("interiors"):
                    for room_spec in loc["interiors"]:
                        try:
                            int_result = await blender.send_command("world_generate_linked_interior", {
                                "name": f"{loc.get('name', 'Loc')}_Interior",
                                "interior_rooms": room_spec.get("rooms", []),
                                "door_positions": room_spec.get("doors", []),
                                "seed": map_seed + 500,
                            })
                            interior_results.append({
                                "location": loc.get("name"),
                                "result": int_result if isinstance(int_result, dict) else str(int_result)[:200],
                            })
                            steps_completed.append(f"interior_{loc.get('name')}")
                        except Exception as e:
                            steps_failed.append({"step": f"interior_{loc.get('name')}", "error": str(e)})

            if interior_results:
                steps_completed.append("interiors_generated")
                _save_chkpt()  # checkpoint after interiors

        if terrain_name and "terrain_visual_verified" in steps_completed:
            terrain_visual_verification = {
                "status": "success",
                "passed": True,
                "required_profiles": terrain_visual_profiles,
                "failed_profiles": [],
                "issues": [],
                "capture_errors": [],
                "screenshots": [],
                "angle_labels": [label for _, _, label in _AAA_CAMERA_ANGLES],
                "profile_results": [],
                "skipped": True,
                "reason": "terrain visual verification already completed in checkpoint state",
            }

        # --- Step 11: Mandatory terrain visual verification ---
        if terrain_name and "terrain_visual_verified" not in steps_completed:
            terrain_visual_verification = await _run_terrain_visual_gate(
                blender,
                map_spec=spec,
                terrain_result=terrain_result_payload,
                object_names=created_objects,
                location_results=location_results,
                validation_profiles=terrain_visual_profiles,
                min_score=int(spec.get("terrain_visual_min_score", 60)),
                screenshot_prefix=f"{map_name}_terrain_gate",
                object_name=terrain_name,
            )
            terrain_visual_profiles = list(terrain_visual_verification.get("required_profiles", terrain_visual_profiles))
            if terrain_visual_verification.get("passed", False):
                steps_completed.append("terrain_visual_verified")
                _save_chkpt()
            else:
                failed_profiles = terrain_visual_verification.get("failed_profiles", terrain_visual_profiles)
                failure_label = ", ".join(failed_profiles) if failed_profiles else "terrain_readability"
                steps_failed.append({
                    "step": "terrain_visual_verification",
                    "error": f"Terrain visual verification failed for {failure_label}",
                })
                _save_chkpt()
                early_result = {
                    "status": "partial",
                    "map_name": map_name,
                    "steps_completed": steps_completed,
                    "steps_failed": steps_failed,
                    "warnings": pipeline_warnings,
                    "objects_created": created_objects,
                    "locations": location_results,
                    "interiors": interior_results,
                    "budget_applied": budget,
                    "quality_report": {
                        "validated_objects": [],
                        "warnings": [],
                        "failures": [],
                        "skipped": True,
                        "reason": "terrain visual verification blocked export",
                    },
                    "heightmap_export_path": None,
                    "game_check_failures": [],
                    "fbx_exported_files": [],
                    "resumed_from_checkpoint": _CHKPT_LOADED,
                    "checkpoint_dir": checkpoint_dir,
                    "terrain_visual_profiles": terrain_visual_profiles,
                    "terrain_visual_verification": terrain_visual_verification,
                    "pipeline_degradations": pipeline_degradations,
                    "terrain_runtime_diagnostics": terrain_runtime_diagnostics,
                    "waterfall_runtime_diagnostics": waterfall_runtime_diagnostics,
                    "approved_for_unity_export": False,
                    "unity_export_status": "blocked_by_visual_verification",
                    "next_steps": [
                        "Review the terrain screenshots and fix the failed terrain visual profiles before exporting.",
                        "Run asset_pipeline action=aaa_verify with the reported validation_profile if you need a focused rerun.",
                        "Do not package or export this map until terrain_visual_verified passes.",
                    ],
                }
                return await _with_screenshot(blender, early_result, capture_viewport, object_name=terrain_name)

        if terrain_name and terrain_visual_verification and terrain_visual_verification.get("passed", False) and not auto_export_unity:
            review_result = {
                "status": "review_required",
                "map_name": map_name,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "warnings": pipeline_warnings,
                "objects_created": created_objects,
                "locations": location_results,
                "interiors": interior_results,
                "budget_applied": budget,
                "quality_report": {
                    "validated_objects": [],
                    "warnings": [],
                    "failures": [],
                    "skipped": True,
                    "reason": "Waiting for Blender visual approval before Unity export",
                },
                "heightmap_export_path": None,
                "game_check_failures": [],
                "fbx_exported_files": [],
                "resumed_from_checkpoint": _CHKPT_LOADED,
                "checkpoint_dir": checkpoint_dir,
                "terrain_visual_profiles": terrain_visual_profiles,
                "terrain_visual_verification": terrain_visual_verification,
                "pipeline_degradations": pipeline_degradations,
                "terrain_runtime_diagnostics": terrain_runtime_diagnostics,
                "waterfall_runtime_diagnostics": waterfall_runtime_diagnostics,
                "approved_for_unity_export": False,
                "unity_export_status": "awaiting_user_approval",
                "export_ready": True,
                "next_steps": [
                    "Review this map in Blender and approve the terrain before exporting anything to Unity.",
                    "When approved, rerun compose_map with map_spec.auto_export_unity=True to resume export, or call generate_map_package explicitly.",
                    "Use asset_pipeline action=aaa_verify with the terrain validation_profile you care about for focused reruns.",
                ],
            }
            return await _with_screenshot(blender, review_result, capture_viewport, object_name=terrain_name)

        # --- Step 11: Export heightmap for Unity import ---
        heightmap_export_path = None
        if terrain_name and "heightmap_exported" not in steps_completed:
            try:
                # MISC-009: use tempfile.gettempdir() instead of hardcoded /tmp/
                import tempfile as _tempfile
                import os as _os_hm
                _hm_dir = checkpoint_dir or _os_hm.path.join(
                    _tempfile.gettempdir(), "veilbreakers_exports"
                )
                _os_hm.makedirs(_hm_dir, exist_ok=True)
                _hm_path = _os_hm.path.join(_hm_dir, f"{map_name}_heightmap.raw")
                hm_result = await blender.send_command("env_export_heightmap", {
                    "terrain_name": terrain_name,
                    "filepath": _hm_path,
                    "unity_compat": True,
                    "flip_vertical": True,
                })
                if isinstance(hm_result, dict) and hm_result.get("filepath"):
                    heightmap_export_path = hm_result["filepath"]
                    steps_completed.append("heightmap_exported")
            except Exception as e:
                steps_failed.append({"step": "heightmap_export", "error": str(e)})

        # --- Step 12: Game-readiness validation (EXPORT-04) ---
        _non_terrain = [n for n in created_objects if "terrain" not in n.lower()]
        _gc_failures: list[dict] = []
        if _non_terrain and "game_check_validated" not in steps_completed:
            try:
                for _obj_name in _non_terrain:
                    try:
                        _gc = await blender.send_command("mesh_check_game_ready", {
                            "object_name": _obj_name,
                        })
                        if isinstance(_gc, dict) and not _gc.get("game_ready", False):
                            _gc_failures.append({
                                "object": _obj_name,
                                "issues": _gc.get("summary", "Unknown"),
                            })
                            _record_pipeline_degradation(
                                "game_check_failed",
                                f"game_check failed for {_obj_name}: {_gc.get('summary', 'Unknown')}",
                            )
                    except Exception as exc:
                        _record_pipeline_warning(
                            "game_check_skipped",
                            exc,
                            object_name=_obj_name,
                        )
                steps_completed.append("game_check_validated")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "game_check_validation", "error": str(e)})

        # --- Step 13: Bake procedural textures to images (EXPORT-02) ---
        if _non_terrain and "textures_baked" not in steps_completed:
            try:
                for _obj_name in _non_terrain:
                    try:
                        await blender.send_command("texture_bake_procedural_to_images", {
                            "object_name": _obj_name,
                            "channels": ["diffuse", "normal", "ao"],
                            "resolution": 1024,
                        })
                    except Exception as exc:
                        _record_pipeline_warning(
                            "texture_bake_failed",
                            exc,
                            object_name=_obj_name,
                        )
                        _record_pipeline_degradation(
                            "texture_bake_failed",
                            f"texture_bake_failed for {_obj_name}: {exc}",
                        )
                steps_completed.append("textures_baked")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "texture_bake", "error": str(e)})

        # --- Step 14: Generate LOD chains (EXPORT-03) ---
        if _non_terrain and "lods_generated" not in steps_completed:
            try:
                for _obj_name in _non_terrain:
                    try:
                        await blender.send_command("asset_pipeline", {
                            "action": "generate_lods",
                            "object_name": _obj_name,
                        })
                    except Exception as exc:
                        _record_pipeline_warning(
                            "lod_generation_failed",
                            exc,
                            object_name=_obj_name,
                        )
                        _record_pipeline_degradation(
                            "lod_generation_failed",
                            f"lod_generation_failed for {_obj_name}: {exc}",
                        )
                steps_completed.append("lods_generated")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "lod_generation", "error": str(e)})

        # --- Step 15: Generate collision meshes (EXPORT-05) ---
        _structure_objects = [n for n in _non_terrain if any(
            kw in n.lower() for kw in ("building", "wall", "gate", "tower", "castle", "bridge", "house", "tavern", "chapel", "keep")
        )]
        if _structure_objects and "collisions_generated" not in steps_completed:
            try:
                await blender.send_command("generate_collision_meshes", {
                    "object_names": _structure_objects,
                    "max_faces": 128,
                })
                steps_completed.append("collisions_generated")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "collision_generation", "error": str(e)})

        # --- Step 16: Export vegetation instances + splatmap (EXPORT-06, EXPORT-07) ---
        if "data_exported" not in steps_completed:
            import tempfile as _tf15
            _data_dir = checkpoint_dir or os.path.join(_tf15.gettempdir(), "veilbreakers_exports")
            os.makedirs(_data_dir, exist_ok=True)
            try:
                if "vegetation_scattered" in steps_completed:
                    try:
                        _veg_path = os.path.join(_data_dir, f"{map_name}_vegetation_instances.json")
                        await blender.send_command("serialize_vegetation", {
                            "output_path": _veg_path,
                            "terrain_name": terrain_name or f"{map_name}_Terrain",
                        })
                    except Exception as exc:
                        _record_pipeline_warning("vegetation_export_failed", exc)
                        _record_pipeline_degradation(
                            "vegetation_export_failed",
                            f"vegetation_export_failed: {exc}",
                        )

                if terrain_name:
                    try:
                        _splat_path = os.path.join(_data_dir, f"{map_name}_splatmap.png")
                        await blender.send_command("export_splatmap", {
                            "terrain_name": terrain_name,
                            "output_path": _splat_path,
                            "target_resolution": 512,
                        })
                    except Exception as exc:
                        _record_pipeline_warning("splatmap_export_failed", exc)

                steps_completed.append("data_exported")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "data_export", "error": str(e)})

        # --- Step 17: Export per-group FBX files (EXPORT-01) ---
        _fbx_files: list[str] = []
        if created_objects and "fbx_exported" not in steps_completed:
            import tempfile as _tf16
            _export_dir = checkpoint_dir or os.path.join(_tf16.gettempdir(), "veilbreakers_exports")
            os.makedirs(_export_dir, exist_ok=True)
            try:
                from blender_addon.handlers.pipeline_state import derive_addressable_groups as _dag
                _terrain_objs = [n for n in created_objects if "terrain" in n.lower()]
                _groups = _dag(
                    map_name, location_results,
                    terrain_objects=_terrain_objs,
                    interior_results=interior_results,
                )
                for _grp in _groups:
                    _grp_objects = _grp.get("objects", [])
                    if not _grp_objects:
                        continue
                    _fbx_path = os.path.join(_export_dir, f"{_grp['group_name']}.fbx")
                    try:
                        await blender.send_command("export_fbx", {
                            "filepath": _fbx_path,
                            "object_names": _grp_objects,
                        })
                        _fbx_files.append(_fbx_path)
                    except Exception as exc:
                        _record_pipeline_warning(
                            "fbx_export_failed",
                            exc,
                            object_name=_grp["group_name"],
                        )
                        _record_pipeline_degradation(
                            "fbx_export_failed",
                            f"fbx_export_failed for {_grp['group_name']}: {exc}",
                        )
                steps_completed.append("fbx_exported")
                _save_chkpt()
            except Exception as e:
                steps_failed.append({"step": "fbx_export", "error": str(e)})

        # --- Build result ---
        quality_report = await _enforce_world_quality(
            blender,
            object_names=created_objects,
            poly_budget=90000 if budget["profile"] != "large_world" else 120000,
        )

        result = {
            "status": "success"
            if not steps_failed and not quality_report["failures"] and not pipeline_degradations
            else "partial",
            "map_name": map_name,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "warnings": pipeline_warnings,
            "objects_created": created_objects,
            "locations": location_results,
            "interiors": interior_results,
            "budget_applied": budget,
            "quality_report": quality_report,
            "heightmap_export_path": heightmap_export_path,
            "game_check_failures": _gc_failures,
            "fbx_exported_files": _fbx_files,
            "resumed_from_checkpoint": _CHKPT_LOADED,
            "checkpoint_dir": checkpoint_dir,
            "terrain_visual_profiles": terrain_visual_profiles,
            "terrain_visual_verification": terrain_visual_verification,
            "pipeline_degradations": pipeline_degradations,
            "terrain_runtime_diagnostics": terrain_runtime_diagnostics,
            "waterfall_runtime_diagnostics": waterfall_runtime_diagnostics,
            "approved_for_unity_export": auto_export_unity,
            "unity_export_status": "export_completed" if auto_export_unity else "awaiting_user_approval",
            "next_steps": [
                "Review the generated map in Blender viewport (use contact_sheet for thorough review).",
                "Run a hero-pass with Tripo only for standout props or landmark pieces.",
                "Export only after the quality report has no remaining failures.",
                f"Import heightmap to Unity: unity_scene action=setup_terrain heightmap_path={heightmap_export_path}" if heightmap_export_path else "Export heightmap manually: blender_environment action=export_heightmap",
                "FBX files exported to: " + (checkpoint_dir or "temp exports dir") if _fbx_files else "No FBX files exported yet.",
                "Import FBX files to Unity and run unity_world action=setup_map_streaming",
            ],
        }
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_map_package":
        # Package compose_map output into per-district Addressable FBX groups + scene hierarchy JSON
        if not map_package_spec:
            return json.dumps({
                "error": "map_package_spec is required",
                "example": {
                    "map_name": "Thornveil",
                    "objects": ["Thornveil_Terrain", "Thornveil_Village"],
                    "locations": [{"name": "Village", "type": "town"}],
                    "export_dir": "C:/Users/YourName/exports",  # use absolute path
                    "generate_lods": True,
                },
            }, indent=2)

        _mpspec = map_package_spec
        _mp_name = _mpspec.get("map_name", "Map")
        _mp_objects = _mpspec.get("objects", [])
        _mp_locations = _mpspec.get("locations", [])
        _mp_export_dir = _mpspec.get("export_dir", ".")
        _mp_gen_lods = _mpspec.get("generate_lods", True)
        _mp_skip_check = _mpspec.get("skip_game_check", False)
        _mp_skip_terrain_visual = bool(_mpspec.get("skip_terrain_visual_validation", False))
        _mp_terrain_objects = [
            name for name in _mp_objects
            if "terrain" in str(name).lower()
        ]
        _mp_terrain_profiles = _normalize_validation_profiles(_mpspec.get("terrain_visual_profiles"))
        _warnings: list[str] = []
        _terrain_visual_verification: dict[str, Any] | None = None

        import os as _os
        _os.makedirs(_mp_export_dir, exist_ok=True)
        _os.makedirs(_os.path.join(_mp_export_dir, _mp_name), exist_ok=True)

        def _record_package_warning(step: str, error: Exception, *, object_name: str | None = None) -> None:
            target = f" for {object_name}" if object_name else ""
            message = f"{step}{target}: {error}"
            logger.warning("generate_map_package warning: %s", message)
            _warnings.append(message)

        try:
            from blender_addon.handlers.pipeline_state import (
                derive_addressable_groups as _derive_groups,
                emit_scene_hierarchy as _emit_hierarchy,
            )
        except ImportError as _ps_err:
            return json.dumps({
                "status": "error",
                "error": f"pipeline_state unavailable in MCP server process (bpy not installed): {_ps_err}",
                "hint": "generate_map_package requires the Blender addon environment.",
            })

        # Step 1: Game-readiness check
        _game_failures = []
        if not _mp_skip_check:
            for _obj_name in _mp_objects:
                try:
                    _chk = await blender.send_command("mesh_check_game_ready", {"object_name": _obj_name})
                    if isinstance(_chk, dict) and not _chk.get("game_ready", False):
                        _failed_checks = [
                            k for k, v in _chk.get("checks", {}).items()
                            if isinstance(v, dict) and not v.get("passed", True)
                        ]
                        _game_failures.append({
                            "object": _obj_name,
                            "game_ready": False,
                            "failed_checks": _failed_checks,
                            "summary": _chk.get("summary", "Unknown failure"),
                        })
                except Exception as exc:
                    _record_package_warning(
                        "game_check_failed",
                        exc,
                        object_name=_obj_name,
                    )

        if _game_failures and not _mp_skip_check:
            return json.dumps({
                "status": "error",
                "error": f"{len(_game_failures)} objects failed game_check",
                "failures": _game_failures,
                "hint": "Fix issues or set skip_game_check=True",
            })

        # Step 2: Mandatory terrain visual validation
        if _mp_terrain_objects and not _mp_skip_terrain_visual:
            _terrain_visual_verification = await _run_terrain_visual_gate(
                blender,
                map_spec=_mpspec,
                object_names=_mp_objects,
                location_results=_mp_locations,
                validation_profiles=_mp_terrain_profiles,
                min_score=int(_mpspec.get("terrain_visual_min_score", 60)),
                screenshot_prefix=f"{_mp_name}_package_terrain",
            )
            _mp_terrain_profiles = list(
                _terrain_visual_verification.get("required_profiles", _mp_terrain_profiles)
            )
            if not _terrain_visual_verification.get("passed", False):
                return {
                    "status": "error",
                    "error": "Terrain visual verification failed",
                    "terrain_visual_profiles": _mp_terrain_profiles,
                    "terrain_visual_verification": _terrain_visual_verification,
                    "hint": "Fix terrain readability and feature framing issues before packaging this map.",
                }

        # Step 3: LOD generation
        _lod_count = 0
        if _mp_gen_lods:
            for _obj_name in _mp_objects:
                try:
                    await blender.send_command("asset_pipeline", {
                        "action": "generate_lods",
                        "object_name": _obj_name,
                    })
                    _lod_count += 1
                except Exception as exc:
                    _record_package_warning(
                        "lod_generation_failed",
                        exc,
                        object_name=_obj_name,
                    )

        # Step 4: Derive Addressable groups
        _addr_groups = _derive_groups(
            _mp_name, _mp_locations,
            terrain_objects=_mp_terrain_objects,
            interior_results=_mpspec.get("interior_results", []),
        )

        # Step 5: Export FBX per group
        _fbx_files = []
        for _grp in _addr_groups:
            _grp_name = _grp["group_name"]
            _grp_objects = _grp.get("objects", [])
            if not _grp_objects:
                continue
            _export_path = _os.path.join(_mp_export_dir, _mp_name, f"{_grp_name}.fbx")
            try:
                await blender.send_command("export_fbx", {
                    "filepath": _export_path,
                    "selected_only": False,
                    "object_names": _grp_objects,
                })
                if _os.path.isfile(_export_path):
                    _fbx_files.append(_export_path)
            except Exception as exc:
                _record_package_warning(
                    "fbx_export_failed",
                    exc,
                    object_name=_grp_name,
                )

        # Step 6: Emit scene hierarchy JSON
        _hierarchy_path = _os.path.join(_mp_export_dir, _mp_name, "scene_hierarchy.json")
        try:
            _hierarchy = _emit_hierarchy(_mp_name, _mp_locations, created_objects=_mp_objects)
            with open(_hierarchy_path, "w", encoding="utf-8") as _fh:
                json.dump(_hierarchy, _fh, indent=2, default=str)
        except RuntimeError as exc:
            _record_package_warning("scene_hierarchy_emit_failed", exc)
            _hierarchy_path = None

        return {
            "status": "success" if _fbx_files and not _warnings else "partial",
            "map_name": _mp_name,
            "fbx_files": _fbx_files,
            "scene_hierarchy_json": _hierarchy_path,
            "addressable_groups": _addr_groups,
            "game_check_failures": _game_failures,
            "lod_variants_generated": _lod_count,
            "warnings": _warnings,
            "terrain_visual_profiles": _mp_terrain_profiles,
            "terrain_visual_verification": _terrain_visual_verification,
            "next_steps": [
                f"Import FBX files into Unity Assets/Maps/{_mp_name}/",
                "Run: unity_world action=setup_map_streaming with scene_hierarchy_json path",
            ],
        }

    elif action == "aaa_verify":
        return await _run_aaa_visual_verification(
            blender,
            angles=angles,
            min_score=min_score,
            validation_profile=validation_profile,
            capture_baseline=capture_baseline,
            baseline_dir=baseline_dir,
            screenshot_prefix="aaa",
            screenshot_dir=os.path.join(Path(os.getenv("TEMP") or os.getenv("TMP") or ".").resolve(), "vb_aaa_verify"),
        )

    elif action == "screenshot_regression":
        # Compare current screenshots against stored baselines
        if not baseline_dir:
            return json.dumps({
                "error": "baseline_dir is required for screenshot_regression",
                "hint": "Run aaa_verify with capture_baseline=True first",
            })
        if not current_screenshots:
            return json.dumps({
                "error": "current_screenshots list is required for screenshot_regression",
            })

        _reg_results: list[dict] = []
        _all_match = True
        for _angle_id, _cur_path in enumerate(current_screenshots):
            _ref_path = os.path.join(baseline_dir, f"baseline_{_angle_id}.png")
            if not os.path.isfile(_ref_path):
                _all_match = False
                _reg_results.append({
                    "angle_id": _angle_id,
                    "match": None,
                    "error": f"Baseline not found: {_ref_path}",
                })
                continue
            if not os.path.isfile(_cur_path):
                _all_match = False
                _reg_results.append({
                    "angle_id": _angle_id,
                    "match": None,
                    "error": f"Current screenshot not found: {_cur_path}",
                })
                continue
            _cmp = compare_screenshots(_ref_path, _cur_path, threshold=0.01)
            if not _cmp["match"]:
                _all_match = False
            _reg_results.append({
                "angle_id": _angle_id,
                **_cmp,
            })

        return {
            "status": "success" if _all_match and bool(_reg_results) else "failed",
            "all_match": _all_match,
            "results": _reg_results,
            "total_angles": len(current_screenshots),
            "passed_angles": sum(1 for r in _reg_results if r.get("match") is True),
        }

    elif action == "performance_check":
        # Performance budget check: triangle count and estimated draw calls
        _pc_result = await blender.send_command("performance_budget_check", {})
        _pc_status = str(_pc_result.get("status", "")).lower()
        _pc_error = str(_pc_result.get("error", _pc_result.get("budget", ""))).lower()
        if _pc_status not in {"ok", "success"} or "not_implemented" in _pc_error:
            return {
                "status": "error",
                "error": "performance_budget_check unavailable",
                "raw_result": _pc_result,
                "summary": {
                    "passed": False,
                    "tri_utilization_pct": None,
                    "draw_call_utilization_pct": None,
                },
            }
        _total_tris = _pc_result.get("total_tris", 0)
        _mat_count = _pc_result.get("unique_material_count", 0)

        # Per-category budgets (tris)
        _CATEGORY_BUDGETS = {
            "terrain":   200_000,
            "buildings": 300_000,
            "walls":     150_000,
            "trees":     400_000,
            "grass":     300_000,
            "rocks":     200_000,
            "water":      20_000,
        }
        _per_category = _pc_result.get("per_category", [])
        _category_results = []
        for _cat_name, _cat_budget in _CATEGORY_BUDGETS.items():
            _cat_tris = next(
                (c.get("tri_count", 0) for c in _per_category if c.get("type") == _cat_name),
                0,
            )
            _category_results.append({
                "type": _cat_name,
                "tris": _cat_tris,
                "budget": _cat_budget,
                "within_budget": _cat_tris <= _cat_budget,
            })

        return {
            "status": "success",
            "total_tris": _total_tris,
            "tri_budget_ok": _total_tris < 2_000_000,
            "estimated_draw_calls": _mat_count,
            "draw_call_budget_ok": _mat_count < 500,
            "per_category": _category_results,
            "summary": {
                "passed": _total_tris < 2_000_000 and _mat_count < 500,
                "tri_utilization_pct": round(_total_tris / 2_000_000 * 100, 1),
                "draw_call_utilization_pct": round(_mat_count / 500 * 100, 1),
            },
        }

    elif action == "generate_lod_chain":
        # Auto-generate LOD chain for one or more objects
        _lod_results = []
        _target_objects = object_names or ([object_name] if object_name else [])
        if not _target_objects:
            return json.dumps({
                "error": "object_name or object_names is required for generate_lod_chain",
            })
        for _lod_obj_name in _target_objects:
            _lod_result = await blender.send_command("auto_generate_lod_chain", {
                "obj_name": _lod_obj_name,
                "asset_type": asset_type or "prop",
            })
            _lod_results.append(_lod_result)
        return {
            "status": "success",
            "lod_chains": _lod_results,
            "total_objects": len(_target_objects),
        }

    elif action == "compose_interior":
        # Interior composition pipeline: room shells → furniture → props → lighting → atmosphere
        if not interior_spec:
            return json.dumps({
                "error": "interior_spec is required",
                "example": {
                    "name": "Tavern_Interior",
                    "seed": 42,
                    "rooms": [
                        {"name": "main_hall", "type": "tavern_hall", "width": 10, "depth": 12, "height": 4},
                        {"name": "kitchen", "type": "kitchen", "width": 5, "depth": 6, "height": 3.5},
                        {"name": "cellar", "type": "storage", "width": 8, "depth": 8, "height": 3, "below_ground": True},
                        {"name": "upstairs", "type": "bedroom", "width": 10, "depth": 12, "height": 3},
                    ],
                    "doors": [
                        {"from": "main_hall", "to": "kitchen", "style": "wooden"},
                        {"from": "main_hall", "to": "cellar", "style": "trapdoor"},
                        {"from": "main_hall", "to": "upstairs", "style": "staircase"},
                    ],
                    "style": "medieval",
                    "storytelling_density": 0.7,
                    "generate_props_with_tripo": False,
                },
            }, indent=2)

        spec = interior_spec
        int_name = spec.get("name", "Interior")
        int_seed = spec.get("seed", 42)
        int_style = spec.get("style", "medieval")
        rooms = spec.get("rooms", [])
        room_plan = _plan_interior_rooms(spec)
        planned_rooms = room_plan["rooms"]
        planned_doors = room_plan["doors"]
        steps_completed = []
        steps_failed = []
        pipeline_warnings: list[str] = []
        room_results: list = []
        _INTERIOR_CHKPT_LOADED = False

        if checkpoint_dir:
            try:
                from blender_addon.handlers.pipeline_state import (
                    load_pipeline_checkpoint as _load_chkpt,
                    validate_checkpoint_compatibility as _validate_chkpt,
                    delete_pipeline_checkpoint as _delete_chkpt,
                )
            except ImportError as _ps_err:
                return json.dumps({
                    "status": "error",
                    "error": f"pipeline_state unavailable in MCP server process: {_ps_err}",
                    "hint": "Checkpoint/resume requires the Blender addon environment.",
                })

            if force_restart:
                _delete_chkpt(checkpoint_dir, int_name)
            ckpt = _load_chkpt(checkpoint_dir, int_name)
            if ckpt:
                ok, reason = _validate_chkpt(ckpt, {"seed": int_seed, "locations": rooms})
                if not ok:
                    return json.dumps({
                        "error": "Incompatible checkpoint found for this interior pipeline.",
                        "reason": reason,
                        "hint": "Set force_restart=True to discard the incompatible checkpoint.",
                    }, indent=2)
                steps_completed = ckpt.get("steps_completed", [])
                steps_failed = ckpt.get("steps_failed", [])
                # Restore room_results from checkpoint so downstream steps are complete
                room_results = list(ckpt.get("location_results", []))
                _INTERIOR_CHKPT_LOADED = True

        def _save_interior_chkpt() -> None:
            if not checkpoint_dir:
                return
            try:
                from blender_addon.handlers.pipeline_state import (
                    save_pipeline_checkpoint as _save_cp,
                )
            except ImportError:
                return
            _save_cp(checkpoint_dir, {
                "map_name": int_name,
                "seed": int_seed,
                "location_count": len(rooms),
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "created_objects": [],
                "location_results": room_results,
                "interior_results": [],
                "params_snapshot": {"pipeline_action": "compose_interior"},
            })

        def _record_interior_warning(step: str, error: Exception, *, object_name: str | None = None) -> None:
            target = f" for {object_name}" if object_name else ""
            message = f"{step}{target}: {error}"
            logger.warning("compose_interior warning: %s", message)
            pipeline_warnings.append(message)

        # --- Step 1: Generate linked interior (room shells + door triggers + occlusion) ---
        room_defs = []
        for planned_room in planned_rooms:
            room_defs.append({
                "name": planned_room["name"],
                "type": planned_room["type"],
                "bounds": planned_room["bounds"],
            })

        try:
            await blender.send_command("world_generate_linked_interior", {
                "name": int_name,
                "building_exterior_bounds": room_plan["building_bounds"],
                "interior_rooms": room_defs,
                "door_positions": planned_doors,
                "seed": int_seed,
            })
            steps_completed.append("linked_interior_created")
        except Exception as e:
            steps_failed.append({"step": "linked_interior", "error": str(e)})
        _save_interior_chkpt()

        # --- Step 2: Generate each room with detailed geometry ---
        room_bounds_by_name = {room["name"]: room for room in planned_rooms}
        completed_rooms = {s for s in steps_completed if s.startswith("room_")}
        # Build a lookup of already-restored room_results by name for fast dedup
        _restored_room_names = {r["name"] for r in room_results}
        for i, room in enumerate(rooms):
            try:
                room_key = f"room_{room.get('name', i)}"
                if room_key in completed_rooms:
                    # Room was completed in a prior run; ensure it appears in room_results
                    # so downstream steps (geometry enhancement, props, etc.) still process it.
                    room_name = room.get("name", f"Room_{i}")
                    if room_name not in _restored_room_names:
                        planned_room = room_bounds_by_name.get(room_name)
                        room_results.append({
                            "name": room_name,
                            "type": room.get("type", "generic"),
                            "bounds": planned_room["bounds"] if planned_room is not None else None,
                        })
                        _restored_room_names.add(room_name)
                    continue
                room_name = room.get("name", f"Room_{i}")
                await blender.send_command("world_generate_interior", {
                    "name": f"{int_name}_{room_name}",
                    "room_type": room.get("type", "generic"),
                    "width": room.get("width", 6),
                    "depth": room.get("depth", 6),
                    "height": room.get("height", 3.5),
                    "seed": int_seed + i,
                })
                planned_room = room_bounds_by_name.get(room_name)
                if planned_room is not None:
                    origin = planned_room["bounds"]["min"]
                    # PIPE-017: Use floor Z from bounds (not hardcoded 0.0)
                    floor_z = float(origin[2]) if len(origin) > 2 else 0.0
                    await _position_generated_object(
                        blender,
                        f"{int_name}_{room_name}",
                        (origin[0], origin[1], floor_z),
                    )
                    steps_completed.append(f"room_positioned_{room_name}")
                steps_completed.append(room_key)
                room_results.append({
                    "name": room_name,
                    "type": room.get("type", "generic"),
                    "bounds": planned_room["bounds"] if planned_room is not None else None,
                })
            except Exception as e:
                steps_failed.append({"step": f"room_{room.get('name', i)}", "error": str(e)})
        _save_interior_chkpt()

        # --- Step 2b: Enhance interior geometry (AAA quality) ---
        for room_res in room_results:
            room_obj_name = f"{int_name}_{room_res['name']}"
            try:
                await blender.send_command("mesh_enhance_geometry", {
                    "object_name": room_obj_name,
                    "profile": "architecture",
                    "apply_modifiers": True,
                })
                steps_completed.append(f"enhance_{room_res['name']}")
            except Exception as exc:
                _record_interior_warning(
                    "room_enhancement_failed",
                    exc,
                    object_name=room_obj_name,
                )
        _save_interior_chkpt()

        # --- Step 3: Add storytelling/narrative props to each room ---
        if spec.get("storytelling_density", 0) > 0:
            for i, room in enumerate(rooms):
                try:
                    await blender.send_command("env_add_storytelling_props", {
                        "target_interior": f"{int_name}_{room.get('name', 'room')}",
                        "room_type": room.get("type", "generic"),
                        "density_modifier": spec.get("storytelling_density", 0.5),
                        "seed": int_seed + 100 + i,  # PIPE-021: unique seed per room
                        "room_width": room.get("width", 6),   # PIPE-018: pass actual dims
                        "room_depth": room.get("depth", 6),
                    })
                    steps_completed.append(f"props_{room.get('name')}")
                except Exception as e:
                    steps_failed.append({"step": f"props_{room.get('name')}", "error": str(e)})
            _save_interior_chkpt()

        # --- Step 3b: Prop quality validation ---
        prop_quality_results = []
        for i, room in enumerate(rooms):
            room_name = room.get("name", f"Room_{i}")
            room_obj_name = f"{int_name}_{room_name}"
            planned_room = room_bounds_by_name.get(room_name)
            if planned_room is None:
                continue
            bounds = planned_room.get("bounds", {})
            b_min = bounds.get("min", [0, 0, 0])
            b_max = bounds.get("max", [0, 0, 0])
            cx = (b_min[0] + b_max[0]) / 2.0
            cy = (b_min[1] + b_max[1]) / 2.0
            floor_z_val = float(b_min[2]) if len(b_min) > 2 else 0.0
            try:
                pq_result = await blender.send_command("validate_prop_quality", {
                    "object_name": room_obj_name,
                    "prop_type": room.get("type", "_default"),
                    "floor_z": floor_z_val,
                    "room_center": [cx, cy],
                })
                pq_result["room"] = room_name
                prop_quality_results.append(pq_result)
                if not pq_result.get("passed", True):
                    steps_failed.append({"step": f"prop_quality_{room_name}", "issues": pq_result.get("issues", [])})
                else:
                    steps_completed.append(f"prop_quality_{room_name}")
            except Exception as pq_err:
                _record_interior_warning(
                    "prop_quality_check_failed",
                    pq_err,
                    object_name=room_obj_name,
                )
                steps_failed.append({
                    "step": f"prop_quality_{room_name}",
                    "error": str(pq_err),
                })
        _save_interior_chkpt()

        # --- Build Tripo prop generation queue ---
        tripo_queue = []
        if spec.get("generate_props_with_tripo", False):
            _ROOM_PROP_PROMPTS = {
                "tavern_hall": ["wooden bar counter with taps", "round wooden tavern table", "wooden bench", "iron chandelier with candles", "barrel stack"],
                "kitchen": ["medieval stone hearth with iron pot", "wooden food prep table", "hanging dried herbs bundle", "iron cooking rack"],
                "bedroom": ["medieval wooden bed frame with canopy", "wooden nightstand with candle", "wooden wardrobe chest", "woven rug"],
                "storage": ["wooden crate stack", "wine barrel rack", "hanging meat hooks", "wooden shelf unit"],
                "throne_room": ["ornate stone throne", "tall banner stand", "iron brazier on stand", "stone pillar with carvings"],
                "library": ["tall wooden bookshelf", "reading desk with candle", "globe on wooden stand", "scroll rack"],
                "forge": ["blacksmith anvil", "stone forge with bellows", "weapon rack", "quenching barrel"],
                "chapel": ["stone altar with candles", "prayer bench pew", "stained glass frame", "holy water font"],
                "prison": ["iron jail cell door", "wall-mounted shackles", "wooden torture rack", "iron cage"],
                "generic": ["wooden table", "wooden chair", "iron torch sconce", "wooden barrel"],
            }
            for room in rooms:
                room_type = room.get("type", "generic")
                prompts = _ROOM_PROP_PROMPTS.get(room_type, _ROOM_PROP_PROMPTS["generic"])
                for prop_prompt in prompts:
                    tripo_queue.append({
                        "room": room.get("name"),
                        "prompt": f"dark fantasy {int_style} {prop_prompt}, game-ready 3D model, clean topology",
                    })

        result = {
            "status": "success" if not steps_failed and not pipeline_warnings else "partial",
            "interior_name": int_name,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "warnings": pipeline_warnings,
            "rooms_generated": room_results,
            "door_positions": planned_doors,
            "building_bounds": room_plan["building_bounds"],
            "prop_quality": prop_quality_results,
            "tripo_prop_queue": tripo_queue[:20] if tripo_queue else [],
            "tripo_props_remaining": max(0, len(tripo_queue) - 20),
            "resumed_from_checkpoint": _INTERIOR_CHKPT_LOADED,
            "checkpoint_dir": checkpoint_dir,
            "next_steps": [
                "--- ENHANCE VISUALS (auto-applied: architecture profile SubD + bevel + smooth shading) ---",
                "1. Review interior: blender_viewport action=contact_sheet object_name=<room>",
                "2. Add materials: blender_material action=create (stone_wall, wooden_floor, etc.)",
                "3. Bake detail maps: blender_mesh action=bake_ao object_name=<room> (AO, curvature)",
                "4. Generate hero props with Tripo: asset_pipeline action=generate_3d prompt='dark fantasy <prop>'",
                "--- UNITY INTERIOR SETUP ---",
                "5. Setup interior streaming: unity_world action=create_interior_streaming",
                "6. Setup door system: unity_world action=create_door_system",
                "7. Dungeon lighting: unity_world action=create_dungeon_lighting",
                "8. Portal audio: unity_audio action=setup_portal_audio",
                "9. Occlusion: unity_world action=setup_occlusion",
                "10. NPC placement: unity_world action=create_npc_placement",
                "11. Interaction prompts: unity_ux action=interaction_prompt",
            ],
        }
        if tripo_queue:
            result["next_steps"].insert(0, f"TRIPO QUEUE: {len(tripo_queue)} props to generate. Run each with: asset_pipeline action=generate_3d prompt='<prompt>'")

        return await _with_screenshot(blender, result, capture_viewport, int_name)

    elif action == "cleanup":
        if not object_name:
            return "ERROR: 'object_name' is required for cleanup"
        runner = PipelineRunner(blender, settings)
        result = await runner.cleanup_ai_model(
            object_name,
            poly_budget,
            has_extracted_textures=has_extracted_textures,
            texture_channels=texture_channels,
        )
        _focus_name = terrain_name if terrain_name else (created_objects[0] if created_objects else None)
        return await _with_screenshot(blender, result, capture_viewport, _focus_name)

    elif action == "generate_lods":
        if not object_name:
            return "ERROR: 'object_name' is required for generate_lods"
        params = {"object_name": object_name}
        if ratios:
            params["ratios"] = ratios
        result = await blender.send_command("pipeline_generate_lods", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "validate_export":
        if not filepath:
            return "ERROR: 'filepath' is required for validate_export"
        runner = PipelineRunner(blender, settings)
        result = await runner.validate_export(filepath)
        return json.dumps(result, indent=2, default=str)

    elif action == "tag_metadata":
        if not asset_id or not output_path:
            return "ERROR: 'asset_id' and 'output_path' are required for tag_metadata"
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            runner = PipelineRunner(blender, settings)
            result = await runner.tag_metadata(asset_id, output_path, catalog)
            return json.dumps(result, indent=2, default=str)
        finally:
            catalog.close()

    elif action == "batch_process":
        if not object_names:
            return "ERROR: 'object_names' is required for batch_process"
        runner = PipelineRunner(blender, settings)
        result = await runner.batch_process(object_names, steps)
        return json.dumps(result, indent=2, default=str)

    elif action == "catalog_query":
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            results = catalog.query_assets(
                asset_type=asset_type,
                tags=tags,
                status=status,
            )
            return json.dumps(results, indent=2, default=str)
        finally:
            catalog.close()

    elif action == "catalog_add":
        if not name or not asset_type or not path:
            return "ERROR: 'name', 'asset_type', and 'path' are required for catalog_add"
        catalog = AssetCatalog(settings.asset_catalog_db)
        try:
            new_id = catalog.add_asset(
                name=name,
                asset_type=asset_type,
                path=path,
                tags=tags,
            )
            return json.dumps({"asset_id": new_id, "status": "added"}, indent=2)
        finally:
            catalog.close()

    # --- Equipment operations (Phase 13) ---

    elif action == "generate_weapon":
        if not weapon_type:
            return "ERROR: 'weapon_type' is required for generate_weapon"
        params = {"weapon_type": weapon_type}
        if object_name:
            params["object_name"] = object_name
        if weapon_style is not None:
            params["style"] = weapon_style
        if weapon_length is not None:
            params["length"] = weapon_length
        if blade_width is not None:
            params["blade_width"] = blade_width
        if material_name is not None:
            params["material_name"] = material_name
        result = await blender.send_command("equipment_generate_weapon", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "split_character":
        if not object_name:
            return "ERROR: 'object_name' is required for split_character"
        params = {"object_name": object_name}
        if parts:
            params["parts"] = parts
        result = await blender.send_command("equipment_split_character", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "fit_armor":
        if not armor_object_name or not character_object_name:
            return "ERROR: 'armor_object_name' and 'character_object_name' are required for fit_armor"
        params = {
            "armor_object_name": armor_object_name,
            "character_object_name": character_object_name,
        }
        if body_types:
            params["body_types"] = body_types
        result = await blender.send_command("equipment_fit_armor", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "render_equipment_icon":
        if not object_name:
            return "ERROR: 'object_name' is required for render_equipment_icon"
        params = {
            "object_name": object_name,
            "resolution": resolution,
            "camera_distance": camera_distance,
            "camera_angle": camera_angle,
        }
        if output_path:
            params["output_path"] = output_path
        result = await blender.send_command("equipment_render_icon", params)
        return json.dumps(result, indent=2, default=str)

    # --- Import local model files (Tripo Studio downloads, etc.) ---

    elif action == "import_model":
        if not filepath:
            return "ERROR: 'filepath' is required for import_model (path to .glb/.fbx/.obj file)"
        from pathlib import Path as _Path
        if not _Path(filepath).exists():
            return f"ERROR: File not found: '{filepath}'. Check the path and try again."
        ext = _Path(filepath).suffix.lower()
        supported = {".glb", ".gltf", ".fbx", ".obj"}
        if ext not in supported:
            return f"ERROR: Unsupported file format '{ext}'. Supported: {sorted(supported)}"
        import_ops = {
            ".glb": "import_scene.gltf",
            ".gltf": "import_scene.gltf",
            ".fbx": "import_scene.fbx",
            ".obj": "wm.obj_import",
        }
        op = import_ops[ext]
        safe_path = filepath.replace("\\", "/").replace('"', '\\"')
        # Track new objects by comparing before/after
        import_code = (
            f'import bpy\n'
            f'existing = set(o.name for o in bpy.data.objects)\n'
            f'bpy.ops.{op}(filepath="{safe_path}")\n'
            f'new_names = [o.name for o in bpy.data.objects if o.name not in existing]\n'
            f'mesh_names = [o.name for o in bpy.data.objects if o.name not in existing and o.type == "MESH"]\n'
            f'{{"new_objects": new_names, "mesh_objects": mesh_names}}'
        )
        import_result = await blender.send_command("execute_code", {"code": import_code})

        # Unwrap execute_code result: {status, result: {output: <actual data>}}
        inner = import_result
        if isinstance(import_result, dict):
            inner = import_result.get("result", import_result)
            if isinstance(inner, dict) and "output" in inner:
                inner = inner["output"]

        # Extract actual imported names from Blender response
        new_objects = []
        mesh_objects = []
        if isinstance(inner, dict):
            new_objects = inner.get("new_objects", [])
            mesh_objects = inner.get("mesh_objects", [])
        imported_name = mesh_objects[0] if mesh_objects else (new_objects[0] if new_objects else _Path(filepath).stem)

        result = {
            "status": "success",
            "object_name": imported_name,
            "all_imported_objects": new_objects,
            "mesh_objects": mesh_objects,
            "filepath": filepath,
            "format": ext.lstrip("."),
            "next_steps": [
                f"Imported {len(new_objects)} objects ({len(mesh_objects)} meshes). Primary: '{imported_name}'",
                f"Run cleanup: asset_pipeline action=cleanup object_name={imported_name}",
                f"Or full pipeline: asset_pipeline action=full_pipeline object_name={imported_name}",
            ],
        }
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "import_and_process":
        if not filepath:
            return "ERROR: 'filepath' is required for import_and_process (path to .glb/.fbx/.obj file)"
        from pathlib import Path as _Path
        if not _Path(filepath).exists():
            return f"ERROR: File not found: '{filepath}'. Check the path and try again."

        # Step 1: Import into Blender and get actual object name
        ext = _Path(filepath).suffix.lower()
        import_ops = {".glb": "import_scene.gltf", ".gltf": "import_scene.gltf",
                      ".fbx": "import_scene.fbx", ".obj": "wm.obj_import"}
        op = import_ops.get(ext)
        if not op:
            return f"ERROR: Unsupported format '{ext}'. Supported: .glb, .gltf, .fbx, .obj"
        safe_path = filepath.replace("\\", "/").replace('"', '\\"')
        import_code = (
            f'import bpy\n'
            f'existing = set(o.name for o in bpy.data.objects)\n'
            f'bpy.ops.{op}(filepath="{safe_path}")\n'
            f'mesh_names = [o.name for o in bpy.data.objects if o.name not in existing and o.type == "MESH"]\n'
            f'mesh_names'
        )
        import_result = await blender.send_command("execute_code", {"code": import_code})
        # Unwrap execute_code result: {status, result: {output: <actual data>}}
        inner = import_result
        if isinstance(import_result, dict):
            inner = import_result.get("result", import_result)
            if isinstance(inner, dict) and "output" in inner:
                inner = inner["output"]
        if isinstance(inner, list) and inner:
            obj_name = inner[0]
        else:
            obj_name = _Path(filepath).stem

        # Step 2: Run full pipeline on the imported object
        runner = PipelineRunner(blender, settings)
        result = await runner.full_asset_pipeline(
            object_name=obj_name,
            asset_type=asset_type or "prop",
            poly_budget=poly_budget,
            material_preset=material_preset,
            weathering_preset=weathering_preset,
            rig_template=rig_template,
            animations=animations,
            lod_count=lod_count,
            export_format=export_format,
            export_dir=export_dir or output_dir,
        )
        result["imported_from"] = filepath
        result["blender_object"] = obj_name
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Full production pipeline ---

    elif action == "full_pipeline":
        if not object_name:
            return "ERROR: 'object_name' is required for full_pipeline"
        runner = PipelineRunner(blender, settings)
        result = await runner.full_asset_pipeline(
            object_name=object_name,
            asset_type=asset_type or "prop",
            poly_budget=poly_budget,
            material_preset=material_preset,
            weathering_preset=weathering_preset,
            rig_template=rig_template,
            animations=animations,
            lod_count=lod_count,
            export_format=export_format,
            export_dir=export_dir or output_dir,
        )
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_and_process":
        if not prompt and not image_path:
            return "ERROR: 'prompt' or 'image_path' is required for generate_and_process"
        runner = PipelineRunner(blender, settings)
        result = await runner.generate_and_process(
            prompt=prompt,
            image_path=image_path,
            asset_type=asset_type or "prop",
            output_dir=export_dir or output_dir,
            poly_budget=poly_budget,
            material_preset=material_preset,
            weathering_preset=weathering_preset,
            rig_template=rig_template,
            animations=animations,
            lod_count=lod_count,
            export_format=export_format,
        )
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: terrain_pipeline (Bundle A-O orchestrator, plan §31)
# ---------------------------------------------------------------------------

@mcp.tool()
async def terrain_pipeline(
    action: Literal[
        "run_pass",
        "run_pipeline",
        "list_passes",
        "list_bundles",
        "rollback",
        "list_checkpoints",
    ],
    # Core execution params
    pass_name: str | None = None,
    pipeline: list[str] | None = None,
    tile_size: int = 64,
    cell_size: float = 1.0,
    seed: int = 0,
    tile_x: int = 0,
    tile_y: int = 0,
    world_origin_x: float = 0.0,
    world_origin_y: float = 0.0,
    # Optional scoping + safety
    region_bounds: dict | list | None = None,
    region: dict | list | None = None,
    protected_zones: list[dict] | None = None,
    scene_read: dict | None = None,
    checkpoint: bool = False,
    enforce_protocol: bool = False,
    out_of_view_ok: bool = True,
    # Initial heightmap (optional)
    height: list | None = None,
    terrain_type: str = "mountains",
    scale: float = 100.0,
    erosion_profile: str = "temperate",
    # Rollback
    checkpoint_id: str | None = None,
) -> str:
    """AAA terrain pipeline orchestrator (Bundle A-O).

    Actions:
        * ``run_pass`` — Execute a single registered pass against the
          ``TerrainPassController``. Supply ``pass_name``.
        * ``run_pipeline`` — Execute an ordered list of passes. If
          ``pipeline`` is omitted the default Bundle A sequence
          (macro_world → structural_masks → erosion → validation_minimal)
          runs.
        * ``list_passes`` — Enumerate every pass currently registered
          with the controller (each bundle registers its own).
        * ``list_bundles`` — Report which Bundle A-O registrars loaded
          successfully at addon startup.
        * ``rollback`` — Restore the terrain mask stack to a previously
          saved checkpoint; supply ``checkpoint_id``.
        * ``list_checkpoints`` — Enumerate checkpoints currently stored
          under ``.planning/terrain_checkpoints/``.

    The tool is intentionally thin — it delegates to ``handle_run_terrain_pass``
    (the ``env_run_terrain_pass`` command handler) which owns intent
    construction, pass sequencing, and result serialization.
    """
    blender = get_blender_connection()

    if action == "list_passes":
        code = (
            "from blender_addon.handlers.terrain_pipeline import TerrainPassController\n"
            "names = sorted(TerrainPassController.PASS_REGISTRY.keys())\n"
            "names"
        )
        result = await blender.send_command("execute_code", {"code": code})
        return json.dumps({"passes": result}, indent=2, default=str)

    if action == "list_bundles":
        code = (
            "from blender_addon.handlers import LOADED_TERRAIN_BUNDLES\n"
            "list(LOADED_TERRAIN_BUNDLES)"
        )
        result = await blender.send_command("execute_code", {"code": code})
        return json.dumps({"bundles": result}, indent=2, default=str)

    if action == "list_checkpoints":
        code = (
            "from blender_addon.handlers.terrain_checkpoints import list_checkpoints\n"
            "list_checkpoints()"
        )
        result = await blender.send_command("execute_code", {"code": code})
        return json.dumps({"checkpoints": result}, indent=2, default=str)

    if action == "rollback":
        if not checkpoint_id:
            return "ERROR: 'checkpoint_id' is required for rollback"
        code = (
            "from blender_addon.handlers.terrain_checkpoints import rollback_to\n"
            f"rollback_to({checkpoint_id!r})"
        )
        result = await blender.send_command("execute_code", {"code": code})
        return json.dumps(result, indent=2, default=str)

    # run_pass / run_pipeline — build the handler params and dispatch via
    # the already-registered "env_run_terrain_pass" command handler.
    if action not in ("run_pass", "run_pipeline"):
        return f"ERROR: unknown action '{action}'"

    params: dict[str, Any] = {
        "tile_size": int(tile_size),
        "cell_size": float(cell_size),
        "seed": int(seed),
        "tile_x": int(tile_x),
        "tile_y": int(tile_y),
        "world_origin_x": float(world_origin_x),
        "world_origin_y": float(world_origin_y),
        "terrain_type": terrain_type,
        "scale": float(scale),
        "erosion_profile": erosion_profile,
        "checkpoint": bool(checkpoint),
        "enforce_protocol": bool(enforce_protocol),
        "out_of_view_ok": bool(out_of_view_ok),
    }
    if region_bounds is not None:
        params["region_bounds"] = region_bounds
    if region is not None:
        params["region"] = region
    if protected_zones is not None:
        params["protected_zones"] = protected_zones
    if scene_read is not None:
        params["scene_read"] = scene_read
    if height is not None:
        params["height"] = height

    if action == "run_pass":
        if not pass_name:
            return "ERROR: 'pass_name' is required for run_pass"
        params["pass_name"] = pass_name
    else:  # run_pipeline
        params["pipeline"] = pipeline  # None → default Bundle A sequence

    result = await blender.send_command("env_run_terrain_pass", params)
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Compound tool: concept_art
# ---------------------------------------------------------------------------

@mcp.tool()
async def concept_art(
    action: Literal["generate", "extract_palette", "style_board", "silhouette_test"],
    # generate params
    prompt: str | None = None,
    style: str = "dark fantasy, weathered Gothic medieval, desaturated",  # STY-002
    width: int = 1024,
    height: int = 1024,
    output_dir: str = ".",
    # palette params
    image_path: str | None = None,
    num_colors: int = 8,
    swatch_size: int = 64,
    # style_board params
    image_paths: list[str] | None = None,
    palette_colors: list[dict] | None = None,
    title: str = "Style Board",
    annotations: list[str] | None = None,
    board_width: int = 2048,
    # silhouette params
    threshold: int = 128,
    min_contrast_ratio: float = 0.3,
    distances: list[float] | None = None
):
    """Concept art generation and visual analysis tools."""
    if action == "generate":
        if not prompt:
            return "ERROR: 'prompt' is required for generate"
        result = generate_concept_art(
            prompt=prompt,
            style=style,
            width=width,
            height=height,
            output_dir=output_dir,
            fal_key=settings.fal_key or None,
        )
        return json.dumps(result, indent=2, default=str)

    elif action == "extract_palette":
        if not image_path:
            return "ERROR: 'image_path' is required for extract_palette"
        result = extract_color_palette(image_path, num_colors, swatch_size)
        parts = [json.dumps({
            "colors": result["colors"],
        }, indent=2, default=str)]
        if result.get("swatch_bytes"):
            parts.append(Image(data=result["swatch_bytes"], format="png"))
        return parts

    elif action == "style_board":
        if not image_paths:
            return "ERROR: 'image_paths' is required for style_board"
        board_bytes = compose_style_board(
            images=image_paths,
            palette_colors=palette_colors,
            title=title,
            annotations=annotations,
            board_width=board_width,
        )
        return Image(data=board_bytes, format="png")

    elif action == "silhouette_test":
        if not image_path:
            return "ERROR: 'image_path' is required for silhouette_test"
        result = test_silhouette_readability(
            image_path,
            threshold=threshold,
            min_contrast_ratio=min_contrast_ratio,
            distances=distances,
        )
        return json.dumps(result, indent=2, default=str)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_rig
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_rig(
    action: Literal[
        "analyze_mesh",        # RIG-01: Mesh analysis for rigging
        "apply_template",      # RIG-02: Apply creature rig template
        "build_custom",        # RIG-03: Custom rig from limb library
        "setup_facial",        # RIG-04: Facial rig with expressions
        "setup_ik",            # RIG-05: IK chain setup
        "setup_spring_bones",  # RIG-06: Spring/jiggle bone system
        "auto_weight",         # RIG-07: Auto weight painting
        "test_deformation",    # RIG-08: Deformation test at 8 poses
        "validate",            # RIG-09: Rig validation with grading
        "fix_weights",         # RIG-10: Weight mirror/normalize/smooth
        "setup_ragdoll",       # RIG-11: Ragdoll auto-setup
        "retarget",            # RIG-12: Rig retargeting
        "add_shape_keys",      # RIG-13: Shape keys for expressions/damage
    ],
    object_name: str,
    # Template / custom rig params
    template: str | None = None,
    limb_types: list[str] | None = None,
    # IK params
    bone_name: str | None = None,
    chain_length: int | None = None,
    constraint_type: str | None = None,
    pole_target: str | None = None,
    pole_bone: str | None = None,
    curve_points: list[list[float]] | None = None,
    rotation_limits: dict | None = None,
    # Spring bone params
    bone_names: list[str] | None = None,
    stiffness: float | None = None,
    damping: float | None = None,
    gravity: float | None = None,
    # Weight params
    armature_name: str | None = None,
    operation: str | None = None,
    direction: str | None = None,
    factor: float | None = None,
    repeat: int | None = None,
    threshold: float | None = None,
    # Deformation test params
    pose_names: list[str] | None = None,
    # Ragdoll params
    bone_collider_map: dict | None = None,
    preset: str | None = None,
    # Retarget params
    source_rig: str | None = None,
    target_rig: str | None = None,
    bone_mapping: dict | None = None,
    # Shape key params
    shape_key_name: str | None = None,
    mode: str | None = None,
    vertex_offsets: dict | None = None,
    expression_name: str | None = None,
    # Facial params
    expressions: list[str] | None = None,
    # Visual feedback
    capture_viewport: bool = True
):
    """Rig creatures for game animation with visual verification."""
    blender = get_blender_connection()

    if action == "analyze_mesh":
        result = await blender.send_command("rig_analyze", {"object_name": object_name})
        return json.dumps(result, indent=2, default=str)

    elif action == "apply_template":
        params = {"object_name": object_name}
        if template is not None:
            params["template"] = template
        result = await blender.send_command("rig_apply_template", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "build_custom":
        params = {"object_name": object_name}
        if limb_types is not None:
            params["limb_types"] = limb_types
        result = await blender.send_command("rig_build_custom", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_facial":
        params = {"rig_name": object_name}
        if expressions is not None:
            params["expressions"] = expressions
        result = await blender.send_command("rig_setup_facial", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_ik":
        params = {"rig_name": object_name}
        if bone_name is not None:
            params["bone_name"] = bone_name
        if chain_length is not None:
            params["chain_length"] = chain_length
        if constraint_type is not None:
            params["constraint_type"] = constraint_type
        if pole_target is not None:
            params["pole_target"] = pole_target
        if pole_bone is not None:
            params["pole_target_bone"] = pole_bone
        if curve_points is not None:
            params["curve_points"] = curve_points
        if rotation_limits is not None:
            params["joint_limits"] = rotation_limits
        result = await blender.send_command("rig_setup_ik", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_spring_bones":
        params = {"rig_name": object_name}
        if bone_names is not None:
            params["bone_names"] = bone_names
        if stiffness is not None:
            params["stiffness"] = stiffness
        if damping is not None:
            params["damping"] = damping
        if gravity is not None:
            params["gravity"] = gravity
        result = await blender.send_command("rig_setup_spring_bones", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "auto_weight":
        params = {"mesh_name": object_name}
        if armature_name is not None:
            params["armature_name"] = armature_name
        result = await blender.send_command("rig_auto_weight", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "test_deformation":
        params = {"rig_name": object_name}
        if pose_names is not None:
            params["pose_names"] = pose_names
        result = await blender.send_command("rig_test_deformation", params)
        # Deformation test returns contact sheet -- always capture
        return await _with_screenshot(blender, result, True)

    elif action == "validate":
        params = {"mesh_name": object_name}
        if armature_name is not None:
            params["armature_name"] = armature_name
        result = await blender.send_command("rig_validate", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "fix_weights":
        params = {"mesh_name": object_name}
        if operation is not None:
            params["operation"] = operation
        if direction is not None:
            params["direction"] = direction
        if factor is not None:
            params["factor"] = factor
        if repeat is not None:
            params["repeat"] = repeat
        if threshold is not None:
            params["threshold"] = threshold
        result = await blender.send_command("rig_fix_weights", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "setup_ragdoll":
        params = {"rig_name": object_name}
        if bone_collider_map is not None:
            params["bone_collider_map"] = bone_collider_map
        if preset is not None:
            params["preset"] = preset
        result = await blender.send_command("rig_setup_ragdoll", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retarget":
        params = {}
        if source_rig is not None:
            params["source_rig"] = source_rig
        if target_rig is not None:
            params["target_rig"] = target_rig
        if bone_mapping is not None:
            params["mapping"] = bone_mapping
        result = await blender.send_command("rig_retarget", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "add_shape_keys":
        params = {"object_name": object_name}
        if shape_key_name is not None:
            params["shape_key_name"] = shape_key_name
        if mode is not None:
            params["mode"] = mode
        if vertex_offsets is not None:
            params["vertex_offsets"] = vertex_offsets
        if expression_name is not None:
            params["expression_name"] = expression_name
        result = await blender.send_command("rig_add_shape_keys", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_animation
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_animation(
    action: Literal[
        "generate_walk",       # ANIM-01: Procedural walk/run cycle
        "generate_fly",        # ANIM-02: Procedural fly/hover cycle
        "generate_idle",       # ANIM-03: Procedural idle animation
        "generate_attack",     # ANIM-04: Attack animations (8 types)
        "generate_reaction",   # ANIM-05: Death, hit, spawn animations
        "generate_custom",     # ANIM-06: Custom animation from text
        "preview",             # ANIM-07: Animation contact sheet preview
        "add_secondary",       # ANIM-08: Secondary motion physics bake
        "extract_root_motion", # ANIM-09: Root motion + animation events
        "retarget_mixamo",     # ANIM-10: Mixamo animation retargeting
        "generate_ai_motion",  # ANIM-11: AI motion generation (API + procedural fallback)
        "batch_export",        # ANIM-12: Batch export as Unity clips
    ],
    object_name: str,
    # Walk/run cycle params
    gait: str | None = None,           # biped/quadruped/hexapod/arachnid/serpent
    speed: str | None = None,          # walk/run
    frame_count: int | None = None,
    # Fly/hover params
    frequency: float | None = None,
    amplitude: float | None = None,
    glide_ratio: float | None = None,
    # Idle params
    breathing_intensity: float | None = None,
    # Attack params
    attack_type: str | None = None,
    intensity: float | None = None,
    # Reaction params
    reaction_type: str | None = None,
    direction: str | None = None,
    # Custom animation params
    description: str | None = None,
    # Preview params
    action_name: str | None = None,
    frame_step: int | None = None,
    angles: list[str] | None = None,
    resolution: int | None = None,
    # Secondary motion params
    bone_names: list[str] | None = None,
    # Root motion params
    hip_bone: str | None = None,
    root_bone: str | None = None,
    extract_rotation: bool | None = None,
    # Mixamo retarget params
    source_file: str | None = None,
    # AI motion params
    prompt: str | None = None,
    model: str | None = None,
    style: str | None = None,       # Motion style: realistic/stylized/exaggerated/subtle
    duration: float | None = None,  # Duration in seconds (overrides frame_count)
    # Batch export params
    output_dir: str | None = None,
    naming: str | None = None,
    actions: list[str] | None = None,
    # Visual feedback
    capture_viewport: bool = True,
):
    """Generate, preview, and export game-ready animations for rigged creatures."""
    blender = get_blender_connection()

    if action == "generate_walk":
        params = {"object_name": object_name}
        if gait is not None:
            params["gait"] = gait
        if speed is not None:
            params["speed"] = speed
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_walk", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_fly":
        params = {"object_name": object_name}
        if frequency is not None:
            params["frequency"] = frequency
        if amplitude is not None:
            params["amplitude"] = amplitude
        if glide_ratio is not None:
            params["glide_ratio"] = glide_ratio
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_fly", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_idle":
        params = {"object_name": object_name}
        if frame_count is not None:
            params["frame_count"] = frame_count
        if breathing_intensity is not None:
            params["breathing_intensity"] = breathing_intensity
        result = await blender.send_command("anim_generate_idle", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_attack":
        params = {"object_name": object_name}
        if attack_type is not None:
            params["attack_type"] = attack_type
        if frame_count is not None:
            params["frame_count"] = frame_count
        if intensity is not None:
            params["intensity"] = intensity
        result = await blender.send_command("anim_generate_attack", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_reaction":
        params = {"object_name": object_name}
        if reaction_type is not None:
            params["reaction_type"] = reaction_type
        if direction is not None:
            params["direction"] = direction
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_reaction", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_custom":
        params = {"object_name": object_name}
        if description is not None:
            params["description"] = description
        if frame_count is not None:
            params["frame_count"] = frame_count
        result = await blender.send_command("anim_generate_custom", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "preview":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if frame_step is not None:
            params["frame_step"] = frame_step
        if angles is not None:
            params["angles"] = angles
        if resolution is not None:
            params["resolution"] = resolution
        result = await blender.send_command("anim_preview", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "add_secondary":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if bone_names is not None:
            params["bone_names"] = bone_names
        result = await blender.send_command("anim_add_secondary_motion", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "extract_root_motion":
        params = {"object_name": object_name}
        if action_name is not None:
            params["action_name"] = action_name
        if hip_bone is not None:
            params["hip_bone"] = hip_bone
        if root_bone is not None:
            params["root_bone"] = root_bone
        if extract_rotation is not None:
            params["extract_rotation"] = extract_rotation
        result = await blender.send_command("anim_extract_root_motion", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "retarget_mixamo":
        params = {"object_name": object_name}
        if source_file is not None:
            params["source_file"] = source_file
        if action_name is not None:
            params["action_name"] = action_name
        result = await blender.send_command("anim_retarget_mixamo", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_ai_motion":
        params = {"object_name": object_name}
        if prompt is not None:
            params["prompt"] = prompt
        if model is not None:
            params["model"] = model
        if frame_count is not None:
            params["frame_count"] = frame_count
        if style is not None:
            params["style"] = style
        if duration is not None:
            params["duration"] = duration
        result = await blender.send_command("anim_generate_ai_motion", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "batch_export":
        params = {"object_name": object_name}
        if output_dir is not None:
            params["output_dir"] = output_dir
        if naming is not None:
            params["naming"] = naming
        if actions is not None:
            params["actions"] = actions
        result = await blender.send_command("anim_batch_export", params)
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_environment
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_environment(
    action: Literal[
        "generate_terrain",
        "paint_terrain",
        "carve_river",
        "generate_road",
        "create_water",
        "export_heightmap",
        "scatter_vegetation",
        "scatter_props",
        "create_breakable",
        "add_storytelling_props",
        "sculpt_terrain",
        "generate_multi_biome_world",
    ],
    # Common params
    name: str | None = None,
    terrain_name: str | None = None,
    seed: int | None = None,
    # generate_terrain params
    terrain_type: str | None = None,
    resolution: int | None = None,
    height_scale: float | None = None,
    scale: float | None = None,
    erosion: str | None = None,
    erosion_iterations: int | None = None,
    octaves: int | None = None,
    persistence: float | None = None,
    lacunarity: float | None = None,
    # paint_terrain params
    biome_rules: list[dict] | None = None,
    # carve_river params
    source: list[int] | None = None,
    destination: list[int] | None = None,
    # road / water / river params
    width: float | None = None,
    depth: float | None = None,
    waypoints: list[list[int]] | None = None,
    grade_strength: float | None = None,
    water_level: float | None = None,
    # export_heightmap params
    filepath: str | None = None,
    # scatter_vegetation params
    rules: list[dict] | None = None,
    min_distance: float | None = None,
    max_instances: int | None = None,
    # scatter_props params
    area_name: str | None = None,
    buildings: list[dict] | None = None,
    prop_density: float | None = None,
    # create_breakable params
    prop_type: str | None = None,
    position: list[float] | None = None,
    # add_storytelling_props params (AAA-05)
    target_interior: str | None = None,
    density_modifier: float | None = None,
    prop_types: list[str] | None = None,
    # sculpt_terrain params (GAP-09)
    radius: float | None = None,
    strength: float | None = None,
    operation: str | None = None,
    falloff: str = "smooth",
    heightmap: list[list[float]] | None = None,
    # generate_multi_biome_world params
    biome_count: int | None = None,
    biomes: list[str] | None = None,
    world_size: float | None = None,
    corruption_level: float | None = None,
    building_plots: list[dict] | None = None,
    scatter_vegetation: bool | None = None,
    min_veg_distance: float | None = None,
    max_veg_instances: int | None = None,
    transition_width_m: float | None = None,
    # Visual feedback
    capture_viewport: bool = True
):
    """Environment generation, terrain sculpting, and scatter operations."""
    blender = get_blender_connection()

    if action == "generate_terrain":
        params: dict = {}
        if name is not None:
            params["name"] = name
        if terrain_type is not None:
            params["terrain_type"] = terrain_type
        if resolution is not None:
            params["resolution"] = resolution
        if height_scale is not None:
            params["height_scale"] = height_scale
        if scale is not None:
            params["scale"] = scale
        if seed is not None:
            params["seed"] = seed
        if erosion is not None:
            params["erosion"] = erosion
        if erosion_iterations is not None:
            params["erosion_iterations"] = erosion_iterations
        if octaves is not None:
            params["octaves"] = octaves
        if persistence is not None:
            params["persistence"] = persistence
        if lacunarity is not None:
            params["lacunarity"] = lacunarity
        params["use_controller"] = True
        result = await blender.send_command("env_generate_terrain", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "paint_terrain":
        params = {}
        if name is not None:
            params["name"] = name
        if biome_rules is not None:
            params["biome_rules"] = biome_rules
        if height_scale is not None:
            params["height_scale"] = height_scale
        result = await blender.send_command("env_paint_terrain", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "carve_river":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if source is not None:
            params["source"] = source
        if destination is not None:
            params["destination"] = destination
        if width is not None:
            params["width"] = int(width)
        if depth is not None:
            params["depth"] = depth
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_carve_river", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_road":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if waypoints is not None:
            params["waypoints"] = waypoints
        if width is not None:
            params["width"] = int(width)
        if grade_strength is not None:
            params["grade_strength"] = grade_strength
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_generate_road", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "create_water":
        params = {}
        if name is not None:
            params["name"] = name
        if water_level is not None:
            params["water_level"] = water_level
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        result = await blender.send_command("env_create_water", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "export_heightmap":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if filepath is not None:
            params["filepath"] = filepath
        result = await blender.send_command("env_export_heightmap", params)
        return json.dumps(result, indent=2, default=str)

    elif action == "scatter_vegetation":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        if rules is not None:
            params["rules"] = rules
        if min_distance is not None:
            params["min_distance"] = min_distance
        if seed is not None:
            params["seed"] = seed
        if max_instances is not None:
            params["max_instances"] = max_instances
        result = await blender.send_command("env_scatter_vegetation", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "scatter_props":
        params = {}
        if area_name is not None:
            params["area_name"] = area_name
        if buildings is not None:
            params["buildings"] = buildings
        if prop_density is not None:
            params["prop_density"] = prop_density
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_scatter_props", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "create_breakable":
        params = {}
        if prop_type is not None:
            params["prop_type"] = prop_type
        if position is not None:
            params["position"] = position
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_create_breakable", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "add_storytelling_props":
        params = {}
        if target_interior is not None:
            params["target_interior"] = target_interior
        # NOTE: blender_environment has no dedicated room_type param, so
        # the generic 'name' parameter serves as room_type for this action.
        if name is not None:
            params["room_type"] = name
        if density_modifier is not None:
            params["density_modifier"] = density_modifier
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("env_add_storytelling_props", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "sculpt_terrain":
        params = {}
        if terrain_name is not None:
            params["terrain_name"] = terrain_name
        elif name is not None:
            params["terrain_name"] = name
        if position is not None:
            params["position"] = position
        if radius is not None:
            params["radius"] = radius
        if strength is not None:
            params["strength"] = strength
        if operation is not None:
            params["operation"] = operation
        params["falloff"] = falloff
        if heightmap is not None:
            params["heightmap"] = heightmap
        result = await blender.send_command("terrain_sculpt", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_multi_biome_world":
        params: dict = {}
        if name is not None:
            params["name"] = name
        if seed is not None:
            params["seed"] = seed
        if resolution is not None:
            params["width"] = resolution
            params["height"] = resolution
        if height_scale is not None:
            params["height_scale"] = height_scale
        if scale is not None:
            params["world_size"] = scale
        if world_size is not None:
            params["world_size"] = world_size
        if erosion is not None:
            params["erosion"] = erosion
        if erosion_iterations is not None:
            params["erosion_iterations"] = erosion_iterations
        if biome_count is not None:
            params["biome_count"] = biome_count
        if biomes is not None:
            params["biomes"] = biomes
        if corruption_level is not None:
            params["corruption_level"] = corruption_level
        if building_plots is not None:
            params["building_plots"] = building_plots
        if scatter_vegetation is not None:
            params["scatter_vegetation"] = scatter_vegetation
        if min_veg_distance is not None:
            params["min_veg_distance"] = min_veg_distance
        if max_veg_instances is not None:
            params["max_veg_instances"] = max_veg_instances
        if transition_width_m is not None:
            params["transition_width_m"] = transition_width_m

        result = await blender.send_command("env_generate_multi_biome_world", params)
        biome_names = result.get("biome_names", [])
        veg_count = result.get("vegetation_count", 0)
        corruption_zones = result.get("corruption_zones", 0)
        world_sz = result.get("world_size_m", 512.0)
        flatten_ct = result.get("flatten_zones_applied", 0)
        result["next_steps"] = [
            f"Verify biome distribution: use blender_viewport action=contact_sheet"
            f" object_name='{result.get('name', name)}'",
            f"Biomes generated: {', '.join(biome_names)}",
            f"Vegetation instances: {veg_count}",
            f"Corruption zones (>30%): {corruption_zones}",
            f"Foundation flatten zones: {flatten_ct}",
            f"World size: {world_sz}m",
            "Add river: use blender_environment action=carve_river",
            "Export heightmap: use blender_environment action=export_heightmap",
            "Game-readiness check: use blender_mesh action=game_check",
        ]
        return await _with_screenshot(blender, result, capture_viewport)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_worldbuilding
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_worldbuilding(
    action: Literal[
        "generate_dungeon",
        "generate_cave",
        "generate_town",
        "generate_building",
        "generate_castle",
        "generate_ruins",
        "generate_interior",
        "generate_modular_kit",
        "generate_location",
        "generate_boss_arena",
        "generate_world_graph",
        "generate_linked_interior",
        "generate_multi_floor_dungeon",
        "generate_overrun_variant",
        "generate_easter_egg",
        "prefetch_settlement_props",
        "generate_hearthvale",
    ],
    # Common params (float to accommodate both grid dimensions and building dimensions)
    name: str | None = None,
    width: float | None = None,
    height: float | None = None,
    depth: float | None = None,
    seed: int | None = None,
    # Dungeon params
    min_room_size: int | None = None,
    max_depth: int | None = None,
    cell_size: float | None = None,
    wall_height: float | None = None,
    # Cave params
    fill_probability: float | None = None,
    iterations: int | None = None,
    # Town params
    num_districts: int | None = None,
    # Building params
    floors: int | None = None,
    style: str | None = None,
    # Castle params
    outer_size: float | None = None,
    keep_size: float | None = None,
    tower_count: int | None = None,
    # Ruins params
    damage_level: float | None = None,
    # Interior params
    room_type: str | None = None,
    # Modular kit params
    name_prefix: str | None = None,
    pieces: list[str] | None = None,
    # Location params (WORLD-01)
    location_type: str | None = None,
    building_count: int | None = None,
    path_count: int | None = None,
    poi_count: int | None = None,
    # Boss arena params (WORLD-03)
    arena_type: str | None = None,
    diameter: float | None = None,
    cover_count: int | None = None,
    hazard_zones: int | None = None,
    phase_trigger_count: int | None = None,
    # World graph params (WORLD-04)
    locations: list[dict] | None = None,
    target_distance: float | None = None,
    # Linked interior params (WORLD-05)
    interior_rooms: list[str] | None = None,
    door_positions: list | None = None,
    # Multi-floor dungeon params (WORLD-06)
    num_floors: int | None = None,
    connection_types: list[str] | None = None,
    # Overrun variant params (WORLD-09)
    corruption_level: float | None = None,
    # Easter egg params (WORLD-10)
    secret_room_count: int | None = None,
    hidden_path_count: int | None = None,
    lore_item_count: int | None = None,
    # Prop prefetch params (Phase 36-02)
    prop_manifest: list | None = None,
    veil_pressure: float | None = None,
    # Hearthvale params (Phase 38 -- MESH-13)
    layout_brief: str | None = None,
    # Visual feedback
    capture_viewport: bool = True
):
    """Worldbuilding generation."""
    blender = get_blender_connection()

    if action == "generate_dungeon":
        params: dict = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if min_room_size is not None:
            params["min_room_size"] = min_room_size
        if max_depth is not None:
            params["max_depth"] = max_depth
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        if wall_height is not None:
            params["wall_height"] = wall_height
        result = await blender.send_command("world_generate_dungeon", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_cave":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if fill_probability is not None:
            params["fill_probability"] = fill_probability
        if iterations is not None:
            params["iterations"] = iterations
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        if wall_height is not None:
            params["wall_height"] = wall_height
        result = await blender.send_command("world_generate_cave", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_town":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if num_districts is not None:
            params["num_districts"] = num_districts
        if seed is not None:
            params["seed"] = seed
        if cell_size is not None:
            params["cell_size"] = cell_size
        result = await blender.send_command("world_generate_town", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_hearthvale":
        params = {"name": name or "Hearthvale"}
        if seed is not None:
            params["seed"] = seed
        if width is not None:
            params["radius"] = float(width)
        if layout_brief is not None:
            params["layout_brief"] = layout_brief
        else:
            params["layout_brief"] = (
                "fortified castle-town, winding cobblestone, market square at center, "
                "radial streets from square, military quarter, commerce district"
            )
        if veil_pressure is not None:
            params["veil_pressure"] = veil_pressure
        result = await blender.send_command("world_generate_hearthvale", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_building":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if floors is not None:
            params["floors"] = floors
        if style is not None:
            params["style"] = style
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_building", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_castle":
        params = {}
        if name is not None:
            params["name"] = name
        if outer_size is not None:
            params["outer_size"] = outer_size
        if keep_size is not None:
            params["keep_size"] = keep_size
        if tower_count is not None:
            params["tower_count"] = tower_count
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_castle", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_ruins":
        params = {}
        if name is not None:
            params["name"] = name
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if floors is not None:
            params["floors"] = floors
        if style is not None:
            params["style"] = style
        if damage_level is not None:
            params["damage_level"] = damage_level
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_ruins", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_interior":
        params = {}
        if name is not None:
            params["name"] = name
        if room_type is not None:
            params["room_type"] = room_type
        if width is not None:
            params["width"] = width
        if depth is not None:
            params["depth"] = depth
        if height is not None:
            params["height"] = height
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_interior", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_modular_kit":
        params = {}
        if name_prefix is not None:
            params["name_prefix"] = name_prefix
        if cell_size is not None:
            params["cell_size"] = cell_size
        if pieces is not None:
            params["pieces"] = pieces
        result = await blender.send_command("world_generate_modular_kit", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_location":
        params = {}
        if name is not None:
            params["name"] = name
        if location_type is not None:
            params["location_type"] = location_type
        if building_count is not None:
            params["building_count"] = building_count
        if path_count is not None:
            params["path_count"] = path_count
        if poi_count is not None:
            params["poi_count"] = poi_count
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_location", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_boss_arena":
        params = {}
        if name is not None:
            params["name"] = name
        if arena_type is not None:
            params["arena_type"] = arena_type
        if diameter is not None:
            params["diameter"] = diameter
        if cover_count is not None:
            params["cover_count"] = cover_count
        if hazard_zones is not None:
            params["hazard_zones"] = hazard_zones
        if phase_trigger_count is not None:
            params["phase_trigger_count"] = phase_trigger_count
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_boss_arena", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_world_graph":
        params = {}
        if name is not None:
            params["name"] = name
        if locations is not None:
            params["locations"] = locations
        if target_distance is not None:
            params["target_distance"] = target_distance
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_world_graph", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_linked_interior":
        params = {}
        if name is not None:
            params["name"] = name
        if interior_rooms is not None:
            params["interior_rooms"] = interior_rooms
        if door_positions is not None:
            params["door_positions"] = door_positions
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_linked_interior", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_multi_floor_dungeon":
        params = {}
        if name is not None:
            params["name"] = name
        if num_floors is not None:
            params["num_floors"] = num_floors
        if width is not None:
            params["width"] = int(width)
        if height is not None:
            params["height"] = int(height)
        if min_room_size is not None:
            params["min_room_size"] = min_room_size
        if max_depth is not None:
            params["max_depth"] = max_depth
        if connection_types is not None:
            params["connection_types"] = connection_types
        if cell_size is not None:
            params["cell_size"] = cell_size
        if wall_height is not None:
            params["wall_height"] = wall_height
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_multi_floor_dungeon", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_overrun_variant":
        params = {}
        if name is not None:
            params["name"] = name
        if corruption_level is not None:
            params["corruption_level"] = corruption_level
        if room_type is not None:
            params["room_type"] = room_type
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_overrun_variant", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "generate_easter_egg":
        params = {}
        if name is not None:
            params["name"] = name
        if secret_room_count is not None:
            params["secret_room_count"] = secret_room_count
        if hidden_path_count is not None:
            params["hidden_path_count"] = hidden_path_count
        if lore_item_count is not None:
            params["lore_item_count"] = lore_item_count
        if seed is not None:
            params["seed"] = seed
        result = await blender.send_command("world_generate_easter_egg", params)
        return await _with_screenshot(blender, result, capture_viewport)

    elif action == "prefetch_settlement_props":
        params = {}
        if prop_manifest is not None:
            params["prop_manifest"] = prop_manifest
        if veil_pressure is not None:
            params["veil_pressure"] = veil_pressure
        result = await blender.send_command("world_prefetch_settlement_props", params)
        return result

    return "Unknown action"


# ---------------------------------------------------------------------------
# Compound tool: blender_quality  (AAA quality generators -- v6.0)
# ---------------------------------------------------------------------------

@mcp.tool()
async def blender_quality(
    action: Literal[
        "quality_sword", "quality_axe", "quality_mace", "quality_bow",
        "quality_shield", "quality_staff", "quality_pauldron",
        "quality_chestplate", "quality_gauntlet",
        "creature_mouth", "creature_eyelid", "creature_paw",
        "creature_wing", "creature_serpent", "creature_quadruped",
        "creature_fantasy",
        "riggable_door", "riggable_chain", "riggable_flag",
        "riggable_chest", "riggable_chandelier", "riggable_drawbridge",
        "riggable_rope_bridge", "riggable_hanging_sign",
        "riggable_windmill", "riggable_cage",
        "clothing_generate",
        "vegetation_tree", "vegetation_leaf_cards",
        "smart_material", "trim_sheet", "macro_variation",
    ],
    style: str = "default",
    seed: int = 42,
    size: float = 1.0,
    width: float | None = None,
    height: float | None = None,
    depth: float | None = None,
    thickness: float | None = None,
    edge_bevel: float = 0.003,
    ornament_level: int = 2,
    object_name: str | None = None,
    position: list[float] | None = None,
    capture_viewport: bool = True,
    # Weapon
    blade_length: float = 0.9,
    fuller: bool = True,
    guard_style: str = "cross",
    grip_wrap: str = "leather_spiral",
    pommel_style: str = "disk",
    shaft_length: float = 0.8,
    head_radius: float = 0.04,
    num_flanges: int = 7,
    bow_length: float = 1.2,
    num_layers: int = 3,
    side: str = "left",
    length: float = 3.0,
    # Creature
    tooth_count: int = 20,
    tooth_style: str = "carnivore",
    include_tongue: bool = True,
    eye_radius: float = 0.015,
    paw_type: str = "canine",
    wing_type: str = "bat",
    wingspan: float = 2.0,
    species: str = "wolf",
    base_type: str = "chimera",
    brand: str | None = None,
    # Riggable
    link_count: int = 8,
    candle_count: int = 8,
    chain_length: float = 1.5,
    plank_count: int = 12,
    sag: float = 0.5,
    blade_count: int = 4,
    # Clothing/vegetation
    clothing_type: str = "tunic",
    leaf_type: str = "broadleaf",
    density: float = 0.8,
    # Texture quality
    material_type: str = "aged_stone",
    age: float = 0.5,
    wear_intensity: float = 0.5,
    dirt_intensity: float = 0.5,
):
    """AAA quality generators for weapons, armor, creatures, riggable props, clothing, vegetation, and textures. For buildings/architecture, use asset_pipeline generate_3d with Tripo instead."""
    blender = get_blender_connection()
    pos = tuple(position) if position else (0.0, 0.0, 0.0)
    _style = None if style == "default" else style

    # --- Weapons & Armor ---
    if action == "quality_sword":
        result = await blender.send_command("weapon_quality_sword", {
            "style": _style or "longsword", "blade_length": blade_length,
            "fuller": fuller, "guard_style": guard_style, "grip_wrap": grip_wrap,
            "pommel_style": pommel_style, "edge_bevel": edge_bevel,
            "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_axe":
        result = await blender.send_command("weapon_quality_axe", {
            "style": _style or "battle_axe", "shaft_length": shaft_length,
            "edge_bevel": edge_bevel, "grip_wrap": grip_wrap,
            "pommel_style": pommel_style, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_mace":
        result = await blender.send_command("weapon_quality_mace", {
            "style": _style or "flanged", "shaft_length": shaft_length,
            "head_radius": head_radius, "num_flanges": num_flanges,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_bow":
        result = await blender.send_command("weapon_quality_bow", {
            "style": _style or "longbow", "bow_length": bow_length,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_shield":
        result = await blender.send_command("weapon_quality_shield", {
            "style": _style or "kite", "size": size,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_staff":
        result = await blender.send_command("weapon_quality_staff", {
            "style": _style or "gnarled", "length": length,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_pauldron":
        result = await blender.send_command("weapon_quality_pauldron", {
            "style": _style or "plate", "size": size, "num_layers": num_layers,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level, "side": side,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_chestplate":
        result = await blender.send_command("weapon_quality_chestplate", {
            "style": _style or "plate", "size": size,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "quality_gauntlet":
        result = await blender.send_command("weapon_quality_gauntlet", {
            "style": _style or "plate", "size": size, "side": side,
            "edge_bevel": edge_bevel, "ornament_level": ornament_level,
        })
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Creature Anatomy ---
    elif action == "creature_mouth":
        result = await blender.send_command("creature_mouth_interior", {
            "tooth_count": tooth_count, "tooth_style": tooth_style,
            "include_tongue": include_tongue, "position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_eyelid":
        result = await blender.send_command("creature_eyelid_topology", {
            "eye_radius": eye_radius, "eye_position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_paw":
        result = await blender.send_command("creature_paw", {
            "paw_type": paw_type, "size": size, "position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_wing":
        result = await blender.send_command("creature_wing", {
            "wing_type": wing_type, "wingspan": wingspan, "position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_serpent":
        result = await blender.send_command("creature_serpent_body", {
            "length": length, "size": size, "species": species, "position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_quadruped":
        result = await blender.send_command("creature_quadruped", {
            "species": species, "size": size, "position": list(pos),
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "creature_fantasy":
        params = {"base_type": base_type, "size": size}
        if brand:
            params["brand"] = brand
        result = await blender.send_command("creature_fantasy", params)
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Riggable Props ---
    elif action == "riggable_door":
        result = await blender.send_command("riggable_generate_door", {
            "style": _style or "wooden_plank", "width": width or 1.0,
            "height": height or 2.0, "thickness": thickness or 0.06,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_chain":
        result = await blender.send_command("riggable_generate_chain", {
            "link_count": link_count, "style": _style or "iron",
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_flag":
        result = await blender.send_command("riggable_generate_flag", {
            "width": width or 1.5, "height": height or 1.0,
            "style": _style or "banner",
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_chest":
        result = await blender.send_command("riggable_generate_chest", {
            "style": _style or "wooden", "width": width or 0.6,
            "height": height or 0.4, "depth": depth or 0.4,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_chandelier":
        result = await blender.send_command("riggable_generate_chandelier", {
            "style": _style or "iron_ring", "candle_count": candle_count,
            "chain_length": chain_length,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_drawbridge":
        result = await blender.send_command("riggable_generate_drawbridge", {
            "width": width or 4.0, "length": length, "plank_count": plank_count,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_rope_bridge":
        result = await blender.send_command("riggable_generate_rope_bridge", {
            "length": length, "width": width or 1.2,
            "plank_count": plank_count, "sag": sag,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_hanging_sign":
        result = await blender.send_command("riggable_generate_hanging_sign", {
            "width": width or 0.8, "height": height or 0.5,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_windmill":
        result = await blender.send_command("riggable_generate_windmill", {
            "blade_count": blade_count,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "riggable_cage":
        result = await blender.send_command("riggable_generate_cage", {
            "style": _style or "hanging_cage",
            "width": width or 1.0, "height": height or 1.5,
        })
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Clothing ---
    elif action == "clothing_generate":
        result = await blender.send_command("clothing_generate", {
            "clothing_type": clothing_type, "size": size,
            "style": _style or "default",
        })
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Vegetation ---
    elif action == "vegetation_tree":
        result = await blender.send_command("vegetation_lsystem_tree", {
            "style": _style or "oak", "seed": seed, "size": size,
        })
        return await _with_screenshot(blender, result, capture_viewport)
    elif action == "vegetation_leaf_cards":
        result = await blender.send_command("vegetation_leaf_cards", {
            "leaf_type": leaf_type, "density": density, "seed": seed,
        })
        return await _with_screenshot(blender, result, capture_viewport)

    # --- Texture Quality ---
    elif action == "smart_material":
        result = await blender.send_command("texture_smart_material_code", {
            "material_type": material_type, "object_name": object_name or "target",
            "wear_intensity": wear_intensity, "dirt_intensity": dirt_intensity,
            "age": age,
        })
        return await _with_screenshot(blender, result, capture_viewport, object_name)
    elif action == "trim_sheet":
        result = await blender.send_command("texture_trim_sheet_code", {
            "sheet_name": _style or "medieval_trim",
        })
        return await _with_screenshot(blender, result, capture_viewport, object_name)
    elif action == "macro_variation":
        result = await blender.send_command("texture_macro_variation_code", {
            "object_name": object_name or "target",
        })
        return await _with_screenshot(blender, result, capture_viewport, object_name)

    return "Unknown action"


# ---------------------------------------------------------------------------
# Strip redundant Pydantic "title" fields from every tool schema.
# These auto-generated titles just repeat the property name in Title Case
# and waste ~24% of schema tokens sent to the LLM.
# ---------------------------------------------------------------------------

def _strip_titles(obj: dict | list) -> None:
    """Recursively remove 'title' keys from a JSON-schema dict."""
    if isinstance(obj, dict):
        obj.pop("title", None)
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _strip_titles(v)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _strip_titles(item)


for _tool in mcp._tool_manager._tools.values():
    _strip_titles(_tool.parameters)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
