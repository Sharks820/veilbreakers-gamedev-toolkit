import atexit
import json
import logging
import math
import os
import re
import threading
from collections import deque
from typing import Literal

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
from veilbreakers_mcp.shared.palette_validator import validate_palette as _validate_palette, validate_roughness_map

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
    blender: BlenderConnection, result: dict, capture: bool = True
) -> list:
    """Return structured result + viewport screenshot for mutation tools."""
    parts: list = [json.dumps(result, indent=2, default=str)]
    if capture:
        try:
            screenshot_bytes = await blender.capture_viewport_bytes()
            parts.append(Image(data=screenshot_bytes, format="png"))
        except (OSError, IOError, BlenderCommandError, ConnectionError) as e:
            parts.append(f"[Screenshot capture failed: {e}]")
    return parts


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


def _normalize_map_point(position: list[float] | tuple[float, ...], terrain_size: float) -> tuple[float, float]:
    """Normalize user map positions into centered Blender-world coordinates."""
    if len(position) < 2:
        raise ValueError("Map position must contain at least two coordinates.")

    x = float(position[0])
    y = float(position[1])
    half = terrain_size / 2.0

    # Heuristic: shift from 0..size space to centered (-half..+half) space.
    # We only shift when BOTH coords are in [0, size] AND at least one exceeds
    # 60% of terrain_size — this avoids false positives for coords that are
    # already in centered space (e.g. (60,60) on size=100 should stay put).
    threshold = terrain_size * 0.6
    if 0.0 <= x <= terrain_size and 0.0 <= y <= terrain_size and (x > threshold or y > threshold):
        return (x - half, y - half)
    return (x, y)


def _map_point_to_terrain_cell(
    position: list[float] | tuple[float, ...],
    *,
    terrain_size: float,
    resolution: int,
) -> tuple[int, int]:
    """Convert a world-space map point into a terrain heightmap cell."""
    x, y = _normalize_map_point(position, terrain_size)
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
                round(math.cos(angle) * radius_x, 3),
                round(math.sin(angle) * radius_y, 3),
            ))
    candidate_points.append((0.0, 0.0))

    for index, location in enumerate(locations):
        radius = _estimate_location_radius(location)
        requested = location.get("position")
        anchor: tuple[float, float] | None = None

        if isinstance(requested, (list, tuple)) and len(requested) >= 2:
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

        clamped = (
            max(-half + radius, min(half - radius, anchor[0])),
            max(-half + radius, min(half - radius, anchor[1])),
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
    report = {
        "mesh_targets": mesh_targets,
        "validated_meshes": 0,
        "uv_fixed": [],
        "materials_fixed": [],
        "lod_generated": [],
        "failures": [],
    }

    for mesh_name in mesh_targets:
        report["validated_meshes"] += 1
        try:
            game_ready = await blender.send_command(
                "mesh_check_game_ready",
                {"object_name": mesh_name, "poly_budget": poly_budget, "platform": "pc"},
            )
            checks = game_ready.get("checks", {}) if isinstance(game_ready, dict) else {}
            has_material = bool(checks.get("materials", {}).get("passed", False))
            has_uv = bool(checks.get("uv", {}).get("passed", False))
            if not has_material:
                await blender.send_command(
                    "texture_create_pbr",
                    {"name": mesh_name, "object_name": mesh_name, "texture_size": 1024},
                )
                report["materials_fixed"].append(mesh_name)

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
                report["uv_fixed"].append(mesh_name)

            await blender.send_command(
                "pipeline_generate_lods",
                {"object_name": mesh_name, "ratios": lod_ratios or [0.6, 0.3, 0.12]},
            )
            report["lod_generated"].append(mesh_name)
        except (OSError, ConnectionError, TimeoutError, ValueError, RuntimeError, BlenderCommandError) as exc:
            report["failures"].append({"object_name": mesh_name, "error": str(exc)})

    report["status"] = "success" if not report["failures"] else "partial"
    report["mesh_target_count"] = len(report["mesh_targets"])
    report["mesh_targets_sample"] = report["mesh_targets"][:20]
    report["uv_fixed_count"] = len(report["uv_fixed"])
    report["uv_fixed_sample"] = report["uv_fixed"][:12]
    report["materials_fixed_count"] = len(report["materials_fixed"])
    report["materials_fixed_sample"] = report["materials_fixed"][:12]
    report["lod_generated_count"] = len(report["lod_generated"])
    report["lod_generated_sample"] = report["lod_generated"][:12]
    del report["mesh_targets"]
    del report["uv_fixed"]
    del report["materials_fixed"]
    del report["lod_generated"]
    return report


def _bounds_overlap(a: dict, b: dict, padding: float = 0.0) -> bool:
    """Return True when two 2D room bounds overlap."""
    if "bounds" not in a or "bounds" not in b:
        return False
    a_min = a["bounds"]["min"]
    a_max = a["bounds"]["max"]
    b_min = b["bounds"]["min"]
    b_max = b["bounds"]["max"]
    return not (
        a_max[0] <= b_min[0] + padding
        or b_max[0] <= a_min[0] + padding
        or a_max[1] <= b_min[1] + padding
        or b_max[1] <= a_min[1] + padding
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
    placed[first_name] = {
        "name": first_name,
        "type": first_room.get("type", "generic"),
        "width": first_width,
        "depth": first_depth,
        "height": first_height,
        "bounds": {"min": (0.0, 0.0, 0.0), "max": (first_width, first_depth, first_height)},
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
                "min": (round(min_x, 3), round(min_y, 3), 0.0),
                "max": (round(min_x + width, 3), round(min_y + depth, 3), round(height, 3)),
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
                chosen = (
                    "east",
                    {
                        "name": neighbor,
                        "type": room_lookup[neighbor].get("type", "generic"),
                        "width": width,
                        "depth": depth,
                        "height": height,
                        "bounds": {
                            "min": (round(max_x + 1.5, 3), current_bounds["bounds"]["min"][1], 0.0),
                            "max": (round(max_x + 1.5 + width, 3), current_bounds["bounds"]["min"][1] + depth, round(height, 3)),
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
                "min": (round(max_x + 2.0, 3), round(y_offset, 3), 0.0),
                "max": (round(max_x + 2.0 + width, 3), round(y_offset + depth, 3), round(height, 3)),
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
    code = f"""
import bpy
from mathutils import Vector
depsgraph = bpy.context.evaluated_depsgraph_get()
origin = Vector(({x}, {y}, 10000.0))
direction = Vector((0.0, 0.0, -1.0))
hit, location, normal, face_index, hit_obj, matrix = bpy.context.scene.ray_cast(depsgraph, origin, direction)
if hit and hit_obj and hit_obj.name == "{terrain_name}":
    print(float(location.z))
else:
    print(0.0)
""".strip()

    try:
        result = await blender.send_command("execute_code", {"code": code})
        output = str(result.get("result", {}).get("output", "")).strip()
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
    action: Literal["inspect", "clear", "configure", "list_objects"],
    render_engine: str | None = None,
    fps: int | None = None,
    unit_scale: float | None = None
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
    action: Literal["create", "assign", "modify", "list"],
    name: str | None = None,
    object_name: str | None = None,
    base_color: list[float] | None = None,
    metallic: float | None = None,
    roughness: float | None = None,
    capture_viewport: bool = True
):
    """Manage Blender materials (basic PBR)."""
    blender = get_blender_connection()

    if action == "list":
        result = await blender.send_command("material_list")
        return json.dumps(result, indent=2, default=str)

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
    action: Literal["screenshot", "contact_sheet", "set_shading", "navigate"],
    object_name: str | None = None,
    shading_type: str | None = None,
    camera_position: list[float] | None = None,
    camera_target: list[float] | None = None,
    angles: list[list[float]] | None = None,
    resolution: list[int] | None = None,
    max_size: int = 1024
):
    """Visual verification and viewport control."""
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
        "sculpt_brush", "dyntopo", "voxel_remesh", "face_sets", "multires"
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
    capture_viewport: bool = True
):
    """Mesh topology analysis, repair, editing, booleans, retopology, and sculpting.

    Extended with position-based selection (GAP-01), transform operations (GAP-02),
    loop cuts (GAP-03), bevel (GAP-04), merge/dissolve (GAP-05), and advanced
    sculpt operations: sculpt_brush (32 brush types), dyntopo (dynamic topology),
    voxel_remesh, face_sets, and multires (multiresolution modifier).
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
                __import__("pathlib").Path(_vb3d) / _asset_dirs[asset_type]
            )
            # Use name subfolder if provided
            if name:
                resolved_dir = str(
                    __import__("pathlib").Path(resolved_dir) / name
                )
            output_dir = resolved_dir
        elif output_dir == "." and _vb3d:
            # Fallback: use a known location inside the Unity project
            # so models don't get lost in the MCP server's CWD
            output_dir = str(
                __import__("pathlib").Path(_vb3d) / "Assets/Art/3D_Models/Tripo_Downloads"
            )
            if name:
                output_dir = str(
                    __import__("pathlib").Path(output_dir) / name
                )
        elif output_dir == ".":
            # Last resort: use temp dir with timestamp so models are findable
            import tempfile
            import time
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = str(
                __import__("pathlib").Path(tempfile.gettempdir()) / f"tripo_models_{ts}"
            )

        # Prefer studio (uses subscription credits), fall back to API key
        studio_cookie = settings.tripo_session_cookie
        studio_token = settings.tripo_studio_token
        api_key = settings.tripo_api_key

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
                if verified:
                    spacing = 3.0
                    positions = [
                        (0, 0), (-spacing, 0),
                        (spacing, 0), (0, spacing),
                    ]
                    imported_names = []
                    for i, m in enumerate(verified):
                        px, py = positions[i % len(positions)]
                        safe = m["path"].replace("\\", "/")
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
                            import_result = await blender.send_command(
                                "execute_code", {"code": code}
                            )
                            imported_names.append(f"variant_{i+1}")
                        except Exception as exc:
                            logger.debug(
                                "Failed to import variant %s into Blender: %s",
                                i + 1,
                                exc,
                                exc_info=True,
                            )
                    result["imported_to_blender"] = len(imported_names)
                    result["next_steps"] = [
                        "All variants imported to Blender in a grid layout.",
                        "Pick the best variant, then run: asset_pipeline action=cleanup object_name=<name>",
                        "Or full pipeline: asset_pipeline action=full_pipeline object_name=<name>",
                        "The AAA pipeline will: repair -> retopo -> UV -> PBR materials -> weathering -> quality gate.",
                    ]

                return json.dumps(result, indent=2, default=str)
            finally:
                await gen.close()
        elif api_key:
            gen = TripoGenerator(api_key=api_key)
            if image_path:
                result = await gen.generate_from_image(image_path, output_dir)
            else:
                result = await gen.generate_from_text(prompt, output_dir)
            result["output_dir"] = output_dir
            return json.dumps(result, indent=2, default=str)
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
            output_dir = str(__import__("pathlib").Path(_vb3d) / "Assets/Art/3D_Models/Buildings")
            if name:
                output_dir = str(__import__("pathlib").Path(output_dir) / name)

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
                return json.dumps(result, indent=2, default=str)
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
            return json.dumps(result, indent=2, default=str)

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
        map_name = spec.get("name", "Map")
        map_seed = spec.get("seed", 42)
        budget = _resolve_map_generation_budget(spec)
        planned_locations = _plan_map_location_anchors(spec)
        steps_completed = []
        steps_failed = []
        created_objects = []
        terrain_cfg = spec.get("terrain", {})
        terrain_size = float(terrain_cfg.get("size", 200.0))
        terrain_resolution = min(
            int(terrain_cfg.get("resolution", 256)),
            int(budget["terrain_resolution_cap"]),
        )

        # --- Step 1: Clear scene ---
        try:
            await blender.send_command("clear_scene", {})
            steps_completed.append("scene_cleared")
        except Exception as e:
            steps_failed.append({"step": "scene_clear", "error": str(e)})

        # --- Step 2: Generate terrain ---
        terrain_name = f"{map_name}_Terrain"
        try:
            t_result = await blender.send_command("env_generate_terrain", {
                "name": terrain_name,
                "terrain_type": terrain_cfg.get("preset", "hills"),
                "resolution": terrain_resolution,
                "height_scale": terrain_cfg.get("height_scale", 20.0),
                "scale": terrain_size,
                "seed": map_seed,
                "erosion": "hydraulic" if terrain_cfg.get("erosion", True) else "none",
                "erosion_iterations": terrain_cfg.get("erosion_iterations", 5000),
            })
            steps_completed.append("terrain_generated")
            created_objects.append(terrain_name)
        except Exception as e:
            steps_failed.append({"step": "terrain", "error": str(e)})

        # --- Step 3: Water bodies ---
        water_cfg = spec.get("water", {})
        if water_cfg:
            # Rivers
            for i, river in enumerate(water_cfg.get("rivers", [])):
                try:
                    source = _map_point_to_terrain_cell(
                        river.get("source", [10, 10]),
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                    )
                    destination = _map_point_to_terrain_cell(
                        river.get("destination", [190, 190]),
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                    )
                    await blender.send_command("env_carve_river", {
                        "terrain_name": terrain_name,
                        "source": list(source),
                        "destination": list(destination),
                        "width": river.get("width", 5),
                        "depth": river.get("depth", 2.0),
                        "seed": map_seed + i,
                    })
                    steps_completed.append(f"river_{i}")
                except Exception as e:
                    steps_failed.append({"step": f"river_{i}", "error": str(e)})

            # Water level (lakes/ocean)
            if "water_level" in water_cfg:
                try:
                    await blender.send_command("env_create_water", {
                        "name": f"{map_name}_Water",
                        "water_level": water_cfg["water_level"],
                        "terrain_name": terrain_name,
                    })
                    steps_completed.append("water_plane")
                    created_objects.append(f"{map_name}_Water")
                except Exception as e:
                    steps_failed.append({"step": "water_plane", "error": str(e)})

        # --- Step 4: Roads ---
        for i, road in enumerate(spec.get("roads", [])):
            try:
                waypoints = [
                    list(_map_point_to_terrain_cell(
                        waypoint,
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                    ))
                    for waypoint in road.get("waypoints", [])
                    if isinstance(waypoint, (list, tuple)) and len(waypoint) >= 2
                ]
                if len(waypoints) < 2:
                    raise ValueError("Road generation requires at least two waypoints")
                await blender.send_command("env_generate_road", {
                    "terrain_name": terrain_name,
                    "waypoints": waypoints,
                    "width": road.get("width", 3),
                    "seed": map_seed + 100 + i,
                })
                steps_completed.append(f"road_{i}")
            except Exception as e:
                steps_failed.append({"step": f"road_{i}", "error": str(e)})

        # --- Step 5: Place locations ---
        location_results = []
        _LOC_HANDLERS = {
            "town": "world_generate_town",
            "castle": "world_generate_castle",
            "dungeon": "world_generate_dungeon",
            "cave": "world_generate_cave",
            "ruins": "world_generate_ruins",
            "building": "world_generate_building",
            "boss_arena": "world_generate_boss_arena",
        }
        for i, planned in enumerate(planned_locations):
            loc = planned["source"]
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

                loc_result = await blender.send_command(handler, loc_params)
                anchor_x, anchor_y = planned["anchor"]
                anchor_z = await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y)
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

        # --- Step 6: Biome paint ---
        biome = spec.get("biome")
        if biome:
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

            try:
                await blender.send_command("setup_dark_fantasy_lighting", {
                    "object_name": terrain_name,
                    "preset": _lighting_preset_for_biome(biome),
                })
                steps_completed.append("lighting_ready")
            except Exception as e:
                steps_failed.append({"step": "lighting", "error": str(e)})

        # --- Step 7: Vegetation scatter ---
        veg_cfg = spec.get("vegetation", {})
        if veg_cfg:
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

        # --- Step 8: Prop scatter ---
        if spec.get("props", True):
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
                    raise ValueError("No location anchors available for contextual prop scatter")
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

        # --- Step 9: Generate interiors for key buildings ---
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

        # --- Build result ---
        # Atmosphere presets for Unity next_steps
        quality_report = await _enforce_world_quality(
            blender,
            object_names=created_objects,
            poly_budget=90000 if budget["profile"] != "large_world" else 120000,
        )

        result = {
            "status": "success" if not steps_failed and not quality_report["failures"] else "partial",
            "map_name": map_name,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "objects_created": created_objects,
            "locations": location_results,
            "interiors": interior_results,
            "budget_applied": budget,
            "quality_report": quality_report,
            "next_steps": [
                "Review the generated city in Blender.",
                "Run a hero-pass with Tripo only for standout props or landmark pieces.",
                "Export only after the quality report has no remaining failures.",
            ],
        }
        return await _with_screenshot(blender, result, capture_viewport)

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
        room_plan = _plan_interior_rooms(spec)
        planned_rooms = room_plan["rooms"]
        planned_doors = room_plan["doors"]
        steps_completed = []
        steps_failed = []

        # --- Step 1: Generate linked interior (room shells + door triggers + occlusion) ---
        rooms = spec.get("rooms", [])
        room_defs = []
        for planned_room in planned_rooms:
            room_defs.append({
                "name": planned_room["name"],
                "type": planned_room["type"],
                "bounds": planned_room["bounds"],
            })

        try:
            linked_result = await blender.send_command("world_generate_linked_interior", {
                "name": int_name,
                "building_exterior_bounds": room_plan["building_bounds"],
                "interior_rooms": room_defs,
                "door_positions": planned_doors,
                "seed": int_seed,
            })
            steps_completed.append("linked_interior_created")
        except Exception as e:
            steps_failed.append({"step": "linked_interior", "error": str(e)})

        # --- Step 2: Generate each room with detailed geometry ---
        room_results = []
        room_bounds_by_name = {room["name"]: room for room in planned_rooms}
        for i, room in enumerate(rooms):
            try:
                room_name = room.get("name", f"Room_{i}")
                room_result = await blender.send_command("world_generate_interior", {
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
                    await _position_generated_object(
                        blender,
                        f"{int_name}_{room_name}",
                        (origin[0], origin[1], 0.0),
                    )
                    steps_completed.append(f"room_positioned_{room_name}")
                steps_completed.append(f"room_{room.get('name', i)}")
                room_results.append({
                    "name": room_name,
                    "type": room.get("type", "generic"),
                    "bounds": planned_room["bounds"] if planned_room is not None else None,
                })
            except Exception as e:
                steps_failed.append({"step": f"room_{room.get('name', i)}", "error": str(e)})

        # --- Step 3: Add storytelling/narrative props to each room ---
        if spec.get("storytelling_density", 0) > 0:
            for room in rooms:
                try:
                    await blender.send_command("env_add_storytelling_props", {
                        "target_interior": f"{int_name}_{room.get('name', 'room')}",
                        "room_type": room.get("type", "generic"),
                        "density_modifier": spec.get("storytelling_density", 0.5),
                        "seed": int_seed + 100,
                    })
                    steps_completed.append(f"props_{room.get('name')}")
                except Exception as e:
                    steps_failed.append({"step": f"props_{room.get('name')}", "error": str(e)})

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
            "status": "success" if not steps_failed else "partial",
            "interior_name": int_name,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "rooms_generated": room_results,
            "door_positions": planned_doors,
            "building_bounds": room_plan["building_bounds"],
            "tripo_prop_queue": tripo_queue[:20] if tripo_queue else [],
            "tripo_props_remaining": max(0, len(tripo_queue) - 20),
            "next_steps": [
                "--- ENHANCE VISUALS ---",
                "1. Review interior: blender_viewport action=contact_sheet object_name=<room>",
                "2. Add materials: blender_material action=create (stone_wall, wooden_floor, etc.)",
                "3. Generate hero props with Tripo: asset_pipeline action=generate_3d prompt='dark fantasy <prop>'",
                "--- UNITY INTERIOR SETUP ---",
                "4. Setup interior streaming: unity_world action=create_interior_streaming",
                "5. Setup door system: unity_world action=create_door_system",
                "6. Dungeon lighting: unity_world action=create_dungeon_lighting",
                "7. Portal audio: unity_audio action=setup_portal_audio",
                "8. Occlusion: unity_world action=setup_occlusion",
                "9. NPC placement: unity_world action=create_npc_placement",
                "10. Interaction prompts: unity_ux action=interaction_prompt",
            ],
        }
        if tripo_queue:
            result["next_steps"].insert(0, f"TRIPO QUEUE: {len(tripo_queue)} props to generate. Run each with: asset_pipeline action=generate_3d prompt='<prompt>'")

        return json.dumps(result, indent=2, default=str)

    elif action == "cleanup":
        if not object_name:
            return "ERROR: 'object_name' is required for cleanup"
        runner = PipelineRunner(blender, settings)
        result = await runner.cleanup_ai_model(object_name, poly_budget)
        return await _with_screenshot(blender, result, capture_viewport)

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
        safe_path = filepath.replace("\\", "/")
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
        safe_path = filepath.replace("\\", "/")
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
# Compound tool: concept_art
# ---------------------------------------------------------------------------

@mcp.tool()
async def concept_art(
    action: Literal["generate", "extract_palette", "style_board", "silhouette_test"],
    # generate params
    prompt: str | None = None,
    style: str = "fantasy",
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
        return json.dumps(result, indent=2, default=str)
    elif action == "trim_sheet":
        result = await blender.send_command("texture_trim_sheet_code", {
            "sheet_name": _style or "medieval_trim",
        })
        return json.dumps(result, indent=2, default=str)
    elif action == "macro_variation":
        result = await blender.send_command("texture_macro_variation_code", {
            "object_name": object_name or "target",
        })
        return json.dumps(result, indent=2, default=str)

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
