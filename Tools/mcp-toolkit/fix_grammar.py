import re

with open('blender_addon/handlers/_building_grammar.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix unused imports
text = re.sub(
    r'\s*generate_gothic_window,\s*generate_stone_wall,\s*generate_flying_buttress,  # ARCH-005',
    r'\n        generate_flying_buttress,  # ARCH-005',
    text
)

# 2. Fix unused wall_material
text = text.replace('    wall_material = STYLE_CONFIGS[style]["walls"]["material"]\n',
                    '    _wall_material = STYLE_CONFIGS[style]["walls"]["material"]\n')

# 3. Fix unused shaft_height
text = text.replace('    shaft_height = max(2.8, height * 0.78)\n',
                    '    _shaft_height = max(2.8, height * 0.78)\n')

# 4. Fix unused rng
text = text.replace('def generate_castle_spec(\n    outer_size: float = 40.0,\n    keep_size: float = 12.0,\n    tower_count: int = 4,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a castle spec with curtain walls, corner towers, keep, gatehouse."""\n    rng = random.Random(seed)\n',
                    'def generate_castle_spec(\n    outer_size: float = 40.0,\n    keep_size: float = 12.0,\n    tower_count: int = 4,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a castle spec with curtain walls, corner towers, keep, gatehouse."""\n    _rng = random.Random(seed)\n')

text = text.replace('def generate_fortress_spec(\n    size: float = 60.0,\n    wall_thickness: float = 2.0,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a fortress spec with outer walls, corner towers, keep, courtyard, gatehouse."""\n    rng = random.Random(seed)\n',
                    'def generate_fortress_spec(\n    size: float = 60.0,\n    wall_thickness: float = 2.0,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a fortress spec with outer walls, corner towers, keep, courtyard, gatehouse."""\n    _rng = random.Random(seed)\n')

text = text.replace('def generate_bridge_spec(\n    length: float = 40.0,\n    width: float = 6.0,\n    height: float = 12.0,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a bridge spec with arches, road deck, and railings."""\n    rng = random.Random(seed)\n',
                    'def generate_bridge_spec(\n    length: float = 40.0,\n    width: float = 6.0,\n    height: float = 12.0,\n    seed: int = 0,\n) -> BuildingSpec:\n    """Generate a bridge spec with arches, road deck, and railings."""\n    _rng = random.Random(seed)\n')

# 5. Fix ambiguous l variable
text = text.replace('for l in lights', 'for light in lights')
text = text.replace('l["position"]', 'light["position"]')
text = text.replace('l["type"]', 'light["type"]')

# 6. Fix unused door_y
text = text.replace('            door_y = 0.1\n', '            _door_y = 0.1\n')

# 7. Modify _append_fortress_tower_kit to accept segments, taper, crown_height and use cylinders
kit_old = """def _append_fortress_tower_kit(
    ops: list[dict],
    *,
    cx: float,
    cy: float,
    base_z: float,
    radius: float,
    height: float,
    material: str,
    role: str,
) -> None:"""

kit_new = """def _append_fortress_tower_kit(
    ops: list[dict],
    *,
    cx: float,
    cy: float,
    base_z: float,
    radius: float,
    height: float,
    segments: int = 8,
    taper: float = 0.9,
    crown_height: float = 0.8,
    material: str,
    role: str,
) -> None:"""
text = text.replace(kit_old, kit_new)

ops_old = """    ops.extend([
        {
            "type": "box",
            "position": [cx - plinth * 0.5, cy - plinth * 0.5, base_z],
            "size": [plinth, plinth, max(0.45, height * 0.10)],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.5, cy - shaft * 0.5, base_z + height * 0.08],
            "size": [shaft, shaft, lower_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.46, cy - shaft * 0.46, base_z + height * 0.34],
            "size": [shaft * 0.92, shaft * 0.92, mid_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - shaft * 0.38, cy - shaft * 0.38, base_z + height * 0.62],
            "size": [shaft * 0.76, shaft * 0.76, upper_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx + radius * 0.58, cy - stair_d * 0.30, base_z + height * 0.14],
            "size": [stair_w, stair_d, stair_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - radius * 1.12, cy + radius * 0.10, base_z + height * 0.18],
            "size": [buttress_w, buttress_d, buttress_h],
            "material": material,
            "role": role,
        },
    ])"""

ops_new = """    ops.extend([
        {
            "type": "cylinder",
            "position": [cx, cy, base_z],
            "radius": plinth * 0.5,
            "height": max(0.45, height * 0.10),
            "segments": segments,
            "material": material,
            "role": role,
        },
        {
            "type": "cylinder",
            "position": [cx, cy, base_z + height * 0.08],
            "radius": shaft * 0.5,
            "height": lower_h,
            "segments": segments,
            "taper": taper,
            "material": material,
            "role": role,
        },
        {
            "type": "cylinder",
            "position": [cx, cy, base_z + height * 0.34],
            "radius": shaft * 0.46,
            "height": mid_h,
            "segments": segments,
            "taper": taper,
            "material": material,
            "role": role,
        },
        {
            "type": "cylinder",
            "position": [cx, cy, base_z + height * 0.62],
            "radius": shaft * 0.38,
            "height": upper_h,
            "segments": segments,
            "taper": taper,
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx + radius * 0.58, cy - stair_d * 0.30, base_z + height * 0.14],
            "size": [stair_w, stair_d, stair_h],
            "material": material,
            "role": role,
        },
        {
            "type": "box",
            "position": [cx - radius * 1.12, cy + radius * 0.10, base_z + height * 0.18],
            "size": [buttress_w, buttress_d, buttress_h],
            "material": material,
            "role": role,
        },
        {
            "type": "cylinder",
            "position": [cx, cy, base_z + height * 0.88],
            "radius": crown * 0.5,
            "height": crown_height,
            "segments": segments,
            "material": material,
            "role": "crenellation",
        },
    ])"""
text = text.replace(ops_old, ops_new)

# 8. Update calls to _append_fortress_tower_kit in generate_castle_spec
call_old_castle = """        _append_fortress_tower_kit(
            ops,
            cx=cx,
            cy=cy,
            base_z=0.0,
            radius=tower_radius,
            height=tower_height,
            material="stone_fortified",
            role="tower",
        )"""

call_new_castle = """        _append_fortress_tower_kit(
            ops,
            cx=cx,
            cy=cy,
            base_z=0.0,
            radius=tower_radius,
            height=tower_height,
            segments=tower_segments,
            taper=tower_taper,
            crown_height=tower_crown_height,
            material="stone_fortified",
            role="tower",
        )"""
text = text.replace(call_old_castle, call_new_castle)

with open('blender_addon/handlers/_building_grammar.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Done")