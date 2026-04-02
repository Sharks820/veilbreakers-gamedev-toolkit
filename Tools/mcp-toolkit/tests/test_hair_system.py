"""Tests for hair_system handler."""

import math

import pytest

from blender_addon.handlers.hair_system import (
    HAIR_STYLES,
    FACIAL_HAIR_STYLES,
    generate_hair_mesh,
    get_helmet_compatible_hair,
    generate_facial_hair_mesh,
)


# ---------------------------------------------------------------------------
# Style definitions
# ---------------------------------------------------------------------------


class TestStyleDefinitions:
    def test_hair_styles_exist(self):
        assert len(HAIR_STYLES) >= 12

    def test_facial_hair_styles_exist(self):
        assert len(FACIAL_HAIR_STYLES) >= 8

    def test_bald_has_zero_cards(self):
        assert HAIR_STYLES["bald"]["card_count"] == 0

    def test_clean_shaven_has_zero_cards(self):
        assert FACIAL_HAIR_STYLES["clean_shaven"]["card_count"] == 0

    def test_all_styles_have_card_count(self):
        for name, style in HAIR_STYLES.items():
            assert "card_count" in style, f"Style '{name}' missing card_count"

    def test_non_bald_styles_have_length(self):
        for name, style in HAIR_STYLES.items():
            if style["card_count"] > 0:
                assert "length" in style, f"Style '{name}' missing length"
                assert style["length"] > 0


# ---------------------------------------------------------------------------
# Hair mesh generation
# ---------------------------------------------------------------------------


class TestGenerateHairMesh:
    def test_basic_generation(self):
        result = generate_hair_mesh("medium_swept")
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0
        assert len(result["uvs"]) > 0

    def test_bald_returns_empty(self):
        result = generate_hair_mesh("bald")
        assert result["vertices"] == []
        assert result["faces"] == []
        assert result["metadata"]["card_count"] == 0

    def test_vertices_are_3d(self):
        result = generate_hair_mesh("short_crop")
        for v in result["vertices"]:
            assert len(v) == 3

    def test_uvs_are_2d(self):
        result = generate_hair_mesh("long_flowing")
        for uv in result["uvs"]:
            assert len(uv) == 2
            assert 0.0 <= uv[0] <= 1.0
            assert 0.0 <= uv[1] <= 1.0

    def test_face_indices_valid(self):
        result = generate_hair_mesh("ponytail")
        n = len(result["vertices"])
        for face in result["faces"]:
            for idx in face:
                assert 0 <= idx < n

    def test_metadata_present(self):
        result = generate_hair_mesh("mohawk")
        meta = result["metadata"]
        assert "name" in meta
        assert "poly_count" in meta
        assert "vertex_count" in meta
        assert meta["vertex_count"] == len(result["vertices"])
        assert meta["poly_count"] == len(result["faces"])

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown hair style"):
            generate_hair_mesh("nonexistent_style")

    def test_all_styles_generate(self):
        for style_name in HAIR_STYLES:
            result = generate_hair_mesh(style_name)
            assert isinstance(result, dict)
            assert "vertices" in result
            assert "faces" in result

    def test_custom_head_params(self):
        result = generate_hair_mesh(
            "short_crop",
            head_radius=0.15,
            head_center=(0, 0, 2.0),
        )
        assert len(result["vertices"]) > 0
        # Vertices should be near the custom head center
        for v in result["vertices"]:
            assert abs(v[2] - 2.0) < 1.0  # Z near head center

    def test_longer_hair_more_vertices(self):
        short = generate_hair_mesh("short_crop")
        long_ = generate_hair_mesh("long_flowing")
        # Long hair has more cards, thus more vertices
        assert len(long_["vertices"]) > len(short["vertices"])


# ---------------------------------------------------------------------------
# Helmet compatibility
# ---------------------------------------------------------------------------


class TestHelmetCompatibility:
    def test_full_helm_hides_all(self):
        result = get_helmet_compatible_hair("long_flowing", "full_helm")
        assert result["visible"] is False
        assert "all" in result["hide_regions"]

    def test_crown_shows_all(self):
        result = get_helmet_compatible_hair("long_flowing", "crown")
        assert result["visible"] is True
        assert result["hide_regions"] == []

    def test_open_face_shows_back(self):
        result = get_helmet_compatible_hair("medium_swept", "open_face")
        assert result["visible"] is True
        assert result["modified_coverage"] == "back_and_sides"

    def test_hood_shows_fringe(self):
        result = get_helmet_compatible_hair("long_straight", "hood")
        assert result["visible"] is True
        assert result["modified_coverage"] == "front_fringe"

    def test_skull_mask_shows_all(self):
        result = get_helmet_compatible_hair("wild_loose", "skull_mask")
        assert result["visible"] is True
        assert result["hide_regions"] == []

    def test_bald_always_compatible(self):
        for helmet in ["full_helm", "open_face", "hood", "crown", "skull_mask"]:
            result = get_helmet_compatible_hair("bald", helmet)
            assert result["visible"] is False

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown hair style"):
            get_helmet_compatible_hair("nonexistent", "crown")

    def test_invalid_helmet_raises(self):
        with pytest.raises(ValueError, match="Unknown helmet style"):
            get_helmet_compatible_hair("mohawk", "baseball_cap")

    def test_original_style_preserved(self):
        result = get_helmet_compatible_hair("ponytail", "open_face")
        assert result["original_style"] == "ponytail"


# ---------------------------------------------------------------------------
# Facial hair generation
# ---------------------------------------------------------------------------


class TestGenerateFacialHairMesh:
    def test_basic_generation(self):
        result = generate_facial_hair_mesh("full_beard")
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0

    def test_clean_shaven_empty(self):
        result = generate_facial_hair_mesh("clean_shaven")
        assert result["vertices"] == []
        assert result["faces"] == []
        assert result["metadata"]["card_count"] == 0

    def test_vertices_3d(self):
        result = generate_facial_hair_mesh("short_beard")
        for v in result["vertices"]:
            assert len(v) == 3

    def test_face_indices_valid(self):
        result = generate_facial_hair_mesh("goatee")
        n = len(result["vertices"])
        for face in result["faces"]:
            for idx in face:
                assert 0 <= idx < n

    def test_braided_beard(self):
        result = generate_facial_hair_mesh("braided_beard")
        assert len(result["vertices"]) > 0
        assert result["metadata"].get("braided") is True

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError, match="Unknown facial hair style"):
            generate_facial_hair_mesh("handlebar")

    def test_all_facial_styles_generate(self):
        for style_name in FACIAL_HAIR_STYLES:
            result = generate_facial_hair_mesh(style_name)
            assert isinstance(result, dict)

    def test_mustache_has_few_cards(self):
        result = generate_facial_hair_mesh("mustache")
        assert result["metadata"]["card_count"] <= 15

    def test_stubble_short_length(self):
        result = generate_facial_hair_mesh("stubble")
        if result["vertices"]:
            # Stubble cards should be very short
            assert result["metadata"]["hair_length"] < 0.01
