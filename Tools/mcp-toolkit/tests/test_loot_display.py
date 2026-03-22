"""Unit tests for the loot drop ground display system.

Tests cover:
- LOOT_DISPLAY constant definitions (5 rarities)
- RARITY_ORDER ordering
- get_loot_display() lookup and validation
- generate_loot_bag_mesh() bag/chest mesh generation
- generate_loot_beam_mesh() vertical beam mesh generation
- compute_item_ground_placement() ground placement parameters
- Mesh integrity: valid face indices, vertex counts, metadata

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.loot_display import (
    LOOT_DISPLAY,
    RARITY_ORDER,
    compute_item_ground_placement,
    generate_loot_bag_mesh,
    generate_loot_beam_mesh,
    get_loot_display,
)


# ---------------------------------------------------------------------------
# TestLootDisplayConstants
# ---------------------------------------------------------------------------

class TestLootDisplayConstants:
    """Test LOOT_DISPLAY constant definitions."""

    def test_has_five_rarities(self):
        assert len(LOOT_DISPLAY) == 5

    def test_rarity_names(self):
        expected = {"common", "uncommon", "rare", "epic", "legendary"}
        assert set(LOOT_DISPLAY.keys()) == expected

    def test_rarity_order(self):
        assert RARITY_ORDER == ["common", "uncommon", "rare", "epic", "legendary"]

    def test_all_have_required_keys(self):
        required = {"glow_color", "beam_height", "ground_mesh",
                     "pickup_radius", "despawn_time", "bob_amplitude"}
        for rarity, data in LOOT_DISPLAY.items():
            for key in required:
                assert key in data, f"Rarity '{rarity}' missing key '{key}'"

    def test_common_no_glow(self):
        assert LOOT_DISPLAY["common"]["glow_color"] is None

    def test_common_no_beam(self):
        assert LOOT_DISPLAY["common"]["beam_height"] == 0

    def test_beam_height_increases_with_rarity(self):
        heights = [LOOT_DISPLAY[r]["beam_height"] for r in RARITY_ORDER]
        for i in range(len(heights) - 1):
            assert heights[i] <= heights[i + 1]

    def test_pickup_radius_increases_with_rarity(self):
        radii = [LOOT_DISPLAY[r]["pickup_radius"] for r in RARITY_ORDER]
        for i in range(len(radii) - 1):
            assert radii[i] <= radii[i + 1]

    def test_despawn_time_increases_with_rarity(self):
        times = [LOOT_DISPLAY[r]["despawn_time"] for r in RARITY_ORDER]
        for i in range(len(times) - 1):
            assert times[i] <= times[i + 1]

    def test_glow_colors_are_rgb_or_none(self):
        for rarity, data in LOOT_DISPLAY.items():
            color = data["glow_color"]
            if color is not None:
                assert len(color) == 3
                for c in color:
                    assert 0.0 <= c <= 1.0

    def test_uncommon_plus_have_glow(self):
        for rarity in RARITY_ORDER[1:]:
            assert LOOT_DISPLAY[rarity]["glow_color"] is not None

    def test_ground_mesh_names_unique(self):
        meshes = [d["ground_mesh"] for d in LOOT_DISPLAY.values()]
        assert len(meshes) == len(set(meshes))


# ---------------------------------------------------------------------------
# TestGetLootDisplay
# ---------------------------------------------------------------------------

class TestGetLootDisplay:
    """Test get_loot_display() lookup function."""

    def test_valid_rarities(self):
        for rarity in RARITY_ORDER:
            result = get_loot_display(rarity)
            assert isinstance(result, dict)

    def test_case_insensitive(self):
        result = get_loot_display("RARE")
        assert result["ground_mesh"] == "loot_bag_large"

    def test_returns_copy(self):
        result = get_loot_display("epic")
        result["beam_height"] = 999
        assert LOOT_DISPLAY["epic"]["beam_height"] != 999

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError, match="Unknown rarity"):
            get_loot_display("mythic")


# ---------------------------------------------------------------------------
# TestGenerateLootBagMesh
# ---------------------------------------------------------------------------

class TestGenerateLootBagMesh:
    """Test generate_loot_bag_mesh() mesh generation."""

    @pytest.mark.parametrize("rarity", RARITY_ORDER)
    def test_returns_mesh_spec(self, rarity):
        result = generate_loot_bag_mesh(rarity)
        assert "vertices" in result
        assert "faces" in result
        assert "metadata" in result

    @pytest.mark.parametrize("rarity", RARITY_ORDER)
    def test_has_vertices_and_faces(self, rarity):
        result = generate_loot_bag_mesh(rarity)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_bag_mesh_for_common(self):
        result = generate_loot_bag_mesh("common")
        assert result["metadata"]["mesh_type"] == "bag"
        assert result["metadata"]["name"] == "loot_bag_small"

    def test_bag_mesh_for_uncommon(self):
        result = generate_loot_bag_mesh("uncommon")
        assert result["metadata"]["mesh_type"] == "bag"
        assert result["metadata"]["name"] == "loot_bag_medium"

    def test_bag_mesh_for_rare(self):
        result = generate_loot_bag_mesh("rare")
        assert result["metadata"]["mesh_type"] == "bag"
        assert result["metadata"]["name"] == "loot_bag_large"

    def test_chest_mesh_for_epic(self):
        result = generate_loot_bag_mesh("epic")
        assert result["metadata"]["mesh_type"] == "chest"
        assert result["metadata"]["name"] == "loot_chest"

    def test_ornate_chest_for_legendary(self):
        result = generate_loot_bag_mesh("legendary")
        assert result["metadata"]["mesh_type"] == "chest"
        assert result["metadata"]["ornate"] is True
        assert result["metadata"]["name"] == "loot_chest_ornate"

    def test_epic_not_ornate(self):
        result = generate_loot_bag_mesh("epic")
        assert result["metadata"].get("ornate", False) is False

    def test_face_indices_valid(self):
        for rarity in RARITY_ORDER:
            result = generate_loot_bag_mesh(rarity)
            num_verts = len(result["vertices"])
            for face in result["faces"]:
                for idx in face:
                    assert 0 <= idx < num_verts, (
                        f"Face index {idx} out of range for {rarity} "
                        f"(num_verts={num_verts})"
                    )

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError):
            generate_loot_bag_mesh("mythic")

    def test_higher_rarity_bags_larger(self):
        common = generate_loot_bag_mesh("common")
        rare = generate_loot_bag_mesh("rare")
        # Rare bags should be bigger (more vertices or larger dimensions)
        common_w = common["metadata"]["dimensions"]["width"]
        rare_w = rare["metadata"]["dimensions"]["width"]
        assert rare_w > common_w

    def test_metadata_has_dimensions(self):
        result = generate_loot_bag_mesh("common")
        dims = result["metadata"]["dimensions"]
        assert "width" in dims
        assert "height" in dims
        assert "depth" in dims

    def test_poly_count_matches(self):
        for rarity in RARITY_ORDER:
            result = generate_loot_bag_mesh(rarity)
            assert result["metadata"]["poly_count"] == len(result["faces"])

    def test_vertex_count_matches(self):
        for rarity in RARITY_ORDER:
            result = generate_loot_bag_mesh(rarity)
            assert result["metadata"]["vertex_count"] == len(result["vertices"])


# ---------------------------------------------------------------------------
# TestGenerateLootBeamMesh
# ---------------------------------------------------------------------------

class TestGenerateLootBeamMesh:
    """Test generate_loot_beam_mesh() beam generation."""

    BEAM_RARITIES = ["uncommon", "rare", "epic", "legendary"]

    @pytest.mark.parametrize("rarity", BEAM_RARITIES)
    def test_returns_mesh_spec(self, rarity):
        result = generate_loot_beam_mesh(rarity)
        assert "vertices" in result
        assert "faces" in result
        assert "metadata" in result

    @pytest.mark.parametrize("rarity", BEAM_RARITIES)
    def test_has_vertices_and_faces(self, rarity):
        result = generate_loot_beam_mesh(rarity)
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_common_raises(self):
        with pytest.raises(ValueError, match="no beam"):
            generate_loot_beam_mesh("common")

    def test_beam_height_metadata(self):
        result = generate_loot_beam_mesh("rare")
        assert result["metadata"]["beam_height"] == 2.0

    def test_custom_height(self):
        result = generate_loot_beam_mesh("rare", height=10.0)
        assert result["metadata"]["beam_height"] == 10.0

    def test_beam_tapers_upward(self):
        result = generate_loot_beam_mesh("epic")
        verts = result["vertices"]
        # Bottom vertices should have larger radius than top
        segments = result["metadata"]["segments"]
        bottom_ring = verts[:segments]
        top_ring = verts[-segments:]
        bottom_radius = math.sqrt(bottom_ring[0][0] ** 2 + bottom_ring[0][2] ** 2)
        top_radius = math.sqrt(top_ring[0][0] ** 2 + top_ring[0][2] ** 2)
        assert bottom_radius > top_radius

    def test_beam_starts_at_ground(self):
        result = generate_loot_beam_mesh("rare")
        bottom_y = min(v[1] for v in result["vertices"])
        assert abs(bottom_y) < 0.01

    def test_beam_reaches_target_height(self):
        height = 5.0
        result = generate_loot_beam_mesh("legendary", height=height)
        top_y = max(v[1] for v in result["vertices"])
        assert abs(top_y - height) < 0.01

    def test_glow_color_in_metadata(self):
        result = generate_loot_beam_mesh("epic")
        assert result["metadata"]["glow_color"] == (0.7, 0.3, 1.0)

    def test_face_indices_valid(self):
        for rarity in self.BEAM_RARITIES:
            result = generate_loot_beam_mesh(rarity)
            num_verts = len(result["vertices"])
            for face in result["faces"]:
                for idx in face:
                    assert 0 <= idx < num_verts

    def test_legendary_taller_than_uncommon(self):
        uncommon = generate_loot_beam_mesh("uncommon")
        legendary = generate_loot_beam_mesh("legendary")
        assert legendary["metadata"]["beam_height"] > uncommon["metadata"]["beam_height"]

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError):
            generate_loot_beam_mesh("mythic")


# ---------------------------------------------------------------------------
# TestComputeItemGroundPlacement
# ---------------------------------------------------------------------------

class TestComputeItemGroundPlacement:
    """Test compute_item_ground_placement() placement computation."""

    def test_returns_expected_keys(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0))
        expected_keys = {
            "position", "rotation", "ground_mesh", "beam_height",
            "glow_color", "pickup_radius", "despawn_time",
            "bob_amplitude", "item_type", "rarity",
        }
        assert set(result.keys()) == expected_keys

    def test_position_preserves_xz(self):
        result = compute_item_ground_placement("armor", (5.0, 2.0, 3.0))
        assert result["position"][0] == 5.0
        assert result["position"][2] == 3.0

    def test_position_y_is_ground(self):
        result = compute_item_ground_placement("armor", (5.0, 2.0, 3.0))
        assert result["position"][1] == 2.0

    def test_rarity_affects_mesh(self):
        common = compute_item_ground_placement("weapon", (0, 0, 0), rarity="common")
        epic = compute_item_ground_placement("weapon", (0, 0, 0), rarity="epic")
        assert common["ground_mesh"] == "loot_bag_small"
        assert epic["ground_mesh"] == "loot_chest"

    def test_common_no_glow(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0), rarity="common")
        assert result["glow_color"] is None
        assert result["beam_height"] == 0

    def test_legendary_has_glow_and_beam(self):
        result = compute_item_ground_placement("armor", (0, 0, 0), rarity="legendary")
        assert result["glow_color"] is not None
        assert result["beam_height"] == 5.0

    def test_item_type_preserved(self):
        result = compute_item_ground_placement("consumable", (0, 0, 0))
        assert result["item_type"] == "consumable"

    def test_rarity_lowercase(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0), rarity="RARE")
        assert result["rarity"] == "rare"

    def test_rotation_is_three_component(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0))
        assert len(result["rotation"]) == 3

    def test_weapon_has_tilt(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0))
        # Weapon should have a Z-axis tilt
        assert result["rotation"][2] != 0.0

    def test_different_positions_different_rotations(self):
        r1 = compute_item_ground_placement("weapon", (1.0, 0, 2.0))
        r2 = compute_item_ground_placement("weapon", (3.0, 0, 7.0))
        # Y rotation varies based on position hash
        assert r1["rotation"][1] != r2["rotation"][1]

    @pytest.mark.parametrize("item_type", [
        "weapon", "armor", "consumable", "material", "currency", "quest_item"
    ])
    def test_all_item_types_work(self, item_type):
        result = compute_item_ground_placement(item_type, (0, 0, 0))
        assert result["item_type"] == item_type

    def test_unknown_item_type_defaults(self):
        result = compute_item_ground_placement("mystery_box", (0, 0, 0))
        assert result["item_type"] == "mystery_box"
        # Should still produce valid output with default rotation

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError):
            compute_item_ground_placement("weapon", (0, 0, 0), rarity="mythic")

    def test_despawn_time_present(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0), rarity="rare")
        assert result["despawn_time"] == 180.0

    def test_bob_amplitude_present(self):
        result = compute_item_ground_placement("weapon", (0, 0, 0), rarity="epic")
        assert result["bob_amplitude"] == 0.04
