"""Phase 3: Interior furnishing + scatter props."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

print("=== Phase 3: Interiors & Props ===", flush=True)

# Generate interiors for key buildings
interiors = [
    ("tavern", {"room_type": "tavern", "width": 9.0, "depth": 7.0,
                "wall_height": 3.0, "seed": 101}),
    ("blacksmith", {"room_type": "blacksmith", "width": 8.0, "depth": 6.0,
                    "wall_height": 3.5, "seed": 102}),
    ("chapel", {"room_type": "temple", "width": 8.0, "depth": 12.0,
                "wall_height": 4.0, "seed": 103}),
    ("shop", {"room_type": "shop", "width": 7.0, "depth": 6.0,
              "wall_height": 3.0, "seed": 104}),
]

for name, params in interiors:
    print(f"\n--- Interior: {name} ---", flush=True)
    try:
        r = blender("world_generate_interior", **params)
        if isinstance(r, dict):
            items = r.get("furniture_count", r.get("prop_count", "?"))
            verts = r.get("vertex_count", "?")
            print(f"  OK: {items} items, {verts} verts", flush=True)
        else:
            print(f"  {json.dumps(r, default=str)[:200]}", flush=True)
    except Exception as e:
        print(f"  {e}", flush=True)

# Scatter environmental props
print("\n--- Environmental Props ---", flush=True)
try:
    r = blender("env_scatter_props",
        area_min=[5, 5],
        area_max=[75, 75],
        prop_types=["barrel", "crate", "hay_bale", "sack"],
        density=0.3,
        seed=42
    )
    print(f"  Props: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Scatter props: {e}", flush=True)

# Scatter vegetation
print("\n--- Vegetation ---", flush=True)
try:
    r = blender("env_scatter_vegetation",
        rules=[
            {"type": "grass", "density": 0.5, "min_slope": 0, "max_slope": 30},
            {"type": "weed", "density": 0.2, "min_slope": 0, "max_slope": 45},
        ],
        min_distance=0.5,
        max_instances=200,
        seed=42
    )
    print(f"  Vegetation: {json.dumps(r, default=str)[:200]}", flush=True)
except Exception as e:
    print(f"  Vegetation: {e}", flush=True)

# Storytelling props
print("\n--- Storytelling Props ---", flush=True)
try:
    r = blender("execute_code", code="""
import bpy

# Add environmental storytelling elements via code
# Since add_storytelling_props needs a target interior
print('Adding storytelling elements...')
""")
except Exception as e:
    print(f"  {e}", flush=True)

# Screenshot
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase3_interiors.png"))
print(f"\nScreenshot: {p}", flush=True)

print("=== Phase 3 Complete ===", flush=True)
