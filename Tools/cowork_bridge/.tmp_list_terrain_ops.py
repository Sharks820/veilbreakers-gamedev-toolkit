import sys
sys.path.insert(0, r'..\veilbreakers-gamedev-toolkit\Tools\cowork_bridge')
from vb_bridge import blender
code = '''import bpy
ops=[]
for name in dir(bpy.ops):
    if any(tok in name.lower() for tok in ("ant","terrain","landscape")):
        ops.append(name)
print(sorted(ops))'''
print(blender('execute_code', code=code)['output'])
