"""Phase 4: PBR materials + vegetation + prop scatter."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

print("=== Phase 4: PBR Materials ===", flush=True)

# Create AAA PBR materials with proper nodes
materials = {
    "AAA_Stone": {"color": (0.3, 0.28, 0.25, 1), "roughness": 0.85, "metallic": 0.0},
    "AAA_DarkStone": {"color": (0.18, 0.16, 0.15, 1), "roughness": 0.9, "metallic": 0.0},
    "AAA_MossStone": {"color": (0.22, 0.25, 0.18, 1), "roughness": 0.88, "metallic": 0.0},
    "AAA_Wood": {"color": (0.28, 0.18, 0.1, 1), "roughness": 0.7, "metallic": 0.0},
    "AAA_DarkWood": {"color": (0.15, 0.09, 0.05, 1), "roughness": 0.75, "metallic": 0.0},
    "AAA_Timber": {"color": (0.35, 0.22, 0.12, 1), "roughness": 0.65, "metallic": 0.0},
    "AAA_Slate": {"color": (0.22, 0.22, 0.25, 1), "roughness": 0.8, "metallic": 0.0},
    "AAA_Iron": {"color": (0.2, 0.2, 0.22, 1), "roughness": 0.45, "metallic": 0.85},
    "AAA_Plaster": {"color": (0.55, 0.5, 0.45, 1), "roughness": 0.9, "metallic": 0.0},
    "AAA_Cobble": {"color": (0.25, 0.22, 0.2, 1), "roughness": 0.88, "metallic": 0.0},
    "AAA_Thatch": {"color": (0.4, 0.32, 0.18, 1), "roughness": 0.95, "metallic": 0.0},
    "AAA_Glass": {"color": (0.4, 0.45, 0.5, 0.3), "roughness": 0.1, "metallic": 0.0},
    "AAA_Leather": {"color": (0.25, 0.15, 0.08, 1), "roughness": 0.7, "metallic": 0.0},
    "AAA_Dirt": {"color": (0.3, 0.25, 0.18, 1), "roughness": 0.95, "metallic": 0.0},
}

for mat_name, props in materials.items():
    try:
        blender("material_create",
            name=mat_name,
            base_color=list(props["color"]),
            roughness=props["roughness"],
            metallic=props["metallic"]
        )
        print(f"  Created: {mat_name}", flush=True)
    except Exception as e:
        print(f"  {mat_name}: {e}", flush=True)

# Apply materials to objects by name pattern
print("\n--- Assigning Materials ---", flush=True)
assignments = {
    "stone_wall": "AAA_Stone",
    "timber_frame": "AAA_Timber",
    "gothic_window": "AAA_DarkStone",
    "Roof": "AAA_Slate",
    "roof": "AAA_Slate",
    "Chimney": "AAA_Stone",
    "chimney": "AAA_Stone",
    "archway": "AAA_DarkStone",
    "battlement": "AAA_Stone",
    "Building": "AAA_Stone",
    "Castle": "AAA_DarkStone",
    "Wall": "AAA_Stone",
    "Well": "AAA_Stone",
    "Road": "AAA_Cobble",
    "Market": "AAA_Cobble",
    "AAA_Terrain": "AAA_Dirt",
}

# Get object list
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])

for obj in obj_list:
    name = obj.get("name", "")
    obj_type = obj.get("type", "")
    if obj_type != "MESH":
        continue
    
    for pattern, mat_name in assignments.items():
        if pattern.lower() in name.lower():
            try:
                blender("material_assign", name=mat_name, object_name=name)
            except:
                pass
            break

print("  Materials assigned", flush=True)

# Add vegetation scatter on terrain
print("\n--- Vegetation ---", flush=True)
try:
    r = blender("env_scatter_vegetation",
        terrain_name="AAA_Terrain",
        rules=[
            {"type": "grass", "density": 0.4, "min_slope": 0, "max_slope": 30},
            {"type": "weed", "density": 0.15, "min_slope": 0, "max_slope": 45},
        ],
        min_distance=1.0,
        max_instances=150,
        seed=42
    )
    print(f"  {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Vegetation: {e}", flush=True)

# Try terrain-specific vegetation again with Terrain name
try:
    r = blender("env_scatter_vegetation",
        terrain_name="Terrain",
        rules=[
            {"type": "grass", "density": 0.4},
        ],
        min_distance=1.0,
        max_instances=100,
        seed=42
    )
    print(f"  Alt vegetation: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Alt vegetation: {e}", flush=True)

# Setup dark fantasy lighting
print("\n--- Dark Fantasy Lighting ---", flush=True)
blender("execute_code", code="""
import bpy
from mathutils import Vector

# Remove old lights
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

# Key light - warm sunset angle (the Waking Shore's "last light")
sun = bpy.data.lights.new('Sun_Key', 'SUN')
sun.energy = 3.0
sun.color = (1.0, 0.85, 0.65)  # Warm amber
sun_obj = bpy.data.objects.new('Sun_Key', sun)
bpy.context.collection.objects.link(sun_obj)
sun_obj.location = (20, -30, 40)
direction = Vector((40, 40, 0)) - sun_obj.location
rot = direction.to_track_quat('-Z', 'Y')
sun_obj.rotation_euler = rot.to_euler()

# Fill light - cool blue (ominous undertone)
fill = bpy.data.lights.new('Fill_Cool', 'SUN')
fill.energy = 0.8
fill.color = (0.6, 0.65, 0.8)  # Cool blue
fill_obj = bpy.data.objects.new('Fill_Cool', fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = (-30, 20, 30)
direction = Vector((40, 40, 0)) - fill_obj.location
rot = direction.to_track_quat('-Z', 'Y')
fill_obj.rotation_euler = rot.to_euler()

# Warm point lights for tavern/blacksmith areas
for name, loc, color, energy in [
    ('Tavern_Glow', (5, 5, 4), (1.0, 0.7, 0.3), 100),
    ('Forge_Glow', (50, 35, 3), (1.0, 0.4, 0.1), 150),
    ('Chapel_Candle', (57, 52, 4), (1.0, 0.85, 0.5), 60),
    ('Gate_Torch', (40, 5, 4), (1.0, 0.6, 0.2), 80),
]:
    light = bpy.data.lights.new(name, 'POINT')
    light.energy = energy
    light.color = color
    light.shadow_soft_size = 2.0
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = loc

# World background - dark moody sky
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('VBWorld')
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs['Color'].default_value = (0.02, 0.025, 0.04, 1)
    bg.inputs['Strength'].default_value = 0.3

print('Dark fantasy lighting setup complete')
""")
print("  Lighting configured", flush=True)

# Switch to material preview for better screenshot
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
""")

# Overview screenshot
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (85, -65, 45)
direction = Vector((35, 35, 5)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase4_materials_lit.png"))
print(f"Material+Lit screenshot: {p}", flush=True)

# Street view with lighting
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (25, 18, 4)
direction = Vector((40, 38, 3)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase4_street_lit.png"))
print(f"Street lit: {p}", flush=True)

# Object count
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])
print(f"\nTotal objects: {len(obj_list)}", flush=True)

print("=== Phase 4 Complete ===", flush=True)
