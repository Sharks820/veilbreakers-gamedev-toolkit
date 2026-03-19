"""Unit tests for Real-ESRGAN runner.

Tests upscale_texture and check_esrgan_available with mocked subprocess.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# check_esrgan_available tests
# ---------------------------------------------------------------------------


class TestCheckEsrganAvailable:
    """Test binary availability detection."""

    def test_returns_false_when_binary_missing(self, tmp_path):
        """check_esrgan_available returns False when path does not exist."""
        from veilbreakers_mcp.shared.esrgan_runner import check_esrgan_available

        assert check_esrgan_available(str(tmp_path / "nonexistent.exe")) is False

    def test_returns_true_when_binary_exists(self, tmp_path):
        """check_esrgan_available returns True when file exists."""
        from veilbreakers_mcp.shared.esrgan_runner import check_esrgan_available

        binary = tmp_path / "realesrgan-ncnn-vulkan.exe"
        binary.write_text("fake binary")
        assert check_esrgan_available(str(binary)) is True


# ---------------------------------------------------------------------------
# upscale_texture tests
# ---------------------------------------------------------------------------


class TestUpscaleTexture:
    """Test upscale_texture subprocess command construction."""

    @pytest.mark.asyncio
    async def test_constructs_correct_subprocess_command(self, tmp_path):
        """upscale_texture builds correct CLI args for realesrgan-ncnn-vulkan."""
        from veilbreakers_mcp.shared.esrgan_runner import upscale_texture

        binary = tmp_path / "realesrgan-ncnn-vulkan.exe"
        binary.write_text("fake binary")
        input_file = tmp_path / "texture.png"
        input_file.write_text("fake image")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "done"
        mock_result.stderr = ""

        with patch(
            "veilbreakers_mcp.shared.esrgan_runner.subprocess.run",
            return_value=mock_result,
        ) as mock_run:
            result = await upscale_texture(
                input_path=str(input_file),
                scale=4,
                model="realesrgan-x4plus",
                esrgan_path=str(binary),
            )

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert str(binary) in cmd[0]
        assert "-i" in cmd
        assert "-s" in cmd
        assert "4" in cmd
        assert "-n" in cmd
        assert "realesrgan-x4plus" in cmd
        assert "-f" in cmd
        assert "png" in cmd

    @pytest.mark.asyncio
    async def test_raises_file_not_found_when_binary_missing(self, tmp_path):
        """upscale_texture raises FileNotFoundError when binary is missing."""
        from veilbreakers_mcp.shared.esrgan_runner import upscale_texture

        input_file = tmp_path / "texture.png"
        input_file.write_text("fake image")

        with pytest.raises(FileNotFoundError, match="realesrgan"):
            await upscale_texture(
                input_path=str(input_file),
                esrgan_path=str(tmp_path / "nonexistent.exe"),
            )

    @pytest.mark.asyncio
    async def test_returns_output_path_on_success(self, tmp_path):
        """upscale_texture returns dict with output path on success."""
        from veilbreakers_mcp.shared.esrgan_runner import upscale_texture

        binary = tmp_path / "realesrgan-ncnn-vulkan.exe"
        binary.write_text("fake binary")
        input_file = tmp_path / "texture.png"
        input_file.write_text("fake image")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "done"
        mock_result.stderr = ""

        with patch(
            "veilbreakers_mcp.shared.esrgan_runner.subprocess.run",
            return_value=mock_result,
        ):
            result = await upscale_texture(
                input_path=str(input_file),
                scale=2,
                esrgan_path=str(binary),
            )

        assert result["success"] is True
        assert "output" in result
        assert result["scale"] == 2
