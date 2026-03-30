"""Analyze town mesh and take screenshots."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

# Get mesh stats
blender("execute_code", code="""
import bpy
from mathutils import Vector
town = bpy.data.objects.get('Town')
if town:
    mesh = town.data
    print(f'Verts: {len(mesh.vertices)}')
    print(f'Faces: {len(mesh.polygons)}')
    bb = [town.matrix_world @ Vector(c) for c in town.bound_box]
    mins = [min(v[i] for v in bb) for i in range(3)]
    maxs = [max(v[i] for v in bb) for i in range(3)]
    print(f'Size: {maxs[0]-mins[0]:.1f} x {maxs[1]-mins[1]:.1f} x {maxs[2]-mins[2]:.1f}m')
    print(f'Materials: {len(mesh.materials)}')
    for m in mesh.materials:
        print(f'  - {m.name if m else "None"}')
""")

# Screenshots from multiple angles
views = [
    ("town2_overview", (60, -40, 45), (20, 20, 0)),
    ("town2_top", (20, 20, 60), (20, 20, 0)),
    ("town2_street", (5, 5, 5), (20, 20, 2)),
    ("town2_closeup", (10, 10, 3), (15, 15, 2)),
]
for label, pos, tgt in views:
    blender("execute_code", code=f"""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = {list(pos)}
direction = Vector({list(tgt)}) - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
""")
    r = blender("get_viewport_screenshot")
    p = r.get("filepath", r) if isinstance(r, dict) else r
    shutil.copy2(p, os.path.join(out, f"{label}.png"))
    print(f"{label}: saved", flush=True)

print("Done", flush=True)
