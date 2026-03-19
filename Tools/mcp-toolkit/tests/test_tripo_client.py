"""Unit tests for Tripo3D client wrapper.

Tests TripoGenerator with mocked tripo3d SDK -- no API key or network needed.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# TripoGenerator tests
# ---------------------------------------------------------------------------


class TestTripoGeneratorFromText:
    """Test TripoGenerator.generate_from_text with mocked SDK."""

    @pytest.mark.asyncio
    async def test_dispatches_to_sdk_with_correct_params(self, tmp_path):
        """generate_from_text calls tripo3d SDK with prompt, texture, pbr, model_version."""
        from veilbreakers_mcp.shared.tripo_client import TripoGenerator

        mock_client = MagicMock()
        mock_client.text_to_model = MagicMock(return_value="task-123")
        mock_client.wait_for_task = MagicMock(return_value=MagicMock(
            status="success",
            output=MagicMock(
                model="https://example.com/model.glb",
                pbr_model="https://example.com/model_pbr.glb",
            ),
        ))
        mock_client.close = MagicMock()

        with patch(
            "veilbreakers_mcp.shared.tripo_client._create_tripo_client",
            return_value=mock_client,
        ), patch(
            "veilbreakers_mcp.shared.tripo_client._download_file",
            new_callable=AsyncMock,
            return_value=str(tmp_path / "model.glb"),
        ):
            gen = TripoGenerator(api_key="test-key")
            result = await gen.generate_from_text(
                prompt="a wooden barrel",
                output_dir=str(tmp_path),
                texture=True,
                pbr=True,
            )

        mock_client.text_to_model.assert_called_once()
        call_kwargs = mock_client.text_to_model.call_args
        assert "a wooden barrel" in str(call_kwargs)
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_returns_model_path_on_success(self, tmp_path):
        """generate_from_text returns dict with model_path on success."""
        from veilbreakers_mcp.shared.tripo_client import TripoGenerator

        mock_client = MagicMock()
        mock_client.text_to_model = MagicMock(return_value="task-456")
        mock_client.wait_for_task = MagicMock(return_value=MagicMock(
            status="success",
            output=MagicMock(
                model="https://example.com/model.glb",
                pbr_model="https://example.com/model_pbr.glb",
            ),
        ))
        mock_client.close = MagicMock()

        model_path = str(tmp_path / "model.glb")
        with patch(
            "veilbreakers_mcp.shared.tripo_client._create_tripo_client",
            return_value=mock_client,
        ), patch(
            "veilbreakers_mcp.shared.tripo_client._download_file",
            new_callable=AsyncMock,
            return_value=model_path,
        ):
            gen = TripoGenerator(api_key="test-key")
            result = await gen.generate_from_text(
                prompt="a sword",
                output_dir=str(tmp_path),
            )

        assert result["status"] == "success"
        assert "model_path" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_failure(self, tmp_path):
        """generate_from_text returns error dict when SDK task fails."""
        from veilbreakers_mcp.shared.tripo_client import TripoGenerator

        mock_client = MagicMock()
        mock_client.text_to_model = MagicMock(return_value="task-789")
        mock_client.wait_for_task = MagicMock(return_value=MagicMock(
            status="failed",
            output=None,
        ))
        mock_client.close = MagicMock()

        with patch(
            "veilbreakers_mcp.shared.tripo_client._create_tripo_client",
            return_value=mock_client,
        ):
            gen = TripoGenerator(api_key="test-key")
            result = await gen.generate_from_text(
                prompt="a broken mesh",
                output_dir=str(tmp_path),
            )

        assert result["status"] == "failed"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_raises_error_when_no_api_key(self, tmp_path):
        """TripoGenerator raises ValueError when api_key is empty."""
        from veilbreakers_mcp.shared.tripo_client import TripoGenerator

        with pytest.raises(ValueError, match="TRIPO_API_KEY"):
            TripoGenerator(api_key="")
