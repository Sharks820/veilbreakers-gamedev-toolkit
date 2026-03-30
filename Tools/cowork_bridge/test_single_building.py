"""Clean test: one building, properly framed, multiple angles."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

# Clear everything
blender("clear_scene")
print("Scene cleared", flush=True)

# Add camera
blender("execute_code", code="""
import bpy
bpy.ops.object.camera_add(location=(15, -12, 10))
cam = bpy.context.object
cam.name = 'TestCam'
bpy.context.scene.camera = cam
from mathutils import Vector
d = Vector((5, 4, 3)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
# Add sun
bpy.ops.object.light_add(type='SUN', location=(10, -8, 15))
sun = bpy.context.object
sun.data.energy = 3.0
sun.data.color = (1.0, 0.9, 0.75)
""")

# Generate a single tavern building using world_generate_building
print("Generating tavern...", flush=True)
r = blender("world_generate_building",
    building_type="tavern",
    width=10.0,
    depth=8.0,
    floors=2,
    style="medieval",
    wall_height=3.5,
    seed=42
)
print(f"Result: {json.dumps(r, default=str)[:400]}", flush=True)

# Set material preview mode
blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = True
                break
# Dark background
world = bpy.context.scene.world or bpy.data.worlds.new('W')
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.03, 0.035, 0.05, 1)
    bg.inputs['Strength'].default_value = 0.4
""")

# Take screenshots from multiple angles
angles = [
    ("bldg_front", (12, -8, 8), (5, 4, 4)),
    ("bldg_corner", (15, -5, 7), (5, 4, 3)),
    ("bldg_side", (-5, 4, 6), (5, 4, 3)),
    ("bldg_back", (5, 15, 7), (5, 4, 3)),
    ("bldg_top", (5, 4, 20), (5, 4, 0)),
    ("bldg_street", (2, -3, 2), (5, 4, 2)),
]
for label, pos, tgt in angles:
    blender("execute_code", code=f"""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = {list(pos)}
d = Vector({list(tgt)}) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
""")
    r = blender("get_viewport_screenshot")
    p = r.get("filepath", r) if isinstance(r, dict) else r
    shutil.copy2(p, os.path.join(out, f"{label}.png"))
    print(f"  {label}: saved", flush=True)

# Mesh analysis
print("\n--- Mesh Analysis ---", flush=True)
blender("execute_code", code="""
import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        v = len(obj.data.vertices)
        f = len(obj.data.polygons)
        mats = [m.name for m in obj.data.materials if m]
        print(f'  {obj.name}: {v}v {f}f mats={mats}')
""")

print("\nDone", flush=True)
