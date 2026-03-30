import json
import sys
sys.path.insert(0, r'..\veilbreakers-gamedev-toolkit\Tools\cowork_bridge')
from vb_bridge import blender
code = '''import bpy, json
addons = []
for key in bpy.context.preferences.addons.keys():
    addons.append(key)
print(json.dumps(sorted(addons)))'''
print(blender('execute_code', code=code)['output'])
