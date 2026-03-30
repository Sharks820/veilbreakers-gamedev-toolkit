"""Get more assessment views + mesh stats."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out_dir = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out_dir, exist_ok=True)

# Copy existing screenshots
for src, dst in [
    ("C:/Users/Conner/AppData/Local/Temp/vb_screenshot_a18b606b.png", "01_overview_solid.png"),
    ("C:/Users/Conner/AppData/Local/Temp/vb_screenshot_79aaf810.png", "02_overview_material.png"),
]:
    try:
        shutil.copy2(src, os.path.join(out_dir, dst))
    except: pass

# Street level
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (30, 25, 3)
direction = Vector((40, 40, 4)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out_dir, "03_street_level.png"))
print(f"Street: {p}", flush=True)

# Tavern closeup
blender("execute_code", code="""
import bpy
from mathutils import Vector
cam = bpy.context.scene.camera
cam.location = (12, -5, 6)
direction = Vector((4, 4, 3)) - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
""")
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out_dir, "04_tavern.png"))
print(f"Tavern: {p}", flush=True)

# Mesh stats
print("\n--- Mesh Analysis ---", flush=True)
for name in ["Foundation", "Terrain", "Road_NS", "BS_Front",
             "GS_GF_Front", "CH_Front", "H1_Front", "MarketSquare",
             "TownWall_E", "Well_Base"]:
    try:
        r = blender("mesh_analyze_topology", object_name=name)
        if isinstance(r, dict):
            g = r.get("grade", "?")
            v = r.get("vertex_count", "?")
            f = r.get("face_count", r.get("poly_count", "?"))
            issues = r.get("issues", [])
            issue_str = ", ".join(issues[:3]) if issues else "none"
            print(f"  {name}: {g} ({v}v/{f}f) issues: {issue_str}", flush=True)
        else:
            print(f"  {name}: {r}", flush=True)
    except Exception as e:
        print(f"  {name}: {e}", flush=True)

print(f"\nScreenshots saved to: {out_dir}", flush=True)
print("Done", flush=True)
