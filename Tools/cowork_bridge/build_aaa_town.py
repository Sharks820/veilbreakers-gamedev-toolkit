"""Build AAA town: generate building, post-process for quality, render."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out, exist_ok=True)

# Clear scene
blender("clear_scene")

# Add camera + lighting
r = blender("execute_code", code="""
import bpy
from mathutils import Vector

# Camera
bpy.ops.object.camera_add(location=(20, -15, 12))
cam = bpy.context.object
cam.name = 'MainCam'
bpy.context.scene.camera = cam
d = Vector((5, 4, 3)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

# Sun - warm amber (Waking Shore sunset)
bpy.ops.object.light_add(type='SUN', location=(15, -10, 20))
sun = bpy.context.object
sun.data.energy = 4.0
sun.data.color = (1.0, 0.85, 0.65)
d = Vector((5, 5, 0)) - sun.location
sun.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

# Cool fill
bpy.ops.object.light_add(type='SUN', location=(-15, 10, 15))
fill = bpy.context.object
fill.data.energy = 1.0
fill.data.color = (0.6, 0.65, 0.8)

# World
world = bpy.data.worlds.new('DarkWorld')
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.02, 0.025, 0.04, 1)
bg.inputs['Strength'].default_value = 0.5

print('Scene setup done')
""")
print(f"Setup: {r.get('output','ok') if isinstance(r, dict) else 'ok'}", flush=True)

# Generate building
print("Generating building...", flush=True)
r = blender("world_generate_building",
    building_type="tavern",
    width=10.0, depth=8.0,
    floors=2, style="medieval",
    wall_height=3.5, seed=42
)
print(f"Building: {json.dumps(r, default=str)[:200]}", flush=True)

# Post-process: fix materials, join walls, cut windows
print("Post-processing...", flush=True)
r = blender("execute_code", code="""
import bpy, bmesh, math

# === STEP 1: Apply dark fantasy materials to each component type ===
mat_defs = {
    'VB_Stone': ((0.22, 0.19, 0.16, 1), 0.88, 0.0),
    'VB_DarkStone': ((0.14, 0.12, 0.10, 1), 0.92, 0.0),
    'VB_Timber': ((0.22, 0.13, 0.06, 1), 0.7, 0.0),
    'VB_Slate': ((0.16, 0.16, 0.20, 1), 0.78, 0.0),
    'VB_Glass': ((0.12, 0.18, 0.25, 1), 0.15, 0.0),
    'VB_Iron': ((0.12, 0.12, 0.14, 1), 0.5, 0.82),
    'VB_Plaster': ((0.42, 0.38, 0.32, 1), 0.92, 0.0),
    'VB_Floor': ((0.2, 0.15, 0.1, 1), 0.8, 0.0),
}

mats = {}
for name, (color, rough, metal) in mat_defs.items():
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal
    mats[name] = mat

# Apply materials by object name pattern
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    mat = None
    if 'wall' in n:
        mat = mats['VB_Stone']
    elif 'window' in n:
        mat = mats['VB_Glass']
    elif 'door' in n or 'arch' in n:
        mat = mats['VB_DarkStone']
    elif 'roof' in n:
        mat = mats['VB_Slate']
    elif 'timber' in n or 'beam' in n or 'frame' in n:
        mat = mats['VB_Timber']
    elif 'stair' in n or 'step' in n:
        mat = mats['VB_Floor']
    elif 'interior' in n or 'floor' in n:
        mat = mats['VB_Plaster']
    elif 'iron' in n or 'metal' in n:
        mat = mats['VB_Iron']
    
    if mat:
        obj.data.materials.clear()
        obj.data.materials.append(mat)

# === STEP 2: Add ground plane ===
bpy.ops.mesh.primitive_plane_add(size=30, location=(5, 4, -0.02))
ground = bpy.context.object
ground.name = 'Ground'
gmat = bpy.data.materials.new('VB_Ground')
gmat.use_nodes = True
gb = gmat.node_tree.nodes['Principled BSDF']
gb.inputs['Base Color'].default_value = (0.18, 0.15, 0.12, 1)
gb.inputs['Roughness'].default_value = 0.95
ground.data.materials.append(gmat)

# === STEP 3: Join all wall meshes for unified appearance ===
# Select all wall objects
bpy.ops.object.select_all(action='DESELECT')
wall_objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'Wall' in o.name]
if wall_objs:
    for w in wall_objs:
        w.select_set(True)
    bpy.context.view_layer.objects.active = wall_objs[0]
    bpy.ops.object.join()
    # Remove doubles at corners
    joined = bpy.context.object
    joined.name = 'Building_Walls_Joined'
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.01)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Re-apply material
    joined.data.materials.clear()
    joined.data.materials.append(mats['VB_Stone'])
    print(f'Walls joined: {len(joined.data.vertices)}v')

# === STEP 4: Join all window meshes ===
bpy.ops.object.select_all(action='DESELECT')
win_objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'Window' in o.name]
if win_objs:
    for w in win_objs:
        w.select_set(True)
    bpy.context.view_layer.objects.active = win_objs[0]
    bpy.ops.object.join()
    joined_win = bpy.context.object
    joined_win.name = 'Building_Windows'
    joined_win.data.materials.clear()
    joined_win.data.materials.append(mats['VB_Glass'])
    print(f'Windows joined: {len(joined_win.data.vertices)}v')

print('Post-processing done')
""")
print(f"Post-process: {r.get('output','') if isinstance(r, dict) else ''}", flush=True)

# Set material preview + proper viewport angle
blender("execute_code", code="""
import bpy
from mathutils import Quaternion, Vector
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        space = area.spaces[0]
        space.shading.type = 'MATERIAL'
        space.shading.use_scene_lights = True
        space.shading.use_scene_world = True
        r3d = space.region_3d
        r3d.view_perspective = 'PERSP'
        break
""")

# Take screenshots
views = [
    ("aaa_front_34", (5, 4, 4), 18, (0.78, 0.33, -0.15, 0.51)),
    ("aaa_street", (2, -2, 2.5), 12, (0.82, 0.35, -0.1, 0.45)),
    ("aaa_corner", (5, 4, 5), 22, (0.75, 0.25, -0.25, 0.55)),
    ("aaa_closeup_wall", (1, 1, 2), 5, (0.78, 0.33, -0.15, 0.51)),
    ("aaa_top", (5, 4, 0), 25, (1, 0, 0, 0)),
]

for label, loc, dist, rot in views:
    blender("execute_code", code=f"""
import bpy
from mathutils import Quaternion, Vector
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        r3d = area.spaces[0].region_3d
        r3d.view_location = Vector({list(loc)})
        r3d.view_distance = {dist}
        r3d.view_rotation = Quaternion({list(rot)})
        r3d.view_perspective = 'PERSP'
        break
""")
    r = blender("get_viewport_screenshot")
    p = r.get("filepath", r) if isinstance(r, dict) else r
    shutil.copy2(p, os.path.join(out, f"{label}.png"))
    print(f"  {label}: saved", flush=True)

print("\n=== AAA Building Test Complete ===", flush=True)
