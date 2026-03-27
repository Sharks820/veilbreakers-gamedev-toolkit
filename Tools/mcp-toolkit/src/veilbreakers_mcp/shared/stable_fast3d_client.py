"""Stable Fast 3D local generator wrapper.

This wrapper keeps the local SF3D path conservative for 8 GB GPUs:
- safe default texture resolution
- CPU/auto device control
- explicit subprocess execution
- hard validation of generated GLB output
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from veilbreakers_mcp.shared.model_validation import validate_generated_model_file


class StableFast3DGenerator:
    """Thin async wrapper around the official Stable Fast 3D repo."""

    def __init__(self, repo_path: str, python_executable: str | None = None):
        self.repo_path = Path(repo_path).expanduser().resolve()
        self.python_executable = python_executable or sys.executable

    async def generate_from_image(
        self,
        *,
        image_path: str,
        output_dir: str,
        texture_resolution: int = 512,
        remesh_option: str = "triangle",
        target_vertex_count: int = 20000,
        device: str = "auto",
        timeout: int = 300,
    ) -> dict:
        image = Path(image_path).expanduser().resolve()
        out_dir = Path(output_dir).expanduser().resolve()
        run_py = self.repo_path / "run.py"

        if not self.repo_path.is_dir():
            return {"status": "failed", "error": f"Stable Fast 3D repo not found: {self.repo_path}"}
        if not run_py.is_file():
            return {"status": "failed", "error": f"Stable Fast 3D entrypoint not found: {run_py}"}
        if not image.is_file():
            return {"status": "failed", "error": f"Image file not found: {image}"}

        safe_texture_resolution = max(256, min(int(texture_resolution or 512), 1024))
        safe_remesh_option = str(remesh_option or "triangle").strip().lower()
        if safe_remesh_option not in {"none", "triangle", "quad"}:
            safe_remesh_option = "triangle"
        safe_vertex_count = max(-1, int(target_vertex_count or 20000))
        safe_device = str(device or "auto").strip().lower()
        if safe_device not in {"auto", "cuda", "cpu"}:
            safe_device = "auto"

        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.python_executable,
            str(run_py),
            str(image),
            "--output-dir",
            str(out_dir),
            "--texture-resolution",
            str(safe_texture_resolution),
            "--remesh_option",
            safe_remesh_option,
            "--target_vertex_count",
            str(safe_vertex_count),
        ]
        if safe_device != "auto":
            cmd.extend(["--device", safe_device])

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.repo_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"status": "failed", "error": f"Stable Fast 3D timed out after {timeout}s"}
        except OSError as exc:
            return {"status": "failed", "error": f"Stable Fast 3D launch failed: {exc}"}

        stdout = stdout_b.decode("utf-8", errors="ignore")
        stderr = stderr_b.decode("utf-8", errors="ignore")

        if proc.returncode != 0:
            combined = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part).strip()
            return {
                "status": "failed",
                "error": combined or f"Stable Fast 3D exited with code {proc.returncode}",
                "backend": "stable_fast_3d",
                "settings": {
                    "texture_resolution": safe_texture_resolution,
                    "remesh_option": safe_remesh_option,
                    "target_vertex_count": safe_vertex_count,
                    "device": safe_device,
                },
            }

        mesh_path = out_dir / "0" / "mesh.glb"
        validation = validate_generated_model_file(str(mesh_path))
        if not validation.get("valid", False):
            return {
                "status": "failed",
                "error": f"Stable Fast 3D output failed validation: {validation.get('error', 'invalid model')}",
                "backend": "stable_fast_3d",
                "validation": validation,
                "settings": {
                    "texture_resolution": safe_texture_resolution,
                    "remesh_option": safe_remesh_option,
                    "target_vertex_count": safe_vertex_count,
                    "device": safe_device,
                },
            }

        warnings: list[str] = []
        if safe_texture_resolution >= 1024:
            warnings.append("1024 texture resolution is near the practical ceiling for an 8 GB card. Prefer 512 during iteration.")
        if safe_remesh_option == "quad":
            warnings.append("Quad remesh adds CPU overhead. Use triangle for safer iteration on this machine.")

        return {
            "status": "success",
            "backend": "stable_fast_3d",
            "model_path": str(mesh_path),
            "output_dir": str(out_dir),
            "validation": validation,
            "settings": {
                "texture_resolution": safe_texture_resolution,
                "remesh_option": safe_remesh_option,
                "target_vertex_count": safe_vertex_count,
                "device": safe_device,
            },
            "warnings": warnings,
            "stdout_tail": stdout[-1200:] if stdout else "",
        }
