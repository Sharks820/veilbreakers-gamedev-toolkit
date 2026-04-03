"""Blender handlers for vegetation scatter, prop scatter, and breakable props.

Provides 3 command handlers:
  - handle_scatter_vegetation: Biome-aware tree/grass/rock scatter using
    collection instances for performance.
  - handle_scatter_props: Context-aware prop placement near tagged buildings.
  - handle_create_breakable: Generate intact + damaged variant pairs.

AAA upgrades (39-02):
  - Leaf card canopies (6-12 intersecting planes) replace UV sphere tree blobs
  - 6-biome grass card system with wind vertex colors
  - Multi-pass scatter: trees -> grass -> rocks with building exclusion
  - Combat clearing generator (15-40m diameter with tree rings + entry paths)
  - Rock power-law size distribution (70% small, 25% medium, 5% large)
"""

from __future__ import annotations

import math
import random
from typing import Any

import numpy as np

import bpy
import bmesh
from mathutils import Vector as _mathutils_Vector

from ._scatter_engine import (
    poisson_disk_sample,
    biome_filter_points,
    context_scatter,
    generate_breakable_variants,
)
from ._terrain_noise import compute_slope_map
from ._mesh_bridge import mesh_from_spec, VEGETATION_GENERATOR_MAP, PROP_GENERATOR_MAP
from .vegetation_lsystem import generate_billboard_impostor
from .lod_pipeline import generate_lod_chain


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

    # Detect actual grid dims by counting unique X and Y positions (handles non-square terrain)
    xs = set(round(v.co.x, 3) for v in bm.verts)
    ys = set(round(v.co.y, 3) for v in bm.verts)
    cols, rows = len(xs), len(ys)
    if cols * rows != vert_count or cols < 2 or rows < 2:
        # Fallback: assume square grid
        side = int(math.sqrt(vert_count))
        if side < 2 or side * side != vert_count:
            bm.free()
            return None
        rows, cols = side, side

    heights = np.array([v.co.z for v in bm.verts], dtype=np.float64)
    bm.free()
    height_max = heights.max() if heights.size and heights.max() > 0 else 1.0
    heightmap = (heights / height_max).reshape(rows, cols)
    dims = terrain_obj.dimensions
    terrain_size = max(dims.x, dims.y, 1.0)
    half_size = terrain_size / 2.0

    def _sample(world_x: float, world_y: float) -> float:
        u = (world_x + half_size) / terrain_size
        v = (world_y + half_size) / terrain_size
        ci = int(u * (cols - 1))
        ri = int(v * (rows - 1))
        ci = max(0, min(ci, cols - 1))
        ri = max(0, min(ri, rows - 1))
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
        # For L-system tree types, use lower iterations and ring segments
        # for scatter templates (these get instanced 1000s of times)
        if veg_type.startswith("tree") or veg_type == "pine_tree":
            scatter_kwargs.setdefault("iterations", 3)  # lower for scatter templates
            scatter_kwargs.setdefault("ring_segments", 4)  # lower LOD for instanced trees
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
# Billboard LOD wiring
# ---------------------------------------------------------------------------

_BILLBOARD_LOD_VERTEX_THRESHOLD = 200
"""Minimum vertex count for a tree template to receive a billboard LOD.

Templates below this threshold are too simple to benefit from impostor LODs
(e.g. placeholder low-poly trees used during early scatter passes).
"""

_TREE_VEG_TYPES = frozenset({"tree", "pine_tree", "dead_tree", "tree_twisted"})
"""Vegetation types that are trees and should receive billboard LOD setup."""


def _setup_billboard_lod(
    template_obj: "bpy.types.Object",
    veg_spec: "dict | None",
    veg_type: str,
    lod_near_dist: float = 30.0,
) -> bool:
    """Set up billboard LOD metadata on a tree template object.

    Calls ``generate_billboard_impostor`` to produce the billboard mesh spec,
    then stores the result as custom properties on *template_obj* so that
    downstream export steps (and Unity LOD group setup) can read them.

    This is the wiring between the vegetation scatter pipeline and the two
    existing pure-logic functions:
      - ``generate_billboard_impostor`` (vegetation_lsystem.py)
      - ``generate_lod_chain`` (lod_pipeline.py)

    Args:
        template_obj: The Blender template object for the tree.
        veg_spec: The MeshSpec dict returned by the generator (may be None for
            fallback primitives). Used to estimate tree dimensions and to supply
            vertices/faces to generate_lod_chain.
        veg_type: The vegetation type key (e.g. "tree", "pine_tree").
        lod_near_dist: Distance (metres) at which LOD switches from full mesh
            to billboard. Default 30 m.

    Returns:
        True if billboard LOD was wired up, False if the template was skipped
        (too few vertices or not a tree type).
    """
    if veg_type not in _TREE_VEG_TYPES:
        return False

    # Check vertex count on the template mesh
    mesh_data = getattr(template_obj, "data", None)
    if mesh_data is None or not hasattr(mesh_data, "vertices"):
        return False
    if len(mesh_data.vertices) < _BILLBOARD_LOD_VERTEX_THRESHOLD:
        return False

    # Estimate tree height/width from the bounding box of the template
    bb_min_z = min(v.co.z for v in mesh_data.vertices)
    bb_max_z = max(v.co.z for v in mesh_data.vertices)
    bb_min_x = min(v.co.x for v in mesh_data.vertices)
    bb_max_x = max(v.co.x for v in mesh_data.vertices)
    bb_min_y = min(v.co.y for v in mesh_data.vertices)
    bb_max_y = max(v.co.y for v in mesh_data.vertices)
    tree_height = max(bb_max_z - bb_min_z, 0.5)
    tree_width = max(
        bb_max_x - bb_min_x,
        bb_max_y - bb_min_y,
        0.5,
    )

    # Generate the billboard impostor mesh spec (pure-logic, no bpy)
    billboard_spec = generate_billboard_impostor({
        "object_name": template_obj.name,
        "height": tree_height,
        "width": tree_width,
        "impostor_type": "cross",
        "num_views": 8,
        "resolution": 256,
    })

    # Also generate the full LOD chain if we have vertex/face data from the
    # procedural generator spec (pure-logic bookkeeping only)
    if veg_spec is not None:
        raw_verts = veg_spec.get("vertices", [])
        raw_faces = veg_spec.get("faces", [])
        if raw_verts and raw_faces:
            generate_lod_chain(
                {"vertices": raw_verts, "faces": raw_faces},
                asset_type="vegetation",
            )
            # lod_chain is computed but not materialised into Blender objects
            # here — the export pipeline reads the custom properties below to
            # reconstruct the chain at export time.

    # Store LOD metadata as custom properties on the template object.
    # All scatter instances share the template's mesh data pointer; the custom
    # properties live on the Object (not the Mesh) so each instance inherits
    # them from the template at export time via the collection-instance lookup.
    template_obj["lod_billboard_enabled"] = 1
    template_obj["lod_0_dist_max"] = lod_near_dist          # full mesh: 0–30 m
    template_obj["lod_1_dist_min"] = lod_near_dist          # billboard: 30 m+
    template_obj["lod_billboard_type"] = billboard_spec["impostor_type"]
    template_obj["lod_billboard_vertex_count"] = billboard_spec["vertex_count"]
    template_obj["lod_billboard_face_count"] = billboard_spec["face_count"]
    template_obj["lod_billboard_atlas_res"] = billboard_spec["atlas_resolution"]
    template_obj["lod_billboard_tree_height"] = tree_height
    template_obj["lod_billboard_tree_width"] = tree_width

    return True


# ---------------------------------------------------------------------------
# AAA: Grass card biome specs
# ---------------------------------------------------------------------------

# sRGB -> linear: (v/255)^2.2
_GRASS_BIOME_SPECS: dict[str, dict[str, Any]] = {
    "prairie": {
        "height_min": 0.5,
        "height_max": 1.2,
        # sRGB(140,160,60) -> linear
        "color": (0.242, 0.349, 0.043, 1.0),
    },
    "forest": {
        "height_min": 0.1,
        "height_max": 0.3,
        # sRGB(50,80,30) -> linear
        "color": (0.031, 0.079, 0.013, 1.0),
    },
    "swamp": {
        "height_min": 0.8,
        "height_max": 2.0,
        # sRGB(100,120,50) -> linear
        "color": (0.118, 0.176, 0.031, 1.0),
    },
    "mountain": {
        "height_min": 0.05,
        "height_max": 0.15,
        # sRGB(90,100,70) -> linear
        "color": (0.089, 0.118, 0.058, 1.0),
    },
    "corrupted": {
        "height_min": 0.3,
        "height_max": 0.8,
        # sRGB(30,25,35) -> linear
        "color": (0.013, 0.010, 0.018, 1.0),
    },
    "dead": {
        "height_min": 0.2,
        "height_max": 0.5,
        # sRGB(120,90,40) -> linear
        "color": (0.196, 0.099, 0.021, 1.0),
    },
}

# Biome density factors for Pass 1 (tree/bush scatter)
_BIOME_DENSITY: dict[str, float] = {
    "dark_forest": 0.8,
    "corrupted_wasteland": 0.05,
    "swamp": 0.5,
    "mountain": 0.2,
    "grassy_plains": 0.65,
    "prairie": 0.65,
    "forest": 0.8,
    "dead": 0.3,
    "default": 0.5,
}


# ---------------------------------------------------------------------------
# AAA: Leaf card canopy helper
# ---------------------------------------------------------------------------

def _add_leaf_card_canopy(
    bm: "bmesh.types.BMesh",
    canopy_center: tuple[float, float, float],
    canopy_radius: float,
    num_planes: int,
    rng: random.Random,
) -> None:
    """Add 6-12 intersecting leaf card planes to a bmesh for a tree canopy.

    Planes are grouped as:
    - 3 vertical planes at 0, 60, 120 degree intervals
    - num_planes-3 angled planes at 30-45 degrees from vertical

    Each plane is sized to canopy_radius and given a small random offset
    (0-0.3m) for organic variety.

    Wind vertex colors are painted:
      R=flutter (1.0), G=random phase, B=amplitude gradient, A=0 (tips only)
    """
    cx, cy, cz = canopy_center
    r = canopy_radius

    # Ensure wind vertex color layer exists
    wind_layer = bm.verts.layers.float_color.get("wind_vc")
    if wind_layer is None:
        wind_layer = bm.verts.layers.float_color.new("wind_vc")

    planes_added = 0

    # 3 vertical planes at 60-degree intervals
    for i in range(3):
        angle = math.radians(i * 60.0)
        offset_x = rng.uniform(-0.3, 0.3)
        offset_y = rng.uniform(-0.3, 0.3)
        px = cx + offset_x
        py = cy + offset_y

        # Plane normal is horizontal (perpendicular to rotation angle)
        nx = math.sin(angle)
        ny = math.cos(angle)

        # 4 corners of the plane: half-width along tangent, half-height along Z
        tx = -ny
        ty = nx
        corners = [
            (px + tx * r,  py + ty * r,  cz - r * 0.5),
            (px - tx * r,  py - ty * r,  cz - r * 0.5),
            (px - tx * r,  py - ty * r,  cz + r * 0.8),
            (px + tx * r,  py + ty * r,  cz + r * 0.8),
        ]
        verts = [bm.verts.new(c) for c in corners]
        phase = rng.random()
        for vi, v in enumerate(verts):
            # Bottom verts: lower amplitude; top verts: full flutter
            height_t = vi // 2  # 0 for bottom row, 1 for top row
            v[wind_layer] = (
                float(height_t),   # R = flutter (1.0 at tips)
                phase,             # G = per-cluster phase
                height_t * 0.85,   # B = branch sway amplitude
                0.0,               # A = trunk sway (0 for leaf tips, used at trunk)
            )
        try:
            bm.faces.new(verts)
        except ValueError:
            pass
        planes_added += 1

    # Angled planes at 30-45 degrees from vertical
    remaining = num_planes - 3
    for i in range(remaining):
        angle = math.radians(i * (360.0 / max(remaining, 1)) + 15.0)
        tilt = math.radians(rng.uniform(30.0, 45.0))
        offset_x = rng.uniform(-0.25, 0.25)
        offset_y = rng.uniform(-0.25, 0.25)
        px = cx + offset_x
        py = cy + offset_y

        # Tangent direction for the plane width
        tx = math.cos(angle)
        ty = math.sin(angle)
        # Z contribution of tilt
        tz_scale = math.cos(tilt)
        plane_h = r * math.sin(tilt)

        corners = [
            (px + tx * r,  py + ty * r,  cz - plane_h * 0.4),
            (px - tx * r,  py - ty * r,  cz - plane_h * 0.4),
            (px - tx * r * tz_scale,  py - ty * r * tz_scale,  cz + plane_h * 0.8),
            (px + tx * r * tz_scale,  py + ty * r * tz_scale,  cz + plane_h * 0.8),
        ]
        verts = [bm.verts.new(c) for c in corners]
        phase = rng.random()
        for vi, v in enumerate(verts):
            height_t = vi // 2
            v[wind_layer] = (
                float(height_t),
                phase,
                height_t * 0.85,
                0.0,
            )
        try:
            bm.faces.new(verts)
        except ValueError:
            pass
        planes_added += 1


def create_leaf_card_tree(
    position: tuple[float, float, float],
    height: float = 5.0,
    canopy_radius: float = 2.5,
    num_planes: int = 8,
    seed: int = 42,
) -> "bpy.types.Object":
    """Create a tree with a leaf card canopy (SpeedTree-style).

    Replaces the UV sphere blob with 6-12 intersecting alpha planes.

    Returns the created Blender object.
    """
    rng = random.Random(seed)
    name = f"LeafCardTree_{seed}"

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Trunk: simple tapered cylinder approximated as extruded polygon
    trunk_radius = height * 0.06
    trunk_segments = 6
    trunk_verts_bottom = []
    trunk_verts_top = []
    for i in range(trunk_segments):
        angle = math.radians(i * 360.0 / trunk_segments)
        x = math.cos(angle) * trunk_radius
        y = math.sin(angle) * trunk_radius
        trunk_verts_bottom.append(bm.verts.new((position[0] + x, position[1] + y, position[2])))
        trunk_verts_top.append(bm.verts.new((
            position[0] + x * 0.7,
            position[1] + y * 0.7,
            position[2] + height * 0.55,
        )))

    # Trunk wind vertex colors: A=trunk_sway gradient
    # WORLD-006: guard against duplicate layer creation
    wind_layer = bm.verts.layers.float_color.get("wind_vc")
    if wind_layer is None:
        wind_layer = bm.verts.layers.float_color.new("wind_vc")
    for v in trunk_verts_bottom:
        v[wind_layer] = (0.0, 0.0, 0.0, 0.0)  # base: no sway
    for v in trunk_verts_top:
        v[wind_layer] = (0.0, 0.0, 0.2, 0.6)  # top of trunk: moderate sway

    # Create trunk faces
    for i in range(trunk_segments):
        j = (i + 1) % trunk_segments
        try:
            bm.faces.new([
                trunk_verts_bottom[i],
                trunk_verts_bottom[j],
                trunk_verts_top[j],
                trunk_verts_top[i],
            ])
        except ValueError:
            pass

    # Canopy: leaf card planes
    canopy_center = (
        position[0],
        position[1],
        position[2] + height * 0.65,
    )
    num_planes_clamped = max(6, min(12, num_planes))
    _add_leaf_card_canopy(bm, canopy_center, canopy_radius, num_planes_clamped, rng)

    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# AAA: Grass card system
# ---------------------------------------------------------------------------

def _create_grass_card(
    biome: str = "prairie",
    seed: int = 0,
    collection: "bpy.types.Collection | None" = None,
) -> "bpy.types.Object":
    """Create a single grass card mesh for the given biome.

    Geometry: 1-3 quads with a V-bend for depth illusion (3-6 tris per tuft).
    Wind vertex colors: R=1.0 at tips, G=random phase, B=0.5-1.0 gradient, A=0.

    Returns the created Blender object.
    """
    rng = random.Random(seed)
    spec = _GRASS_BIOME_SPECS.get(biome, _GRASS_BIOME_SPECS["prairie"])
    height = rng.uniform(spec["height_min"], spec["height_max"])
    color = spec["color"]

    name = f"GrassCard_{biome}_{seed}"
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # WORLD-006: guard against duplicate layer creation
    wind_layer = bm.verts.layers.float_color.get("wind_vc")
    if wind_layer is None:
        wind_layer = bm.verts.layers.float_color.new("wind_vc")
    phase = rng.random()

    # Main blade: 2 quads (V-bend at midpoint)
    # Bottom quad
    mid_z = height * 0.5
    bend_offset = height * 0.08  # slight forward bend at midpoint
    w = height * 0.18  # blade width proportional to height

    v0 = bm.verts.new((-w, 0.0, 0.0))
    v1 = bm.verts.new((w, 0.0, 0.0))
    v2 = bm.verts.new((w * 0.6, bend_offset, mid_z))
    v3 = bm.verts.new((-w * 0.6, bend_offset, mid_z))

    # Top quad (tapers to a point-ish tip)
    v4 = bm.verts.new((w * 0.15, bend_offset * 2, height))
    v5 = bm.verts.new((-w * 0.15, bend_offset * 2, height))

    # Wind colors: base=no flutter, mid=partial, tip=full
    v0[wind_layer] = (0.0, phase, 0.0, 0.0)
    v1[wind_layer] = (0.0, phase, 0.0, 0.0)
    v2[wind_layer] = (0.5, phase, 0.55, 0.0)
    v3[wind_layer] = (0.5, phase, 0.55, 0.0)
    v4[wind_layer] = (1.0, phase, 1.0, 0.0)
    v5[wind_layer] = (1.0, phase, 1.0, 0.0)

    try:
        bm.faces.new([v0, v1, v2, v3])
    except ValueError:
        pass
    try:
        bm.faces.new([v3, v2, v4, v5])
    except ValueError:
        pass

    # Optional: second crossing blade rotated 60 degrees for volume
    angle2 = math.radians(60.0)
    cos_a, sin_a = math.cos(angle2), math.sin(angle2)
    w2 = w * 0.85

    def rot(x: float, y: float) -> tuple[float, float]:
        return x * cos_a - y * sin_a, x * sin_a + y * cos_a

    rx0, ry0 = rot(-w2, 0.0)
    rx1, ry1 = rot(w2, 0.0)
    rx2, ry2 = rot(w2 * 0.6, bend_offset)
    rx3, ry3 = rot(-w2 * 0.6, bend_offset)
    rx4, ry4 = rot(w2 * 0.15, bend_offset * 2)
    rx5, ry5 = rot(-w2 * 0.15, bend_offset * 2)

    phase2 = rng.random()
    b0 = bm.verts.new((rx0, ry0, 0.0))
    b1 = bm.verts.new((rx1, ry1, 0.0))
    b2 = bm.verts.new((rx2, ry2, mid_z))
    b3 = bm.verts.new((rx3, ry3, mid_z))
    b4 = bm.verts.new((rx4, ry4, height))
    b5 = bm.verts.new((rx5, ry5, height))

    b0[wind_layer] = (0.0, phase2, 0.0, 0.0)
    b1[wind_layer] = (0.0, phase2, 0.0, 0.0)
    b2[wind_layer] = (0.5, phase2, 0.55, 0.0)
    b3[wind_layer] = (0.5, phase2, 0.55, 0.0)
    b4[wind_layer] = (1.0, phase2, 1.0, 0.0)
    b5[wind_layer] = (1.0, phase2, 1.0, 0.0)

    try:
        bm.faces.new([b0, b1, b2, b3])
    except ValueError:
        pass
    try:
        bm.faces.new([b3, b2, b4, b5])
    except ValueError:
        pass

    bm.to_mesh(mesh)
    bm.free()

    # Material
    mat_name = f"mat_grass_{biome}"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        if mat.node_tree:
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = color
                if "Roughness" in bsdf.inputs:
                    bsdf.inputs["Roughness"].default_value = 0.88
    mesh.materials.append(mat)

    obj = bpy.data.objects.new(name, mesh)
    if collection is not None:
        collection.objects.link(obj)
    else:
        bpy.context.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# AAA: Rock power-law distribution
# ---------------------------------------------------------------------------

def _rock_size_from_power_law(rng: random.Random) -> tuple[float, str]:
    """Sample a rock size using power-law distribution.

    Returns (scale, size_class) where size_class is 'small', 'medium', 'large'.
    Distribution: 70% small (0.1-0.3m), 25% medium (0.3-1.0m), 5% large (1.0-3.0m).
    """
    roll = rng.random()
    if roll < 0.70:
        return rng.uniform(0.1, 0.3), "small"
    elif roll < 0.95:
        return rng.uniform(0.3, 1.0), "medium"
    else:
        return rng.uniform(1.0, 3.0), "large"


# ---------------------------------------------------------------------------
# AAA: Combat clearing generator
# ---------------------------------------------------------------------------

def _generate_combat_clearing(
    center: tuple[float, float, float],
    diameter: float,
    num_entries: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate a combat clearing: circular area 15-40m diameter.

    Creates a tree ring around the perimeter with num_entries gaps for paths.

    Parameters
    ----------
    center : (x, y, z)
        World position of clearing center.
    diameter : float
        Diameter in meters, clamped to [15, 40].
    num_entries : int
        Number of entry path gaps in the tree ring, clamped to [2, 4].
    seed : int
        Random seed.

    Returns
    -------
    dict with keys: center, radius, entry_points, tree_positions,
                    tree_count, cleared_area_m2
    """
    diameter = max(15.0, min(40.0, diameter))
    radius = diameter / 2.0
    num_entries = max(2, min(4, num_entries))
    rng = random.Random(seed)
    cx, cy, cz = center

    # Entry path angles: evenly spaced with slight random offset
    base_angle_step = 360.0 / num_entries
    entry_angles = [
        math.radians(i * base_angle_step + rng.uniform(-10.0, 10.0))
        for i in range(num_entries)
    ]

    # Tree ring: trees at 3-5m spacing around circumference
    tree_spacing = rng.uniform(3.0, 5.0)
    circumference = 2.0 * math.pi * radius
    num_trees_full = int(circumference / tree_spacing)
    entry_gap_half_angle = math.asin(min(1.0, 2.0 / radius))  # ~2m half-gap

    tree_positions = []
    for i in range(num_trees_full):
        angle = 2.0 * math.pi * i / num_trees_full
        # Check if this angle is within an entry gap
        in_gap = False
        for ea in entry_angles:
            diff = abs(angle - ea)
            diff = min(diff, 2.0 * math.pi - diff)
            if diff < entry_gap_half_angle:
                in_gap = True
                break
        if not in_gap:
            jitter_r = radius + rng.uniform(-0.5, 0.5)
            tx = cx + math.cos(angle) * jitter_r
            ty = cy + math.sin(angle) * jitter_r
            tree_positions.append((tx, ty, cz))

    # Entry path endpoints (outside the ring, 2m beyond edge)
    entry_points = []
    for ea in entry_angles:
        ex = cx + math.cos(ea) * (radius + 2.0)
        ey = cy + math.sin(ea) * (radius + 2.0)
        entry_points.append((ex, ey, cz))

    cleared_area = math.pi * radius * radius

    return {
        "center": center,
        "radius": radius,
        "entry_points": entry_points,
        "tree_positions": tree_positions,
        "tree_count": len(tree_positions),
        "cleared_area_m2": cleared_area,
    }


# ---------------------------------------------------------------------------
# AAA: Multi-pass scatter internal helper
# ---------------------------------------------------------------------------

def _scatter_pass(
    heightmap: np.ndarray,
    slope_map: np.ndarray,
    terrain_size: float,
    pass_type: str,
    biome: str = "default",
    seed: int = 0,
    building_zones: "list[tuple[float, float, float, float]] | None" = None,
    tree_positions: "list[tuple[float, float]] | None" = None,
    combat_clearings: "list[dict] | None" = None,
) -> list[dict[str, Any]]:
    """Execute a single scatter pass (structure, ground_cover, or debris).

    Parameters
    ----------
    heightmap : np.ndarray
        Normalized 2D heightmap [0,1].
    slope_map : np.ndarray
        Slope in degrees.
    terrain_size : float
        World-space terrain size in meters.
    pass_type : str
        One of "structure" (trees/bushes), "ground_cover" (grass/flowers),
        "debris" (rocks/sticks).
    biome : str
        Biome key for density lookup.
    seed : int
        Random seed.
    building_zones : list of (min_x, min_y, max_x, max_y)
        Axis-aligned bounding boxes to exclude.
    tree_positions : list of (x, y)
        Already-placed tree positions to avoid within 1m (for grass pass).
    combat_clearings : list of clearing dicts
        Reserved clearing areas.

    Returns
    -------
    list of placement dicts with keys: position, vegetation_type, rotation, scale.
    """
    rng = random.Random(seed)
    density_factor = _BIOME_DENSITY.get(biome, 0.5)
    side = heightmap.shape[0]
    terrain_half = terrain_size / 2.0

    placements: list[dict[str, Any]] = []

    if pass_type == "structure":
        # Poisson disk: large trees (4-8m min distance), bushes (2-4m)
        tree_candidates = poisson_disk_sample(terrain_size, terrain_size, 5.0, seed=seed)
        bush_candidates = poisson_disk_sample(terrain_size, terrain_size, 2.5, seed=seed + 1)

        def _sample_height_norm(pos: tuple[float, float]) -> float:
            u = pos[0] / terrain_size
            v = pos[1] / terrain_size
            ci = int(u * (side - 1))
            ri = int(v * (side - 1))
            ci = max(0, min(ci, side - 1))
            ri = max(0, min(ri, side - 1))
            return float(heightmap[ri, ci])

        def _sample_slope(pos: tuple[float, float]) -> float:
            u = pos[0] / terrain_size
            v = pos[1] / terrain_size
            ci = int(u * (side - 1))
            ri = int(v * (side - 1))
            ci = max(0, min(ci, side - 1))
            ri = max(0, min(ri, side - 1))
            return float(slope_map[ri, ci])

        def _in_building(wx: float, wy: float) -> bool:
            if not building_zones:
                return False
            for bz in building_zones:
                if bz[0] <= wx <= bz[2] and bz[1] <= wy <= bz[3]:
                    return True
            return False

        def _in_clearing(wx: float, wy: float) -> bool:
            if not combat_clearings:
                return False
            for cl in combat_clearings:
                cx, cy = cl["center"][0], cl["center"][1]
                if math.sqrt((wx - cx) ** 2 + (wy - cy) ** 2) < cl["radius"]:
                    return True
            return False

        for pos in tree_candidates:
            wx = pos[0] - terrain_half
            wy = pos[1] - terrain_half
            h = _sample_height_norm(pos)
            sl = _sample_slope(pos)
            if sl > 30.0 or h < 0.1 or h > 0.7:
                continue
            if _in_building(wx, wy) or _in_clearing(wx, wy):
                continue
            if rng.random() > density_factor:
                continue
            scale = rng.uniform(0.8, 1.5)
            placements.append({
                "position": (wx, wy),
                "vegetation_type": "tree",
                "rotation": rng.uniform(0, 360),
                "scale": scale,
                "gpu_instance": True,
            })

        for pos in bush_candidates:
            wx = pos[0] - terrain_half
            wy = pos[1] - terrain_half
            h = _sample_height_norm(pos)
            sl = _sample_slope(pos)
            if sl > 35.0 or h < 0.05 or h > 0.55:
                continue
            if _in_building(wx, wy) or _in_clearing(wx, wy):
                continue
            if rng.random() > density_factor * 1.1:
                continue
            placements.append({
                "position": (wx, wy),
                "vegetation_type": "bush",
                "rotation": rng.uniform(0, 360),
                "scale": rng.uniform(0.5, 1.0),
                "gpu_instance": True,
            })

    elif pass_type == "ground_cover":
        # Grass cards at 8-16 tufts/m2 -- sample a subset of the terrain
        # (not per-m2 literally -- too many instances; use Poisson at 0.8m min dist)
        grass_candidates = poisson_disk_sample(
            terrain_size, terrain_size, 0.9, seed=seed + 2,
        )
        biome_grass = biome if biome in _GRASS_BIOME_SPECS else "prairie"

        def _near_tree(wx: float, wy: float) -> bool:
            if not tree_positions:
                return False
            for tx, ty in tree_positions:
                if math.sqrt((wx - tx) ** 2 + (wy - ty) ** 2) < 1.0:
                    return True
            return False

        for pos in grass_candidates:
            wx = pos[0] - terrain_half
            wy = pos[1] - terrain_half
            u = pos[0] / terrain_size
            v = pos[1] / terrain_size
            ci = int(u * (side - 1))
            ri = int(v * (side - 1))
            ci = max(0, min(ci, side - 1))
            ri = max(0, min(ri, side - 1))
            sl = float(slope_map[ri, ci])
            if sl > 40.0:
                continue
            if building_zones:
                in_bz = False
                for bz in building_zones:
                    if bz[0] <= wx <= bz[2] and bz[1] <= wy <= bz[3]:
                        in_bz = True
                        break
                if in_bz:
                    continue
            if _near_tree(wx, wy):
                continue
            if rng.random() > density_factor:
                continue
            placements.append({
                "position": (wx, wy),
                "vegetation_type": f"grass_{biome_grass}",
                "rotation": rng.uniform(0, 360),
                "scale": 1.0,
                "biome": biome_grass,
                "gpu_instance": True,
            })

    elif pass_type == "debris":
        # Rocks with power-law size distribution
        rock_candidates = poisson_disk_sample(
            terrain_size, terrain_size, 1.2, seed=seed + 3,
        )
        for pos in rock_candidates:
            wx = pos[0] - terrain_half
            wy = pos[1] - terrain_half
            if building_zones:
                in_bz = False
                for bz in building_zones:
                    if bz[0] <= wx <= bz[2] and bz[1] <= wy <= bz[3]:
                        in_bz = True
                        break
                if in_bz:
                    continue
            if rng.random() > 0.6:
                continue
            scale, size_class = _rock_size_from_power_law(rng)
            placements.append({
                "position": (wx, wy),
                "vegetation_type": "rock",
                "rotation": rng.uniform(0, 360),
                "scale": scale,
                "size_class": size_class,
                "gpu_instance": True,
            })

    return placements


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

    # Filter out placements that overlap with building footprints or roads
    # Collect bounding boxes of all EMPTY-type objects (building parents) in scene
    _exclusion_zones: list[tuple[float, float, float, float]] = []
    for _obj in bpy.data.objects:
        if _obj.type == "EMPTY" and _obj.children:
            # ARCH-025: Estimate building footprint from actual mesh bounding box,
            # then add a proportional clearance margin (half the diagonal, min 1.5m).
            _min_x = _min_y = float("inf")
            _max_x = _max_y = float("-inf")
            for _child in _obj.children:
                if _child.type == "MESH":
                    _bb_corners = [_child.matrix_world @ _mathutils_Vector(c) for c in _child.bound_box]
                    for _c in _bb_corners:
                        _min_x = min(_min_x, _c.x)
                        _max_x = max(_max_x, _c.x)
                        _min_y = min(_min_y, _c.y)
                        _max_y = max(_max_y, _c.y)
            if _min_x < float("inf"):
                # Proportional margin: half the footprint diagonal, clamped 1.5–6.0m
                _fp_w = max(_max_x - _min_x, 0.1)
                _fp_d = max(_max_y - _min_y, 0.1)
                _margin = max(1.5, min(6.0, ((_fp_w ** 2 + _fp_d ** 2) ** 0.5) * 0.25))
                _exclusion_zones.append((
                    _min_x - _margin, _min_y - _margin,
                    _max_x + _margin, _max_y + _margin,
                ))

        # Also exclude road objects (with a buffer margin for natural clearance)
        if _obj.type == "MESH" and ("road" in _obj.name.lower() or "_Road_" in _obj.name):
            _bb = [_obj.matrix_world @ _mathutils_Vector(corner) for corner in _obj.bound_box]
            _road_margin = 2.0  # meters buffer around road edges
            _r_min_x = min(v.x for v in _bb) - _road_margin
            _r_max_x = max(v.x for v in _bb) + _road_margin
            _r_min_y = min(v.y for v in _bb) - _road_margin
            _r_max_y = max(v.y for v in _bb) + _road_margin
            _exclusion_zones.append((_r_min_x, _r_min_y, _r_max_x, _r_max_y))

    if _exclusion_zones:
        terrain_half_bz = terrain_size / 2.0
        _filtered = []
        for p in placements:
            wx = p["position"][0] - terrain_half_bz
            wy = p["position"][1] - terrain_half_bz
            _in_excluded = False
            for bz_min_x, bz_min_y, bz_max_x, bz_max_y in _exclusion_zones:
                if bz_min_x <= wx <= bz_max_x and bz_min_y <= wy <= bz_max_y:
                    _in_excluded = True
                    break
            if not _in_excluded:
                _filtered.append(p)
        placements = _filtered

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

    # Wire billboard LOD for tree templates that have sufficient geometry.
    # Each template is created once and shared across all its instances; we
    # annotate the template object with custom properties so that the export
    # pipeline can set up a 2-level LOD group (LOD0: full mesh 0-30 m,
    # LOD1: billboard impostor 30 m+) without needing per-instance data.
    for vt, tmpl_obj in templates.items():
        # The generator spec is not re-fetched here; pass None so
        # _setup_billboard_lod falls back to bounding-box estimation.
        # Vertex-count guard inside the helper keeps low-poly types out.
        _setup_billboard_lod(tmpl_obj, veg_spec=None, veg_type=vt)

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

        # Sample terrain height at this position with bilinear interpolation
        u = p["position"][0] / terrain_size
        v = p["position"][1] / terrain_size
        col_f = u * (side - 1)
        row_f = v * (side - 1)
        c0 = max(0, min(int(col_f), side - 2))
        r0 = max(0, min(int(row_f), side - 2))
        c1, r1 = c0 + 1, r0 + 1
        cf, rf = col_f - c0, row_f - r0
        h00 = float(heightmap[r0, c0])
        h10 = float(heightmap[r0, c1])
        h01 = float(heightmap[r1, c0])
        h11 = float(heightmap[r1, c1])
        wz = (h00 * (1 - cf) * (1 - rf) + h10 * cf * (1 - rf)
              + h01 * (1 - cf) * rf + h11 * cf * rf) * height_max

        instance.location = (wx, wy, wz)

        # Align vegetation to terrain normal (slope-perpendicular placement)
        # Compute terrain normal from finite differences of heightmap
        cell_size = terrain_size / max(side - 1, 1)
        dzdx = (h10 - h00) * height_max / max(cell_size, 0.01)
        dzdy = (h01 - h00) * height_max / max(cell_size, 0.01)
        slope_pitch = math.atan2(-dzdy, 1.0)  # tilt around X
        slope_roll = math.atan2(dzdx, 1.0)   # tilt around Y
        base_rot = _vegetation_rotation(vt, p["rotation"])
        instance.rotation_euler = (
            base_rot[0] + slope_pitch * 0.7,  # partial alignment (70%) for natural look
            base_rot[1] + slope_roll * 0.7,
            base_rot[2],
        )
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
        if prop_type in ("dead_tree", "tree_twisted"):
            scatter_kwargs.setdefault("iterations", 3)  # lower for scatter
            scatter_kwargs.setdefault("ring_segments", 4)  # lower LOD
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

    # Apply intact material with proper color from scatter presets
    mat_intact = bpy.data.materials.new(name=f"mat_{prop_type}_intact")
    mat_intact.use_nodes = True
    if mat_intact.node_tree:
        _bsdf = mat_intact.node_tree.nodes.get("Principled BSDF")
        if _bsdf:
            _preset = _SCATTER_MATERIAL_PRESETS.get(prop_type, {})
            _bc = _preset.get("base_color", (0.15, 0.13, 0.11, 1.0))
            _bsdf.inputs["Base Color"].default_value = tuple(list(_bc)[:4])
            _bsdf.inputs["Roughness"].default_value = float(_preset.get("roughness", 0.8))
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

    # Apply destroyed material with darker, damaged color
    mat_destroyed = bpy.data.materials.new(name=f"mat_{prop_type}_destroyed")
    mat_destroyed.use_nodes = True
    if mat_destroyed.node_tree:
        _bsdf_d = mat_destroyed.node_tree.nodes.get("Principled BSDF")
        if _bsdf_d:
            _preset_d = _SCATTER_MATERIAL_PRESETS.get(prop_type, {})
            _bc_d = _preset_d.get("base_color", (0.15, 0.13, 0.11, 1.0))
            # Destroyed: shift toward charred brown-gray, not just pitch black.
            # Mix 70% original + 30% char color sRGB(60,50,40)->linear
            _bsdf_d.inputs["Base Color"].default_value = (
                _bc_d[0] * 0.7 + 0.046 * 0.3,
                _bc_d[1] * 0.7 + 0.030 * 0.3,
                _bc_d[2] * 0.7 + 0.021 * 0.3,
                1.0,
            )
            _bsdf_d.inputs["Roughness"].default_value = min(
                float(_preset_d.get("roughness", 0.8)) + 0.15, 1.0,
            )

    return {
        "name": parent_name,
        "intact_vertex_count": intact_vertex_count,
        "fragment_count": fragment_count,
        "debris_count": debris_count,
    }
