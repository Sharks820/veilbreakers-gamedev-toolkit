"""Blender handlers for vegetation scatter, prop scatter, and breakable props.

Provides 3 command handlers:
  - handle_scatter_vegetation: Biome-aware tree/grass/rock scatter using
    collection instances for performance.
  - handle_scatter_props: Context-aware prop placement near tagged buildings.
  - handle_create_breakable: Generate intact + damaged variant pairs.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

import bpy
import bmesh

from ._scatter_engine import (
    poisson_disk_sample,
    biome_filter_points,
    context_scatter,
    generate_breakable_variants,
)
from ._terrain_noise import compute_slope_map
from ._mesh_bridge import mesh_from_spec, VEGETATION_GENERATOR_MAP, PROP_GENERATOR_MAP


# ---------------------------------------------------------------------------
# Lightweight scatter material presets
# ---------------------------------------------------------------------------

_SCATTER_MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "tree": {
        "mode": "tree",
        "trunk_color": (0.19, 0.15, 0.10, 1.0),
        "foliage_color": (0.16, 0.23, 0.12, 1.0),
        "accent_color": (0.10, 0.14, 0.08, 1.0),
        "roughness": 0.80,
    },
    "tree_healthy": {
        "mode": "tree",
        "trunk_color": (0.20, 0.15, 0.09, 1.0),
        "foliage_color": (0.18, 0.25, 0.14, 1.0),
        "accent_color": (0.12, 0.17, 0.09, 1.0),
        "roughness": 0.78,
    },
    "tree_boundary": {
        "mode": "tree",
        "trunk_color": (0.18, 0.14, 0.10, 1.0),
        "foliage_color": (0.14, 0.18, 0.11, 1.0),
        "accent_color": (0.11, 0.10, 0.08, 1.0),
        "roughness": 0.83,
    },
    "tree_blighted": {
        "mode": "tree",
        "trunk_color": (0.17, 0.15, 0.14, 1.0),
        "foliage_color": (0.12, 0.10, 0.12, 1.0),
        "accent_color": (0.16, 0.07, 0.15, 1.0),
        "roughness": 0.87,
        "emission_strength": 0.04,
    },
    "tree_dead": {
        "mode": "tree",
        "trunk_color": (0.23, 0.21, 0.18, 1.0),
        "foliage_color": (0.23, 0.21, 0.18, 1.0),
        "accent_color": (0.14, 0.12, 0.10, 1.0),
        "roughness": 0.88,
    },
    "tree_twisted": {
        "mode": "tree",
        "trunk_color": (0.18, 0.14, 0.10, 1.0),
        "foliage_color": (0.14, 0.18, 0.11, 1.0),
        "accent_color": (0.11, 0.10, 0.08, 1.0),
        "roughness": 0.83,
    },
    "pine_tree": {
        "mode": "tree",
        "trunk_color": (0.16, 0.12, 0.08, 1.0),
        "foliage_color": (0.10, 0.15, 0.09, 1.0),
        "accent_color": (0.06, 0.10, 0.06, 1.0),
        "roughness": 0.80,
    },
    "bush": {"mode": "foliage", "base_color": (0.14, 0.20, 0.11, 1.0), "accent_color": (0.09, 0.13, 0.07, 1.0), "roughness": 0.74},
    "shrub": {"mode": "foliage", "base_color": (0.14, 0.20, 0.11, 1.0), "accent_color": (0.09, 0.13, 0.07, 1.0), "roughness": 0.74},
    "grass": {"mode": "foliage", "base_color": (0.16, 0.20, 0.10, 1.0), "accent_color": (0.10, 0.12, 0.06, 1.0), "roughness": 0.72},
    "weed": {"mode": "foliage", "base_color": (0.15, 0.17, 0.10, 1.0), "accent_color": (0.10, 0.11, 0.07, 1.0), "roughness": 0.76},
    "rock": {"mode": "mineral", "base_color": (0.24, 0.24, 0.22, 1.0), "accent_color": (0.12, 0.16, 0.10, 1.0), "roughness": 0.92},
    "rock_mossy": {"mode": "mineral", "base_color": (0.21, 0.22, 0.20, 1.0), "accent_color": (0.11, 0.15, 0.10, 1.0), "roughness": 0.90},
    "cliff_rock": {"mode": "mineral", "base_color": (0.23, 0.22, 0.21, 1.0), "accent_color": (0.10, 0.12, 0.10, 1.0), "roughness": 0.94},
    "mushroom": {"mode": "organic", "base_color": (0.28, 0.22, 0.20, 1.0), "accent_color": (0.18, 0.12, 0.10, 1.0), "roughness": 0.78},
    "mushroom_cluster": {"mode": "organic", "base_color": (0.22, 0.20, 0.17, 1.0), "accent_color": (0.16, 0.12, 0.10, 1.0), "roughness": 0.80},
    "root": {"mode": "organic", "base_color": (0.18, 0.14, 0.10, 1.0), "accent_color": (0.11, 0.08, 0.06, 1.0), "roughness": 0.86},
    "fallen_log": {"mode": "organic", "base_color": (0.20, 0.15, 0.10, 1.0), "accent_color": (0.11, 0.08, 0.06, 1.0), "roughness": 0.84},
    "barrel": {"mode": "organic", "base_color": (0.23, 0.16, 0.10, 1.0), "accent_color": (0.15, 0.10, 0.06, 1.0), "roughness": 0.74},
    "crate": {"mode": "organic", "base_color": (0.24, 0.17, 0.11, 1.0), "accent_color": (0.16, 0.11, 0.07, 1.0), "roughness": 0.76},
    "lantern": {"mode": "metal", "base_color": (0.18, 0.17, 0.16, 1.0), "accent_color": (0.32, 0.24, 0.12, 1.0), "roughness": 0.45},
}


_VEGETATION_Y_UP_TYPES = frozenset({
    "tree",
    "tree_healthy",
    "tree_boundary",
    "tree_blighted",
    "tree_dead",
    "tree_twisted",
    "pine_tree",
    "bush",
    "shrub",
    "grass",
    "weed",
    "mushroom",
    "root",
})

_PROP_Y_UP_TYPES = frozenset({
    "bush",
    "shrub",
    "dead_tree",
    "tree",
    "tree_healthy",
    "tree_boundary",
    "tree_blighted",
    "tree_twisted",
    "pine_tree",
    "mushroom",
})


def _assign_scatter_material(obj: bpy.types.Object, material_key: str) -> None:
    """Assign a lightweight procedural preview material.

    The goal is not final authored shading; it is to avoid flat gray
    placeholders so Blender previews show readable bark, foliage, and
    rock variation.
    """
    if not hasattr(obj, "data") or obj.data is None:
        return

    preset = _SCATTER_MATERIAL_PRESETS.get(material_key, {
        "mode": "organic",
        "base_color": (0.2, 0.2, 0.2, 1.0),
        "accent_color": (0.1, 0.1, 0.1, 1.0),
        "roughness": 0.8,
    })
    mat_name = f"mat_{material_key}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    if not mat.node_tree:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        return

    nt = mat.node_tree
    nt.nodes.clear()
    output = nt.nodes.new("ShaderNodeOutputMaterial")
    output.location = (640, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (360, 0)
    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-1000, 80)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-800, 80)
    mapping.inputs["Scale"].default_value = (3.2, 3.2, 3.2)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-580, 120)
    noise.inputs["Scale"].default_value = 5.5
    noise.inputs["Detail"].default_value = 7.0
    noise.inputs["Roughness"].default_value = 0.55
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-340, 120)
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[1].position = 0.82

    mode = str(preset.get("mode", "organic"))
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.location = (120, 110)
    mix.blend_type = "MIX"

    if mode == "tree":
        geom = nt.nodes.new("ShaderNodeNewGeometry")
        geom.location = (-1000, -180)
        separate = nt.nodes.new("ShaderNodeSeparateXYZ")
        separate.location = (-780, -180)
        height_ramp = nt.nodes.new("ShaderNodeValToRGB")
        height_ramp.location = (-520, -180)
        height_ramp.color_ramp.elements[0].position = 0.28
        height_ramp.color_ramp.elements[1].position = 0.52
        height_ramp.color_ramp.elements[0].color = preset["trunk_color"]
        height_ramp.color_ramp.elements[1].color = preset["foliage_color"]
        accent_mix = nt.nodes.new("ShaderNodeMixRGB")
        accent_mix.location = (-120, -20)
        accent_mix.blend_type = "MULTIPLY"
        accent_mix.inputs["Color2"].default_value = preset.get("accent_color", preset["foliage_color"])
        accent_mix.inputs["Fac"].default_value = 0.28

        nt.links.new(geom.outputs["Position"], separate.inputs["Vector"])
        nt.links.new(separate.outputs["Y"], height_ramp.inputs["Fac"])
        nt.links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(height_ramp.outputs["Color"], accent_mix.inputs["Color1"])
        nt.links.new(noise.outputs["Fac"], accent_mix.inputs["Fac"])
        nt.links.new(accent_mix.outputs["Color"], mix.inputs["Color1"])
        mix.inputs["Color2"].default_value = preset.get("accent_color", preset["foliage_color"])
        mix.inputs["Fac"].default_value = 0.15
    else:
        mix.inputs["Color1"].default_value = preset["base_color"]
        mix.inputs["Color2"].default_value = preset.get("accent_color", preset["base_color"])
        nt.links.new(tex_coord.outputs["Object"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(noise.outputs["Fac"], mix.inputs["Fac"])

    nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = float(preset["roughness"])
    if "Emission Color" in bsdf.inputs and float(preset.get("emission_strength", 0.0)) > 0.0:
        bsdf.inputs["Emission Color"].default_value = preset.get("accent_color", preset.get("base_color", (0.1, 0.1, 0.1, 1.0)))
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = float(preset.get("emission_strength", 0.0))
    if mode == "metal":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.4
    nt.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _vegetation_rotation(veg_type: str, yaw_degrees: float) -> tuple[float, float, float]:
    """Return a world rotation that converts Y-up generated meshes to Blender Z-up."""
    x_rot = math.radians(90.0) if veg_type in _VEGETATION_Y_UP_TYPES else 0.0
    return (x_rot, 0.0, math.radians(yaw_degrees))


def _prop_rotation(prop_type: str, yaw_degrees: float) -> tuple[float, float, float]:
    """Return a world rotation for prop-scatter meshes with Y-up authored geometry."""
    x_rot = math.radians(90.0) if prop_type in _PROP_Y_UP_TYPES else 0.0
    return (x_rot, 0.0, math.radians(yaw_degrees))


def _terrain_height_sampler(terrain_obj: bpy.types.Object | None):
    """Build a lightweight terrain-height sampler for prop placement."""
    if terrain_obj is None or terrain_obj.type != "MESH" or terrain_obj.data is None:
        return None

    mesh = terrain_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    vert_count = len(bm.verts)
    side = int(math.sqrt(vert_count))
    if side < 2 or side * side != vert_count:
        bm.free()
        return None

    heights = np.array([v.co.z for v in bm.verts], dtype=np.float64)
    bm.free()
    height_max = heights.max() if heights.size and heights.max() > 0 else 1.0
    heightmap = (heights / height_max).reshape(side, side)
    dims = terrain_obj.dimensions
    terrain_size = max(dims.x, dims.y, 1.0)
    half_size = terrain_size / 2.0

    def _sample(world_x: float, world_y: float) -> float:
        u = (world_x + half_size) / terrain_size
        v = (world_y + half_size) / terrain_size
        ci = int(u * (side - 1))
        ri = int(v * (side - 1))
        ci = max(0, min(ci, side - 1))
        ri = max(0, min(ri, side - 1))
        return float(heightmap[ri, ci]) * height_max

    return _sample


# ---------------------------------------------------------------------------
# Default biome vegetation rules
# ---------------------------------------------------------------------------

_DEFAULT_VEG_RULES: list[dict[str, Any]] = [
    {
        "vegetation_type": "tree",
        "min_alt": 0.15,
        "max_alt": 0.65,
        "min_slope": 0.0,
        "max_slope": 25.0,
        "scale_range": (0.8, 1.5),
        "density": 0.7,
    },
    {
        "vegetation_type": "bush",
        "min_alt": 0.1,
        "max_alt": 0.5,
        "min_slope": 0.0,
        "max_slope": 35.0,
        "scale_range": (0.5, 1.0),
        "density": 0.8,
    },
    {
        "vegetation_type": "grass",
        "min_alt": 0.05,
        "max_alt": 0.4,
        "min_slope": 0.0,
        "max_slope": 30.0,
        "scale_range": (0.3, 0.7),
        "density": 0.9,
    },
    {
        "vegetation_type": "rock",
        "min_alt": 0.4,
        "max_alt": 1.0,
        "min_slope": 20.0,
        "max_slope": 90.0,
        "scale_range": (0.5, 1.2),
        "density": 0.6,
    },
]


# ---------------------------------------------------------------------------
# Template geometry helpers
# ---------------------------------------------------------------------------

def _create_template_collection(name: str) -> bpy.types.Collection:
    """Create a hidden collection for instance templates."""
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    # Hide from viewport and render
    coll.hide_viewport = True
    coll.hide_render = True
    return coll


def _create_vegetation_template(
    veg_type: str, collection: bpy.types.Collection
) -> bpy.types.Object:
    """Create a template mesh for a vegetation type.

    Uses procedural mesh generators from VEGETATION_GENERATOR_MAP when
    available. Falls back to simple primitives for unmapped types.
    """
    gen_entry = VEGETATION_GENERATOR_MAP.get(veg_type)
    if gen_entry is not None:
        # Use procedural mesh generator with lower segment counts for
        # scatter templates (these get instanced 1000s of times)
        gen_func, gen_kwargs = gen_entry
        scatter_kwargs = dict(gen_kwargs)
        if veg_type == "tree":
            scatter_kwargs.setdefault("branch_count", 4)  # lower for scatter
        elif veg_type == "rock":
            scatter_kwargs.setdefault("detail", 2)  # lower for scatter
        spec = gen_func(**scatter_kwargs)
        obj = mesh_from_spec(
            spec,
            name=f"_template_{veg_type}",
            collection=collection,
        )
        if getattr(obj, "data", None) is not None and hasattr(obj.data, "polygons"):
            for poly in obj.data.polygons:
                poly.use_smooth = True
        _assign_scatter_material(obj, veg_type)
        return obj

    # Fallback: simple primitives for unmapped types
    mesh = bpy.data.meshes.new(f"_template_{veg_type}")
    bm = bmesh.new()

    if veg_type == "grass":
        # Flat plane for grass (billboard grass is correct for games)
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.3)
    else:
        bmesh.ops.create_cube(bm, size=0.5)

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(f"_template_{veg_type}", mesh)
    collection.objects.link(obj)
    if hasattr(obj.data, "polygons"):
        for poly in obj.data.polygons:
            poly.use_smooth = True

    _assign_scatter_material(obj, veg_type)

    return obj


# ---------------------------------------------------------------------------
# Handler: scatter_vegetation
# ---------------------------------------------------------------------------

def handle_scatter_vegetation(params: dict) -> dict:
    """Scatter vegetation on terrain using Poisson disk + biome rules.

    Uses collection instances for performance (not individual objects).

    Params:
        terrain_name (str): Existing terrain object name.
        rules (list of dict, optional): Biome vegetation rules. Defaults to
            built-in dark-fantasy rules. Each rule can include min_moisture
            and max_moisture keys when moisture_map is provided.
        min_distance (float, default 3.0): Minimum distance between instances.
        seed (int, default 0): Random seed.
        max_instances (int, default 5000): Cap on total instances.
        max_tilt_angle (float, default 45.0): Maximum terrain slope in degrees.
            Points where terrain is steeper than this are rejected.
        moisture_map (list of list or None): Optional 2D moisture map [0,1]
            matching terrain resolution.  When provided, per-rule
            min_moisture/max_moisture are applied during filtering.

    Returns dict with: name, instance_count, vegetation_types, bounds.
    """
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    rules = params.get("rules", _DEFAULT_VEG_RULES)
    min_distance = params.get("min_distance", 3.0)
    seed = params.get("seed", 0)
    max_instances = params.get("max_instances", 5000)
    max_tilt_angle = params.get("max_tilt_angle", 45.0)
    moisture_map_raw = params.get("moisture_map", None)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    # Extract heightmap from terrain mesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    vert_count = len(bm.verts)
    side = int(math.sqrt(vert_count))
    if side < 2:
        bm.free()
        raise ValueError("Terrain mesh too small for scatter")

    heights = np.array([v.co.z for v in bm.verts])
    bm.free()

    height_max = heights.max() if heights.max() > 0 else 1.0
    heightmap = (heights / height_max).reshape(side, side)
    slope_map = compute_slope_map(heightmap)

    # Determine terrain world-space size
    dims = obj.dimensions
    terrain_size = max(dims.x, dims.y, 1.0)

    # Generate scatter points
    candidates = poisson_disk_sample(
        terrain_size, terrain_size, min_distance, seed=seed,
    )

    # Convert moisture_map to numpy array if provided
    moisture_np = None
    if moisture_map_raw is not None:
        moisture_np = np.array(moisture_map_raw, dtype=np.float64)
        # Resize to match heightmap if needed
        if moisture_np.shape != heightmap.shape:
            # Simple nearest-neighbor resize
            from numpy import round as np_round
            y_idx = np.round(np.linspace(0, moisture_np.shape[0] - 1, side)).astype(int)
            x_idx = np.round(np.linspace(0, moisture_np.shape[1] - 1, side)).astype(int)
            moisture_np = moisture_np[np.ix_(y_idx, x_idx)]

    # Filter through biome rules
    placements = biome_filter_points(
        candidates, heightmap, slope_map, rules,
        terrain_size=terrain_size, seed=seed,
        max_tilt_angle=max_tilt_angle,
        moisture_map=moisture_np,
    )

    # Cap instances
    if len(placements) > max_instances:
        placements = placements[:max_instances]

    # Create template collection and templates
    template_coll = _create_template_collection(f"{terrain_name}_veg_templates")
    templates: dict[str, bpy.types.Object] = {}

    # Collect unique vegetation types
    veg_types_needed = set(p["vegetation_type"] for p in placements)
    for vt in veg_types_needed:
        templates[vt] = _create_vegetation_template(vt, template_coll)

    # Create instances using collection instances
    scatter_coll_name = f"{terrain_name}_vegetation"
    scatter_coll = bpy.data.collections.new(scatter_coll_name)
    bpy.context.scene.collection.children.link(scatter_coll)

    veg_counts: dict[str, int] = {}
    terrain_half = terrain_size / 2.0

    for p in placements:
        vt = p["vegetation_type"]
        template = templates.get(vt)
        if template is None:
            continue

        veg_counts[vt] = veg_counts.get(vt, 0) + 1

        instance = bpy.data.objects.new(
            f"{vt}_{veg_counts[vt]:04d}", template.data,
        )
        # Position: offset from terrain center
        wx = p["position"][0] - terrain_half
        wy = p["position"][1] - terrain_half

        # Sample terrain height at this position
        u = p["position"][0] / terrain_size
        v = p["position"][1] / terrain_size
        ci = int(u * (side - 1))
        ri = int(v * (side - 1))
        ci = max(0, min(ci, side - 1))
        ri = max(0, min(ri, side - 1))
        wz = float(heightmap[ri, ci]) * height_max

        instance.location = (wx, wy, wz)
        instance.rotation_euler = _vegetation_rotation(vt, p["rotation"])
        s = p["scale"]
        instance.scale = (s, s, s)

        scatter_coll.objects.link(instance)

    total_instances = sum(veg_counts.values())

    return {
        "name": scatter_coll_name,
        "instance_count": total_instances,
        "vegetation_types": veg_counts,
        "bounds": {
            "width": terrain_size,
            "depth": terrain_size,
        },
    }


# ---------------------------------------------------------------------------
# Handler: scatter_props
# ---------------------------------------------------------------------------

def _create_prop_template(
    prop_type: str, collection: bpy.types.Collection
) -> bpy.types.Object:
    """Create a template mesh for a prop type.

    Uses procedural mesh generators from PROP_GENERATOR_MAP when
    available. Falls back to a scaled cube with a warning for unmapped
    types so that scatter never silently produces featureless geometry.
    """
    gen_entry = PROP_GENERATOR_MAP.get(prop_type)
    if gen_entry is not None:
        gen_func, gen_kwargs = gen_entry
        # Use lower detail for scatter templates (instanced many times)
        scatter_kwargs = dict(gen_kwargs)
        if prop_type in ("dead_tree",):
            scatter_kwargs.setdefault("branch_count", 3)
        elif prop_type in ("rock", "coal_pile"):
            scatter_kwargs.setdefault("detail", 2)
        spec = gen_func(**scatter_kwargs)
        obj = mesh_from_spec(
            spec,
            name=f"_template_{prop_type}",
            collection=collection,
        )
        _assign_scatter_material(obj, prop_type)
        return obj

    # Fallback: cube with warning for unmapped prop types
    print(f"WARNING: No procedural generator for prop type '{prop_type}', "
          f"using fallback cube. Add an entry to PROP_GENERATOR_MAP.")
    mesh = bpy.data.meshes.new(f"_template_{prop_type}")
    bm_fallback = bmesh.new()
    bmesh.ops.create_cube(bm_fallback, size=0.5)
    bm_fallback.to_mesh(mesh)
    bm_fallback.free()

    obj = bpy.data.objects.new(f"_template_{prop_type}", mesh)
    collection.objects.link(obj)

    _assign_scatter_material(obj, prop_type)

    return obj


def handle_scatter_props(params: dict) -> dict:
    """Scatter context-aware props near buildings using collection instances.

    Uses procedural mesh generators from PROP_GENERATOR_MAP for real prop
    meshes instead of placeholder cubes. Falls back to cubes with a warning
    for any prop type without a generator mapping.

    Params:
        area_name (str, default "PropScatter"): Name for the scatter collection.
        buildings (list of dict): Each has type, position, footprint (optional).
        prop_density (float, default 0.3): Scatter density.
        seed (int, default 0): Random seed.

    Returns dict with: name, prop_count, prop_types.
    """
    area_name = params.get("area_name", "PropScatter")
    buildings = params.get("buildings", [])
    prop_density = params.get("prop_density", 0.3)
    seed = params.get("seed", 0)

    if not buildings:
        raise ValueError("'buildings' list is required and must not be empty")

    # Determine area size from building positions
    positions = [b["position"] for b in buildings]
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    margin = 20.0
    area_size = max(max(xs) - min(xs) + margin * 2, max(ys) - min(ys) + margin * 2, 30.0)
    terrain_sampler = _terrain_height_sampler(bpy.data.objects.get(area_name))

    placements = context_scatter(buildings, area_size, prop_density, seed)

    # Create scatter collection
    scatter_coll = bpy.data.collections.new(area_name)
    bpy.context.scene.collection.children.link(scatter_coll)

    # Template collection for prop types (hidden, used for instancing)
    template_coll = _create_template_collection(f"{area_name}_templates")
    templates: dict[str, bpy.types.Object] = {}

    prop_counts: dict[str, int] = {}

    for p in placements:
        ptype = p["type"]
        prop_counts[ptype] = prop_counts.get(ptype, 0) + 1

        # Create template on first use via mesh bridge
        if ptype not in templates:
            templates[ptype] = _create_prop_template(ptype, template_coll)

        template = templates[ptype]
        instance = bpy.data.objects.new(
            f"{ptype}_{prop_counts[ptype]:04d}", template.data,
        )
        wz = terrain_sampler(p["position"][0], p["position"][1]) if terrain_sampler else 0.0
        instance.location = (p["position"][0], p["position"][1], wz)
        instance.rotation_euler = _prop_rotation(ptype, p["rotation"])
        s = p["scale"]
        instance.scale = (s, s, s)
        scatter_coll.objects.link(instance)

    return {
        "name": area_name,
        "prop_count": sum(prop_counts.values()),
        "prop_types": prop_counts,
    }


# ---------------------------------------------------------------------------
# Handler: create_breakable
# ---------------------------------------------------------------------------

def handle_create_breakable(params: dict) -> dict:
    """Create a breakable prop with intact and destroyed variants.

    Params:
        prop_type (str): One of barrel, crate, pot, fence, cart.
        position (list of 3 floats, default [0,0,0]): World position.
        seed (int, default 0): Random seed.

    Returns dict with: name, intact_vertex_count, fragment_count, debris_count.
    """
    prop_type = params.get("prop_type")
    if not prop_type:
        raise ValueError("'prop_type' is required")

    position = params.get("position", [0, 0, 0])
    seed = params.get("seed", 0)

    variants = generate_breakable_variants(prop_type, seed)
    intact_spec = variants["intact_spec"]
    destroyed_spec = variants["destroyed_spec"]

    # Create parent empty
    parent_name = f"{prop_type}_breakable"
    parent = bpy.data.objects.new(parent_name, None)
    parent.empty_display_type = "PLAIN_AXES"
    parent.location = tuple(position)
    bpy.context.collection.objects.link(parent)

    # Create intact version
    intact_bm = bmesh.new()
    for op in intact_spec["geometry_ops"]:
        if op["type"] == "cylinder":
            bmesh.ops.create_cone(
                intact_bm, cap_ends=True, cap_tris=True,
                segments=op.get("segments", 12),
                radius1=op["radius"], radius2=op["radius"],
                depth=op["height"],
            )
        elif op["type"] == "box":
            sx, sy, sz = op["size"]
            bmesh.ops.create_cube(intact_bm, size=1.0)
            for v in intact_bm.verts:
                v.co.x *= sx
                v.co.y *= sy
                v.co.z *= sz

    intact_mesh = bpy.data.meshes.new(f"{prop_type}_intact")
    intact_bm.to_mesh(intact_mesh)
    intact_vertex_count = len(intact_bm.verts)
    intact_bm.free()

    intact_obj = bpy.data.objects.new(f"{prop_type}_intact", intact_mesh)
    intact_obj.parent = parent
    bpy.context.collection.objects.link(intact_obj)

    # Apply intact material
    mat_intact = bpy.data.materials.new(name=f"mat_{prop_type}_intact")
    mat_intact.use_nodes = True
    intact_mesh.materials.append(mat_intact)

    # Create destroyed version collection
    destroyed_coll = bpy.data.collections.new(f"{prop_type}_destroyed")
    bpy.context.scene.collection.children.link(destroyed_coll)
    destroyed_coll.hide_viewport = True  # Hidden by default

    # Create fragments
    fragment_count = len(destroyed_spec["fragment_ops"])
    for i, frag in enumerate(destroyed_spec["fragment_ops"]):
        frag_bm = bmesh.new()
        sx, sy, sz = frag["size"]
        bmesh.ops.create_cube(frag_bm, size=1.0)
        for v in frag_bm.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z *= sz
        frag_mesh = bpy.data.meshes.new(f"{prop_type}_frag_{i}")
        frag_bm.to_mesh(frag_mesh)
        frag_bm.free()

        frag_obj = bpy.data.objects.new(f"{prop_type}_frag_{i}", frag_mesh)
        frag_obj.location = tuple(frag["position"])
        frag_obj.parent = parent
        destroyed_coll.objects.link(frag_obj)

    # Create debris
    debris_count = len(destroyed_spec["debris_ops"])
    for i, deb in enumerate(destroyed_spec["debris_ops"]):
        deb_bm = bmesh.new()
        sx, sy, sz = deb["size"]
        bmesh.ops.create_cube(deb_bm, size=1.0)
        for v in deb_bm.verts:
            v.co.x *= sx
            v.co.y *= sy
            v.co.z *= sz
        deb_mesh = bpy.data.meshes.new(f"{prop_type}_debris_{i}")
        deb_bm.to_mesh(deb_mesh)
        deb_bm.free()

        deb_obj = bpy.data.objects.new(f"{prop_type}_debris_{i}", deb_mesh)
        deb_obj.location = tuple(deb["position"])
        deb_obj.parent = parent
        destroyed_coll.objects.link(deb_obj)

    # Apply destroyed material
    mat_destroyed = bpy.data.materials.new(name=f"mat_{prop_type}_destroyed")
    mat_destroyed.use_nodes = True

    return {
        "name": parent_name,
        "intact_vertex_count": intact_vertex_count,
        "fragment_count": fragment_count,
        "debris_count": debris_count,
    }
