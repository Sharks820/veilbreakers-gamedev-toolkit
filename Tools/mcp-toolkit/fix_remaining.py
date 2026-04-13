
def fix_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

anim_files = [
    'blender_addon/handlers/animation_abilities.py',
    'blender_addon/handlers/animation_blob.py',
    'blender_addon/handlers/animation_combat.py',
    'blender_addon/handlers/animation_locomotion.py',
    'blender_addon/handlers/animation_monster.py'
]
for af in anim_files:
    fix_file(af, [
        ('_t = frame / frame_count\n', 't = frame / frame_count\n'),
        ('_t = frame / fc\n', 't = frame / fc\n'),
        ('_profile = _BRAND_ATTACK_PROFILES', 'profile = _BRAND_ATTACK_PROFILES'),
    ])

fix_file('blender_addon/handlers/encounter_spaces.py', [
    ('L = template["length"]\n', 'length = template["length"]\n'),
    ('L = template.get("length", 30.0)\n', 'length = template.get("length", 30.0)\n'),
    ('L = template.get("length", 25.0)\n', 'length = template.get("length", 25.0)\n'),
])

fix_file('blender_addon/handlers/weapon_quality.py', [
    ('side__base = len(verts)\n', 'side_base = len(verts)\n'),
    ('flange__base = len(verts)\n', 'flange_base = len(verts)\n')
])

fix_file('blender_addon/handlers/procedural_meshes.py', [
    ('bevel = 0.005\n', '_bevel = 0.005\n')
])

fix_file('blender_addon/handlers/mesh_enhance.py', [
    ('tri_count = sum(', '_tri_count = sum(')
])

print("Reverted overly aggressive replacements and fixed specific typos.")
