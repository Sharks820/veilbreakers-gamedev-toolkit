"""Pipeline orchestrator for batch asset processing.

Orchestrates repair, UV unwrap, texture, LOD generation, and export
validation in sequence for game assets via the Blender TCP connection.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
    from veilbreakers_mcp.shared.blender_client import BlenderConnection
    from veilbreakers_mcp.shared.config import Settings


class PipelineRunner:
    """Orchestrates asset pipeline steps via Blender connection.

    Usage::

        runner = PipelineRunner(blender_conn, settings)
        result = await runner.cleanup_ai_model("ImportedModel", poly_budget=50000)
    """

    def __init__(self, blender: BlenderConnection, settings: Settings):
        self.blender = blender
        self.settings = settings

    async def cleanup_ai_model(
        self, object_name: str, poly_budget: int = 50000
    ) -> dict:
        """Orchestrate repair -> UV -> material pipeline for an AI-generated model.

        Steps:
        1. Auto-repair mesh (fix non-manifold, remove doubles)
        2. Check game-readiness (poly budget compliance)
        3. Retopologize if over budget
        4. UV unwrap via xatlas
        5. Create PBR material

        Args:
            object_name: Name of the Blender object to process.
            poly_budget: Maximum triangle count target.

        Returns:
            Dict with per-step results and overall status.
        """
        steps_completed: list[str] = []
        results: dict = {"object_name": object_name, "steps": {}}

        try:
            # Step 1: Auto-repair
            repair_result = await self.blender.send_command(
                "mesh_auto_repair", {"object_name": object_name}
            )
            results["steps"]["repair"] = repair_result
            steps_completed.append("repair")

            # Step 2: Game-readiness check
            check_result = await self.blender.send_command(
                "mesh_check_game_ready",
                {"object_name": object_name, "poly_budget": poly_budget},
            )
            results["steps"]["game_ready_check"] = check_result
            steps_completed.append("game_ready_check")

            # Step 3: Retopologize if over budget
            if not check_result.get("game_ready", True):
                checks = check_result.get("checks", {})
                poly_check = checks.get("poly_budget", {})
                if not poly_check.get("passed", True):
                    retopo_result = await self.blender.send_command(
                        "mesh_retopologize",
                        {"object_name": object_name, "target_faces": poly_budget},
                    )
                    results["steps"]["retopologize"] = retopo_result
                    steps_completed.append("retopologize")

            # Step 4: UV unwrap
            uv_result = await self.blender.send_command(
                "uv_unwrap_xatlas", {"object_name": object_name}
            )
            results["steps"]["uv_unwrap"] = uv_result
            steps_completed.append("uv_unwrap")

            # Step 5: Create PBR material
            pbr_result = await self.blender.send_command(
                "texture_create_pbr",
                {"name": object_name, "object_name": object_name},
            )
            results["steps"]["create_pbr"] = pbr_result
            steps_completed.append("create_pbr")

            results["status"] = "success"
            results["steps_completed"] = steps_completed

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            results["status"] = "failed"
            results["error"] = str(exc)
            results["steps_completed"] = steps_completed

        return results

    async def validate_export(self, filepath: str) -> dict:
        """Validate an exported FBX or GLB file for game-engine compatibility.

        Checks:
        - File exists and is non-empty
        - Format detection (FBX vs GLB)
        - For GLB: parses JSON chunk for scene/node/mesh/material counts
        - For FBX: checks header magic bytes

        Args:
            filepath: Path to the exported file.

        Returns:
            Dict with valid, filepath, format, and checks sub-dict.
        """
        result: dict = {
            "valid": False,
            "filepath": filepath,
            "format": "unknown",
            "checks": {},
        }

        if not os.path.isfile(filepath):
            result["error"] = "File not found"
            return result

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            result["error"] = "File is empty"
            return result

        result["checks"]["file_size"] = {"value": file_size, "passed": True}

        ext = Path(filepath).suffix.lower()

        if ext == ".glb":
            result["format"] = "glb"
            result = self._validate_glb(filepath, result)
        elif ext == ".fbx":
            result["format"] = "fbx"
            result = self._validate_fbx(filepath, result)
        else:
            result["error"] = f"Unsupported format: {ext}"
            return result

        # Overall valid if all checks passed
        all_passed = all(
            c.get("passed", False) for c in result["checks"].values()
        )
        result["valid"] = all_passed

        return result

    @staticmethod
    def _validate_glb(filepath: str, result: dict) -> dict:
        """Validate a GLB file by parsing the JSON chunk."""
        try:
            with open(filepath, "rb") as f:
                # GLB header: magic(4) + version(4) + length(4)
                header = f.read(12)
                if len(header) < 12:
                    result["checks"]["header"] = {
                        "passed": False,
                        "error": "File too small for GLB header",
                    }
                    return result

                magic = struct.unpack("<I", header[0:4])[0]
                if magic != 0x46546C67:  # "glTF"
                    result["checks"]["header"] = {
                        "passed": False,
                        "error": "Invalid GLB magic bytes",
                    }
                    return result

                version = struct.unpack("<I", header[4:8])[0]
                result["checks"]["header"] = {
                    "passed": True,
                    "version": version,
                }

                # JSON chunk: length(4) + type(4) + data
                chunk_header = f.read(8)
                if len(chunk_header) < 8:
                    result["checks"]["json_chunk"] = {
                        "passed": False,
                        "error": "Missing JSON chunk",
                    }
                    return result

                chunk_length = struct.unpack("<I", chunk_header[0:4])[0]
                chunk_type = struct.unpack("<I", chunk_header[4:8])[0]

                if chunk_type != 0x4E4F534A:  # "JSON"
                    result["checks"]["json_chunk"] = {
                        "passed": False,
                        "error": "First chunk is not JSON",
                    }
                    return result

                json_data = f.read(chunk_length)
                gltf = json.loads(json_data)

                scenes = len(gltf.get("scenes", []))
                nodes = len(gltf.get("nodes", []))
                meshes = len(gltf.get("meshes", []))
                materials = len(gltf.get("materials", []))

                result["checks"]["json_chunk"] = {
                    "passed": True,
                    "scenes": scenes,
                    "nodes": nodes,
                    "meshes": meshes,
                    "materials": materials,
                }

                result["checks"]["materials"] = {
                    "passed": materials > 0,
                    "count": materials,
                }

        except (OSError, json.JSONDecodeError, ValueError, KeyError, struct.error) as exc:
            result["checks"]["parse_error"] = {
                "passed": False,
                "error": str(exc),
            }

        return result

    @staticmethod
    def _validate_fbx(filepath: str, result: dict) -> dict:
        """Validate an FBX file by checking header magic bytes."""
        try:
            with open(filepath, "rb") as f:
                header = f.read(23)
                # FBX binary header: "Kaydara FBX Binary  \x00"
                if header[:20] == b"Kaydara FBX Binary  ":
                    result["checks"]["header"] = {
                        "passed": True,
                        "format": "binary",
                    }
                else:
                    # Could be ASCII FBX
                    f.seek(0)
                    first_line = f.readline().decode("ascii", errors="ignore")
                    if "FBX" in first_line.upper():
                        result["checks"]["header"] = {
                            "passed": True,
                            "format": "ascii",
                        }
                    else:
                        result["checks"]["header"] = {
                            "passed": False,
                            "error": "Not a valid FBX file",
                        }
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            result["checks"]["parse_error"] = {
                "passed": False,
                "error": str(exc),
            }

        return result

    async def batch_process(
        self,
        object_names: list[str],
        steps: list[str] | None = None,
    ) -> dict:
        """Run pipeline for each object sequentially.

        Args:
            object_names: List of Blender object names to process.
            steps: Pipeline steps to run. Default:
                ["repair", "uv_unwrap", "create_pbr", "generate_lods", "export"].

        Returns:
            Dict with total, completed, failed counts and per-object results.
        """
        if steps is None:
            steps = ["repair", "uv_unwrap", "create_pbr", "generate_lods", "export"]

        results: list[dict] = []
        completed = 0
        failed = 0

        step_command_map = {
            "repair": ("mesh_auto_repair", lambda name: {"object_name": name}),
            "uv_unwrap": ("uv_unwrap_xatlas", lambda name: {"object_name": name}),
            "create_pbr": (
                "texture_create_pbr",
                lambda name: {"name": name, "object_name": name},
            ),
            "generate_lods": (
                "pipeline_generate_lods",
                lambda name: {"object_name": name},
            ),
            "export": (
                "export_gltf",
                lambda name: {"filepath": f"{name}.glb", "selected_only": True},
            ),
        }

        for obj_name in object_names:
            obj_result: dict = {
                "object_name": obj_name,
                "status": "success",
                "steps_completed": [],
            }

            for step in steps:
                mapping = step_command_map.get(step)
                if mapping is None:
                    continue

                cmd, params_fn = mapping
                try:
                    await self.blender.send_command(cmd, params_fn(obj_name))
                    obj_result["steps_completed"].append(step)
                except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                    obj_result["status"] = "failed"
                    obj_result["error"] = f"Step '{step}' failed: {exc}"
                    break

            if obj_result["status"] == "success":
                completed += 1
            else:
                failed += 1

            results.append(obj_result)

        return {
            "total": len(object_names),
            "completed": completed,
            "failed": failed,
            "results": results,
        }

    async def tag_metadata(
        self,
        asset_id: str,
        output_path: str,
        catalog: AssetCatalog,
    ) -> dict:
        """Export JSON sidecar metadata for an asset.

        Args:
            asset_id: UUID of the asset in the catalog.
            output_path: Path for the output JSON file.
            catalog: AssetCatalog instance.

        Returns:
            Dict from catalog.export_metadata().
        """
        return catalog.export_metadata(asset_id, output_path)
