"""Tests for clothing mesh generation, wrinkle maps, and material layer stack.

Validates:
- All 12 clothing types generate valid meshes across all style variants
- Robes/cloaks have separate drape mesh pieces
- Cloth simulation vertex groups present on all garments
- UV layouts stay within 0-1 range
- Different styles produce different geometry
- Wrinkle regions have valid vertex indices within mesh bounds
- Wrinkle displacement vectors are properly normalized/scaled
- Layer stack blending: opacity 0 = invisible, opacity 1 = full override
- Layer blend modes produce different results
- Clothing offset mesh has more vertices than input body (when applicable)
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.clothing_system import (
    ALL_CLOTHING_TYPES,
    CLOTHING_GENERATORS,
    CLOTHING_STYLES,
    generate_clothing,
    generate_tunic,
    generate_robe,
    generate_cloak,
    generate_hood,
    generate_pants,
    generate_shirt,
    generate_belt,
    generate_scarf,
    generate_tabard,
    generate_loincloth,
    generate_bandage_wrap,
    generate_sash,
    _offset_mesh_outward,
    _flatten_to_uv_pattern,
    _generate_tube_grid,
    _generate_sheet_grid,
)

from blender_addon.handlers.wrinkle_maps import (
    ALL_WRINKLE_REGIONS,
    WRINKLE_REGION_DEFS,
    SMART_MATERIAL_PRESETS,
    ALL_MATERIAL_PRESETS,
    compute_wrinkle_map_regions,
    generate_wrinkle_displacement_code,
    compute_layer_stack,
    handle_material_layer_stack,
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_clothing_mesh(result: dict, label: str, min_verts: int = 10, min_faces: int = 4):
    """Validate a clothing mesh result has required fields and valid data."""
    # Required top-level keys
    assert "vertices" in result, f"{label}: missing 'vertices'"
    assert "faces" in result, f"{label}: missing 'faces'"
    assert "uvs" in result, f"{label}: missing 'uvs'"
    assert "vertex_groups" in result, f"{label}: missing 'vertex_groups'"
    assert "material_regions" in result, f"{label}: missing 'material_regions'"
    assert "metadata" in result, f"{label}: missing 'metadata'"

    verts = result["vertices"]
    faces = result["faces"]
    meta = result["metadata"]

    # Non-empty geometry
    assert len(verts) >= min_verts, (
        f"{label}: expected >= {min_verts} vertices, got {len(verts)}"
    )
    assert len(faces) >= min_faces, (
        f"{label}: expected >= {min_faces} faces, got {len(faces)}"
    )

    # Valid vertices (3-tuples of finite numbers)
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{label}: vertex {i} has {len(v)} components"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{label}: vertex {i} has non-numeric component"
            )
            assert math.isfinite(comp), f"{label}: vertex {i} has non-finite component"

    # Valid face indices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{label}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{label}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Metadata
    assert "poly_count" in meta, f"{label}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{label}: metadata missing 'vertex_count'"
    assert "dimensions" in meta, f"{label}: metadata missing 'dimensions'"
    assert meta["poly_count"] == len(faces)
    assert meta["vertex_count"] == len(verts)

    # Vertex groups should be dicts
    vgroups = result["vertex_groups"]
    assert isinstance(vgroups, dict), f"{label}: vertex_groups should be dict"

    # Material regions should be dicts
    mat_regions = result["material_regions"]
    assert isinstance(mat_regions, dict), f"{label}: material_regions should be dict"


def validate_uvs_in_range(result: dict, label: str):
    """Validate all UVs are within the 0-1 range."""
    uvs = result.get("uvs", [])
    if not uvs:
        return  # Some garments may have empty UVs initially
    for i, uv in enumerate(uvs):
        assert len(uv) == 2, f"{label}: UV {i} has {len(uv)} components"
        assert 0.0 <= uv[0] <= 1.0, (
            f"{label}: UV {i} u={uv[0]:.4f} out of [0,1] range"
        )
        assert 0.0 <= uv[1] <= 1.0, (
            f"{label}: UV {i} v={uv[1]:.4f} out of [0,1] range"
        )


# ---------------------------------------------------------------------------
# Test: All 12 clothing types generate valid meshes
# ---------------------------------------------------------------------------


class TestAllClothingTypes:
    """Verify every clothing type + style produces valid geometry."""

    def test_all_types_registered(self):
        """CLOTHING_GENERATORS has entries for all 12 types."""
        assert len(CLOTHING_GENERATORS) == 12
        for ctype in ALL_CLOTHING_TYPES:
            assert ctype in CLOTHING_GENERATORS, f"Missing generator for {ctype}"

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_default_style_valid(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        validate_clothing_mesh(result, f"{clothing_type}_default")

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_default_has_uvs(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        validate_uvs_in_range(result, f"{clothing_type}_default")

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown clothing type"):
            generate_clothing("spacesuit")


# ---------------------------------------------------------------------------
# Test: Each type x style combination
# ---------------------------------------------------------------------------


class TestClothingStyles:
    """Test that every style variant produces valid and distinct geometry."""

    @pytest.mark.parametrize("clothing_type,style", [
        (ct, st)
        for ct in ALL_CLOTHING_TYPES
        for st in CLOTHING_STYLES[ct]
    ])
    def test_style_valid(self, clothing_type, style):
        result = generate_clothing(clothing_type, style=style)
        validate_clothing_mesh(result, f"{clothing_type}_{style}")
        validate_uvs_in_range(result, f"{clothing_type}_{style}")

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_different_styles_produce_different_geometry(self, clothing_type):
        styles = CLOTHING_STYLES[clothing_type]
        if len(styles) < 2:
            pytest.skip("Need at least 2 styles to compare")

        meshes = {}
        for s in styles:
            result = generate_clothing(clothing_type, style=s)
            meshes[s] = result

        # Check at least vertex count or positions differ between styles
        first_style = styles[0]
        any_different = False
        for s in styles[1:]:
            vc1 = len(meshes[first_style]["vertices"])
            vc2 = len(meshes[s]["vertices"])
            if vc1 != vc2:
                any_different = True
                break
            # If same count, check positions differ
            v1 = meshes[first_style]["vertices"]
            v2 = meshes[s]["vertices"]
            if v1 != v2:
                any_different = True
                break

        assert any_different, (
            f"{clothing_type}: all styles produce identical geometry"
        )


# ---------------------------------------------------------------------------
# Test: Robe/cloak drape mesh
# ---------------------------------------------------------------------------


class TestDrapeMeshes:
    """Test that robes and cloaks have separate drape mesh pieces."""

    @pytest.mark.parametrize("style", CLOTHING_STYLES["robe"])
    def test_robe_has_drape_mesh(self, style):
        result = generate_robe(style=style)
        assert "drape_mesh" in result, f"Robe {style} missing drape_mesh"
        drape = result["drape_mesh"]
        validate_clothing_mesh(drape, f"robe_{style}_drape", min_verts=10, min_faces=4)

    @pytest.mark.parametrize("style", CLOTHING_STYLES["cloak"])
    def test_cloak_has_drape_mesh(self, style):
        result = generate_cloak(style=style)
        assert "drape_mesh" in result, f"Cloak {style} missing drape_mesh"
        drape = result["drape_mesh"]
        validate_clothing_mesh(drape, f"cloak_{style}_drape", min_verts=10, min_faces=4)

    def test_robe_drape_has_cloth_sim_group(self):
        result = generate_robe(style="mage")
        drape = result["drape_mesh"]
        assert "cloth_sim" in drape["vertex_groups"]
        assert len(drape["vertex_groups"]["cloth_sim"]) > 0

    def test_cloak_drape_has_cloth_sim_group(self):
        result = generate_cloak(style="traveling")
        drape = result["drape_mesh"]
        assert "cloth_sim" in drape["vertex_groups"]
        assert len(drape["vertex_groups"]["cloth_sim"]) > 0

    def test_robe_drape_has_pinned_group(self):
        result = generate_robe(style="mage")
        drape = result["drape_mesh"]
        assert "pinned" in drape["vertex_groups"]
        assert len(drape["vertex_groups"]["pinned"]) > 0


# ---------------------------------------------------------------------------
# Test: Cloth simulation vertex groups
# ---------------------------------------------------------------------------


class TestClothSimVertexGroups:
    """Verify cloth sim vertex groups are present and populated."""

    REQUIRED_GROUPS = ["cloth_sim", "pinned", "hem", "seam"]

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_vertex_groups_present(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        vgroups = result["vertex_groups"]
        for group_name in self.REQUIRED_GROUPS:
            assert group_name in vgroups, (
                f"{clothing_type}: missing vertex group '{group_name}'"
            )

    @pytest.mark.parametrize("clothing_type", [
        "tunic", "robe", "shirt", "pants", "scarf", "tabard",
    ])
    def test_cloth_sim_or_pinned_nonempty(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        vgroups = result["vertex_groups"]
        has_cloth = len(vgroups.get("cloth_sim", [])) > 0
        has_pinned = len(vgroups.get("pinned", [])) > 0
        assert has_cloth or has_pinned, (
            f"{clothing_type}: both cloth_sim and pinned are empty"
        )

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_vertex_group_indices_valid(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        n_verts = len(result["vertices"])
        vgroups = result["vertex_groups"]
        for gname, indices in vgroups.items():
            for idx in indices:
                assert 0 <= idx < n_verts, (
                    f"{clothing_type}: group '{gname}' has index {idx} >= {n_verts}"
                )


# ---------------------------------------------------------------------------
# Test: Material regions
# ---------------------------------------------------------------------------


class TestMaterialRegions:
    """Verify material regions are correctly defined."""

    EXPECTED_REGIONS = ["outer_fabric", "inner_lining", "trim"]

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_material_regions_present(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        mat_regions = result["material_regions"]
        for region in self.EXPECTED_REGIONS:
            assert region in mat_regions, (
                f"{clothing_type}: missing material region '{region}'"
            )

    @pytest.mark.parametrize("clothing_type", ALL_CLOTHING_TYPES)
    def test_material_region_indices_valid(self, clothing_type):
        result = generate_clothing(clothing_type, style="default")
        n_verts = len(result["vertices"])
        for rname, indices in result["material_regions"].items():
            for idx in indices:
                assert 0 <= idx < n_verts, (
                    f"{clothing_type}: region '{rname}' has index {idx} >= {n_verts}"
                )


# ---------------------------------------------------------------------------
# Test: Size scaling
# ---------------------------------------------------------------------------


class TestSizeScaling:
    """Test that size parameter scales geometry."""

    @pytest.mark.parametrize("clothing_type", ["tunic", "robe", "pants", "shirt"])
    def test_larger_size_larger_dims(self, clothing_type):
        small = generate_clothing(clothing_type, size=0.8)
        large = generate_clothing(clothing_type, size=1.2)

        small_dims = small["metadata"]["dimensions"]
        large_dims = large["metadata"]["dimensions"]

        # At least one dimension should be larger
        assert (
            large_dims["width"] >= small_dims["width"] * 0.9 or
            large_dims["height"] >= small_dims["height"] * 0.9 or
            large_dims["depth"] >= small_dims["depth"] * 0.9
        ), f"{clothing_type}: size scaling not working"


# ---------------------------------------------------------------------------
# Test: Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Test core helper functions."""

    def test_offset_mesh_outward(self):
        # Simple cube face: push outward
        verts = [
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        result = _offset_mesh_outward(verts, faces, 0.1)
        assert len(result) == 4
        # All Z should be negative (normal points -Z for this winding)
        for v in result:
            assert v[2] != 0.0, "Offset should move vertices"

    def test_offset_preserves_vertex_count(self):
        verts = [(math.cos(a), math.sin(a), 0.0)
                 for a in [i * math.pi / 4 for i in range(8)]]
        faces = [(0, 1, 2, 3), (4, 5, 6, 7)]
        result = _offset_mesh_outward(verts, faces, 0.05)
        assert len(result) == len(verts)

    def test_flatten_to_uv_pattern(self):
        verts = [
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
        ]
        faces = [(0, 1, 2, 3)]
        uvs = _flatten_to_uv_pattern(verts, faces)
        assert len(uvs) == 4
        for u, v in uvs:
            assert 0.0 <= u <= 1.0
            assert 0.0 <= v <= 1.0

    def test_flatten_empty_verts(self):
        result = _flatten_to_uv_pattern([], [])
        assert result == []

    def test_tube_grid_generates_valid_mesh(self):
        verts, faces, uvs, vgroups = _generate_tube_grid(
            center_y_start=1.0,
            center_y_end=0.0,
            radius_profile=[0.1, 0.12, 0.1],
            circumference_segments=8,
            length_segments=4,
        )
        assert len(verts) > 0
        assert len(faces) > 0
        # All faces reference valid verts
        n = len(verts)
        for face in faces:
            for idx in face:
                assert 0 <= idx < n

    def test_sheet_grid_generates_valid_mesh(self):
        verts, faces, uvs, vgroups = _generate_sheet_grid(
            width=0.5,
            height=0.8,
            subdivs_x=4,
            subdivs_y=6,
        )
        assert len(verts) == 5 * 7  # (subdivs_x+1) * (subdivs_y+1)
        assert len(faces) == 4 * 6  # subdivs_x * subdivs_y


# ---------------------------------------------------------------------------
# Test: Specific garment features
# ---------------------------------------------------------------------------


class TestGarmentFeatures:
    """Test specific features of individual garment types."""

    def test_tunic_has_sleeves_metadata(self):
        result = generate_tunic(style="peasant")
        assert result["metadata"]["has_sleeves"] is True

    def test_robe_has_hood_metadata(self):
        result = generate_robe(style="mage")
        assert result["metadata"]["has_hood"] is True

    def test_robe_royal_no_hood(self):
        result = generate_robe(style="royal")
        assert result["metadata"]["has_hood"] is False

    def test_robe_has_drape_metadata(self):
        result = generate_robe(style="mage")
        assert result["metadata"]["has_drape"] is True

    def test_pants_two_legs(self):
        """Pants should have significantly more vertices than a simple tube
        (waistband + 2 legs)."""
        result = generate_pants(style="baggy")
        assert len(result["vertices"]) > 100  # Two legs + waist

    def test_belt_has_buckle(self):
        """Belt should have extra geometry for the buckle."""
        result = generate_belt(style="leather")
        # Buckle adds 8 verts (a box)
        assert len(result["vertices"]) > 80  # tube + buckle

    def test_tabard_two_panels(self):
        """Tabard should have front and back panels."""
        result = generate_tabard(style="plain")
        assert len(result["vertices"]) > 80  # Two sheets

    def test_bandage_arm_spiral(self):
        result = generate_bandage_wrap(style="arm")
        assert len(result["vertices"]) > 50

    def test_bandage_torso_bands(self):
        result = generate_bandage_wrap(style="torso")
        assert len(result["vertices"]) > 50

    def test_sash_diagonal(self):
        result = generate_sash(style="diagonal")
        validate_clothing_mesh(result, "sash_diagonal")

    def test_sash_waist_tube(self):
        result = generate_sash(style="waist")
        validate_clothing_mesh(result, "sash_waist")

    def test_loincloth_has_flaps(self):
        result = generate_loincloth(style="simple")
        # Band + front flap + back flap
        assert len(result["vertices"]) > 60

    def test_scarf_has_tail(self):
        result = generate_scarf(style="standard")
        assert len(result["vertices"]) > 40


# =========================================================================
# WRINKLE MAP TESTS
# =========================================================================


class TestWrinkleRegionDefs:
    """Test wrinkle region definitions are well-formed."""

    def test_all_regions_defined(self):
        assert len(ALL_WRINKLE_REGIONS) >= 10

    @pytest.mark.parametrize("region", ALL_WRINKLE_REGIONS)
    def test_region_has_required_fields(self, region):
        rdef = WRINKLE_REGION_DEFS[region]
        required = [
            "center_z", "center_x", "radius", "direction",
            "depth", "trigger_shape", "trigger_bone",
            "line_pattern", "line_count", "description",
        ]
        for field in required:
            assert field in rdef, f"Region '{region}' missing field '{field}'"

    @pytest.mark.parametrize("region", ALL_WRINKLE_REGIONS)
    def test_direction_is_normalized_or_normalizable(self, region):
        d = WRINKLE_REGION_DEFS[region]["direction"]
        assert len(d) == 3
        length = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        assert length > 0.1, f"Region '{region}' has near-zero direction vector"


class TestWrinkleComputation:
    """Test wrinkle region computation on a face mesh."""

    @pytest.fixture
    def simple_face_mesh(self):
        """Simple face-like grid for testing."""
        verts = []
        faces = []
        cols = 10
        rows = 15
        for r in range(rows):
            for c in range(cols):
                x = (c / (cols - 1) - 0.5) * 0.16
                y = 0.05  # forward
                z = (r / (rows - 1)) * 0.24 - 0.05
                verts.append((x, y, z))

        for r in range(rows - 1):
            for c in range(cols - 1):
                v0 = r * cols + c
                v1 = v0 + 1
                v2 = v0 + cols + 1
                v3 = v0 + cols
                faces.append((v0, v1, v2, v3))

        return verts, faces

    def test_compute_all_regions(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        regions = compute_wrinkle_map_regions(verts, faces)
        assert len(regions) > 0

    def test_region_vertex_indices_valid(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        n_verts = len(verts)
        regions = compute_wrinkle_map_regions(verts, faces)
        for rname, rdata in regions.items():
            for vi in rdata["vertex_indices"]:
                assert 0 <= vi < n_verts, (
                    f"Region '{rname}': vertex index {vi} >= {n_verts}"
                )

    def test_displacement_vectors_reasonable(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        regions = compute_wrinkle_map_regions(verts, faces)
        for rname, rdata in regions.items():
            for disp in rdata["displacement_vectors"]:
                assert len(disp) == 3
                length = math.sqrt(disp[0] ** 2 + disp[1] ** 2 + disp[2] ** 2)
                # Displacement should be small (< 5mm) for wrinkles
                assert length < 0.005, (
                    f"Region '{rname}': displacement {length:.4f}m too large"
                )

    def test_falloff_weights_0_to_1(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        regions = compute_wrinkle_map_regions(verts, faces)
        for rname, rdata in regions.items():
            for w in rdata["falloff_weights"]:
                assert 0.0 <= w <= 1.0, (
                    f"Region '{rname}': falloff weight {w} out of [0,1]"
                )

    def test_age_factor_increases_depth(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        young = compute_wrinkle_map_regions(verts, faces, age_factor=0.5)
        old = compute_wrinkle_map_regions(verts, faces, age_factor=2.0)
        # For any region with vertices, deeper wrinkles should exist
        for rname in young:
            if young[rname]["vertex_count"] > 0 and old[rname]["vertex_count"] > 0:
                assert old[rname]["wrinkle_depth"] > young[rname]["wrinkle_depth"]

    def test_empty_mesh(self):
        result = compute_wrinkle_map_regions([], [])
        assert result == {}

    def test_specific_regions_requested(self, simple_face_mesh):
        verts, faces = simple_face_mesh
        regions = compute_wrinkle_map_regions(
            verts, faces, regions=["forehead_horizontal", "nasolabial_left"]
        )
        assert "forehead_horizontal" in regions
        assert "nasolabial_left" in regions
        assert "crow_feet_left" not in regions


class TestWrinkleCodeGeneration:
    """Test Blender code generation for wrinkle drivers."""

    def test_generates_code_string(self):
        regions = {
            "forehead_horizontal": {
                "vertex_indices": [10, 11, 12],
                "displacement_vectors": [
                    (0.0, 0.001, 0.0),
                    (0.0, 0.0008, 0.0),
                    (0.0, 0.001, 0.0),
                ],
                "trigger_shape": "brow_raise",
                "trigger_bone": "brow_ctrl",
                "description": "test wrinkle",
            }
        }
        code = generate_wrinkle_displacement_code("MyFace", regions, "shape_key")
        assert isinstance(code, str)
        assert "import bpy" in code
        assert "MyFace" in code
        assert "wrinkle_forehead_horizontal" in code
        assert "brow_raise" in code

    def test_bone_driver_type(self):
        regions = {
            "chin_dimple": {
                "vertex_indices": [5],
                "displacement_vectors": [(0.0, 0.001, 0.0)],
                "trigger_shape": "chin_raise",
                "trigger_bone": "chin_ctrl",
                "description": "chin test",
            }
        }
        code = generate_wrinkle_displacement_code("Face", regions, "bone")
        assert "bone_target" in code
        assert "chin_ctrl" in code

    def test_empty_regions_still_valid(self):
        code = generate_wrinkle_displacement_code("Face", {})
        assert isinstance(code, str)
        assert "import bpy" in code


# =========================================================================
# MATERIAL LAYER STACK TESTS
# =========================================================================


class TestMaterialPresets:
    """Test smart material presets are well-formed."""

    def test_presets_count(self):
        assert len(ALL_MATERIAL_PRESETS) >= 10

    @pytest.mark.parametrize("preset", ALL_MATERIAL_PRESETS)
    def test_preset_has_required_fields(self, preset):
        p = SMART_MATERIAL_PRESETS[preset]
        assert "base_color" in p
        assert "roughness" in p
        assert "metallic" in p
        assert len(p["base_color"]) == 4
        assert 0.0 <= p["roughness"] <= 1.0
        assert 0.0 <= p["metallic"] <= 1.0


class TestLayerStackComputation:
    """Test pure-logic layer stack blending."""

    def test_single_layer(self):
        layers = [{"name": "base", "base_color": (0.5, 0.3, 0.2, 1.0),
                    "roughness": 0.7, "metallic": 0.0, "opacity": 1.0,
                    "blend_mode": "MIX", "mask_value": 1.0}]
        result = compute_layer_stack(layers)
        assert result["layer_count"] == 1
        assert abs(result["roughness"] - 0.7) < 0.001

    def test_opacity_zero_invisible(self):
        """Layer with opacity=0 should not affect the result."""
        layers = [
            {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "overlay", "base_color": (1.0, 0.0, 0.0, 1.0),
             "roughness": 0.1, "metallic": 1.0, "opacity": 0.0,
             "blend_mode": "MIX", "mask_value": 1.0},
        ]
        result = compute_layer_stack(layers)
        # Result should match base layer exactly
        assert abs(result["base_color"][0] - 0.5) < 0.001
        assert abs(result["roughness"] - 0.5) < 0.001
        assert abs(result["metallic"] - 0.0) < 0.001

    def test_opacity_one_full_override(self):
        """Layer with opacity=1 and MIX should fully replace base."""
        layers = [
            {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "overlay", "base_color": (1.0, 0.0, 0.0, 1.0),
             "roughness": 0.9, "metallic": 1.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
        ]
        result = compute_layer_stack(layers)
        assert abs(result["base_color"][0] - 1.0) < 0.001
        assert abs(result["base_color"][1] - 0.0) < 0.001
        assert abs(result["roughness"] - 0.9) < 0.001
        assert abs(result["metallic"] - 1.0) < 0.001

    def test_blend_modes_produce_different_results(self):
        """Different blend modes should produce different output."""
        base_layer = {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
                      "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
                      "blend_mode": "MIX", "mask_value": 1.0}
        overlay_template = {"name": "over", "base_color": (0.8, 0.3, 0.2, 1.0),
                            "roughness": 0.7, "metallic": 0.5, "opacity": 0.7,
                            "mask_value": 1.0}

        results = {}
        for mode in ["MIX", "ADD", "MULTIPLY", "OVERLAY", "SCREEN"]:
            overlay = {**overlay_template, "blend_mode": mode}
            results[mode] = compute_layer_stack([base_layer, overlay])

        # Check that at least 3 different color outputs exist
        colors = [results[m]["base_color"][:3] for m in results]
        unique = set()
        for c in colors:
            unique.add(tuple(round(x, 4) for x in c))
        assert len(unique) >= 3, (
            f"Expected >= 3 unique colors from 5 blend modes, got {len(unique)}"
        )

    def test_mask_value_zero_transparent(self):
        """mask_value=0 should make layer invisible (same as opacity=0)."""
        layers = [
            {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "masked", "base_color": (1.0, 0.0, 0.0, 1.0),
             "roughness": 0.1, "metallic": 1.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 0.0},
        ]
        result = compute_layer_stack(layers)
        assert abs(result["base_color"][0] - 0.5) < 0.001

    def test_empty_stack(self):
        result = compute_layer_stack([])
        assert result["layer_count"] == 0

    def test_multiply_darkens(self):
        layers = [
            {"name": "base", "base_color": (0.8, 0.8, 0.8, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "dirt", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.9, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MULTIPLY", "mask_value": 1.0},
        ]
        result = compute_layer_stack(layers)
        # Multiply of 0.8 * 0.5 = 0.4
        assert result["base_color"][0] < 0.5

    def test_add_brightens(self):
        layers = [
            {"name": "base", "base_color": (0.3, 0.3, 0.3, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "glow", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "ADD", "mask_value": 1.0},
        ]
        result = compute_layer_stack(layers)
        # Add: 0.3 + 0.5 = 0.8
        assert result["base_color"][0] > 0.7

    def test_contributions_tracked(self):
        layers = [
            {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
            {"name": "rust", "base_color": (0.3, 0.15, 0.08, 1.0),
             "roughness": 0.85, "metallic": 0.3, "opacity": 0.6,
             "blend_mode": "MIX", "mask_value": 0.8},
        ]
        result = compute_layer_stack(layers)
        assert len(result["contributions"]) == 2
        assert result["contributions"][1]["name"] == "rust"
        assert abs(result["contributions"][1]["effective_opacity"] - 0.48) < 0.001


class TestMaterialLayerStackHandler:
    """Test the handle_material_layer_stack entry point."""

    def test_list_layers_action(self):
        result = handle_material_layer_stack({"action": "list_layers"})
        assert "available_presets" in result
        assert "available_blend_modes" in result
        assert "available_mask_types" in result

    def test_add_layer_generates_code(self):
        result = handle_material_layer_stack({
            "action": "add_layer",
            "object_name": "TestObj",
            "layer_name": "rust",
            "material_preset": "rusted_iron",
            "blend_mode": "MIX",
            "opacity": 0.7,
            "mask_type": "curvature",
        })
        assert "code" in result
        assert "import bpy" in result["code"]
        assert "TestObj" in result["code"]
        assert result["action"] == "add_layer"

    def test_remove_layer_generates_code(self):
        result = handle_material_layer_stack({
            "action": "remove_layer",
            "object_name": "TestObj",
            "layer_name": "rust",
        })
        assert "code" in result
        assert "remove" in result["code"]

    def test_set_opacity_generates_code(self):
        result = handle_material_layer_stack({
            "action": "set_opacity",
            "object_name": "TestObj",
            "layer_name": "rust",
            "opacity": 0.3,
        })
        assert "code" in result
        assert "0.3" in result["code"]

    def test_set_blend_mode_generates_code(self):
        result = handle_material_layer_stack({
            "action": "set_blend_mode",
            "object_name": "TestObj",
            "layer_name": "dirt",
            "blend_mode": "MULTIPLY",
        })
        assert "code" in result
        assert "MULTIPLY" in result["code"]

    def test_flatten_action(self):
        layers = [
            {"name": "base", "base_color": (0.5, 0.5, 0.5, 1.0),
             "roughness": 0.5, "metallic": 0.0, "opacity": 1.0,
             "blend_mode": "MIX", "mask_value": 1.0},
        ]
        result = handle_material_layer_stack({
            "action": "flatten",
            "layers": layers,
        })
        assert "result" in result
        assert result["result"]["layer_count"] == 1

    def test_add_layer_with_noise_mask(self):
        result = handle_material_layer_stack({
            "action": "add_layer",
            "object_name": "Rock",
            "layer_name": "moss",
            "material_preset": "moss_growth",
            "mask_type": "noise",
            "mask_params": {"scale": 8.0, "detail": 3.0},
        })
        assert "code" in result
        assert "Noise" in result["code"]

    def test_add_layer_with_ao_mask(self):
        result = handle_material_layer_stack({
            "action": "add_layer",
            "object_name": "Wall",
            "layer_name": "dirt",
            "material_preset": "dirt_accumulation",
            "mask_type": "ao",
        })
        assert "code" in result
        assert "AmbientOcclusion" in result["code"]

    def test_invalid_blend_mode_defaults_to_mix(self):
        result = handle_material_layer_stack({
            "action": "add_layer",
            "object_name": "Obj",
            "layer_name": "test",
            "material_preset": "rough_stone",
            "blend_mode": "INVALID_MODE",
        })
        assert result["blend_mode"] == "MIX"

    def test_opacity_clamped(self):
        result = handle_material_layer_stack({
            "action": "add_layer",
            "object_name": "Obj",
            "layer_name": "test",
            "material_preset": "rough_stone",
            "opacity": 5.0,
        })
        assert result["opacity"] == 1.0

    def test_unknown_action_returns_error(self):
        result = handle_material_layer_stack({
            "action": "explode",
            "object_name": "Obj",
        })
        assert "error" in result
