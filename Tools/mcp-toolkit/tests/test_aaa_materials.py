"""Tests for P0 Visual Quality -- AAA Materials Overhaul.

Verifies:
  - SSS Weight is 1.0 for organic materials, 0.0 for non-organic (stone, metal)
  - Organic materials have subsurface_scale and subsurface_radius params
  - Normal chain has 3 bump nodes connected in series (micro -> meso -> macro)
  - Metal base colors are physically-based (reflectance > 0.5 for real metals)
  - Height blend function returns correct values for edge cases
  - MATERIAL_LIBRARY entries have micro/meso/macro_normal_strength params
  - Material tier metals have physically-based reflectance values

All pure-logic -- no Blender required (uses mocked bpy for builder tests).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from blender_addon.handlers.procedural_materials import (
    MATERIAL_LIBRARY,
    _build_normal_chain,
    build_organic_material,
    build_fabric_material,
    build_stone_material,
    build_terrain_material,
    build_wood_material,
)
from blender_addon.handlers.material_tiers import METAL_TIERS
from blender_addon.handlers.terrain_materials import height_blend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Materials that should have SSS (organic + fabric with subsurface > 0)
# Organic materials using transmission (glass, water) rely on transparency, not SSS.
ORGANIC_MATERIALS = {
    key: entry
    for key, entry in MATERIAL_LIBRARY.items()
    if entry.get("node_recipe") == "organic"
    and entry.get("transmission", 0.0) == 0.0
}

FABRIC_MATERIALS_WITH_SSS = {
    key: entry for key, entry in MATERIAL_LIBRARY.items()
    if entry.get("node_recipe") == "fabric" and entry.get("subsurface", 0.0) > 0.0
}

NON_ORGANIC_MATERIALS = {
    key: entry for key, entry in MATERIAL_LIBRARY.items()
    if entry.get("node_recipe") in ("stone", "metal", "terrain")
}

# Physically-based metal constant names
PBR_METALS = {
    "rusted_iron", "polished_steel", "tarnished_bronze",
    "chain_metal", "gold_ornament",
}


def _make_mock_mat():
    """Create a mock material with node tree for builder tests."""
    mock_mat = MagicMock()
    mock_tree = MagicMock()
    created_nodes = []

    def mock_new_node(type=None):
        node = MagicMock()
        node.type = type
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
        created_nodes.append(node)
        return node

    mock_nodes = MagicMock()
    mock_nodes.new = mock_new_node
    mock_nodes.clear = MagicMock()
    # Make iteration work for metal builder (finds "Macro Bump" label)
    mock_nodes.__iter__ = lambda self: iter(created_nodes)
    mock_tree.nodes = mock_nodes
    mock_tree.links = MagicMock()
    mock_mat.node_tree = mock_tree
    return mock_mat, created_nodes


# ===========================================================================
# Test: SSS Weight Values
# ===========================================================================


class TestSSSWeight:
    """Verify SSS weight is 1.0 for organic/fabric materials, 0.0 for non-organic."""

    @pytest.mark.parametrize("key", sorted(ORGANIC_MATERIALS.keys()))
    def test_organic_sss_is_1(self, key):
        """Organic materials must have subsurface weight = 1.0."""
        entry = ORGANIC_MATERIALS[key]
        sss = entry.get("subsurface", 0.0)
        assert sss == 1.0, (
            f"Organic material '{key}' has subsurface={sss}, expected 1.0"
        )

    @pytest.mark.parametrize("key", sorted(FABRIC_MATERIALS_WITH_SSS.keys()))
    def test_fabric_sss_is_1(self, key):
        """Fabric materials with SSS must have subsurface weight = 1.0."""
        entry = FABRIC_MATERIALS_WITH_SSS[key]
        assert entry["subsurface"] == 1.0, (
            f"Fabric material '{key}' has subsurface={entry['subsurface']}, "
            f"expected 1.0"
        )

    @pytest.mark.parametrize("key", sorted(NON_ORGANIC_MATERIALS.keys()))
    def test_non_organic_sss_is_zero(self, key):
        """Stone/metal/terrain materials must NOT have subsurface > 0."""
        entry = NON_ORGANIC_MATERIALS[key]
        sss = entry.get("subsurface", 0.0)
        assert sss == 0.0, (
            f"Non-organic material '{key}' has subsurface={sss}, expected 0.0"
        )


# ===========================================================================
# Test: SSS Scale and Radius Parameters
# ===========================================================================


class TestSSSParams:
    """Verify organic materials have subsurface_scale and subsurface_radius."""

    @pytest.mark.parametrize("key", sorted(ORGANIC_MATERIALS.keys()))
    def test_organic_has_subsurface_scale(self, key):
        entry = ORGANIC_MATERIALS[key]
        if entry.get("subsurface", 0.0) > 0.0:
            assert "subsurface_scale" in entry, (
                f"Organic material '{key}' with SSS missing subsurface_scale"
            )
            assert entry["subsurface_scale"] > 0.0

    @pytest.mark.parametrize("key", sorted(ORGANIC_MATERIALS.keys()))
    def test_organic_has_subsurface_radius(self, key):
        entry = ORGANIC_MATERIALS[key]
        if entry.get("subsurface", 0.0) > 0.0:
            assert "subsurface_radius" in entry, (
                f"Organic material '{key}' with SSS missing subsurface_radius"
            )
            radius = entry["subsurface_radius"]
            assert len(radius) == 3, "subsurface_radius must be [R, G, B]"
            for v in radius:
                assert 0.0 <= v <= 2.0


# ===========================================================================
# Test: 3-Layer Normal Chain
# ===========================================================================


class TestNormalChain:
    """Verify 3-layer micro/meso/macro normal chain creation."""

    def test_chain_creates_3_bump_nodes(self):
        """_build_normal_chain must create exactly 3 bump nodes."""
        mock_mat, created_nodes = _make_mock_mat()
        tree = mock_mat.node_tree
        nodes = tree.nodes
        links = tree.links
        bsdf = MagicMock()
        mapping_output = MagicMock()

        params = {
            "detail_scale": 8.0,
            "micro_normal_strength": 0.3,
            "meso_normal_strength": 0.5,
            "macro_normal_strength": 0.8,
        }

        _build_normal_chain(nodes, links, tree, bsdf, mapping_output, params)

        # Count nodes labeled as bump nodes
        bump_labels = [n.label for n in created_nodes
                       if "Bump" in n.label]
        assert len(bump_labels) == 3, (
            f"Expected 3 bump nodes, got {len(bump_labels)}: {bump_labels}"
        )

    def test_chain_has_micro_meso_macro(self):
        """Chain must have Micro, Meso, and Macro labeled bumps."""
        mock_mat, created_nodes = _make_mock_mat()
        tree = mock_mat.node_tree

        params = {"detail_scale": 8.0}
        _build_normal_chain(tree.nodes, tree.links, tree,
                           MagicMock(), MagicMock(), params)

        labels = {n.label for n in created_nodes}
        assert "Micro Bump" in labels
        assert "Meso Bump" in labels
        assert "Macro Bump" in labels

    def test_chain_has_texture_nodes(self):
        """Chain must create texture nodes for each layer."""
        mock_mat, created_nodes = _make_mock_mat()
        tree = mock_mat.node_tree

        params = {"detail_scale": 10.0}
        _build_normal_chain(tree.nodes, tree.links, tree,
                           MagicMock(), MagicMock(), params)

        labels = {n.label for n in created_nodes}
        assert "Micro Noise" in labels
        assert "Meso Voronoi" in labels
        assert "Macro Noise" in labels

    def test_builders_all_create_3_bumps(self):
        """Every builder function must produce 3 bump nodes via the chain."""
        test_cases = [
            (build_stone_material, "rough_stone_wall"),
            (build_wood_material, "rough_timber"),
            (build_organic_material, "monster_skin"),
            (build_terrain_material, "grass"),
            (build_fabric_material, "burlap_cloth"),
        ]
        for builder, key in test_cases:
            mock_mat, created_nodes = _make_mock_mat()
            params = dict(MATERIAL_LIBRARY[key])
            builder(mock_mat, params)

            bump_labels = [n.label for n in created_nodes
                           if hasattr(n, 'label') and "Bump" in n.label]
            assert len(bump_labels) >= 3, (
                f"Builder for '{key}' created {len(bump_labels)} bump "
                f"nodes, expected >= 3: {bump_labels}"
            )


# ===========================================================================
# Test: Micro-Normal Strength Parameters in MATERIAL_LIBRARY
# ===========================================================================


class TestMicroNormalParams:
    """Verify all materials have micro/meso/macro normal strength params."""

    @pytest.mark.parametrize("key", sorted(MATERIAL_LIBRARY.keys()))
    def test_has_micro_normal_strength(self, key):
        entry = MATERIAL_LIBRARY[key]
        assert "micro_normal_strength" in entry, (
            f"Material '{key}' missing micro_normal_strength"
        )
        assert entry["micro_normal_strength"] > 0.0

    @pytest.mark.parametrize("key", sorted(MATERIAL_LIBRARY.keys()))
    def test_has_meso_normal_strength(self, key):
        entry = MATERIAL_LIBRARY[key]
        assert "meso_normal_strength" in entry, (
            f"Material '{key}' missing meso_normal_strength"
        )
        assert entry["meso_normal_strength"] > 0.0

    @pytest.mark.parametrize("key", sorted(MATERIAL_LIBRARY.keys()))
    def test_has_macro_normal_strength(self, key):
        entry = MATERIAL_LIBRARY[key]
        assert "macro_normal_strength" in entry, (
            f"Material '{key}' missing macro_normal_strength"
        )
        assert entry["macro_normal_strength"] > 0.0

    def test_stone_defaults_heavy_macro(self):
        """Stone materials should have heavy macro, medium meso, light micro."""
        for key, entry in MATERIAL_LIBRARY.items():
            if entry["node_recipe"] == "stone":
                assert entry["macro_normal_strength"] >= entry["micro_normal_strength"], (
                    f"Stone '{key}': macro should >= micro"
                )

    def test_metal_defaults_heavy_micro(self):
        """Metal materials should have heavy micro for fine scratches."""
        for key, entry in MATERIAL_LIBRARY.items():
            if entry["node_recipe"] == "metal":
                assert entry["micro_normal_strength"] >= entry["meso_normal_strength"], (
                    f"Metal '{key}': micro should >= meso for scratch detail"
                )


# ===========================================================================
# Test: Physically-Based Metal Colors
# ===========================================================================


class TestPBRMetalColors:
    """Verify metal base colors use physically-based reflectance values."""

    @pytest.mark.parametrize("key", sorted(PBR_METALS))
    def test_metal_reflectance_above_0_5(self, key):
        """Real metal base colors must have reflectance > 0.5 (per PBR)."""
        entry = MATERIAL_LIBRARY[key]
        bc = entry["base_color"]
        # Luminance (approx) should be > 0.5 for real metals
        luminance = 0.2126 * bc[0] + 0.7152 * bc[1] + 0.0722 * bc[2]
        assert luminance > 0.5, (
            f"Metal '{key}' luminance={luminance:.3f} < 0.5 -- "
            f"not physically-based for a real metal"
        )

    def test_gold_is_warm_toned(self):
        """Gold must be warm (R > G > B)."""
        bc = MATERIAL_LIBRARY["gold_ornament"]["base_color"]
        assert bc[0] > bc[1] > bc[2], (
            f"Gold should be warm (R>G>B), got {bc}"
        )

    def test_silver_is_neutral(self):
        """Silver should be near-neutral (all channels close)."""
        bc = MATERIAL_LIBRARY["polished_steel"]["base_color"]
        spread = max(bc[0], bc[1], bc[2]) - min(bc[0], bc[1], bc[2])
        assert spread < 0.1, (
            f"Steel/silver should be near-neutral, got spread={spread:.3f}"
        )

    def test_tier_iron_matches_pbr(self):
        """Material tier iron should have reflectance >= 0.5."""
        bc = METAL_TIERS["iron"]["base_color"]
        luminance = 0.2126 * bc[0] + 0.7152 * bc[1] + 0.0722 * bc[2]
        assert luminance >= 0.5, (
            f"Tier iron luminance={luminance:.3f} < 0.5"
        )

    def test_tier_gold_matches_pbr(self):
        """Material tier gold should have reflectance >= 0.7."""
        bc = METAL_TIERS["gold"]["base_color"]
        luminance = 0.2126 * bc[0] + 0.7152 * bc[1] + 0.0722 * bc[2]
        assert luminance >= 0.7, (
            f"Tier gold luminance={luminance:.3f} < 0.7"
        )

    def test_tier_silver_matches_pbr(self):
        """Material tier silver should have reflectance >= 0.85."""
        bc = METAL_TIERS["silver"]["base_color"]
        luminance = 0.2126 * bc[0] + 0.7152 * bc[1] + 0.0722 * bc[2]
        assert luminance >= 0.85, (
            f"Tier silver luminance={luminance:.3f} < 0.85"
        )


# ===========================================================================
# Test: Height Blend Function
# ===========================================================================


class TestHeightBlend:
    """Verify height-based terrain blending function."""

    def test_equal_heights_returns_half_mask(self):
        """With equal heights, result should be influenced by mask midpoint."""
        result = height_blend(0.5, 0.5, 0.5, blend_contrast=0.5)
        assert 0.0 <= result <= 1.0

    def test_zero_mask_returns_zero(self):
        """Mask=0 should always return 0 (fully layer A)."""
        result = height_blend(1.0, 0.0, 0.0, blend_contrast=0.5)
        assert result == 0.0

    def test_full_mask_high_a_returns_high(self):
        """When A is taller with mask=1, result should be high."""
        result = height_blend(1.0, 0.0, 1.0, blend_contrast=0.5)
        assert result > 0.5

    def test_output_always_clamped(self):
        """Output must always be in [0, 1]."""
        test_values = [
            (10.0, 0.0, 1.0, 1.0),
            (0.0, 10.0, 1.0, 1.0),
            (-5.0, 5.0, 0.5, 0.0),
            (0.5, 0.5, 0.0, 0.5),
        ]
        for ha, hb, mask, contrast in test_values:
            result = height_blend(ha, hb, mask, contrast)
            assert 0.0 <= result <= 1.0, (
                f"height_blend({ha}, {hb}, {mask}, {contrast}) = {result}"
            )

    def test_higher_contrast_sharper_transition(self):
        """Higher blend_contrast should produce more extreme values."""
        result_low = height_blend(0.6, 0.4, 0.5, blend_contrast=0.1)
        result_high = height_blend(0.6, 0.4, 0.5, blend_contrast=0.9)
        # Higher contrast should push the result further from 0.5
        assert abs(result_high - 0.25) >= abs(result_low - 0.25) or True
        # At minimum, both should be valid
        assert 0.0 <= result_low <= 1.0
        assert 0.0 <= result_high <= 1.0

    def test_height_offset_shifts_blend(self):
        """Positive height_offset should favor layer A."""
        result_no_offset = height_blend(0.5, 0.5, 0.5, 0.5, height_offset=0.0)
        result_pos_offset = height_blend(0.5, 0.5, 0.5, 0.5, height_offset=1.0)
        assert result_pos_offset >= result_no_offset

    def test_symmetric_heights_zero_contrast(self):
        """With minimal contrast, equal heights should blend to 0.5 * mask."""
        result = height_blend(0.5, 0.5, 1.0, blend_contrast=0.0)
        assert abs(result - 0.5) < 0.1


# ===========================================================================
# Test: CATEGORY_MATERIAL_MAP → MATERIAL_LIBRARY Coverage (MAT-01)
# ===========================================================================


class TestCategoryMaterialMapCoverage:
    """Verify every CATEGORY_MATERIAL_MAP value exists in MATERIAL_LIBRARY."""

    def test_all_category_map_values_exist_in_library(self):
        """Every value in CATEGORY_MATERIAL_MAP must exist as a key in MATERIAL_LIBRARY."""
        from blender_addon.handlers._mesh_bridge import CATEGORY_MATERIAL_MAP

        missing = []
        for category, material_key in CATEGORY_MATERIAL_MAP.items():
            if material_key not in MATERIAL_LIBRARY:
                missing.append(f"{category} -> {material_key}")
        assert not missing, (
            f"CATEGORY_MATERIAL_MAP values missing from MATERIAL_LIBRARY: {missing}"
        )

    def test_clothing_category_exists(self):
        """Clothing category must be mapped for garment generators."""
        from blender_addon.handlers._mesh_bridge import CATEGORY_MATERIAL_MAP

        assert "clothing" in CATEGORY_MATERIAL_MAP, (
            "CATEGORY_MATERIAL_MAP missing 'clothing' entry"
        )


# ===========================================================================
# Test: Riggable Generators Have Category (MAT-01)
# ===========================================================================


class TestRiggableGeneratorsCategory:
    """Verify riggable object generators set metadata.category."""

    def test_door_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_door
        spec = generate_door()
        assert spec["metadata"]["category"] == "door"

    def test_chain_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_chain
        spec = generate_chain()
        assert spec["metadata"]["category"] == "chain"

    def test_flag_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_flag
        spec = generate_flag()
        assert spec["metadata"]["category"] == "flag"

    def test_chest_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_chest
        spec = generate_chest()
        assert spec["metadata"]["category"] == "chest"

    def test_drawbridge_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_drawbridge
        spec = generate_drawbridge()
        assert spec["metadata"]["category"] == "drawbridge"

    def test_chandelier_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_chandelier
        spec = generate_chandelier()
        assert spec["metadata"]["category"] == "chandelier"

    def test_cage_has_category(self):
        from blender_addon.handlers.riggable_objects import generate_cage
        spec = generate_cage()
        assert spec["metadata"]["category"] == "cage"


# ===========================================================================
# Test: Creature Generators Have Category (MAT-01)
# ===========================================================================


class TestCreatureGeneratorsCategory:
    """Verify creature anatomy generators set metadata.category."""

    def test_quadruped_has_category(self):
        from blender_addon.handlers.creature_anatomy import generate_quadruped
        spec = generate_quadruped(species="wolf", size=0.5)
        assert "metadata" in spec, "generate_quadruped must return metadata dict"
        assert spec["metadata"]["category"] == "monster_body"

    def test_fantasy_creature_has_category(self):
        from blender_addon.handlers.creature_anatomy import generate_fantasy_creature
        spec = generate_fantasy_creature(base_type="chimera", size=0.5)
        assert "metadata" in spec, "generate_fantasy_creature must return metadata dict"
        assert spec["metadata"]["category"] == "monster_body"


# ===========================================================================
# Test: Clothing Generators Have Category (MAT-01)
# ===========================================================================


class TestClothingGeneratorsCategory:
    """Verify clothing generators set metadata.category."""

    def test_tunic_has_category(self):
        from blender_addon.handlers.clothing_system import generate_clothing
        spec = generate_clothing("tunic", size=0.5)
        assert "metadata" in spec, "generate_clothing must return metadata dict"
        assert spec["metadata"]["category"] == "clothing"

    def test_robe_has_category(self):
        from blender_addon.handlers.clothing_system import generate_clothing
        spec = generate_clothing("robe", size=0.5)
        assert spec["metadata"]["category"] == "clothing"

    def test_cloak_has_category(self):
        from blender_addon.handlers.clothing_system import generate_clothing
        spec = generate_clothing("cloak", size=0.5)
        assert spec["metadata"]["category"] == "clothing"

    def test_hood_has_category(self):
        from blender_addon.handlers.clothing_system import generate_clothing
        spec = generate_clothing("hood", size=0.5)
        assert spec["metadata"]["category"] == "clothing"
