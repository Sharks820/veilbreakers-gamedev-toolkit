"""Tests for the MeshSpec-to-Blender bridge module.

Validates:
- All mapping tables have the expected keys
- Every mapped generator is callable and returns valid MeshSpec
- generate_lod_specs produces correct LOD chain
- resolve_generator returns correct results for all maps
- Pure-logic validation (no bpy-dependent mesh_from_spec)
"""

from __future__ import annotations

import pytest

from blender_addon.handlers._mesh_bridge import (
    FURNITURE_GENERATOR_MAP,
    VEGETATION_GENERATOR_MAP,
    DUNGEON_PROP_MAP,
    CASTLE_ELEMENT_MAP,
    PROP_GENERATOR_MAP,
    CATEGORY_MATERIAL_MAP,
    generate_lod_specs,
    resolve_generator,
    get_material_for_category,
    post_boolean_cleanup,
)


# ---------------------------------------------------------------------------
# Helper validation
# ---------------------------------------------------------------------------


def validate_mesh_spec(spec: dict, label: str) -> None:
    """Assert that a dict is a valid MeshSpec."""
    assert "vertices" in spec, f"{label}: missing 'vertices'"
    assert "faces" in spec, f"{label}: missing 'faces'"
    assert "uvs" in spec, f"{label}: missing 'uvs'"
    assert "metadata" in spec, f"{label}: missing 'metadata'"

    verts = spec["vertices"]
    faces = spec["faces"]
    meta = spec["metadata"]

    assert len(verts) >= 4, f"{label}: expected >= 4 vertices, got {len(verts)}"
    assert len(faces) >= 1, f"{label}: expected >= 1 faces, got {len(faces)}"

    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{label}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{label}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    assert "name" in meta, f"{label}: metadata missing 'name'"
    assert "poly_count" in meta, f"{label}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{label}: metadata missing 'vertex_count'"


# ---------------------------------------------------------------------------
# FURNITURE_GENERATOR_MAP tests
# ---------------------------------------------------------------------------


FURNITURE_DIRECT_MATCH_KEYS = [
    "table", "chair", "shelf", "chest", "barrel", "candelabra",
    "bookshelf", "altar", "pillar", "brazier", "chandelier", "crate",
    "rug", "banner", "anvil", "forge", "workbench", "cauldron",
    "sarcophagus", "chain",
]

FURNITURE_CLOSE_MATCH_KEYS = [
    "large_table", "long_table", "serving_table", "desk",
    "locked_chest", "carpet", "cage", "shelf_with_bottles", "wall_tomb",
]


class TestFurnitureGeneratorMap:
    """Tests for FURNITURE_GENERATOR_MAP completeness and correctness."""

    @pytest.mark.parametrize("key", FURNITURE_DIRECT_MATCH_KEYS)
    def test_has_direct_match_entry(self, key: str) -> None:
        assert key in FURNITURE_GENERATOR_MAP, (
            f"FURNITURE_GENERATOR_MAP missing direct-match key '{key}'"
        )

    @pytest.mark.parametrize("key", FURNITURE_CLOSE_MATCH_KEYS)
    def test_has_close_match_entry(self, key: str) -> None:
        assert key in FURNITURE_GENERATOR_MAP, (
            f"FURNITURE_GENERATOR_MAP missing close-match key '{key}'"
        )

    def test_total_entries_at_least_29(self) -> None:
        assert len(FURNITURE_GENERATOR_MAP) >= 29, (
            f"Expected >= 29 furniture entries, got {len(FURNITURE_GENERATOR_MAP)}"
        )

    @pytest.mark.parametrize("key", FURNITURE_DIRECT_MATCH_KEYS + FURNITURE_CLOSE_MATCH_KEYS)
    def test_generator_returns_valid_mesh_spec(self, key: str) -> None:
        gen_func, kwargs = FURNITURE_GENERATOR_MAP[key]
        assert callable(gen_func), f"Generator for '{key}' is not callable"
        spec = gen_func(**kwargs)
        validate_mesh_spec(spec, f"FURNITURE[{key}]")

    def test_large_table_uses_wider_dimensions(self) -> None:
        gen_func, kwargs = FURNITURE_GENERATOR_MAP["large_table"]
        assert kwargs.get("width", 0) >= 1.5, "large_table should be wider than default"

    def test_long_table_uses_long_depth(self) -> None:
        gen_func, kwargs = FURNITURE_GENERATOR_MAP["long_table"]
        assert kwargs.get("depth", 0) >= 3.0, "long_table should have extended depth"

    def test_desk_uses_noble_style(self) -> None:
        gen_func, kwargs = FURNITURE_GENERATOR_MAP["desk"]
        assert kwargs.get("style") == "noble_carved", "desk should use noble_carved style"

    def test_locked_chest_uses_iron_style(self) -> None:
        gen_func, kwargs = FURNITURE_GENERATOR_MAP["locked_chest"]
        # The chest generator supports "iron_locked" style
        assert "iron" in kwargs.get("style", ""), (
            "locked_chest should use an iron-bound/locked style"
        )


# ---------------------------------------------------------------------------
# VEGETATION_GENERATOR_MAP tests
# ---------------------------------------------------------------------------


VEGETATION_KEYS = [
    "tree",
    "tree_healthy",
    "tree_boundary",
    "tree_blighted",
    "dead_tree",
    "tree_twisted",
    "bush",
    "grass",
    "rock",
    "rock_mossy",
    "mushroom",
    "mushroom_cluster",
    "root",
]


class TestVegetationGeneratorMap:
    """Tests for VEGETATION_GENERATOR_MAP completeness and correctness."""

    @pytest.mark.parametrize("key", VEGETATION_KEYS)
    def test_has_entry(self, key: str) -> None:
        assert key in VEGETATION_GENERATOR_MAP, (
            f"VEGETATION_GENERATOR_MAP missing key '{key}'"
        )

    @pytest.mark.parametrize("key", VEGETATION_KEYS)
    def test_generator_returns_valid_mesh_spec(self, key: str) -> None:
        gen_func, kwargs = VEGETATION_GENERATOR_MAP[key]
        assert callable(gen_func), f"Generator for '{key}' is not callable"
        spec = gen_func(**kwargs)
        validate_mesh_spec(spec, f"VEGETATION[{key}]")

    def test_settlement_defaults_do_not_use_dead_tree_or_mushroom_placeholders(self) -> None:
        tree_func, tree_kwargs = VEGETATION_GENERATOR_MAP["tree"]
        bush_func, bush_kwargs = VEGETATION_GENERATOR_MAP["bush"]

        assert tree_kwargs.get("canopy_style") == "veil_healthy"
        assert bush_func.__name__ != "generate_mushroom_mesh"

    def test_thornwood_aliases_resolve_to_progression_tree_styles(self) -> None:
        assert VEGETATION_GENERATOR_MAP["tree_boundary"][1]["canopy_style"] == "veil_boundary"
        assert VEGETATION_GENERATOR_MAP["tree_blighted"][1]["canopy_style"] == "veil_blighted"
        assert VEGETATION_GENERATOR_MAP["dead_tree"][1]["tree_type"] == "dead"
        assert VEGETATION_GENERATOR_MAP["tree_twisted"][1]["canopy_style"] == "veil_boundary"


# ---------------------------------------------------------------------------
# DUNGEON_PROP_MAP tests
# ---------------------------------------------------------------------------


DUNGEON_PROP_KEYS = [
    "torch_sconce", "altar", "prison_door", "spike_trap", "bear_trap",
    "pressure_plate", "dart_launcher", "swinging_blade", "falling_cage",
    "skull_pile", "sarcophagus", "chain", "archway", "pillar",
]


class TestDungeonPropMap:
    """Tests for DUNGEON_PROP_MAP completeness and correctness."""

    @pytest.mark.parametrize("key", DUNGEON_PROP_KEYS)
    def test_has_entry(self, key: str) -> None:
        assert key in DUNGEON_PROP_MAP, (
            f"DUNGEON_PROP_MAP missing key '{key}'"
        )

    @pytest.mark.parametrize("key", DUNGEON_PROP_KEYS)
    def test_generator_returns_valid_mesh_spec(self, key: str) -> None:
        gen_func, kwargs = DUNGEON_PROP_MAP[key]
        assert callable(gen_func), f"Generator for '{key}' is not callable"
        spec = gen_func(**kwargs)
        validate_mesh_spec(spec, f"DUNGEON_PROP[{key}]")


# ---------------------------------------------------------------------------
# CASTLE_ELEMENT_MAP tests
# ---------------------------------------------------------------------------


CASTLE_ELEMENT_KEYS = ["gate", "rampart", "drawbridge", "fountain", "pillar"]


class TestCastleElementMap:
    """Tests for CASTLE_ELEMENT_MAP completeness and correctness."""

    @pytest.mark.parametrize("key", CASTLE_ELEMENT_KEYS)
    def test_has_entry(self, key: str) -> None:
        assert key in CASTLE_ELEMENT_MAP, (
            f"CASTLE_ELEMENT_MAP missing key '{key}'"
        )

    @pytest.mark.parametrize("key", CASTLE_ELEMENT_KEYS)
    def test_generator_returns_valid_mesh_spec(self, key: str) -> None:
        gen_func, kwargs = CASTLE_ELEMENT_MAP[key]
        assert callable(gen_func), f"Generator for '{key}' is not callable"
        spec = gen_func(**kwargs)
        validate_mesh_spec(spec, f"CASTLE[{key}]")


# ---------------------------------------------------------------------------
# generate_lod_specs tests
# ---------------------------------------------------------------------------


def _make_test_spec(face_count: int = 20, name: str = "TestMesh") -> dict:
    """Create a minimal valid MeshSpec for LOD testing."""
    # Create a simple grid of vertices and quad faces
    verts = []
    size = face_count + 5  # ensure enough vertices
    for i in range(size):
        verts.append((float(i), 0.0, 0.0))
        verts.append((float(i), 1.0, 0.0))
        verts.append((float(i), 1.0, 1.0))
        verts.append((float(i), 0.0, 1.0))

    faces = []
    for i in range(face_count):
        base = i * 4
        faces.append((base, base + 1, base + 2, base + 3))

    return {
        "vertices": verts,
        "faces": faces,
        "uvs": [],
        "metadata": {
            "name": name,
            "poly_count": len(faces),
            "vertex_count": len(verts),
            "dimensions": {"width": 1.0, "height": 1.0, "depth": 1.0},
        },
    }


class TestGenerateLodSpecs:
    """Tests for generate_lod_specs pure-logic LOD generation."""

    def test_returns_three_specs(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        assert len(lods) == 3, f"Expected 3 LOD specs, got {len(lods)}"

    def test_lod0_has_all_faces(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        assert len(lods[0]["faces"]) == 20

    def test_lod1_fewer_faces_than_lod0(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        assert len(lods[1]["faces"]) < len(lods[0]["faces"]), (
            "LOD1 should have fewer faces than LOD0"
        )

    def test_lod2_fewer_faces_than_lod1(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        assert len(lods[2]["faces"]) < len(lods[1]["faces"]), (
            "LOD2 should have fewer faces than LOD1"
        )

    def test_lod_name_suffixes(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        assert lods[0]["metadata"]["name"] == "Barrel_LOD0"
        assert lods[1]["metadata"]["name"] == "Barrel_LOD1"
        assert lods[2]["metadata"]["name"] == "Barrel_LOD2"

    def test_lod_poly_count_matches_faces(self) -> None:
        spec = _make_test_spec(20, "Barrel")
        lods = generate_lod_specs(spec)
        for i, lod in enumerate(lods):
            assert lod["metadata"]["poly_count"] == len(lod["faces"]), (
                f"LOD{i} poly_count mismatch"
            )

    def test_custom_ratios(self) -> None:
        spec = _make_test_spec(100, "BigMesh")
        lods = generate_lod_specs(spec, ratios=[1.0, 0.3, 0.1])
        assert len(lods) == 3
        assert len(lods[1]["faces"]) <= 30
        assert len(lods[2]["faces"]) <= 10

    def test_compacts_vertices(self) -> None:
        spec = _make_test_spec(20, "Test")
        lods = generate_lod_specs(spec)
        # LOD0 keeps all faces, so vertices are only those referenced by faces
        orig_referenced = set(idx for face in spec["faces"] for idx in face)
        assert len(lods[0]["vertices"]) == len(orig_referenced)
        # Lower LODs have fewer faces, so should have fewer (or equal) vertices
        assert len(lods[1]["vertices"]) <= len(lods[0]["vertices"])
        assert len(lods[2]["vertices"]) <= len(lods[1]["vertices"])
        # All LOD face indices must be valid (within vertex range)
        for lod in lods:
            vert_count = len(lod["vertices"])
            for face in lod["faces"]:
                for idx in face:
                    assert 0 <= idx < vert_count

    def test_handles_empty_uvs(self) -> None:
        spec = _make_test_spec(20, "NoUV")
        spec["uvs"] = []
        lods = generate_lod_specs(spec)
        assert len(lods) == 3
        for lod in lods:
            assert lod["uvs"] == []

    def test_single_face_spec(self) -> None:
        """Even a single-face spec should produce 3 LODs without crashing."""
        spec = _make_test_spec(1, "Tiny")
        lods = generate_lod_specs(spec)
        assert len(lods) == 3
        # LOD0 has the single face; LOD1/LOD2 may have 0 or 1
        assert len(lods[0]["faces"]) == 1


# ---------------------------------------------------------------------------
# resolve_generator tests
# ---------------------------------------------------------------------------


class TestResolveGenerator:
    """Tests for resolve_generator lookup helper."""

    def test_furniture_lookup(self) -> None:
        result = resolve_generator("furniture", "table")
        assert result is not None
        gen_func, kwargs = result
        assert callable(gen_func)

    def test_vegetation_lookup(self) -> None:
        result = resolve_generator("vegetation", "tree")
        assert result is not None

    def test_dungeon_prop_lookup(self) -> None:
        result = resolve_generator("dungeon_prop", "torch_sconce")
        assert result is not None

    def test_castle_lookup(self) -> None:
        result = resolve_generator("castle", "gate")
        assert result is not None

    def test_unknown_map_returns_none(self) -> None:
        result = resolve_generator("nonexistent_map", "table")
        assert result is None

    def test_unknown_item_returns_none(self) -> None:
        result = resolve_generator("furniture", "nonexistent_item_xyz")
        assert result is None


# ---------------------------------------------------------------------------
# mesh_from_spec (pure-logic validation only -- bpy not available)
# ---------------------------------------------------------------------------


class TestMeshFromSpecPureLogic:
    """Test the pure-logic aspects of mesh_from_spec without bpy.

    We can only test that the function exists and handles input validation.
    Actual Blender object creation requires bpy which is mocked as a stub.
    """

    def test_mesh_from_spec_exists(self) -> None:
        from blender_addon.handlers._mesh_bridge import mesh_from_spec
        assert callable(mesh_from_spec)

    def test_mesh_from_spec_name_from_metadata(self) -> None:
        """When no name override is given, name should come from spec metadata."""
        spec = _make_test_spec(4, "MyObj")
        # Since bpy is a stub module, mesh_from_spec will return a dict fallback
        from blender_addon.handlers._mesh_bridge import mesh_from_spec
        result = mesh_from_spec(spec)
        # The function should use the name from metadata when no override given
        if isinstance(result, dict):
            assert result.get("obj_name") == "MyObj"

    def test_mesh_from_spec_name_override(self) -> None:
        """Name override should take precedence over metadata name."""
        spec = _make_test_spec(4, "Original")
        from blender_addon.handlers._mesh_bridge import mesh_from_spec
        result = mesh_from_spec(spec, name="Override")
        if isinstance(result, dict):
            assert result.get("obj_name") == "Override"

    def test_mesh_from_spec_empty_uvs(self) -> None:
        """Calling with empty UVs should not crash."""
        spec = _make_test_spec(4, "NoUV")
        spec["uvs"] = []
        from blender_addon.handlers._mesh_bridge import mesh_from_spec
        result = mesh_from_spec(spec)
        # Should complete without error
        assert result is not None


# ---------------------------------------------------------------------------
# CATEGORY_MATERIAL_MAP tests -- procedural material auto-assignment
# ---------------------------------------------------------------------------

# All generator categories found in procedural_meshes.py
ALL_GENERATOR_CATEGORIES = [
    "furniture", "vegetation", "dungeon_prop", "weapon", "armor",
    "architecture", "building", "container", "dark_fantasy",
    "monster_part", "monster_body", "projectile", "trap",
    "light_source", "wall_decor", "crafting", "vehicle",
    "structural", "fortification", "sign", "natural",
    "fence_barrier", "door", "camp", "infrastructure",
    "consumable", "crafting_material", "currency", "key_item",
    "combat_item", "forest_animal", "mountain_animal",
    "domestic_animal", "vermin", "swamp_animal",
]


class TestCategoryMaterialMap:
    """Tests for CATEGORY_MATERIAL_MAP coverage and validity."""

    @pytest.mark.parametrize("category", ALL_GENERATOR_CATEGORIES)
    def test_every_generator_category_has_material(self, category: str) -> None:
        """Every generator category must map to a procedural material."""
        assert category in CATEGORY_MATERIAL_MAP, (
            f"CATEGORY_MATERIAL_MAP missing category '{category}'"
        )

    @pytest.mark.parametrize("category", ALL_GENERATOR_CATEGORIES)
    def test_material_key_exists_in_library(self, category: str) -> None:
        """Every mapped material key must exist in MATERIAL_LIBRARY."""
        from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
        material_key = CATEGORY_MATERIAL_MAP[category]
        assert material_key in MATERIAL_LIBRARY, (
            f"Category '{category}' maps to '{material_key}' "
            f"which is not in MATERIAL_LIBRARY"
        )

    def test_total_mappings_at_least_21(self) -> None:
        """Must cover at least 21 generator categories."""
        assert len(CATEGORY_MATERIAL_MAP) >= 21, (
            f"Expected >= 21 category mappings, got {len(CATEGORY_MATERIAL_MAP)}"
        )

    def test_get_material_for_category_returns_key(self) -> None:
        result = get_material_for_category("furniture")
        assert result == "rough_timber"

    def test_get_material_for_category_returns_none_for_unknown(self) -> None:
        result = get_material_for_category("nonexistent_category_xyz")
        assert result is None

    def test_furniture_maps_to_wood_material(self) -> None:
        key = CATEGORY_MATERIAL_MAP["furniture"]
        assert "timber" in key or "wood" in key, (
            f"Furniture should map to a wood material, got '{key}'"
        )

    def test_weapon_maps_to_metal_material(self) -> None:
        key = CATEGORY_MATERIAL_MAP["weapon"]
        assert "iron" in key or "steel" in key or "metal" in key, (
            f"Weapons should map to a metal material, got '{key}'"
        )

    def test_architecture_maps_to_stone_material(self) -> None:
        key = CATEGORY_MATERIAL_MAP["architecture"]
        assert "stone" in key, (
            f"Architecture should map to a stone material, got '{key}'"
        )


# ---------------------------------------------------------------------------
# Post-boolean cleanup tests
# ---------------------------------------------------------------------------


def _make_simple_cube():
    """Create a simple cube for cleanup testing."""
    verts = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (2, 3, 7, 6),
        (0, 4, 7, 3), (1, 2, 6, 5),
    ]
    return verts, faces


class TestPostBooleanCleanup:
    """Tests for post_boolean_cleanup pure-logic mesh cleanup."""

    def test_clean_mesh_unchanged(self) -> None:
        """A clean cube should pass through with no changes."""
        verts, faces = _make_simple_cube()
        result = post_boolean_cleanup(verts, faces)
        assert result["report"]["doubles_removed"] == 0
        assert len(result["vertices"]) == 8
        assert len(result["faces"]) == 6

    def test_removes_duplicate_vertices(self) -> None:
        """Vertices at the same location should be merged."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.00005, 0.00005, 0.00005),  # Near-duplicate of vertex 0
        ]
        faces = [
            (0, 1, 2, 3),
            (4, 1, 2),  # Uses near-duplicate
        ]
        result = post_boolean_cleanup(verts, faces, merge_distance=0.0001)
        assert result["report"]["doubles_removed"] >= 1

    def test_empty_mesh_returns_empty(self) -> None:
        result = post_boolean_cleanup([], [])
        assert result["vertices"] == []
        assert result["faces"] == []
        assert result["report"]["doubles_removed"] == 0

    def test_report_has_all_keys(self) -> None:
        verts, faces = _make_simple_cube()
        result = post_boolean_cleanup(verts, faces)
        report = result["report"]
        assert "doubles_removed" in report
        assert "normals_fixed" in report
        assert "holes_filled" in report
        assert "non_manifold_edges" in report

    def test_degenerate_faces_removed(self) -> None:
        """Faces that collapse to < 3 verts after merge should be removed."""
        verts = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.00005, 0.00005, 0.00005),  # Duplicate of 0
        ]
        faces = [(0, 1, 2)]  # After merge, becomes (0, 1, 0) -> degenerate
        result = post_boolean_cleanup(verts, faces, merge_distance=0.0001)
        # The degenerate face should be removed
        assert len(result["faces"]) == 0

    def test_face_indices_valid_after_cleanup(self) -> None:
        """All face indices must be valid after vertex compaction."""
        verts, faces = _make_simple_cube()
        # Add some duplicate verts
        verts_with_dupes = list(verts) + [
            (0.500005, 0.500005, 0.500005),  # Near-dupe of vertex 6
        ]
        faces_extended = list(faces) + [(8, 5, 4)]
        result = post_boolean_cleanup(verts_with_dupes, faces_extended, merge_distance=0.0001)
        n_verts = len(result["vertices"])
        for fi, face in enumerate(result["faces"]):
            for idx in face:
                assert 0 <= idx < n_verts, (
                    f"Face {fi} has index {idx} >= {n_verts}"
                )

    def test_manifold_cube_has_zero_non_manifold_edges(self) -> None:
        verts, faces = _make_simple_cube()
        result = post_boolean_cleanup(verts, faces)
        assert result["report"]["non_manifold_edges"] == 0
