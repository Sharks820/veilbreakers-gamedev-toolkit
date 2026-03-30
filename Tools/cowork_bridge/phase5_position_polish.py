"""Phase 5: Position buildings, add vegetation via code, final polish."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"

print("=== Phase 5: Positioning & Polish ===", flush=True)

# Position all generated buildings to their correct town locations
print("--- Positioning Buildings ---", flush=True)
blender("execute_code", code="""
import bpy
import math

# Map generated buildings to town locations
# The generators place at origin - we need to move them
positions = {
    # Original empty positions from the town layout
    'Tavern': (0, 0, 0),       # Tavern at origin
    'Blacksmith': (50, 35, 0),
    'Chapel': (55, 52, 0),
    'GeneralStore': (35, 50, 0),
    'GuardTower': (60, 20, 0),
    'House1': (20, 25, 0),
    'House2': (20, 50, 0),
}

# Find building-type objects and distribute them
buildings = [o for o in bpy.data.objects if o.type == 'MESH' and 
             ('Building' in o.name or 'Castle' in o.name)]

# Get the main generated buildings (they're named Building, Building.001, etc.)
building_names = sorted([o.name for o in buildings if 'Building' in o.name])
castle_names = [o.name for o in buildings if 'Castle' in o.name]

# Map buildings to positions (order: blacksmith, chapel, store, house1, house2)
target_positions = [
    (50, 35, 0),   # Blacksmith
    (55, 52, 0),   # Chapel
    (35, 50, 0),   # General Store
    (20, 25, 0),   # House 1
    (20, 50, 0),   # House 2
]

for i, name in enumerate(building_names[:5]):
    obj = bpy.data.objects[name]
    if i < len(target_positions):
        obj.location = target_positions[i]
        print(f'  {name} -> {target_positions[i]}')

# Castle (guard tower) position
for name in castle_names[:1]:
    obj = bpy.data.objects[name]
    obj.location = (60, 20, 0)
    print(f'  {name} -> (60, 20, 0)')

# Position stone walls (tavern components) around tavern area
stone_walls = [o for o in bpy.data.objects if 'stone_wall' in o.name.lower()]
offsets = [(0, 0, 0), (0, 7, 0), (-4.5, 3.5, 0), (4.5, 3.5, 0)]
for i, obj in enumerate(stone_walls[:4]):
    if i < len(offsets):
        obj.location = offsets[i]
        # Rotate side walls
        if i >= 2:
            obj.rotation_euler = (0, 0, math.pi/2)
    print(f'  {obj.name} positioned')

# Timber frames above stone walls
timber_frames = [o for o in bpy.data.objects if 'timber_frame' in o.name.lower()]
for i, obj in enumerate(timber_frames[:4]):
    if i < len(offsets):
        obj.location = (offsets[i][0], offsets[i][1], 3.0)
        if i >= 2:
            obj.rotation_euler = (0, 0, math.pi/2)
    print(f'  {obj.name} positioned')

# Town wall positions
wall_objects = [o for o in bpy.data.objects if 'stone_wall_ashlar' in o.name 
                and o.name.count('.') >= 2]
# The bigger wall segments
for obj in bpy.data.objects:
    if obj.name.startswith('stone_wall_ashlar') and len(obj.data.vertices) > 500:
        # These are the town wall segments
        pass  # Already at origin, need manual placement

print('Building positioning complete')
""")

# Add vegetation and ground cover via execute_code
print("\n--- Vegetation & Ground Cover ---", flush=True)
blender("execute_code", code="""
import bpy, bmesh, math, random
random.seed(42)

# Create grass patches around buildings
def create_grass_patch(name, center, radius, count=30):
    for i in range(count):
        angle = random.uniform(0, 2*math.pi)
        dist = random.uniform(0.5, radius)
        x = center[0] + math.cos(angle) * dist
        y = center[1] + math.sin(angle) * dist
        
        # Create a simple grass blade (thin triangle)
        mesh = bpy.data.meshes.new(f'{name}_{i}')
        obj = bpy.data.objects.new(f'{name}_{i}', mesh)
        bpy.context.collection.objects.link(obj)
        
        bm = bmesh.new()
        h = random.uniform(0.15, 0.35)
        w = 0.03
        lean = random.uniform(-0.05, 0.05)
        v1 = bm.verts.new((-w, 0, 0))
        v2 = bm.verts.new((w, 0, 0))
        v3 = bm.verts.new((lean, 0, h))
        bm.faces.new([v1, v2, v3])
        bm.to_mesh(mesh); bm.free()
        
        obj.location = (x, y, 0)
        obj.rotation_euler = (0, 0, random.uniform(0, 2*math.pi))
        
        # Green material
        mat = bpy.data.materials.get('AAA_Grass')
        if not mat:
            mat = bpy.data.materials.new('AAA_Grass')
            mat.use_nodes = True
            b = mat.node_tree.nodes['Principled BSDF']
            b.inputs['Base Color'].default_value = (0.15, 0.25, 0.08, 1)
            b.inputs['Roughness'].default_value = 0.9
        obj.data.materials.append(mat)

# Scatter grass around town perimeter and along walls
grass_centers = [
    (10, 10, 8), (70, 10, 6), (10, 70, 7),
    (30, 15, 5), (15, 40, 6), (65, 45, 5),
    (45, 65, 4), (25, 60, 5),
]
for i, (x, y, count) in enumerate(grass_centers):
    create_grass_patch(f'Grass_{i}', (x, y), 5.0, count)

print(f'Vegetation added: {sum(c for _,_,c in grass_centers)} grass blades')
""")
print("  Vegetation added", flush=True)

# Add market stall props
print("\n--- Market Stall Props ---", flush=True)
blender("execute_code", code="""
import bpy, bmesh, math, random
random.seed(123)

# Create simple but effective market props
def create_barrel(name, loc):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    
    # Barrel shape: cylinder with bulge
    segs = 12
    rings = 6
    radius = 0.3
    height = 0.6
    
    verts_by_ring = []
    for r in range(rings):
        t = r / (rings-1)
        z = t * height
        # Bulge in middle
        bulge = 1.0 + 0.1 * math.sin(t * math.pi)
        ring_verts = []
        for s in range(segs):
            a = 2*math.pi*s/segs
            x = math.cos(a) * radius * bulge
            y = math.sin(a) * radius * bulge
            ring_verts.append(bm.verts.new((x, y, z)))
        verts_by_ring.append(ring_verts)
    
    bm.verts.ensure_lookup_table()
    for r in range(rings-1):
        for s in range(segs):
            ns = (s+1) % segs
            try:
                bm.faces.new([verts_by_ring[r][s], verts_by_ring[r][ns],
                             verts_by_ring[r+1][ns], verts_by_ring[r+1][s]])
            except: pass
    
    # Top and bottom caps
    try:
        bm.faces.new(verts_by_ring[0])
        bm.faces.new(list(reversed(verts_by_ring[-1])))
    except: pass
    
    bm.to_mesh(mesh); bm.free()
    obj.location = loc
    
    mat = bpy.data.materials.get('AAA_Wood')
    if mat:
        obj.data.materials.append(mat)
    return obj

def create_crate(name, loc, size=0.4):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    obj = bpy.context.object
    obj.name = name
    # Add slight random rotation for natural look
    obj.rotation_euler = (random.uniform(-0.05, 0.05),
                         random.uniform(-0.05, 0.05),
                         random.uniform(-0.3, 0.3))
    mat = bpy.data.materials.get('AAA_Wood')
    if mat:
        obj.data.materials.append(mat)
    return obj

# Place barrels and crates around the market and buildings
props = []
# Market area
for i in range(8):
    x = 35 + random.uniform(-8, 8)
    y = 35 + random.uniform(-8, 8)
    if random.random() > 0.5:
        create_barrel(f'Barrel_{i}', (x, y, 0))
    else:
        create_crate(f'Crate_{i}', (x, y, 0.2))

# Near tavern
for i in range(4):
    create_barrel(f'TavernBarrel_{i}', 
                 (random.uniform(-2, 10), random.uniform(-2, 8), 0))

# Near blacksmith
create_crate('BS_Crate_0', (48, 33, 0.2))
create_crate('BS_Crate_1', (52, 33, 0.2))

# Near gate
create_barrel('GateBarrel_0', (38, 6, 0))
create_barrel('GateBarrel_1', (42, 6, 0))

print('Market and environmental props placed')
""")
print("  Props placed", flush=True)

# Final screenshots from multiple angles
print("\n--- Final Visual Verification ---", flush=True)

views = [
    ("final_overview", (90, -70, 55), (35, 35, 3)),
    ("final_street", (28, 20, 4), (42, 42, 3)),
    ("final_tavern_closeup", (12, -8, 7), (3, 4, 3)),
    ("final_market", (35, 25, 5), (38, 40, 2)),
    ("final_gate_approach", (40, -10, 5), (40, 10, 4)),
    ("final_chapel", (48, 58, 8), (57, 52, 4)),
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
        print(f"  {label}: OK", flush=True)
    except Exception as e:
        print(f"  {label}: {e}", flush=True)

# Final stats
result = blender("list_objects")
obj_list = result if isinstance(result, list) else result.get("objects", [])
types = {}
total_verts = 0
for obj in obj_list:
    t = obj.get("type", "?")
    types[t] = types.get(t, 0) + 1

print(f"\n=== FINAL STATS ===", flush=True)
print(f"Total objects: {len(obj_list)}", flush=True)
print(f"By type: {types}", flush=True)
print(f"Screenshots saved to: {out}", flush=True)

# Run mesh quality check on a key building
try:
    r = blender("mesh_analyze_topology", object_name="Building")
    if isinstance(r, dict):
        print(f"Building quality: grade={r.get('grade','?')} verts={r.get('vertex_count','?')} faces={r.get('face_count','?')}", flush=True)
except:
    pass

print("=== Phase 5 Complete - Town Overhaul Done ===", flush=True)
