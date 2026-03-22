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
        }
        assert set(GENERATORS.keys()) == expected

    def test_registry_furniture_count(self):
        assert len(GENERATORS["furniture"]) == 16

    def test_registry_vegetation_count(self):
        assert len(GENERATORS["vegetation"]) == 5

    def test_registry_dungeon_prop_count(self):
        assert len(GENERATORS["dungeon_prop"]) == 8

    def test_registry_weapon_count(self):
        assert len(GENERATORS["weapon"]) == 8

    def test_registry_architecture_count(self):
        assert len(GENERATORS["architecture"]) == 6

    def test_all_registry_functions_callable(self):
        """Every function in the registry should be callable and return valid mesh."""
        for category, generators in GENERATORS.items():
            for name, func in generators.items():
                result = func()
                validate_mesh_spec(result, f"{category}/{name}")

    def test_total_generator_count(self):
        total = sum(len(g) for g in GENERATORS.values())
        assert total == 136


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
