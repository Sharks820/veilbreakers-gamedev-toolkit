import json
import sys
sys.path.insert(0, r'..\veilbreakers-gamedev-toolkit\Tools\cowork_bridge')
from vb_bridge import blender

code = '''import bpy, json
roots=["AcademyAnnex","HarborTavern","StarterCity"]
out={}
for root in roots:
    objs=[o for o in bpy.data.objects if o.name==root or o.name.startswith(root+"_")]
    out[root]={
        "count": len(objs),
        "facade": sum(1 for o in objs if "_Facade_" in o.name),
        "walls": sum(1 for o in objs if "_Wall_" in o.name or "_Wall" in o.name),
        "windows": sum(1 for o in objs if "_Window_" in o.name),
        "doors": sum(1 for o in objs if "_Door_" in o.name or "_Door" in o.name),
        "foundation": sum(1 for o in objs if "_Foundation" in o.name or "_Retaining_" in o.name),
        "samples": [o.name for o in objs[:40]],
    }
print(json.dumps(out))'''
print(blender('execute_code', code=code)['output'])

code2 = '''import bpy, json
name="AcademyAnnex_Facade_0"
o=bpy.data.objects.get(name)
mesh=o.data if o and o.type=="MESH" else None
out={}
if o and mesh:
    out={
      "name": o.name,
      "dimensions": list(o.dimensions),
      "location": list(o.location),
      "verts": len(mesh.vertices),
      "polys": len(mesh.polygons),
      "materials": [m.name for m in mesh.materials],
      "parent": o.parent.name if o.parent else None,
    }
print(json.dumps(out))'''
print(blender('execute_code', code=code2)['output'])
