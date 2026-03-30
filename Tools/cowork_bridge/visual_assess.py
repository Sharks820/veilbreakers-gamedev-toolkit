"""Visual assessment with camera setup."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

# Add camera since scene doesn't have one
blender("execute_code", code="""
import bpy
# Add camera if none exists
if not any(o.type == 'CAMERA' for o in bpy.data.objects):
    bpy.ops.object.camera_add(location=(80, -60, 50))
    cam = bpy.context.object
    cam.name = 'AssessCamera'
    bpy.context.scene.camera = cam
else:
    cam = [o for o in bpy.data.objects if o.type == 'CAMERA'][0]
    cam.location = (80, -60, 50)
    bpy.context.scene.camera = cam

# Point at town center
from mathutils import Vector
direction = Vector((35, 35, 5)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
print("Camera added", flush=True)

# Overview screenshot in solid mode
blender("set_shading", shading_type="SOLID")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
print(f"Overview solid: {p}", flush=True)

# Material preview
blender("set_shading", shading_type="MATERIAL")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
print(f"Overview material: {p}", flush=True)

# Wireframe for geometry assessment
blender("set_shading", shading_type="WIREFRAME")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
print(f"Wireframe: {p}", flush=True)

blender("set_shading", shading_type="SOLID")

# Street-level view
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (25, 20, 3)
direction = Vector((40, 40, 3)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
print(f"Street level: {p}", flush=True)

# Tavern interior peek
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (4, 2, 2)
direction = Vector((4, 6, 2)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
print(f"Tavern interior: {p}", flush=True)

# Check materials
try:
    mats = blender("material_list")
    mat_list = mats if isinstance(mats, list) else mats.get("materials", [])
    print(f"\nMaterials ({len(mat_list)}):", flush=True)
    for m in mat_list[:25]:
        name = m.get("name", m) if isinstance(m, dict) else m
        print(f"  {name}", flush=True)
    if len(mat_list) > 25:
        print(f"  ... +{len(mat_list)-25} more", flush=True)
except Exception as e:
    print(f"Materials: {e}", flush=True)

# Mesh analysis on key objects
for obj_name in ["Foundation", "Terrain", "Road_NS", "BS_Front", "GS_GF_Front"]:
    try:
        result = blender("mesh_analyze_topology", object_name=obj_name)
        if isinstance(result, dict):
            g = result.get("grade", "?")
            v = result.get("vertex_count", "?")
            f = result.get("face_count", result.get("poly_count", "?"))
            print(f"  {obj_name}: grade={g} verts={v} faces={f}", flush=True)
    except Exception as e:
        print(f"  {obj_name}: {e}", flush=True)

print("\nAssessment complete", flush=True)
