"""Build and inspect a small live vegetation scatter scene in Blender."""

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
SUMMARY_PATH = OUT_DIR / "environment_scatter_probe.json"


def _mesh_snapshot(name: str) -> dict:
    code = f"""
import bpy
import json
obj = bpy.data.objects.get("{name}")
if obj is None or obj.type != "MESH" or obj.data is None:
    print(json.dumps({{"name": "{name}", "exists": False}}))
else:
    mats = [mat.name for mat in obj.data.materials if mat]
    print(json.dumps({{
        "name": obj.name,
        "exists": True,
        "vertices": len(obj.data.vertices),
        "polygons": len(obj.data.polygons),
        "dimensions": [round(v, 4) for v in obj.dimensions[:]],
        "materials": mats,
    }}))
""".strip()
    raw = blender("execute_code", code=code)
    output = raw.get("output", "") if isinstance(raw, dict) else ""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return {"name": name, "exists": False, "error": "no_output"}
    return json.loads(lines[-1])


def main() -> None:
    blender("clear_scene")
    terrain_result = blender(
        "env_generate_terrain",
        name="ScatterProbeTerrain",
        terrain_type="plains",
        resolution=96,
        height_scale=5.0,
        scale=70.0,
        seed=77,
        erosion="hydraulic",
        erosion_iterations=1200,
    )
    vegetation_result = blender(
        "env_scatter_vegetation",
        terrain_name="ScatterProbeTerrain",
        rules=[
            {"vegetation_type": "tree", "density": 0.22, "min_alt": 0.10, "max_alt": 0.60, "min_slope": 0.0, "max_slope": 28.0, "scale_range": [0.85, 1.35]},
            {"vegetation_type": "bush", "density": 0.38, "min_alt": 0.06, "max_alt": 0.58, "min_slope": 0.0, "max_slope": 32.0, "scale_range": [0.75, 1.25]},
            {"vegetation_type": "grass", "density": 0.58, "min_alt": 0.0, "max_alt": 0.54, "min_slope": 0.0, "max_slope": 30.0, "scale_range": [0.55, 0.95]},
            {"vegetation_type": "rock", "density": 0.14, "min_alt": 0.24, "max_alt": 1.0, "min_slope": 12.0, "max_slope": 90.0, "scale_range": [0.65, 1.2]},
        ],
        min_distance=2.2,
        seed=88,
        max_instances=260,
    )
    props_result = blender(
        "env_scatter_props",
        area_name="ScatterProbeProps",
        buildings=[
            {"type": "tavern", "position": [12.0, 10.0], "footprint": [8.0, 6.0]},
            {"type": "market", "position": [-10.0, -8.0], "footprint": [10.0, 8.0]},
        ],
        prop_density=0.22,
        seed=91,
    )

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
    screenshot_path = screenshot.get("filepath", screenshot) if isinstance(screenshot, dict) else screenshot
    copied_shot = OUT_DIR / "environment_scatter_probe.png"
    shutil.copy2(screenshot_path, copied_shot)

    summary = {
        "terrain_result": terrain_result,
        "vegetation_result": vegetation_result,
        "props_result": props_result,
        "templates": {
            "tree": _mesh_snapshot("_template_tree"),
            "bush": _mesh_snapshot("_template_bush"),
            "grass": _mesh_snapshot("_template_grass"),
            "rock": _mesh_snapshot("_template_rock"),
            "crate": _mesh_snapshot("_template_crate"),
        },
        "viewport_screenshot": str(copied_shot),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(SUMMARY_PATH)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
