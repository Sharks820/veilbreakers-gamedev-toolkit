"""Generate a Blender starter-city test map with the latest toolkit code."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "mcp-toolkit"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from veilbreakers_mcp.blender_server import asset_pipeline, get_blender_connection  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULT_PATH = OUTPUT_DIR / "starter_city_result.json"


RELOAD_CODE = """
import importlib
import blender_addon.handlers as handlers
import blender_addon.handlers._building_grammar as bg
import blender_addon.handlers.settlement_generator as sg
import blender_addon.handlers.worldbuilding as wb
import blender_addon.handlers.worldbuilding_layout as wl
importlib.reload(bg)
importlib.reload(sg)
importlib.reload(wb)
importlib.reload(wl)
importlib.reload(handlers)
handlers.COMMAND_HANDLERS["world_generate_building"] = wb.handle_generate_building
handlers.COMMAND_HANDLERS["world_generate_settlement"] = wb.handle_generate_settlement
handlers.COMMAND_HANDLERS["world_generate_town"] = wl.handle_generate_town
{"status": "reloaded"}
""".strip()


MAP_SPEC = {
    "name": "StarterCity_Overworld_Test",
    "seed": 1337,
    "performance_budget": "balanced_pc",
    "layout_brief": (
        "fortified waterfront trade city with terraced upper wards, a ridge keep, "
        "varied street rhythm, walkable civic buildings, and a sorcery annex on the slope"
    ),
    "terrain": {
        "preset": "hills",
        "size": 220.0,
        "resolution": 192,
        "height_scale": 16.0,
        "erosion": True,
        "erosion_iterations": 7000,
    },
    "water": {
        "rivers": [
            {"source": [-82.0, 72.0], "destination": [88.0, -74.0], "width": 7.0},
        ],
        "water_level": 1.6,
    },
    "roads": [
        {"waypoints": [[-84.0, -12.0], [-35.0, -4.0], [14.0, 10.0], [82.0, 26.0]], "width": 4.2},
        {"waypoints": [[-60.0, -66.0], [-18.0, -24.0], [26.0, -12.0], [90.0, -6.0]], "width": 3.6},
        {"waypoints": [[-12.0, 84.0], [4.0, 32.0], [18.0, 8.0], [34.0, -26.0]], "width": 3.1},
    ],
    "locations": [
        {
            "type": "town",
            "name": "StarterCity",
            "districts": 5,
            "grid_size": 48,
            "layout_brief": (
                "terraced fortified waterfront trade city with a market quarter, "
                "guild streets, varied rowhouses, and an upper noble ward"
            ),
        },
        {
            "type": "castle",
            "name": "NorthwatchKeep",
            "outer_size": 52,
            "keep_size": 16,
            "description": "ridge citadel overlooking the city and the river mouth",
        },
        {
            "type": "building",
            "name": "HarborTavern",
            "building_size": "large",
            "width": 18,
            "depth": 12,
            "floors": 2,
            "layout_brief": "busy merchant tavern with broad doors and player-usable room scale",
        },
        {
            "type": "building",
            "name": "AcademyAnnex",
            "building_size": "large",
            "width": 20,
            "depth": 14,
            "floors": 3,
            "layout_brief": "cliffside sorcery annex with tall bays, study rooms, and ritual balconies",
        },
        {
            "type": "ruins",
            "name": "OldGateRuins",
            "outer_size": 24,
            "width": 18,
            "depth": 14,
            "floors": 2,
            "damage_level": 0.48,
            "description": "collapsed outer gate ruins near the southern road",
        },
    ],
    "vegetation": {
        "density": 0.7,
        "max_instances": 3200,
        "rules": [
            {"vegetation_type": "tree", "density": 0.5, "min_alt": 0.08, "max_alt": 0.72, "min_slope": 0.0, "max_slope": 24.0, "scale_range": [0.95, 1.65]},
            {"vegetation_type": "bush", "density": 0.62, "min_alt": 0.02, "max_alt": 0.58, "min_slope": 0.0, "max_slope": 30.0, "scale_range": [0.55, 1.15]},
            {"vegetation_type": "grass", "density": 0.86, "min_alt": 0.0, "max_alt": 0.48, "min_slope": 0.0, "max_slope": 28.0, "scale_range": [0.35, 0.78]},
            {"vegetation_type": "rock", "density": 0.26, "min_alt": 0.28, "max_alt": 1.0, "min_slope": 16.0, "max_slope": 90.0, "scale_range": [0.55, 1.2]},
        ],
    },
    "prop_density": 0.42,
    "biome": "thornwood_forest",
    "atmosphere": "overcast",
}


async def _main() -> None:
    blender = get_blender_connection()
    try:
        reload_result = await blender.send_command("execute_code", {"code": RELOAD_CODE})
    except Exception as exc:  # noqa: BLE001
        reload_result = {"status": "skipped", "error": str(exc)}
    result = await asset_pipeline(
        action="compose_map",
        map_spec=MAP_SPEC,
        capture_viewport=False,
    )

    if isinstance(result, list):
        result_payload = result[0] if result else "{}"
    else:
        result_payload = result

    parsed = json.loads(result_payload)
    parsed["reload_result"] = reload_result
    objects = await blender.send_command("list_objects", {})
    object_names = [obj.get("name", "") for obj in objects if isinstance(obj, dict)]
    parsed["scene_summary"] = {
        "object_count": len(object_names),
        "facade_object_count": sum(1 for name in object_names if "_Facade_" in name),
        "foundation_object_count": sum(1 for name in object_names if "_Foundation" in name),
        "retaining_wall_count": sum(1 for name in object_names if "_Retaining_" in name),
    }
    try:
        screenshot = await blender.send_command(
            "get_viewport_screenshot",
            {"filepath": str(OUTPUT_DIR / "starter_city_viewport.png"), "format": "png"},
        )
        parsed["viewport_screenshot"] = screenshot.get("filepath", screenshot)
    except Exception as exc:  # noqa: BLE001
        parsed["viewport_screenshot_error"] = str(exc)
    RESULT_PATH.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    print(RESULT_PATH)
    print(json.dumps({
        "status": parsed.get("status"),
        "steps_failed": len(parsed.get("steps_failed", [])),
        "objects_created": parsed.get("objects_created", []),
        "scene_summary": parsed.get("scene_summary", {}),
        "quality_status": parsed.get("quality_report", {}).get("status"),
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
