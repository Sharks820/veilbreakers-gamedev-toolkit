"""Phase 1: AAA Terrain Generation - Fixed."""
import sys, os, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

out = "C:/Users/Conner/Desktop/vb_assess"
os.makedirs(out, exist_ok=True)

print("=== Phase 1: Terrain Overhaul ===", flush=True)

# Generate proper terrain with elevation
print("Generating AAA terrain...", flush=True)
result = blender("env_generate_terrain",
    terrain_type="hills",
    resolution=128,
    height_scale=12.0,
    erosion="both",
    erosion_iterations=5,
    seed=42
)
print(f"  Terrain: {json.dumps(result, default=str)[:300]}", flush=True)

# Position terrain under town center
print("Positioning terrain...", flush=True)
blender("execute_code", code="""
import bpy
# Find the generated terrain
terrain = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and ('terrain' in obj.name.lower() or 'Terrain' in obj.name):
        if obj.name != 'Terrain':  # Skip if old one somehow still exists
            terrain = obj
            break
        terrain = obj

if terrain:
    terrain.name = 'AAA_Terrain'
    terrain.scale = (1.5, 1.5, 1.0)
    terrain.location = (40, 40, -3)
    print(f'OK: {terrain.name} verts={len(terrain.data.vertices)}')
else:
    # List all meshes to debug
    meshes = [o.name for o in bpy.data.objects if o.type == 'MESH'][-10:]
    print(f'No terrain found. Recent meshes: {meshes}')
""")

# Generate cobblestone roads with proper geometry
print("Generating roads...", flush=True)
for road in ["Road_NS", "Road_EW", "MarketSquare"]:
    try:
        blender("delete_object", name=road)
    except: pass

blender("execute_code", code="""
import bpy, bmesh, math, random
random.seed(42)

def make_road(name, start, end, width=4.0):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    dx, dy = end[0]-start[0], end[1]-start[1]
    length = math.sqrt(dx*dx+dy*dy)
    angle = math.atan2(dy, dx)
    seg = 1.0
    n = max(int(length/seg), 1)
    hw = width/2
    rows = []
    for i in range(n+1):
        t = i/n
        cx, cy = start[0]+dx*t, start[1]+dy*t
        px, py = -math.sin(angle), math.cos(angle)
        h = random.uniform(-0.02, 0.02)
        row = []
        for j in range(6):
            f = (j/5-0.5)*2*hw
            x, y = cx+px*f, cy+py*f
            z = 0.08+h+0.03*math.sin(j*1.5)
            row.append(bm.verts.new((x,y,z)))
        rows.append(row)
    bm.verts.ensure_lookup_table()
    for i in range(len(rows)-1):
        for j in range(5):
            try: bm.faces.new([rows[i][j],rows[i][j+1],rows[i+1][j+1],rows[i+1][j]])
            except: pass
    bm.to_mesh(mesh); bm.free(); mesh.update()
    mat = bpy.data.materials.get('Cobble')
    if not mat:
        mat = bpy.data.materials.new('AAA_Cobblestone')
        mat.use_nodes = True
        b = mat.node_tree.nodes.get('Principled BSDF')
        if b:
            b.inputs['Base Color'].default_value = (0.25,0.22,0.2,1)
            b.inputs['Roughness'].default_value = 0.85
    obj.data.materials.append(mat)

make_road('Road_NS', (40,5), (40,75), 5)
make_road('Road_EW', (5,40), (75,40), 5)
make_road('MarketSquare', (30,30), (50,50), 20)
print('Roads done')
""")
print("  Roads generated", flush=True)

# Screenshot
r = blender("get_viewport_screenshot")
p = r.get("filepath", r) if isinstance(r, dict) else r
shutil.copy2(p, os.path.join(out, "phase1_terrain_roads.png"))
print(f"Screenshot: {p}", flush=True)

print("=== Phase 1 Complete ===", flush=True)
