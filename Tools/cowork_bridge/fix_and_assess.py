"""Fix viewport + get assessment screenshots + mesh stats."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out, exist_ok=True)

# Fix viewport shading via execute_code
blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'SOLID'
                break
""")
print("Viewport reset to SOLID", flush=True)

# Overview
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "01_overview.png"))
print(f"Overview: {p}", flush=True)

# Move camera for different views
views = [
    ("02_street", (30, 25, 3), (40, 40, 4)),
    ("03_tavern", (12, -5, 6), (4, 4, 3)),
    ("04_blacksmith", (55, 28, 5), (50, 35, 3)),
    ("05_chapel", (48, 55, 8), (58, 52, 5)),
]
for label, pos, tgt in views:
    try:
        blender("execute_code", code=f"""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = {list(pos)}
direction = Vector({list(tgt)}) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
        r = blender("get_viewport_screenshot")
        p = r.get("filepath", r) if isinstance(r, dict) else r
        shutil.copy2(p, os.path.join(out, f"{label}.png"))
        print(f"{label}: OK", flush=True)
    except Exception as e:
        print(f"{label}: {e}", flush=True)

# Material view
try:
    blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
                break
""")
    # Reset to overview
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
    shutil.copy2(p, os.path.join(out, "06_material_view.png"))
    print("Material view: OK", flush=True)
except Exception as e:
    print(f"Material view: {e}", flush=True)

# Back to solid
blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'SOLID'
                break
""")

# Mesh analysis
print("\n--- Mesh Quality ---", flush=True)
key_objects = [
    "Foundation", "Terrain", "Road_NS", "BS_Front", "BS_Forge",
    "GS_GF_Front", "CH_Front", "CH_Spire", "H1_Front",
    "MarketSquare", "TownWall_E", "Well_Base", "Gate_L",
    "Stall_Counter_0", "Stall_Awning_0"
]
for name in key_objects:
    try:
        r = blender("mesh_analyze_topology", object_name=name)
        if isinstance(r, dict):
            g = r.get("grade", "?")
            v = r.get("vertex_count", "?")
            f = r.get("face_count", r.get("poly_count", "?"))
            ngons = r.get("ngon_count", 0)
            tris = r.get("triangle_count", 0)
            quads = r.get("quad_count", 0)
            print(f"  {name}: {g} | {v}v {f}f (q:{quads} t:{tris} n:{ngons})", flush=True)
    except Exception as e:
        print(f"  {name}: {e}", flush=True)

# Material inventory
print("\n--- Materials ---", flush=True)
try:
    mats = blender("material_list")
    mat_list = mats if isinstance(mats, list) else mats.get("materials", [])
    print(f"Total materials: {len(mat_list)}", flush=True)
    for m in mat_list:
        name = m.get("name", m) if isinstance(m, dict) else m
        users = m.get("users", "?") if isinstance(m, dict) else "?"
        print(f"  {name} (users: {users})", flush=True)
except Exception as e:
    print(f"  Error: {e}", flush=True)

print(f"\nAll screenshots saved to: {out}", flush=True)
print("Assessment complete!", flush=True)
