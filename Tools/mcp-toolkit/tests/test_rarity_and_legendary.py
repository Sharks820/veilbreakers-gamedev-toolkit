"""Tests for rarity_system and legendary_weapons modules.

Covers:
- RARITY_TIERS data integrity (all 5 tiers, required keys, value ranges)
- validate_rarity error handling
- get_rarity_material_tier mapping correctness
- get_rarity_tier returns copies
- apply_rarity_to_mesh with all rarities, brands, and edge cases
- compute_gem_socket_positions geometry correctness
- BRAND_EMISSION_COLORS completeness and value ranges
- RARITY_ORDER ordering
- LEGENDARY_WEAPONS registry (10 weapons, required keys)
- generate_legendary_weapon_mesh for all 10 weapons (mesh validity)
- Legendary weapon silhouette differentiation (bounding box comparison)
- Error handling for unknown legendary names
- LEGENDARY_GENERATORS registry completeness

All pure-logic -- no Blender required.
"""

from __future__ import annotations

import importlib.util
import math

import pytest


# ---------------------------------------------------------------------------
# Load modules without triggering blender_addon __init__ (needs bpy)
# ---------------------------------------------------------------------------

def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_rarity_mod = _load_module(
    "rarity_system",
    "blender_addon/handlers/rarity_system.py",
)
_legendary_mod = _load_module(
    "legendary_weapons",
    "blender_addon/handlers/legendary_weapons.py",
)

# Rarity system imports
RARITY_TIERS = _rarity_mod.RARITY_TIERS
VALID_RARITIES = _rarity_mod.VALID_RARITIES
RARITY_ORDER = _rarity_mod.RARITY_ORDER
BRAND_EMISSION_COLORS = _rarity_mod.BRAND_EMISSION_COLORS
VALID_BRANDS = _rarity_mod.VALID_BRANDS
apply_rarity_to_mesh = _rarity_mod.apply_rarity_to_mesh
compute_gem_socket_positions = _rarity_mod.compute_gem_socket_positions
get_rarity_material_tier = _rarity_mod.get_rarity_material_tier
get_rarity_tier = _rarity_mod.get_rarity_tier
validate_rarity = _rarity_mod.validate_rarity

# Legendary weapon imports
LEGENDARY_WEAPONS = _legendary_mod.LEGENDARY_WEAPONS
LEGENDARY_GENERATORS = _legendary_mod.LEGENDARY_GENERATORS
VALID_LEGENDARY_NAMES = _legendary_mod.VALID_LEGENDARY_NAMES
generate_legendary_weapon_mesh = _legendary_mod.generate_legendary_weapon_mesh


# ---------------------------------------------------------------------------
# Mesh validation helper
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
    assert meta["poly_count"] == len(faces)
    assert meta["vertex_count"] == len(verts)


# =========================================================================
# RARITY SYSTEM TESTS
# =========================================================================


class TestRarityTiersDataIntegrity:
    """Verify all rarity tier dicts have correct structure and values."""

    def test_exactly_five_tiers(self):
        assert len(RARITY_TIERS) == 5

    def test_valid_rarities_matches_tiers(self):
        assert VALID_RARITIES == frozenset(RARITY_TIERS.keys())

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_required_keys_present(self, rarity):
        tier = RARITY_TIERS[rarity]
        required = {
            "detail_multiplier", "trim_detail", "gem_sockets",
            "emission", "particle_effect", "material_tier",
            "color_saturation_boost",
        }
        missing = required - set(tier.keys())
        assert not missing, f"{rarity} missing keys: {missing}"

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_detail_multiplier_positive(self, rarity):
        assert RARITY_TIERS[rarity]["detail_multiplier"] > 0

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_gem_sockets_non_negative(self, rarity):
        assert RARITY_TIERS[rarity]["gem_sockets"] >= 0

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_emission_non_negative(self, rarity):
        assert RARITY_TIERS[rarity]["emission"] >= 0.0

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_color_saturation_boost_range(self, rarity):
        boost = RARITY_TIERS[rarity]["color_saturation_boost"]
        assert 0.0 <= boost <= 1.0

    def test_detail_multiplier_increases_with_rarity(self):
        """Higher rarities should have higher detail multipliers."""
        for i in range(len(RARITY_ORDER) - 1):
            lower = RARITY_ORDER[i]
            higher = RARITY_ORDER[i + 1]
            assert (
                RARITY_TIERS[lower]["detail_multiplier"]
                <= RARITY_TIERS[higher]["detail_multiplier"]
            ), f"{lower} has higher detail_multiplier than {higher}"

    def test_gem_sockets_increase_with_rarity(self):
        """Gem sockets should increase or stay same with rarity."""
        for i in range(len(RARITY_ORDER) - 1):
            lower = RARITY_ORDER[i]
            higher = RARITY_ORDER[i + 1]
            assert (
                RARITY_TIERS[lower]["gem_sockets"]
                <= RARITY_TIERS[higher]["gem_sockets"]
            ), f"{lower} has more gem sockets than {higher}"

    def test_emission_increases_with_rarity(self):
        """Emission should increase with rarity."""
        for i in range(len(RARITY_ORDER) - 1):
            lower = RARITY_ORDER[i]
            higher = RARITY_ORDER[i + 1]
            assert (
                RARITY_TIERS[lower]["emission"]
                <= RARITY_TIERS[higher]["emission"]
            )

    def test_legendary_has_unique_silhouette(self):
        assert RARITY_TIERS["legendary"].get("unique_silhouette") is True

    def test_common_has_no_unique_silhouette(self):
        assert RARITY_TIERS["common"].get("unique_silhouette") is not True

    def test_common_has_no_trim(self):
        assert RARITY_TIERS["common"]["trim_detail"] is False

    def test_uncommon_and_above_have_trim(self):
        for rarity in ["uncommon", "rare", "epic", "legendary"]:
            assert RARITY_TIERS[rarity]["trim_detail"] is True, f"{rarity} missing trim"

    def test_rare_and_above_have_emission_color(self):
        for rarity in ["rare", "epic", "legendary"]:
            assert "emission_color" in RARITY_TIERS[rarity], (
                f"{rarity} missing emission_color"
            )


class TestRarityOrder:
    """Verify RARITY_ORDER list correctness."""

    def test_five_entries(self):
        assert len(RARITY_ORDER) == 5

    def test_starts_with_common(self):
        assert RARITY_ORDER[0] == "common"

    def test_ends_with_legendary(self):
        assert RARITY_ORDER[-1] == "legendary"

    def test_all_rarities_included(self):
        assert set(RARITY_ORDER) == VALID_RARITIES


class TestValidateRarity:
    """Test validate_rarity function."""

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_valid_rarities(self, rarity):
        assert validate_rarity(rarity) == rarity

    def test_case_insensitive(self):
        assert validate_rarity("LEGENDARY") == "legendary"
        assert validate_rarity("Epic") == "epic"
        assert validate_rarity("  Rare  ") == "rare"

    def test_unknown_rarity_raises(self):
        with pytest.raises(ValueError, match="Unknown rarity"):
            validate_rarity("mythical")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            validate_rarity("")


class TestGetRarityMaterialTier:
    """Test get_rarity_material_tier mapping."""

    EXPECTED_MAPPING = {
        "common": "iron",
        "uncommon": "steel",
        "rare": "silver",
        "epic": "mithril",
        "legendary": "void_touched",
    }

    @pytest.mark.parametrize(
        "rarity,expected_tier",
        list(EXPECTED_MAPPING.items()),
    )
    def test_correct_mapping(self, rarity, expected_tier):
        assert get_rarity_material_tier(rarity) == expected_tier

    def test_invalid_rarity_raises(self):
        with pytest.raises(ValueError):
            get_rarity_material_tier("mythical")


class TestGetRarityTier:
    """Test get_rarity_tier function."""

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_returns_dict(self, rarity):
        result = get_rarity_tier(rarity)
        assert isinstance(result, dict)
        assert result == RARITY_TIERS[rarity]

    def test_returns_copy(self):
        """Returned dict should be a copy, not the original."""
        tier = get_rarity_tier("legendary")
        tier["detail_multiplier"] = 999
        assert RARITY_TIERS["legendary"]["detail_multiplier"] != 999


class TestBrandEmissionColors:
    """Test BRAND_EMISSION_COLORS registry."""

    EXPECTED_BRANDS = {
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    }

    def test_all_brands_present(self):
        assert set(BRAND_EMISSION_COLORS.keys()) == self.EXPECTED_BRANDS

    def test_valid_brands_frozenset(self):
        assert VALID_BRANDS == frozenset(self.EXPECTED_BRANDS)

    @pytest.mark.parametrize("brand", sorted(EXPECTED_BRANDS))
    def test_rgb_tuple_format(self, brand):
        color = BRAND_EMISSION_COLORS[brand]
        assert isinstance(color, tuple)
        assert len(color) == 3

    @pytest.mark.parametrize("brand", sorted(EXPECTED_BRANDS))
    def test_rgb_values_in_range(self, brand):
        for comp in BRAND_EMISSION_COLORS[brand]:
            assert 0.0 <= comp <= 1.0, f"{brand} has out-of-range color component {comp}"


class TestApplyRarityToMesh:
    """Test apply_rarity_to_mesh function."""

    SAMPLE_MESH = {
        "vertices": [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0.5, 2, 0), (0.5, 1.5, 0.5),
        ],
        "faces": [(0, 1, 2, 3), (2, 3, 4), (3, 4, 5)],
        "uvs": [],
        "metadata": {
            "name": "TestWeapon",
            "poly_count": 3,
            "vertex_count": 6,
        },
    }

    @pytest.mark.parametrize("rarity", sorted(RARITY_TIERS.keys()))
    def test_all_rarities_apply(self, rarity):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, rarity)
        meta = result["metadata"]
        assert meta["rarity"] == rarity
        assert "detail_multiplier" in meta
        assert "gem_sockets" in meta
        assert "material_tier" in meta
        assert "particle_effect" in meta

    def test_does_not_mutate_input(self):
        original_meta = dict(self.SAMPLE_MESH["metadata"])
        apply_rarity_to_mesh(self.SAMPLE_MESH, "legendary")
        assert self.SAMPLE_MESH["metadata"] == original_meta

    def test_common_no_emission_color(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "common")
        assert "emission_color" not in result["metadata"]

    def test_rare_with_brand_has_emission_color(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "rare", brand="SURGE")
        meta = result["metadata"]
        assert "emission_color" in meta
        assert meta["emission_color"] == BRAND_EMISSION_COLORS["SURGE"]

    def test_rare_without_brand_fallback_color(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "rare")
        meta = result["metadata"]
        assert "emission_color" in meta
        # Should be neutral white-silver fallback
        assert meta["emission_color"] == (0.8, 0.8, 0.9)

    def test_legendary_has_gem_positions(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "legendary")
        meta = result["metadata"]
        assert "gem_positions" in meta
        assert len(meta["gem_positions"]) == 3  # legendary has 3 gem sockets

    def test_common_no_gem_positions(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "common")
        meta = result["metadata"]
        assert "gem_positions" not in meta

    def test_preserves_original_metadata(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "epic")
        meta = result["metadata"]
        assert meta["name"] == "TestWeapon"
        assert meta["poly_count"] == 3
        assert meta["vertex_count"] == 6

    def test_case_insensitive_rarity(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "EPIC")
        assert result["metadata"]["rarity"] == "epic"

    def test_case_insensitive_brand(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "epic", brand="surge")
        assert result["metadata"]["emission_color"] == BRAND_EMISSION_COLORS["SURGE"]

    def test_unknown_brand_fallback(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "epic", brand="UNKNOWN_BRAND")
        meta = result["metadata"]
        assert "emission_color" in meta
        assert meta["emission_color"] == (0.8, 0.8, 0.9)

    def test_unique_silhouette_legendary(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "legendary")
        assert result["metadata"]["unique_silhouette"] is True

    def test_unique_silhouette_common(self):
        result = apply_rarity_to_mesh(self.SAMPLE_MESH, "common")
        assert result["metadata"]["unique_silhouette"] is False

    def test_empty_mesh_data_gem_positions(self):
        empty_mesh = {"vertices": [], "faces": [], "metadata": {}}
        result = apply_rarity_to_mesh(empty_mesh, "epic")
        # Should still work, gem_positions with fallback zeros
        assert result["metadata"]["gem_sockets"] == 2


class TestComputeGemSocketPositions:
    """Test compute_gem_socket_positions function."""

    SAMPLE_VERTS = [
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 2, 0), (1, 2, 0), (0.5, 3, 0),
    ]
    SAMPLE_FACES = [(0, 1, 2, 3), (2, 3, 4, 5), (4, 5, 6)]

    def test_returns_correct_count(self):
        positions = compute_gem_socket_positions(self.SAMPLE_VERTS, self.SAMPLE_FACES, 2)
        assert len(positions) == 2

    def test_positions_are_3d_tuples(self):
        positions = compute_gem_socket_positions(self.SAMPLE_VERTS, self.SAMPLE_FACES, 1)
        for pos in positions:
            assert len(pos) == 3
            for comp in pos:
                assert isinstance(comp, (int, float))

    def test_zero_count_returns_empty(self):
        positions = compute_gem_socket_positions(self.SAMPLE_VERTS, self.SAMPLE_FACES, 0)
        assert positions == []

    def test_empty_verts_fallback(self):
        positions = compute_gem_socket_positions([], [], 2)
        assert len(positions) == 2
        assert all(p == (0.0, 0.0, 0.0) for p in positions)

    def test_positions_in_upper_region(self):
        """Gem positions should prefer upper 60% of mesh."""
        positions = compute_gem_socket_positions(self.SAMPLE_VERTS, self.SAMPLE_FACES, 1)
        # y range is 0 to 3, threshold at 0.4 * 3 = 1.2
        # Positions should be at y >= 1.2 if possible
        for pos in positions:
            assert pos[1] >= 1.0  # should be in upper region

    def test_more_sockets_than_faces(self):
        """Requesting more sockets than faces should not crash."""
        positions = compute_gem_socket_positions(self.SAMPLE_VERTS, self.SAMPLE_FACES, 10)
        assert len(positions) == 10

    def test_single_triangle(self):
        verts = [(0, 0, 0), (1, 0, 0), (0.5, 1, 0)]
        faces = [(0, 1, 2)]
        positions = compute_gem_socket_positions(verts, faces, 1)
        assert len(positions) == 1
        # Centroid should be approximately (0.5, 0.33, 0)
        assert abs(positions[0][0] - 0.5) < 0.01
        assert abs(positions[0][1] - 1.0 / 3.0) < 0.01


# =========================================================================
# LEGENDARY WEAPONS TESTS
# =========================================================================


class TestLegendaryWeaponsRegistry:
    """Verify LEGENDARY_WEAPONS registry completeness."""

    def test_exactly_ten_weapons(self):
        assert len(LEGENDARY_WEAPONS) == 10

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_required_keys(self, weapon):
        data = LEGENDARY_WEAPONS[weapon]
        for key in ("type", "feature", "desc"):
            assert key in data, f"{weapon} missing key: {key}"

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_desc_not_empty(self, weapon):
        assert len(LEGENDARY_WEAPONS[weapon]["desc"]) > 10

    def test_unique_features(self):
        """Each legendary weapon must have a unique feature."""
        features = [w["feature"] for w in LEGENDARY_WEAPONS.values()]
        assert len(features) == len(set(features)), "Duplicate features found"

    def test_valid_legendary_names_matches(self):
        assert VALID_LEGENDARY_NAMES == frozenset(LEGENDARY_WEAPONS.keys())


class TestLegendaryGeneratorsRegistry:
    """Verify LEGENDARY_GENERATORS registry matches LEGENDARY_WEAPONS."""

    def test_same_keys(self):
        assert set(LEGENDARY_GENERATORS.keys()) == set(LEGENDARY_WEAPONS.keys())

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_GENERATORS.keys()))
    def test_generators_are_callable(self, weapon):
        assert callable(LEGENDARY_GENERATORS[weapon])


class TestGenerateLegendaryWeaponMesh:
    """Test generate_legendary_weapon_mesh for all weapons."""

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_generates_valid_mesh(self, weapon):
        result = generate_legendary_weapon_mesh(weapon)
        validate_mesh_spec(result, weapon, min_verts=20, min_faces=10)

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_has_legendary_metadata(self, weapon):
        result = generate_legendary_weapon_mesh(weapon)
        meta = result["metadata"]
        assert meta.get("legendary_name") == weapon
        assert "weapon_type" in meta
        assert "feature" in meta
        assert meta["category"] == "legendary_weapon"

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_has_combat_metadata(self, weapon):
        """Legendary weapons should have grip/trail points."""
        result = generate_legendary_weapon_mesh(weapon)
        meta = result["metadata"]
        assert "grip_point" in meta, f"{weapon} missing grip_point"
        assert "trail_top" in meta, f"{weapon} missing trail_top"
        assert "trail_bottom" in meta, f"{weapon} missing trail_bottom"

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_weapon_type_matches_registry(self, weapon):
        result = generate_legendary_weapon_mesh(weapon)
        meta = result["metadata"]
        assert meta["weapon_type"] == LEGENDARY_WEAPONS[weapon]["type"]

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_feature_matches_registry(self, weapon):
        result = generate_legendary_weapon_mesh(weapon)
        meta = result["metadata"]
        assert meta["feature"] == LEGENDARY_WEAPONS[weapon]["feature"]

    def test_unknown_weapon_raises(self):
        with pytest.raises(ValueError, match="Unknown legendary weapon"):
            generate_legendary_weapon_mesh("excalibur")

    def test_case_insensitive(self):
        result = generate_legendary_weapon_mesh("VOIDREAVER")
        assert result["metadata"]["legendary_name"] == "voidreaver"

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_has_dimensions(self, weapon):
        result = generate_legendary_weapon_mesh(weapon)
        dims = result["metadata"]["dimensions"]
        assert "width" in dims
        assert "height" in dims
        assert "depth" in dims
        assert dims["width"] > 0 or dims["height"] > 0 or dims["depth"] > 0


class TestLegendarySilhouetteDifferentiation:
    """Verify legendary weapons have dramatically different silhouettes
    from each other -- measured by bounding box aspect ratios."""

    @pytest.fixture(scope="class")
    def all_meshes(self):
        return {
            name: generate_legendary_weapon_mesh(name)
            for name in LEGENDARY_WEAPONS
        }

    def _bbox_signature(self, mesh: dict) -> tuple[float, float, float]:
        """Return (width, height, depth) bounding box of mesh."""
        dims = mesh["metadata"]["dimensions"]
        return (dims["width"], dims["height"], dims["depth"])

    def test_unique_bounding_boxes(self, all_meshes):
        """No two legendary weapons should have identical bounding boxes."""
        signatures = []
        for name, mesh in all_meshes.items():
            sig = self._bbox_signature(mesh)
            signatures.append((name, sig))

        for i in range(len(signatures)):
            for j in range(i + 1, len(signatures)):
                name_i, sig_i = signatures[i]
                name_j, sig_j = signatures[j]
                # Check they differ in at least one dimension by > 5%
                same = all(
                    abs(a - b) < max(abs(a), abs(b), 0.001) * 0.05
                    for a, b in zip(sig_i, sig_j)
                )
                assert not same, (
                    f"{name_i} and {name_j} have nearly identical bounding boxes: "
                    f"{sig_i} vs {sig_j}"
                )

    def test_minimum_poly_counts(self, all_meshes):
        """Legendary weapons should have substantial geometry."""
        for name, mesh in all_meshes.items():
            poly_count = mesh["metadata"]["poly_count"]
            assert poly_count >= 30, (
                f"{name} has only {poly_count} polys -- too simple for legendary"
            )

    def test_vertex_counts_reasonable(self, all_meshes):
        """Should have enough vertices for detail but not be absurdly high."""
        for name, mesh in all_meshes.items():
            vert_count = mesh["metadata"]["vertex_count"]
            assert 30 <= vert_count <= 5000, (
                f"{name} has {vert_count} vertices -- outside reasonable range"
            )


class TestLegendaryWithRarity:
    """Test interaction between legendary weapons and rarity system."""

    @pytest.mark.parametrize("weapon", sorted(LEGENDARY_WEAPONS.keys()))
    def test_apply_legendary_rarity(self, weapon):
        """Legendary rarity should apply cleanly to legendary weapons."""
        mesh = generate_legendary_weapon_mesh(weapon)
        result = apply_rarity_to_mesh(mesh, "legendary", brand="VOID")
        meta = result["metadata"]
        assert meta["rarity"] == "legendary"
        assert meta["unique_silhouette"] is True
        assert meta["emission"] == 0.5
        assert meta["gem_sockets"] == 3
        assert "gem_positions" in meta
        assert len(meta["gem_positions"]) == 3
        assert meta["emission_color"] == BRAND_EMISSION_COLORS["VOID"]

    @pytest.mark.parametrize("weapon", ["voidreaver", "chainbreaker"])
    @pytest.mark.parametrize("brand", ["IRON", "SURGE", "VOID"])
    def test_different_brands_different_colors(self, weapon, brand):
        mesh = generate_legendary_weapon_mesh(weapon)
        result = apply_rarity_to_mesh(mesh, "epic", brand=brand)
        assert result["metadata"]["emission_color"] == BRAND_EMISSION_COLORS[brand]

    def test_legendary_weapon_with_common_rarity(self):
        """Even legendary weapon mesh can have common rarity applied."""
        mesh = generate_legendary_weapon_mesh("voidreaver")
        result = apply_rarity_to_mesh(mesh, "common")
        meta = result["metadata"]
        assert meta["rarity"] == "common"
        assert meta["emission"] == 0.0
        assert meta["gem_sockets"] == 0
        assert meta["unique_silhouette"] is False
