"""Fix materials to dark fantasy colors + render proper views."""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

# Apply dark fantasy PBR materials to all building components
blender("execute_code", code="""
import bpy

# Define dark fantasy material palette
palette = {
    'stone_wall': (0.25, 0.22, 0.18, 1.0, 0.88, 0.0),     # dark warm stone
    'smooth_stone': (0.3, 0.28, 0.24, 1.0, 0.82, 0.0),     # lighter stone
    'rough_stone': (0.2, 0.18, 0.15, 1.0, 0.92, 0.0),      # rough dark stone
    'timber': (0.2, 0.12, 0.06, 1.0, 0.7, 0.0),            # dark wood
    'slate_roof': (0.18, 0.18, 0.22, 1.0, 0.75, 0.0),      # dark slate
    'thatch_roof': (0.35, 0.28, 0.15, 1.0, 0.95, 0.0),     # golden thatch
    'iron': (0.15, 0.15, 0.17, 1.0, 0.5, 0.8),             # dark iron metallic
    'glass': (0.15, 0.2, 0.25, 0.3, 0.1, 0.0),             # dark tinted glass
    'plaster': (0.5, 0.45, 0.38, 1.0, 0.9, 0.0),           # warm plaster
}
# format: (R, G, B, Alpha, Roughness, Metallic)

def create_vb_material(name, color, alpha, rough, metal):
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (*color, 1.0)
        bsdf.inputs['Roughness'].default_value = rough
        bsdf.inputs['Metallic'].default_value = metal
        if alpha < 1.0:
            try:
                mat.blend_method = 'BLEND'
            except:
                pass
            bsdf.inputs['Alpha'].default_value = alpha
    return mat

# Create all materials
mats = {}
for key, (r, g, b, a, rough, metal) in palette.items():
    mats[key] = create_vb_material(f'VB_{key}', (r, g, b), a, rough, metal)

# Apply to building parts based on name
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    name = obj.name.lower()
    
    mat = None
    if 'wall' in name:
        mat = mats['stone_wall']
    elif 'window' in name:
        mat = mats['glass']
    elif 'door' in name or 'arch' in name:
        mat = mats['rough_stone']
    elif 'roof' in name:
        mat = mats['slate_roof']
    elif 'beam' in name or 'timber' in name:
        mat = mats['timber']
    elif 'stair' in name or 'floor' in name:
        mat = mats['timber']
    elif 'interior' in name:
        mat = mats['plaster']
    
    if mat:
        obj.data.materials.clear()
        obj.data.materials.append(mat)

print('Materials applied')
""")
print("Materials fixed", flush=True)

# Set up material preview with scene lighting
blender("execute_code", code="""
import bpy
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = True
                break
""")

# Take proper screenshots using viewport region_3d manipulation
views = [
    ("final2_front", (5, 4, 3.5), 18, (0.78, 0.33, -0.15, 0.51)),
    ("final2_corner", (5, 4, 4), 22, (0.82, 0.22, -0.22, 0.48)),
    ("final2_close_wall", (2, 0.5, 2), 6, (0.78, 0.33, -0.15, 0.51)),
    ("final2_interior", (5, 4, 1.5), 8, (0.5, 0.5, -0.5, 0.5)),
    ("final2_top", (5, 4, 0), 30, (1, 0, 0, 0)),
]

for label, loc, dist, rot in views:
    blender("execute_code", code=f"""
import bpy
from mathutils import Quaternion, Vector
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        r3d = area.spaces[0].region_3d
        r3d.view_location = Vector({list(loc)})
        r3d.view_distance = {dist}
        r3d.view_rotation = Quaternion({list(rot)})
        r3d.view_perspective = 'PERSP'
        break
""")
    r = blender("get_viewport_screenshot")
    p = r.get("filepath", r) if isinstance(r, dict) else r
    shutil.copy2(p, os.path.join(out, f"{label}.png"))
    print(f"{label}: saved", flush=True)

print("Done", flush=True)
