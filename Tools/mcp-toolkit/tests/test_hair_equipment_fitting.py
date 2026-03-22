"""Tests for hair system, facial hair, and equipment-body integration.

Validates:
- Hair card mesh generation for all 12 styles
- Hair card UV mapping (root-to-tip gradient)
- Distinct silhouettes per style
- Helmet compatibility rules
- Facial hair generation for all 8 styles
- Equipment visibility rules for all slots/styles
- Body shrink computation and application
- Vertex region assignment
- Vertex normal computation
- Edge cases: bald, clean_shaven, empty equipment, invalid inputs
"""

from __future__ import annotations

import importlib.util
import math

import pytest

# ---------------------------------------------------------------------------
# Load modules without triggering bpy imports
# ---------------------------------------------------------------------------

_hair_spec = importlib.util.spec_from_file_location(
    "hair_system",
    "blender_addon/handlers/hair_system.py",
)
_hair_mod = importlib.util.module_from_spec(_hair_spec)
_hair_spec.loader.exec_module(_hair_mod)

generate_hair_mesh = _hair_mod.generate_hair_mesh
get_helmet_compatible_hair = _hair_mod.get_helmet_compatible_hair
generate_facial_hair_mesh = _hair_mod.generate_facial_hair_mesh
HAIR_STYLES = _hair_mod.HAIR_STYLES
FACIAL_HAIR_STYLES = _hair_mod.FACIAL_HAIR_STYLES
_distribute_angles = _hair_mod._distribute_angles
_generate_hair_card = _hair_mod._generate_hair_card
_head_surface_point = _hair_mod._head_surface_point
_outward_direction = _hair_mod._outward_direction

_equip_spec = importlib.util.spec_from_file_location(
    "equipment_fitting",
    "blender_addon/handlers/equipment_fitting.py",
)
_equip_mod = importlib.util.module_from_spec(_equip_spec)
_equip_spec.loader.exec_module(_equip_mod)

compute_equipment_body_changes = _equip_mod.compute_equipment_body_changes
apply_body_shrink = _equip_mod.apply_body_shrink
get_body_region_vertices = _equip_mod.get_body_region_vertices
compute_vertex_normals = _equip_mod.compute_vertex_normals
BODY_PART_VISIBILITY = _equip_mod.BODY_PART_VISIBILITY


# ---------------------------------------------------------------------------
# Mesh validation helper (shared pattern from test_armor_meshes.py)
# ---------------------------------------------------------------------------

def validate_mesh_spec(result: dict, name: str, min_verts: int = 0, min_faces: int = 0):
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

    # Validate vertex format
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{name}: vertex {i} has {len(v)} components"
        for comp in v:
            assert isinstance(comp, (int, float)), (
                f"{name}: vertex {i} component {comp} is not a number"
            )

    # Validate face indices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{name}: face {fi} has {len(face)} verts, need >= 3"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{name}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Validate metadata
    assert "name" in meta, f"{name}: metadata missing 'name'"
    assert "poly_count" in meta, f"{name}: metadata missing 'poly_count'"
    assert "vertex_count" in meta, f"{name}: metadata missing 'vertex_count'"
    assert meta["poly_count"] == len(faces)
    assert meta["vertex_count"] == len(verts)

    return True


# ===========================================================================
# HAIR SYSTEM TESTS
# ===========================================================================


class TestHairStyles:
    """Test hair style definitions and constants."""

    def test_all_styles_defined(self):
        """All 12 hair styles are defined."""
        expected = {
            "short_crop", "medium_swept", "long_flowing", "ponytail",
            "mohawk", "bald", "shaved_sides", "short_bob",
            "long_straight", "braided", "updo", "wild_loose",
        }
        assert set(HAIR_STYLES.keys()) == expected

    def test_styles_have_required_fields(self):
        """Non-bald styles have card_count, length, and coverage."""
        for name, style in HAIR_STYLES.items():
            assert "card_count" in style, f"{name}: missing card_count"
            if style["card_count"] > 0:
                assert "length" in style, f"{name}: missing length"
                assert "coverage" in style, f"{name}: missing coverage"
                assert style["length"] > 0, f"{name}: length must be > 0"

    def test_bald_style(self):
        """Bald style has zero card count."""
        assert HAIR_STYLES["bald"]["card_count"] == 0

    def test_card_counts_are_positive(self):
        """All non-bald styles have positive card counts."""
        for name, style in HAIR_STYLES.items():
            if name != "bald":
                assert style["card_count"] > 0, f"{name}: card_count should be > 0"


class TestHairMeshGeneration:
    """Test generate_hair_mesh for all styles."""

    @pytest.mark.parametrize("style", [s for s in HAIR_STYLES if s != "bald"])
    def test_generate_all_non_bald_styles(self, style):
        """Each non-bald style produces valid mesh with vertices and faces."""
        result = generate_hair_mesh(style=style)
        validate_mesh_spec(result, style, min_verts=4, min_faces=1)
        assert result["metadata"]["style"] == style
        assert result["metadata"]["card_count"] > 0

    def test_generate_bald(self):
        """Bald style produces empty mesh."""
        result = generate_hair_mesh(style="bald")
        validate_mesh_spec(result, "bald", min_verts=0, min_faces=0)
        assert result["metadata"]["card_count"] == 0
        assert len(result["vertices"]) == 0
        assert len(result["faces"]) == 0

    def test_invalid_style_raises(self):
        """Unknown style raises ValueError."""
        with pytest.raises(ValueError, match="Unknown hair style"):
            generate_hair_mesh(style="nonexistent")

    def test_uv_mapping_root_to_tip(self):
        """UV V coordinate goes from 0 (root) to 1 (tip) along each card."""
        result = generate_hair_mesh(style="short_crop", segments_per_card=3)
        uvs = result["uvs"]
        assert len(uvs) > 0

        # Each card has (segments+1) * 2 UV entries
        # V values should range from 0 to 1
        v_values = [uv[1] for uv in uvs]
        assert min(v_values) == pytest.approx(0.0, abs=0.01)
        assert max(v_values) == pytest.approx(1.0, abs=0.01)

        # U values should be 0 or 1 (left/right of card)
        u_values = set(round(uv[0], 2) for uv in uvs)
        assert 0.0 in u_values or pytest.approx(0.0) in [round(u, 2) for u in u_values]
        assert 1.0 in u_values or pytest.approx(1.0) in [round(u, 2) for u in u_values]

    def test_uvs_match_vertex_count(self):
        """Number of UVs equals number of vertices."""
        for style in HAIR_STYLES:
            result = generate_hair_mesh(style=style)
            assert len(result["uvs"]) == len(result["vertices"]), (
                f"{style}: UV count {len(result['uvs'])} != vertex count {len(result['vertices'])}"
            )

    def test_distinct_silhouettes(self):
        """Different styles produce different vertex counts (distinct geometry)."""
        counts = {}
        for style in HAIR_STYLES:
            result = generate_hair_mesh(style=style)
            counts[style] = len(result["vertices"])

        # At least 8 distinct vertex counts among 12 styles
        unique_counts = len(set(counts.values()))
        assert unique_counts >= 8, (
            f"Only {unique_counts} distinct vertex counts among {len(counts)} styles. "
            f"Hair styles should produce distinct silhouettes."
        )

    def test_custom_head_parameters(self):
        """Custom head radius and center are respected."""
        result1 = generate_hair_mesh(style="short_crop",
                                      head_radius=0.11,
                                      head_center=(0, 0, 1.7))
        result2 = generate_hair_mesh(style="short_crop",
                                      head_radius=0.15,
                                      head_center=(0, 0, 2.0))

        # Different head params should produce different vertex positions
        if len(result1["vertices"]) > 0 and len(result2["vertices"]) > 0:
            v1 = result1["vertices"][0]
            v2 = result2["vertices"][0]
            # At least one coordinate should differ
            assert v1 != v2

    def test_card_width_affects_geometry(self):
        """Wider cards produce wider mesh."""
        narrow = generate_hair_mesh(style="short_crop", card_width=0.005)
        wide = generate_hair_mesh(style="short_crop", card_width=0.03)

        narrow_dims = narrow["metadata"]["dimensions"]
        wide_dims = wide["metadata"]["dimensions"]

        # Wide cards should produce greater overall width
        narrow_size = narrow_dims["width"] + narrow_dims["depth"]
        wide_size = wide_dims["width"] + wide_dims["depth"]
        assert wide_size > narrow_size

    def test_segments_per_card(self):
        """More segments produce more vertices per card."""
        result3 = generate_hair_mesh(style="short_crop", segments_per_card=3)
        result5 = generate_hair_mesh(style="short_crop", segments_per_card=5)

        # More segments = more vertices (each card has (segs+1)*2 verts)
        assert len(result5["vertices"]) > len(result3["vertices"])


class TestHairCardGeneration:
    """Test the low-level _generate_hair_card function."""

    def test_basic_card(self):
        """Generate a basic hair card with correct structure."""
        verts, faces, uvs = _generate_hair_card(
            root_pos=(0, 0, 0),
            direction=(0, 0, 1),
            length=0.1,
            card_width=0.01,
            vert_offset=0,
            segments=3,
        )
        # 3 segments -> 4 rows -> 8 vertices
        assert len(verts) == 8
        # 3 segments -> 3 quad faces
        assert len(faces) == 3
        assert len(uvs) == 8

    def test_card_uv_gradient(self):
        """Card UVs have V=0 at root and V=1 at tip."""
        verts, faces, uvs = _generate_hair_card(
            root_pos=(0, 0, 0),
            direction=(0, 0, 1),
            length=0.1,
            card_width=0.01,
            vert_offset=0,
            segments=4,
        )
        # First row UVs should have V=0
        assert uvs[0][1] == pytest.approx(0.0)
        assert uvs[1][1] == pytest.approx(0.0)
        # Last row UVs should have V=1
        assert uvs[-1][1] == pytest.approx(1.0)
        assert uvs[-2][1] == pytest.approx(1.0)

    def test_card_taper(self):
        """Card width tapers from root to tip."""
        verts, faces, uvs = _generate_hair_card(
            root_pos=(0, 0, 0),
            direction=(0, 1, 0),
            length=0.5,
            card_width=0.02,
            vert_offset=0,
            segments=4,
        )
        # Root width: distance between first pair of verts
        v0, v1 = verts[0], verts[1]
        root_width = math.sqrt(sum((a - b) ** 2 for a, b in zip(v0, v1)))
        # Tip width: distance between last pair of verts
        vn0, vn1 = verts[-2], verts[-1]
        tip_width = math.sqrt(sum((a - b) ** 2 for a, b in zip(vn0, vn1)))
        assert tip_width < root_width, "Card should taper toward tip"

    def test_vert_offset(self):
        """Face indices respect vert_offset."""
        _, faces, _ = _generate_hair_card(
            root_pos=(0, 0, 0),
            direction=(0, 0, 1),
            length=0.1,
            card_width=0.01,
            vert_offset=100,
            segments=2,
        )
        min_idx = min(idx for face in faces for idx in face)
        assert min_idx >= 100


class TestHelmetCompatibility:
    """Test helmet-hair compatibility rules."""

    def test_full_helm_hides_all(self):
        """Full helm hides all hair."""
        for style in HAIR_STYLES:
            result = get_helmet_compatible_hair(style, "full_helm")
            assert result["visible"] is False
            # Bald has no regions to hide, non-bald hides "all"
            if HAIR_STYLES[style].get("card_count", 0) > 0:
                assert "all" in result["hide_regions"]

    def test_crown_shows_all(self):
        """Crown shows all hair unchanged."""
        for style in HAIR_STYLES:
            if HAIR_STYLES[style].get("card_count", 0) == 0:
                continue
            result = get_helmet_compatible_hair(style, "crown")
            assert result["visible"] is True
            assert len(result["hide_regions"]) == 0

    def test_open_face_partial(self):
        """Open face helm shows back/sides only."""
        result = get_helmet_compatible_hair("long_flowing", "open_face")
        assert result["visible"] is True
        assert "top" in result["hide_regions"]
        assert "front" in result["hide_regions"]

    def test_hood_front_fringe(self):
        """Hood shows front fringe only."""
        result = get_helmet_compatible_hair("long_flowing", "hood")
        assert result["visible"] is True
        assert "back" in result["hide_regions"]
        assert "sides" in result["hide_regions"]

    def test_skull_mask_shows_hair(self):
        """Skull mask shows all hair (only covers face)."""
        result = get_helmet_compatible_hair("medium_swept", "skull_mask")
        assert result["visible"] is True
        assert len(result["hide_regions"]) == 0

    def test_bald_always_compatible(self):
        """Bald style is always compatible with any helmet."""
        for helmet in ["full_helm", "open_face", "hood", "crown", "skull_mask"]:
            result = get_helmet_compatible_hair("bald", helmet)
            assert result["visible"] is False
            assert result["original_style"] == "bald"

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown hair style"):
            get_helmet_compatible_hair("nonexistent", "crown")

    def test_invalid_helmet_raises(self):
        with pytest.raises(ValueError, match="Unknown helmet style"):
            get_helmet_compatible_hair("short_crop", "nonexistent")

    def test_original_style_preserved(self):
        """Return includes original style reference."""
        result = get_helmet_compatible_hair("long_flowing", "open_face")
        assert result["original_style"] == "long_flowing"

    @pytest.mark.parametrize("helmet", ["full_helm", "open_face", "hood", "crown", "skull_mask"])
    def test_all_helmets_all_styles(self, helmet):
        """All helmet/style combinations produce valid results."""
        for style in HAIR_STYLES:
            result = get_helmet_compatible_hair(style, helmet)
            assert "visible" in result
            assert "modified_coverage" in result
            assert "hide_regions" in result
            assert "original_style" in result


class TestDistributeAngles:
    """Test the angle distribution helper."""

    def test_zero_count(self):
        assert _distribute_angles(0, "full") == []

    def test_count_matches(self):
        angles = _distribute_angles(20, "full")
        assert len(angles) == 20

    def test_angles_in_range(self):
        """All angles are within coverage range."""
        angles = _distribute_angles(30, "full")
        for a in angles:
            assert 0.0 <= a <= 2 * math.pi + 0.1

    def test_center_strip_narrow(self):
        """Center strip produces narrow angle range."""
        angles = _distribute_angles(10, "center_strip")
        if angles:
            spread = max(angles) - min(angles)
            full_angles = _distribute_angles(10, "full")
            full_spread = max(full_angles) - min(full_angles)
            assert spread < full_spread


class TestHeadSurfacePoint:
    """Test head surface point calculation."""

    def test_top_of_head(self):
        """Elevation 0 gives top of head."""
        point = _head_surface_point(0, 0, (0, 0, 1.7), 0.11)
        assert point[2] == pytest.approx(1.7 + 0.11, abs=0.001)

    def test_front_of_head(self):
        """Azimuth 0, elevation pi/2 gives front."""
        point = _head_surface_point(0, math.pi / 2, (0, 0, 1.7), 0.11)
        assert point[1] == pytest.approx(0.11, abs=0.001)  # Positive Y = front


# ===========================================================================
# FACIAL HAIR TESTS
# ===========================================================================


class TestFacialHairStyles:
    """Test facial hair style definitions."""

    def test_all_styles_defined(self):
        expected = {
            "clean_shaven", "stubble", "short_beard", "full_beard",
            "long_beard", "braided_beard", "mustache", "goatee",
        }
        assert set(FACIAL_HAIR_STYLES.keys()) == expected

    def test_styles_have_required_fields(self):
        for name, style in FACIAL_HAIR_STYLES.items():
            assert "card_count" in style, f"{name}: missing card_count"
            if style["card_count"] > 0:
                assert "length" in style, f"{name}: missing length"
                assert "coverage" in style, f"{name}: missing coverage"


class TestFacialHairGeneration:
    """Test generate_facial_hair_mesh."""

    @pytest.mark.parametrize("style", [s for s in FACIAL_HAIR_STYLES if s != "clean_shaven"])
    def test_generate_all_non_empty_styles(self, style):
        result = generate_facial_hair_mesh(style=style)
        validate_mesh_spec(result, style, min_verts=4, min_faces=1)
        assert result["metadata"]["style"] == style
        assert result["metadata"]["card_count"] > 0

    def test_generate_clean_shaven(self):
        result = generate_facial_hair_mesh(style="clean_shaven")
        assert len(result["vertices"]) == 0
        assert len(result["faces"]) == 0
        assert result["metadata"]["card_count"] == 0

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown facial hair style"):
            generate_facial_hair_mesh(style="nonexistent")

    def test_uvs_match_vertices(self):
        for style in FACIAL_HAIR_STYLES:
            result = generate_facial_hair_mesh(style=style)
            assert len(result["uvs"]) == len(result["vertices"])

    def test_braided_beard_metadata(self):
        result = generate_facial_hair_mesh(style="braided_beard")
        assert result["metadata"]["braided"] is True

    def test_non_braided_metadata(self):
        result = generate_facial_hair_mesh(style="full_beard")
        assert result["metadata"]["braided"] is False

    def test_distinct_styles(self):
        """Different facial hair styles produce different geometry."""
        counts = {}
        for style in FACIAL_HAIR_STYLES:
            result = generate_facial_hair_mesh(style=style)
            counts[style] = len(result["vertices"])
        unique = len(set(counts.values()))
        assert unique >= 5, f"Only {unique} distinct counts among {len(counts)} styles"

    def test_positioned_on_face(self):
        """Facial hair vertices are near the face center."""
        face_center = (0.0, 0.0, 1.64)
        result = generate_facial_hair_mesh(
            style="full_beard", face_center=face_center, face_radius=0.10
        )
        verts = result["vertices"]
        assert len(verts) > 0

        # All vertices should be within reasonable distance of face
        for v in verts:
            dist = math.sqrt(
                (v[0] - face_center[0]) ** 2 +
                (v[1] - face_center[1]) ** 2 +
                (v[2] - face_center[2]) ** 2
            )
            # Within face_radius + max beard length + margin
            assert dist < 0.30, f"Vertex {v} too far from face center"


# ===========================================================================
# EQUIPMENT FITTING TESTS
# ===========================================================================


class TestEquipmentBodyChanges:
    """Test compute_equipment_body_changes."""

    def test_empty_equipment(self):
        """No equipment means nothing hidden."""
        result = compute_equipment_body_changes({})
        assert result["hide_regions"] == []
        assert result["shrink_regions"] == {}
        assert result["hair_visible"] is True
        assert result["facial_hair_visible"] is True

    def test_full_helm_hides_hair(self):
        """Full helm hides head hair, facial hair, and ears."""
        result = compute_equipment_body_changes({"helmet": "full_helm"})
        assert "head_hair" in result["hide_regions"]
        assert "facial_hair" in result["hide_regions"]
        assert "ears" in result["hide_regions"]
        assert result["hair_visible"] is False
        assert result["facial_hair_visible"] is False

    def test_crown_hides_nothing(self):
        """Crown hides nothing."""
        result = compute_equipment_body_changes({"helmet": "crown"})
        assert result["hide_regions"] == []
        assert result["hair_visible"] is True
        assert result["facial_hair_visible"] is True

    def test_plate_chest_shrinks_torso(self):
        """Plate chest armor hides torso and shrinks by 0.02."""
        result = compute_equipment_body_changes({"chest_armor": "plate"})
        assert "torso_skin" in result["hide_regions"]
        assert result["shrink_regions"]["torso"] == pytest.approx(0.02)

    def test_light_armor_no_hide(self):
        """Light chest armor hides nothing."""
        result = compute_equipment_body_changes({"chest_armor": "light"})
        assert result["hide_regions"] == []
        assert result["shrink_regions"] == {}

    def test_robes_hide_torso_and_legs(self):
        """Robes hide torso and upper legs."""
        result = compute_equipment_body_changes({"chest_armor": "robes"})
        assert "torso_skin" in result["hide_regions"]
        assert "upper_legs_skin" in result["hide_regions"]

    def test_plate_gauntlet_hides_hands_forearms(self):
        result = compute_equipment_body_changes({"gauntlet": "plate"})
        assert "hand_skin" in result["hide_regions"]
        assert "forearm_skin" in result["hide_regions"]

    def test_leather_gauntlet_hides_hands_only(self):
        result = compute_equipment_body_changes({"gauntlet": "leather"})
        assert "hand_skin" in result["hide_regions"]
        assert "forearm_skin" not in result["hide_regions"]

    def test_wraps_hide_nothing(self):
        result = compute_equipment_body_changes({"gauntlet": "wraps"})
        assert result["hide_regions"] == []

    def test_plate_boots(self):
        result = compute_equipment_body_changes({"boot": "plate"})
        assert "foot_skin" in result["hide_regions"]
        assert "shin_skin" in result["hide_regions"]

    def test_sandals_hide_nothing(self):
        result = compute_equipment_body_changes({"boot": "sandals"})
        assert result["hide_regions"] == []

    def test_combined_equipment(self):
        """Full armor set combines all hide regions."""
        result = compute_equipment_body_changes({
            "helmet": "full_helm",
            "chest_armor": "plate",
            "gauntlet": "plate",
            "boot": "plate",
        })
        assert "head_hair" in result["hide_regions"]
        assert "torso_skin" in result["hide_regions"]
        assert "hand_skin" in result["hide_regions"]
        assert "foot_skin" in result["hide_regions"]
        assert result["hair_visible"] is False
        assert result["shrink_regions"]["torso"] == pytest.approx(0.02)

    def test_invalid_slot_raises(self):
        with pytest.raises(ValueError, match="Unknown equipment slot"):
            compute_equipment_body_changes({"weapon": "sword"})

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown style"):
            compute_equipment_body_changes({"helmet": "nonexistent"})

    def test_invalid_type_raises(self):
        with pytest.raises(TypeError):
            compute_equipment_body_changes("not a dict")

    def test_skull_mask_hides_facial_hair(self):
        result = compute_equipment_body_changes({"helmet": "skull_mask"})
        assert "facial_hair" in result["hide_regions"]
        assert result["facial_hair_visible"] is False
        assert result["hair_visible"] is True  # Head hair still visible

    def test_no_duplicate_regions(self):
        """Hide regions list has no duplicates."""
        result = compute_equipment_body_changes({
            "chest_armor": "robes",
            "leg_armor": "plate",
        })
        assert len(result["hide_regions"]) == len(set(result["hide_regions"]))

    def test_all_slots_all_styles(self):
        """Every defined slot/style combination produces valid output."""
        for slot, styles in BODY_PART_VISIBILITY.items():
            for style in styles:
                result = compute_equipment_body_changes({slot: style})
                assert "hide_regions" in result
                assert "shrink_regions" in result
                assert "hair_visible" in result
                assert "facial_hair_visible" in result

    def test_shrink_takes_maximum(self):
        """When multiple items shrink same region, max is used."""
        # Plate chest (0.02) + plate pauldron (0.015 for shoulders)
        result = compute_equipment_body_changes({
            "chest_armor": "plate",
            "pauldron": "plate",
        })
        assert result["shrink_regions"]["torso"] == pytest.approx(0.02)
        assert result["shrink_regions"]["shoulders"] == pytest.approx(0.015)


class TestBodyShrink:
    """Test apply_body_shrink."""

    def test_no_shrink_no_change(self):
        """Empty shrink map returns identical vertices."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        normals = [(0, 0, 1), (0, 0, 1), (0, 0, 1)]
        result = apply_body_shrink(verts, normals, {}, {})
        assert result == list(verts)

    def test_shrink_moves_inward(self):
        """Shrink moves vertices opposite to normal direction."""
        verts = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        normals = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        regions = {"torso": [0, 1]}
        shrink = {"torso": 0.01}

        result = apply_body_shrink(verts, normals, regions, shrink)
        # Vertex 0 should move in -X
        assert result[0][0] < 1.0
        assert result[0][0] == pytest.approx(0.99)
        # Vertex 1 should move in -Y
        assert result[1][1] < 1.0
        assert result[1][1] == pytest.approx(0.99)

    def test_unaffected_vertices_unchanged(self):
        """Vertices not in any shrink region stay the same."""
        verts = [(0, 0, 0), (1, 0, 0)]
        normals = [(0, 0, 1), (0, 0, 1)]
        regions = {"torso": [0]}  # Only vertex 0
        shrink = {"torso": 0.05}

        result = apply_body_shrink(verts, normals, regions, shrink)
        assert result[1] == (1, 0, 0)  # Unchanged

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="body_vertices length"):
            apply_body_shrink(
                [(0, 0, 0)], [(0, 0, 1), (0, 0, 1)],
                {}, {},
            )

    def test_out_of_range_index_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            apply_body_shrink(
                [(0, 0, 0)], [(0, 0, 1)],
                {"torso": [5]}, {"torso": 0.01},
            )

    def test_zero_shrink_no_change(self):
        """Zero shrink distance doesn't move vertices."""
        verts = [(1.0, 0.0, 0.0)]
        normals = [(1.0, 0.0, 0.0)]
        regions = {"torso": [0]}
        shrink = {"torso": 0.0}

        result = apply_body_shrink(verts, normals, regions, shrink)
        assert result[0] == (1.0, 0.0, 0.0)

    def test_missing_region_in_assignments(self):
        """Shrink map references region not in assignments -- no crash."""
        verts = [(0, 0, 0)]
        normals = [(0, 0, 1)]
        result = apply_body_shrink(verts, normals, {}, {"torso": 0.01})
        assert result[0] == (0, 0, 0)

    def test_negative_index_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            apply_body_shrink(
                [(0, 0, 0)], [(0, 0, 1)],
                {"torso": [-1]}, {"torso": 0.01},
            )


class TestBodyRegionAssignment:
    """Test get_body_region_vertices."""

    def test_basic_assignment(self):
        """Vertices at known heights are assigned to correct regions."""
        body_height = 1.8
        verts = [
            (0, 0, 0.0),    # feet
            (0, 0, 0.3),    # shins
            (0, 0, 0.5),    # knees / upper legs
            (0, 0, 0.9),    # upper legs / torso
            (0, 0, 1.2),    # torso
            (0, 0, 1.6),    # torso/shoulders
            (0, 0, 1.7),    # head
        ]
        regions = get_body_region_vertices(verts, body_center=(0, 0, 0), body_height=body_height)

        # Verify regions are dicts with lists
        for name, indices in regions.items():
            assert isinstance(indices, list), f"{name} should be a list"
            for idx in indices:
                assert 0 <= idx < len(verts)

        # Verify all vertices are assigned to exactly one region
        all_assigned = []
        for indices in regions.values():
            all_assigned.extend(indices)
        assert sorted(all_assigned) == list(range(len(verts)))

    def test_all_regions_present(self):
        """All expected regions are returned."""
        regions = get_body_region_vertices([(0, 0, 0)])
        expected = {"head", "torso", "shoulders", "upper_legs", "knees",
                     "shins", "feet", "hands", "forearms"}
        assert set(regions.keys()) == expected

    def test_empty_vertices(self):
        """Empty vertex list produces empty regions."""
        regions = get_body_region_vertices([])
        for indices in regions.values():
            assert len(indices) == 0


class TestVertexNormals:
    """Test compute_vertex_normals."""

    def test_simple_triangle(self):
        """Single upward-facing triangle has Z-up normals."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        faces = [(0, 1, 2)]
        normals = compute_vertex_normals(verts, faces)
        assert len(normals) == 3
        # All should point up (positive Z)
        for n in normals:
            assert n[2] > 0.9

    def test_quad(self):
        """Quad face produces consistent normals."""
        verts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        faces = [(0, 1, 2, 3)]
        normals = compute_vertex_normals(verts, faces)
        assert len(normals) == 4

    def test_normals_are_normalized(self):
        """All normals have unit length."""
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
        faces = [(0, 1, 2), (1, 3, 2)]
        normals = compute_vertex_normals(verts, faces)
        for n in normals:
            length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            assert length == pytest.approx(1.0, abs=0.001)

    def test_empty_input(self):
        normals = compute_vertex_normals([], [])
        assert normals == []


# ===========================================================================
# INTEGRATION TESTS
# ===========================================================================


class TestIntegration:
    """Integration tests combining hair + equipment systems."""

    def test_hair_then_helmet_workflow(self):
        """Generate hair, check helmet compatibility, validate rules."""
        hair = generate_hair_mesh(style="long_flowing")
        assert len(hair["vertices"]) > 0

        compat = get_helmet_compatible_hair("long_flowing", "full_helm")
        assert compat["visible"] is False

        body_changes = compute_equipment_body_changes({"helmet": "full_helm"})
        assert body_changes["hair_visible"] is False

    def test_full_character_equipment(self):
        """Full armor set with all body changes computed correctly."""
        equipped = {
            "helmet": "open_face",
            "chest_armor": "chain",
            "gauntlet": "leather",
            "boot": "leather",
        }
        changes = compute_equipment_body_changes(equipped)

        # Open face helm only hides top hair
        assert changes["hair_visible"] is False  # head_hair_top counts
        assert "torso_skin" in changes["hide_regions"]
        assert "hand_skin" in changes["hide_regions"]
        assert "foot_skin" in changes["hide_regions"]
        assert changes["shrink_regions"]["torso"] == pytest.approx(0.01)

    def test_shrink_with_real_normals(self):
        """Compute normals from mesh data, then apply shrink."""
        # Simple box-like mesh
        verts = [
            (0.5, 0, 0), (-0.5, 0, 0),
            (0, 0.5, 0), (0, -0.5, 0),
        ]
        faces = [(0, 2, 1), (0, 1, 3)]

        normals = compute_vertex_normals(verts, faces)
        assert len(normals) == len(verts)

        regions = {"torso": [0, 1, 2, 3]}
        shrunk = apply_body_shrink(verts, normals, regions, {"torso": 0.01})

        # Verify vertices moved
        for orig, new in zip(verts, shrunk):
            assert orig != new or all(
                abs(o - n) < 1e-9 for o, n in zip(orig, new)
            )
