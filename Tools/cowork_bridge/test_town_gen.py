"""Test: clear scene and use world_generate_town for a coherent layout."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out, exist_ok=True)

print("=== Clean Slate Test ===", flush=True)

# Nuke everything
blender("clear_scene")
print("Scene cleared", flush=True)

# Add camera
blender("execute_code", code="""
import bpy
bpy.ops.object.camera_add(location=(80, -60, 50))
cam = bpy.context.object
cam.name = 'MainCam'
bpy.context.scene.camera = cam
from mathutils import Vector
direction = Vector((35, 35, 5)) - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
""")

# Test world_generate_town
print("Generating town...", flush=True)
try:
    r = blender("world_generate_town",
        town_type="medieval",
        width=80,
        height=80,
        building_count=8,
        has_walls=True,
        has_market=True,
        seed=42
    )
    print(f"Town result: {json.dumps(r, default=str)[:500]}", flush=True)
except Exception as e:
    print(f"Town error: {e}", flush=True)
    print("Trying world_generate_location instead...", flush=True)
    try:
        r = blender("world_generate_location",
            location_type="town",
            poi_count=8,
            seed=42
        )
        print(f"Location result: {json.dumps(r, default=str)[:500]}", flush=True)
    except Exception as e2:
        print(f"Location error: {e2}", flush=True)

# Screenshot
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "town_gen_test.png"))
print(f"Screenshot: {p}", flush=True)

# Object inventory
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])
print(f"\nObjects: {len(obj_list)}", flush=True)
types = {}
for obj in obj_list:
    t = obj.get("type", "?")
    types[t] = types.get(t, 0) + 1
    name = obj.get("name", "?")
    loc = obj.get("location", [0,0,0])
    if t == "MESH":
        print(f"  {name} @ ({loc[0]:.0f},{loc[1]:.0f},{loc[2]:.0f})", flush=True)
print(f"Types: {types}", flush=True)

print("Done", flush=True)
