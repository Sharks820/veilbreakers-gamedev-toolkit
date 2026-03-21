"""Tests for RPG world object procedural mesh generators (categories 10-16).

Validates that every new generator function returns valid mesh data:
- Non-empty vertex and face lists
- All face indices reference valid vertices
- Reasonable vertex/face counts for the object type
- Required metadata keys present
- Different styles/params produce different geometry
"""

from __future__ import annotations

import pytest

from blender_addon.handlers.procedural_meshes import (
    # Category 10: Containers & Loot
    generate_urn_mesh,
    generate_crate_mesh,
    generate_sack_mesh,
    generate_basket_mesh,
    generate_treasure_pile_mesh,
    generate_potion_bottle_mesh,
    generate_scroll_mesh,
    # Category 11: Light Sources
    generate_lantern_mesh,
    generate_brazier_mesh,
    generate_campfire_mesh,
    generate_crystal_light_mesh,
    generate_magic_orb_light_mesh,
    # Category 12: Doors & Windows
    generate_door_mesh,
    generate_window_mesh,
    generate_trapdoor_mesh,
    # Category 13: Wall & Floor Decorations
    generate_banner_mesh,
    generate_wall_shield_mesh,
    generate_mounted_head_mesh,
    generate_painting_frame_mesh,
    generate_rug_mesh,
    generate_chandelier_mesh,
    generate_hanging_cage_mesh,
    # Category 14: Crafting & Trade
    generate_anvil_mesh,
    generate_forge_mesh,
    generate_workbench_mesh,
    generate_cauldron_mesh,
    generate_grinding_wheel_mesh,
    generate_loom_mesh,
    generate_market_stall_mesh,
    # Category 15: Signs & Markers
    generate_signpost_mesh,
    generate_gravestone_mesh,
    generate_waystone_mesh,
    generate_milestone_mesh,
    # Category 16: Natural Formations
    generate_stalactite_mesh,
    generate_stalagmite_mesh,
    generate_bone_pile_mesh,
    generate_nest_mesh,
    generate_geyser_vent_mesh,
    generate_fallen_log_mesh,
    # Registry
    GENERATORS,
)


# ---------------------------------------------------------------------------
# Shared validation helper
# ---------------------------------------------------------------------------


def validate_mesh_spec(result: dict, name: str, min_verts: int = 4, min_faces: int = 1):
    """Validate a mesh spec dict has all required fields and valid data."""
    assert "vertices" in result, f"{name}: missing 'vertices'"
    assert "faces" in result, f"{name}: missing 'faces'"
    assert "uvs" in result, f"{name}: missing 'uvs'"
    assert "metadata" in result, f"{name}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    assert len(verts) >= min_verts, (
        f"{name}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{name}: expected >= {min_faces} faces, got {len(faces)}"
    )

    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components, expected 3"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{name}: metadata missing 'dimensions'"

    assert meta["poly_count"] == len(faces), (
        f"{name}: poly_count {meta['poly_count']} != actual {len(faces)}"
    )
    assert meta["vertex_count"] == len(verts), (
        f"{name}: vertex_count {meta['vertex_count']} != actual {len(verts)}"
    )

    dims = meta["dimensions"]
    assert "width" in dims and "height" in dims and "depth" in dims
    for dim_name, val in dims.items():
        assert val >= 0, f"{name}: dimension '{dim_name}' is negative: {val}"

    return True


# ---------------------------------------------------------------------------
# CATEGORY 10: CONTAINERS & LOOT
# ---------------------------------------------------------------------------


class TestContainers:
    """Test container and loot object mesh generators."""

    @pytest.mark.parametrize("style", ["ceramic_round", "metal_ornate", "stone_burial"])
    def test_urn_styles(self, style):
        result = generate_urn_mesh(height=0.5, style=style)
        validate_mesh_spec(result, f"Urn_{style}", min_verts=20)

    def test_urn_sizes(self):
        small = generate_urn_mesh(height=0.3)
        large = generate_urn_mesh(height=1.0)
        assert large["metadata"]["dimensions"]["height"] > small["metadata"]["dimensions"]["height"]

    @pytest.mark.parametrize("condition", ["new", "weathered", "broken_open"])
    def test_crate_conditions(self, condition):
        result = generate_crate_mesh(size=0.6, condition=condition)
        validate_mesh_spec(result, f"Crate_{condition}", min_verts=8)

    def test_crate_sizes(self):
        small = generate_crate_mesh(size=0.3)
        large = generate_crate_mesh(size=1.2)
        assert large["metadata"]["dimensions"]["width"] > small["metadata"]["dimensions"]["width"]

    @pytest.mark.parametrize("fullness", [0.0, 0.5, 1.0])
    def test_sack_fullness(self, fullness):
        result = generate_sack_mesh(fullness=fullness)
        validate_mesh_spec(result, f"Sack_{fullness}", min_verts=20)

    def test_sack_fullness_clamp(self):
        low = generate_sack_mesh(fullness=-0.5)
        high = generate_sack_mesh(fullness=1.5)
        validate_mesh_spec(low, "Sack_clamped_low")
        validate_mesh_spec(high, "Sack_clamped_high")

    @pytest.mark.parametrize("handle", [True, False])
    def test_basket_handle(self, handle):
        result = generate_basket_mesh(size=0.3, handle=handle)
        validate_mesh_spec(result, f"Basket_handle={handle}", min_verts=20)
        if handle:
            assert result["metadata"]["vertex_count"] > generate_basket_mesh(
                size=0.3, handle=False
            )["metadata"]["vertex_count"]

    def test_treasure_pile(self):
        result = generate_treasure_pile_mesh(size=0.5, coin_count=20)
        validate_mesh_spec(result, "TreasurePile", min_verts=20)

    def test_treasure_pile_sizes(self):
        small = generate_treasure_pile_mesh(size=0.2, coin_count=5)
        large = generate_treasure_pile_mesh(size=1.0, coin_count=50)
        assert large["metadata"]["vertex_count"] > small["metadata"]["vertex_count"]

    @pytest.mark.parametrize("style", ["round_flask", "tall_vial", "skull_bottle", "crystal_decanter"])
    def test_potion_bottle_styles(self, style):
        result = generate_potion_bottle_mesh(style=style)
        validate_mesh_spec(result, f"PotionBottle_{style}", min_verts=10)

    @pytest.mark.parametrize("rolled", [True, False])
    def test_scroll(self, rolled):
        result = generate_scroll_mesh(rolled=rolled, length=0.3)
        validate_mesh_spec(result, f"Scroll_rolled={rolled}", min_verts=8)


# ---------------------------------------------------------------------------
# CATEGORY 11: LIGHT SOURCES
# ---------------------------------------------------------------------------


class TestLightSources:
    """Test light source mesh generators."""

    @pytest.mark.parametrize("style", ["iron_cage", "paper_hanging", "crystal_embedded", "skull_lantern"])
    def test_lantern_styles(self, style):
        result = generate_lantern_mesh(style=style)
        validate_mesh_spec(result, f"Lantern_{style}", min_verts=20)

    @pytest.mark.parametrize("style", ["iron_standing", "stone_bowl", "hanging_chain"])
    def test_brazier_styles(self, style):
        result = generate_brazier_mesh(style=style, size=0.5)
        validate_mesh_spec(result, f"Brazier_{style}", min_verts=20)

    def test_brazier_sizes(self):
        small = generate_brazier_mesh(size=0.3)
        large = generate_brazier_mesh(size=1.0)
        assert large["metadata"]["dimensions"]["width"] > small["metadata"]["dimensions"]["width"]

    @pytest.mark.parametrize("log_count", [2, 4, 8])
    def test_campfire_log_count(self, log_count):
        result = generate_campfire_mesh(log_count=log_count)
        validate_mesh_spec(result, f"Campfire_{log_count}logs", min_verts=40)

    def test_campfire_log_clamp(self):
        result = generate_campfire_mesh(log_count=100)
        validate_mesh_spec(result, "Campfire_clamped")

    def test_crystal_light(self):
        result = generate_crystal_light_mesh(cluster_count=5, size=0.3)
        validate_mesh_spec(result, "CrystalLight", min_verts=20)

    def test_crystal_light_cluster_count(self):
        small = generate_crystal_light_mesh(cluster_count=2)
        large = generate_crystal_light_mesh(cluster_count=10)
        assert large["metadata"]["vertex_count"] > small["metadata"]["vertex_count"]

    @pytest.mark.parametrize("cage", [True, False])
    def test_magic_orb_light(self, cage):
        result = generate_magic_orb_light_mesh(radius=0.1, cage=cage)
        validate_mesh_spec(result, f"MagicOrb_cage={cage}", min_verts=20)
        if cage:
            assert result["metadata"]["vertex_count"] > generate_magic_orb_light_mesh(
                radius=0.1, cage=False
            )["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# CATEGORY 12: DOORS & WINDOWS
# ---------------------------------------------------------------------------


class TestDoorsWindows:
    """Test door and window mesh generators."""

    @pytest.mark.parametrize("style", [
        "wooden_plank", "iron_reinforced", "stone_carved", "hidden_bookcase", "dungeon_gate"
    ])
    def test_door_styles(self, style):
        result = generate_door_mesh(style=style, width=1.0, height=2.2)
        validate_mesh_spec(result, f"Door_{style}", min_verts=8)

    def test_door_dimensions(self):
        result = generate_door_mesh(width=1.5, height=3.0)
        dims = result["metadata"]["dimensions"]
        assert dims["height"] > 2.0

    @pytest.mark.parametrize("style", ["arched_gothic", "circular_rose", "arrow_slit", "stained_frame"])
    def test_window_styles(self, style):
        result = generate_window_mesh(style=style, width=0.6, height=1.0)
        validate_mesh_spec(result, f"Window_{style}", min_verts=8)

    @pytest.mark.parametrize("style", ["wooden", "iron"])
    def test_trapdoor_styles(self, style):
        result = generate_trapdoor_mesh(size=0.8, style=style)
        validate_mesh_spec(result, f"Trapdoor_{style}", min_verts=8)


# ---------------------------------------------------------------------------
# CATEGORY 13: WALL & FLOOR DECORATIONS
# ---------------------------------------------------------------------------


class TestWallDecor:
    """Test wall and floor decoration mesh generators."""

    @pytest.mark.parametrize("style", ["pointed", "straight", "swallowtail"])
    def test_banner_styles(self, style):
        result = generate_banner_mesh(width=0.5, length=1.2, style=style)
        validate_mesh_spec(result, f"Banner_{style}", min_verts=20)

    @pytest.mark.parametrize("style", ["kite", "round", "heater", "tower"])
    def test_wall_shield_styles(self, style):
        result = generate_wall_shield_mesh(style=style)
        validate_mesh_spec(result, f"WallShield_{style}", min_verts=8)

    @pytest.mark.parametrize("creature", ["deer", "boar", "dragon", "demon"])
    def test_mounted_head_creatures(self, creature):
        result = generate_mounted_head_mesh(creature=creature)
        validate_mesh_spec(result, f"MountedHead_{creature}", min_verts=20)

    @pytest.mark.parametrize("frame_style", ["ornate", "simple", "gothic"])
    def test_painting_frame_styles(self, frame_style):
        result = generate_painting_frame_mesh(width=0.5, height=0.7, frame_style=frame_style)
        validate_mesh_spec(result, f"PaintingFrame_{frame_style}", min_verts=20)

    @pytest.mark.parametrize("style", ["rectangular", "circular", "runner"])
    def test_rug_styles(self, style):
        result = generate_rug_mesh(width=1.5, length=2.0, style=style)
        validate_mesh_spec(result, f"Rug_{style}", min_verts=8)

    @pytest.mark.parametrize("arms,tiers", [(3, 1), (6, 1), (8, 2), (12, 3)])
    def test_chandelier_variants(self, arms, tiers):
        result = generate_chandelier_mesh(arms=arms, tiers=tiers)
        validate_mesh_spec(result, f"Chandelier_{arms}x{tiers}", min_verts=20)

    def test_chandelier_clamp(self):
        result = generate_chandelier_mesh(arms=100, tiers=100)
        validate_mesh_spec(result, "Chandelier_clamped")

    def test_hanging_cage(self):
        result = generate_hanging_cage_mesh(size=0.5)
        validate_mesh_spec(result, "HangingCage", min_verts=20)

    def test_hanging_cage_sizes(self):
        small = generate_hanging_cage_mesh(size=0.3)
        large = generate_hanging_cage_mesh(size=1.0)
        assert large["metadata"]["dimensions"]["height"] > small["metadata"]["dimensions"]["height"]


# ---------------------------------------------------------------------------
# CATEGORY 14: CRAFTING & TRADE
# ---------------------------------------------------------------------------


class TestCrafting:
    """Test crafting and trade object mesh generators."""

    def test_anvil(self):
        result = generate_anvil_mesh(size=1.0)
        validate_mesh_spec(result, "Anvil", min_verts=20)

    def test_anvil_sizes(self):
        small = generate_anvil_mesh(size=0.5)
        large = generate_anvil_mesh(size=2.0)
        assert large["metadata"]["dimensions"]["width"] > small["metadata"]["dimensions"]["width"]

    def test_forge(self):
        result = generate_forge_mesh(size=1.0)
        validate_mesh_spec(result, "Forge", min_verts=20)

    @pytest.mark.parametrize("tools", [True, False])
    def test_workbench(self, tools):
        result = generate_workbench_mesh(width=1.5, tools=tools)
        validate_mesh_spec(result, f"Workbench_tools={tools}", min_verts=20)
        if tools:
            assert result["metadata"]["vertex_count"] > generate_workbench_mesh(
                width=1.5, tools=False
            )["metadata"]["vertex_count"]

    @pytest.mark.parametrize("legs", [3, 4])
    def test_cauldron_legs(self, legs):
        result = generate_cauldron_mesh(size=0.5, legs=legs)
        validate_mesh_spec(result, f"Cauldron_{legs}legs", min_verts=20)

    def test_grinding_wheel(self):
        result = generate_grinding_wheel_mesh(radius=0.3)
        validate_mesh_spec(result, "GrindingWheel", min_verts=20)

    def test_loom(self):
        result = generate_loom_mesh()
        validate_mesh_spec(result, "Loom", min_verts=20)

    @pytest.mark.parametrize("canopy", [True, False])
    def test_market_stall(self, canopy):
        result = generate_market_stall_mesh(width=2.0, canopy=canopy)
        validate_mesh_spec(result, f"MarketStall_canopy={canopy}", min_verts=20)
        if canopy:
            assert result["metadata"]["vertex_count"] > generate_market_stall_mesh(
                width=2.0, canopy=False
            )["metadata"]["vertex_count"]


# ---------------------------------------------------------------------------
# CATEGORY 15: SIGNS & MARKERS
# ---------------------------------------------------------------------------


class TestSignsMarkers:
    """Test sign and marker mesh generators."""

    @pytest.mark.parametrize("arms", [1, 2, 3, 4])
    def test_signpost_arms(self, arms):
        result = generate_signpost_mesh(arms=arms)
        validate_mesh_spec(result, f"Signpost_{arms}arms", min_verts=20)

    def test_signpost_clamp(self):
        result = generate_signpost_mesh(arms=100)
        validate_mesh_spec(result, "Signpost_clamped")

    @pytest.mark.parametrize("style", ["cross", "rounded", "obelisk", "fallen_broken"])
    def test_gravestone_styles(self, style):
        result = generate_gravestone_mesh(style=style)
        validate_mesh_spec(result, f"Gravestone_{style}", min_verts=8)

    def test_waystone(self):
        result = generate_waystone_mesh(height=1.0)
        validate_mesh_spec(result, "Waystone", min_verts=20)

    def test_waystone_sizes(self):
        small = generate_waystone_mesh(height=0.5)
        large = generate_waystone_mesh(height=2.0)
        assert large["metadata"]["dimensions"]["height"] > small["metadata"]["dimensions"]["height"]

    def test_milestone(self):
        result = generate_milestone_mesh()
        validate_mesh_spec(result, "Milestone", min_verts=20)


# ---------------------------------------------------------------------------
# CATEGORY 16: NATURAL FORMATIONS
# ---------------------------------------------------------------------------


class TestNaturalFormations:
    """Test natural formation mesh generators."""

    def test_stalactite(self):
        result = generate_stalactite_mesh(length=0.5, thickness=0.08)
        validate_mesh_spec(result, "Stalactite", min_verts=20)

    def test_stalactite_sizes(self):
        small = generate_stalactite_mesh(length=0.2)
        large = generate_stalactite_mesh(length=1.0)
        assert large["metadata"]["dimensions"]["height"] > small["metadata"]["dimensions"]["height"]

    def test_stalagmite(self):
        result = generate_stalagmite_mesh(height=0.4, thickness=0.1)
        validate_mesh_spec(result, "Stalagmite", min_verts=20)

    def test_stalagmite_sizes(self):
        small = generate_stalagmite_mesh(height=0.2)
        large = generate_stalagmite_mesh(height=1.0)
        assert large["metadata"]["dimensions"]["height"] > small["metadata"]["dimensions"]["height"]

    @pytest.mark.parametrize("count", [5, 10, 20])
    def test_bone_pile_counts(self, count):
        result = generate_bone_pile_mesh(count=count, creature_size=1.0)
        validate_mesh_spec(result, f"BonePile_{count}", min_verts=20)

    def test_bone_pile_clamp(self):
        result = generate_bone_pile_mesh(count=100)
        validate_mesh_spec(result, "BonePile_clamped")

    @pytest.mark.parametrize("material", ["bird_sticks", "spider_web", "dragon_bones"])
    def test_nest_materials(self, material):
        result = generate_nest_mesh(size=0.4, material=material)
        validate_mesh_spec(result, f"Nest_{material}", min_verts=10)

    def test_geyser_vent(self):
        result = generate_geyser_vent_mesh(radius=0.3)
        validate_mesh_spec(result, "GeyserVent", min_verts=20)

    def test_fallen_log(self):
        result = generate_fallen_log_mesh(length=2.0, diameter=0.3)
        validate_mesh_spec(result, "FallenLog", min_verts=20)

    def test_fallen_log_sizes(self):
        small = generate_fallen_log_mesh(length=1.0, diameter=0.15)
        large = generate_fallen_log_mesh(length=4.0, diameter=0.6)
        assert large["metadata"]["dimensions"]["depth"] > small["metadata"]["dimensions"]["depth"]


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestWorldRegistry:
    """Test that all new generators are registered in GENERATORS."""

    def test_container_category_exists(self):
        assert "container" in GENERATORS

    def test_container_generators(self):
        expected = {"urn", "crate", "sack", "basket", "treasure_pile", "potion_bottle", "scroll"}
        assert set(GENERATORS["container"].keys()) == expected

    def test_light_source_category_exists(self):
        assert "light_source" in GENERATORS

    def test_light_source_generators(self):
        expected = {"lantern", "brazier", "campfire", "crystal_light", "magic_orb_light"}
        assert set(GENERATORS["light_source"].keys()) == expected

    def test_door_window_category_exists(self):
        assert "door_window" in GENERATORS

    def test_door_window_generators(self):
        expected = {"door", "window", "trapdoor"}
        assert set(GENERATORS["door_window"].keys()) == expected

    def test_wall_decor_category_exists(self):
        assert "wall_decor" in GENERATORS

    def test_wall_decor_generators(self):
        expected = {"banner", "wall_shield", "mounted_head", "painting_frame",
                    "rug", "chandelier", "hanging_cage"}
        assert set(GENERATORS["wall_decor"].keys()) == expected

    def test_crafting_category_exists(self):
        assert "crafting" in GENERATORS

    def test_crafting_generators(self):
        expected = {"anvil", "forge", "workbench", "cauldron",
                    "grinding_wheel", "loom", "market_stall"}
        assert set(GENERATORS["crafting"].keys()) == expected

    def test_sign_category_exists(self):
        assert "sign" in GENERATORS

    def test_sign_generators(self):
        expected = {"signpost", "gravestone", "waystone", "milestone"}
        assert set(GENERATORS["sign"].keys()) == expected

    def test_natural_category_exists(self):
        assert "natural" in GENERATORS

    def test_natural_generators(self):
        expected = {"stalactite", "stalagmite", "bone_pile", "nest",
                    "geyser_vent", "fallen_log"}
        assert set(GENERATORS["natural"].keys()) == expected

    def test_all_registry_entries_callable(self):
        """Every entry in new categories should be callable and return valid mesh."""
        new_categories = [
            "container", "light_source", "door_window",
            "wall_decor", "crafting", "sign", "natural",
        ]
        for cat in new_categories:
            for name, fn in GENERATORS[cat].items():
                result = fn()
                validate_mesh_spec(result, f"Registry:{cat}/{name}")
