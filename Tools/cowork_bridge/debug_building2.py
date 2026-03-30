"""Debug: Use viewport navigation + contact sheet to properly see the building."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

# First, list all objects to see what exists
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])
print(f"Objects: {len(obj_list)}", flush=True)
for obj in obj_list:
    name = obj.get("name", "?")
    t = obj.get("type", "?")
    loc = obj.get("location", [0,0,0])
    print(f"  [{t}] {name} @ ({loc[0]:.1f},{loc[1]:.1f},{loc[2]:.1f})", flush=True)

# Use viewport navigation (not scene camera)
print("\n--- Viewport Navigation ---", flush=True)
blender("execute_code", code="""
import bpy
# Move the 3D viewport view directly
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                override = bpy.context.copy()
                override['area'] = area
                override['region'] = region
                space = area.spaces[0]
                r3d = space.region_3d
                # Set viewport to look at the building
                from mathutils import Vector
                r3d.view_location = Vector((5, 4, 3))
                r3d.view_distance = 20
                r3d.view_rotation = (0.8, 0.3, -0.2, 0.5)  # Quaternion
                # Set solid shading with random colors
                space.shading.type = 'SOLID'
                space.shading.color_type = 'RANDOM'
                break
        break
print('Viewport moved')
""")

r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "debug2_viewport.png"))
print(f"Viewport: saved", flush=True)

# Try contact sheet on the Building object
print("\n--- Contact Sheet ---", flush=True)
try:
    r = blender("render_contact_sheet", object_name="Building")
    p = r.get("filepath", r) if isinstance(r, dict) else r
    shutil.copy2(p, os.path.join(out, "debug2_contact.png"))
    print(f"Contact sheet: saved", flush=True)
except Exception as e:
    print(f"Contact sheet failed: {e}", flush=True)
    # Try with child mesh names
    for obj in obj_list:
        name = obj.get("name", "")
        if "Wall" in name and obj.get("type") == "MESH":
            try:
                r = blender("render_contact_sheet", object_name=name)
                p = r.get("filepath", r) if isinstance(r, dict) else r
                shutil.copy2(p, os.path.join(out, f"debug2_contact_{name}.png"))
                print(f"Contact {name}: saved", flush=True)
                break
            except Exception as e2:
                print(f"Contact {name}: {e2}", flush=True)

print("Done", flush=True)
