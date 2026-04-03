"""Environment handlers for terrain generation, biome painting, water, and export.

Provides 6 command handlers:
  - handle_generate_terrain: Heightmap -> bmesh grid terrain mesh
  - handle_paint_terrain: Slope/altitude biome rules -> material slot assignment
  - handle_carve_river: River channel carving along A* path
  - handle_generate_road: A-to-B road with proper grading
  - handle_create_water: Lake/ocean/pond plane with shoreline
  - handle_export_heightmap: 16-bit Unity RAW export
"""

from __future__ import annotations

import logging
import math
import struct
from pathlib import Path
from typing import Any

import numpy as np

import bpy
import bmesh

logger = logging.getLogger(__name__)

from ._terrain_noise import (
    generate_heightmap,
    compute_slope_map,
    compute_biome_assignments,
    carve_river_path,
    generate_road_path,
    TERRAIN_PRESETS,
    BIOME_RULES,
)
from ._terrain_erosion import (
    apply_hydraulic_erosion,
    apply_thermal_erosion,
)


# ---------------------------------------------------------------------------
# Validation helpers (pure logic -- testable without Blender)
# ---------------------------------------------------------------------------

_VALID_TERRAIN_TYPES = frozenset(TERRAIN_PRESETS.keys())
_VALID_EROSION_MODES = frozenset({"none", "hydraulic", "thermal", "both"})
_MAX_RESOLUTION = 4096  # 8192 can OOM Blender; 4096 is practical AAA limit


def _detect_grid_dims(bm) -> tuple[int, int]:
    """WORLD-004: Detect actual (rows, cols) of a terrain grid mesh.

    Counts unique rounded X and Y coordinate positions to infer actual
    grid width and height.  This is robust for non-square terrain meshes
    (e.g. 256×512) where ``int(math.sqrt(vert_count))`` would give wrong
    dimensions and cause reshape crashes.

    Falls back to sqrt-based square assumption only when coordinate
    detection produces an inconsistent vertex count.

    Returns:
        (rows, cols) tuple suitable for ``array.reshape(rows, cols)``.
    """
    xs = set(round(v.co.x, 3) for v in bm.verts)
    ys = set(round(v.co.y, 3) for v in bm.verts)
    cols, rows = len(xs), len(ys)
    if cols * rows == len(bm.verts):
        return rows, cols
    # Fallback: assume square
    side = max(2, int(math.sqrt(len(bm.verts))))
    return side, side


# ---------------------------------------------------------------------------
# VeilBreakers biome presets
# ---------------------------------------------------------------------------

VB_BIOME_PRESETS: dict[str, dict] = {
    "thornwood_forest": {
        "terrain_type": "hills",
        "resolution": 512,
        "height_scale": 15.0,
        "erosion": True,
        "erosion_iterations": 2000,
        "seed": None,  # random
        "scatter_rules": [
            {"asset": "tree_healthy", "density": 0.24, "min_distance": 4.5, "scale_range": [1.0, 1.9]},
            {"asset": "tree_boundary", "density": 0.14, "min_distance": 4.0, "scale_range": [0.9, 1.8]},
            {"asset": "tree_blighted", "density": 0.05, "min_distance": 5.5, "scale_range": [0.8, 1.4]},
            {"asset": "shrub", "density": 0.24, "min_distance": 2.0, "scale_range": [0.7, 1.2]},
            {"asset": "grass", "density": 0.35, "min_distance": 1.2, "scale_range": [0.6, 1.0]},
            {"asset": "rock_mossy", "density": 0.10, "min_distance": 3.0, "scale_range": [0.7, 1.3]},
            {"asset": "root", "density": 0.07, "min_distance": 2.6, "scale_range": [0.7, 1.1]},
            {"asset": "mushroom_cluster", "density": 0.05, "min_distance": 1.8, "scale_range": [0.45, 0.9]},
            {"asset": "fallen_log", "density": 0.02, "min_distance": 8.0, "scale_range": [0.8, 1.2]},
        ],
    },
    "corrupted_swamp": {
        "terrain_type": "flat",
        "resolution": 512,
        "height_scale": 5.0,
        "erosion": True,
        "erosion_iterations": 3000,
        "seed": None,
        "scatter_rules": [
            {"asset": "dead_tree", "density": 0.2, "min_distance": 4.0, "scale_range": [0.6, 1.0]},
            {"asset": "poison_pool", "density": 0.1, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
            {"asset": "vine_cluster", "density": 0.3, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "spore_pod", "density": 0.15, "min_distance": 3.0, "scale_range": [0.3, 0.8]},
        ],
    },
    "mountain_pass": {
        "terrain_type": "mountains",
        "resolution": 512,
        "height_scale": 40.0,
        "erosion": True,
        "erosion_iterations": 5000,
        "seed": None,
        "scatter_rules": [
            {"asset": "boulder", "density": 0.3, "min_distance": 3.0, "scale_range": [0.5, 2.5]},
            {"asset": "pine_tree", "density": 0.1, "min_distance": 5.0, "scale_range": [0.8, 1.2]},
            {"asset": "snow_patch", "density": 0.2, "min_distance": 4.0, "scale_range": [1.0, 3.0]},
        ],
    },
    "ruined_fortress": {
        "terrain_type": "hills",
        "resolution": 257,
        "height_scale": 12.0,
        "erosion": True,
        "erosion_iterations": 1500,
        "seed": None,
        "scatter_rules": [
            {"asset": "rubble_pile", "density": 0.35, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "broken_pillar", "density": 0.1, "min_distance": 5.0, "scale_range": [0.8, 1.5]},
            {"asset": "wall_fragment", "density": 0.15, "min_distance": 4.0, "scale_range": [0.6, 1.2]},
            {"asset": "dead_tree", "density": 0.08, "min_distance": 6.0, "scale_range": [0.8, 1.2]},
            {"asset": "iron_fence", "density": 0.05, "min_distance": 7.0, "scale_range": [1.0, 1.0]},
        ],
    },
    "abandoned_village": {
        "terrain_type": "plains",
        "resolution": 257,
        "height_scale": 6.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "collapsed_roof", "density": 0.15, "min_distance": 6.0, "scale_range": [0.8, 1.2]},
            {"asset": "broken_cart", "density": 0.08, "min_distance": 8.0, "scale_range": [0.8, 1.0]},
            {"asset": "barrel", "density": 0.2, "min_distance": 3.0, "scale_range": [0.6, 1.0]},
            {"asset": "crate", "density": 0.2, "min_distance": 3.0, "scale_range": [0.5, 0.9]},
            {"asset": "weed_patch", "density": 0.3, "min_distance": 2.0, "scale_range": [0.4, 1.0]},
        ],
    },
    "veil_crack_zone": {
        "terrain_type": "chaotic",
        "resolution": 257,
        "height_scale": 20.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "crystal_shard", "density": 0.3, "min_distance": 2.0, "scale_range": [0.3, 2.0]},
            {"asset": "void_tendril", "density": 0.1, "min_distance": 5.0, "scale_range": [0.5, 1.5]},
            {"asset": "floating_rock", "density": 0.15, "min_distance": 4.0, "scale_range": [0.5, 3.0]},
            {"asset": "corruption_pool", "density": 0.08, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
        ],
    },
    "underground_dungeon": {
        "terrain_type": "flat",
        "resolution": 257,
        "height_scale": 2.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "stalagmite", "density": 0.15, "min_distance": 3.0, "scale_range": [0.5, 1.5]},
            {"asset": "bone_pile", "density": 0.1, "min_distance": 4.0, "scale_range": [0.3, 0.8]},
            {"asset": "cobweb", "density": 0.2, "min_distance": 2.0, "scale_range": [0.5, 1.0]},
            {"asset": "torch_sconce", "density": 0.05, "min_distance": 8.0, "scale_range": [1.0, 1.0]},
        ],
    },
    "sacred_shrine": {
        "terrain_type": "plains",
        "resolution": 257,
        "height_scale": 4.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "stone_lantern", "density": 0.1, "min_distance": 5.0, "scale_range": [0.8, 1.2]},
            {"asset": "offering_bowl", "density": 0.08, "min_distance": 6.0, "scale_range": [0.6, 1.0]},
            {"asset": "prayer_flag", "density": 0.12, "min_distance": 4.0, "scale_range": [0.8, 1.0]},
            {"asset": "moss_patch", "density": 0.25, "min_distance": 2.0, "scale_range": [0.5, 1.5]},
            {"asset": "cherry_blossom", "density": 0.06, "min_distance": 7.0, "scale_range": [1.0, 1.8]},
        ],
    },
    "battlefield": {
        "terrain_type": "hills",
        "resolution": 257,
        "height_scale": 8.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "broken_weapon", "density": 0.3, "min_distance": 2.0, "scale_range": [0.5, 1.0]},
            {"asset": "shield_fragment", "density": 0.2, "min_distance": 2.5, "scale_range": [0.4, 0.8]},
            {"asset": "bone_pile", "density": 0.15, "min_distance": 3.0, "scale_range": [0.5, 1.2]},
            {"asset": "banner_torn", "density": 0.05, "min_distance": 8.0, "scale_range": [1.0, 1.5]},
            {"asset": "crater", "density": 0.08, "min_distance": 6.0, "scale_range": [1.0, 2.0]},
        ],
    },
    "cemetery": {
        "terrain_type": "flat",
        "resolution": 257,
        "height_scale": 3.0,
        "erosion": False,
        "erosion_iterations": 0,
        "seed": None,
        "scatter_rules": [
            {"asset": "gravestone", "density": 0.5, "min_distance": 2.0, "scale_range": [0.8, 1.2]},
            {"asset": "dead_tree", "density": 0.08, "min_distance": 8.0, "scale_range": [1.0, 2.0]},
            {"asset": "iron_fence", "density": 0.1, "min_distance": 3.0, "scale_range": [1.0, 1.0]},
            {"asset": "fog_emitter", "density": 0.05, "min_distance": 10.0, "scale_range": [1.0, 1.0]},
        ],
    },
}


def get_vb_biome_preset(biome_name: str) -> dict | None:
    """Return a copy of the VB biome preset for *biome_name*, or None.

    The returned dict contains terrain generation parameters (terrain_type,
    resolution, height_scale, erosion, erosion_iterations, seed) and
    scatter_rules for post-terrain vegetation/prop placement.

    Pure logic -- no bpy dependency.
    """
    preset = VB_BIOME_PRESETS.get(biome_name)
    if preset is None:
        return None
    # Return a deep-ish copy so callers can mutate without affecting the preset
    import copy
    return copy.deepcopy(preset)


def _validate_terrain_params(params: dict) -> dict:
    """Validate and normalize terrain generation parameters.

    Raises ValueError for invalid parameters. Returns normalized dict.
    Pure logic -- no bpy dependency.
    """
    resolution = params.get("resolution", 257)
    terrain_type = params.get("terrain_type", "mountains")
    erosion = params.get("erosion", "none")

    if resolution > _MAX_RESOLUTION:
        raise ValueError(
            f"Resolution {resolution} exceeds maximum {_MAX_RESOLUTION}. "
            f"Use resolution <= {_MAX_RESOLUTION} to avoid memory issues."
        )
    if resolution < 3:
        raise ValueError(
            f"Resolution {resolution} is too small. Minimum is 3."
        )

    if terrain_type not in _VALID_TERRAIN_TYPES:
        raise ValueError(
            f"Unknown terrain_type '{terrain_type}'. "
            f"Valid types: {sorted(_VALID_TERRAIN_TYPES)}"
        )

    if erosion not in _VALID_EROSION_MODES:
        raise ValueError(
            f"Unknown erosion mode '{erosion}'. "
            f"Valid modes: {sorted(_VALID_EROSION_MODES)}"
        )

    return {
        "name": params.get("name", "Terrain"),
        "resolution": resolution,
        "terrain_type": terrain_type,
        "scale": params.get("scale", 100.0),
        "height_scale": params.get("height_scale", 20.0),
        "seed": params.get("seed", 0),
        "octaves": params.get("octaves"),
        "persistence": params.get("persistence"),
        "lacunarity": params.get("lacunarity"),
        "erosion": erosion,
        "erosion_iterations": params.get("erosion_iterations", 5000),
    }


def _export_heightmap_raw(
    heightmap: np.ndarray,
    flip_vertical: bool = True,
) -> bytes:
    """Convert a heightmap to 16-bit little-endian RAW bytes.

    Pure logic -- no file I/O. Returns raw bytes suitable for writing
    to a .raw file for Unity Terrain import.

    Parameters
    ----------
    heightmap : np.ndarray
        2D array with values in [0, 1].
    flip_vertical : bool
        Flip rows for Unity coordinate system compatibility.

    Returns
    -------
    bytes
        16-bit unsigned little-endian binary data.
    """
    hmap = heightmap.astype(np.float64).copy()

    # Normalize to [0, 1]
    hmin, hmax = hmap.min(), hmap.max()
    if hmax - hmin > 1e-10:
        hmap = (hmap - hmin) / (hmax - hmin)
    else:
        hmap = np.zeros_like(hmap)

    if flip_vertical:
        hmap = np.flipud(hmap)

    # Convert to uint16 (0-65535)
    hmap_u16 = (hmap * 65535).astype(np.uint16)

    return hmap_u16.tobytes()


# ---------------------------------------------------------------------------
# Handler: generate_terrain
# ---------------------------------------------------------------------------

def handle_generate_terrain(params: dict) -> dict:
    """Generate a terrain mesh from noise heightmap with optional erosion.

    Params:
        name (str, default "Terrain"): Object name.
        resolution (int, default 257): Grid resolution (vertices per side).
        terrain_type (str, default "mountains"): One of 8 terrain presets,
            or a VeilBreakers biome name (e.g. "thornwood_forest").
            When a biome name is given, its preset parameters are applied
            as defaults, overrideable by explicit params.
        scale (float, default 100.0): Noise sampling scale.
        height_scale (float, default 20.0): Vertical scale multiplier.
        seed (int, default 0): Random seed.
        octaves, persistence, lacunarity: Override preset values.
        erosion (str, default "none"): none|hydraulic|thermal|both.
        erosion_iterations (int, default 5000): Erosion iteration count.

    Returns dict with: name, vertex_count, terrain_type, resolution,
        height_scale, erosion_applied, and optionally biome_preset
        and scatter_rules when a VB biome preset was used.
    """
    # Check if terrain_type is a VB biome preset name
    biome_preset = get_vb_biome_preset(params.get("terrain_type", ""))
    if biome_preset is not None:
        biome_name = params["terrain_type"]
        # Build effective params: preset defaults, overridden by explicit params
        effective = {}
        effective["terrain_type"] = biome_preset["terrain_type"]
        effective["resolution"] = biome_preset["resolution"]
        effective["height_scale"] = biome_preset["height_scale"]
        if biome_preset.get("erosion"):
            effective["erosion"] = "hydraulic"
            effective["erosion_iterations"] = biome_preset.get("erosion_iterations", 5000)
        else:
            effective["erosion"] = "none"
        # Explicit params override preset defaults (except terrain_type which
        # was the biome name -- we already resolved the real terrain_type).
        # Note: preset seed is intentionally NOT applied -- caller's seed
        # (or downstream default) always takes precedence.
        for key in ("name", "resolution", "height_scale", "scale", "seed",
                     "octaves", "persistence", "lacunarity", "erosion",
                     "erosion_iterations"):
            if key in params and key != "terrain_type":
                effective[key] = params[key]
        # Keep the original terrain_type param out so validation uses the
        # resolved terrain_type from the biome preset
        params = effective

    logger.info("Generating terrain (type=%s)", params.get("terrain_type", "mountains"))
    validated = _validate_terrain_params(params)

    name = validated["name"]
    resolution = validated["resolution"]
    terrain_type = validated["terrain_type"]
    scale = validated["scale"]
    height_scale = validated["height_scale"]
    seed = validated["seed"]
    erosion = validated["erosion"]
    erosion_iters = validated["erosion_iterations"]

    # Auto-scale erosion: minimum 150K droplets for AAA-quality river channels
    # and natural-looking drainage (Skyrim/Valhalla uses 150K+ for visible features)
    if erosion in ("hydraulic", "both") and erosion_iters < 150000:
        erosion_iters = max(150000, resolution * resolution // 2)

    # Domain warp params (organic terrain features)
    warp_strength = params.get("warp_strength", 0.4)  # default organic
    warp_scale = params.get("warp_scale", 0.5)

    # Generate heightmap
    heightmap = generate_heightmap(
        width=resolution,
        height=resolution,
        scale=scale,
        octaves=validated["octaves"],
        persistence=validated["persistence"],
        lacunarity=validated["lacunarity"],
        seed=seed,
        terrain_type=terrain_type,
        warp_strength=warp_strength,
        warp_scale=warp_scale,
    )

    # Apply erosion
    erosion_applied = False
    if erosion in ("hydraulic", "both"):
        heightmap = apply_hydraulic_erosion(
            heightmap, iterations=erosion_iters, seed=seed
        )
        erosion_applied = True
    if erosion in ("thermal", "both"):
        heightmap = apply_thermal_erosion(heightmap, iterations=max(erosion_iters // 50, 5))
        erosion_applied = True

    # Apply flatten zones for building foundations (MESH-05)
    flatten_zones = params.get("flatten_zones", None)
    if flatten_zones:
        from .terrain_advanced import flatten_multiple_zones
        heightmap = flatten_multiple_zones(heightmap, flatten_zones)

    # Compute moisture map from flow accumulation (for splatmap painting)
    moisture_map = None
    if erosion_applied:
        from .terrain_advanced import compute_flow_map
        flow_result = compute_flow_map(heightmap)
        flow_acc = np.asarray(flow_result["flow_accumulation"], dtype=np.float64)
        # Normalize flow accumulation to [0, 1] using log scale
        log_flow = np.log1p(flow_acc)
        fa_max = log_flow.max()
        if fa_max > 0:
            moisture_map = log_flow / fa_max
        else:
            moisture_map = np.zeros_like(heightmap)

    # Convert heightmap to Blender mesh
    terrain_size = scale
    rows, cols = heightmap.shape

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    bmesh.ops.create_grid(
        bm,
        x_segments=cols - 1,
        y_segments=rows - 1,
        size=terrain_size / 2.0,
        calc_uvs=True,
    )

    bm.verts.ensure_lookup_table()

    # Set vertex Z from heightmap using bilinear interpolation for smooth terrain
    for vert in bm.verts:
        u = (vert.co.x + terrain_size / 2.0) / terrain_size
        v = (vert.co.y + terrain_size / 2.0) / terrain_size
        # Continuous float coordinates in heightmap space
        col_f = u * (cols - 1)
        row_f = v * (rows - 1)
        # Bilinear interpolation corners
        c0 = max(0, min(int(col_f), cols - 2))
        r0 = max(0, min(int(row_f), rows - 2))
        c1 = c0 + 1
        r1 = r0 + 1
        # Fractional parts for interpolation weights
        cf = col_f - c0
        rf = row_f - r0
        # Bilinear blend of 4 surrounding heightmap samples
        h00 = float(heightmap[r0, c0])
        h10 = float(heightmap[r0, c1])
        h01 = float(heightmap[r1, c0])
        h11 = float(heightmap[r1, c1])
        h = (h00 * (1 - cf) * (1 - rf)
             + h10 * cf * (1 - rf)
             + h01 * (1 - cf) * rf
             + h11 * cf * rf)
        vert.co.z = h * height_scale

    bm.to_mesh(mesh)
    vertex_count = len(bm.verts)
    bm.free()
    if hasattr(mesh, "polygons"):
        for poly in mesh.polygons:
            poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    # Auto-generate cliff mesh overlays at steep edges (MESH-05)
    cliff_overlays_enabled = params.get("cliff_overlays", True)
    cliff_threshold = params.get("cliff_threshold_deg", 60.0)
    cliff_placements = []
    if cliff_overlays_enabled:
        from ._terrain_depth import detect_cliff_edges, generate_cliff_face_mesh
        cliff_placements = detect_cliff_edges(
            heightmap,
            slope_threshold_deg=cliff_threshold,
            min_cluster_size=4,
            terrain_size=terrain_size,
        )
        for i, cp in enumerate(cliff_placements):
            cliff_mesh_spec = generate_cliff_face_mesh(
                width=cp["width"],
                height=cp["height"],
                seed=seed + i + 1000,
            )
            # Create cliff mesh object in Blender
            cliff_mesh = bpy.data.meshes.new(f"{name}_Cliff_{i}")
            cliff_bm = bmesh.new()
            for vert_data in cliff_mesh_spec["vertices"]:
                cliff_bm.verts.new(vert_data)
            cliff_bm.verts.ensure_lookup_table()
            for face_data in cliff_mesh_spec["faces"]:
                try:
                    cliff_bm.faces.new(
                        [cliff_bm.verts[vi] for vi in face_data]
                    )
                except (ValueError, IndexError):
                    pass  # Skip degenerate faces
            cliff_bm.to_mesh(cliff_mesh)
            cliff_bm.free()

            cliff_obj = bpy.data.objects.new(f"{name}_Cliff_{i}", cliff_mesh)
            cliff_obj.location = (cp["position"][0], cp["position"][1],
                                  cp["position"][2] * height_scale)
            cliff_obj.rotation_euler = tuple(cp["rotation"])
            bpy.context.collection.objects.link(cliff_obj)
            # Parent cliff to terrain
            cliff_obj.parent = obj

    result = {
        "name": obj.name,
        "vertex_count": vertex_count,
        "terrain_type": terrain_type,
        "resolution": resolution,
        "height_scale": height_scale,
        "erosion_applied": erosion_applied,
        "cliff_overlays": len(cliff_placements),
        "flatten_zones_applied": len(flatten_zones) if flatten_zones else 0,
        "has_moisture_map": moisture_map is not None,
    }
    if biome_preset is not None:
        result["biome_preset"] = biome_name
        result["scatter_rules"] = biome_preset.get("scatter_rules", [])
    return result


# ---------------------------------------------------------------------------
# Handler: paint_terrain
# ---------------------------------------------------------------------------

def handle_paint_terrain(params: dict) -> dict:
    """Auto-paint terrain with biome materials based on slope/altitude rules.

    Params:
        name (str): Existing terrain object name.
        biome_rules (list of dict, optional): Biome rules with name, material,
            min_alt, max_alt, min_slope, max_slope. Defaults to BIOME_RULES.
        height_scale (float, default 20.0): Used to normalize altitude.

    Returns dict with: name, material_count, biome_rules_applied.
    """
    logger.info("Painting terrain biomes")
    name = params.get("name")
    if not name:
        raise ValueError("'name' is required")

    biome_rules = params.get("biome_rules") or BIOME_RULES
    height_scale = params.get("height_scale", 20.0)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")
    if obj.type != "MESH":
        raise ValueError(f"Object '{name}' is type '{obj.type}', expected 'MESH'")

    mesh = obj.data

    # Create material slots with proper Base Color from biome rules
    for rule in biome_rules:
        mat_name = rule.get("material", rule["name"])
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            # Apply base_color and roughness from rule if present
            if mat.node_tree:
                bsdf = mat.node_tree.nodes.get("Principled BSDF")
                if bsdf:
                    base_color = rule.get("base_color")
                    if base_color:
                        bc = list(base_color)
                        while len(bc) < 4:
                            bc.append(1.0)
                        bsdf.inputs["Base Color"].default_value = tuple(bc[:4])
                    roughness = rule.get("roughness")
                    if roughness is not None:
                        bsdf.inputs["Roughness"].default_value = roughness
        mesh.materials.append(mat)

    # Assign faces using bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    for face in bm.faces:
        center = face.calc_center_median()
        altitude = center.z / height_scale if height_scale > 0 else 0.0
        altitude = max(0.0, min(1.0, altitude))

        # Slope from face normal
        slope_rad = math.acos(max(-1.0, min(1.0, face.normal.z)))
        slope_deg = math.degrees(slope_rad)

        # First matching rule wins
        for idx, rule in enumerate(biome_rules):
            min_alt = rule.get("min_alt", 0.0)
            max_alt = rule.get("max_alt", 1.0)
            min_slope = rule.get("min_slope", 0.0)
            max_slope = rule.get("max_slope", 90.0)

            if (min_alt <= altitude <= max_alt
                    and min_slope <= slope_deg <= max_slope):
                face.material_index = idx
                break

    bm.to_mesh(mesh)
    bm.free()

    return {
        "name": obj.name,
        "material_count": len(mesh.materials),
        "biome_rules_applied": len(biome_rules),
    }


# ---------------------------------------------------------------------------
# Handler: carve_river
# ---------------------------------------------------------------------------

def handle_carve_river(params: dict) -> dict:
    """Carve a river channel on an existing terrain mesh.

    Params:
        terrain_name (str): Existing terrain object name.
        source (list of 2 ints): Start grid coordinate [row, col].
        destination (list of 2 ints): End grid coordinate [row, col].
        width (int, default 2): Channel width in cells.
        depth (float, default 0.05): Channel depth.
        seed (int, default 0): Random seed.

    Returns dict with: name, path_length, depth.
    """
    logger.info("Carving river on terrain")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    source = tuple(params.get("source", [0, 0]))
    destination = tuple(params.get("destination", [0, 0]))
    width = params.get("width", 2)
    depth = params.get("depth", 0.05)
    seed = params.get("seed", 0)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    # Extract heightmap from mesh vertex Z
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    # Extract heights
    heights = np.array([v.co.z for v in bm.verts])
    height_scale = heights.max() if heights.max() > 0 else 1.0
    heightmap = (heights / height_scale).reshape(rows, cols)

    # Carve river
    path, carved = carve_river_path(
        heightmap, source=source, dest=destination,
        width=width, depth=depth, seed=seed,
    )

    # Apply back to mesh
    carved_flat = carved.flatten()
    for i, vert in enumerate(bm.verts):
        if i < len(carved_flat):
            vert.co.z = float(carved_flat[i]) * height_scale

    bm.to_mesh(mesh)
    bm.free()

    return {
        "name": terrain_name,
        "path_length": len(path),
        "depth": depth,
    }


# ---------------------------------------------------------------------------
# Handler: generate_road
# ---------------------------------------------------------------------------

def handle_generate_road(params: dict) -> dict:
    """Generate a road between waypoints on terrain with grading.

    Params:
        terrain_name (str): Existing terrain object name.
        waypoints (list of [row, col]): Ordered waypoints.
        width (int, default 3): Road width in cells.
        grade_strength (float, default 0.8): Flattening intensity.
        seed (int, default 0): Random seed.

    Returns dict with: name, path_length, width.
    """
    logger.info("Generating road on terrain")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    waypoints = [tuple(wp) for wp in params.get("waypoints", [(0, 0), (0, 0)])]
    width = params.get("width", 3)
    grade_strength = params.get("grade_strength", 0.8)
    seed = params.get("seed", 0)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    heights = np.array([v.co.z for v in bm.verts])
    height_scale = heights.max() if heights.max() > 0 else 1.0
    heightmap = (heights / height_scale).reshape(rows, cols)

    # Convert width from meters to grid cells if it looks like meters
    terrain_scale = obj.dimensions.x if obj.dimensions.x > 0 else 100.0
    cell_size = terrain_scale / max(cols - 1, 1)
    if width > 10:  # likely specified in meters, not cells
        width = max(1, int(width / cell_size))

    path, graded = generate_road_path(
        heightmap, waypoints=waypoints,
        width=width, grade_strength=grade_strength, seed=seed,
    )

    graded_flat = graded.flatten()
    for i, vert in enumerate(bm.verts):
        if i < len(graded_flat):
            vert.co.z = float(graded_flat[i]) * height_scale

    bm.to_mesh(mesh)
    bm.free()

    # Generate visible road surface mesh with cobblestone material
    road_mesh_name = f"{terrain_name}_Road"
    terrain_obj = bpy.data.objects.get(terrain_name)
    terrain_size = terrain_obj.dimensions.x if terrain_obj else 100.0
    cell_size = terrain_size / max(cols - 1, 1)

    road_bm = bmesh.new()
    road_uv = road_bm.loops.layers.uv.new("UVMap")
    road_half_width = width * cell_size * 0.5

    # Build road mesh as series of connected quads along the path
    if len(path) >= 2:
        prev_left = prev_right = None
        for pi in range(len(path) - 1):
            r0, c0 = path[pi]
            r1, c1 = path[pi + 1]
            # Convert grid coords to world coords
            x0 = (c0 / max(cols - 1, 1)) * terrain_size - terrain_size / 2
            y0 = (r0 / max(rows - 1, 1)) * terrain_size - terrain_size / 2
            x1 = (c1 / max(cols - 1, 1)) * terrain_size - terrain_size / 2
            y1 = (r1 / max(rows - 1, 1)) * terrain_size - terrain_size / 2
            z0 = float(graded_flat[r0 * cols + c0]) * height_scale + 0.03
            z1 = float(graded_flat[r1 * cols + c1]) * height_scale + 0.03

            # Perpendicular direction for road width
            dx, dy = x1 - x0, y1 - y0
            length = max(math.sqrt(dx * dx + dy * dy), 0.01)
            nx, ny = -dy / length * road_half_width, dx / length * road_half_width

            v0 = road_bm.verts.new((x0 + nx, y0 + ny, z0))
            v1 = road_bm.verts.new((x0 - nx, y0 - ny, z0))
            v2 = road_bm.verts.new((x1 - nx, y1 - ny, z1))
            v3 = road_bm.verts.new((x1 + nx, y1 + ny, z1))

            if prev_left is not None and prev_right is not None:
                # Connect to previous segment for continuous road
                try:
                    road_bm.faces.new([prev_left, prev_right, v1, v0])
                except ValueError:
                    pass

            try:
                face = road_bm.faces.new([v0, v1, v2, v3])
                face.smooth = True
            except ValueError:
                pass
            prev_left = v3
            prev_right = v2

    # Remove doubles and recalc normals
    if road_bm.verts:
        bmesh.ops.remove_doubles(road_bm, verts=road_bm.verts[:], dist=0.01)
        bmesh.ops.recalc_face_normals(road_bm, faces=road_bm.faces[:])

    road_mesh_data = bpy.data.meshes.new(road_mesh_name)
    road_bm.to_mesh(road_mesh_data)
    road_bm.free()
    for poly in road_mesh_data.polygons:
        poly.use_smooth = True

    road_obj = bpy.data.objects.new(road_mesh_name, road_mesh_data)
    bpy.context.collection.objects.link(road_obj)

    # Apply cobblestone material
    from .procedural_materials import create_procedural_material
    try:
        road_mat = create_procedural_material(road_mesh_name, "cobblestone_floor")
        if road_mat:
            road_mesh_data.materials.append(road_mat)
    except Exception:
        # Fallback: basic grey stone material
        road_mat = bpy.data.materials.new(name="Road_Cobblestone")
        road_mat.use_nodes = True
        if road_mat.node_tree:
            bsdf = road_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bc = bsdf.inputs.get("Base Color")
                if bc:
                    bc.default_value = (0.25, 0.22, 0.18, 1.0)
                rgh = bsdf.inputs.get("Roughness")
                if rgh:
                    rgh.default_value = 0.85
        road_mesh_data.materials.append(road_mat)

    return {
        "name": terrain_name,
        "road_mesh_name": road_obj.name,
        "path_length": len(path),
        "width": width,
        "road_vertex_count": len(road_mesh_data.vertices),
    }


# ---------------------------------------------------------------------------
# Handler: create_water
# ---------------------------------------------------------------------------

def handle_create_water(params: dict) -> dict:
    """Create a water body -- spline-based surface mesh with AAA flow data.

    AAA upgrade (39-02): replaces flat disc placeholder with a spline-following
    mesh that encodes flow speed, direction, and foam as vertex colors.  A simple
    grid fallback is used when no path_points are provided.

    Params:
        name (str, default "Water"): Water object name.
        water_level (float, default 0.3): Water plane height (world Z).
        terrain_name (str, optional): Reference terrain for sizing.
        width (float, default 8.0): Cross-section width (river default 8m).
        depth (float, default 100.0): Along-flow length for grid mode.
        material_name (str, default "Water_Material"): Material name.
        path_points (list of [x,y,z], optional): Spline control points for the
            river/lake centre-line.  When provided the mesh follows the path.
        cross_sections (int, default 12): Subdivisions perpendicular to flow.

    Vertex color layer "flow_vc" RGBA convention:
        R = flow speed  (0=still, 1=fast; narrower channel = faster)
        G = flow dir X  (normalised, remapped to 0-1)
        B = flow dir Z  (normalised, remapped to 0-1)
        A = foam        (1.0 where depth<0.2m or speed>0.8, else 0.0)

    Returns dict with: name, water_level, area, tri_count, vertex_count,
                       has_flow_vertex_colors, has_shore_alpha.
    """
    logger.info("Creating water body (AAA spline mesh)")
    name = params.get("name", "Water")
    water_level = params.get("water_level", 0.3)
    terrain_name = params.get("terrain_name")
    width = float(params.get("width", 8.0))
    fallback_depth = float(params.get("depth", 100.0))
    material_name = params.get("material_name", "Water_Material")
    path_points_raw = params.get("path_points")
    cross_sections = max(8, min(16, int(params.get("cross_sections", 12))))

    # If terrain specified, use its Z for water level snapping
    if terrain_name:
        terrain_obj = bpy.data.objects.get(terrain_name)
        if terrain_obj is not None and path_points_raw is None:
            dims = terrain_obj.dimensions
            fallback_depth = max(dims.y, fallback_depth)
            width = max(dims.x * 0.08, width)  # 8% of terrain width for a river

    # -----------------------------------------------------------------------
    # Build spline path
    # -----------------------------------------------------------------------
    if path_points_raw and len(path_points_raw) >= 2:
        path = [tuple(float(v) for v in pt) for pt in path_points_raw]
    else:
        # Fallback: straight line along Y axis
        path = [
            (0.0, -fallback_depth / 2.0, water_level),
            (0.0,  fallback_depth / 2.0, water_level),
        ]

    # -----------------------------------------------------------------------
    # Build cross-section mesh following the spline
    # -----------------------------------------------------------------------
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()

    # Vertex color layer for flow data
    flow_layer = bm.loops.layers.float_color.new("flow_vc")

    half_w = width / 2.0
    num_segs = len(path) - 1

    # Estimate total path length for speed calculation
    total_length = 0.0
    for i in range(num_segs):
        p0 = path[i]
        p1 = path[i + 1]
        seg_len = math.sqrt(
            (p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2 + (p1[2] - p0[2]) ** 2
        )
        total_length += max(seg_len, 0.001)

    # Ring of vertices per path point
    rings: list[list] = []
    for pi, pt in enumerate(path):
        px, py, pz = pt

        # Tangent direction
        if pi == 0:
            nxt = path[1]
            tx = nxt[0] - px
            ty = nxt[1] - py
        elif pi == len(path) - 1:
            prv = path[-2]
            tx = px - prv[0]
            ty = py - prv[1]
        else:
            prv = path[pi - 1]
            nxt = path[pi + 1]
            tx = nxt[0] - prv[0]
            ty = nxt[1] - prv[1]

        tlen = math.sqrt(tx * tx + ty * ty) or 1.0
        tx /= tlen
        ty /= tlen

        # Perpendicular (cross-section direction)
        perp_x = -ty
        perp_y = tx

        # Normalised flow direction components (remapped 0-1)
        flow_dir_x = (tx + 1.0) * 0.5
        flow_dir_z = (ty + 1.0) * 0.5

        # Flow speed: terrain-aware based on channel slope
        if pi > 0:
            prev_pt = path[pi - 1]
            dz = abs(pz - prev_pt[2])
            dx_dist = math.sqrt((px - prev_pt[0]) ** 2 + (py - prev_pt[1]) ** 2)
            slope = dz / max(dx_dist, 0.1)
            flow_speed = min(1.0, 0.2 + slope * 3.0)
        else:
            flow_speed = 0.3

        ring_verts = []
        for ci in range(cross_sections + 1):
            t = ci / cross_sections  # 0 = left shore, 1 = right shore
            offset = (t - 0.5) * 2.0  # -1 to +1
            vx = px + perp_x * offset * half_w
            vy = py + perp_y * offset * half_w
            vz = pz

            # Shore depth proxy: 0 at edges, 1 at center
            shore_t = 1.0 - abs(offset)  # 0.0 at shore, 1.0 at centre

            v = bm.verts.new((vx, vy, vz))
            ring_verts.append((v, shore_t, flow_speed, flow_dir_x, flow_dir_z))
        rings.append(ring_verts)

    # Connect rings into quads
    for ri in range(len(rings) - 1):
        ring_a = rings[ri]
        ring_b = rings[ri + 1]
        for ci in range(cross_sections):
            va, sha, spa, fdxa, fdza = ring_a[ci]
            vb, shb, spb, fdxb, fdzb = ring_a[ci + 1]
            vc, shc, spc, fdxc, fdzc = ring_b[ci + 1]
            vd, shd, spd, fdxd, fdzd = ring_b[ci]
            try:
                face = bm.faces.new([va, vb, vc, vd])
                # Paint flow vertex colors per loop
                loop_data = [
                    (sha, spa, fdxa, fdza),
                    (shb, spb, fdxb, fdzb),
                    (shc, spc, fdxc, fdzc),
                    (shd, spd, fdxd, fdzd),
                ]
                for loop, (sh, sp, fdx, fdz) in zip(face.loops, loop_data):
                    # Foam: shallow shore (depth<0.2 proxy = shore_t<0.2) or fast flow
                    foam = 1.0 if (sh < 0.2 or sp > 0.8) else 0.0
                    loop[flow_layer] = (sp, fdx, fdz, foam)
            except ValueError:
                pass

    bm.to_mesh(mesh)
    tri_count = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
    # Count quads as 2 tris each for budget check
    total_tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0.0, 0.0, water_level)
    bpy.context.collection.objects.link(obj)

    # -----------------------------------------------------------------------
    # AAA water material: sRGB(40,60,50), roughness 0.05, alpha 0.6, IOR 1.33
    # -----------------------------------------------------------------------
    mat = bpy.data.materials.get(material_name)
    if mat is None:
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
        mat.use_backface_culling = False
        if hasattr(mat, "blend_method"):
            mat.blend_method = "BLEND"
        if mat.node_tree:
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            bsdf = nodes.get("Principled BSDF")
            if bsdf:
                # sRGB(40,60,50) -> linear: (40/255)^2.2, (60/255)^2.2, (50/255)^2.2
                base_color = bsdf.inputs.get("Base Color")
                if base_color:
                    base_color.default_value = (0.021, 0.046, 0.031, 1.0)
                rough = bsdf.inputs.get("Roughness")
                if rough:
                    rough.default_value = 0.05
                ior = bsdf.inputs.get("IOR")
                if ior:
                    ior.default_value = 1.333
                # Alpha 0.6
                alpha = bsdf.inputs.get("Alpha")
                if alpha:
                    alpha.default_value = 0.6
                # Transmission for underwater view
                trans = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
                if trans:
                    trans.default_value = 0.7
                # Specular highlights
                spec = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
                if spec:
                    spec.default_value = 0.8
                # Procedural wave normal
                try:
                    noise_tex = nodes.new("ShaderNodeTexNoise")
                    noise_tex.inputs["Scale"].default_value = 25.0
                    noise_tex.inputs["Detail"].default_value = 8.0
                    noise_tex.inputs["Roughness"].default_value = 0.6
                    bump_node = nodes.new("ShaderNodeBump")
                    bump_node.inputs["Strength"].default_value = 0.15
                    bump_node.inputs["Distance"].default_value = 0.02
                    links.new(noise_tex.outputs["Fac"], bump_node.inputs["Height"])
                    normal_input = bsdf.inputs.get("Normal")
                    if normal_input:
                        links.new(bump_node.outputs["Normal"], normal_input)
                except Exception:
                    pass

    mesh.materials.append(mat)

    area = total_length * width if total_length > 0 else width * fallback_depth

    return {
        "name": obj.name,
        "water_level": water_level,
        "area": area,
        "tri_count": total_tris,
        "vertex_count": len(mesh.vertices),
        "has_flow_vertex_colors": True,
        "has_shore_alpha": True,
        "cross_sections": cross_sections,
        "path_point_count": len(path),
    }


# ---------------------------------------------------------------------------
# Handler: export_heightmap
# ---------------------------------------------------------------------------

def handle_export_heightmap(params: dict) -> dict:
    """Export terrain heightmap as 16-bit little-endian RAW for Unity.

    Params:
        terrain_name (str): Terrain object name.
        filepath (str): Output file path (.raw).
        flip_vertical (bool, default True): Flip for Unity coordinate system.
        unity_compat (bool, default False): Resize to power-of-two+1.

    Returns dict with: filepath, width, height, bit_depth, byte_order.
    """
    logger.info("Exporting heightmap")
    terrain_name = params.get("terrain_name")
    if not terrain_name:
        raise ValueError("'terrain_name' is required")

    filepath = params.get("filepath")
    if not filepath:
        raise ValueError("'filepath' is required")

    flip_vertical = params.get("flip_vertical", True)
    unity_compat = params.get("unity_compat", False)

    obj = bpy.data.objects.get(terrain_name)
    if obj is None:
        raise ValueError(f"Object not found: {terrain_name}")

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # WORLD-004: Detect actual grid dimensions (robust to non-square terrain)
    rows, cols = _detect_grid_dims(bm)

    heights = np.array([v.co.z for v in bm.verts])
    bm.free()

    # Normalize heights to [0, 1]
    hmin, hmax = heights.min(), heights.max()
    if hmax - hmin > 1e-10:
        heightmap = (heights - hmin) / (hmax - hmin)
    else:
        heightmap = np.zeros_like(heights)

    heightmap = heightmap.reshape(rows, cols)

    # Unity compat: resize to nearest power-of-two + 1 (use cols as ref dimension)
    if unity_compat:
        target = _nearest_pot_plus_1(cols)
        if target != cols:
            # Simple nearest-neighbor resize
            x_indices = np.round(np.linspace(0, cols - 1, target)).astype(int)
            y_indices = np.round(np.linspace(0, rows - 1, target)).astype(int)
            heightmap = heightmap[np.ix_(y_indices, x_indices)]

    # Export
    raw_bytes = _export_heightmap_raw(heightmap, flip_vertical=flip_vertical)

    out_path = Path(filepath)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(raw_bytes)

    rows, cols = heightmap.shape

    return {
        "filepath": str(out_path),
        "width": cols,
        "height": rows,
        "bit_depth": 16,
        "byte_order": "little-endian",
    }


def _nearest_pot_plus_1(n: int) -> int:
    """Find nearest power-of-two + 1 >= n."""
    pot = 1
    while pot + 1 < n:
        pot *= 2
    return pot + 1


# ---------------------------------------------------------------------------
# Handler: generate_multi_biome_world
# ---------------------------------------------------------------------------

def handle_generate_multi_biome_world(params: dict) -> dict:
    """Generate a complete multi-biome world map in Blender.

    Orchestrates: WorldMapSpec -> terrain mesh -> biome vertex colors ->
    biome material -> vegetation scatter.  Requires bpy (runs inside Blender).

    Params:
        name (str): Base name for terrain object. Default "MultibiomeTerrain".
        width (int): Grid resolution. Default 256.
        height (int): Grid resolution. Default 256.
        world_size (float): Terrain size in meters. Default 512.0.
        height_scale (float): Vertical exaggeration. Default 80.0.
        biome_count (int): Number of Voronoi regions. Default 6.
        biomes (list[str]): Biome names. Default 6 VB presets.
        seed (int): Master seed. Default 42.
        corruption_level (float): Global corruption intensity 0-1. Default 0.3.
        building_plots (list[dict]): Pre-placed footprints for foundation flatten.
        erosion (str): "hydraulic"|"thermal"|"both"|"none". Default "hydraulic".
        erosion_iterations (int): Default 5000.
        scatter_vegetation (bool): Whether to scatter per-biome vegetation. Default True.
        min_veg_distance (float): Min spacing between vegetation instances. Default 4.0.
        max_veg_instances (int): Cap per biome. Default 2000.
        transition_width_m (float): Blend zone width in meters. Default 15.0.

    Returns dict with:
        name, biome_count, biome_names, corruption_level, corruption_zones,
        vegetation_count, flatten_zones_applied, vertex_count, world_size_m.
    """
    from ._biome_grammar import generate_world_map_spec
    from .terrain_materials import BIOME_PALETTES_V2

    # --- 1. Build world spec (pure logic, no bpy) ---
    name = params.get("name", "MultibiomeTerrain")
    seed = params.get("seed", 42)
    world_size = params.get("world_size", 512.0)
    width = params.get("width", 256)
    height = params.get("height", 256)
    biome_count = params.get("biome_count", 6)
    biomes = params.get("biomes")
    corruption_level = params.get("corruption_level", 0.3)
    building_plots = params.get("building_plots", [])
    scatter_veg = params.get("scatter_vegetation", True)

    spec = generate_world_map_spec(
        width=width,
        height=height,
        world_size=world_size,
        biome_count=biome_count,
        biomes=biomes,
        seed=seed,
        corruption_level=corruption_level,
        building_plots=building_plots,
        transition_width_m=params.get("transition_width_m", 15.0),
    )

    # --- 2. Generate base terrain mesh ---
    # Determine terrain type from dominant biome instead of hardcoding "mountain"
    dominant_biome = biomes[0] if biomes else (spec.biome_names[0] if spec.biome_names else "hills")
    biome_preset = get_vb_biome_preset(dominant_biome)
    base_terrain_type = biome_preset["terrain_type"] if biome_preset else "hills"
    terrain_params = {
        "name": name,
        "terrain_type": base_terrain_type,
        "resolution": width,
        "height_scale": params.get("height_scale", 80.0),
        "scale": world_size,
        "seed": seed,
        "erosion": params.get("erosion", "hydraulic"),
        "erosion_iterations": params.get("erosion_iterations", 5000),
        "flatten_zones": spec.flatten_zones,
    }
    terrain_result = handle_generate_terrain(terrain_params)

    obj = bpy.data.objects.get(name)
    if obj is None:
        raise RuntimeError(f"Terrain object '{name}' not found after generation")

    # --- 3. Assign biome vertex colors per-vertex ---
    vertex_colors = _compute_vertex_colors_for_biome_map(
        obj, spec, world_size
    )

    mesh = obj.data
    if mesh.color_attributes.get("BiomeColor"):
        mesh.color_attributes.remove(mesh.color_attributes["BiomeColor"])
    col_attr = mesh.color_attributes.new(
        name="BiomeColor", type="FLOAT_COLOR", domain="POINT"
    )
    for i, rgba in enumerate(vertex_colors):
        col_attr.data[i].color = rgba

    # --- 4. Apply biome material for primary biome ---
    # Primary biome = dominant biome at terrain center (simple heuristic)
    cx_cell = int(spec.biome_ids[height // 2, width // 2])
    primary_biome = spec.biome_names[cx_cell]
    if primary_biome in BIOME_PALETTES_V2:
        from .terrain_materials import handle_create_biome_terrain
        try:
            handle_create_biome_terrain({
                "name": name,
                "biome_name": primary_biome,
            })
        except Exception:
            pass  # Non-fatal: material assignment is best-effort

    # --- 5. Scatter vegetation per biome (if enabled) ---
    vegetation_total = 0
    if scatter_veg:
        from .vegetation_system import handle_scatter_biome_vegetation
        for biome_name in spec.biome_names:
            try:
                veg_result = handle_scatter_biome_vegetation({
                    "terrain_name": name,
                    "biome_name": biome_name,
                    "min_distance": params.get("min_veg_distance", 4.0),
                    "seed": seed + (hash(biome_name) & 0xFFFF),
                    "max_instances": params.get("max_veg_instances", 2000),
                    "season": "corrupted" if corruption_level > 0.5 else None,
                    "bake_wind_colors": True,
                    "water_level": 0.05,
                })
                vegetation_total += veg_result.get("instance_count", 0)
            except Exception:
                pass  # Biome may not have vegetation set -- skip silently

    # --- 6. Count corruption zones ---
    corruption_zones = int((spec.corruption_map > 0.3).sum())

    return {
        "name": name,
        "biome_count": biome_count,
        "biome_names": spec.biome_names,
        "corruption_level": corruption_level,
        "corruption_zones": corruption_zones,
        "vegetation_count": vegetation_total,
        "flatten_zones_applied": len(spec.flatten_zones),
        "vertex_count": terrain_result.get("vertex_count", 0),
        "world_size_m": world_size,
    }


def _compute_vertex_colors_for_biome_map(
    obj,            # Blender object
    spec,           # WorldMapSpec
    world_size: float,
) -> list:
    """Sample per-vertex biome color from WorldMapSpec corruption map + biome palette.

    Returns list of (R, G, B, A) tuples, one per vertex.
    """
    from .terrain_materials import apply_corruption_tint, BIOME_PALETTES, _get_material_def

    mesh = obj.data
    rows, cols = spec.biome_ids.shape

    result_colors = []
    for v in mesh.vertices:
        vx, vy = v.co.x, v.co.y

        # Map world position to biome grid cell
        nx = max(0, min(cols - 1, int((vx / world_size + 0.5) * cols)))
        ny = max(0, min(rows - 1, int((vy / world_size + 0.5) * rows)))
        biome_idx = int(spec.biome_ids[ny, nx])
        corruption = float(spec.corruption_map[ny, nx])

        # Base color from biome palette
        base_color = (0.15, 0.12, 0.10, 1.0)
        try:
            biome_name = spec.biome_names[biome_idx]
            palette = BIOME_PALETTES.get(biome_name, {})
            ground_mats = palette.get("ground", [])
            if ground_mats:
                mat_def = _get_material_def(ground_mats[0])
                if mat_def and "base_color" in mat_def:
                    base_color = tuple(mat_def["base_color"])
                    if len(base_color) == 3:
                        base_color = base_color + (1.0,)
        except Exception:
            pass

        tinted = apply_corruption_tint([base_color], corruption)
        result_colors.append(tinted[0])

    return result_colors
