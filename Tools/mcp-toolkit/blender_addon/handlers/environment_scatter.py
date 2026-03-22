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
from ._mesh_bridge import mesh_from_spec, VEGETATION_GENERATOR_MAP


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
    available. Falls back to simple primitives for unmapped types (e.g.
    grass stays as a flat plane -- billboard grass is standard for games).
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
        # Assign a basic material
        if hasattr(obj, "data") and obj.data is not None:
            mat = bpy.data.materials.new(name=f"mat_{veg_type}")
            mat.use_nodes = True
            obj.data.materials.append(mat)
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

    # Assign a basic material
    mat = bpy.data.materials.new(name=f"mat_{veg_type}")
    mat.use_nodes = True
    mesh.materials.append(mat)

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
        instance.rotation_euler = (0, 0, math.radians(p["rotation"]))
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

def handle_scatter_props(params: dict) -> dict:
    """Scatter context-aware props near buildings using collection instances.

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

    placements = context_scatter(buildings, area_size, prop_density, seed)

    # Create scatter collection
    scatter_coll = bpy.data.collections.new(area_name)
    bpy.context.scene.collection.children.link(scatter_coll)

    # Template collection for prop types
    template_coll = _create_template_collection(f"{area_name}_templates")
    templates: dict[str, bpy.types.Object] = {}

    prop_counts: dict[str, int] = {}

    for p in placements:
        ptype = p["type"]
        prop_counts[ptype] = prop_counts.get(ptype, 0) + 1

        # Create template on first use
        if ptype not in templates:
            tmesh = bpy.data.meshes.new(f"_template_{ptype}")
            tbm = bmesh.new()
            bmesh.ops.create_cube(tbm, size=0.5)
            tbm.to_mesh(tmesh)
            tbm.free()
            tobj = bpy.data.objects.new(f"_template_{ptype}", tmesh)
            template_coll.objects.link(tobj)
            templates[ptype] = tobj

        template = templates[ptype]
        instance = bpy.data.objects.new(
            f"{ptype}_{prop_counts[ptype]:04d}", template.data,
        )
        instance.location = (p["position"][0], p["position"][1], 0)
        instance.rotation_euler = (0, 0, math.radians(p["rotation"]))
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
