"""Demo: Create a cube, apply dark fantasy material, take screenshot."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import *

print("=== VeilBreakers Cowork Bridge Demo ===", flush=True)

# 1. Clear scene
result = blender("clear_scene")
print(f"Scene cleared: {result}", flush=True)

# 2. Create a cube
result = blender("create_object", mesh_type="cube", position=[0,0,0.5], scale=[1,1,1])
print(f"Cube created: {result}", flush=True)

# 3. Create dark fantasy material
result = blender("material_create", name="DarkStone",
                 base_color=[0.15, 0.12, 0.18, 1.0],
                 metallic=0.1, roughness=0.85)
print(f"Material created: {result}", flush=True)

# 4. Assign material
result = blender("material_assign", name="DarkStone", object_name="Cube")
print(f"Material assigned: {result}", flush=True)

# 5. Take screenshot for verification
result = blender("get_viewport_screenshot")
print(f"Screenshot: {result}", flush=True)

# 6. Get scene info to confirm
info = blender("get_scene_info")
print(f"Scene objects: {json.dumps(info, indent=2, default=str)[:500]}", flush=True)

print("=== Demo Complete ===", flush=True)
