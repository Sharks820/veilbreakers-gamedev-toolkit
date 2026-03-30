"""Explore Tripo Bridge - try known operator patterns."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vb_bridge import blender

# Try common Tripo operator names
r = blender("execute_code", code="""
import bpy

# Try to find Tripo operators by trying common patterns
ops_to_try = [
    'bpy.ops.tripo',
    'bpy.ops.tripo3d',
    'bpy.ops.triposr',
]

# Check if tripo module exists in ops
try:
    ops = bpy.ops.tripo
    print('bpy.ops.tripo EXISTS')
except:
    print('bpy.ops.tripo not found')

try:
    ops = bpy.ops.tripo3d
    print('bpy.ops.tripo3d EXISTS')
except:
    print('bpy.ops.tripo3d not found')

# Check scene properties
scene = bpy.context.scene
try:
    print(f'scene.tripo_props exists: {scene.tripo_props is not None}')
except:
    print('scene.tripo_props not found')

try:
    print(f'scene.tripo3d exists: {scene.tripo3d is not None}')
except:
    print('scene.tripo3d not found')

# Try to get info from the addon module directly
for addon_name in ['Tripo3d_Blender_Bridge', 'tripo-3d-for-blender']:
    prefs = bpy.context.preferences.addons.get(addon_name)
    if prefs:
        print(f'{addon_name}: addon found, prefs={prefs.preferences is not None}')
        if prefs.preferences:
            p = prefs.preferences
            # Try known property names
            for attr_name in ['api_key', 'token', 'apikey', 'api_token', 'model_format', 
                             'output_path', 'resolution', 'seed']:
                try:
                    val = repr(p[attr_name])[:50]
                    print(f'  {attr_name} = {val}')
                except:
                    pass
""")
if isinstance(r, dict):
    print(r.get('output', ''), flush=True)
