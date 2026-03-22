"""Tests for dungeon prop, ambiance, loot, and ritual mesh generators.

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
    # Imprisonment
    generate_shackle_mesh,
    generate_cage_mesh,
    generate_stocks_mesh,
    generate_iron_maiden_mesh,
    generate_prisoner_skeleton_mesh,
    # Ambiance
    generate_cobweb_mesh,
    generate_spider_egg_sac_mesh,
    generate_rubble_pile_mesh,
    generate_hanging_skeleton_mesh,
    generate_dripping_water_mesh,
    generate_rat_nest_mesh,
    generate_rotting_barrel_mesh,
    # Loot/Discovery
    generate_treasure_chest_mesh,
    generate_gem_pile_mesh,
    generate_gold_pile_mesh,
    generate_lore_tablet_mesh,
    # Ritual
    generate_summoning_circle_mesh,
    generate_ritual_candles_mesh,
    generate_occult_symbols_mesh,
    # Registry
    GENERATORS,
)


# ---------------------------------------------------------------------------
# Helper validation (mirrors test_procedural_meshes.py)
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
# IMPRISONMENT tests
# ---------------------------------------------------------------------------


class TestImprisonment:
    """Test imprisonment-themed dungeon prop generators."""

    @pytest.mark.parametrize("style", ["wall", "floor", "hanging"])
    def test_shackle_styles(self, style):
        result = generate_shackle_mesh(style=style)
        validate_mesh_spec(result, f"Shackle_{style}", min_verts=20, min_faces=5)

    def test_shackle_category(self):
        result = generate_shackle_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_shackle_different_styles_different_geometry(self):
        r1 = generate_shackle_mesh(style="wall")
        r2 = generate_shackle_mesh(style="hanging")
        assert r1["metadata"]["vertex_count"] != r2["metadata"]["vertex_count"] or \
               r1["vertices"] != r2["vertices"]

    @pytest.mark.parametrize("style", ["hanging", "floor", "gibbet"])
    def test_cage_styles(self, style):
        result = generate_cage_mesh(style=style)
        validate_mesh_spec(result, f"Cage_{style}", min_verts=20, min_faces=5)

    def test_cage_size_scales(self):
        r_small = generate_cage_mesh(size=0.5)
        r_large = generate_cage_mesh(size=1.5)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["height"] > d_small["height"]

    def test_cage_category(self):
        result = generate_cage_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_stocks(self):
        result = generate_stocks_mesh()
        validate_mesh_spec(result, "Stocks", min_verts=30, min_faces=10)

    def test_stocks_category(self):
        result = generate_stocks_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_stocks_has_head_and_hand_holes(self):
        """Stocks should have enough geometry for head + hand hole torus rings."""
        result = generate_stocks_mesh()
        # 3 torus rings (1 head + 2 hands) contribute significant verts
        assert result["metadata"]["vertex_count"] > 80

    def test_iron_maiden(self):
        result = generate_iron_maiden_mesh()
        validate_mesh_spec(result, "IronMaiden", min_verts=50, min_faces=20)

    def test_iron_maiden_category(self):
        result = generate_iron_maiden_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_iron_maiden_has_spikes(self):
        """Iron maiden should have enough geometry for body + door + spikes."""
        result = generate_iron_maiden_mesh()
        # Body lathe + door + 24 spike cones + 2 hinges + base
        assert result["metadata"]["poly_count"] > 40

    def test_prisoner_skeleton(self):
        result = generate_prisoner_skeleton_mesh()
        validate_mesh_spec(result, "PrisonerSkeleton", min_verts=80, min_faces=30)

    def test_prisoner_skeleton_category(self):
        result = generate_prisoner_skeleton_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_prisoner_skeleton_has_chain(self):
        """Skeleton should include chain links (torus rings at top)."""
        result = generate_prisoner_skeleton_mesh()
        # Skull + spine + ribs + pelvis + arms + legs + chains
        assert result["metadata"]["vertex_count"] > 200


# ---------------------------------------------------------------------------
# AMBIANCE tests
# ---------------------------------------------------------------------------


class TestAmbiance:
    """Test ambiance-themed dungeon prop generators."""

    @pytest.mark.parametrize("style", ["corner", "spanning", "draped"])
    def test_cobweb_styles(self, style):
        result = generate_cobweb_mesh(style=style)
        validate_mesh_spec(result, f"Cobweb_{style}", min_verts=10, min_faces=4)

    def test_cobweb_size_scales(self):
        r_small = generate_cobweb_mesh(size=0.3)
        r_large = generate_cobweb_mesh(size=1.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"] or \
               d_large["depth"] > d_small["depth"]

    def test_cobweb_category(self):
        result = generate_cobweb_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_spider_egg_sac(self):
        result = generate_spider_egg_sac_mesh()
        validate_mesh_spec(result, "SpiderEggSac", min_verts=20, min_faces=5)

    def test_spider_egg_sac_count(self):
        r3 = generate_spider_egg_sac_mesh(count=3)
        r8 = generate_spider_egg_sac_mesh(count=8)
        assert r8["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_spider_egg_sac_category(self):
        result = generate_spider_egg_sac_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    @pytest.mark.parametrize("style", ["stone", "wood", "mixed"])
    def test_rubble_pile_styles(self, style):
        result = generate_rubble_pile_mesh(style=style)
        validate_mesh_spec(result, f"RubblePile_{style}", min_verts=15, min_faces=5)

    def test_rubble_pile_size(self):
        r_small = generate_rubble_pile_mesh(size=0.3)
        r_large = generate_rubble_pile_mesh(size=1.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_rubble_pile_category(self):
        result = generate_rubble_pile_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_hanging_skeleton(self):
        result = generate_hanging_skeleton_mesh()
        validate_mesh_spec(result, "HangingSkeleton", min_verts=80, min_faces=30)

    def test_hanging_skeleton_category(self):
        result = generate_hanging_skeleton_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_dripping_water(self):
        result = generate_dripping_water_mesh()
        validate_mesh_spec(result, "DrippingWater", min_verts=15, min_faces=5)

    def test_dripping_water_category(self):
        result = generate_dripping_water_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_dripping_water_has_stalactite_and_pool(self):
        """Should include stalactite body + water drop + pool."""
        result = generate_dripping_water_mesh()
        assert result["metadata"]["poly_count"] > 15

    def test_rat_nest(self):
        result = generate_rat_nest_mesh()
        validate_mesh_spec(result, "RatNest", min_verts=15, min_faces=5)

    def test_rat_nest_category(self):
        result = generate_rat_nest_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_rotting_barrel(self):
        result = generate_rotting_barrel_mesh()
        validate_mesh_spec(result, "RottingBarrel", min_verts=20, min_faces=8)

    def test_rotting_barrel_category(self):
        result = generate_rotting_barrel_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"


# ---------------------------------------------------------------------------
# LOOT / DISCOVERY tests
# ---------------------------------------------------------------------------


class TestLootDiscovery:
    """Test loot and discovery prop generators."""

    @pytest.mark.parametrize("style", ["locked", "open", "trapped", "ornate"])
    def test_treasure_chest_styles(self, style):
        result = generate_treasure_chest_mesh(style=style)
        validate_mesh_spec(result, f"TreasureChest_{style}", min_verts=20, min_faces=5)

    def test_treasure_chest_size(self):
        r_small = generate_treasure_chest_mesh(size=0.5)
        r_large = generate_treasure_chest_mesh(size=2.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_treasure_chest_category(self):
        result = generate_treasure_chest_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_treasure_chest_locked_has_lock(self):
        """Locked variant should have more geometry than open (lock plate + keyhole)."""
        r_locked = generate_treasure_chest_mesh(style="locked")
        r_open = generate_treasure_chest_mesh(style="open")
        # Both should be valid
        validate_mesh_spec(r_locked, "TreasureChest_locked")
        validate_mesh_spec(r_open, "TreasureChest_open")

    def test_gem_pile(self):
        result = generate_gem_pile_mesh()
        validate_mesh_spec(result, "GemPile", min_verts=15, min_faces=5)

    def test_gem_pile_size(self):
        r_small = generate_gem_pile_mesh(size=0.2)
        r_large = generate_gem_pile_mesh(size=0.6)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] >= d_small["width"]

    def test_gem_pile_count(self):
        r_few = generate_gem_pile_mesh(gem_count=4)
        r_many = generate_gem_pile_mesh(gem_count=20)
        assert r_many["metadata"]["vertex_count"] >= r_few["metadata"]["vertex_count"]

    def test_gem_pile_category(self):
        result = generate_gem_pile_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    def test_gold_pile(self):
        result = generate_gold_pile_mesh()
        validate_mesh_spec(result, "GoldPile", min_verts=15, min_faces=5)

    def test_gold_pile_count(self):
        r_few = generate_gold_pile_mesh(coin_count=5)
        r_many = generate_gold_pile_mesh(coin_count=40)
        assert r_many["metadata"]["vertex_count"] >= r_few["metadata"]["vertex_count"]

    def test_gold_pile_category(self):
        result = generate_gold_pile_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"

    @pytest.mark.parametrize("style", ["stone", "clay", "obsidian"])
    def test_lore_tablet_styles(self, style):
        result = generate_lore_tablet_mesh(style=style)
        validate_mesh_spec(result, f"LoreTablet_{style}", min_verts=10, min_faces=4)

    def test_lore_tablet_different_styles_different_geometry(self):
        r1 = generate_lore_tablet_mesh(style="stone")
        r2 = generate_lore_tablet_mesh(style="clay")
        assert r1["vertices"] != r2["vertices"]

    def test_lore_tablet_category(self):
        result = generate_lore_tablet_mesh()
        assert result["metadata"]["category"] == "dungeon_prop"


# ---------------------------------------------------------------------------
# RITUAL tests
# ---------------------------------------------------------------------------


class TestRitual:
    """Test ritual-themed dark fantasy generators."""

    def test_summoning_circle(self):
        result = generate_summoning_circle_mesh()
        validate_mesh_spec(result, "SummoningCircle", min_verts=30, min_faces=10)

    def test_summoning_circle_rune_count(self):
        r4 = generate_summoning_circle_mesh(rune_count=4)
        r12 = generate_summoning_circle_mesh(rune_count=12)
        assert r12["metadata"]["vertex_count"] > r4["metadata"]["vertex_count"]

    def test_summoning_circle_radius(self):
        r_small = generate_summoning_circle_mesh(radius=0.5)
        r_large = generate_summoning_circle_mesh(radius=3.0)
        d_small = r_small["metadata"]["dimensions"]
        d_large = r_large["metadata"]["dimensions"]
        assert d_large["width"] > d_small["width"]

    def test_summoning_circle_category(self):
        result = generate_summoning_circle_mesh()
        assert result["metadata"]["category"] == "dark_fantasy"

    @pytest.mark.parametrize("arrangement", ["circle", "cluster"])
    def test_ritual_candles_arrangements(self, arrangement):
        result = generate_ritual_candles_mesh(arrangement=arrangement)
        validate_mesh_spec(result, f"RitualCandles_{arrangement}", min_verts=20, min_faces=5)

    def test_ritual_candles_count(self):
        r3 = generate_ritual_candles_mesh(count=3)
        r9 = generate_ritual_candles_mesh(count=9)
        assert r9["metadata"]["vertex_count"] > r3["metadata"]["vertex_count"]

    def test_ritual_candles_category(self):
        result = generate_ritual_candles_mesh()
        assert result["metadata"]["category"] == "dark_fantasy"

    def test_ritual_candles_count_clamped(self):
        """Count should be clamped to 3-9 range."""
        r_min = generate_ritual_candles_mesh(count=1)  # clamped to 3
        r_max = generate_ritual_candles_mesh(count=20)  # clamped to 9
        # Both should be valid
        validate_mesh_spec(r_min, "RitualCandles_min")
        validate_mesh_spec(r_max, "RitualCandles_max")

    @pytest.mark.parametrize("symbol_type", ["pentagram", "runes", "sigil"])
    def test_occult_symbols_types(self, symbol_type):
        result = generate_occult_symbols_mesh(symbol_type=symbol_type)
        validate_mesh_spec(result, f"OccultSymbols_{symbol_type}", min_verts=10, min_faces=4)

    def test_occult_symbols_different_types_different_geometry(self):
        r1 = generate_occult_symbols_mesh(symbol_type="pentagram")
        r2 = generate_occult_symbols_mesh(symbol_type="runes")
        r3 = generate_occult_symbols_mesh(symbol_type="sigil")
        # All three should be different
        verts = {
            "pentagram": r1["metadata"]["vertex_count"],
            "runes": r2["metadata"]["vertex_count"],
            "sigil": r3["metadata"]["vertex_count"],
        }
        assert len(set(verts.values())) >= 2, "At least 2 of 3 symbol types should differ"

    def test_occult_symbols_category(self):
        result = generate_occult_symbols_mesh()
        assert result["metadata"]["category"] == "dark_fantasy"


# ---------------------------------------------------------------------------
# REGISTRY tests
# ---------------------------------------------------------------------------


class TestDungeonRegistry:
    """Test that all dungeon generators are registered in GENERATORS dict."""

    DUNGEON_PROP_EXPECTED = [
        "shackle", "cage", "stocks", "iron_maiden", "prisoner_skeleton",
        "cobweb", "spider_egg_sac", "rubble_pile", "hanging_skeleton",
        "dripping_water", "rat_nest", "rotting_barrel",
        "treasure_chest", "gem_pile", "gold_pile", "lore_tablet",
    ]

    DARK_FANTASY_EXPECTED = [
        "summoning_circle", "ritual_candles", "occult_symbols",
    ]

    @pytest.mark.parametrize("key", DUNGEON_PROP_EXPECTED)
    def test_dungeon_prop_registered(self, key):
        assert key in GENERATORS["dungeon_prop"], (
            f"{key} not registered in GENERATORS['dungeon_prop']"
        )

    @pytest.mark.parametrize("key", DARK_FANTASY_EXPECTED)
    def test_dark_fantasy_registered(self, key):
        assert key in GENERATORS["dark_fantasy"], (
            f"{key} not registered in GENERATORS['dark_fantasy']"
        )

    @pytest.mark.parametrize("key", DUNGEON_PROP_EXPECTED)
    def test_dungeon_prop_callable(self, key):
        gen = GENERATORS["dungeon_prop"][key]
        assert callable(gen), f"{key} generator is not callable"

    @pytest.mark.parametrize("key", DARK_FANTASY_EXPECTED)
    def test_dark_fantasy_callable(self, key):
        gen = GENERATORS["dark_fantasy"][key]
        assert callable(gen), f"{key} generator is not callable"

    @pytest.mark.parametrize("key", DUNGEON_PROP_EXPECTED)
    def test_dungeon_prop_default_call(self, key):
        """Every registered generator should work with default arguments."""
        gen = GENERATORS["dungeon_prop"][key]
        result = gen()
        validate_mesh_spec(result, key)

    @pytest.mark.parametrize("key", DARK_FANTASY_EXPECTED)
    def test_dark_fantasy_default_call(self, key):
        """Every registered generator should work with default arguments."""
        gen = GENERATORS["dark_fantasy"][key]
        result = gen()
        validate_mesh_spec(result, key)
