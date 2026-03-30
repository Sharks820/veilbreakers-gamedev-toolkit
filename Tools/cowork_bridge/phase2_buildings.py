"""Phase 2: Rebuild all buildings with proper architecture generators."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out, exist_ok=True)

print("=== Phase 2: Architecture Overhaul ===", flush=True)

# First, delete ALL the old cube-based building parts
print("Removing old cube buildings...", flush=True)
old_prefixes = [
    "Foundation", "GF_", "UF_", "Beam_", "DivWall", "Door", 
    "Fireplace", "Chimney", "Gable", "Roof", "Shelf_", "Table_",
    "Bed", "Desk", "Bar", "Glass", "WinFrame", "Stall_",
    "BS_", "CH_", "GS_", "GT_", "H1_", "H2_",
    "Gate_", "TownWall_", "Merl_", "Well_"
]
# Keep track of empties (they have position info)
empties = {}

result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])

for obj in obj_list:
    name = obj.get("name", "")
    obj_type = obj.get("type", "")
    loc = obj.get("location", [0,0,0])
    
    if obj_type == "EMPTY":
        empties[name] = loc
        continue
    
    for prefix in old_prefixes:
        if name.startswith(prefix) or name == prefix.rstrip("_"):
            try:
                blender("delete_object", name=name)
            except:
                pass
            break

print(f"  Cleared old meshes. Empties preserved: {list(empties.keys())}", flush=True)

# Build locations from empties
locations = {
    "Tavern": empties.get("Tavern_Building", [0, 0, 0]),
    "Blacksmith": empties.get("Blacksmith", [50, 35, 0]),
    "Chapel": empties.get("Chapel", [55, 52, 0]),
    "GeneralStore": empties.get("GeneralStore", [35, 50, 0]),
    "GuardTower": empties.get("GuardTower", [60, 20, 0]),
    "House1": empties.get("House1", [20, 25, 0]),
    "House2": empties.get("House2", [20, 50, 0]),
}

# === TAVERN ===
print("\n--- Building: Tavern ---", flush=True)
tavern_pos = locations["Tavern"]

# Stone foundation walls
print("  Stone walls...", flush=True)
for label, params in [
    ("front", {"width": 9.0, "height": 3.0, "thickness": 0.4, "stone_rows": 8, "stone_cols": 12}),
    ("back", {"width": 9.0, "height": 3.0, "thickness": 0.4, "stone_rows": 8, "stone_cols": 12}),
    ("left", {"width": 7.0, "height": 3.0, "thickness": 0.4, "stone_rows": 8, "stone_cols": 9}),
    ("right", {"width": 7.0, "height": 3.0, "thickness": 0.4, "stone_rows": 8, "stone_cols": 9}),
]:
    try:
        r = blender("building_stone_wall", **params)
        print(f"    {label}: {r.get('object_name', r) if isinstance(r, dict) else 'ok'}", flush=True)
    except Exception as e:
        print(f"    {label}: {e}", flush=True)

# Timber frame upper floor
print("  Timber framing...", flush=True)
for label in ["front_upper", "back_upper", "left_upper", "right_upper"]:
    try:
        r = blender("building_timber_frame",
            width=9.0 if "front" in label or "back" in label else 7.0,
            height=3.0,
            horizontal_beams=2,
            vertical_beams=4
        )
        print(f"    {label}: ok", flush=True)
    except Exception as e:
        print(f"    {label}: {e}", flush=True)

# Gothic windows
print("  Windows...", flush=True)
for i in range(4):
    try:
        r = blender("building_gothic_window",
            width=0.8, height=1.5,
            frame_depth=0.15,
            has_glass=True
        )
        print(f"    window_{i}: ok", flush=True)
    except Exception as e:
        print(f"    window_{i}: {e}", flush=True)

# Roof
print("  Roof...", flush=True)
try:
    r = blender("building_roof",
        width=10.0, depth=8.0,
        roof_type="gable",
        overhang=0.5,
        tile_rows=8
    )
    print(f"  roof: ok", flush=True)
except Exception as e:
    print(f"  roof: {e}", flush=True)

# Chimney
print("  Chimney...", flush=True)
try:
    r = blender("building_chimney",
        width=0.8, depth=0.8, height=5.0,
        cap_type="simple"
    )
    print(f"  chimney: ok", flush=True)
except Exception as e:
    print(f"  chimney: {e}", flush=True)

# Archway for door
print("  Door archway...", flush=True)
try:
    r = blender("building_archway",
        width=1.2, height=2.2,
        depth=0.5,
        arch_type="pointed"
    )
    print(f"  archway: ok", flush=True)
except Exception as e:
    print(f"  archway: {e}", flush=True)

# Screenshot after tavern
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase2_tavern.png"))
print(f"  Tavern screenshot saved", flush=True)

# === BLACKSMITH ===
print("\n--- Building: Blacksmith ---", flush=True)
try:
    r = blender("world_generate_building",
        building_type="blacksmith",
        width=8.0, depth=6.0,
        floors=1,
        style="medieval",
        seed=100
    )
    print(f"  Blacksmith: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Blacksmith: {e}", flush=True)

# === CHAPEL ===
print("\n--- Building: Chapel ---", flush=True)
try:
    r = blender("world_generate_building",
        building_type="chapel",
        width=8.0, depth=12.0,
        floors=1,
        style="gothic",
        seed=200
    )
    print(f"  Chapel: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Chapel: {e}", flush=True)

# === GENERAL STORE ===
print("\n--- Building: General Store ---", flush=True)
try:
    r = blender("world_generate_building",
        building_type="shop",
        width=7.0, depth=6.0,
        floors=2,
        style="medieval",
        seed=300
    )
    print(f"  Store: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Store: {e}", flush=True)

# === GUARD TOWER ===
print("\n--- Building: Guard Tower ---", flush=True)
try:
    r = blender("world_generate_castle",
        outer_size=6.0,
        keep_size=4.0,
        tower_count=1,
        wall_height=8.0,
        seed=400
    )
    print(f"  Tower: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Tower: {e}", flush=True)

# === HOUSES ===
print("\n--- Houses ---", flush=True)
for i, seed in enumerate([500, 600], 1):
    try:
        r = blender("world_generate_building",
            building_type="house",
            width=6.0, depth=5.0,
            floors=1 if i == 1 else 2,
            style="medieval",
            seed=seed
        )
        print(f"  House{i}: {json.dumps(r, default=str)[:200]}", flush=True)
    except Exception as e:
        print(f"  House{i}: {e}", flush=True)

# === TOWN WALLS ===
print("\n--- Town Walls ---", flush=True)
# Generate wall segments using building_battlements and building_stone_wall
for wall_name, length in [("Wall_South", 35.0), ("Wall_East", 70.0), ("Wall_South2", 30.0)]:
    try:
        r = blender("building_stone_wall",
            width=length, height=4.0, thickness=1.0,
            stone_rows=10, stone_cols=int(length*2)
        )
        print(f"  {wall_name}: ok", flush=True)
    except Exception as e:
        print(f"  {wall_name}: {e}", flush=True)

# Battlements on walls
try:
    r = blender("building_battlements",
        length=70.0, height=1.2,
        merlon_width=0.6, merlon_spacing=0.4
    )
    print(f"  Battlements: ok", flush=True)
except Exception as e:
    print(f"  Battlements: {e}", flush=True)

# === GATE ===
print("\n--- Gate ---", flush=True)
try:
    r = blender("building_archway",
        width=3.0, height=4.0,
        depth=1.5,
        arch_type="pointed"
    )
    print(f"  Gate: ok", flush=True)
except Exception as e:
    print(f"  Gate: {e}", flush=True)

# === WELL (rebuild with better geometry) ===
print("\n--- Well ---", flush=True)
blender("execute_code", code="""
import bpy, bmesh, math

# Create a proper stone well
mesh = bpy.data.meshes.new('AAA_Well')
obj = bpy.data.objects.new('AAA_Well', mesh)
bpy.context.collection.objects.link(obj)
bm = bmesh.new()

# Circular base with stone texture
segs = 16
radius = 0.6
height = 0.8
wall_thick = 0.15

# Outer cylinder
for i in range(segs):
    a = 2*math.pi*i/segs
    a2 = 2*math.pi*((i+1)%segs)/segs
    # Outer verts
    v1 = bm.verts.new((math.cos(a)*radius, math.sin(a)*radius, 0))
    v2 = bm.verts.new((math.cos(a2)*radius, math.sin(a2)*radius, 0))
    v3 = bm.verts.new((math.cos(a2)*radius, math.sin(a2)*radius, height))
    v4 = bm.verts.new((math.cos(a)*radius, math.sin(a)*radius, height))
    bm.faces.new([v1,v2,v3,v4])
    # Inner verts
    ir = radius - wall_thick
    v5 = bm.verts.new((math.cos(a)*ir, math.sin(a)*ir, 0))
    v6 = bm.verts.new((math.cos(a2)*ir, math.sin(a2)*ir, 0))
    v7 = bm.verts.new((math.cos(a2)*ir, math.sin(a2)*ir, height))
    v8 = bm.verts.new((math.cos(a)*ir, math.sin(a)*ir, height))
    bm.faces.new([v8,v7,v6,v5])
    # Top cap
    bm.faces.new([v4,v3,v7,v8])

# Support posts
for angle in [0, math.pi]:
    x = math.cos(angle) * (radius + 0.05)
    y = math.sin(angle) * (radius + 0.05)
    for dx in range(-1, 2, 2):
        post_w = 0.06
        for iz in range(4):
            z0, z1 = iz*0.4 + height, (iz+1)*0.4 + height
            v1 = bm.verts.new((x-post_w, y-post_w, z0))
            v2 = bm.verts.new((x+post_w, y-post_w, z0))
            v3 = bm.verts.new((x+post_w, y-post_w, z1))
            v4 = bm.verts.new((x-post_w, y-post_w, z1))
            bm.faces.new([v1,v2,v3,v4])

bm.to_mesh(mesh); bm.free()
obj.location = (40, 40, 0)

# Material
mat = bpy.data.materials.new('AAA_WellStone')
mat.use_nodes = True
b = mat.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (0.35, 0.33, 0.3, 1)
b.inputs['Roughness'].default_value = 0.9
obj.data.materials.append(mat)
print(f'Well: {len(mesh.vertices)}v {len(mesh.polygons)}f')
""")
print("  Well rebuilt", flush=True)

# Screenshot overview
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (80, -60, 50)
direction = Vector((35, 35, 5)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase2_all_buildings.png"))
print(f"\nFinal screenshot: {p}", flush=True)

# Object count check
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])
print(f"Total objects now: {len(obj_list)}", flush=True)

print("=== Phase 2 Complete ===", flush=True)
