import sys
sys.path.insert(0, r'..\veilbreakers-gamedev-toolkit\Tools\cowork_bridge')
from vb_bridge import blender
code = '''import addon_utils
mods=[]
for mod in addon_utils.modules():
    name = getattr(mod, "__name__", "")
    if any(tok in name.lower() for tok in ("terrain","landscape","scatter","forest","botaniq","grass","ant")):
        mods.append(name)
print(sorted(mods))'''
print(blender('execute_code', code=code)['output'])
