"""Build a lit dark-forest probe scene in Blender for fast visual checks."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vb_bridge import blender  # noqa: E402


OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = OUT_DIR / "dark_forest_probe.json"
SCREENSHOT_PATH = OUT_DIR / "dark_forest_probe.png"


def main() -> None:
    blender("clear_scene")

    terrain_name = "DarkForestProbeTerrain"
    blender(
        "env_generate_terrain",
        name=terrain_name,
        terrain_type="thornwood_forest",
        resolution=128,
        height_scale=12.0,
        scale=90.0,
        seed=127,
        erosion="hydraulic",
        erosion_iterations=1800,
    )
    blender(
        "terrain_create_biome_material",
        biome_name="thornwood_forest",
        object_name=terrain_name,
    )
    blender(
        "env_scatter_vegetation",
        terrain_name=terrain_name,
        rules=[
            {"vegetation_type": "tree_healthy", "density": 0.20, "min_alt": 0.10, "max_alt": 0.72, "min_slope": 0.0, "max_slope": 24.0, "scale_range": [1.0, 1.8]},
            {"vegetation_type": "tree_boundary", "density": 0.14, "min_alt": 0.14, "max_alt": 0.82, "min_slope": 0.0, "max_slope": 28.0, "scale_range": [0.95, 1.8]},
            {"vegetation_type": "tree_blighted", "density": 0.05, "min_alt": 0.22, "max_alt": 0.92, "min_slope": 0.0, "max_slope": 32.0, "scale_range": [0.8, 1.4]},
            {"vegetation_type": "shrub", "density": 0.30, "min_alt": 0.05, "max_alt": 0.62, "min_slope": 0.0, "max_slope": 34.0, "scale_range": [0.7, 1.2]},
            {"vegetation_type": "grass", "density": 0.42, "min_alt": 0.0, "max_alt": 0.44, "min_slope": 0.0, "max_slope": 30.0, "scale_range": [0.55, 0.95]},
            {"vegetation_type": "rock_mossy", "density": 0.12, "min_alt": 0.28, "max_alt": 1.0, "min_slope": 14.0, "max_slope": 90.0, "scale_range": [0.75, 1.35]},
        ],
        min_distance=2.4,
        seed=211,
        max_instances=420,
    )
    blender(
        "setup_dark_fantasy_lighting",
        object_name=terrain_name,
        preset="forest_transition",
    )
    blender("setup_beauty_scene", object_name=terrain_name)

    blender(
        "execute_code",
        code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = True
""",
    )

    screenshot = blender("get_viewport_screenshot")
    shot_path = screenshot.get("filepath", screenshot) if isinstance(screenshot, dict) else screenshot
    shutil.copy2(shot_path, SCREENSHOT_PATH)

    scene_summary = blender(
        "execute_code",
        code="""
import bpy, json
counts = {}
for obj in bpy.data.objects:
    if obj.name.startswith(('tree_', 'shrub_', 'grass_', 'rock_')):
        prefix = obj.name.split('_')[0]
        counts[prefix] = counts.get(prefix, 0) + 1
terrain = bpy.data.objects.get('DarkForestProbeTerrain')
materials = []
if terrain and terrain.type == 'MESH':
    materials = [m.name for m in terrain.data.materials if m]
print(json.dumps({
    'object_count': len(bpy.data.objects),
    'scatter_counts': counts,
    'terrain_materials': materials,
}))
""",
    )
    output = scene_summary.get("output", "") if isinstance(scene_summary, dict) else ""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    summary_data = json.loads(lines[-1]) if lines else {}
    summary_data["viewport_screenshot"] = str(SCREENSHOT_PATH)
    SUMMARY_PATH.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(SUMMARY_PATH)
    print(json.dumps(summary_data, indent=2))


if __name__ == "__main__":
    main()
