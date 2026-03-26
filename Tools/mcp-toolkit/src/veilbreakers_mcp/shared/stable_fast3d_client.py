"""Stable Fast 3D wrapper for local image-to-3D generation.

This is the preferred local 3D reconstruction path for the toolkit when a
reference image is available. It keeps the pipeline on-device for the fast,
lower-VRAM cases and falls back to remote generation only when needed.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from veilbreakers_mcp.shared.model_validation import validate_generated_model_file


class StableFast3DGenerator:
    """Wrapper around the official Stable Fast 3D repo's ``run.py`` entrypoint."""

    def __init__(self, repo_path: str, python_executable: str | None = None):
        if not repo_path:
            raise ValueError("STABLE_FAST3D_REPO_PATH is required")
        self.repo_path = Path(repo_path).expanduser().resolve()
        self.python_executable = python_executable or sys.executable
        self.run_script = self.repo_path / "run.py"

    def close(self) -> None:
        """Compatibility no-op for callers that always close generators."""
        return None

    @staticmethod
    def _latest_glb(output_dir: Path) -> Path | None:
        candidates = [p for p in output_dir.rglob("*.glb") if p.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    async def generate_from_image(
        self,
        image_path: str,
        output_dir: str,
        texture_resolution: int = 1024,
        remesh_option: str = "quad",
        timeout: int = 300,
    ) -> dict:
        """Run Stable Fast 3D on a single image and validate the output GLB."""
        if not self.run_script.is_file():
            return {
                "status": "unavailable",
                "error": f"Stable Fast 3D repo not found or missing run.py: {self.run_script}",
            }

        image = Path(image_path)
        if not image.is_file():
            return {
                "status": "failed",
                "error": f"Image file not found: {image_path}",
            }

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.python_executable,
            str(self.run_script),
            str(image),
            "--output-dir",
            str(out_dir),
            "--texture-resolution",
            str(texture_resolution),
            "--remesh_option",
            remesh_option,
        ]

        def _run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

        try:
            proc = await asyncio.to_thread(_run)
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": f"Stable Fast 3D timed out after {timeout} seconds",
            }
        except OSError as exc:
            return {
                "status": "failed",
                "error": f"Stable Fast 3D execution failed: {exc}",
            }

        if proc.returncode != 0:
            return {
                "status": "failed",
                "error": "Stable Fast 3D exited with a non-zero status",
                "returncode": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-8000:],
            }

        model_path = self._latest_glb(out_dir)
        if model_path is None:
            return {
                "status": "failed",
                "error": "Stable Fast 3D completed but did not emit a GLB file",
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-8000:],
            }

        validation = validate_generated_model_file(str(model_path))
        if not validation.get("valid", False):
            try:
                model_path.unlink(missing_ok=True)
            except OSError:
                pass
            return {
                "status": "failed",
                "error": f"Stable Fast 3D model failed validation: {validation.get('error', 'unknown')}",
                "model_path": str(model_path),
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-8000:],
            }

        result: dict = {
            "status": "success",
            "backend": "stable_fast_3d",
            "model_path": str(model_path),
            "stdout": proc.stdout[-4000:],
        }
        if proc.stderr:
            result["warnings"] = [proc.stderr[-4000:]]
        return result
