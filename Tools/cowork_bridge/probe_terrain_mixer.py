"""Probe the live Blender Terrain Mixer addon setup."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vb_bridge import blender  # noqa: E402


CODE = """
import bpy

bpy.ops.preferences.addon_disable(module="bl_ext.blender_org.terrainmixer")
bpy.ops.preferences.addon_enable(module="bl_ext.blender_org.terrainmixer")

before_collections = [c.name for c in bpy.data.collections if c.name.startswith("TerrainMixer")]
before_objects = [o.name for o in bpy.data.objects if o.name.startswith(("TerrainMixer", "WorkingCamera", "OrthoCamera4Baking", "VIEWPORT_3D_VIEW"))]

result = bpy.ops.object.replace_with_terrain()

after_collections = [c.name for c in bpy.data.collections if c.name.startswith("TerrainMixer")]
after_objects = [o.name for o in bpy.data.objects if o.name.startswith(("TerrainMixer", "WorkingCamera", "OrthoCamera4Baking", "VIEWPORT_3D_VIEW"))]

print({
    "before_collections": before_collections,
    "before_objects": before_objects[:80],
    "operator_result": list(result),
    "after_collections": after_collections,
    "after_objects": after_objects[:120],
})
""".strip()


def main() -> None:
    result = blender("execute_code", code=CODE)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
