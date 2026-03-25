"""Pipeline orchestrator for batch asset processing.

Orchestrates repair, UV unwrap, texture, LOD generation, and export
validation in sequence for game assets via the Blender TCP connection.

Also provides ``full_asset_pipeline()`` for end-to-end production:
import -> cleanup -> smart material -> weathering -> quality gate ->
rig -> animate -> LOD -> export -> validate.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from veilbreakers_mcp.shared.blender_client import BlenderCommandError
from veilbreakers_mcp.shared.model_validation import validate_generated_model_file
from veilbreakers_mcp.shared.visual_validation import validate_render_screens

if TYPE_CHECKING:
    from veilbreakers_mcp.shared.asset_catalog import AssetCatalog
    from veilbreakers_mcp.shared.blender_client import BlenderConnection
    from veilbreakers_mcp.shared.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default smart material presets per asset type.
MATERIAL_PRESETS: dict[str, str] = {
    "prop": "old_wood",
    "character": "worn_leather",
    "creature": "chitin",
    "weapon": "rusted_armor",
    "building": "dungeon_stone",
    "vegetation": "bark",
}

#: Auto-detected rig template per asset type.
RIG_TEMPLATES: dict[str, str] = {
    "character": "humanoid",
    "creature": "quadruped",
}

#: Recognised animation names and the Blender command + extra params for each.
ANIMATION_COMMANDS: dict[str, tuple[str, dict]] = {
    "walk": ("anim_generate_walk", {"speed": "walk"}),
    "run": ("anim_generate_walk", {"speed": "run"}),
    "idle": ("anim_generate_idle", {}),
    "attack": ("anim_generate_attack", {}),
    "fly": ("anim_generate_fly", {}),
    "death": ("anim_generate_reaction", {"reaction_type": "death"}),
    "hit": ("anim_generate_reaction", {"reaction_type": "hit"}),
    "spawn": ("anim_generate_reaction", {"reaction_type": "spawn"}),
}

#: Asset types that require rigging before animation.
RIGGABLE_TYPES: frozenset[str] = frozenset({"character", "creature"})

#: File extensions recognised as importable 3D files.
IMPORT_EXTENSIONS: frozenset[str] = frozenset({".glb", ".gltf", ".fbx", ".obj"})


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
        self, object_name: str, poly_budget: int = 50000,
        enhance_profile: str = "prop",
        skip_enhance: bool = False,
    ) -> dict:
        """Orchestrate repair -> enhance -> UV -> material pipeline.

        Steps:
        1. Auto-repair mesh (fix non-manifold, remove doubles)
        2. Check game-readiness (poly budget compliance)
        3. Retopologize if over budget
        4. Geometry enhancement (SubD, bevel, weighted normals, smooth shading)
        5. UV unwrap via xatlas
        6. Create PBR material

        Args:
            object_name: Name of the Blender object to process.
            poly_budget: Maximum triangle count target.
            enhance_profile: Enhancement profile preset (weapon, architecture,
                organic, prop, character, vegetation). Default "prop".
            skip_enhance: If True, skip the geometry enhancement step.

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

            # Step 4: Geometry enhancement (AAA quality)
            if not skip_enhance:
                enhance_result = await self.blender.send_command(
                    "mesh_enhance_geometry",
                    {
                        "object_name": object_name,
                        "profile": enhance_profile,
                        "apply_modifiers": True,
                    },
                )
                results["steps"]["enhance_geometry"] = enhance_result
                steps_completed.append("enhance_geometry")

            # Step 5: UV unwrap
            uv_result = await self.blender.send_command(
                "uv_unwrap_xatlas", {"object_name": object_name}
            )
            results["steps"]["uv_unwrap"] = uv_result
            steps_completed.append("uv_unwrap")

            # Step 6: Create PBR material
            pbr_result = await self.blender.send_command(
                "texture_create_pbr",
                {"name": object_name, "object_name": object_name},
            )
            results["steps"]["create_pbr"] = pbr_result
            steps_completed.append("create_pbr")

            results["status"] = "success"
            results["steps_completed"] = steps_completed

        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, BlenderCommandError) as exc:
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

    async def validate_visual_quality(
        self,
        object_name: str,
        min_score: float = 55.0,
        angles: list[list[float]] | None = None,
    ) -> dict:
        """Render a contact sheet and reject visually weak outputs."""
        render_angles = angles or [
            [0, 12],
            [90, 12],
            [180, 12],
            [270, 12],
            [45, 28],
            [315, 28],
        ]
        result: dict = {
            "valid": False,
            "object_name": object_name,
            "min_score": float(min_score),
            "render": {},
            "validation": {},
        }

        try:
            render_result = await self.blender.send_command(
                "render_contact_sheet",
                {
                    "object_name": object_name,
                    "angles": render_angles,
                    "resolution": [512, 512],
                    "skip_beauty": False,
                },
            )
            result["render"] = render_result
            paths = render_result.get("paths", []) if isinstance(render_result, dict) else []
            validation = validate_render_screens(paths, min_score=min_score)
            result["validation"] = validation
            result["valid"] = validation.get("valid", False)
            if not result["valid"]:
                result["error"] = "Visual quality gate failed"
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            BlenderCommandError,
        ) as exc:
            result["error"] = str(exc)
            result["validation"] = {"valid": False, "issues": [str(exc)]}

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

                mat_check: dict = {"passed": True, "count": materials}
                if materials == 0:
                    mat_check["warning"] = "no materials"
                result["checks"]["materials"] = mat_check

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
                lambda name: {"filepath": str(Path(tempfile.gettempdir()) / f"{name}.glb"), "selected_only": True},
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
                except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, BlenderCommandError) as exc:
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

    async def blender_to_unity_pipeline(
        self,
        object_name: str,
        asset_type: str = "prop",
        export_format: str = "fbx",
        unity_project_path: str = "",
    ) -> dict:
        """Orchestrate the full Blender-side export pipeline for Unity import.

        Chains existing Blender operations to prepare an asset for Unity:
        1. Game-readiness check (mesh analysis + poly budget)
        2. Auto-repair if needed (fix non-manifold, remove doubles)
        3. UV analysis + unwrap if needed
        4. Export FBX to Unity project Assets folder

        This is a Python helper that chains existing MCP tool calls -- NOT a new
        MCP tool itself. It returns a dict suitable for passing to the Unity-side
        bridge script.

        Args:
            object_name: Name of the Blender object to process.
            asset_type: hero, monster, weapon, prop, or environment.
            export_format: Export format (fbx or gltf). Default fbx.
            unity_project_path: Absolute path to Unity project root.
                If empty, exports to a temp directory.

        Returns:
            Dict with fbx_path, mesh_grade, poly_count, uv_coverage, warnings,
            and per-step results.
        """
        poly_budgets = {
            "hero": 65000,
            "monster": 50000,
            "weapon": 15000,
            "prop": 8000,
            "environment": 100000,
        }
        poly_budget = poly_budgets.get(asset_type, 50000)

        result: dict = {
            "object_name": object_name,
            "asset_type": asset_type,
            "fbx_path": "",
            "mesh_grade": "",
            "poly_count": 0,
            "uv_coverage": 0.0,
            "warnings": [],
            "steps": {},
            "status": "pending",
        }

        try:
            # ----- Step 1: Game-readiness check -----
            game_check = await self.blender.send_command(
                "mesh_check_game_ready",
                {"object_name": object_name, "poly_budget": poly_budget},
            )
            result["steps"]["game_check"] = game_check
            result["mesh_grade"] = game_check.get("grade", "")
            checks = game_check.get("checks", {})
            poly_info = checks.get("poly_budget", {})
            result["poly_count"] = poly_info.get("value", 0)

            # ----- Step 2: Auto-repair if needed -----
            needs_repair = not game_check.get("game_ready", True)
            if needs_repair:
                repair_result = await self.blender.send_command(
                    "mesh_auto_repair", {"object_name": object_name}
                )
                result["steps"]["repair"] = repair_result
                result["warnings"].append(
                    "Mesh required auto-repair before export"
                )

                # Re-check after repair if poly budget was exceeded
                if not poly_info.get("passed", True):
                    retopo_result = await self.blender.send_command(
                        "mesh_retopologize",
                        {
                            "object_name": object_name,
                            "target_faces": poly_budget,
                        },
                    )
                    result["steps"]["retopologize"] = retopo_result
                    result["warnings"].append(
                        f"Retopologized to meet {poly_budget} poly budget"
                    )

            # ----- Step 3: UV analysis + unwrap -----
            uv_analysis = await self.blender.send_command(
                "uv_analyze", {"object_name": object_name}
            )
            result["steps"]["uv_analyze"] = uv_analysis
            result["uv_coverage"] = uv_analysis.get("coverage", 0.0)

            # Unwrap if coverage is poor or no UVs exist
            needs_unwrap = (
                uv_analysis.get("coverage", 0.0) < 0.1
                or uv_analysis.get("uv_layers", 0) == 0
            )
            if needs_unwrap:
                unwrap_result = await self.blender.send_command(
                    "uv_unwrap_xatlas", {"object_name": object_name}
                )
                result["steps"]["uv_unwrap"] = unwrap_result
                result["warnings"].append("UV unwrap was required")
                # Update coverage
                result["uv_coverage"] = unwrap_result.get("coverage", 0.0)

            # ----- Step 4: Export -----
            if unity_project_path:
                export_dir = (
                    Path(unity_project_path) / "Assets" / "Models"
                )
                export_dir.mkdir(parents=True, exist_ok=True)
            else:
                export_dir = Path(".")

            ext = "fbx" if export_format == "fbx" else "glb"
            export_path = str(export_dir / f"{object_name}.{ext}")

            export_cmd = (
                "export_fbx" if export_format == "fbx" else "export_gltf"
            )
            export_result = await self.blender.send_command(
                export_cmd,
                {
                    "filepath": export_path,
                    "selected_only": False,
                    "apply_modifiers": True,
                },
            )
            result["steps"]["export"] = export_result
            result["fbx_path"] = export_path
            result["status"] = "success"

        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            BlenderCommandError,
        ) as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            result["warnings"].append(f"Pipeline failed: {exc}")

        return result

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

    # ------------------------------------------------------------------
    # Full production pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_asset_type(object_name: str, mesh_stats: dict) -> str:
        """Auto-detect asset type from mesh characteristics.

        Heuristics (evaluated in order):
        - High vertex count + bounding box roughly humanoid proportions
          -> ``'character'``
        - Bounding box height >> width AND width/depth small
          -> ``'weapon'``
        - Large footprint (X*Y) + many faces + openings (non-manifold edges)
          -> ``'building'``
        - Very high vertex count + non-humanoid proportions
          -> ``'creature'``
        - Low vertex count (< 2000) and small bounding box
          -> ``'vegetation'`` if name hints, else ``'prop'``
        - Default fallback -> ``'prop'``

        Args:
            object_name: The Blender object name (used for keyword hints).
            mesh_stats: Dict with ``vertex_count``, ``face_count``, and
                optionally ``dimensions`` ``[x, y, z]`` and
                ``non_manifold_edges``.

        Returns:
            One of: ``'character'``, ``'creature'``, ``'weapon'``,
            ``'building'``, ``'vegetation'``, or ``'prop'``.
        """
        verts = mesh_stats.get("vertex_count", 0)
        dims = mesh_stats.get("dimensions", [1.0, 1.0, 1.0])
        if len(dims) < 3:
            dims = [1.0, 1.0, 1.0]
        dx, dy, dz = float(dims[0]), float(dims[1]), float(dims[2])
        non_manifold = mesh_stats.get("non_manifold_edges", 0)
        name_lower = object_name.lower()

        # Compute height (longest axis) and width (shortest axis)
        sorted_dims = sorted([dx, dy, dz])
        height = sorted_dims[2]  # largest
        width = sorted_dims[0]   # smallest
        aspect = height / max(width, 0.001)

        # --- Keyword-based detection (high priority) ---

        # Vegetation keywords (check early -- vegetation can be any shape)
        veg_keywords = ("tree", "bush", "grass", "plant", "leaf", "vine",
                        "flower", "fern", "shrub", "moss")
        if any(kw in name_lower for kw in veg_keywords):
            return "vegetation"

        # Character keywords (high-vert bipeds)
        char_keywords = ("character", "human", "hero", "npc", "player",
                         "warrior", "mage", "knight")
        if verts > 5000 and any(kw in name_lower for kw in char_keywords):
            return "character"

        # Creature keywords
        creature_keywords = ("creature", "monster", "beast", "demon",
                             "dragon", "spider", "wolf", "skeleton")
        if verts > 5000 and any(kw in name_lower for kw in creature_keywords):
            return "creature"

        # --- Geometry-based detection ---

        # Building: large footprint with many non-manifold edges (openings)
        footprint = sorted_dims[1] * sorted_dims[2]  # two largest dims
        if footprint > 25.0 and verts > 5000 and non_manifold > 10:
            return "building"

        # Weapon: elongated and thin
        if aspect > 4.0 and verts < 15000:
            return "weapon"

        # Character: humanoid proportions (tall, narrow, high verts)
        # Use height / median_dim for a more forgiving aspect ratio
        median_dim = sorted_dims[1]
        humanoid_aspect = height / max(median_dim, 0.001)
        if 1.4 < humanoid_aspect < 5.0 and verts > 8000:
            # Ambiguous high-vert humanoid -> character
            if verts > 20000:
                return "character"

        # Creature: non-humanoid high vert count
        if verts > 10000 and (aspect > 3.5 or aspect < 1.0):
            return "creature"

        return "prop"

    async def _run_step(
        self,
        step_name: str,
        command: str,
        params: dict,
        results: dict,
        steps_completed: list[str],
    ) -> dict:
        """Execute a single pipeline step with error capture.

        Returns the command result on success, or ``None`` on failure
        (with the error recorded in *results*).
        """
        try:
            step_result = await self.blender.send_command(command, params)
            results["steps"][step_name] = step_result
            steps_completed.append(step_name)
            return step_result
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            BlenderCommandError,
        ) as exc:
            results["steps"][step_name] = {"status": "failed", "error": str(exc)}
            results["warnings"].append(f"Step '{step_name}' failed: {exc}")
            logger.warning("Pipeline step '%s' failed: %s", step_name, exc)
            return None

    async def full_asset_pipeline(
        self,
        object_name: str,
        asset_type: str = "prop",
        poly_budget: int = 50000,
        material_preset: str = "auto",
        weathering_preset: str = "medium",
        rig_template: str = "auto",
        animations: list[str] | None = None,
        lod_count: int = 3,
        visual_gate: bool = True,
        visual_min_score: float = 55.0,
        export_format: str = "fbx",
        export_dir: str = ".",
    ) -> dict:
        """Run the complete production pipeline on a Blender object.

        Steps executed in order:
        1. **Import** -- if *object_name* is a file path (.glb/.fbx/.obj),
           import it into Blender first.
        2. **Cleanup** -- repair, game check, retopo, UV, PBR via
           :meth:`cleanup_ai_model`.
        3. **Smart material** -- apply a type-appropriate procedural material.
        4. **Weathering** -- apply the selected weathering preset.
        5. **Quality gate** -- autonomous refine loop (max 3 iterations).
        6. **Rig** -- apply rig template + auto-weight (character/creature only).
        7. **Animate** -- generate requested animation clips.
        8. **LODs** -- generate LOD chain.
        9. **Visual gate** -- render contact-sheet screenshots and reject
           weak outputs before export.
        10. **Export** -- write FBX or glTF to *export_dir*.
        11. **Validate** -- run export validation on the output file.

        Each step records its result.  If a non-critical step fails the
        pipeline continues with a warning; critical failures (import,
        cleanup) abort early.

        Args:
            object_name: Blender object name **or** file path to import.
            asset_type: ``prop``, ``character``, ``creature``, ``weapon``,
                ``building``, or ``vegetation``.
            poly_budget: Maximum triangle count for quality gate.
            material_preset: Smart material name or ``'auto'`` to pick by
                asset_type.
            weathering_preset: ``none``, ``light``, ``medium``, ``heavy``,
                or ``ancient``.
            rig_template: Rig template name or ``'auto'`` for type-based
                default.
            animations: List of animation names to generate (e.g.
                ``['idle', 'walk', 'attack']``).
            lod_count: Number of LOD levels to generate.
            export_format: ``'fbx'`` or ``'gltf'``.
            export_dir: Directory for the exported file.

        Returns:
            Dict with ``status``, ``object_name``, ``export_path``,
            ``steps_completed``, ``steps`` (per-step results), and
            ``warnings``.
        """
        steps_completed: list[str] = []
        results: dict = {
            "object_name": object_name,
            "asset_type": asset_type,
            "export_path": "",
            "steps": {},
            "steps_completed": steps_completed,
            "warnings": [],
            "status": "pending",
        }

        # Resolve the working object name (may change after import)
        name = object_name

        try:
            # ----- Step 1: Import (if file path) -----
            ext = Path(object_name).suffix.lower()
            if ext in IMPORT_EXTENSIONS:
                import_ops = {
                    ".glb": "import_scene.gltf",
                    ".gltf": "import_scene.gltf",
                    ".fbx": "import_scene.fbx",
                    ".obj": "wm.obj_import",
                }
                op = import_ops.get(ext, "import_scene.gltf")
                # Normalise path separators for Blender (always forward slashes)
                safe_path = object_name.replace("\\", "/")
                import_code = (
                    f'_pre = set(o.name for o in bpy.data.objects)\n'
                    f'bpy.ops.{op}(filepath="{safe_path}")\n'
                    f'_new = [o.name for o in bpy.data.objects if o.name not in _pre and o.type == "MESH"]\n'
                    f'_new[0] if _new else (bpy.context.active_object.name if bpy.context.active_object else "")'
                )
                import_result = await self._run_step(
                    "import", "execute_code", {"code": import_code},
                    results, steps_completed,
                )
                if import_result is None:
                    results["status"] = "failed"
                    results["error"] = "Import failed -- cannot continue"
                    return results
                _imported_name = ""
                if isinstance(import_result, dict):
                    _imported_name = str(import_result.get("result", "")).strip("'\" ")
                if not _imported_name:
                    _imported_name = Path(object_name).stem
                name = _imported_name
                results["object_name"] = name

            # ----- Step 2: Cleanup (repair -> enhance -> UV -> PBR) -----
            # Map asset_type to enhancement profile for AAA geometry quality
            _enhance_map = {
                "prop": "prop",
                "weapon": "weapon",
                "character": "character",
                "creature": "organic",
                "building": "architecture",
                "environment": "architecture",
                "vegetation": "vegetation",
            }
            _enhance_profile = _enhance_map.get(asset_type, "prop")
            cleanup_result = await self.cleanup_ai_model(
                name, poly_budget,
                enhance_profile=_enhance_profile,
            )
            results["steps"]["cleanup"] = cleanup_result
            if cleanup_result.get("status") == "failed":
                results["status"] = "failed"
                results["error"] = (
                    f"Cleanup failed: {cleanup_result.get('error', 'unknown')}"
                )
                results["steps_completed"] = steps_completed
                return results
            steps_completed.append("cleanup")

            # ----- Step 3: Smart material -----
            mat_name = material_preset
            if mat_name == "auto":
                mat_name = MATERIAL_PRESETS.get(asset_type, "old_wood")
            await self._run_step(
                "smart_material",
                "material_create_procedural",
                {"object_name": name, "preset": mat_name},
                results,
                steps_completed,
            )

            # ----- Step 4: Weathering -----
            if weathering_preset != "none":
                await self._run_step(
                    "weathering",
                    "weathering_apply",
                    {"object_name": name, "preset": weathering_preset},
                    results,
                    steps_completed,
                )

            # ----- Step 5: Quality gate -----
            await self._run_step(
                "quality_gate",
                "autonomous_refine",
                {
                    "object_name": name,
                    "max_iterations": 3,
                    "quality_targets": {
                        "max_poly_count": poly_budget,
                        "no_non_manifold": True,
                    },
                },
                results,
                steps_completed,
            )

            # ----- Step 6: Rig (character / creature only) -----
            if asset_type in RIGGABLE_TYPES:
                template = rig_template
                if template == "auto":
                    template = RIG_TEMPLATES.get(asset_type, "humanoid")
                rig_result = await self._run_step(
                    "rig_template",
                    "rig_apply_template",
                    {"object_name": name, "template": template},
                    results,
                    steps_completed,
                )
                if rig_result is not None:
                    await self._run_step(
                        "rig_auto_weight",
                        "rig_auto_weight",
                        {"object_name": name},
                        results,
                        steps_completed,
                    )

            # ----- Step 7: Animate -----
            if animations:
                anim_results: dict = {}
                for anim_name in animations:
                    cmd_info = ANIMATION_COMMANDS.get(anim_name)
                    if cmd_info is None:
                        results["warnings"].append(
                            f"Unknown animation '{anim_name}' -- skipped"
                        )
                        continue
                    cmd, extra_params = cmd_info
                    params = {"object_name": name, **extra_params}
                    anim_step = await self._run_step(
                        f"anim_{anim_name}",
                        cmd,
                        params,
                        results,
                        steps_completed,
                    )
                    anim_results[anim_name] = anim_step
                results["steps"]["animations"] = anim_results

            # ----- Step 8: LODs -----
            await self._run_step(
                "lod_generation",
                "pipeline_generate_lods",
                {"object_name": name, "lod_count": lod_count},
                results,
                steps_completed,
            )

            # ----- Step 9: Visual gate -----
            if visual_gate:
                visual_result = await self.validate_visual_quality(
                    name,
                    min_score=visual_min_score,
                )
                results["steps"]["visual_gate"] = visual_result
                steps_completed.append("visual_gate")
                if not visual_result.get("valid", False):
                    results["status"] = "failed"
                    results["error"] = (
                        f"Visual quality gate failed: {visual_result.get('error', 'low score')}"
                    )
                    results["steps_completed"] = steps_completed
                    return results

            # ----- Step 10: Export -----
            ext_out = "fbx" if export_format == "fbx" else "glb"
            export_path = str(Path(export_dir) / f"{name}.{ext_out}")
            export_cmd = "export_fbx" if export_format == "fbx" else "export_gltf"
            export_result = await self._run_step(
                "export",
                export_cmd,
                {
                    "filepath": export_path,
                    "selected_only": True,
                    "apply_modifiers": True,
                },
                results,
                steps_completed,
            )
            if export_result is not None:
                results["export_path"] = export_path

            # ----- Step 10: Validate export -----
            if results["export_path"]:
                validate_result = await self.validate_export(results["export_path"])
                results["steps"]["validate_export"] = validate_result
                steps_completed.append("validate_export")
                if not validate_result.get("valid", False):
                    results["warnings"].append(
                        "Export validation failed -- check validate_export step"
                    )

            results["status"] = "success"
            results["steps_completed"] = steps_completed

        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            BlenderCommandError,
        ) as exc:
            results["status"] = "failed"
            results["error"] = str(exc)
            results["steps_completed"] = steps_completed

        return results

    async def generate_and_process(
        self,
        prompt: str | None = None,
        image_path: str | None = None,
        asset_type: str = "prop",
        output_dir: str = ".",
        **pipeline_kwargs,
    ) -> dict:
        """One-call: Generate 3D model via Tripo -> import -> full pipeline -> export.

        This is the ultimate convenience method: provide a text prompt or
        reference image and get a fully processed, rigged (if applicable),
        animated, LOD-ed, and exported game asset.

        Args:
            prompt: Text description for Tripo3D generation.
            image_path: Reference image path for Tripo3D generation.
            asset_type: See :meth:`full_asset_pipeline`.
            output_dir: Directory for Tripo download AND final export.
            **pipeline_kwargs: Forwarded to :meth:`full_asset_pipeline`
                (``poly_budget``, ``material_preset``, ``weathering_preset``,
                ``rig_template``, ``animations``, ``lod_count``,
                ``visual_gate``, ``visual_min_score``, ``export_format``).

        Returns:
            Dict with ``generation`` and ``pipeline`` sub-dicts.
        """
        result: dict = {
            "generation": {},
            "pipeline": {},
            "status": "pending",
        }

        if not prompt and not image_path:
            result["status"] = "failed"
            result["error"] = "'prompt' or 'image_path' is required"
            return result

        preferred_backend = str(getattr(self.settings, "preferred_3d_backend", "stable_fast_3d") or "").strip().lower()
        stable_fast3d_repo_path = str(getattr(self.settings, "stable_fast3d_repo_path", "") or "").strip()
        stable_fast3d_python = str(getattr(self.settings, "stable_fast3d_python", "") or "").strip()
        stable_fast3d_device = str(getattr(self.settings, "stable_fast3d_device", "auto") or "auto").strip().lower()
        stable_fast3d_texture_resolution = int(getattr(self.settings, "stable_fast3d_texture_resolution", 512) or 512)
        stable_fast3d_remesh_option = str(getattr(self.settings, "stable_fast3d_remesh_option", "triangle") or "triangle").strip().lower()
        stable_fast3d_target_vertex_count = int(getattr(self.settings, "stable_fast3d_target_vertex_count", 20000) or 20000)

        local_generation_attempted = False
        local_generation_result: dict | None = None

        if image_path and preferred_backend in {"stable_fast_3d", "stable-fast-3d", "sf3d"} and stable_fast3d_repo_path:
            try:
                from veilbreakers_mcp.shared.stable_fast3d_client import StableFast3DGenerator

                local_gen = StableFast3DGenerator(
                    repo_path=stable_fast3d_repo_path,
                    python_executable=stable_fast3d_python or None,
                )
                local_generation_attempted = True
                local_generation_result = await local_gen.generate_from_image(
                    image_path=image_path,
                    output_dir=output_dir,
                    device=stable_fast3d_device,
                    texture_resolution=stable_fast3d_texture_resolution,
                    remesh_option=stable_fast3d_remesh_option,
                    target_vertex_count=stable_fast3d_target_vertex_count,
                    timeout=getattr(self.settings, "blender_timeout", 300),
                )
                result["generation"]["local_3d"] = local_generation_result
            except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
                local_generation_attempted = True
                local_generation_result = {
                    "status": "failed",
                    "error": f"Stable Fast 3D error: {exc}",
                }
                result["generation"]["local_3d"] = local_generation_result

            if local_generation_result and local_generation_result.get("status") == "success":
                result["generation"] = local_generation_result
            else:
                result.setdefault("warnings", []).append(
                    "Stable Fast 3D local generation failed or was unavailable; falling back to Tripo when credentials are configured."
                )

        # --- Generate via Tripo (prompt path or local fallback) ---
        studio_cookie = getattr(self.settings, "tripo_session_cookie", "")
        studio_token = getattr(self.settings, "tripo_studio_token", "")
        api_key = getattr(self.settings, "tripo_api_key", "")

        if not studio_cookie and not studio_token and not api_key:
            result["status"] = "failed"
            result["error"] = "No Tripo credentials configured (TRIPO_API_KEY, TRIPO_SESSION_COOKIE, or TRIPO_STUDIO_TOKEN)"
            return result

        gen = None
        try:
            if local_generation_attempted and local_generation_result and local_generation_result.get("status") == "success":
                gen_result = local_generation_result
            elif studio_cookie or studio_token:
                from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient
                gen = TripoStudioClient(
                    session_cookie=studio_cookie,
                    session_token=studio_token,
                )
            else:
                from veilbreakers_mcp.shared.tripo_client import TripoGenerator
                gen = TripoGenerator(api_key=api_key)
            if image_path:
                gen_result = await gen.generate_from_image(image_path, output_dir)
            else:
                gen_result = await gen.generate_from_text(prompt, output_dir)
            result["generation"] = gen_result if gen_result is not None else result["generation"]

            if gen_result.get("status") != "success":
                result["status"] = "failed"
                result["error"] = (
                    f"Tripo generation failed: {gen_result.get('error', 'unknown')}"
                )
                return result
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
        ) as exc:
            result["status"] = "failed"
            result["error"] = f"Tripo generation error: {exc}"
            return result
        finally:
            if gen is not None:
                try:
                    close_result = gen.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                except (OSError, RuntimeError):
                    pass

        # Prefer PBR model if available, fall back to standard model
        model_path = gen_result.get("pbr_model_path") or gen_result.get("model_path", "")
        if not model_path:
            result["status"] = "failed"
            result["error"] = "Tripo returned no model file"
            return result

        validation = validate_generated_model_file(model_path)
        result["generation"]["model_validation"] = validation
        if not validation.get("valid", False):
            result["status"] = "failed"
            result["error"] = (
                f"Tripo model failed validation: {validation.get('error', 'unknown')}"
            )
            return result

        # --- Run full pipeline on the downloaded model ---
        pipeline_result = await self.full_asset_pipeline(
            object_name=model_path,
            asset_type=asset_type,
            export_dir=pipeline_kwargs.pop("export_dir", output_dir),
            **pipeline_kwargs,
        )
        result["pipeline"] = pipeline_result
        result["status"] = pipeline_result.get("status", "failed")
        if pipeline_result.get("export_path"):
            result["export_path"] = pipeline_result["export_path"]

        return result
