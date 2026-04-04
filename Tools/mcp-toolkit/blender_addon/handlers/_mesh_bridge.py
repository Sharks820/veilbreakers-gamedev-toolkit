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
from .vegetation_lsystem import generate_lsystem_tree, generate_leaf_cards

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
    # ---- Clutter type mappings (MESH-03) ----
    "mug": (generate_potion_bottle_mesh, {"style": "round_flask"}),
    "plate": (generate_rug_mesh, {}),  # flat disc approximation
    "bottle": (generate_potion_bottle_mesh, {}),
    "goblet": (generate_potion_bottle_mesh, {"style": "round_flask"}),
    "pot": (generate_cauldron_mesh, {"size": 0.3}),
    "candle_stub": (generate_candelabra_mesh, {}),
    "book": (generate_map_scroll_mesh, {"style": "rolled"}),
    "open_book": (generate_map_scroll_mesh, {"style": "rolled"}),
    "scroll": (generate_map_scroll_mesh, {"style": "rolled"}),
    "potion_bottle": (generate_potion_bottle_mesh, {}),
    "coin_pile": (generate_rock_mesh, {"rock_type": "rubble_pile", "size": 0.2}),
    "skull_pile": (generate_skull_pile_mesh, {}),
    "bone_fragment": (generate_skull_pile_mesh, {}),
    "coal_pile": (generate_rock_mesh, {"rock_type": "rubble_pile", "size": 0.5}),
    "hammer": (generate_anvil_mesh, {"size": 0.3}),
    "tongs": (generate_anvil_mesh, {"size": 0.25}),
    "horseshoe": (generate_anvil_mesh, {"size": 0.15}),
    "metal_ingot": (generate_crate_mesh, {}),
    "rope_coil": (generate_basket_mesh, {"handle": False}),
    "sack": (generate_sack_mesh, {}),
    "basket": (generate_basket_mesh, {}),
    "lantern": (generate_lantern_mesh, {}),
    "torch_sconce": (generate_torch_sconce_mesh, {}),
}

# ---------------------------------------------------------------------------
# L-system tree adapter for VEGETATION_GENERATOR_MAP
# ---------------------------------------------------------------------------


def _lsystem_tree_generator(**kwargs: Any) -> MeshSpec:
    """Adapter: calls generate_lsystem_tree with dict params, returns MeshSpec.

    Bridges the (func, kwargs) pattern used by VEGETATION_GENERATOR_MAP to
    the dict-params interface of generate_lsystem_tree. Optionally merges
    leaf card geometry at branch tips when leaf_type is specified.
    """
    # Extract leaf_type and canopy_style before passing params to L-system generator
    leaf_type = kwargs.pop("leaf_type", "broadleaf")
    canopy_style = kwargs.pop("canopy_style", "veil_healthy")

    tree_result = generate_lsystem_tree(kwargs)

    # Build MeshSpec from L-system output
    vertices = tree_result["vertices"]
    faces = tree_result["faces"]
    tree_type = kwargs.get("tree_type", "oak")
    spec: MeshSpec = {
        "vertices": vertices,
        "faces": faces,
        "uvs": [],
        "metadata": {
            "name": f"lsystem_tree_{tree_type}",
            "generator": "lsystem_tree",
            "tree_type": tree_type,
            "canopy_style": canopy_style,
            "category": "vegetation",
            "poly_count": len(faces),
            "vertex_count": len(vertices),
            **tree_result.get("metadata", {}),
        },
    }

    # Add leaf cards if tip data available and leaf generation requested
    if leaf_type and tree_result.get("tip_positions"):
        tips: list[dict[str, Any]] = []
        for i, pos in enumerate(tree_result["tip_positions"]):
            tip_dirs = tree_result.get("tip_directions", [])
            tip_radii = tree_result.get("tip_radii", [])
            tips.append({
                "position": pos,
                "direction": tip_dirs[i] if i < len(tip_dirs) else [0, 0, 1],
                "radius": tip_radii[i] if i < len(tip_radii) else 0.05,
            })
        leaf_spec = generate_leaf_cards(
            tips, leaf_type=leaf_type, seed=kwargs.get("seed", 42),
        )
        # Merge leaf vertices/faces into main spec
        v_offset = len(spec["vertices"])
        spec["vertices"] = list(spec["vertices"]) + list(leaf_spec["vertices"])
        spec["faces"] = list(spec["faces"]) + [
            tuple(idx + v_offset for idx in face)
            for face in leaf_spec["faces"]
        ]

    return spec


# ---------------------------------------------------------------------------
# VEGETATION_GENERATOR_MAP
# ---------------------------------------------------------------------------
# Maps vegetation type strings (as used in environment_scatter templates)
# to (generator_function, kwargs_override) tuples.
#
# Tree entries use L-system branching (not sphere clusters) via
# _lsystem_tree_generator. iterations=4 caps branching depth for scatter
# performance (prevents exponential geometry growth).
# ---------------------------------------------------------------------------

VEGETATION_GENERATOR_MAP: dict[str, tuple[Callable[..., MeshSpec], dict[str, Any]]] = {
    "tree": (_lsystem_tree_generator, {"tree_type": "oak", "iterations": 4, "leaf_type": "broadleaf", "canopy_style": "veil_healthy"}),
    "tree_healthy": (_lsystem_tree_generator, {"tree_type": "oak", "iterations": 4, "leaf_type": "broadleaf", "canopy_style": "veil_healthy"}),
    "tree_boundary": (_lsystem_tree_generator, {"tree_type": "birch", "iterations": 4, "leaf_type": "broadleaf", "canopy_style": "veil_boundary"}),
    "tree_blighted": (_lsystem_tree_generator, {"tree_type": "twisted", "iterations": 4, "leaf_type": "vine", "canopy_style": "veil_blighted"}),
    "tree_dead": (_lsystem_tree_generator, {"tree_type": "dead", "iterations": 4, "leaf_type": None, "canopy_style": "veil_blighted"}),
    "tree_twisted": (_lsystem_tree_generator, {"tree_type": "twisted", "iterations": 4, "leaf_type": "vine", "canopy_style": "veil_boundary"}),
    "pine_tree": (_lsystem_tree_generator, {"tree_type": "pine", "iterations": 4, "leaf_type": "needle", "canopy_style": "veil_healthy"}),
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
    "dead_tree": (_lsystem_tree_generator, {"tree_type": "dead", "iterations": 4, "leaf_type": None}),
    "tree_twisted": (_lsystem_tree_generator, {"tree_type": "twisted", "iterations": 4, "leaf_type": "vine"}),
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
    # Clothing -- fabric cloth for garments
    "clothing": "burlap_cloth",
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
# post_boolean_cleanup -- pure-logic mesh cleanup after boolean operations
# ---------------------------------------------------------------------------


def post_boolean_cleanup(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    *,
    merge_distance: float = 0.0001,
    max_hole_sides: int = 8,
) -> dict[str, Any]:
    """Clean up mesh geometry after boolean operations.

    Pure-logic function (no bpy). Performs:
    1. Remove doubles (merge vertices closer than merge_distance)
    2. Recalculate normals (ensure consistent face winding)
    3. Detect non-manifold edges (boundary edges with only 1 face)
    4. Fill holes up to max_hole_sides

    Args:
        vertices: Input vertex list.
        faces: Input face list.
        merge_distance: Distance threshold for merging duplicate vertices.
        max_hole_sides: Maximum number of sides for hole filling.

    Returns:
        Dict with:
        - vertices: Cleaned vertex list
        - faces: Cleaned face list
        - report: Dict with doubles_removed, normals_fixed, holes_filled,
          non_manifold_edges counts
    """
    if not vertices or not faces:
        return {
            "vertices": vertices,
            "faces": faces,
            "report": {
                "doubles_removed": 0,
                "normals_fixed": 0,
                "holes_filled": 0,
                "non_manifold_edges": 0,
            },
        }

    # --- Step 1: Remove doubles (merge nearby vertices) ---
    merge_dist_sq = merge_distance * merge_distance
    n_verts = len(vertices)
    remap = list(range(n_verts))  # vertex -> canonical vertex
    doubles_removed = 0

    # Simple O(n^2) merge for correctness (boolean outputs are typically small)
    for i in range(n_verts):
        if remap[i] != i:
            continue
        for j in range(i + 1, n_verts):
            if remap[j] != j:
                continue
            vi = vertices[i]
            vj = vertices[j]
            dx = vi[0] - vj[0]
            dy = vi[1] - vj[1]
            dz = vi[2] - vj[2]
            if dx * dx + dy * dy + dz * dz < merge_dist_sq:
                remap[j] = i
                doubles_removed += 1

    # Remap face indices and remove degenerate faces
    remapped_faces: list[tuple[int, ...]] = []
    for face in faces:
        new_face_indices: list[int] = []
        seen: set[int] = set()
        for idx in face:
            canonical = remap[idx]
            if canonical not in seen:
                new_face_indices.append(canonical)
                seen.add(canonical)
        if len(new_face_indices) >= 3:
            remapped_faces.append(tuple(new_face_indices))

    # Compact vertex list (remove unreferenced vertices)
    used = sorted(set(idx for f in remapped_faces for idx in f))
    compact_map = {old: new for new, old in enumerate(used)}
    clean_verts = [vertices[i] for i in used]
    clean_faces = [
        tuple(compact_map[idx] for idx in f) for f in remapped_faces
    ]

    # --- Step 2: Recalculate normals (consistent winding) ---
    normals_fixed = 0
    # Build edge -> face adjacency
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, face in enumerate(clean_faces):
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            key = (min(a, b), max(a, b))
            if key not in edge_faces:
                edge_faces[key] = []
            edge_faces[key].append(fi)

    # BFS to propagate consistent winding from face 0
    if clean_faces:
        visited = [False] * len(clean_faces)
        face_list = [list(f) for f in clean_faces]
        queue = [0]
        visited[0] = True
        while queue:
            fi = queue.pop(0)
            face = face_list[fi]
            n = len(face)
            for i in range(n):
                a, b = face[i], face[(i + 1) % n]
                key = (min(a, b), max(a, b))
                for neighbor_fi in edge_faces.get(key, []):
                    if visited[neighbor_fi]:
                        continue
                    visited[neighbor_fi] = True
                    queue.append(neighbor_fi)
                    # Check winding consistency
                    nf = face_list[neighbor_fi]
                    # Find shared edge in neighbor
                    for j in range(len(nf)):
                        na, nb = nf[j], nf[(j + 1) % len(nf)]
                        if (min(na, nb), max(na, nb)) == key:
                            # Shared edge should have OPPOSITE winding
                            if na == a and nb == b:
                                # Same winding -- need to reverse neighbor
                                face_list[neighbor_fi] = list(reversed(nf))
                                normals_fixed += 1
                            break
        clean_faces = [tuple(f) for f in face_list]

    # --- Step 3: Detect non-manifold edges ---
    # Rebuild edge adjacency after potential face reversals
    edge_faces_final: dict[tuple[int, int], int] = {}
    for fi, face in enumerate(clean_faces):
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            key = (min(a, b), max(a, b))
            edge_faces_final[key] = edge_faces_final.get(key, 0) + 1

    non_manifold_edges = sum(
        1 for count in edge_faces_final.values() if count == 1
    )

    # --- Step 4: Fill holes (boundary loops up to max_hole_sides) ---
    holes_filled = 0
    if non_manifold_edges > 0:
        # Find boundary edges (edges with only 1 face)
        boundary_edges: list[tuple[int, int]] = [
            edge for edge, count in edge_faces_final.items() if count == 1
        ]

        # Build boundary adjacency: vertex -> list of connected boundary vertices
        boundary_adj: dict[int, list[int]] = {}
        for a, b in boundary_edges:
            boundary_adj.setdefault(a, []).append(b)
            boundary_adj.setdefault(b, []).append(a)

        # Trace boundary loops
        visited_edges: set[tuple[int, int]] = set()
        for start_a, start_b in boundary_edges:
            key = (min(start_a, start_b), max(start_a, start_b))
            if key in visited_edges:
                continue

            # Trace loop from start_a
            loop: list[int] = [start_a]
            current = start_b
            prev = start_a
            for _ in range(max_hole_sides + 2):
                ekey = (min(prev, current), max(prev, current))
                visited_edges.add(ekey)
                if current == start_a:
                    break
                loop.append(current)
                neighbors = boundary_adj.get(current, [])
                next_v = None
                for nb in neighbors:
                    if nb != prev:
                        nkey = (min(current, nb), max(current, nb))
                        if nkey not in visited_edges:
                            next_v = nb
                            break
                if next_v is None:
                    break
                prev = current
                current = next_v

            if (
                len(loop) >= 3
                and len(loop) <= max_hole_sides
                and current == start_a
            ):
                # Fill this hole with a face
                clean_faces.append(tuple(reversed(loop)))
                holes_filled += 1

    return {
        "vertices": clean_verts,
        "faces": clean_faces,
        "report": {
            "doubles_removed": doubles_removed,
            "normals_fixed": normals_fixed,
            "holes_filled": holes_filled,
            "non_manifold_edges": non_manifold_edges,
        },
    }


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
    material_ids: list[int] = list(spec.get("material_ids", []))

    # Validate material_ids: must be in range [0, num_slots-1]
    if material_ids:
        unique_slots = sorted(set(material_ids))
        num_slots = len(unique_slots)
        for fi, mid in enumerate(material_ids):
            if mid < 0 or mid >= num_slots:
                raise ValueError(
                    f"mesh_from_spec: material_id {mid} at face {fi} is out of range "
                    f"[0, {num_slots - 1}] for {num_slots} unique slot(s) in material_ids"
                )
    else:
        num_slots = 1

    # -- Fallback for non-Blender environments (testing) --
    if not _HAS_BPY or not hasattr(bpy, "data"):
        return {
            "obj_name": obj_name,
            "vertex_count": len(verts),
            "face_count": len(faces),
            "smooth_shading": smooth_shading,
            "material_slot_count": num_slots,
            "face_material_ids": list(material_ids) if material_ids else [],
        }

    # -- Blender path --
    bm = bmesh.new()

    # Add vertices with deduplication: weld coincident vertices from
    # generators that create disconnected components at the same positions
    _WELD_TOLERANCE = 0.005  # 5mm — covers mortar gaps in stone generators
    _vert_dedup: dict[tuple[int, int, int], int] = {}
    bm_verts: list[Any] = []
    _remap: list[int] = []  # maps original index -> deduped index
    for v in verts:
        # Quantize to tolerance grid for fast lookup
        key = (
            round(v[0] / _WELD_TOLERANCE),
            round(v[1] / _WELD_TOLERANCE),
            round(v[2] / _WELD_TOLERANCE),
        )
        if key in _vert_dedup:
            _remap.append(_vert_dedup[key])
        else:
            idx = len(bm_verts)
            _vert_dedup[key] = idx
            bm_verts.append(bm.verts.new(v))
            _remap.append(idx)
    bm.verts.ensure_lookup_table()

    # Add faces using remapped vertex indices
    for face_indices in faces:
        try:
            remapped = [_remap[i] for i in face_indices]
            # Skip degenerate faces where dedup collapsed vertices
            if len(set(remapped)) < 3:
                continue
            bm.faces.new([bm_verts[i] for i in remapped])
        except (ValueError, IndexError):
            pass  # skip duplicate or degenerate faces

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
            except Exception as e:
                import logging
                logging.getLogger("veilbreakers.mesh_bridge").warning(
                    "Material assignment failed for %s (category=%s, key=%s): %s",
                    obj_name, category, material_key, e,
                )

    return obj


def _math_radians(degrees: float) -> float:
    """Convert degrees to radians (avoids importing math at module level)."""
    return degrees * 3.141592653589793 / 180.0
