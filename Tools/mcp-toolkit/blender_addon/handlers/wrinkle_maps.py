"""Dynamic wrinkle maps and non-destructive material layer stack system.

Pure-logic module (NO bpy imports). Provides:

1. **Wrinkle Map System** -- Define facial wrinkle regions driven by blend
   shapes or bones, and generate Blender Python code for driver setup.
2. **Material Layer Stack** -- Non-destructive layered material system with
   blend modes, masks, and opacity, returning Blender Python code for
   node-graph construction.

All public functions return either pure data dicts or Blender Python code
strings (for ``blender_execute``).  No ``bpy``/``bmesh`` dependencies.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]

# =========================================================================
# PART 1: Dynamic Wrinkle Map System (Gap #32)
# =========================================================================

# ---------------------------------------------------------------------------
# Wrinkle region definitions
# ---------------------------------------------------------------------------

# Each region defines a wrinkle pattern on the face mesh.
# center_z: vertical position (0=chin, 1=top of head, relative to face height)
# center_x: horizontal position (0=center, +right, -left)
# radius: region influence radius (in face-relative units)
# direction: primary displacement direction as (dx, dy, dz) unit vector
# depth: default wrinkle depth in metres
# trigger: which facial control drives this wrinkle

WRINKLE_REGION_DEFS: dict[str, dict[str, Any]] = {
    "forehead_horizontal": {
        "center_z": 0.80,
        "center_x": 0.0,
        "radius": 0.25,
        "direction": (0.0, 1.0, 0.0),   # outward from face
        "depth": 0.0015,
        "trigger_shape": "brow_raise",
        "trigger_bone": "brow_ctrl",
        "line_pattern": "horizontal",
        "line_count": 3,
        "description": "Horizontal forehead lines when brow raises",
    },
    "brow_vertical": {
        "center_z": 0.72,
        "center_x": 0.0,
        "radius": 0.08,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0020,
        "trigger_shape": "brow_furrow",
        "trigger_bone": "brow_inner_ctrl",
        "line_pattern": "vertical",
        "line_count": 2,
        "description": "Vertical furrow between brows (concentration/anger)",
    },
    "crow_feet_left": {
        "center_z": 0.60,
        "center_x": -0.35,
        "radius": 0.10,
        "direction": (0.0, 1.0, 0.2),
        "depth": 0.0010,
        "trigger_shape": "eye_squint_L",
        "trigger_bone": "eye_squint_L_ctrl",
        "line_pattern": "radial",
        "line_count": 4,
        "description": "Lines radiating from left eye corner",
    },
    "crow_feet_right": {
        "center_z": 0.60,
        "center_x": 0.35,
        "radius": 0.10,
        "direction": (0.0, 1.0, -0.2),
        "depth": 0.0010,
        "trigger_shape": "eye_squint_R",
        "trigger_bone": "eye_squint_R_ctrl",
        "line_pattern": "radial",
        "line_count": 4,
        "description": "Lines radiating from right eye corner",
    },
    "nasolabial_left": {
        "center_z": 0.40,
        "center_x": -0.15,
        "radius": 0.12,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0018,
        "trigger_shape": "smile_L",
        "trigger_bone": "lip_corner_L_ctrl",
        "line_pattern": "curve",
        "line_count": 1,
        "description": "Left nose-to-mouth fold (smiling)",
    },
    "nasolabial_right": {
        "center_z": 0.40,
        "center_x": 0.15,
        "radius": 0.12,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0018,
        "trigger_shape": "smile_R",
        "trigger_bone": "lip_corner_R_ctrl",
        "line_pattern": "curve",
        "line_count": 1,
        "description": "Right nose-to-mouth fold (smiling)",
    },
    "lip_lines": {
        "center_z": 0.28,
        "center_x": 0.0,
        "radius": 0.08,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0008,
        "trigger_shape": "lip_pucker",
        "trigger_bone": "lip_ctrl",
        "line_pattern": "vertical",
        "line_count": 6,
        "description": "Vertical lines around lips (pursing)",
    },
    "chin_dimple": {
        "center_z": 0.15,
        "center_x": 0.0,
        "radius": 0.06,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0012,
        "trigger_shape": "chin_raise",
        "trigger_bone": "chin_ctrl",
        "line_pattern": "single",
        "line_count": 1,
        "description": "Chin crease / dimple",
    },
    "neck_horizontal": {
        "center_z": 0.02,
        "center_x": 0.0,
        "radius": 0.20,
        "direction": (0.0, 0.0, 1.0),
        "depth": 0.0010,
        "trigger_shape": "head_tilt_down",
        "trigger_bone": "neck_ctrl",
        "line_pattern": "horizontal",
        "line_count": 2,
        "description": "Horizontal neck lines",
    },
    "cheek_fold_left": {
        "center_z": 0.45,
        "center_x": -0.25,
        "radius": 0.10,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0012,
        "trigger_shape": "cheek_puff_L",
        "trigger_bone": "cheek_L_ctrl",
        "line_pattern": "curve",
        "line_count": 1,
        "description": "Left cheek compression fold",
    },
    "cheek_fold_right": {
        "center_z": 0.45,
        "center_x": 0.25,
        "radius": 0.10,
        "direction": (0.0, 1.0, 0.0),
        "depth": 0.0012,
        "trigger_shape": "cheek_puff_R",
        "trigger_bone": "cheek_R_ctrl",
        "line_pattern": "curve",
        "line_count": 1,
        "description": "Right cheek compression fold",
    },
}

ALL_WRINKLE_REGIONS: list[str] = list(WRINKLE_REGION_DEFS.keys())


# ---------------------------------------------------------------------------
# Wrinkle region computation
# ---------------------------------------------------------------------------


def compute_wrinkle_map_regions(
    face_mesh_verts: list[Vec3],
    face_mesh_faces: list[tuple[int, ...]],
    regions: list[str] | None = None,
    age_factor: float = 1.0,
) -> dict[str, dict[str, Any]]:
    """Define wrinkle regions on a face mesh for animation-driven displacement.

    For each requested wrinkle region, finds the vertices within that region
    and computes per-vertex displacement vectors and falloff weights.

    Args:
        face_mesh_verts: Face mesh vertex positions.
        face_mesh_faces: Face mesh face indices.
        regions: List of region names to compute. None = all regions.
        age_factor: Multiplier for wrinkle depth (>1 = deeper/older, <1 = subtle).

    Returns:
        Dict keyed by region name, each containing:
        - vertex_indices: list of affected vertex indices
        - displacement_vectors: per-vertex (dx, dy, dz) displacement
        - falloff_weights: per-vertex 0..1 influence weight
        - wrinkle_depth: computed depth value
        - trigger_shape: shape key name that drives this wrinkle
        - trigger_bone: bone name alternative driver
        - line_pattern: pattern type
    """
    if not face_mesh_verts:
        return {}

    requested = regions or ALL_WRINKLE_REGIONS

    # Compute face mesh bounding box for normalization
    xs = [v[0] for v in face_mesh_verts]
    ys = [v[1] for v in face_mesh_verts]
    zs = [v[2] for v in face_mesh_verts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)

    face_width = max_x - min_x if max_x > min_x else 1.0
    face_height = max_z - min_z if max_z > min_z else (max_y - min_y if max_y > min_y else 1.0)

    # Determine which axis is "up" (largest range axis for vertical)
    ranges = [max_x - min_x, max_y - min_y, max_z - min_z]
    vertical_axis = ranges.index(max(ranges))  # Typically Y or Z

    results: dict[str, dict[str, Any]] = {}

    for region_name in requested:
        if region_name not in WRINKLE_REGION_DEFS:
            continue

        rdef = WRINKLE_REGION_DEFS[region_name]
        region_center_z_norm = rdef["center_z"]  # normalized 0..1 vertical
        region_center_x_norm = rdef["center_x"]  # normalized horizontal
        region_radius = rdef["radius"]
        depth = rdef["depth"] * age_factor
        direction = rdef["direction"]

        # Normalize direction
        d_len = math.sqrt(direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2)
        if d_len > 1e-8:
            direction = (direction[0] / d_len, direction[1] / d_len, direction[2] / d_len)

        vertex_indices: list[int] = []
        displacement_vectors: list[Vec3] = []
        falloff_weights: list[float] = []

        for vi, v in enumerate(face_mesh_verts):
            # Normalize vertex position to 0..1 range
            if vertical_axis == 1:
                # Y is up
                v_norm_z = (v[1] - min_y) / face_height if face_height > 0 else 0.5
                v_norm_x = (v[0] - (min_x + max_x) * 0.5) / (face_width * 0.5) if face_width > 0 else 0.0
            elif vertical_axis == 2:
                # Z is up
                v_norm_z = (v[2] - min_z) / face_height if face_height > 0 else 0.5
                v_norm_x = (v[0] - (min_x + max_x) * 0.5) / (face_width * 0.5) if face_width > 0 else 0.0
            else:
                # X is up (unusual)
                v_norm_z = (v[0] - min_x) / face_height if face_height > 0 else 0.5
                v_norm_x = (v[1] - (min_y + max_y) * 0.5) / (face_width * 0.5) if face_width > 0 else 0.0

            # Distance from region center
            dz = v_norm_z - region_center_z_norm
            dx = v_norm_x - region_center_x_norm
            dist = math.sqrt(dz * dz + dx * dx)

            if dist <= region_radius:
                # Smooth falloff using cosine
                falloff = 0.5 * (1.0 + math.cos(math.pi * dist / region_radius))

                # Wrinkle line modulation based on pattern
                pattern = rdef["line_pattern"]
                line_count = rdef["line_count"]
                modulation = 1.0

                if pattern == "horizontal":
                    # Horizontal wrinkle lines: modulate by vertical position
                    local_t = (dz / region_radius + 1.0) * 0.5  # 0..1
                    modulation = 0.5 * (1.0 + math.sin(local_t * line_count * math.pi * 2))
                elif pattern == "vertical":
                    local_t = (dx / region_radius + 1.0) * 0.5
                    modulation = 0.5 * (1.0 + math.sin(local_t * line_count * math.pi * 2))
                elif pattern == "radial":
                    angle = math.atan2(dz, dx)
                    modulation = 0.5 * (1.0 + math.sin(angle * line_count))
                elif pattern == "curve":
                    # Curved nasolabial fold
                    modulation = max(0.0, 1.0 - abs(dx) * 5.0)
                # "single" pattern: modulation stays 1.0

                weight = falloff * modulation
                if weight > 0.01:
                    vertex_indices.append(vi)
                    displacement_vectors.append((
                        direction[0] * depth * weight,
                        direction[1] * depth * weight,
                        direction[2] * depth * weight,
                    ))
                    falloff_weights.append(weight)

        results[region_name] = {
            "vertex_indices": vertex_indices,
            "displacement_vectors": displacement_vectors,
            "falloff_weights": falloff_weights,
            "wrinkle_depth": depth,
            "trigger_shape": rdef["trigger_shape"],
            "trigger_bone": rdef["trigger_bone"],
            "line_pattern": rdef["line_pattern"],
            "line_count": rdef["line_count"],
            "vertex_count": len(vertex_indices),
            "description": rdef["description"],
        }

    return results


# ---------------------------------------------------------------------------
# Blender code generation for wrinkle drivers
# ---------------------------------------------------------------------------


def generate_wrinkle_displacement_code(
    object_name: str,
    regions: dict[str, dict[str, Any]],
    driver_type: str = "shape_key",
) -> str:
    """Generate Blender Python code to set up wrinkle map drivers.

    Creates shape keys for each wrinkle region, driven by facial
    bones or shape keys.  When a character smiles, the nasolabial
    shape key activates and displaces the wrinkle geometry.

    Args:
        object_name: Name of the mesh object in Blender.
        regions: Output from compute_wrinkle_map_regions().
        driver_type: 'shape_key' or 'bone' -- what drives the wrinkles.

    Returns:
        Blender Python code string for blender_execute.
    """
    if driver_type not in ("shape_key", "bone"):
        driver_type = "shape_key"

    lines: list[str] = [
        "import bpy",
        "import mathutils",
        "",
        f"obj = bpy.data.objects.get('{object_name}')",
        "if obj is None or obj.type != 'MESH':",
        f"    raise ValueError('Object {object_name} not found or not a mesh')",
        "",
        "mesh = obj.data",
        "",
        "# Ensure shape key basis exists",
        "if obj.data.shape_keys is None:",
        "    obj.shape_key_add(name='Basis', from_mix=False)",
        "",
    ]

    for region_name, rdata in regions.items():
        indices = rdata.get("vertex_indices", [])
        displacements = rdata.get("displacement_vectors", [])
        trigger = rdata.get("trigger_shape", "")
        trigger_bone = rdata.get("trigger_bone", "")

        if not indices:
            continue

        sk_name = f"wrinkle_{region_name}"
        lines.append(f"# --- {region_name}: {rdata.get('description', '')} ---")
        lines.append(f"sk = obj.shape_key_add(name='{sk_name}', from_mix=False)")
        lines.append(f"sk.value = 0.0")
        lines.append("")

        # Set displacements
        lines.append(f"# Set wrinkle displacements for {len(indices)} vertices")
        for vi, disp in zip(indices, displacements):
            lines.append(
                f"sk.data[{vi}].co = mesh.vertices[{vi}].co + "
                f"mathutils.Vector(({disp[0]:.6f}, {disp[1]:.6f}, {disp[2]:.6f}))"
            )

        lines.append("")

        # Set up driver
        if driver_type == "shape_key":
            lines.append(f"# Driver: {sk_name} driven by {trigger}")
            lines.append(f"fcurve = sk.driver_add('value')")
            lines.append(f"drv = fcurve.driver")
            lines.append(f"drv.type = 'AVERAGE'")
            lines.append(f"var = drv.variables.new()")
            lines.append(f"var.name = 'trigger'")
            lines.append(f"var.type = 'SINGLE_PROP'")
            lines.append(f"var.targets[0].id = obj")
            lines.append(
                f"var.targets[0].data_path = "
                f"'data.shape_keys.key_blocks[\"{trigger}\"].value'"
            )
        else:  # bone driver
            lines.append(f"# Driver: {sk_name} driven by bone {trigger_bone}")
            lines.append(f"fcurve = sk.driver_add('value')")
            lines.append(f"drv = fcurve.driver")
            lines.append(f"drv.type = 'SCRIPTED'")
            lines.append(f"drv.expression = 'var'")
            lines.append(f"var = drv.variables.new()")
            lines.append(f"var.name = 'var'")
            lines.append(f"var.type = 'TRANSFORMS'")
            lines.append(f"var.targets[0].id = obj.parent")  # armature
            lines.append(f"var.targets[0].bone_target = '{trigger_bone}'")
            lines.append(f"var.targets[0].transform_type = 'LOC_Y'")
            lines.append(f"var.targets[0].transform_space = 'LOCAL_SPACE'")

        lines.append("")

    lines.append(f"print('Wrinkle setup complete for {object_name}: "
                 f"{len(regions)} regions')")

    return "\n".join(lines)


# =========================================================================
# PART 2: Non-Destructive Material Layer Stack (Gap #49)
# =========================================================================

# ---------------------------------------------------------------------------
# Smart material presets
# ---------------------------------------------------------------------------

SMART_MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "base_metal": {
        "base_color": (0.56, 0.57, 0.58, 1.0),
        "roughness": 0.45,
        "roughness_variation": 0.12,
        "roughness_noise_scale": 15.0,
        "metallic": 1.0,
        "normal_strength": 0.5,
    },
    "rusted_iron": {
        "base_color": (0.28, 0.15, 0.08, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.25,
        "roughness_noise_scale": 10.0,
        "metallic": 0.3,
        "normal_strength": 1.2,
    },
    "polished_steel": {
        "base_color": (0.63, 0.62, 0.64, 1.0),
        "roughness": 0.15,
        "roughness_variation": 0.05,
        "roughness_noise_scale": 20.0,
        "metallic": 1.0,
        "normal_strength": 0.3,
    },
    "dark_leather": {
        "base_color": (0.08, 0.05, 0.03, 1.0),
        "roughness": 0.70,
        "roughness_variation": 0.12,
        "roughness_noise_scale": 12.0,
        "metallic": 0.0,
        "normal_strength": 0.8,
    },
    "worn_fabric": {
        "base_color": (0.18, 0.15, 0.12, 1.0),
        "roughness": 0.90,
        "roughness_variation": 0.08,
        "roughness_noise_scale": 18.0,
        "metallic": 0.0,
        "normal_strength": 0.6,
    },
    "aged_wood": {
        "base_color": (0.14, 0.11, 0.08, 1.0),
        "roughness": 0.80,
        "roughness_variation": 0.12,
        "roughness_noise_scale": 8.0,
        "metallic": 0.0,
        "normal_strength": 0.9,
    },
    "rough_stone": {
        "base_color": (0.14, 0.12, 0.10, 1.0),
        "roughness": 0.85,
        "roughness_variation": 0.15,
        "roughness_noise_scale": 8.0,
        "metallic": 0.0,
        "normal_strength": 1.2,
    },
    "bone_white": {
        "base_color": (0.35, 0.32, 0.27, 1.0),
        "roughness": 0.55,
        "roughness_variation": 0.08,
        "roughness_noise_scale": 10.0,
        "metallic": 0.0,
        "normal_strength": 0.5,
    },
    "blood_stain": {
        "base_color": (0.25, 0.03, 0.02, 1.0),
        "roughness": 0.60,
        "roughness_variation": 0.15,
        "roughness_noise_scale": 6.0,
        "metallic": 0.0,
        "normal_strength": 0.3,
    },
    "edge_wear": {
        "base_color": (0.45, 0.42, 0.38, 1.0),
        "roughness": 0.30,
        "roughness_variation": 0.10,
        "roughness_noise_scale": 15.0,
        "metallic": 0.8,
        "normal_strength": 0.4,
    },
    "dirt_accumulation": {
        "base_color": (0.10, 0.08, 0.05, 1.0),
        "roughness": 0.95,
        "roughness_variation": 0.05,
        "roughness_noise_scale": 8.0,
        "metallic": 0.0,
        "normal_strength": 0.7,
    },
    "moss_growth": {
        "base_color": (0.08, 0.12, 0.06, 1.0),
        "roughness": 0.88,
        "roughness_variation": 0.08,
        "roughness_noise_scale": 12.0,
        "metallic": 0.0,
        "normal_strength": 0.9,
    },
    "frost_layer": {
        "base_color": (0.75, 0.82, 0.88, 1.0),
        "roughness": 0.20,
        "roughness_variation": 0.08,
        "roughness_noise_scale": 10.0,
        "metallic": 0.0,
        "normal_strength": 0.4,
    },
    "corruption_veins": {
        "base_color": (0.12, 0.04, 0.14, 1.0),
        "roughness": 0.50,
        "roughness_variation": 0.20,
        "roughness_noise_scale": 6.0,
        "metallic": 0.2,
        "normal_strength": 1.0,
    },
    "gold_trim": {
        "base_color": (1.0, 0.86, 0.57, 1.0),
        "roughness": 0.25,
        "roughness_variation": 0.08,
        "roughness_noise_scale": 18.0,
        "metallic": 1.0,
        "normal_strength": 0.3,
    },
}

ALL_MATERIAL_PRESETS: list[str] = list(SMART_MATERIAL_PRESETS.keys())

# ---------------------------------------------------------------------------
# Blend mode math (pure logic)
# ---------------------------------------------------------------------------

_BLEND_MODES = ("MIX", "ADD", "MULTIPLY", "OVERLAY", "SCREEN")


def _blend_value(base: float, layer: float, mode: str, opacity: float) -> float:
    """Blend a single channel value using the specified blend mode."""
    if opacity <= 0.0:
        return base
    if opacity >= 1.0:
        eff_opacity = 1.0
    else:
        eff_opacity = opacity

    if mode == "MIX":
        result = layer
    elif mode == "ADD":
        result = min(1.0, base + layer)
    elif mode == "MULTIPLY":
        result = base * layer
    elif mode == "OVERLAY":
        if base < 0.5:
            result = 2.0 * base * layer
        else:
            result = 1.0 - 2.0 * (1.0 - base) * (1.0 - layer)
    elif mode == "SCREEN":
        result = 1.0 - (1.0 - base) * (1.0 - layer)
    else:
        result = layer

    return base + (result - base) * eff_opacity


def _blend_color(
    base: tuple[float, ...],
    layer: tuple[float, ...],
    mode: str,
    opacity: float,
) -> tuple[float, ...]:
    """Blend two RGBA colors using the specified blend mode."""
    return tuple(
        _blend_value(base[i], layer[i], mode, opacity)
        for i in range(min(len(base), len(layer)))
    )


# ---------------------------------------------------------------------------
# Layer stack computation (pure logic)
# ---------------------------------------------------------------------------


def compute_layer_stack(layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute final material values from a layer stack.

    Each layer dict should contain:
        - name: str
        - base_color: tuple (r, g, b, a)
        - roughness: float
        - metallic: float
        - opacity: float (0-1)
        - blend_mode: str (MIX/ADD/MULTIPLY/OVERLAY/SCREEN)
        - mask_value: float (0-1, overall mask influence)

    Returns dict with final blended base_color, roughness, metallic, and
    per-layer contribution info.
    """
    if not layers:
        return {
            "base_color": (0.5, 0.5, 0.5, 1.0),
            "roughness": 0.5,
            "metallic": 0.0,
            "layer_count": 0,
            "contributions": [],
        }

    # Start with first layer as base
    first = layers[0]
    current_color = tuple(first.get("base_color", (0.5, 0.5, 0.5, 1.0)))
    current_roughness = first.get("roughness", 0.5)
    current_metallic = first.get("metallic", 0.0)

    contributions: list[dict[str, Any]] = [{
        "name": first.get("name", "base"),
        "effective_opacity": first.get("opacity", 1.0) * first.get("mask_value", 1.0),
    }]

    # Blend subsequent layers
    for layer in layers[1:]:
        opacity = layer.get("opacity", 1.0) * layer.get("mask_value", 1.0)
        mode = layer.get("blend_mode", "MIX")
        if mode not in _BLEND_MODES:
            mode = "MIX"

        layer_color = tuple(layer.get("base_color", (0.5, 0.5, 0.5, 1.0)))
        layer_roughness = layer.get("roughness", 0.5)
        layer_metallic = layer.get("metallic", 0.0)

        current_color = _blend_color(current_color, layer_color, mode, opacity)
        current_roughness = _blend_value(
            current_roughness, layer_roughness, mode, opacity
        )
        current_metallic = _blend_value(
            current_metallic, layer_metallic, mode, opacity
        )

        contributions.append({
            "name": layer.get("name", "unnamed"),
            "effective_opacity": opacity,
        })

    return {
        "base_color": current_color,
        "roughness": max(0.0, min(1.0, current_roughness)),
        "metallic": max(0.0, min(1.0, current_metallic)),
        "layer_count": len(layers),
        "contributions": contributions,
    }


# ---------------------------------------------------------------------------
# Material layer stack Blender code generation
# ---------------------------------------------------------------------------


def _generate_layer_node_group_code(
    layer_name: str,
    preset_name: str,
    group_index: int,
) -> list[str]:
    """Generate Blender Python code for a single material layer node group."""
    preset = SMART_MATERIAL_PRESETS.get(preset_name, SMART_MATERIAL_PRESETS["rough_stone"])
    bc = preset["base_color"]
    rough = preset["roughness"]
    metal = preset["metallic"]

    lines: list[str] = []
    gn = f"layer_{group_index}_{layer_name}"
    lines.append(f"# --- Layer {group_index}: {layer_name} ({preset_name}) ---")
    lines.append(f"grp_{group_index} = bpy.data.node_groups.new('{gn}', 'ShaderNodeTree')")
    lines.append(f"g = grp_{group_index}")
    # Outputs
    lines.append(f"g_out = g.nodes.new('NodeGroupOutput')")
    lines.append(f"g.interface.new_socket(name='Color', socket_type='NodeSocketColor', in_out='OUTPUT')")
    lines.append(f"g.interface.new_socket(name='Roughness', socket_type='NodeSocketFloat', in_out='OUTPUT')")
    lines.append(f"g.interface.new_socket(name='Metallic', socket_type='NodeSocketFloat', in_out='OUTPUT')")
    # Color node
    lines.append(f"rgb_{group_index} = g.nodes.new('ShaderNodeRGB')")
    lines.append(f"rgb_{group_index}.outputs[0].default_value = {list(bc)}")
    lines.append(f"g.links.new(rgb_{group_index}.outputs[0], g_out.inputs['Color'])")
    # Roughness
    lines.append(f"rough_{group_index} = g.nodes.new('ShaderNodeValue')")
    lines.append(f"rough_{group_index}.outputs[0].default_value = {rough}")
    lines.append(f"g.links.new(rough_{group_index}.outputs[0], g_out.inputs['Roughness'])")
    # Metallic
    lines.append(f"metal_{group_index} = g.nodes.new('ShaderNodeValue')")
    lines.append(f"metal_{group_index}.outputs[0].default_value = {metal}")
    lines.append(f"g.links.new(metal_{group_index}.outputs[0], g_out.inputs['Metallic'])")
    lines.append("")
    return lines


def _generate_mask_code(
    mask_type: str,
    mask_params: dict[str, Any],
    index: int,
) -> tuple[list[str], str]:
    """Generate mask node code. Returns (code_lines, output_socket_ref)."""
    lines: list[str] = []
    socket_ref = f"mask_{index}.outputs[0]"

    if mask_type == "noise":
        scale = mask_params.get("scale", 5.0)
        detail = mask_params.get("detail", 2.0)
        lines.append(f"mask_{index} = nodes.new('ShaderNodeTexNoise')")
        lines.append(f"mask_{index}.inputs['Scale'].default_value = {scale}")
        lines.append(f"mask_{index}.inputs['Detail'].default_value = {detail}")
        socket_ref = f"mask_{index}.outputs['Fac']"
    elif mask_type == "curvature":
        lines.append(f"# Curvature mask via Geometry node + Color Ramp")
        lines.append(f"mask_geom_{index} = nodes.new('ShaderNodeNewGeometry')")
        lines.append(f"mask_{index} = nodes.new('ShaderNodeValToRGB')")
        lines.append(f"links.new(mask_geom_{index}.outputs['Pointiness'], "
                      f"mask_{index}.inputs['Fac'])")
        socket_ref = f"mask_{index}.outputs['Color']"
    elif mask_type == "ao":
        lines.append(f"mask_{index} = nodes.new('ShaderNodeAmbientOcclusion')")
        dist = mask_params.get("distance", 1.0)
        lines.append(f"mask_{index}.inputs['Distance'].default_value = {dist}")
        socket_ref = f"mask_{index}.outputs['AO']"
    elif mask_type == "height":
        lines.append(f"mask_coord_{index} = nodes.new('ShaderNodeTexCoord')")
        lines.append(f"mask_sep_{index} = nodes.new('ShaderNodeSeparateXYZ')")
        lines.append(f"links.new(mask_coord_{index}.outputs['Object'], "
                      f"mask_sep_{index}.inputs['Vector'])")
        lines.append(f"mask_{index} = nodes.new('ShaderNodeMapRange')")
        low = mask_params.get("low", 0.0)
        high = mask_params.get("high", 1.0)
        lines.append(f"mask_{index}.inputs['From Min'].default_value = {low}")
        lines.append(f"mask_{index}.inputs['From Max'].default_value = {high}")
        lines.append(f"links.new(mask_sep_{index}.outputs['Z'], "
                      f"mask_{index}.inputs['Value'])")
        socket_ref = f"mask_{index}.outputs['Result']"
    elif mask_type == "vertex_group":
        vg_name = mask_params.get("vertex_group", "Group")
        lines.append(f"mask_attr_{index} = nodes.new('ShaderNodeAttribute')")
        lines.append(f"mask_attr_{index}.attribute_name = '{vg_name}'")
        lines.append(f"mask_{index} = mask_attr_{index}")
        socket_ref = f"mask_{index}.outputs['Fac']"
    else:
        # No mask -- use a constant 1.0 value
        lines.append(f"mask_{index} = nodes.new('ShaderNodeValue')")
        lines.append(f"mask_{index}.outputs[0].default_value = 1.0")
        socket_ref = f"mask_{index}.outputs[0]"

    return lines, socket_ref


def handle_material_layer_stack(params: dict[str, Any]) -> dict[str, Any]:
    """Create or manage a non-destructive layered material system.

    Params:
        object_name: str -- target Blender object
        action: str -- one of: add_layer, remove_layer, reorder_layer,
                       set_mask, set_blend_mode, set_opacity, list_layers, flatten
        layer_name: str -- name of the layer
        material_preset: str -- from SMART_MATERIAL_PRESETS
        blend_mode: str -- MIX/ADD/MULTIPLY/OVERLAY/SCREEN
        opacity: float -- 0.0 to 1.0
        mask_type: str -- none/curvature/ao/height/noise/vertex_group
        mask_params: dict -- parameters for the mask type
        layers: list[dict] -- for 'flatten' action, full layer stack

    Returns:
        Dict with 'code' (Blender Python code string) and/or 'result' data.
    """
    action = params.get("action", "add_layer")
    object_name = params.get("object_name", "")
    layer_name = params.get("layer_name", "Layer_0")
    preset_name = params.get("material_preset", "rough_stone")
    blend_mode = params.get("blend_mode", "MIX")
    opacity = params.get("opacity", 1.0)
    mask_type = params.get("mask_type", "none")
    mask_params = params.get("mask_params", {})

    if blend_mode not in _BLEND_MODES:
        blend_mode = "MIX"
    opacity = max(0.0, min(1.0, float(opacity)))

    if action == "list_layers":
        return {
            "available_presets": ALL_MATERIAL_PRESETS,
            "available_blend_modes": list(_BLEND_MODES),
            "available_mask_types": ["none", "curvature", "ao", "height", "noise", "vertex_group"],
        }

    if action == "flatten":
        layer_list = params.get("layers", [])
        result = compute_layer_stack(layer_list)
        return {"result": result, "action": "flatten"}

    if action == "add_layer":
        # Generate Blender code to add a material layer
        lines: list[str] = [
            "import bpy",
            "",
            f"obj = bpy.data.objects.get('{object_name}')",
            "if obj is None:",
            f"    raise ValueError('Object {object_name} not found')",
            "",
            "mat = obj.active_material",
            "if mat is None:",
            f"    mat = bpy.data.materials.new(name='{object_name}_layered')",
            "    mat.use_nodes = True",
            "    obj.data.materials.append(mat)",
            "",
            "nodes = mat.node_tree.nodes",
            "links = mat.node_tree.links",
            "",
        ]

        # Create layer node group
        layer_code = _generate_layer_node_group_code(layer_name, preset_name, 0)
        lines.extend(layer_code)

        # Create group node in material
        lines.append(f"layer_node = nodes.new('ShaderNodeGroup')")
        lines.append(f"layer_node.node_tree = grp_0")
        lines.append(f"layer_node.name = 'Layer_{layer_name}'")
        lines.append(f"layer_node.label = '{layer_name}'")
        lines.append("")

        # Create mask
        mask_lines, mask_socket = _generate_mask_code(mask_type, mask_params, 0)
        lines.extend(mask_lines)
        lines.append("")

        # Create Mix nodes for color, roughness, metallic
        lines.append(f"# Blend: {blend_mode} at opacity {opacity}")
        lines.append(f"mix_color = nodes.new('ShaderNodeMix')")
        lines.append(f"mix_color.data_type = 'RGBA'")
        lines.append(f"mix_color.blend_type = '{blend_mode}'")
        lines.append(f"mix_color.inputs['Fac'].default_value = {opacity}")
        lines.append(f"mix_color.label = '{layer_name}_color_blend'")
        lines.append("")

        # Connect mask to factor if applicable
        if mask_type != "none":
            lines.append(f"# Multiply opacity by mask")
            lines.append(f"mask_mul = nodes.new('ShaderNodeMath')")
            lines.append(f"mask_mul.operation = 'MULTIPLY'")
            lines.append(f"mask_mul.inputs[0].default_value = {opacity}")
            lines.append(f"links.new({mask_socket}, mask_mul.inputs[1])")
            lines.append(f"links.new(mask_mul.outputs[0], mix_color.inputs['Fac'])")

        lines.append(f"print('Layer {layer_name} added with {preset_name} preset')")

        return {
            "code": "\n".join(lines),
            "action": "add_layer",
            "layer_name": layer_name,
            "preset": preset_name,
            "blend_mode": blend_mode,
            "opacity": opacity,
            "mask_type": mask_type,
        }

    if action == "remove_layer":
        code = "\n".join([
            "import bpy",
            "",
            f"obj = bpy.data.objects.get('{object_name}')",
            "if obj and obj.active_material:",
            "    nodes = obj.active_material.node_tree.nodes",
            f"    target = nodes.get('Layer_{layer_name}')",
            "    if target:",
            "        nodes.remove(target)",
            f"        print('Removed layer {layer_name}')",
            "    else:",
            f"        print('Layer {layer_name} not found')",
        ])
        return {"code": code, "action": "remove_layer", "layer_name": layer_name}

    if action == "set_opacity":
        code = "\n".join([
            "import bpy",
            "",
            f"obj = bpy.data.objects.get('{object_name}')",
            "if obj and obj.active_material:",
            "    nodes = obj.active_material.node_tree.nodes",
            f"    mix = nodes.get('{layer_name}_color_blend')",
            "    if mix:",
            f"        mix.inputs['Fac'].default_value = {opacity}",
            f"        print('Set {layer_name} opacity to {opacity}')",
        ])
        return {"code": code, "action": "set_opacity", "layer_name": layer_name, "opacity": opacity}

    if action == "set_blend_mode":
        code = "\n".join([
            "import bpy",
            "",
            f"obj = bpy.data.objects.get('{object_name}')",
            "if obj and obj.active_material:",
            "    nodes = obj.active_material.node_tree.nodes",
            f"    mix = nodes.get('{layer_name}_color_blend')",
            "    if mix:",
            f"        mix.blend_type = '{blend_mode}'",
            f"        print('Set {layer_name} blend mode to {blend_mode}')",
        ])
        return {"code": code, "action": "set_blend_mode", "layer_name": layer_name,
                "blend_mode": blend_mode}

    if action == "set_mask":
        lines_list: list[str] = [
            "import bpy",
            "",
            f"obj = bpy.data.objects.get('{object_name}')",
            "if obj and obj.active_material:",
            "    nodes = obj.active_material.node_tree.nodes",
            "    links = obj.active_material.node_tree.links",
            "",
        ]
        mask_lines, mask_socket = _generate_mask_code(mask_type, mask_params, 0)
        lines_list.extend(["    " + l for l in mask_lines])
        lines_list.append(f"    print('Mask set for {layer_name}: {mask_type}')")
        return {"code": "\n".join(lines_list), "action": "set_mask",
                "layer_name": layer_name, "mask_type": mask_type}

    if action == "reorder_layer":
        # Reordering requires knowledge of current layer order -- return guidance
        return {
            "action": "reorder_layer",
            "note": "Reorder by removing and re-adding layers in desired order.",
            "layer_name": layer_name,
        }

    return {"error": f"Unknown action: {action}"}
