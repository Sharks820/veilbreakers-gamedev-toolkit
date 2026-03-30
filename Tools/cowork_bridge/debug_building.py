"""Debug: zoom into building to see actual geometry + fix materials."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

# Switch to solid shading with random face colors to see geometry
blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'SOLID'
                space.shading.color_type = 'RANDOM'
                break
""")

# Zoom in VERY close to see stone detail on front wall
views = [
    ("debug_wall_close", (3, -1.5, 2), (3, 0, 2)),     # Front wall closeup
    ("debug_window_close", (3, -1.5, 4), (3, -0.1, 4)), # Window area
    ("debug_interior", (5, 4, 1.5), (3, 4, 1.5)),       # Looking inside
    ("debug_roof_close", (5, -2, 8), (5, 4, 7)),        # Roof detail
    ("debug_overall_random", (15, -10, 10), (5, 4, 3)),  # Overview with random colors
]
for label, pos, tgt in views:
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
    print(f"{label}: saved", flush=True)

# List ALL objects with vertex counts
blender("execute_code", code="""
import bpy
print('=== ALL OBJECTS ===')
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    if obj.type == 'MESH':
        v = len(obj.data.vertices)
        f = len(obj.data.polygons)
        vis = 'VIS' if not obj.hide_viewport else 'HID'
        mats = [m.name for m in obj.data.materials if m][:3]
        par = obj.parent.name if obj.parent else 'none'
        print(f'  [{vis}] {obj.name}: {v}v {f}f parent={par} mats={mats}')
    elif obj.type == 'EMPTY':
        print(f'  [EMP] {obj.name} children={len(obj.children)}')
""")

print("Done", flush=True)
