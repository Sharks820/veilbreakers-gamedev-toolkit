"""Check Blender addons - stdout is captured in result['output']."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

r = blender("execute_code", code="""
import bpy
print('VERSION:', bpy.app.version_string)
print('ENGINE:', bpy.context.scene.render.engine)
print('ADDONS:')
for name in sorted(bpy.context.preferences.addons.keys()):
    print(f'  {name}')
print(f'TOTAL: {len(bpy.context.preferences.addons)}')
""")

# The result has 'output' field with captured stdout
if isinstance(r, dict):
    output = r.get('output', '')
    print(output, flush=True)
else:
    print(f"Raw: {r}", flush=True)
