"""Tests for procedural mesh generation library.

Validates that every generator function returns valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Reasonable vertex/face counts for the object type
- Required metadata keys present
- Different styles produce different geometry
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.procedural_meshes import (
    # Furniture
    generate_table_mesh,
    generate_chair_mesh,
    generate_shelf_mesh,
    generate_chest_mesh,
    generate_barrel_mesh,
    generate_candelabra_mesh,
    generate_bookshelf_mesh,
    generate_bed_mesh,
    generate_wardrobe_mesh,
    generate_cabinet_mesh,
    generate_curtain_mesh,
    generate_mirror_mesh,
    generate_hay_bale_mesh,
    generate_wine_rack_mesh,
    generate_bathtub_mesh,
    generate_fireplace_mesh,
    # Vegetation
    generate_tree_mesh,
    generate_rock_mesh,
    generate_mushroom_mesh,
    generate_root_mesh,
    generate_ivy_mesh,
    # Dungeon props
    generate_torch_sconce_mesh,
    generate_prison_door_mesh,
    generate_sarcophagus_mesh,
    generate_altar_mesh,
    generate_pillar_mesh,
    generate_archway_mesh,
    generate_chain_mesh,
    generate_skull_pile_mesh,
    # Dungeon props (expanded)
    generate_portcullis_mesh,
    generate_iron_gate_mesh,
    generate_bridge_plank_mesh,
    generate_shackle_mesh,
    generate_cage_mesh,
    generate_stocks_mesh,
    generate_iron_maiden_mesh,
    generate_prisoner_skeleton_mesh,
    generate_summoning_circle_mesh,
    generate_ritual_candles_mesh,
    generate_occult_symbols_mesh,
    generate_cobweb_mesh,
    generate_spider_egg_sac_mesh,
    generate_rubble_pile_mesh,
    generate_hanging_skeleton_mesh,
    generate_dripping_water_mesh,
    generate_rat_nest_mesh,
    generate_rotting_barrel_mesh,
    generate_treasure_chest_mesh,
    generate_gem_pile_mesh,
    generate_gold_pile_mesh,
    generate_lore_tablet_mesh,
    # Weapons
    generate_hammer_mesh,
    generate_spear_mesh,
    generate_crossbow_mesh,
    generate_scythe_mesh,
    generate_flail_mesh,
    generate_whip_mesh,
    generate_claw_mesh,
    generate_tome_mesh,
    # Architecture
    generate_gargoyle_mesh,
    generate_fountain_mesh,
    generate_statue_mesh,
    generate_bridge_mesh,
    generate_gate_mesh,
    generate_staircase_mesh,
    # Outdoor Structures & Fortifications
    generate_palisade_mesh,
    generate_watchtower_mesh,
    generate_battlement_mesh,
    generate_moat_edge_mesh,
    generate_windmill_mesh,
    generate_dock_mesh,
    generate_bridge_stone_mesh,
    generate_rope_bridge_mesh,
    generate_tent_mesh,
    generate_hitching_post_mesh,
    generate_feeding_trough_mesh,
    generate_barricade_outdoor_mesh,
    generate_lookout_post_mesh,
    generate_spike_fence_mesh,
    # Consumables
    generate_health_potion_mesh,
    generate_mana_potion_mesh,
    generate_antidote_mesh,
    generate_bread_mesh,
    generate_cheese_mesh,
    generate_meat_mesh,
    generate_apple_mesh,
    generate_mushroom_food_mesh,
    generate_fish_mesh,
    # Crafting Materials
    generate_ore_mesh,
    generate_leather_mesh,
    generate_herb_mesh,
    generate_gem_mesh,
    generate_bone_shard_mesh,
    # Currency
    generate_coin_mesh,
    generate_coin_pouch_mesh,
    # Key Items
    generate_key_mesh,
    generate_map_scroll_mesh,
    generate_lockpick_mesh,
    # Registry
    GENERATORS,
    # Utilities
    _make_box,
    _make_cylinder,
    _make_sphere,
    _make_cone,
    _make_beveled_box,
    _make_lathe,
    _make_torus_ring,
    _make_tapered_cylinder,
    _merge_meshes,
    _make_result,
    _compute_dimensions,
)


# ---------------------------------------------------------------------------
# Helper validation functions
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a mesh spec dict has all required fields and valid data."""
    # Required top-level keys
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "uvs" in result, f"{name}: missing 'uvs'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    # Non-empty
    assert len(verts) >= min_verts, (
        f"{name}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{name}: expected >= {min_faces} faces, got {len(faces)}"
    )

    # All vertices are 3-tuples of numbers
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    # All face indices reference valid vertices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Metadata required keys
    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{name}: metadata missing 'dimensions'"

    # Metadata consistency
    assert meta["poly_count"] == len(faces), (
        f"{name}: poly_count {meta['poly_count']} != actual {len(faces)}"
    )
    assert meta["vertex_count"] == len(verts), (
        f"{name}: vertex_count {meta['vertex_count']} != actual {len(verts)}"
    )

    # Dimensions are positive or zero
    dims = meta["dimensions"]
    assert "width" in dims and "height" in dims and "depth" in dims
    for dim_name, val in dims.items():
        assert val >= 0, f"{name}: dimension '{dim_name}' is negative: {val}"

    return True


# ---------------------------------------------------------------------------
# Utility primitive tests
# ---------------------------------------------------------------------------


class TestPrimitives:
    """Test low-level mesh primitive generators."""

    def test_make_box(self):
        verts, faces = _make_box(0, 0, 0, 1, 1, 1)
        assert len(verts) == 8
        assert len(faces) == 6
        for face in faces:
            assert len(face) == 4
            for idx in face:
                assert 0 <= idx < 8

    def test_make_box_offset(self):
        verts, faces = _make_box(0, 0, 0, 1, 1, 1, base_idx=10)
        for face in faces:
            for idx in face:
                assert 10 <= idx < 18

    def test_make_cylinder(self):
        verts, faces = _make_cylinder(0, 0, 0, 1.0, 2.0, segments=8)
        assert len(verts) == 16  # 8 bottom + 8 top
        assert len(faces) >= 8  # 8 sides + 2 caps

    def test_make_cylinder_no_caps(self):
        verts, faces = _make_cylinder(0, 0, 0, 1.0, 2.0, segments=8,
                                      cap_top=False, cap_bottom=False)
        assert len(faces) == 8  # sides only

    def test_make_sphere(self):
        verts, faces = _make_sphere(0, 0, 0, 1.0, rings=6, sectors=8)
        assert len(verts) > 10
        assert len(faces) > 10
        n = len(verts)
        for face in faces:
            for idx in face:
                assert 0 <= idx < n

    def test_make_cone(self):
        verts, faces = _make_cone(0, 0, 0, 1.0, 2.0, segments=8)
        assert len(verts) == 9  # 8 base + 1 apex
        assert len(faces) == 9  # 8 sides + 1 bottom cap

    def test_make_beveled_box(self):
        verts, faces = _make_beveled_box(0, 0, 0, 1, 1, 1, bevel=0.1)
        assert len(verts) == 24  # 8 corners * 3 verts each
        assert len(faces) == 18  # 6 main + 12 edge bevels

    def test_make_lathe(self):
        profile = [(0.5, 0), (0.5, 1), (0.3, 2)]
        verts, faces = _make_lathe(profile, segments=8)
        assert len(verts) == 24  # 3 rings * 8 segments
        assert len(faces) >= 16  # 2 rings * 8 segments

    def test_make_torus_ring(self):
        verts, faces = _make_torus_ring(0, 0, 0, 1.0, 0.2,
                                        major_segments=12, minor_segments=6)
        assert len(verts) == 72  # 12 * 6
        assert len(faces) == 72  # 12 * 6

    def test_make_tapered_cylinder(self):
        verts, faces = _make_tapered_cylinder(0, 0, 0, 1.0, 0.5, 2.0,
                                              segments=8, rings=3)
        assert len(verts) == 32  # 4 rings * 8 segments
        assert len(faces) >= 24  # 3 ring gaps * 8 segments

    def test_merge_meshes(self):
        v1, f1 = _make_box(0, 0, 0, 1, 1, 1)
        v2, f2 = _make_box(3, 0, 0, 1, 1, 1)
        merged_v, merged_f = _merge_meshes((v1, f1), (v2, f2))
        assert len(merged_v) == 16
        assert len(merged_f) == 12
        # Second set of faces should be offset
        for face in merged_f[6:]:
            for idx in face:
                assert idx >= 8

    def test_compute_dimensions(self):
        verts = [(0, 0, 0), (2, 3, 4)]
        dims = _compute_dimensions(verts)
        assert dims["width"] == 2.0
        assert dims["height"] == 3.0
        assert dims["depth"] == 4.0

    def test_compute_dimensions_empty(self):
        dims = _compute_dimensions([])
        assert dims["width"] == 0.0

    def test_make_result(self):
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        result = _make_result("Test", verts, faces, custom_key="value")
        assert result["metadata"]["name"] == "Test"
        assert result["metadata"]["poly_count"] == 1
        assert result["metadata"]["vertex_count"] == 4
        assert result["metadata"]["custom_key"] == "value"


# ---------------------------------------------------------------------------
# FURNITURE tests
# ---------------------------------------------------------------------------


class TestFurniture:
    """Test furniture mesh generators."""

    @pytest.mark.parametrize("style", ["tavern_rough", "noble_carved", "stone_slab"])
    def test_table_styles(self, style):
        result = generate_table_mesh(style=style)
        validate_mesh_spec(result, f"Table_{style}", min_verts=30, min_faces=10)

    def test_table_different_styles_different_geometry(self):
        r1 = generate_table_mesh(style="tavern_rough")
        r2 = generate_table_mesh(style="stone_slab")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    def test_table_leg_counts(self):
        r2 = generate_table_mesh(legs=2)
        r4 = generate_table_mesh(legs=4)
        # 4-leg table should have more geometry than 2-leg
        assert r4["metadata"]["vertex_count"] > r2["metadata"]["vertex_count"]

    def test_table_custom_dimensions(self):
        result = generate_table_mesh(width=2.0, height=1.2, depth=1.0)
        validate_mesh_spec(result, "Table_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 1.0  # Should be wider than default

    @pytest.mark.parametrize("style", ["wooden_bench", "throne", "stool"])
    def test_chair_styles(self, style):
        result = generate_chair_mesh(style=style)
        validate_mesh_spec(result, f"Chair_{style}", min_verts=20, min_faces=8)

    def test_chair_with_arms(self):
        r_no = generate_chair_mesh(has_arms=False)
        r_yes = generate_chair_mesh(has_arms=True)
        assert r_yes["metadata"]["vertex_count"] > r_no["metadata"]["vertex_count"]

    def test_chair_stool_no_back(self):
        result = generate_chair_mesh(style="stool", has_back=False)
        validate_mesh_spec(result, "Chair_stool")

    @pytest.mark.parametrize("tiers", [2, 3, 5])
    def test_shelf_tiers(self, tiers):
        result = generate_shelf_mesh(tiers=tiers)
        validate_mesh_spec(result, f"Shelf_{tiers}t", min_verts=20, min_faces=8)
        assert result["metadata"]["tiers"] == tiers

    def test_shelf_wall_mounted(self):
        result = generate_shelf_mesh(freestanding=False)
        validate_mesh_spec(result, "Shelf_wall")

    @pytest.mark.parametrize("style", ["wooden_bound", "iron_locked", "ornate_treasure"])
    def test_chest_styles(self, style):
        result = generate_chest_mesh(style=style)
        validate_mesh_spec(result, f"Chest_{style}", min_verts=30, min_faces=10)

    def test_chest_size_scaling(self):
        r_small = generate_chest_mesh(size=0.5)
        r_large = generate_chest_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_barrel(self):
        result = generate_barrel_mesh()
        validate_mesh_spec(result, "Barrel", min_verts=50, min_faces=20)

    def test_barrel_custom_staves(self):
        r8 = generate_barrel_mesh(staves=8)
        r24 = generate_barrel_mesh(staves=24)
        assert r24["metadata"]["vertex_count"] > r8["metadata"]["vertex_count"]

    def test_candelabra_standing(self):
        result = generate_candelabra_mesh(arms=5)
        validate_mesh_spec(result, "Candelabra_standing", min_verts=40, min_faces=15)

    def test_candelabra_wall_mounted(self):
        result = generate_candelabra_mesh(wall_mounted=True)
        validate_mesh_spec(result, "Candelabra_wall", min_verts=20, min_faces=8)

    def test_candelabra_arm_count(self):
        r3 = generate_candelabra_mesh(arms=3)
        r7 = generate_candelabra_mesh(arms=7)
        assert r7["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_bookshelf(self):
        result = generate_bookshelf_mesh(sections=3, with_books=True)
        validate_mesh_spec(result, "Bookshelf", min_verts=50, min_faces=20)

    def test_bookshelf_no_books(self):
        r_books = generate_bookshelf_mesh(with_books=True)
        r_empty = generate_bookshelf_mesh(with_books=False)
        assert r_books["metadata"]["vertex_count"] > r_empty["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# VEGETATION tests
# ---------------------------------------------------------------------------


class TestVegetation:
    """Test vegetation mesh generators."""

    @pytest.mark.parametrize("canopy", [
        "dead_twisted", "ancient_oak", "dark_pine", "willow_hanging",
    ])
    def test_tree_canopy_styles(self, canopy):
        result = generate_tree_mesh(canopy_style=canopy)
        validate_mesh_spec(result, f"Tree_{canopy}", min_verts=40, min_faces=15)

    def test_tree_different_canopies_different_geometry(self):
        r_oak = generate_tree_mesh(canopy_style="ancient_oak")
        r_pine = generate_tree_mesh(canopy_style="dark_pine")
        assert r_oak["vertices"] != r_pine["vertices"]

    def test_tree_custom_dimensions(self):
        result = generate_tree_mesh(trunk_height=5.0, trunk_radius=0.4, branch_count=12)
        validate_mesh_spec(result, "Tree_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > 3.0

    @pytest.mark.parametrize("rock_type", ["boulder", "standing_stone", "crystal", "rubble_pile"])
    def test_rock_types(self, rock_type):
        result = generate_rock_mesh(rock_type=rock_type)
        validate_mesh_spec(result, f"Rock_{rock_type}", min_verts=10, min_faces=5)

    def test_rock_detail_levels(self):
        r_low = generate_rock_mesh(detail=1)
        r_high = generate_rock_mesh(detail=5)
        assert r_high["metadata"]["vertex_count"] > r_low["metadata"]["vertex_count"]

    def test_rock_size_scaling(self):
        r_small = generate_rock_mesh(size=0.5)
        r_large = generate_rock_mesh(size=3.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    @pytest.mark.parametrize("cap_style", ["giant_cap", "cluster", "shelf_fungus"])
    def test_mushroom_styles(self, cap_style):
        result = generate_mushroom_mesh(cap_style=cap_style)
        validate_mesh_spec(result, f"Mushroom_{cap_style}", min_verts=10, min_faces=4)

    def test_roots(self):
        result = generate_root_mesh()
        validate_mesh_spec(result, "Roots", min_verts=20, min_faces=8)

    def test_roots_custom_params(self):
        result = generate_root_mesh(spread=2.5, thickness=0.12, segments=8)
        validate_mesh_spec(result, "Roots_custom")

    def test_ivy(self):
        result = generate_ivy_mesh()
        validate_mesh_spec(result, "Ivy", min_verts=20, min_faces=5)

    def test_ivy_density(self):
        r_sparse = generate_ivy_mesh(density=2)
        r_dense = generate_ivy_mesh(density=10)
        assert r_dense["metadata"]["vertex_count"] > r_sparse["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# DUNGEON PROPS tests
# ---------------------------------------------------------------------------


class TestDungeonProps:
    """Test dungeon prop mesh generators."""

    @pytest.mark.parametrize("style", ["iron_bracket", "ornate_dragon", "simple_ring"])
    def test_torch_sconce_styles(self, style):
        result = generate_torch_sconce_mesh(style=style)
        validate_mesh_spec(result, f"TorchSconce_{style}", min_verts=15, min_faces=5)

    def test_prison_door(self):
        result = generate_prison_door_mesh()
        validate_mesh_spec(result, "PrisonDoor", min_verts=40, min_faces=15)

    def test_prison_door_bar_count(self):
        r3 = generate_prison_door_mesh(bar_count=3)
        r8 = generate_prison_door_mesh(bar_count=8)
        assert r8["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["stone_plain", "ornate_carved", "dark_ritual"])
    def test_sarcophagus_styles(self, style):
        result = generate_sarcophagus_mesh(style=style)
        validate_mesh_spec(result, f"Sarcophagus_{style}", min_verts=10, min_faces=4)

    @pytest.mark.parametrize("style", ["sacrificial", "prayer", "dark_ritual"])
    def test_altar_styles(self, style):
        result = generate_altar_mesh(style=style)
        validate_mesh_spec(result, f"Altar_{style}", min_verts=20, min_faces=8)

    def test_altar_different_styles_different_geometry(self):
        r1 = generate_altar_mesh(style="sacrificial")
        r2 = generate_altar_mesh(style="dark_ritual")
        assert r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["stone_round", "stone_square", "carved_serpent"])
    def test_pillar_styles(self, style):
        result = generate_pillar_mesh(style=style)
        validate_mesh_spec(result, f"Pillar_{style}", min_verts=20, min_faces=8)

    def test_pillar_height(self):
        r_short = generate_pillar_mesh(height=1.0)
        r_tall = generate_pillar_mesh(height=5.0)
        d_short = r_short["metadata"]["dimensions"]
        d_tall = r_tall["metadata"]["dimensions"]
        assert d_tall["height"] > d_short["height"]

    def test_archway(self):
        result = generate_archway_mesh()
        validate_mesh_spec(result, "Archway", min_verts=30, min_faces=10)

    def test_archway_dimensions(self):
        result = generate_archway_mesh(width=2.0, height=3.5, depth=0.6)
        validate_mesh_spec(result, "Archway_custom")

    def test_chain(self):
        result = generate_chain_mesh(links=6)
        validate_mesh_spec(result, "Chain", min_verts=20, min_faces=10)

    def test_chain_link_count(self):
        r4 = generate_chain_mesh(links=4)
        r12 = generate_chain_mesh(links=12)
        assert r12["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_skull_pile(self):
        result = generate_skull_pile_mesh(count=5)
        validate_mesh_spec(result, "SkullPile", min_verts=30, min_faces=15)

    def test_skull_pile_count(self):
        r3 = generate_skull_pile_mesh(count=3)
        r10 = generate_skull_pile_mesh(count=10)
        assert r10["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    # --- Pillar expanded styles ---

    @pytest.mark.parametrize("style", ["stone_round", "stone_square", "carved_serpent", "wooden", "broken"])
    def test_pillar_all_styles(self, style):
        result = generate_pillar_mesh(style=style)
        validate_mesh_spec(result, f"Pillar_{style}", min_verts=20, min_faces=6)

    def test_pillar_wooden_vs_stone(self):
        r1 = generate_pillar_mesh(style="wooden")
        r2 = generate_pillar_mesh(style="stone_round")
        assert r1["vertices"] != r2["vertices"]

    def test_pillar_broken_has_rubble(self):
        r = generate_pillar_mesh(style="broken")
        validate_mesh_spec(r, "Pillar_broken", min_verts=30, min_faces=10)

    # --- Archway expanded styles ---

    @pytest.mark.parametrize("style", ["stone_round", "stone_pointed", "wooden", "ruined"])
    def test_archway_all_styles(self, style):
        result = generate_archway_mesh(style=style)
        validate_mesh_spec(result, f"Archway_{style}", min_verts=20, min_faces=6)

    def test_archway_styles_differ(self):
        r1 = generate_archway_mesh(style="stone_round")
        r2 = generate_archway_mesh(style="stone_pointed")
        r3 = generate_archway_mesh(style="wooden")
        assert r1["vertices"] != r2["vertices"]
        assert r1["vertices"] != r3["vertices"]

    # --- Portcullis ---

    def test_portcullis(self):
        result = generate_portcullis_mesh()
        validate_mesh_spec(result, "Portcullis", min_verts=50, min_faces=15)

    def test_portcullis_custom_size(self):
        result = generate_portcullis_mesh(width=3.0, height=3.5)
        validate_mesh_spec(result, "Portcullis_large")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 2.0

    # --- Iron Gate ---

    @pytest.mark.parametrize("style", ["barred", "solid", "ornate"])
    def test_iron_gate_styles(self, style):
        result = generate_iron_gate_mesh(style=style)
        validate_mesh_spec(result, f"IronGate_{style}", min_verts=30, min_faces=8)

    def test_iron_gate_styles_differ(self):
        r1 = generate_iron_gate_mesh(style="barred")
        r2 = generate_iron_gate_mesh(style="solid")
        assert r1["vertices"] != r2["vertices"]

    # --- Bridge Plank ---

    @pytest.mark.parametrize("style", ["wooden", "stone", "rope"])
    def test_bridge_plank_styles(self, style):
        result = generate_bridge_plank_mesh(style=style)
        validate_mesh_spec(result, f"BridgePlank_{style}", min_verts=16, min_faces=4)

    def test_bridge_plank_styles_differ(self):
        r1 = generate_bridge_plank_mesh(style="wooden")
        r2 = generate_bridge_plank_mesh(style="rope")
        assert r1["vertices"] != r2["vertices"]

    # --- Shackle ---

    @pytest.mark.parametrize("style", ["wall", "floor", "hanging"])
    def test_shackle_styles(self, style):
        result = generate_shackle_mesh(style=style)
        validate_mesh_spec(result, f"Shackle_{style}", min_verts=20, min_faces=6)

    def test_shackle_styles_differ(self):
        r1 = generate_shackle_mesh(style="wall")
        r2 = generate_shackle_mesh(style="hanging")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"]

    # --- Cage ---

    @pytest.mark.parametrize("style", ["hanging", "floor", "gibbet"])
    def test_cage_styles(self, style):
        result = generate_cage_mesh(style=style)
        validate_mesh_spec(result, f"Cage_{style}", min_verts=30, min_faces=10)

    def test_cage_styles_differ(self):
        r1 = generate_cage_mesh(style="hanging")
        r2 = generate_cage_mesh(style="floor")
        r3 = generate_cage_mesh(style="gibbet")
        assert r1["vertices"] != r2["vertices"]
        assert r1["vertices"] != r3["vertices"]

    # --- Stocks ---

    def test_stocks(self):
        result = generate_stocks_mesh()
        validate_mesh_spec(result, "Stocks", min_verts=40, min_faces=10)

    # --- Iron Maiden ---

    def test_iron_maiden(self):
        result = generate_iron_maiden_mesh()
        validate_mesh_spec(result, "IronMaiden", min_verts=50, min_faces=15)

    # --- Prisoner Skeleton ---

    def test_prisoner_skeleton(self):
        result = generate_prisoner_skeleton_mesh()
        validate_mesh_spec(result, "PrisonerSkeleton", min_verts=50, min_faces=20)

    # --- Summoning Circle ---

    def test_summoning_circle(self):
        result = generate_summoning_circle_mesh()
        validate_mesh_spec(result, "SummoningCircle", min_verts=50, min_faces=20)

    def test_summoning_circle_rune_count(self):
        r4 = generate_summoning_circle_mesh(rune_count=4)
        r12 = generate_summoning_circle_mesh(rune_count=12)
        assert r12["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    # --- Ritual Candles ---

    def test_ritual_candles(self):
        result = generate_ritual_candles_mesh()
        validate_mesh_spec(result, "RitualCandles", min_verts=20, min_faces=8)

    def test_ritual_candles_count(self):
        r3 = generate_ritual_candles_mesh(count=3)
        r9 = generate_ritual_candles_mesh(count=9)
        assert r9["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    # --- Occult Symbols ---

    @pytest.mark.parametrize("symbol_type", ["pentagram", "runes", "sigil"])
    def test_occult_symbols(self, symbol_type):
        result = generate_occult_symbols_mesh(symbol_type=symbol_type)
        validate_mesh_spec(result, f"OccultSymbols_{symbol_type}", min_verts=10, min_faces=3)

    def test_occult_symbols_differ(self):
        r1 = generate_occult_symbols_mesh(symbol_type="pentagram")
        r2 = generate_occult_symbols_mesh(symbol_type="runes")
        assert r1["vertices"] != r2["vertices"]

    # --- Cobweb ---

    @pytest.mark.parametrize("style", ["corner", "spanning", "draped"])
    def test_cobweb_styles(self, style):
        result = generate_cobweb_mesh(style=style)
        validate_mesh_spec(result, f"Cobweb_{style}", min_verts=10, min_faces=3)

    def test_cobweb_styles_differ(self):
        r1 = generate_cobweb_mesh(style="corner")
        r2 = generate_cobweb_mesh(style="draped")
        assert r1["vertices"] != r2["vertices"]

    # --- Spider Egg Sac ---

    def test_spider_egg_sac(self):
        result = generate_spider_egg_sac_mesh()
        validate_mesh_spec(result, "SpiderEggSac", min_verts=20, min_faces=8)

    def test_spider_egg_sac_count(self):
        r3 = generate_spider_egg_sac_mesh(count=3)
        r8 = generate_spider_egg_sac_mesh(count=8)
        assert r8["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    # --- Rubble Pile ---

    @pytest.mark.parametrize("style", ["stone", "wood", "mixed"])
    def test_rubble_pile_styles(self, style):
        result = generate_rubble_pile_mesh(style=style)
        validate_mesh_spec(result, f"RubblePile_{style}", min_verts=20, min_faces=6)

    def test_rubble_pile_styles_differ(self):
        r1 = generate_rubble_pile_mesh(style="stone")
        r2 = generate_rubble_pile_mesh(style="wood")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    # --- Hanging Skeleton ---

    def test_hanging_skeleton(self):
        result = generate_hanging_skeleton_mesh()
        validate_mesh_spec(result, "HangingSkeleton", min_verts=50, min_faces=20)

    # --- Dripping Water ---

    def test_dripping_water(self):
        result = generate_dripping_water_mesh()
        validate_mesh_spec(result, "DrippingWater", min_verts=20, min_faces=6)

    # --- Rat Nest ---

    def test_rat_nest(self):
        result = generate_rat_nest_mesh()
        validate_mesh_spec(result, "RatNest", min_verts=20, min_faces=6)

    # --- Rotting Barrel ---

    def test_rotting_barrel(self):
        result = generate_rotting_barrel_mesh()
        validate_mesh_spec(result, "RottingBarrel", min_verts=30, min_faces=10)

    # --- Treasure Chest ---

    @pytest.mark.parametrize("style", ["locked", "open", "trapped", "ornate"])
    def test_treasure_chest_styles(self, style):
        result = generate_treasure_chest_mesh(style=style)
        validate_mesh_spec(result, f"TreasureChest_{style}", min_verts=20, min_faces=6)

    def test_treasure_chest_styles_differ(self):
        r1 = generate_treasure_chest_mesh(style="locked")
        r2 = generate_treasure_chest_mesh(style="open")
        r3 = generate_treasure_chest_mesh(style="trapped")
        assert r1["vertices"] != r2["vertices"]
        assert r1["vertices"] != r3["vertices"]

    # --- Gem Pile ---

    def test_gem_pile(self):
        result = generate_gem_pile_mesh()
        validate_mesh_spec(result, "GemPile", min_verts=10, min_faces=4)

    def test_gem_pile_count(self):
        r5 = generate_gem_pile_mesh(gem_count=5)
        r20 = generate_gem_pile_mesh(gem_count=20)
        assert r20["metadata"]["vertex_count"] > r5["metadata"]["vertex_count"]

    # --- Gold Pile ---

    def test_gold_pile(self):
        result = generate_gold_pile_mesh()
        validate_mesh_spec(result, "GoldPile", min_verts=20, min_faces=6)

    def test_gold_pile_count(self):
        r10 = generate_gold_pile_mesh(coin_count=10)
        r50 = generate_gold_pile_mesh(coin_count=50)
        assert r50["metadata"]["vertex_count"] > r10["metadata"]["vertex_count"]

    # --- Lore Tablet ---

    @pytest.mark.parametrize("style", ["stone", "clay", "obsidian"])
    def test_lore_tablet_styles(self, style):
        result = generate_lore_tablet_mesh(style=style)
        validate_mesh_spec(result, f"LoreTablet_{style}", min_verts=20, min_faces=6)

    def test_lore_tablet_styles_differ(self):
        r1 = generate_lore_tablet_mesh(style="stone")
        r2 = generate_lore_tablet_mesh(style="clay")
        assert r1["vertices"] != r2["vertices"]


# ---------------------------------------------------------------------------
# WEAPONS tests
# ---------------------------------------------------------------------------


class TestWeapons:
    """Test weapon mesh generators."""

    @pytest.mark.parametrize("head_style", ["flat", "spiked", "ornate"])
    def test_hammer_styles(self, head_style):
        result = generate_hammer_mesh(head_style=head_style)
        validate_mesh_spec(result, f"Hammer_{head_style}", min_verts=30, min_faces=10)

    def test_hammer_handle_length(self):
        r_short = generate_hammer_mesh(handle_length=0.5)
        r_long = generate_hammer_mesh(handle_length=1.5)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["height"] > d_short["height"]

    @pytest.mark.parametrize("head_style", ["leaf", "broad", "halberd"])
    def test_spear_styles(self, head_style):
        result = generate_spear_mesh(head_style=head_style)
        validate_mesh_spec(result, f"Spear_{head_style}", min_verts=20, min_faces=8)

    def test_spear_shaft_length(self):
        result = generate_spear_mesh(shaft_length=3.0)
        validate_mesh_spec(result, "Spear_long")
        assert result["metadata"]["dimensions"]["height"] > 2.0

    def test_crossbow(self):
        result = generate_crossbow_mesh()
        validate_mesh_spec(result, "Crossbow", min_verts=20, min_faces=8)

    def test_crossbow_size_scaling(self):
        r_small = generate_crossbow_mesh(size=0.5)
        r_large = generate_crossbow_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"] or \
               d_large["depth"] > d_small["depth"]

    def test_scythe(self):
        result = generate_scythe_mesh()
        validate_mesh_spec(result, "Scythe", min_verts=30, min_faces=10)

    def test_scythe_blade_curve(self):
        r1 = generate_scythe_mesh(blade_curve=0.5)
        r2 = generate_scythe_mesh(blade_curve=1.5)
        assert r1["vertices"] != r2["vertices"]

    def test_flail(self):
        result = generate_flail_mesh()
        validate_mesh_spec(result, "Flail", min_verts=30, min_faces=10)

    def test_flail_multi_head(self):
        r1 = generate_flail_mesh(head_count=1)
        r3 = generate_flail_mesh(head_count=3)
        assert r3["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]

    def test_whip(self):
        result = generate_whip_mesh()
        validate_mesh_spec(result, "Whip", min_verts=30, min_faces=10)

    def test_whip_length(self):
        r_short = generate_whip_mesh(length=1.0)
        r_long = generate_whip_mesh(length=3.0)
        d_short = r_short["metadata"]["dimensions"]
        d_long = r_long["metadata"]["dimensions"]
        assert d_long["height"] > d_short["height"]

    @pytest.mark.parametrize("fingers", [3, 4, 5])
    def test_claw_finger_count(self, fingers):
        result = generate_claw_mesh(finger_count=fingers)
        validate_mesh_spec(result, f"Claw_{fingers}f", min_verts=20, min_faces=8)

    def test_claw_different_counts_different_geometry(self):
        r3 = generate_claw_mesh(finger_count=3)
        r5 = generate_claw_mesh(finger_count=5)
        assert r5["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_tome(self):
        result = generate_tome_mesh()
        validate_mesh_spec(result, "Tome", min_verts=30, min_faces=10)

    def test_tome_page_count_affects_thickness(self):
        r_thin = generate_tome_mesh(pages=50)
        r_thick = generate_tome_mesh(pages=500)
        # Thicker tome should have different dimensions
        d_thin = r_thin["metadata"]["dimensions"]
        d_thick = r_thick["metadata"]["dimensions"]
        assert d_thick["depth"] > d_thin["depth"] or d_thick["width"] > d_thin["width"]


# ---------------------------------------------------------------------------
# ARCHITECTURE tests
# ---------------------------------------------------------------------------


class TestArchitecture:
    """Test architectural detail mesh generators."""

    @pytest.mark.parametrize("pose", ["crouching", "winged", "screaming"])
    def test_gargoyle_poses(self, pose):
        result = generate_gargoyle_mesh(pose=pose)
        validate_mesh_spec(result, f"Gargoyle_{pose}", min_verts=30, min_faces=10)

    def test_gargoyle_winged_has_more_geometry(self):
        r_crouch = generate_gargoyle_mesh(pose="crouching")
        r_wing = generate_gargoyle_mesh(pose="winged")
        assert r_wing["metadata"]["vertex_count"] > r_crouch["metadata"]["vertex_count"]

    @pytest.mark.parametrize("tiers", [1, 2, 3])
    def test_fountain_tiers(self, tiers):
        result = generate_fountain_mesh(tiers=tiers)
        validate_mesh_spec(result, f"Fountain_{tiers}t", min_verts=30, min_faces=10)

    def test_fountain_more_tiers_more_geometry(self):
        r1 = generate_fountain_mesh(tiers=1)
        r3 = generate_fountain_mesh(tiers=3)
        assert r3["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]

    @pytest.mark.parametrize("pose", ["standing", "praying", "warrior"])
    def test_statue_poses(self, pose):
        result = generate_statue_mesh(pose=pose)
        validate_mesh_spec(result, f"Statue_{pose}", min_verts=30, min_faces=10)

    def test_statue_warrior_has_weapon(self):
        r_stand = generate_statue_mesh(pose="standing")
        r_war = generate_statue_mesh(pose="warrior")
        assert r_war["metadata"]["vertex_count"] > r_stand["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["stone_arch", "rope", "drawbridge"])
    def test_bridge_styles(self, style):
        result = generate_bridge_mesh(style=style)
        validate_mesh_spec(result, f"Bridge_{style}", min_verts=20, min_faces=8)

    def test_bridge_different_styles_different_geometry(self):
        r_stone = generate_bridge_mesh(style="stone_arch")
        r_rope = generate_bridge_mesh(style="rope")
        assert r_stone["vertices"] != r_rope["vertices"]

    @pytest.mark.parametrize("style", ["portcullis", "wooden_double", "iron_grid"])
    def test_gate_styles(self, style):
        result = generate_gate_mesh(style=style)
        validate_mesh_spec(result, f"Gate_{style}", min_verts=20, min_faces=8)

    def test_gate_dimensions(self):
        result = generate_gate_mesh(width=3.0, height=4.0)
        validate_mesh_spec(result, "Gate_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 2.0 or dims["height"] > 3.0

    @pytest.mark.parametrize("direction", ["straight", "spiral"])
    def test_staircase_directions(self, direction):
        result = generate_staircase_mesh(direction=direction)
        validate_mesh_spec(result, f"Staircase_{direction}", min_verts=20, min_faces=8)

    def test_staircase_step_count(self):
        r_few = generate_staircase_mesh(steps=4)
        r_many = generate_staircase_mesh(steps=20)
        assert r_many["metadata"]["vertex_count"] > r_few["metadata"]["vertex_count"]

    def test_staircase_spiral_vs_straight(self):
        r_str = generate_staircase_mesh(direction="straight")
        r_spi = generate_staircase_mesh(direction="spiral")
        assert r_str["vertices"] != r_spi["vertices"]


# ---------------------------------------------------------------------------
# INTERIOR FURNITURE & PROPS tests
# ---------------------------------------------------------------------------


class TestInteriorFurniture:
    """Test interior furniture and prop mesh generators."""

    # --- Bed ---

    @pytest.mark.parametrize("style", ["simple", "ornate", "bedroll"])
    def test_bed_styles(self, style):
        result = generate_bed_mesh(style=style)
        validate_mesh_spec(result, f"Bed_{style}", min_verts=20, min_faces=6)

    def test_bed_different_styles_different_geometry(self):
        r1 = generate_bed_mesh(style="simple")
        r2 = generate_bed_mesh(style="ornate")
        r3 = generate_bed_mesh(style="bedroll")
        # Ornate has extra posts/headboard, so more vertices
        assert r2["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]
        # Bedroll is simpler than framed beds
        assert r3["metadata"]["vertex_count"] < r1["metadata"]["vertex_count"]

    def test_bed_custom_dimensions(self):
        result = generate_bed_mesh(width=2.5, depth=1.2, height=0.6)
        validate_mesh_spec(result, "Bed_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 1.5

    # --- Wardrobe ---

    @pytest.mark.parametrize("style", ["wooden", "ornate", "armoire"])
    def test_wardrobe_styles(self, style):
        result = generate_wardrobe_mesh(style=style)
        validate_mesh_spec(result, f"Wardrobe_{style}", min_verts=30, min_faces=10)

    def test_wardrobe_different_styles_different_geometry(self):
        r1 = generate_wardrobe_mesh(style="wooden")
        r2 = generate_wardrobe_mesh(style="ornate")
        r3 = generate_wardrobe_mesh(style="armoire")
        # Ornate and armoire have extra decoration geometry
        assert r2["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]
        assert r3["metadata"]["vertex_count"] > r1["metadata"]["vertex_count"]

    # --- Cabinet ---

    @pytest.mark.parametrize("style", ["simple", "apothecary", "display"])
    def test_cabinet_styles(self, style):
        result = generate_cabinet_mesh(style=style)
        validate_mesh_spec(result, f"Cabinet_{style}", min_verts=20, min_faces=6)

    def test_cabinet_apothecary_more_geometry(self):
        r_simple = generate_cabinet_mesh(style="simple")
        r_apoth = generate_cabinet_mesh(style="apothecary")
        # Apothecary has 20 drawer faces + knobs
        assert r_apoth["metadata"]["vertex_count"] > r_simple["metadata"]["vertex_count"]

    # --- Curtain ---

    @pytest.mark.parametrize("style", ["hanging", "gathered", "tattered"])
    def test_curtain_styles(self, style):
        result = generate_curtain_mesh(style=style)
        validate_mesh_spec(result, f"Curtain_{style}", min_verts=50, min_faces=20)

    def test_curtain_has_uvs(self):
        result = generate_curtain_mesh()
        assert len(result["uvs"]) > 0, "Curtain should have UV coordinates"

    def test_curtain_different_styles_different_geometry(self):
        r1 = generate_curtain_mesh(style="hanging")
        r2 = generate_curtain_mesh(style="gathered")
        assert r1["vertices"] != r2["vertices"]

    # --- Mirror ---

    @pytest.mark.parametrize("style", ["wall", "standing", "hand"])
    def test_mirror_styles(self, style):
        result = generate_mirror_mesh(style=style)
        validate_mesh_spec(result, f"Mirror_{style}", min_verts=10, min_faces=4)

    def test_mirror_standing_taller(self):
        r_wall = generate_mirror_mesh(style="wall")
        r_stand = generate_mirror_mesh(style="standing")
        # Standing mirror has legs and support
        assert r_stand["metadata"]["vertex_count"] > r_wall["metadata"]["vertex_count"]

    # --- Hay bale ---

    @pytest.mark.parametrize("style", ["rectangular", "round", "scattered"])
    def test_hay_bale_styles(self, style):
        result = generate_hay_bale_mesh(style=style)
        validate_mesh_spec(result, f"HayBale_{style}", min_verts=8, min_faces=4)

    def test_hay_bale_different_styles_different_geometry(self):
        r1 = generate_hay_bale_mesh(style="rectangular")
        r2 = generate_hay_bale_mesh(style="round")
        assert r1["vertices"] != r2["vertices"]

    # --- Wine rack ---

    @pytest.mark.parametrize("style", ["wall", "diamond", "barrel"])
    def test_wine_rack_styles(self, style):
        result = generate_wine_rack_mesh(style=style)
        validate_mesh_spec(result, f"WineRack_{style}", min_verts=20, min_faces=6)

    def test_wine_rack_more_slots_more_geometry(self):
        r_small = generate_wine_rack_mesh(cols=2, rows=2)
        r_large = generate_wine_rack_mesh(cols=6, rows=5)
        assert r_large["metadata"]["vertex_count"] > r_small["metadata"]["vertex_count"]

    # --- Bathtub ---

    @pytest.mark.parametrize("style", ["wooden", "metal"])
    def test_bathtub_styles(self, style):
        result = generate_bathtub_mesh(style=style)
        validate_mesh_spec(result, f"Bathtub_{style}", min_verts=30, min_faces=10)

    def test_bathtub_different_styles_different_geometry(self):
        r1 = generate_bathtub_mesh(style="wooden")
        r2 = generate_bathtub_mesh(style="metal")
        assert r1["vertices"] != r2["vertices"]

    # --- Fireplace ---

    @pytest.mark.parametrize("style", ["stone", "grand", "simple"])
    def test_fireplace_styles(self, style):
        result = generate_fireplace_mesh(style=style)
        validate_mesh_spec(result, f"Fireplace_{style}", min_verts=20, min_faces=6)

    def test_fireplace_grand_more_geometry(self):
        r_stone = generate_fireplace_mesh(style="stone")
        r_grand = generate_fireplace_mesh(style="grand")
        # Grand has columns, capitals, keystone
        assert r_grand["metadata"]["vertex_count"] > r_stone["metadata"]["vertex_count"]

    def test_fireplace_simple_less_geometry(self):
        r_simple = generate_fireplace_mesh(style="simple")
        r_stone = generate_fireplace_mesh(style="stone")
        assert r_simple["metadata"]["vertex_count"] < r_stone["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# OUTDOOR STRUCTURES & FORTIFICATIONS tests
# ---------------------------------------------------------------------------


class TestFortification:
    """Test fortification mesh generators."""

    # --- Palisade ---

    @pytest.mark.parametrize("style", ["pointed", "flat", "damaged"])
    def test_palisade_styles(self, style):
        result = generate_palisade_mesh(style=style)
        validate_mesh_spec(result, f"Palisade_{style}", min_verts=20, min_faces=10)

    def test_palisade_pointed_has_cones(self):
        r_pointed = generate_palisade_mesh(style="pointed")
        r_flat = generate_palisade_mesh(style="flat")
        # Pointed should have more geometry (cone tips)
        assert r_pointed["metadata"]["vertex_count"] > r_flat["metadata"]["vertex_count"]

    def test_palisade_damaged_less_geometry(self):
        r_pointed = generate_palisade_mesh(style="pointed")
        r_damaged = generate_palisade_mesh(style="damaged")
        # Damaged has missing/shorter logs
        assert r_damaged["metadata"]["vertex_count"] < r_pointed["metadata"]["vertex_count"]

    def test_palisade_custom_dimensions(self):
        result = generate_palisade_mesh(width=6.0, height=4.0)
        validate_mesh_spec(result, "Palisade_wide")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 4.0

    # --- Watchtower ---

    @pytest.mark.parametrize("style", ["wooden", "stone", "ruined"])
    def test_watchtower_styles(self, style):
        result = generate_watchtower_mesh(style=style)
        validate_mesh_spec(result, f"Watchtower_{style}", min_verts=40, min_faces=20)

    def test_watchtower_is_tall(self):
        result = generate_watchtower_mesh(height=8.0)
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > 5.0

    def test_watchtower_different_styles_different_geometry(self):
        r1 = generate_watchtower_mesh(style="wooden")
        r2 = generate_watchtower_mesh(style="stone")
        assert r1["vertices"] != r2["vertices"]

    # --- Battlement ---

    @pytest.mark.parametrize("style", ["stone", "weathered", "ruined"])
    def test_battlement_styles(self, style):
        result = generate_battlement_mesh(style=style)
        validate_mesh_spec(result, f"Battlement_{style}", min_verts=20, min_faces=6)

    def test_battlement_has_merlons(self):
        result = generate_battlement_mesh(style="stone", width=6.0)
        # More width = more merlons = more geometry
        r_narrow = generate_battlement_mesh(style="stone", width=2.0)
        assert result["metadata"]["vertex_count"] > r_narrow["metadata"]["vertex_count"]

    # --- Moat Edge ---

    @pytest.mark.parametrize("style", ["stone", "earth", "reinforced"])
    def test_moat_edge_styles(self, style):
        result = generate_moat_edge_mesh(style=style)
        validate_mesh_spec(result, f"MoatEdge_{style}", min_verts=20, min_faces=6)

    def test_moat_edge_stone_has_blocks(self):
        r_stone = generate_moat_edge_mesh(style="stone")
        r_earth = generate_moat_edge_mesh(style="earth")
        # Stone has wall + blocks detail, more geometry
        assert r_stone["metadata"]["vertex_count"] > r_earth["metadata"]["vertex_count"]


class TestInfrastructure:
    """Test infrastructure mesh generators."""

    # --- Windmill ---

    @pytest.mark.parametrize("style", ["wooden", "stone"])
    def test_windmill_styles(self, style):
        result = generate_windmill_mesh(style=style)
        validate_mesh_spec(result, f"Windmill_{style}", min_verts=50, min_faces=20)

    def test_windmill_is_tall(self):
        result = generate_windmill_mesh(height=10.0)
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > 6.0

    def test_windmill_stone_more_detail(self):
        r_wood = generate_windmill_mesh(style="wooden")
        r_stone = generate_windmill_mesh(style="stone")
        # Stone has torus bands, different structure
        assert r_stone["metadata"]["vertex_count"] != r_wood["metadata"]["vertex_count"]

    # --- Dock ---

    @pytest.mark.parametrize("style", ["wooden", "stone"])
    def test_dock_styles(self, style):
        result = generate_dock_mesh(style=style)
        validate_mesh_spec(result, f"Dock_{style}", min_verts=30, min_faces=10)

    def test_dock_custom_dimensions(self):
        result = generate_dock_mesh(width=5.0, length=12.0)
        validate_mesh_spec(result, "Dock_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["depth"] > 8.0  # Length maps to Z axis

    def test_dock_wooden_has_posts(self):
        r_wood = generate_dock_mesh(style="wooden")
        r_stone = generate_dock_mesh(style="stone")
        # Wooden has more individual components (posts, planks, cleats)
        assert r_wood["metadata"]["vertex_count"] > r_stone["metadata"]["vertex_count"]

    # --- Stone Bridge ---

    @pytest.mark.parametrize("style", ["arch", "multi_arch", "flat"])
    def test_bridge_stone_styles(self, style):
        result = generate_bridge_stone_mesh(style=style)
        validate_mesh_spec(result, f"StoneBridge_{style}", min_verts=40, min_faces=15)

    def test_bridge_stone_arch_has_curves(self):
        result = generate_bridge_stone_mesh(style="arch", span=10.0)
        # Arch bridge should have significant vertex count for curved geometry
        assert result["metadata"]["vertex_count"] > 200

    def test_bridge_stone_different_styles_different_geometry(self):
        r1 = generate_bridge_stone_mesh(style="arch")
        r2 = generate_bridge_stone_mesh(style="flat")
        assert r1["vertices"] != r2["vertices"]

    # --- Rope Bridge ---

    @pytest.mark.parametrize("style", ["simple", "sturdy", "damaged"])
    def test_rope_bridge_styles(self, style):
        result = generate_rope_bridge_mesh(style=style)
        validate_mesh_spec(result, f"RopeBridge_{style}", min_verts=30, min_faces=10)

    def test_rope_bridge_damaged_fewer_planks(self):
        r_simple = generate_rope_bridge_mesh(style="simple")
        r_damaged = generate_rope_bridge_mesh(style="damaged")
        # Damaged has missing planks
        assert r_damaged["metadata"]["vertex_count"] < r_simple["metadata"]["vertex_count"]

    def test_rope_bridge_sturdy_reinforced(self):
        r_simple = generate_rope_bridge_mesh(style="simple")
        r_sturdy = generate_rope_bridge_mesh(style="sturdy")
        # Sturdy has thicker planks, double rails, cross-bracing
        assert r_sturdy["metadata"]["poly_count"] != r_simple["metadata"]["poly_count"]


class TestCamp:
    """Test camp/settlement mesh generators."""

    # --- Tent ---

    @pytest.mark.parametrize("style", ["small", "large", "command"])
    def test_tent_styles(self, style):
        result = generate_tent_mesh(style=style)
        validate_mesh_spec(result, f"Tent_{style}", min_verts=10, min_faces=4)

    def test_tent_small_is_smallest(self):
        r_small = generate_tent_mesh(style="small")
        r_large = generate_tent_mesh(style="large")
        r_cmd = generate_tent_mesh(style="command")
        assert r_small["metadata"]["vertex_count"] < r_large["metadata"]["vertex_count"]
        assert r_large["metadata"]["vertex_count"] < r_cmd["metadata"]["vertex_count"]

    def test_tent_command_is_wide(self):
        result = generate_tent_mesh(style="command")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 3.0
        assert dims["depth"] > 4.0

    # --- Hitching Post ---

    @pytest.mark.parametrize("style", ["wooden", "iron"])
    def test_hitching_post_styles(self, style):
        result = generate_hitching_post_mesh(style=style)
        validate_mesh_spec(result, f"HitchingPost_{style}", min_verts=20, min_faces=10)

    def test_hitching_post_has_rope_loops(self):
        result = generate_hitching_post_mesh(style="wooden")
        # Torus rings for rope loops add significant geometry
        assert result["metadata"]["vertex_count"] > 100

    # --- Feeding Trough ---

    @pytest.mark.parametrize("style", ["wooden", "stone"])
    def test_feeding_trough_styles(self, style):
        result = generate_feeding_trough_mesh(style=style)
        validate_mesh_spec(result, f"FeedingTrough_{style}", min_verts=16, min_faces=6)

    def test_feeding_trough_wooden_has_legs(self):
        r_wood = generate_feeding_trough_mesh(style="wooden")
        r_stone = generate_feeding_trough_mesh(style="stone")
        # Wooden has 4 legs, more geometry
        assert r_wood["metadata"]["vertex_count"] > r_stone["metadata"]["vertex_count"]

    # --- Barricade Outdoor ---

    @pytest.mark.parametrize("style", ["wooden", "sandbag", "rubble"])
    def test_barricade_outdoor_styles(self, style):
        result = generate_barricade_outdoor_mesh(style=style)
        validate_mesh_spec(result, f"BarricadeOutdoor_{style}", min_verts=20, min_faces=6)

    def test_barricade_outdoor_different_styles_different_geometry(self):
        r1 = generate_barricade_outdoor_mesh(style="wooden")
        r2 = generate_barricade_outdoor_mesh(style="sandbag")
        r3 = generate_barricade_outdoor_mesh(style="rubble")
        # All three styles produce different geometry
        verts = {len(r1["vertices"]), len(r2["vertices"]), len(r3["vertices"])}
        assert len(verts) == 3

    def test_barricade_outdoor_custom_dimensions(self):
        result = generate_barricade_outdoor_mesh(width=4.0, height=2.0)
        validate_mesh_spec(result, "BarricadeOutdoor_custom")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > 2.0

    # --- Lookout Post ---

    @pytest.mark.parametrize("style", ["raised", "ground"])
    def test_lookout_post_styles(self, style):
        result = generate_lookout_post_mesh(style=style)
        validate_mesh_spec(result, f"LookoutPost_{style}", min_verts=16, min_faces=6)

    def test_lookout_post_raised_is_tall(self):
        result = generate_lookout_post_mesh(style="raised")
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > 3.0

    def test_lookout_post_raised_more_geometry(self):
        r_raised = generate_lookout_post_mesh(style="raised")
        r_ground = generate_lookout_post_mesh(style="ground")
        assert r_raised["metadata"]["vertex_count"] > r_ground["metadata"]["vertex_count"]

    # --- Spike Fence ---

    @pytest.mark.parametrize("style", ["iron", "wood"])
    def test_spike_fence_styles(self, style):
        result = generate_spike_fence_mesh(style=style)
        validate_mesh_spec(result, f"SpikeFence_{style}", min_verts=30, min_faces=10)

    def test_spike_fence_iron_has_finials(self):
        r_iron = generate_spike_fence_mesh(style="iron")
        r_wood = generate_spike_fence_mesh(style="wood")
        # Iron has finials, decorative scrolls, more detail
        assert r_iron["metadata"]["vertex_count"] > r_wood["metadata"]["vertex_count"]

    def test_spike_fence_custom_length(self):
        r_short = generate_spike_fence_mesh(length=2.0)
        r_long = generate_spike_fence_mesh(length=6.0)
        # Longer fence has more spikes
        assert r_long["metadata"]["vertex_count"] > r_short["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Test the GENERATORS registry."""

    def test_registry_has_all_categories(self):
        expected = {
            "furniture", "vegetation", "dungeon_prop", "weapon", "architecture",
            "fence_barrier", "trap", "vehicle", "structural", "dark_fantasy",
            "container", "light_source", "door_window", "wall_decor",
            "crafting", "sign", "natural",
            "monster_part", "monster_body", "projectile", "armor",
            "fortification", "infrastructure", "camp",
            "consumable", "crafting_material", "currency", "key_item",
            "domestic_animals", "forest_animals", "mountain_animals",
            "swamp_animals", "vermin",
        }
        assert set(GENERATORS.keys()) == expected

    def test_registry_furniture_count(self):
        assert len(GENERATORS["furniture"]) == 16

    def test_registry_vegetation_count(self):
        assert len(GENERATORS["vegetation"]) == 5

    def test_registry_dungeon_prop_count(self):
        assert len(GENERATORS["dungeon_prop"]) >= 8

    def test_registry_weapon_count(self):
        assert len(GENERATORS["weapon"]) >= 8

    def test_registry_architecture_count(self):
        assert len(GENERATORS["architecture"]) >= 6

    def test_all_registry_functions_callable(self):
        """Every function in the registry should be callable and return valid mesh."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                validate_mesh_spec(result, f"{category}/{name}")

    def test_total_generator_count(self):
        total = sum(len(g) for g in GENERATORS.values())
        assert total >= 169

    def test_registry_fortification_count(self):
        assert len(GENERATORS["fortification"]) == 4

    def test_registry_infrastructure_count(self):
        assert len(GENERATORS["infrastructure"]) == 4

    def test_registry_camp_count(self):
        assert len(GENERATORS["camp"]) == 6

    def test_registry_consumable_count(self):
        assert len(GENERATORS["consumable"]) == 9

    def test_registry_crafting_material_count(self):
        assert len(GENERATORS["crafting_material"]) == 5

    def test_registry_currency_count(self):
        assert len(GENERATORS["currency"]) == 2

    def test_registry_key_item_count(self):
        assert len(GENERATORS["key_item"]) == 3


# ---------------------------------------------------------------------------
# CROSS-CUTTING tests
# ---------------------------------------------------------------------------


class TestCrossCutting:
    """Tests that span multiple categories."""

    def test_all_generators_return_dicts(self):
        """Every generator returns a dict."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                assert isinstance(result, dict), f"{category}/{name} did not return dict"

    def test_no_nan_vertices(self):
        """No generator should produce NaN or inf vertices."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                for vi, v in enumerate(result["vertices"]):
                    for ci, c in enumerate(v):
                        assert not (c != c), f"{category}/{name}: NaN at vertex {vi}[{ci}]"
                        assert abs(c) < 1e6, f"{category}/{name}: huge value at vertex {vi}[{ci}]"

    def test_no_degenerate_faces(self):
        """No face should reference the same vertex twice."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                for fi, face in enumerate(result["faces"]):
                    # Check that face has at least 3 unique indices
                    unique = set(face)
                    assert len(unique) >= 3, (
                        f"{category}/{name}: degenerate face {fi} with only "
                        f"{len(unique)} unique vertices: {face}"
                    )

    def test_metadata_category_present(self):
        """All generators should include a category in metadata."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                meta = result["metadata"]
                assert "category" in meta or "style" in meta or "name" in meta, (
                    f"{category}/{name}: no identifying metadata"
                )

    def test_reasonable_poly_counts(self):
        """No generator should produce unreasonably high poly counts for props."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                pc = result["metadata"]["poly_count"]
                # Props should stay under 50k polys
                assert pc < 50000, f"{category}/{name}: {pc} polys is excessive"
                # But should have at least some faces
                assert pc >= 1, f"{category}/{name}: 0 polys"


# ---------------------------------------------------------------------------
# CONSUMABLE tests
# ---------------------------------------------------------------------------


class TestConsumables:
    """Test consumable item mesh generators."""

    # --- Health Potion ---

    @pytest.mark.parametrize("style", ["small", "medium", "large"])
    def test_health_potion_styles(self, style):
        result = generate_health_potion_mesh(style=style)
        validate_mesh_spec(result, f"HealthPotion_{style}", min_verts=10, min_faces=4)

    def test_health_potion_sizes_differ(self):
        r_small = generate_health_potion_mesh(style="small")
        r_med = generate_health_potion_mesh(style="medium")
        r_large = generate_health_potion_mesh(style="large")
        # Larger potions should be physically bigger
        d_small = r_small["metadata"]["dimensions"]["height"]
        d_med = r_med["metadata"]["dimensions"]["height"]
        d_large = r_large["metadata"]["dimensions"]["height"]
        assert d_small < d_med < d_large

    def test_health_potion_has_cork(self):
        result = generate_health_potion_mesh(style="small")
        # Cork adds extra geometry beyond the bottle body
        assert result["metadata"]["vertex_count"] > 20

    def test_health_potion_category(self):
        result = generate_health_potion_mesh()
        assert result["metadata"]["category"] == "consumable"

    # --- Mana Potion ---

    @pytest.mark.parametrize("style", ["small", "medium", "large"])
    def test_mana_potion_styles(self, style):
        result = generate_mana_potion_mesh(style=style)
        validate_mesh_spec(result, f"ManaPotion_{style}", min_verts=10, min_faces=4)

    def test_mana_potion_has_ornate_detail(self):
        # Mana potions have cone top + torus ring for decoration
        r_mana = generate_mana_potion_mesh(style="small")
        # Should have meaningful geometry (cone + ring + lathe body)
        assert r_mana["metadata"]["vertex_count"] > 50

    def test_mana_potion_category(self):
        result = generate_mana_potion_mesh()
        assert result["metadata"]["category"] == "consumable"

    # --- Antidote ---

    @pytest.mark.parametrize("style", ["vial", "ampoule", "flask"])
    def test_antidote_styles(self, style):
        result = generate_antidote_mesh(style=style)
        validate_mesh_spec(result, f"Antidote_{style}", min_verts=10, min_faces=4)

    def test_antidote_vial_has_wax_seal(self):
        r_vial = generate_antidote_mesh(style="vial")
        r_ampoule = generate_antidote_mesh(style="ampoule")
        # Vial has wax seal cylinder, ampoule does not
        assert r_vial["metadata"]["vertex_count"] > r_ampoule["metadata"]["vertex_count"]

    def test_antidote_styles_differ(self):
        r1 = generate_antidote_mesh(style="vial")
        r2 = generate_antidote_mesh(style="ampoule")
        r3 = generate_antidote_mesh(style="flask")
        verts = {r1["metadata"]["vertex_count"],
                 r2["metadata"]["vertex_count"],
                 r3["metadata"]["vertex_count"]}
        assert len(verts) >= 2  # At least 2 different vertex counts

    # --- Bread ---

    @pytest.mark.parametrize("style", ["loaf", "roll", "flatbread"])
    def test_bread_styles(self, style):
        result = generate_bread_mesh(style=style)
        validate_mesh_spec(result, f"Bread_{style}", min_verts=4, min_faces=1)

    def test_bread_loaf_has_score_marks(self):
        result = generate_bread_mesh(style="loaf")
        # Loaf has 3 score mark boxes + sphere body
        assert result["metadata"]["vertex_count"] > 30

    def test_bread_flatbread_is_flat(self):
        result = generate_bread_mesh(style="flatbread")
        dims = result["metadata"]["dimensions"]
        assert dims["height"] < dims["width"]

    # --- Cheese ---

    @pytest.mark.parametrize("style", ["wheel", "wedge", "block"])
    def test_cheese_styles(self, style):
        result = generate_cheese_mesh(style=style)
        validate_mesh_spec(result, f"Cheese_{style}", min_verts=4, min_faces=1)

    def test_cheese_wheel_has_rind_ring(self):
        result = generate_cheese_mesh(style="wheel")
        # Cylinder + torus ring for rind = more geometry
        assert result["metadata"]["vertex_count"] > 30

    def test_cheese_wedge_is_triangular(self):
        result = generate_cheese_mesh(style="wedge")
        # Wedge has only 6 vertices (triangular prism)
        assert result["metadata"]["vertex_count"] == 6

    # --- Meat ---

    @pytest.mark.parametrize("style", ["drumstick", "steak", "ham"])
    def test_meat_styles(self, style):
        result = generate_meat_mesh(style=style)
        validate_mesh_spec(result, f"Meat_{style}", min_verts=10, min_faces=4)

    def test_meat_drumstick_has_bone(self):
        result = generate_meat_mesh(style="drumstick")
        # Cylinder bone + knob sphere + meat sphere
        assert result["metadata"]["vertex_count"] > 30

    def test_meat_styles_produce_different_geometry(self):
        r1 = generate_meat_mesh(style="drumstick")
        r2 = generate_meat_mesh(style="steak")
        r3 = generate_meat_mesh(style="ham")
        verts = {r1["metadata"]["vertex_count"],
                 r2["metadata"]["vertex_count"],
                 r3["metadata"]["vertex_count"]}
        assert len(verts) == 3

    # --- Apple ---

    @pytest.mark.parametrize("style", ["whole", "bitten", "rotten"])
    def test_apple_styles(self, style):
        result = generate_apple_mesh(style=style)
        validate_mesh_spec(result, f"Apple_{style}", min_verts=10, min_faces=4)

    def test_apple_whole_has_stem_and_leaf(self):
        result = generate_apple_mesh(style="whole")
        # Body + stem cylinder + leaf box
        assert result["metadata"]["vertex_count"] > 30

    def test_apple_bitten_has_bite_sphere(self):
        r_whole = generate_apple_mesh(style="whole")
        r_bitten = generate_apple_mesh(style="bitten")
        # Bitten adds a subtraction sphere
        assert r_bitten["metadata"]["vertex_count"] > r_whole["metadata"]["vertex_count"]

    # --- Mushroom Food ---

    @pytest.mark.parametrize("style", ["cap", "cluster"])
    def test_mushroom_food_styles(self, style):
        result = generate_mushroom_food_mesh(style=style)
        validate_mesh_spec(result, f"MushroomFood_{style}", min_verts=10, min_faces=4)

    def test_mushroom_food_cluster_has_more_geometry(self):
        r_single = generate_mushroom_food_mesh(style="cap")
        r_cluster = generate_mushroom_food_mesh(style="cluster")
        assert r_cluster["metadata"]["vertex_count"] > r_single["metadata"]["vertex_count"]

    # --- Fish ---

    @pytest.mark.parametrize("style", ["whole", "fillet"])
    def test_fish_styles(self, style):
        result = generate_fish_mesh(style=style)
        validate_mesh_spec(result, f"Fish_{style}", min_verts=4, min_faces=1)

    def test_fish_whole_has_tail_and_fin(self):
        result = generate_fish_mesh(style="whole")
        # Body lathe + tail quad + dorsal fin tri + eye sphere
        assert result["metadata"]["vertex_count"] > 40

    def test_fish_whole_more_complex_than_fillet(self):
        r_whole = generate_fish_mesh(style="whole")
        r_fillet = generate_fish_mesh(style="fillet")
        assert r_whole["metadata"]["vertex_count"] > r_fillet["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# CRAFTING MATERIAL tests
# ---------------------------------------------------------------------------


class TestCraftingMaterials:
    """Test crafting material mesh generators."""

    # --- Ore ---

    @pytest.mark.parametrize("style", ["iron", "copper", "gold", "dark_crystal"])
    def test_ore_styles(self, style):
        result = generate_ore_mesh(style=style)
        validate_mesh_spec(result, f"Ore_{style}", min_verts=10, min_faces=4)

    def test_ore_dark_crystal_has_spikes(self):
        r_crystal = generate_ore_mesh(style="dark_crystal")
        r_iron = generate_ore_mesh(style="iron")
        # Dark crystal has 4 tapered cylinders + base sphere
        assert r_crystal["metadata"]["vertex_count"] > r_iron["metadata"]["vertex_count"]

    def test_ore_category(self):
        result = generate_ore_mesh()
        assert result["metadata"]["category"] == "crafting_material"

    def test_ore_styles_differ(self):
        results = {s: generate_ore_mesh(style=s) for s in ["iron", "copper", "gold", "dark_crystal"]}
        vert_counts = {s: r["metadata"]["vertex_count"] for s, r in results.items()}
        # Dark crystal should differ from the metallic ores
        assert vert_counts["dark_crystal"] != vert_counts["iron"]

    # --- Leather ---

    @pytest.mark.parametrize("style", ["folded", "strip", "hide"])
    def test_leather_styles(self, style):
        result = generate_leather_mesh(style=style)
        validate_mesh_spec(result, f"Leather_{style}", min_verts=4, min_faces=1)

    def test_leather_folded_has_layers(self):
        result = generate_leather_mesh(style="folded")
        # 3 folded layers, each a beveled box (24 verts)
        assert result["metadata"]["vertex_count"] >= 60

    def test_leather_strip_is_long(self):
        result = generate_leather_mesh(style="strip")
        dims = result["metadata"]["dimensions"]
        assert dims["depth"] > dims["width"]

    # --- Herb ---

    @pytest.mark.parametrize("style", ["leaf", "bundle", "flower"])
    def test_herb_styles(self, style):
        result = generate_herb_mesh(style=style)
        validate_mesh_spec(result, f"Herb_{style}", min_verts=4, min_faces=1)

    def test_herb_bundle_has_more_geometry(self):
        r_leaf = generate_herb_mesh(style="leaf")
        r_bundle = generate_herb_mesh(style="bundle")
        assert r_bundle["metadata"]["vertex_count"] > r_leaf["metadata"]["vertex_count"]

    def test_herb_flower_has_petals(self):
        result = generate_herb_mesh(style="flower")
        # Stem + 5 petals + center sphere
        assert result["metadata"]["vertex_count"] > 20

    # --- Gem ---

    @pytest.mark.parametrize("style", ["ruby", "sapphire", "emerald", "diamond", "amethyst"])
    def test_gem_styles(self, style):
        result = generate_gem_mesh(style=style)
        validate_mesh_spec(result, f"Gem_{style}", min_verts=8, min_faces=4)

    def test_gem_has_faceted_structure(self):
        result = generate_gem_mesh(style="diamond")
        # 8 table verts + 8 girdle verts + 1 culet = 17
        assert result["metadata"]["vertex_count"] == 17

    def test_gem_category(self):
        result = generate_gem_mesh()
        assert result["metadata"]["category"] == "crafting_material"

    def test_gem_is_small(self):
        result = generate_gem_mesh(style="ruby")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] < 0.05
        assert dims["height"] < 0.05

    # --- Bone Shard ---

    @pytest.mark.parametrize("style", ["fragment", "fang", "horn"])
    def test_bone_shard_styles(self, style):
        result = generate_bone_shard_mesh(style=style)
        validate_mesh_spec(result, f"BoneShard_{style}", min_verts=10, min_faces=4)

    def test_bone_shard_horn_is_tallest(self):
        r_frag = generate_bone_shard_mesh(style="fragment")
        r_horn = generate_bone_shard_mesh(style="horn")
        assert r_horn["metadata"]["dimensions"]["height"] > r_frag["metadata"]["dimensions"]["height"]

    def test_bone_shard_fang_has_root(self):
        result = generate_bone_shard_mesh(style="fang")
        # Lathe body + root sphere
        assert result["metadata"]["vertex_count"] > 30


# ---------------------------------------------------------------------------
# CURRENCY tests
# ---------------------------------------------------------------------------


class TestCurrency:
    """Test currency mesh generators."""

    # --- Coin ---

    @pytest.mark.parametrize("style", ["copper", "silver", "gold"])
    def test_coin_styles(self, style):
        result = generate_coin_mesh(style=style)
        validate_mesh_spec(result, f"Coin_{style}", min_verts=16, min_faces=4)

    def test_coin_gold_is_largest(self):
        r_copper = generate_coin_mesh(style="copper")
        r_gold = generate_coin_mesh(style="gold")
        assert r_gold["metadata"]["dimensions"]["width"] > r_copper["metadata"]["dimensions"]["width"]

    def test_coin_has_embossed_detail(self):
        result = generate_coin_mesh(style="gold")
        # Disc + rim torus + top emboss + bottom emboss
        assert result["metadata"]["vertex_count"] > 50

    def test_coin_category(self):
        result = generate_coin_mesh()
        assert result["metadata"]["category"] == "currency"

    # --- Coin Pouch ---

    @pytest.mark.parametrize("style", ["small", "large"])
    def test_coin_pouch_styles(self, style):
        result = generate_coin_pouch_mesh(style=style)
        validate_mesh_spec(result, f"CoinPouch_{style}", min_verts=10, min_faces=4)

    def test_coin_pouch_large_is_bigger(self):
        r_small = generate_coin_pouch_mesh(style="small")
        r_large = generate_coin_pouch_mesh(style="large")
        assert r_large["metadata"]["dimensions"]["height"] > r_small["metadata"]["dimensions"]["height"]
        assert r_large["metadata"]["dimensions"]["width"] > r_small["metadata"]["dimensions"]["width"]

    def test_coin_pouch_large_has_spilled_coins(self):
        result = generate_coin_pouch_mesh(style="large")
        # Large pouch has 3 spilled coin cylinders
        assert result["metadata"]["vertex_count"] > 100


# ---------------------------------------------------------------------------
# KEY ITEM tests
# ---------------------------------------------------------------------------


class TestKeyItems:
    """Test key item mesh generators."""

    # --- Key ---

    @pytest.mark.parametrize("style", ["skeleton", "dungeon", "master"])
    def test_key_styles(self, style):
        result = generate_key_mesh(style=style)
        validate_mesh_spec(result, f"Key_{style}", min_verts=10, min_faces=4)

    def test_key_master_most_complex(self):
        r_skeleton = generate_key_mesh(style="skeleton")
        r_master = generate_key_mesh(style="master")
        # Master key has double torus + notches + 4 teeth
        assert r_master["metadata"]["vertex_count"] > r_skeleton["metadata"]["vertex_count"]

    def test_key_category(self):
        result = generate_key_mesh()
        assert result["metadata"]["category"] == "key_item"

    def test_key_skeleton_has_teeth(self):
        result = generate_key_mesh(style="skeleton")
        # Bow torus + shaft box + 3 teeth boxes + decoration sphere
        assert result["metadata"]["vertex_count"] > 50

    # --- Map Scroll ---

    @pytest.mark.parametrize("style", ["rolled", "open", "sealed"])
    def test_map_scroll_styles(self, style):
        result = generate_map_scroll_mesh(style=style)
        validate_mesh_spec(result, f"MapScroll_{style}", min_verts=10, min_faces=4)

    def test_map_scroll_open_is_flat(self):
        result = generate_map_scroll_mesh(style="open")
        dims = result["metadata"]["dimensions"]
        assert dims["width"] > dims["height"]

    def test_map_scroll_sealed_has_wax(self):
        r_rolled = generate_map_scroll_mesh(style="rolled")
        r_sealed = generate_map_scroll_mesh(style="sealed")
        # Sealed has wax seal + emblem + ribbon, similar complexity
        assert r_sealed["metadata"]["vertex_count"] > 20

    def test_map_scroll_styles_differ(self):
        r1 = generate_map_scroll_mesh(style="rolled")
        r2 = generate_map_scroll_mesh(style="open")
        r3 = generate_map_scroll_mesh(style="sealed")
        verts = {r1["metadata"]["vertex_count"],
                 r2["metadata"]["vertex_count"],
                 r3["metadata"]["vertex_count"]}
        assert len(verts) >= 2

    # --- Lockpick ---

    @pytest.mark.parametrize("style", ["set", "single", "skeleton_key"])
    def test_lockpick_styles(self, style):
        result = generate_lockpick_mesh(style=style)
        validate_mesh_spec(result, f"Lockpick_{style}", min_verts=4, min_faces=1)

    def test_lockpick_set_has_multiple_picks(self):
        r_set = generate_lockpick_mesh(style="set")
        r_single = generate_lockpick_mesh(style="single")
        # Set has 5 picks + roll + tie, much more geometry
        assert r_set["metadata"]["vertex_count"] > r_single["metadata"]["vertex_count"] * 2

    def test_lockpick_category(self):
        result = generate_lockpick_mesh()
        assert result["metadata"]["category"] == "key_item"

    def test_lockpick_set_has_roll(self):
        result = generate_lockpick_mesh(style="set")
        # Roll base + 5 shafts + 5 tips + 5 handles + tie
        assert result["metadata"]["vertex_count"] > 80


# ---------------------------------------------------------------------------
# ITEM POLY BUDGET tests
# ---------------------------------------------------------------------------


class TestItemPolyBudgets:
    """Verify all item generators stay within the 200-1500 tri budget."""

    @pytest.mark.parametrize("gen_func,name", [
        (generate_health_potion_mesh, "health_potion"),
        (generate_mana_potion_mesh, "mana_potion"),
        (generate_antidote_mesh, "antidote"),
        (generate_bread_mesh, "bread"),
        (generate_cheese_mesh, "cheese"),
        (generate_meat_mesh, "meat"),
        (generate_apple_mesh, "apple"),
        (generate_mushroom_food_mesh, "mushroom_food"),
        (generate_fish_mesh, "fish"),
        (generate_ore_mesh, "ore"),
        (generate_leather_mesh, "leather"),
        (generate_herb_mesh, "herb"),
        (generate_gem_mesh, "gem"),
        (generate_bone_shard_mesh, "bone_shard"),
        (generate_coin_mesh, "coin"),
        (generate_coin_pouch_mesh, "coin_pouch"),
        (generate_key_mesh, "key"),
        (generate_map_scroll_mesh, "map_scroll"),
        (generate_lockpick_mesh, "lockpick"),
    ])
    def test_item_under_1500_faces(self, gen_func, name):
        result = gen_func()
        pc = result["metadata"]["poly_count"]
        assert pc <= 1500, f"{name}: {pc} faces exceeds 1500 budget"
        assert pc >= 1, f"{name}: 0 faces"
