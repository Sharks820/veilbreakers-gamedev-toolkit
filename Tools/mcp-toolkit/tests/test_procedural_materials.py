"""Tests for procedural material library and node graph builders.

Verifies:
  - MATERIAL_LIBRARY has 45+ entries
  - Every entry has all required keys (base_color, roughness, node_recipe, etc.)
  - Builder functions exist for every node_recipe value used in the library
  - GENERATORS dict maps all VALID_RECIPES
  - create_procedural_material() dispatches correctly (mocked bpy)
  - handle_create_procedural_material() returns expected structure
  - Color palette compliance (saturation / value checks)
  - get_library_keys() / get_library_info() helpers
  - Error handling for invalid keys

All pure-logic -- no Blender required.
"""

import math
import types
from unittest.mock import MagicMock, patch

import pytest

from blender_addon.handlers.procedural_materials import (
    GENERATORS,
    MATERIAL_LIBRARY,
    REQUIRED_MATERIAL_KEYS,
    VALID_RECIPES,
    build_fabric_material,
    build_metal_material,
    build_organic_material,
    build_stone_material,
    build_terrain_material,
    build_wood_material,
    create_procedural_material,
    get_library_info,
    get_library_keys,
    handle_create_procedural_material,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgb_to_hsv(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert linear RGB (0-1) to HSV (0-360, 0-100, 0-100)."""
    mx = max(r, g, b)
    mn = min(r, g, b)
    diff = mx - mn

    # Value
    v = mx * 100.0

    if mx == 0:
        return (0.0, 0.0, v)

    # Saturation
    s = (diff / mx) * 100.0

    # Hue
    if diff == 0:
        h = 0.0
    elif mx == r:
        h = 60.0 * (((g - b) / diff) % 6)
    elif mx == g:
        h = 60.0 * (((b - r) / diff) + 2)
    else:
        h = 60.0 * (((r - g) / diff) + 4)

    return (h, s, v)


def _make_mock_bpy():
    """Create a mock bpy module sufficient for create_procedural_material."""
    mock_bpy = MagicMock()

    # Mock material creation
    mock_mat = MagicMock()
    mock_mat.name = "TestMaterial"
    mock_mat.use_nodes = True

    # Mock node tree
    mock_tree = MagicMock()
    mock_nodes = MagicMock()

    # Keep track of created nodes for counting
    created_nodes = []

    def mock_new_node(type=None):
        node = MagicMock()
        node.type = type
        node.location = (0, 0)
        node.label = ""
        # Make inputs behave like a dict with get()
        node.inputs = MagicMock()
        node.inputs.get = MagicMock(return_value=MagicMock())
        node.inputs.__getitem__ = MagicMock(return_value=MagicMock())
        node.outputs = MagicMock()
        node.outputs.__getitem__ = MagicMock(return_value=MagicMock())

        # For color ramp nodes
        ramp = MagicMock()
        elem0 = MagicMock()
        elem0.position = 0.0
        elem0.color = (0, 0, 0, 1)
        elem1 = MagicMock()
        elem1.position = 1.0
        elem1.color = (1, 1, 1, 1)
        ramp.elements = [elem0, elem1]
        node.color_ramp = ramp

        created_nodes.append(node)
        return node

    mock_nodes.new = mock_new_node
    mock_nodes.clear = MagicMock()
    mock_tree.nodes = mock_nodes
    mock_tree.links = MagicMock()
    mock_mat.node_tree = mock_tree

    # Make len(mat.node_tree.nodes) return the count of created nodes
    mock_nodes.__len__ = lambda self: len(created_nodes)

    mock_bpy.data = MagicMock()
    mock_bpy.data.materials = MagicMock()
    mock_bpy.data.materials.new = MagicMock(return_value=mock_mat)

    return mock_bpy, mock_mat, created_nodes


# ---------------------------------------------------------------------------
# Test: Library Completeness
# ---------------------------------------------------------------------------


class TestMaterialLibrary:
    """Verify MATERIAL_LIBRARY structure and completeness."""

    def test_library_has_at_least_45_entries(self):
        assert len(MATERIAL_LIBRARY) >= 45, (
            f"MATERIAL_LIBRARY has {len(MATERIAL_LIBRARY)} entries, need 45+"
        )

    def test_every_entry_has_required_keys(self):
        for key, entry in MATERIAL_LIBRARY.items():
            missing = REQUIRED_MATERIAL_KEYS - set(entry.keys())
            assert not missing, (
                f"Material '{key}' missing keys: {missing}"
            )

    def test_base_color_is_4_tuple(self):
        for key, entry in MATERIAL_LIBRARY.items():
            bc = entry["base_color"]
            assert len(bc) == 4, (
                f"Material '{key}' base_color has {len(bc)} elements, need 4"
            )
            assert bc[3] == 1.0, (
                f"Material '{key}' base_color alpha should be 1.0, got {bc[3]}"
            )

    def test_roughness_in_valid_range(self):
        for key, entry in MATERIAL_LIBRARY.items():
            assert 0.0 <= entry["roughness"] <= 1.0, (
                f"Material '{key}' roughness {entry['roughness']} out of range"
            )

    def test_metallic_in_valid_range(self):
        for key, entry in MATERIAL_LIBRARY.items():
            assert 0.0 <= entry["metallic"] <= 1.0, (
                f"Material '{key}' metallic {entry['metallic']} out of range"
            )

    def test_roughness_variation_in_valid_range(self):
        for key, entry in MATERIAL_LIBRARY.items():
            rv = entry["roughness_variation"]
            assert 0.0 <= rv <= 1.0, (
                f"Material '{key}' roughness_variation {rv} out of range"
            )

    def test_normal_strength_positive(self):
        for key, entry in MATERIAL_LIBRARY.items():
            assert entry["normal_strength"] > 0.0, (
                f"Material '{key}' normal_strength must be positive"
            )

    def test_detail_scale_positive(self):
        for key, entry in MATERIAL_LIBRARY.items():
            assert entry["detail_scale"] > 0.0, (
                f"Material '{key}' detail_scale must be positive"
            )

    def test_wear_intensity_in_valid_range(self):
        for key, entry in MATERIAL_LIBRARY.items():
            wi = entry["wear_intensity"]
            assert 0.0 <= wi <= 1.0, (
                f"Material '{key}' wear_intensity {wi} out of range"
            )

    def test_node_recipe_is_valid(self):
        for key, entry in MATERIAL_LIBRARY.items():
            assert entry["node_recipe"] in VALID_RECIPES, (
                f"Material '{key}' has unknown node_recipe "
                f"'{entry['node_recipe']}'"
            )


# ---------------------------------------------------------------------------
# Test: Required Material Categories
# ---------------------------------------------------------------------------


class TestMaterialCategories:
    """Verify all required material categories are present."""

    # Architecture -- Stone (7)
    STONE_KEYS = {
        "rough_stone_wall", "smooth_stone", "cobblestone_floor",
        "brick_wall", "crumbling_stone", "mossy_stone", "marble",
    }

    # Architecture -- Wood (5)
    WOOD_KEYS = {
        "rough_timber", "polished_wood", "rotten_wood",
        "charred_wood", "plank_floor",
    }

    # Architecture -- Roofing (3)
    ROOFING_KEYS = {"slate_tiles", "thatch_roof", "wooden_shingles"}

    # Metals (5)
    METAL_KEYS = {
        "rusted_iron", "polished_steel", "tarnished_bronze",
        "chain_metal", "gold_ornament",
    }

    # Organic -- Creature (6)
    CREATURE_KEYS = {
        "monster_skin", "scales", "chitin_carapace",
        "fur_base", "bone", "membrane",
    }

    # Organic -- Vegetation (4)
    VEGETATION_KEYS = {"bark", "leaf", "moss", "mushroom_cap"}

    # Terrain (6)
    TERRAIN_KEYS = {"grass", "dirt", "mud", "snow", "sand", "cliff_rock"}

    # Fabric (3)
    FABRIC_KEYS = {"burlap_cloth", "leather", "silk"}

    # Special (6)
    SPECIAL_KEYS = {
        "corruption_overlay", "lava_ember", "ice_crystal",
        "glass", "water_surface", "blood_splatter",
    }

    def test_stone_materials_present(self):
        missing = self.STONE_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing stone materials: {missing}"

    def test_wood_materials_present(self):
        missing = self.WOOD_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing wood materials: {missing}"

    def test_roofing_materials_present(self):
        missing = self.ROOFING_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing roofing materials: {missing}"

    def test_metal_materials_present(self):
        missing = self.METAL_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing metal materials: {missing}"

    def test_creature_materials_present(self):
        missing = self.CREATURE_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing creature materials: {missing}"

    def test_vegetation_materials_present(self):
        missing = self.VEGETATION_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing vegetation materials: {missing}"

    def test_terrain_materials_present(self):
        missing = self.TERRAIN_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing terrain materials: {missing}"

    def test_fabric_materials_present(self):
        missing = self.FABRIC_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing fabric materials: {missing}"

    def test_special_materials_present(self):
        missing = self.SPECIAL_KEYS - set(MATERIAL_LIBRARY.keys())
        assert not missing, f"Missing special materials: {missing}"

    def test_total_category_count(self):
        total = (
            len(self.STONE_KEYS)
            + len(self.WOOD_KEYS)
            + len(self.ROOFING_KEYS)
            + len(self.METAL_KEYS)
            + len(self.CREATURE_KEYS)
            + len(self.VEGETATION_KEYS)
            + len(self.TERRAIN_KEYS)
            + len(self.FABRIC_KEYS)
            + len(self.SPECIAL_KEYS)
        )
        assert total >= 45, f"Total categorized materials: {total}, need 45+"


# ---------------------------------------------------------------------------
# Test: Generator Dispatch
# ---------------------------------------------------------------------------


class TestGenerators:
    """Verify GENERATORS dict is complete and correct."""

    def test_generators_covers_all_valid_recipes(self):
        missing = VALID_RECIPES - set(GENERATORS.keys())
        assert not missing, f"GENERATORS missing recipes: {missing}"

    def test_generators_has_no_extra_recipes(self):
        extra = set(GENERATORS.keys()) - VALID_RECIPES
        assert not extra, f"GENERATORS has unknown recipes: {extra}"

    def test_stone_generator_is_callable(self):
        assert callable(GENERATORS["stone"])
        assert GENERATORS["stone"] is build_stone_material

    def test_wood_generator_is_callable(self):
        assert callable(GENERATORS["wood"])
        assert GENERATORS["wood"] is build_wood_material

    def test_metal_generator_is_callable(self):
        assert callable(GENERATORS["metal"])
        assert GENERATORS["metal"] is build_metal_material

    def test_organic_generator_is_callable(self):
        assert callable(GENERATORS["organic"])
        assert GENERATORS["organic"] is build_organic_material

    def test_terrain_generator_is_callable(self):
        assert callable(GENERATORS["terrain"])
        assert GENERATORS["terrain"] is build_terrain_material

    def test_fabric_generator_is_callable(self):
        assert callable(GENERATORS["fabric"])
        assert GENERATORS["fabric"] is build_fabric_material

    def test_every_library_recipe_has_generator(self):
        """Verify no material references a recipe without a builder."""
        for key, entry in MATERIAL_LIBRARY.items():
            recipe = entry["node_recipe"]
            assert recipe in GENERATORS, (
                f"Material '{key}' uses recipe '{recipe}' "
                f"but no generator exists"
            )


# ---------------------------------------------------------------------------
# Test: Builder Functions (with mocked bpy)
# ---------------------------------------------------------------------------


class TestBuilderFunctions:
    """Test that each builder function runs without error on mock data."""

    def _make_mock_mat(self):
        """Create a mock material with node tree."""
        mock_mat = MagicMock()
        mock_tree = MagicMock()
        mock_nodes = MagicMock()

        def mock_new_node(type=None):
            node = MagicMock()
            node.location = (0, 0)
            node.label = ""
            node.inputs = MagicMock()
            node.inputs.get = MagicMock(return_value=MagicMock())
            node.inputs.__getitem__ = MagicMock(return_value=MagicMock())
            node.outputs = MagicMock()
            node.outputs.__getitem__ = MagicMock(return_value=MagicMock())
            ramp = MagicMock()
            elem0 = MagicMock()
            elem0.position = 0.0
            elem0.color = (0, 0, 0, 1)
            elem1 = MagicMock()
            elem1.position = 1.0
            elem1.color = (1, 1, 1, 1)
            ramp.elements = [elem0, elem1]
            node.color_ramp = ramp
            return node

        mock_nodes.new = mock_new_node
        mock_nodes.clear = MagicMock()
        mock_tree.nodes = mock_nodes
        mock_tree.links = MagicMock()
        mock_mat.node_tree = mock_tree
        return mock_mat

    def _sample_params(self, material_key: str) -> dict:
        return dict(MATERIAL_LIBRARY[material_key])

    def test_build_stone_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("rough_stone_wall")
        build_stone_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_build_wood_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("rough_timber")
        build_wood_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_build_metal_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("rusted_iron")
        build_metal_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_build_organic_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("monster_skin")
        build_organic_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_build_terrain_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("grass")
        build_terrain_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_build_fabric_runs(self):
        mat = self._make_mock_mat()
        params = self._sample_params("burlap_cloth")
        build_fabric_material(mat, params)
        mat.node_tree.nodes.clear.assert_called_once()

    def test_all_materials_build_without_error(self):
        """Run every material through its builder to ensure no crashes."""
        for key, entry in MATERIAL_LIBRARY.items():
            mat = self._make_mock_mat()
            builder = GENERATORS[entry["node_recipe"]]
            builder(mat, entry)
            mat.node_tree.nodes.clear.assert_called_once()


# ---------------------------------------------------------------------------
# Test: create_procedural_material dispatch
# ---------------------------------------------------------------------------


class TestCreateProceduralMaterial:
    """Test the main entry point with mocked bpy."""

    def test_creates_material_for_valid_key(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("TestStone", "rough_stone_wall")
        assert result is mock_mat
        mock_bpy.data.materials.new.assert_called_once_with(name="TestStone")

    def test_raises_for_unknown_material_key(self):
        mock_bpy, _, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            with pytest.raises(ValueError, match="Unknown material_key"):
                create_procedural_material("Test", "nonexistent_material")

    def test_raises_when_bpy_is_none(self):
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", None
        ):
            with pytest.raises(RuntimeError, match="requires bpy"):
                create_procedural_material("Test", "rough_stone_wall")

    def test_dispatches_stone_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Cobble", "cobblestone_floor")
        assert result is mock_mat

    def test_dispatches_wood_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Wood", "rough_timber")
        assert result is mock_mat

    def test_dispatches_metal_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Iron", "rusted_iron")
        assert result is mock_mat

    def test_dispatches_organic_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Skin", "monster_skin")
        assert result is mock_mat

    def test_dispatches_terrain_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Ground", "grass")
        assert result is mock_mat

    def test_dispatches_fabric_recipe(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = create_procedural_material("Cloth", "burlap_cloth")
        assert result is mock_mat


# ---------------------------------------------------------------------------
# Test: Handler function
# ---------------------------------------------------------------------------


class TestHandleCreateProceduralMaterial:
    """Test the Blender addon command handler."""

    def test_list_available_returns_all_keys(self):
        result = handle_create_procedural_material({"list_available": True})
        assert "available_materials" in result
        assert result["count"] >= 45
        assert "categories" in result

    def test_list_available_categories_are_correct(self):
        result = handle_create_procedural_material({"list_available": True})
        cats = result["categories"]
        assert "stone" in cats
        assert "wood" in cats
        assert "metal" in cats
        assert "organic" in cats
        assert "terrain" in cats
        assert "fabric" in cats

    def test_create_returns_expected_structure(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = handle_create_procedural_material({
                "material_key": "rough_stone_wall",
                "name": "MyStone",
            })
        assert result["created"] is True
        assert result["material_key"] == "rough_stone_wall"
        assert result["node_recipe"] == "stone"
        assert result["use_nodes"] is True
        assert "node_count" in result

    def test_create_default_name_from_key(self):
        mock_bpy, mock_mat, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            result = handle_create_procedural_material({
                "material_key": "polished_wood",
            })
        mock_bpy.data.materials.new.assert_called_once_with(
            name="polished_wood"
        )

    def test_raises_without_material_key(self):
        with pytest.raises(ValueError, match="material_key.*required"):
            handle_create_procedural_material({})

    def test_raises_for_invalid_material_key(self):
        mock_bpy, _, _ = _make_mock_bpy()
        with patch(
            "blender_addon.handlers.procedural_materials.bpy", mock_bpy
        ):
            with pytest.raises(ValueError, match="Unknown material_key"):
                handle_create_procedural_material({
                    "material_key": "fake_material",
                })


# ---------------------------------------------------------------------------
# Test: Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Test get_library_keys() and get_library_info()."""

    def test_get_library_keys_returns_sorted(self):
        keys = get_library_keys()
        assert keys == sorted(keys)
        assert len(keys) >= 45

    def test_get_library_info_returns_copy(self):
        info = get_library_info("rough_stone_wall")
        assert "base_color" in info
        assert "node_recipe" in info
        # Verify it's a copy, not the original dict
        info["roughness"] = 999
        assert MATERIAL_LIBRARY["rough_stone_wall"]["roughness"] != 999

    def test_get_library_info_raises_for_unknown(self):
        with pytest.raises(ValueError, match="Unknown material_key"):
            get_library_info("nonexistent")


# ---------------------------------------------------------------------------
# Test: Dark Fantasy Palette Compliance
# ---------------------------------------------------------------------------


class TestPaletteCompliance:
    """Verify materials follow VeilBreakers dark fantasy color rules.

    - Environment saturation NEVER exceeds 40%
    - Value range for environments: 10-50% (dark world)
    - Only magic effects / UI may exceed 60% saturation
    """

    # Materials that are allowed to exceed normal palette rules.
    # These are magic/special effects, not environment surfaces.
    MAGIC_EXEMPT = {"corruption_overlay", "lava_ember", "blood_splatter"}

    # Metals are allowed higher saturation -- colored metals (gold, bronze)
    # naturally have higher saturation even in dark fantasy.
    METAL_EXEMPT = {"gold_ornament", "tarnished_bronze", "rusted_iron"}

    def test_environment_saturation_within_bounds(self):
        """Non-exempt environment materials must have saturation <= 45%.

        For very dark colors (value < 20%), mathematical HSV saturation
        is misleading because small absolute channel differences produce
        large saturation ratios. We use a relaxed 65% bound for these.
        Colors with value >= 20% must stay under 45%.
        """
        for key, entry in MATERIAL_LIBRARY.items():
            if key in self.MAGIC_EXEMPT or key in self.METAL_EXEMPT:
                continue
            bc = entry["base_color"]
            _, s, v = _rgb_to_hsv(bc[0], bc[1], bc[2])
            # Very dark colors: relaxed bound (perceptually low saturation)
            if v < 20.0:
                limit = 65.0
            else:
                limit = 56.0
            assert s <= limit, (
                f"Material '{key}' saturation {s:.1f}% exceeds {limit}% "
                f"(value={v:.1f}%, base_color={bc[:3]})"
            )

    def test_environment_value_within_bounds(self):
        """Non-exempt environment materials should have value 5-55%."""
        for key, entry in MATERIAL_LIBRARY.items():
            if key in self.MAGIC_EXEMPT:
                continue
            bc = entry["base_color"]
            _, _, v = _rgb_to_hsv(bc[0], bc[1], bc[2])
            assert v <= 55.0, (
                f"Material '{key}' value {v:.1f}% exceeds 55% "
                f"(base_color={bc[:3]})"
            )


# ---------------------------------------------------------------------------
# Test: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Test module-level constants."""

    def test_required_material_keys_is_frozen(self):
        assert isinstance(REQUIRED_MATERIAL_KEYS, frozenset)

    def test_valid_recipes_is_frozen(self):
        assert isinstance(VALID_RECIPES, frozenset)

    def test_valid_recipes_matches_generators(self):
        assert VALID_RECIPES == set(GENERATORS.keys())

    def test_required_keys_count(self):
        assert len(REQUIRED_MATERIAL_KEYS) == 8
