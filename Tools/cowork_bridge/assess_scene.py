"""Assess current Blender scene - screenshot + full object inventory."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

print("=== Scene Assessment ===", flush=True)

# Get scene info
info = blender("get_scene_info")
print(f"Render engine: {info.get('render_engine', '?')}", flush=True)
print(f"FPS: {info.get('fps', '?')}", flush=True)

# List all objects
objects = blender("list_objects")
if isinstance(objects, list):
    print(f"\nTotal objects: {len(objects)}", flush=True)
    # Categorize
    types = {}
    for obj in objects:
        t = obj.get("type", "UNKNOWN")
        types[t] = types.get(t, 0) + 1
        name = obj.get("name", "?")
        loc = obj.get("location", [0,0,0])
        print(f"  [{t}] {name} @ ({loc[0]:.1f}, {loc[1]:.1f}, {loc[2]:.1f})", flush=True)
    print(f"\nType breakdown: {types}", flush=True)
elif isinstance(objects, dict):
    obj_list = objects.get("objects", [])
    print(f"\nTotal objects: {len(obj_list)}", flush=True)
    types = {}
    for obj in obj_list:
        t = obj.get("type", "UNKNOWN")
        types[t] = types.get(t, 0) + 1
        name = obj.get("name", "?")
        print(f"  [{t}] {name}", flush=True)
    print(f"\nType breakdown: {types}", flush=True)

# Take screenshots from multiple angles
print("\n--- Taking screenshots ---", flush=True)

# Overview shot
try:
    r = blender("get_viewport_screenshot")
    path = r.get("filepath", r) if isinstance(r, dict) else r
    print(f"Screenshot saved: {path}", flush=True)
except Exception as e:
    print(f"Screenshot failed: {e}", flush=True)

# Navigate to top-down view for layout assessment
try:
    blender("navigate_camera", camera_position=[0, 0, 80], camera_target=[0, 0, 0])
    r = blender("get_viewport_screenshot")
    path = r.get("filepath", r) if isinstance(r, dict) else r
    print(f"Top-down screenshot: {path}", flush=True)
except Exception as e:
    print(f"Top-down failed: {e}", flush=True)

# Navigate to a 3/4 perspective
try:
    blender("navigate_camera", camera_position=[50, -50, 40], camera_target=[0, 0, 0])
    r = blender("get_viewport_screenshot")
    path = r.get("filepath", r) if isinstance(r, dict) else r
    print(f"Perspective screenshot: {path}", flush=True)
except Exception as e:
    print(f"Perspective failed: {e}", flush=True)

print("\n=== Assessment Complete ===", flush=True)
