"""MeshSpec-to-Blender bridge and generator mapping tables.

Provides the wiring layer between procedural mesh generators (pure-logic)
and Blender scene handlers (worldbuilding, environment, etc.).

Section 1: Pure-logic (no bpy imports) -- mapping tables, LOD helper, resolver.
Section 2: Blender-dependent (guarded import) -- mesh_from_spec converter.

All mapping tables map item-type strings to (generator_function, kwargs_override)
tuples. Calling ``gen_func(**kwargs)`` produces a valid MeshSpec dict.
"""

from __future__ import annotations

import math
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Import all generators from procedural_meshes
# ---------------------------------------------------------------------------
from .procedural_meshes import (
    # Furniture
    generate_bed_mesh,
    generate_table_mesh,
    generate_chair_mesh,
    generate_shelf_mesh,
    generate_chest_mesh,
    generate_barrel_mesh,
    generate_candelabra_mesh,
    generate_bookshelf_mesh,
    generate_wardrobe_mesh,
    generate_cabinet_mesh,
    generate_fireplace_mesh,
    generate_map_scroll_mesh,
    generate_holy_symbol_mesh,
    # Vegetation
    generate_tree_mesh,
    generate_rock_mesh,
    generate_mushroom_mesh,
    generate_root_mesh,
    generate_grass_clump_mesh,
    generate_shrub_mesh,
    # Dungeon props
    generate_torch_sconce_mesh,
    generate_prison_door_mesh,
    generate_sarcophagus_mesh,
    generate_altar_mesh,
    generate_pillar_mesh,
    generate_archway_mesh,
    generate_chain_mesh,
    generate_skull_pile_mesh,
    # Traps
    generate_spike_trap_mesh,
    generate_bear_trap_mesh,
    generate_pressure_plate_mesh,
    generate_dart_launcher_mesh,
    generate_swinging_blade_mesh,
    generate_falling_cage_mesh,
    # Architecture
    generate_gate_mesh,
    generate_fountain_mesh,
    generate_staircase_mesh,
    # Structural
    generate_rampart_mesh,
    generate_drawbridge_mesh,
    # Containers
    generate_crate_mesh,
    generate_sack_mesh,
    generate_basket_mesh,
    # Light sources
    generate_brazier_mesh,
    generate_lantern_mesh,
    generate_campfire_mesh,
    # Camps / lookout / barriers
    generate_tent_mesh,
    generate_lookout_post_mesh,
    generate_spike_fence_mesh,
    generate_hitching_post_mesh,
    generate_barricade_mesh,
    generate_barricade_outdoor_mesh,
    # Wall decor
    generate_banner_mesh,
    generate_rug_mesh,
    generate_chandelier_mesh,
    # Crafting
    generate_anvil_mesh,
    generate_forge_mesh,
    generate_workbench_mesh,
    generate_cauldron_mesh,
    generate_market_stall_mesh,
    # Vehicles & transport
    generate_cart_mesh,
    # Fences
    generate_fence_mesh,
    # Structural
    generate_well_mesh,
    # Signs & markers
    generate_signpost_mesh,
    generate_gravestone_mesh,
    generate_waystone_mesh,
    generate_milestone_mesh,
    # Corruption / ritual markers
    generate_sacrificial_circle_mesh,
    generate_corruption_crystal_mesh,
    generate_veil_tear_mesh,
    generate_dark_obelisk_mesh,
    # Natural formations
    generate_fallen_log_mesh,
    # Misc containers
    generate_potion_bottle_mesh,
)

# Type alias matching procedural_meshes convention
MeshSpec = dict[str, Any]

# ============================================================================
# Section 1: Pure-logic (no bpy imports, fully testable outside Blender)
# ============================================================================

# ---------------------------------------------------------------------------
# FURNITURE_GENERATOR_MAP
# ---------------------------------------------------------------------------
# Maps furniture type strings (as used in _building_grammar._ROOM_CONFIGS)
# to (generator_function, kwargs_override) tuples.
#
# Direct matches: the key name matches a generator exactly (default kwargs).
# Close matches: the key name is an alias with customised kwargs.
# ---------------------------------------------------------------------------

FURNITURE_GENERATOR_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    # ---- Direct matches (20) ----
    "bed": (generate_bed_mesh, {}),
    "table": (generate_table_mesh, {}),
    "chair": (generate_chair_mesh, {}),
    "shelf": (generate_shelf_mesh, {}),
    "chest": (generate_chest_mesh, {}),
    "barrel": (generate_barrel_mesh, {}),
    "candelabra": (generate_candelabra_mesh, {}),
    "bookshelf": (generate_bookshelf_mesh, {}),
    "wardrobe": (generate_wardrobe_mesh, {}),
    "cabinet": (generate_cabinet_mesh, {}),
    "altar": (generate_altar_mesh, {}),
    "pillar": (generate_pillar_mesh, {}),
    "brazier": (generate_brazier_mesh, {}),
    "chandelier": (generate_chandelier_mesh, {}),
    "crate": (generate_crate_mesh, {}),
    "rug": (generate_rug_mesh, {}),
    "banner": (generate_banner_mesh, {}),
    "anvil": (generate_anvil_mesh, {}),
    "forge": (generate_forge_mesh, {}),
    "workbench": (generate_workbench_mesh, {}),
    "cauldron": (generate_cauldron_mesh, {}),
    "sarcophagus": (generate_sarcophagus_mesh, {}),
    "chain": (generate_chain_mesh, {}),
    "chains": (generate_chain_mesh, {}),
    "staircase": (generate_staircase_mesh, {}),
    "tent": (generate_tent_mesh, {"style": "small"}),
    "tent_large": (generate_tent_mesh, {"style": "large"}),
    "command_tent": (generate_tent_mesh, {"style": "command"}),
    "supply_tent": (generate_tent_mesh, {"style": "large"}),
    "lookout_post": (generate_lookout_post_mesh, {"style": "raised"}),
    "lookout_post_ground": (generate_lookout_post_mesh, {"style": "ground"}),
    # ---- Close matches (9) ----
    "bar_counter": (generate_table_mesh, {"width": 3.0, "depth": 0.8}),
    "fireplace": (generate_fireplace_mesh, {}),
    "cooking_fire": (generate_fireplace_mesh, {}),
    "pew": (generate_chair_mesh, {"style": "wooden_bench"}),
    "map_display": (generate_map_scroll_mesh, {"style": "rolled"}),
    "holy_symbol": (generate_holy_symbol_mesh, {}),
    "prayer_mat": (generate_rug_mesh, {}),
    "nightstand": (generate_cabinet_mesh, {}),
    "tool_rack": (generate_shelf_mesh, {"tiers": 2, "width": 1.0}),
    "bellows": (generate_forge_mesh, {"size": 0.8}),
    "large_table": (generate_table_mesh, {"width": 1.8, "depth": 1.2}),
    "long_table": (generate_table_mesh, {"width": 1.8, "depth": 4.0}),
    "serving_table": (generate_table_mesh, {"width": 1.5, "depth": 0.6}),
    "desk": (generate_table_mesh, {"style": "noble_carved", "width": 1.2}),
    "locked_chest": (generate_chest_mesh, {"style": "iron_locked"}),
    "carpet": (generate_rug_mesh, {}),
    "cage": (generate_falling_cage_mesh, {}),
    "shelf_with_bottles": (generate_shelf_mesh, {}),
    "wall_tomb": (generate_sarcophagus_mesh, {}),
}

# ---------------------------------------------------------------------------
# VEGETATION_GENERATOR_MAP
# ---------------------------------------------------------------------------
# Maps vegetation type strings (as used in environment_scatter templates)
# to (generator_function, kwargs_override) tuples.
# ---------------------------------------------------------------------------

VEGETATION_GENERATOR_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    "tree": (generate_tree_mesh, {"canopy_style": "veil_healthy"}),
    "tree_healthy": (generate_tree_mesh, {"canopy_style": "veil_healthy"}),
    "tree_boundary": (generate_tree_mesh, {"canopy_style": "veil_boundary"}),
    "tree_blighted": (generate_tree_mesh, {"canopy_style": "veil_blighted"}),
    "tree_dead": (generate_tree_mesh, {"canopy_style": "dead_twisted"}),
    "tree_twisted": (generate_tree_mesh, {"canopy_style": "veil_boundary"}),
    "pine_tree": (generate_tree_mesh, {"canopy_style": "dark_pine"}),
    "bush": (generate_shrub_mesh, {}),
    "shrub": (generate_shrub_mesh, {}),
    "grass": (generate_grass_clump_mesh, {}),
    "weed": (generate_grass_clump_mesh, {"blade_count": 9, "height": 0.5, "spread": 0.16, "width": 0.035}),
    "flower": (generate_mushroom_mesh, {"size": 0.28, "cap_style": "cluster"}),
    "rock": (generate_rock_mesh, {"rock_type": "boulder"}),
    "rock_mossy": (generate_rock_mesh, {"rock_type": "boulder", "size": 0.92}),
    "cliff_rock": (generate_rock_mesh, {"rock_type": "cliff_outcrop"}),
    "mushroom": (generate_mushroom_mesh, {}),
    "mushroom_cluster": (generate_mushroom_mesh, {"cap_style": "cluster", "size": 0.34}),
    "root": (generate_root_mesh, {}),
}

# ---------------------------------------------------------------------------
# DUNGEON_PROP_MAP
# ---------------------------------------------------------------------------
# Maps dungeon prop type strings to procedural generators. Covers all
# torch/trap/decorative items found in dungeon generation handlers.
# ---------------------------------------------------------------------------

DUNGEON_PROP_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    "torch_sconce": (generate_torch_sconce_mesh, {}),
    "altar": (generate_altar_mesh, {}),
    "prison_door": (generate_prison_door_mesh, {}),
    "spike_trap": (generate_spike_trap_mesh, {}),
    "bear_trap": (generate_bear_trap_mesh, {}),
    "pressure_plate": (generate_pressure_plate_mesh, {}),
    "dart_launcher": (generate_dart_launcher_mesh, {}),
    "swinging_blade": (generate_swinging_blade_mesh, {}),
    "falling_cage": (generate_falling_cage_mesh, {}),
    "skull_pile": (generate_skull_pile_mesh, {}),
    "sarcophagus": (generate_sarcophagus_mesh, {}),
    "chain": (generate_chain_mesh, {}),
    "archway": (generate_archway_mesh, {}),
    "pillar": (generate_pillar_mesh, {}),
}

# ---------------------------------------------------------------------------
# CASTLE_ELEMENT_MAP
# ---------------------------------------------------------------------------
# Maps castle/fortification element types to procedural generators.
# ---------------------------------------------------------------------------

CASTLE_ELEMENT_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    "gate": (generate_gate_mesh, {}),
    "rampart": (generate_rampart_mesh, {}),
    "drawbridge": (generate_drawbridge_mesh, {}),
    "fountain": (generate_fountain_mesh, {}),
    "pillar": (generate_pillar_mesh, {}),
}

# ---------------------------------------------------------------------------
# PROP_GENERATOR_MAP
# ---------------------------------------------------------------------------
# Maps prop type strings (as used in PROP_AFFINITY and _GENERIC_PROPS in
# _scatter_engine.py) to (generator_function, kwargs_override) tuples.
# Every prop type appearing in PROP_AFFINITY or _GENERIC_PROPS must have
# an entry here. Types without a perfect generator match use the closest
# available generator with appropriate kwargs.
# ---------------------------------------------------------------------------

PROP_GENERATOR_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    # ---- Direct matches ----
    "barrel": (generate_barrel_mesh, {}),
    "crate": (generate_crate_mesh, {}),
    "lantern": (generate_lantern_mesh, {}),
    "cart": (generate_cart_mesh, {}),
    "anvil": (generate_anvil_mesh, {}),
    "rock": (generate_rock_mesh, {"rock_type": "boulder"}),
    "cliff_rock": (generate_rock_mesh, {"rock_type": "cliff_outcrop"}),
    "mushroom": (generate_mushroom_mesh, {}),
    "fence": (generate_fence_mesh, {}),
    "sack": (generate_sack_mesh, {}),
    "basket": (generate_basket_mesh, {}),
    "well": (generate_well_mesh, {}),
    "market_stall": (generate_market_stall_mesh, {}),
    "signpost": (generate_signpost_mesh, {}),
    "campfire": (generate_campfire_mesh, {}),
    "spike_fence": (generate_spike_fence_mesh, {}),
    "barricade": (generate_barricade_mesh, {}),
    "barricade_outdoor": (generate_barricade_outdoor_mesh, {}),
    "hitching_post": (generate_hitching_post_mesh, {}),
    "gravestone": (generate_gravestone_mesh, {}),
    "waystone": (generate_waystone_mesh, {}),
    "milestone": (generate_milestone_mesh, {}),
    "torch_sconce": (generate_torch_sconce_mesh, {}),
    "brazier": (generate_brazier_mesh, {}),
    "sacrificial_circle": (generate_sacrificial_circle_mesh, {}),
    "corruption_crystal": (generate_corruption_crystal_mesh, {}),
    "veil_tear": (generate_veil_tear_mesh, {}),
    "dark_obelisk": (generate_dark_obelisk_mesh, {}),
    # ---- Close matches (aliases using best-fit generators) ----
    "bench": (generate_chair_mesh, {"style": "wooden_bench"}),
    "mug": (generate_potion_bottle_mesh, {"style": "round_flask"}),
    "pot": (generate_cauldron_mesh, {"size": 0.3}),
    "tombstone": (generate_gravestone_mesh, {}),
    "dead_tree": (generate_tree_mesh, {"canopy_style": "dead_twisted"}),
    "tree_twisted": (generate_tree_mesh, {"canopy_style": "veil_boundary"}),
    "fallen_log": (generate_fallen_log_mesh, {}),
    "log": (generate_fallen_log_mesh, {}),
    "bush": (generate_shrub_mesh, {}),
    "shrub": (generate_shrub_mesh, {}),
    "grass": (generate_grass_clump_mesh, {}),
    "weed_patch": (generate_grass_clump_mesh, {"blade_count": 12, "height": 0.42, "spread": 0.18, "width": 0.03}),
    "rock_mossy": (generate_rock_mesh, {"rock_type": "boulder", "size": 0.92}),
    "mushroom_cluster": (generate_mushroom_mesh, {"cap_style": "cluster", "size": 0.34}),
    "rope_coil": (generate_basket_mesh, {"handle": False}),
    "anchor": (generate_anvil_mesh, {"size": 0.8}),
    "weapon_rack": (generate_shelf_mesh, {"tiers": 2, "width": 1.0}),
    "coal_pile": (generate_rock_mesh, {"rock_type": "rubble_pile", "size": 0.5}),
}

# ---------------------------------------------------------------------------
# All maps by name (for resolve_generator)
# ---------------------------------------------------------------------------

_ALL_MAPS: dict[str, dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]]] = {
    "furniture": FURNITURE_GENERATOR_MAP,
    "vegetation": VEGETATION_GENERATOR_MAP,
    "dungeon_prop": DUNGEON_PROP_MAP,
    "castle": CASTLE_ELEMENT_MAP,
    "prop": PROP_GENERATOR_MAP,
}


# ---------------------------------------------------------------------------
# CATEGORY_MATERIAL_MAP -- procedural material auto-assignment
# ---------------------------------------------------------------------------
# Maps generator category strings (from MeshSpec metadata["category"]) to
# the procedural material key from MATERIAL_LIBRARY in procedural_materials.py.
#
# Every mesh category gets an appropriate AAA-quality procedural material
# instead of a flat single-color Principled BSDF.
# ---------------------------------------------------------------------------

CATEGORY_MATERIAL_MAP: dict[str, str] = {
    # Furniture -- aged wood look with grain and roughness variation
    "furniture": "rough_timber",
    # Vegetation -- bark for trunks, leaf for canopy (bark is default)
    "vegetation": "bark",
    # Dungeon props -- dark stone for the dungeon atmosphere
    "dungeon_prop": "rough_stone_wall",
    # Weapons -- rusted iron for dark fantasy weapons
    "weapon": "rusted_iron",
    # Armor -- polished steel with wear
    "armor": "polished_steel",
    # Architecture -- stone wall appearance
    "architecture": "rough_stone_wall",
    # Building -- brick wall appearance
    "building": "brick_wall",
    # Containers -- aged wood crates/barrels
    "container": "rough_timber",
    # Dark fantasy -- corruption overlay with purple glow
    "dark_fantasy": "corruption_overlay",
    # Monster parts -- organic chitin/scales
    "monster_part": "chitin_carapace",
    # Monster bodies -- organic skin
    "monster_body": "monster_skin",
    # Projectiles -- rusted iron for arrows/bolts
    "projectile": "rusted_iron",
    # Traps -- chain metal for mechanical traps
    "trap": "chain_metal",
    # Light sources -- tarnished bronze for lanterns/braziers
    "light_source": "tarnished_bronze",
    # Wall decorations -- burlap cloth for banners/rugs
    "wall_decor": "burlap_cloth",
    # Crafting stations -- rusted iron for forges/anvils
    "crafting": "rusted_iron",
    # Vehicles -- rough timber for carts
    "vehicle": "rough_timber",
    # Structural -- rough stone for pillars/buttresses
    "structural": "rough_stone_wall",
    # Fortification -- smooth stone for castle elements
    "fortification": "smooth_stone",
    # Signs/markers -- rough timber for signposts
    "sign": "rough_timber",
    # Natural formations -- cliff rock
    "natural": "cliff_rock",
    # Fences and barriers -- rough timber
    "fence_barrier": "rough_timber",
    # Doors -- rough timber
    "door": "rough_timber",
    # Camp equipment -- leather
    "camp": "leather",
    # Infrastructure -- cobblestone floor
    "infrastructure": "cobblestone_floor",
    # Consumables -- organic mushroom cap
    "consumable": "mushroom_cap",
    # Crafting materials -- cliff rock for ore
    "crafting_material": "cliff_rock",
    # Currency -- gold ornament
    "currency": "gold_ornament",
    # Key items -- polished wood
    "key_item": "polished_wood",
    # Combat items -- rusted iron
    "combat_item": "rusted_iron",
    # Forest animals -- fur base
    "forest_animal": "fur_base",
    # Mountain animals -- fur base
    "mountain_animal": "fur_base",
    # Domestic animals -- fur base
    "domestic_animal": "fur_base",
    # Vermin -- chitin carapace
    "vermin": "chitin_carapace",
    # Swamp animals -- scales
    "swamp_animal": "scales",
}


def get_material_for_category(category: str) -> str | None:
    """Return the procedural material key for a generator category.

    Args:
        category: Generator category string from MeshSpec metadata.

    Returns:
        Material key for MATERIAL_LIBRARY, or None if no mapping exists.
    """
    return CATEGORY_MATERIAL_MAP.get(category)


# ---------------------------------------------------------------------------
# resolve_generator
# ---------------------------------------------------------------------------


def resolve_generator(
    map_name: str, item_type: str
) -> tuple[Callable[..., MeshSpec], dict[str, Any]] | None:
    """Look up a generator from a named mapping table.

    Args:
        map_name: One of "furniture", "vegetation", "dungeon_prop", "castle".
        item_type: The item type key (e.g. "table", "tree", "gate").

    Returns:
        (generator_function, kwargs_override) or None if not found.
    """
    mapping = _ALL_MAPS.get(map_name)
    if mapping is None:
        return None
    return mapping.get(item_type)


# ---------------------------------------------------------------------------
# generate_lod_specs
# ---------------------------------------------------------------------------


def generate_lod_specs(
    spec: MeshSpec,
    ratios: list[float] | None = None,
) -> list[MeshSpec]:
    """Generate LOD variants of a MeshSpec by decimating the face list.

    Pure-logic function -- no Blender dependency. Creates LOD0 (original),
    LOD1 (reduced), LOD2 (minimal) by keeping a fraction of faces.

    Args:
        spec: Source MeshSpec with vertices, faces, uvs, metadata.
        ratios: Decimation ratios per LOD level. Default [1.0, 0.5, 0.25].
            Each value is the fraction of faces to keep (1.0 = all).

    Returns:
        List of MeshSpec dicts, one per LOD level, with metadata names
        suffixed ``_LOD0``, ``_LOD1``, ``_LOD2`` etc.
    """
    if ratios is None:
        ratios = [1.0, 0.5, 0.25]

    faces = spec["faces"]
    total_faces = len(faces)
    base_name = spec["metadata"]["name"]

    lod_specs: list[MeshSpec] = []

    for level, ratio in enumerate(ratios):
        keep_count = max(1, int(math.ceil(total_faces * ratio)))
        # Clamp to actual face count
        keep_count = min(keep_count, total_faces)
        lod_faces = faces[:keep_count]

        # Compact vertices: remove orphaned vertices not referenced by any face
        used_indices = sorted(set(idx for face in lod_faces for idx in face))
        index_remap = {old: new for new, old in enumerate(used_indices)}
        lod_verts = [spec["vertices"][i] for i in used_indices]
        lod_faces_remapped = [
            tuple(index_remap[i] for i in face) for face in lod_faces
        ]

        # Remap UVs if per-vertex
        lod_uvs = spec["uvs"]
        if lod_uvs and len(lod_uvs) == len(spec["vertices"]):
            lod_uvs = [spec["uvs"][i] for i in used_indices]

        lod_spec: MeshSpec = {
            "vertices": lod_verts,
            "faces": lod_faces_remapped,
            "uvs": lod_uvs,
            "metadata": {
                **spec["metadata"],
                "name": f"{base_name}_LOD{level}",
                "poly_count": len(lod_faces_remapped),
                "vertex_count": len(lod_verts),
            },
        }
        lod_specs.append(lod_spec)

    return lod_specs


# ============================================================================
# Section 2: Blender-dependent (guarded by bpy import)
# ============================================================================

_HAS_BPY = False
try:
    import bpy
    import bmesh

    _HAS_BPY = True
except ImportError:
    pass


def mesh_from_spec(
    spec: MeshSpec,
    name: str | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    collection: Any = None,
    parent: Any = None,
    smooth_shading: bool = True,
    auto_smooth_angle: float = 35.0,
) -> Any:
    """Convert a MeshSpec dict into a Blender mesh object.

    Uses the bmesh pattern from worldbuilding._spec_to_bmesh for vertex/face
    creation and optionally assigns UVs, normals, collection, and parent.

    Now also supports:
    - Smooth shading with auto-smooth angle threshold
    - Edge annotations from MeshSpec: ``sharp_edges`` and ``crease_edges``

    When running outside Blender (bpy is a stub), returns a dict summary
    instead of a bpy.types.Object so that pure-logic tests can verify
    name resolution without crashing.

    Args:
        spec: MeshSpec dict with vertices, faces, uvs, metadata.
            Optional keys:
            - ``sharp_edges``: list of [vert_a, vert_b] pairs to mark sharp.
            - ``crease_edges``: list of {"edge": [a, b], "value": float} dicts.
        name: Override object name. Falls back to spec metadata name.
        location: World-space position (x, y, z).
        rotation: Euler rotation in radians (x, y, z).
        scale: Scale factors (x, y, z).
        collection: Blender collection to link the object into.
        parent: Blender object to set as parent.
        smooth_shading: Apply smooth shading to all faces (default True).
        auto_smooth_angle: Auto-smooth angle in degrees (default 35.0).

    Returns:
        bpy.types.Object when Blender is available, otherwise a dict
        summary ``{"obj_name": str, "vertex_count": int, "face_count": int}``.
    """
    # Validate input
    if not spec or not isinstance(spec, dict):
        raise ValueError("mesh_from_spec: spec must be a non-empty dict")
    if "vertices" not in spec or "faces" not in spec:
        raise ValueError("mesh_from_spec: spec must contain 'vertices' and 'faces'")
    if not spec["vertices"]:
        raise ValueError("mesh_from_spec: spec has empty vertices list")

    obj_name = name or spec.get("metadata", {}).get("name", "MeshSpec_Object")
    verts = spec["vertices"]
    faces = spec["faces"]
    uvs = spec.get("uvs", [])
    sharp_edges = spec.get("sharp_edges", [])
    crease_edges = spec.get("crease_edges", [])

    # -- Fallback for non-Blender environments (testing) --
    if not _HAS_BPY or not hasattr(bpy, "data"):
        return {
            "obj_name": obj_name,
            "vertex_count": len(verts),
            "face_count": len(faces),
            "smooth_shading": smooth_shading,
        }

    # -- Blender path --
    bm = bmesh.new()

    # Add vertices
    bm_verts = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()

    # Add faces
    for face_indices in faces:
        try:
            bm.faces.new([bm_verts[i] for i in face_indices])
        except (ValueError, IndexError):
            print(f"Warning: skipped degenerate face {face_indices}")

    # Process edge annotations from MeshSpec
    if sharp_edges or crease_edges:
        bm.edges.ensure_lookup_table()

        # Build vertex-pair -> edge lookup
        edge_lookup: dict[tuple[int, int], Any] = {}
        for edge in bm.edges:
            key = (min(edge.verts[0].index, edge.verts[1].index),
                   max(edge.verts[0].index, edge.verts[1].index))
            edge_lookup[key] = edge

        # Mark sharp edges
        for se in sharp_edges:
            if len(se) >= 2:
                key = (min(se[0], se[1]), max(se[0], se[1]))
                edge = edge_lookup.get(key)
                if edge:
                    edge.smooth = False

        # Set edge creases
        if crease_edges:
            crease_layer = bm.edges.layers.float.get("crease_edge")
            if crease_layer is None:
                crease_layer = bm.edges.layers.float.new("crease_edge")
            for ce in crease_edges:
                edge_pair = ce.get("edge", [])
                if len(edge_pair) >= 2:
                    key = (min(edge_pair[0], edge_pair[1]),
                           max(edge_pair[0], edge_pair[1]))
                    edge = edge_lookup.get(key)
                    if edge:
                        edge[crease_layer] = ce.get("value", 1.0)

    # Assign UVs if present
    if uvs:
        uv_layer = bm.loops.layers.uv.new("UVMap")
        bm.faces.ensure_lookup_table()
        for face in bm.faces:
            for loop in face.loops:
                vi = loop.vert.index
                if vi < len(uvs):
                    loop[uv_layer].uv = uvs[vi]

    # Recalculate normals
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    # Create Blender mesh data and object
    mesh_data = bpy.data.meshes.new(obj_name)
    bm.to_mesh(mesh_data)
    bm.free()

    # Apply smooth shading
    if smooth_shading:
        for poly in mesh_data.polygons:
            poly.use_smooth = True
        # Auto-smooth: Blender 3.x has use_auto_smooth, 4.x uses sharp edges
        if hasattr(mesh_data, "use_auto_smooth"):
            mesh_data.use_auto_smooth = True
            mesh_data.auto_smooth_angle = _math_radians(auto_smooth_angle)

    obj = bpy.data.objects.new(obj_name, mesh_data)
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale

    # Link to collection
    if collection is not None:
        collection.objects.link(obj)
    else:
        bpy.context.collection.objects.link(obj)

    # Set parent
    if parent is not None:
        obj.parent = parent

    # Auto-assign procedural material based on generator category
    category = spec.get("metadata", {}).get("category", "")
    if category:
        material_key = CATEGORY_MATERIAL_MAP.get(category)
        if material_key:
            try:
                from .procedural_materials import (
                    create_procedural_material,
                    MATERIAL_LIBRARY,
                )
                if material_key in MATERIAL_LIBRARY:
                    mat_name = f"{obj_name}_{material_key}"
                    mat = create_procedural_material(mat_name, material_key)
                    if obj.data.materials:
                        obj.data.materials[0] = mat
                    else:
                        obj.data.materials.append(mat)
            except Exception:
                # Graceful fallback: if procedural material creation fails,
                # the object keeps its default material (no crash)
                pass

    return obj


def _math_radians(degrees: float) -> float:
    """Convert degrees to radians (avoids importing math at module level)."""
    return degrees * 3.141592653589793 / 180.0
