"""Unit tests for Stable Fast 3D local generator wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestStableFast3DGenerator:
    @pytest.mark.asyncio
    async def test_returns_unavailable_when_repo_missing(self, tmp_path):
        from veilbreakers_mcp.shared.stable_fast3d_client import StableFast3DGenerator

        gen = StableFast3DGenerator(repo_path=str(tmp_path / "missing-repo"))
        result = await gen.generate_from_image(
            image_path=str(tmp_path / "input.png"),
            output_dir=str(tmp_path),
        )

        assert result["status"] == "unavailable"
        assert "run.py" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_success_for_valid_output(self, tmp_path):
        from veilbreakers_mcp.shared.stable_fast3d_client import StableFast3DGenerator

        repo_path = tmp_path / "stable-fast-3d"
        repo_path.mkdir()
        (repo_path / "run.py").write_text("print('ok')", encoding="utf-8")
        image_path = tmp_path / "input.png"
        image_path.write_bytes(b"fake")
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        glb_path = out_dir / "model.glb"
        glb_path.write_bytes(b"glb")

        fake_proc = MagicMock(
            returncode=0,
            stdout="finished",
            stderr="",
        )

        with patch(
            "veilbreakers_mcp.shared.stable_fast3d_client.subprocess.run",
            return_value=fake_proc,
        ), patch(
            "veilbreakers_mcp.shared.stable_fast3d_client.validate_generated_model_file",
            return_value={"valid": True},
        ):
            gen = StableFast3DGenerator(repo_path=str(repo_path), python_executable="python")
            result = await gen.generate_from_image(
                image_path=str(image_path),
                output_dir=str(out_dir),
            )

        assert result["status"] == "success"
        assert result["model_path"] == str(glb_path)
        assert result["backend"] == "stable_fast_3d"

    @pytest.mark.asyncio
    async def test_returns_failed_when_subprocess_errors(self, tmp_path):
        from veilbreakers_mcp.shared.stable_fast3d_client import StableFast3DGenerator

        repo_path = tmp_path / "stable-fast-3d"
        repo_path.mkdir()
        (repo_path / "run.py").write_text("print('ok')", encoding="utf-8")
        image_path = tmp_path / "input.png"
        image_path.write_bytes(b"fake")

        def _raise(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="python", timeout=1)

        with patch(
            "veilbreakers_mcp.shared.stable_fast3d_client.subprocess.run",
            side_effect=_raise,
        ):
            gen = StableFast3DGenerator(repo_path=str(repo_path), python_executable="python")
            result = await gen.generate_from_image(
                image_path=str(image_path),
                output_dir=str(tmp_path / "output"),
                timeout=1,
            )

        assert result["status"] == "failed"
        assert "timed out" in result["error"]
