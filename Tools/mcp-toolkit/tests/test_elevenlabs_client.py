"""Unit tests for ElevenLabs audio client.

Tests ElevenLabsAudioClient in stub mode (no API key) and verifies
the expected return structure. Live mode is tested with mocked SDK calls.
"""

import os
import struct
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from veilbreakers_mcp.shared.elevenlabs_client import ElevenLabsAudioClient


# ---------------------------------------------------------------------------
# Stub mode (no API key)
# ---------------------------------------------------------------------------


class TestElevenLabsAudioClientStubMode:
    """Tests for ElevenLabsAudioClient when no API key is provided."""

    def test_stub_mode_when_no_key(self):
        client = ElevenLabsAudioClient(api_key="")
        assert client.stub_mode is True

    def test_stub_mode_when_none_key(self):
        import os
        old_val = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            client = ElevenLabsAudioClient(api_key=None)
            assert client.stub_mode is True
        finally:
            if old_val is not None:
                os.environ["ELEVENLABS_API_KEY"] = old_val

    def test_not_stub_mode_with_key(self):
        client = ElevenLabsAudioClient(api_key="test-key-123")
        assert client.stub_mode is False

    def test_generate_sfx_stub_returns_dict(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_sfx.wav")
            result = client.generate_sfx(
                description="sword slash",
                duration_seconds=2.0,
                output_path=output_path,
            )
            assert isinstance(result, dict)
            assert result["stub"] is True
            assert result["path"] == output_path
            assert result["duration"] == 2.0
            assert "sword slash" in result["description"]

    def test_generate_sfx_stub_creates_valid_wav(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_sfx.wav")
            client.generate_sfx(
                description="explosion",
                duration_seconds=1.0,
                output_path=output_path,
            )
            assert os.path.exists(output_path)
            # Verify WAV header
            with open(output_path, "rb") as f:
                data = f.read(12)
                assert data[:4] == b"RIFF"
                assert data[8:12] == b"WAVE"

    def test_generate_sfx_stub_wav_correct_duration(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_sfx.wav")
            client.generate_sfx(
                description="click",
                duration_seconds=3.0,
                output_path=output_path,
            )
            file_size = os.path.getsize(output_path)
            # 44 byte header + 3 seconds * 44100 Hz * 2 bytes/sample
            expected_data_size = 3 * 44100 * 2
            expected_total = 44 + expected_data_size
            assert file_size == expected_total

    def test_generate_music_loop_stub(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "combat_loop.wav")
            result = client.generate_music_loop(
                theme="combat",
                duration_seconds=10.0,
                output_path=output_path,
            )
            assert result["stub"] is True
            assert result["path"] == output_path
            assert os.path.exists(output_path)

    def test_generate_voice_line_stub(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "voice.wav")
            result = client.generate_voice_line(
                text="You dare enter my domain?",
                voice_id="default",
                output_path=output_path,
            )
            assert result["stub"] is True
            assert result["path"] == output_path
            assert os.path.exists(output_path)

    def test_generate_ambient_layers_stub(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.generate_ambient_layers(
                biome="forest",
                layers=["wind", "birds", "water"],
                output_dir=tmpdir,
            )
            assert result["stub"] is True
            assert len(result["layer_paths"]) == 3
            for layer_path in result["layer_paths"]:
                assert os.path.exists(layer_path)

    def test_generate_ambient_layers_default_layers(self):
        client = ElevenLabsAudioClient(api_key="")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = client.generate_ambient_layers(
                biome="cave",
                output_dir=tmpdir,
            )
            assert result["stub"] is True
            assert len(result["layer_paths"]) > 0


# ---------------------------------------------------------------------------
# Live mode (mocked SDK)
# ---------------------------------------------------------------------------


class TestElevenLabsAudioClientLiveMode:
    """Tests for ElevenLabsAudioClient with mocked ElevenLabs SDK."""

    def test_generate_sfx_live_calls_sdk(self):
        mock_client_cls = MagicMock()
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.text_to_sound_effects.convert.return_value = iter(
            [b"\x00" * 100]
        )

        with patch(
            "veilbreakers_mcp.shared.elevenlabs_client._ElevenLabsSDK",
            mock_client_cls,
        ):
            client = ElevenLabsAudioClient(api_key="live-key")
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "sfx.mp3")
                result = client.generate_sfx(
                    description="metal clang",
                    duration_seconds=2.0,
                    output_path=output_path,
                )
                assert result["stub"] is False
                assert result["path"] == output_path
                assert os.path.exists(output_path)
                mock_instance.text_to_sound_effects.convert.assert_called_once()

    def test_generate_music_loop_live_calls_sdk(self):
        mock_client_cls = MagicMock()
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.text_to_sound_effects.convert.return_value = iter(
            [b"\x00" * 200]
        )

        with patch(
            "veilbreakers_mcp.shared.elevenlabs_client._ElevenLabsSDK",
            mock_client_cls,
        ):
            client = ElevenLabsAudioClient(api_key="live-key")
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "loop.mp3")
                result = client.generate_music_loop(
                    theme="combat",
                    duration_seconds=20.0,
                    output_path=output_path,
                )
                assert result["stub"] is False
                assert result["path"] == output_path
                # Verify the call used "loopable" prefix
                call_args = (
                    mock_instance.text_to_sound_effects.convert.call_args
                )
                assert "loopable" in call_args.kwargs.get(
                    "text", call_args[1].get("text", "")
                ).lower() or "loopable" in str(call_args)

    def test_generate_voice_line_live_calls_tts(self):
        mock_client_cls = MagicMock()
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.text_to_speech.convert.return_value = iter(
            [b"\x00" * 150]
        )

        with patch(
            "veilbreakers_mcp.shared.elevenlabs_client._ElevenLabsSDK",
            mock_client_cls,
        ):
            client = ElevenLabsAudioClient(api_key="live-key")
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, "voice.mp3")
                result = client.generate_voice_line(
                    text="Hello traveler",
                    voice_id="voice_abc",
                    output_path=output_path,
                )
                assert result["stub"] is False
                mock_instance.text_to_speech.convert.assert_called_once()

    def test_generate_ambient_layers_live(self):
        mock_client_cls = MagicMock()
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.text_to_sound_effects.convert.return_value = iter(
            [b"\x00" * 100]
        )

        with patch(
            "veilbreakers_mcp.shared.elevenlabs_client._ElevenLabsSDK",
            mock_client_cls,
        ):
            client = ElevenLabsAudioClient(api_key="live-key")
            with tempfile.TemporaryDirectory() as tmpdir:
                result = client.generate_ambient_layers(
                    biome="forest",
                    layers=["wind", "birds"],
                    output_dir=tmpdir,
                )
                assert result["stub"] is False
                assert len(result["layer_paths"]) == 2


# ---------------------------------------------------------------------------
# Constructor / configuration
# ---------------------------------------------------------------------------


class TestElevenLabsAudioClientConfig:
    """Tests for ElevenLabsAudioClient configuration."""

    def test_accepts_api_key_string(self):
        client = ElevenLabsAudioClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    def test_empty_string_is_stub(self):
        client = ElevenLabsAudioClient(api_key="")
        assert client.stub_mode is True

    def test_valid_key_is_not_stub(self):
        client = ElevenLabsAudioClient(api_key="real-key")
        assert client.stub_mode is False

    def test_default_no_env_is_stub(self):
        """When no api_key arg given and no env var, should be stub mode."""
        old_val = os.environ.pop("ELEVENLABS_API_KEY", None)
        try:
            client = ElevenLabsAudioClient()
            assert client.stub_mode is True
        finally:
            if old_val is not None:
                os.environ["ELEVENLABS_API_KEY"] = old_val
