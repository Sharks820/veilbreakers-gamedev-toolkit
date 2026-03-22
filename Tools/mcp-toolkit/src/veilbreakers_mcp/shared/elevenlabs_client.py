"""ElevenLabs AI audio generation client.

Provides ElevenLabsAudioClient for generating SFX, music loops, voice lines,
and ambient soundscapes via the ElevenLabs Python SDK. Falls back to stub mode
(silent WAV files) when no API key is configured.

Pattern follows gemini_client.py's graceful degradation approach.
"""

from __future__ import annotations

import os
import struct
import time
from pathlib import Path
from typing import Any

try:
    from elevenlabs.client import ElevenLabs as _ElevenLabsSDK  # type: ignore[import-untyped]
except ImportError:
    _ElevenLabsSDK = None  # type: ignore[assignment, misc]


# Default ambient layer definitions per biome
_BIOME_LAYERS: dict[str, list[str]] = {
    "forest": ["gentle wind through trees", "birds chirping", "distant stream water flowing"],
    "cave": ["dripping water echoes", "distant rumble", "cave wind howl"],
    "town": ["crowd murmur", "distant blacksmith hammering", "wooden cart wheels"],
    "dungeon": ["chains rattling", "distant growl", "torches crackling"],
    "desert": ["sand wind blowing", "distant eagle cry", "dry heat shimmer hum"],
    "swamp": ["bubbling mud", "insects buzzing", "frog croaking"],
}


class ElevenLabsAudioClient:
    """Client for ElevenLabs AI audio generation.

    Supports SFX generation, music loop creation, voice line synthesis,
    and ambient soundscape layering. When no API key is provided, operates
    in stub mode -- generating silent WAV placeholder files.

    Args:
        api_key: ElevenLabs API key. If empty/None, runs in stub mode.
        unity_project_path: Optional Unity project root for resolving paths.
    """

    def __init__(
        self,
        api_key: str | None = None,
        unity_project_path: str = "",
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        self.api_key: str = api_key
        self.stub_mode: bool = not bool(api_key)
        self.unity_project_path: str = unity_project_path
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazily initialise the ElevenLabs SDK client."""
        if self._client is None:
            if _ElevenLabsSDK is None:
                raise ImportError(
                    "elevenlabs package not installed. Run: pip install elevenlabs"
                )
            self._client = _ElevenLabsSDK(api_key=self.api_key)
        return self._client

    # ------------------------------------------------------------------
    # Stub helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_silent_wav(path: str, duration_seconds: float) -> None:
        """Write a minimal valid WAV file with silence.

        Creates a 16-bit mono PCM WAV at 44100 Hz with the specified duration.
        """
        sample_rate = 44100
        bits_per_sample = 16
        num_channels = 1
        num_samples = int(sample_rate * duration_seconds)
        data_size = num_samples * num_channels * (bits_per_sample // 8)

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            # RIFF header
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + data_size))  # file size - 8
            f.write(b"WAVE")
            # fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))  # chunk size
            f.write(struct.pack("<H", 1))  # PCM format
            f.write(struct.pack("<H", num_channels))
            f.write(struct.pack("<I", sample_rate))
            f.write(
                struct.pack("<I", sample_rate * num_channels * (bits_per_sample // 8))
            )  # byte rate
            f.write(struct.pack("<H", num_channels * (bits_per_sample // 8)))  # block align
            f.write(struct.pack("<H", bits_per_sample))
            # data chunk
            f.write(b"data")
            f.write(struct.pack("<I", data_size))
            f.write(b"\x00" * data_size)

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    @staticmethod
    def _retry_on_rate_limit(fn, *args, max_retries: int = 3, **kwargs) -> Any:
        """Execute *fn* with exponential backoff on HTTP 429 rate-limit errors."""
        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except (ConnectionError, TimeoutError, OSError, ValueError, KeyError) as exc:
                is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
                if is_rate_limit and attempt < max_retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sfx(
        self,
        description: str,
        duration_seconds: float = 2.0,
        output_path: str = "sfx.wav",
    ) -> dict[str, Any]:
        """Generate a sound effect from a text description.

        Args:
            description: Text description of the sound (e.g., "sword slash metal impact").
            duration_seconds: Duration in seconds.
            output_path: File path to write the audio to.

        Returns:
            Dict with path, duration, stub flag, and description.
        """
        if self.stub_mode:
            self._write_silent_wav(output_path, duration_seconds)
            return {
                "path": output_path,
                "duration": duration_seconds,
                "stub": True,
                "description": description,
            }

        client = self._get_client()
        audio_iter = self._retry_on_rate_limit(
            client.text_to_sound_effects.convert,
            text=description,
            duration_seconds=duration_seconds,
            prompt_influence=0.5,
        )
        audio_bytes = b"".join(audio_iter)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return {
            "path": output_path,
            "duration": duration_seconds,
            "stub": False,
            "description": description,
        }

    def generate_music_loop(
        self,
        theme: str = "combat",
        duration_seconds: float = 22.0,
        output_path: str = "music_loop.mp3",
    ) -> dict[str, Any]:
        """Generate a loopable music track for the given theme.

        Args:
            theme: Music theme keyword (e.g., "combat", "exploration", "boss", "town").
            duration_seconds: Duration in seconds (typically 22-30s for loops).
            output_path: File path to write the audio to.

        Returns:
            Dict with path, duration, stub flag, and description.
        """
        description = f"loopable {theme} game music loop, seamless"

        if self.stub_mode:
            self._write_silent_wav(output_path, duration_seconds)
            return {
                "path": output_path,
                "duration": duration_seconds,
                "stub": True,
                "description": description,
            }

        client = self._get_client()
        audio_iter = self._retry_on_rate_limit(
            client.text_to_sound_effects.convert,
            text=description,
            duration_seconds=duration_seconds,
            prompt_influence=0.5,
        )
        audio_bytes = b"".join(audio_iter)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        return {
            "path": output_path,
            "duration": duration_seconds,
            "stub": False,
            "description": description,
        }

    def generate_voice_line(
        self,
        text: str,
        voice_id: str = "default",
        output_path: str = "voice.mp3",
    ) -> dict[str, Any]:
        """Synthesise a voice line using ElevenLabs TTS.

        Args:
            text: Dialogue text to synthesise.
            voice_id: ElevenLabs voice ID or "default".
            output_path: File path to write the audio to.

        Returns:
            Dict with path, stub flag, text, and voice_id.
        """
        if self.stub_mode:
            # Estimate ~3 words/second for duration
            word_count = max(1, len(text.split()))
            duration = max(1.0, word_count / 3.0)
            self._write_silent_wav(output_path, duration)
            return {
                "path": output_path,
                "duration": duration,
                "stub": True,
                "description": text,
                "voice_id": voice_id,
            }

        client = self._get_client()

        # Use a sensible default voice if "default" is specified
        effective_voice_id = voice_id if voice_id != "default" else "21m00Tcm4TlvDq8ikWAM"

        audio_iter = self._retry_on_rate_limit(
            client.text_to_speech.convert,
            text=text,
            voice_id=effective_voice_id,
            model_id="eleven_multilingual_v2",
        )
        audio_bytes = b"".join(audio_iter)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        word_count = max(1, len(text.split()))
        duration = max(1.0, word_count / 3.0)

        return {
            "path": output_path,
            "duration": duration,
            "stub": False,
            "description": text,
            "voice_id": voice_id,
        }

    def generate_ambient_layers(
        self,
        biome: str = "forest",
        layers: list[str] | None = None,
        output_dir: str = "ambient",
    ) -> dict[str, Any]:
        """Generate layered ambient soundscape for a biome.

        Each layer is a separate audio file that can be mixed in Unity.

        Args:
            biome: Biome type (forest, cave, town, dungeon, desert, swamp).
            layers: Optional list of layer descriptions. If None, uses biome defaults.
            output_dir: Directory to write the layer audio files.

        Returns:
            Dict with layer_paths list, biome, stub flag.
        """
        if layers is None:
            layers = _BIOME_LAYERS.get(biome, _BIOME_LAYERS["forest"])

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        layer_paths: list[str] = []

        for i, layer_desc in enumerate(layers):
            safe_name = layer_desc.replace(" ", "_")[:30]
            filename = f"{biome}_layer{i}_{safe_name}.wav"
            output_path = os.path.join(output_dir, filename)

            result = self.generate_sfx(
                description=f"{biome} ambient {layer_desc}",
                duration_seconds=10.0,
                output_path=output_path,
            )
            layer_paths.append(result["path"])

        return {
            "layer_paths": layer_paths,
            "biome": biome,
            "layers": layers,
            "stub": self.stub_mode,
        }
