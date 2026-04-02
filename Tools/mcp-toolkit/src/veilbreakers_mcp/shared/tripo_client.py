"""Tripo3D SDK wrapper for AI 3D model generation.

Provides TripoGenerator with async text-to-model and image-to-model.
Gracefully returns error dict if tripo3d package is not installed.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from veilbreakers_mcp.shared.model_validation import validate_generated_model_file

try:
    import tripo3d  # type: ignore[import-untyped]

    _TRIPO_AVAILABLE = True
except ImportError:
    _TRIPO_AVAILABLE = False


def _create_tripo_client(api_key: str):
    """Create a tripo3d.TripoClient instance. Separated for testability."""
    return tripo3d.TripoClient(api_key=api_key)


async def _download_file(url: str, output_path: str, max_retries: int = 3) -> str:
    """Download a model file from a Tripo3D HTTPS URL to a local path.

    Uses the tripo3d SDK's built-in download_file helper when available.
    Retries with exponential backoff on transient failures.

    Only HTTPS URLs from the Tripo3D CDN are expected.
    """

    def _do_download() -> str:
        if _TRIPO_AVAILABLE and hasattr(tripo3d, "download_file"):
            tripo3d.download_file(url, output_path)
        else:
            raise RuntimeError(
                "tripo3d.download_file is unavailable; refusing to create "
                "an empty placeholder file"
            )
        return output_path

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            downloaded = await asyncio.to_thread(_do_download)
            validation = validate_generated_model_file(downloaded)
            if not validation.get("valid", False):
                try:
                    Path(downloaded).unlink(missing_ok=True)
                except OSError:
                    pass
                raise RuntimeError(
                    f"Downloaded model failed validation: {validation.get('error', 'unknown')}"
                )
            return downloaded
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


class TripoGenerator:
    """Wrapper for Tripo3D API for AI 3D model generation.

    Usage::

        gen = TripoGenerator(api_key="your-key")
        result = await gen.generate_from_text("a wooden barrel", "/output")
        # result: {status, model_path, pbr_model_path, task_id}
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "TRIPO_API_KEY is required. Get one at "
                "https://platform.tripo3d.ai -> Settings -> API Keys"
            )
        self.api_key = api_key

    def close(self) -> None:
        """Compatibility no-op for callers that always close generators."""
        return None

    async def generate_from_text(
        self,
        prompt: str,
        output_dir: str,
        texture: bool = True,
        pbr: bool = True,
        model_version: str = "v3.1-20260211",
        timeout: int = 300,
        polling_interval: float = 3.0,
    ) -> dict:
        """Generate a 3D model from a text prompt via Tripo3D API.

        Args:
            prompt: Text description of the 3D model to generate.
            output_dir: Directory to save downloaded model files.
            texture: Whether to generate textures.
            pbr: Whether to generate PBR materials.
            model_version: Tripo3D model version string.
            timeout: Maximum seconds to wait for task completion.
            polling_interval: Seconds between status polls.

        Returns:
            Dict with status, model_path, pbr_model_path, task_id on success,
            or status="failed"/"unavailable" with error on failure.
        """
        if not _TRIPO_AVAILABLE:
            return {
                "status": "unavailable",
                "error": "tripo3d package not installed. Run: pip install tripo3d",
            }

        last_exc: Exception | None = None
        for attempt in range(3):
            client = _create_tripo_client(self.api_key)
            try:
                raw = client.text_to_model(
                    prompt=prompt,
                    texture=texture,
                    pbr=pbr,
                    model_version=model_version,
                )
                task_id = (await raw) if asyncio.iscoroutine(raw) else raw

                raw2 = client.wait_for_task(
                    task_id,
                    timeout=timeout,
                    polling_interval=polling_interval,
                )
                task_result = (await raw2) if asyncio.iscoroutine(raw2) else raw2

                task_status = getattr(task_result, "status", None) or (
                    task_result.get("status") if isinstance(task_result, dict) else "unknown"
                )
                if task_status != "success":
                    return {
                        "status": "failed",
                        "error": f"Tripo3D task {task_id} ended with status: {task_status}",
                        "task_id": task_id,
                    }

                os.makedirs(output_dir, exist_ok=True)
                result: dict = {
                    "status": "success",
                    "task_id": task_id,
                }

                output = getattr(task_result, "output", None) or (
                    task_result.get("output") if isinstance(task_result, dict) else None
                )
                model_url = getattr(output, "model", None) if output else None
                if model_url:
                    model_path = str(Path(output_dir) / "model.glb")
                    result["model_path"] = await _download_file(model_url, model_path)

                pbr_url = getattr(output, "pbr_model", None) if output else None
                if pbr_url:
                    pbr_path = str(Path(output_dir) / "model_pbr.glb")
                    try:
                        result["pbr_model_path"] = await _download_file(pbr_url, pbr_path)
                    except RuntimeError as exc:
                        result.setdefault("warnings", []).append(
                            f"PBR model unavailable or invalid: {exc}"
                        )

                return result

            except (ConnectionError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"status": "failed", "error": str(exc)}
            except (ValueError, KeyError, RuntimeError) as exc:
                return {"status": "failed", "error": str(exc)}
            finally:
                try:
                    coro = client.close()
                    if asyncio.iscoroutine(coro):
                        await coro
                except (OSError, RuntimeError):
                    pass
        return {"status": "failed", "error": str(last_exc)}

    async def generate_from_image(
        self,
        image_path: str,
        output_dir: str,
        texture: bool = True,
        pbr: bool = True,
        model_version: str = "v3.1-20260211",
        timeout: int = 300,
        polling_interval: float = 3.0,
    ) -> dict:
        """Generate a 3D model from an image via Tripo3D API.

        Args:
            image_path: Path to the source image file.
            output_dir: Directory to save downloaded model files.
            texture: Whether to generate textures.
            pbr: Whether to generate PBR materials.
            model_version: Tripo3D model version string.
            timeout: Maximum seconds to wait for task completion.
            polling_interval: Seconds between status polls.

        Returns:
            Dict with status, model_path, pbr_model_path, task_id on success,
            or status="failed"/"unavailable" with error on failure.
        """
        if not _TRIPO_AVAILABLE:
            return {
                "status": "unavailable",
                "error": "tripo3d package not installed. Run: pip install tripo3d",
            }

        if not os.path.isfile(image_path):
            return {
                "status": "failed",
                "error": f"Image file not found: {image_path}",
            }

        last_exc: Exception | None = None
        for attempt in range(3):
            client = _create_tripo_client(self.api_key)
            try:
                raw = client.image_to_model(
                    image_path=image_path,
                    texture=texture,
                    pbr=pbr,
                    model_version=model_version,
                )
                task_id = (await raw) if asyncio.iscoroutine(raw) else raw

                raw2 = client.wait_for_task(
                    task_id,
                    timeout=timeout,
                    polling_interval=polling_interval,
                )
                task_result = (await raw2) if asyncio.iscoroutine(raw2) else raw2

                task_status = getattr(task_result, "status", None) or (
                    task_result.get("status") if isinstance(task_result, dict) else "unknown"
                )
                if task_status != "success":
                    return {
                        "status": "failed",
                        "error": f"Tripo3D task {task_id} ended with status: {task_status}",
                        "task_id": task_id,
                    }

                os.makedirs(output_dir, exist_ok=True)
                result: dict = {
                    "status": "success",
                    "task_id": task_id,
                }

                output = getattr(task_result, "output", None) or (
                    task_result.get("output") if isinstance(task_result, dict) else None
                )
                model_url = getattr(output, "model", None) if output else None
                if model_url:
                    model_path = str(Path(output_dir) / "model.glb")
                    result["model_path"] = await _download_file(model_url, model_path)

                pbr_url = getattr(output, "pbr_model", None) if output else None
                if pbr_url:
                    pbr_path = str(Path(output_dir) / "model_pbr.glb")
                    try:
                        result["pbr_model_path"] = await _download_file(pbr_url, pbr_path)
                    except RuntimeError as exc:
                        result.setdefault("warnings", []).append(
                            f"PBR model unavailable or invalid: {exc}"
                        )

                return result

            except (ConnectionError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {"status": "failed", "error": str(exc)}
            except (ValueError, KeyError, RuntimeError) as exc:
                return {"status": "failed", "error": str(exc)}
            finally:
                try:
                    coro = client.close()
                    if asyncio.iscoroutine(coro):
                        await coro
                except (OSError, ConnectionError):
                    pass
        return {"status": "failed", "error": str(last_exc)}
