"""Regression tests for standalone texture validation helpers."""

from veilbreakers_mcp.shared.texture_validation import (
    recommend_compression,
    validate_texture_file,
)


class TestTextureValidationErrorPaths:
    """Exercise non-fatal image read failures."""

    def test_validate_texture_file_returns_issue_for_unreadable_image(self, tmp_path):
        bad_file = tmp_path / "broken.png"
        bad_file.write_text("not an image", encoding="utf-8")

        result = validate_texture_file(str(bad_file))

        assert result["valid"] is False
        assert result["issues"]
        assert "Cannot open image" in result["issues"][0]

    def test_recommend_compression_skips_size_estimate_for_unreadable_image(self, tmp_path):
        bad_file = tmp_path / "broken.png"
        bad_file.write_text("not an image", encoding="utf-8")

        result = recommend_compression(str(bad_file), "albedo")

        assert result["recommended_format"] == "BC7"
        assert "estimated_compressed_size_kb" not in result
