"""Real-ESRGAN ncnn-vulkan subprocess wrapper for texture upscaling.

Provides upscale_texture (async) and check_esrgan_available helper.
Uses asyncio.to_thread to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path


def check_esrgan_available(esrgan_path: str) -> bool:
    """Check if the Real-ESRGAN binary exists at the given path.

    Args:
        esrgan_path: Full path to the realesrgan-ncnn-vulkan executable.

    Returns:
        True if the file exists, False otherwise.
    """
    return os.path.isfile(esrgan_path)


async def upscale_texture(
    input_path: str,
    scale: int = 4,
    model: str = "realesrgan-x4plus",
    esrgan_path: str | None = None,
    output_path: str | None = None,
    timeout: int = 120,
) -> dict:
    """Upscale a texture image using Real-ESRGAN ncnn-vulkan.

    Args:
        input_path: Path to the input image file.
        scale: Upscale factor (2 or 4).
        model: ESRGAN model name (e.g. "realesrgan-x4plus").
        esrgan_path: Path to realesrgan-ncnn-vulkan binary.
            Defaults to bin/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe.
        output_path: Path for the output file. Auto-generated if None.
        timeout: Maximum seconds to wait for subprocess.

    Returns:
        Dict with input, output, scale, model, success keys.

    Raises:
        FileNotFoundError: If the realesrgan binary does not exist.
    """
    if esrgan_path is None:
        esrgan_path = os.path.join(
            "bin", "realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"
        )

    if not check_esrgan_available(esrgan_path):
        raise FileNotFoundError(
            f"realesrgan-ncnn-vulkan binary not found at: {esrgan_path}. "
            "Download from https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases"
        )

    input_p = Path(input_path)
    if output_path is None:
        output_path = str(
            input_p.parent / f"{input_p.stem}_x{scale}{input_p.suffix}"
        )

    cmd = [
        esrgan_path,
        "-i", str(input_path),
        "-o", output_path,
        "-s", str(scale),
        "-n", model,
        "-f", "png",
    ]

    def _run():
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    try:
        result = await asyncio.to_thread(_run)

        if result.returncode != 0:
            return {
                "input": str(input_path),
                "output": output_path,
                "scale": scale,
                "model": model,
                "success": False,
                "error": result.stderr or f"Exit code {result.returncode}",
            }

        return {
            "input": str(input_path),
            "output": output_path,
            "scale": scale,
            "model": model,
            "success": True,
        }

    except subprocess.TimeoutExpired:
        return {
            "input": str(input_path),
            "output": output_path,
            "scale": scale,
            "model": model,
            "success": False,
            "error": f"Timeout after {timeout}s",
        }
