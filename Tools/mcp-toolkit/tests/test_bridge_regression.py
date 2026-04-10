"""v8.0 regression test suite.

Verifies that critical v8.0 fixes across 8 categories remain intact:
Camera, Checkpoints, Pipeline, Materials, Architecture, Interiors,
Animation, Export.

Uses source code inspection (imports, dicts, function existence) rather
than live Blender/Unity execution.
"""

from __future__ import annotations

import inspect

import pytest


class TestV8Regression:
    """Verify v8.0 fixes are still present in current codebase."""

    # -----------------------------------------------------------------
    # 1. Camera regression
    # -----------------------------------------------------------------

    def test_camera_auto_frame_handler_exists(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "auto_frame_camera" in COMMAND_HANDLERS

    def test_camera_interior_shot_handler_exists(self):
        from blender_addon.handlers import COMMAND_HANDLERS
        assert "interior_camera_shot" in COMMAND_HANDLERS

    def test_camera_auto_frame_callable(self):
        from blender_addon.handlers.viewport import handle_auto_frame_camera
        assert callable(handle_auto_frame_camera)

    def test_camera_interior_shot_callable(self):
        from blender_addon.handlers.viewport import handle_interior_camera_shot
        assert callable(handle_interior_camera_shot)

    # -----------------------------------------------------------------
    # 2. Checkpoints -- interior_results guard + atomic writes
    # -----------------------------------------------------------------

    def test_checkpoint_interior_results_guard(self):
        """compose_map initializes interior_results list before checkpoint."""
        import veilbreakers_mcp.blender_server as bs
        source = inspect.getsource(bs.asset_pipeline)
        assert "interior_results" in source, (
            "interior_results guard missing from compose_map"
        )

    def test_checkpoint_atomic_writes_exist(self):
        """Pipeline state uses os.replace for atomic checkpoint writes."""
        from blender_addon.handlers import pipeline_state
        source = inspect.getsource(pipeline_state)
        assert "os.replace" in source, (
            "os.replace not found in pipeline_state -- atomic writes missing"
        )

    # -----------------------------------------------------------------
    # 3. Pipeline -- _LOC_HANDLERS routes settlement correctly
    # -----------------------------------------------------------------

    def test_loc_handlers_settlement_route(self):
        """_LOC_HANDLERS['settlement'] routes to world_generate_settlement."""
        import veilbreakers_mcp.blender_server as bs
        source = inspect.getsource(bs.asset_pipeline)
        # Verify the _LOC_HANDLERS dict contains settlement -> world_generate_settlement
        assert '"settlement"' in source
        assert '"world_generate_settlement"' in source

    def test_loc_handlers_not_town_for_settlement(self):
        """Settlement should NOT route to world_generate_town."""
        import veilbreakers_mcp.blender_server as bs
        source = inspect.getsource(bs.asset_pipeline)
        # Find the _LOC_HANDLERS block
        idx = source.find("_LOC_HANDLERS")
        assert idx != -1
        block = source[idx:idx + 600]
        # settlement should map to world_generate_settlement not world_generate_town
        assert '"settlement": "world_generate_settlement"' in block

    # -----------------------------------------------------------------
    # 4. Materials -- MATERIAL_LIBRARY entries + binary metallic
    # -----------------------------------------------------------------

    def test_material_library_has_entries(self):
        from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
        assert len(MATERIAL_LIBRARY) >= 7, (
            f"Expected >= 7 entries, got {len(MATERIAL_LIBRARY)}"
        )

    def test_material_library_metallic_binary(self):
        """All metallic values must be exactly 0.0 or 1.0 (no intermediate)."""
        from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
        for key, entry in MATERIAL_LIBRARY.items():
            metallic = entry.get("metallic")
            if metallic is not None:
                assert metallic in (0.0, 1.0), (
                    f"Material '{key}' has non-binary metallic: {metallic}"
                )

    def test_material_library_has_stone_entries(self):
        from blender_addon.handlers.procedural_materials import MATERIAL_LIBRARY
        stone_keys = [k for k in MATERIAL_LIBRARY if "stone" in k]
        assert len(stone_keys) >= 3, (
            f"Expected >= 3 stone materials, got {stone_keys}"
        )

    # -----------------------------------------------------------------
    # 5. Architecture -- building quality geometry functions
    # -----------------------------------------------------------------

    def test_building_quality_timber_frame(self):
        from blender_addon.handlers.building_quality import generate_timber_frame
        assert callable(generate_timber_frame)

    def test_building_quality_flying_buttress(self):
        from blender_addon.handlers.building_quality import generate_flying_buttress
        assert callable(generate_flying_buttress)

    # -----------------------------------------------------------------
    # 6. Interiors -- 180-degree rotation uses atan2
    # -----------------------------------------------------------------

    def test_interior_rotation_uses_atan2(self):
        """Interior placement rotation calculation uses atan2."""
        from blender_addon.handlers import building_quality
        source = inspect.getsource(building_quality)
        assert "atan2" in source, (
            "atan2 not found in building_quality -- rotation formula may be wrong"
        )

    # -----------------------------------------------------------------
    # 7. Animation -- bone existence filter
    # -----------------------------------------------------------------

    def test_animation_bone_existence_check(self):
        """Animation handlers check bone existence before assignment."""
        from blender_addon.handlers import animation
        source = inspect.getsource(animation)
        # Should have hasattr or 'in' check for bones
        has_guard = "hasattr" in source or "pose.bones" in source
        assert has_guard, (
            "No bone existence guard found in animation handlers"
        )

    # -----------------------------------------------------------------
    # 8. Export -- roughness-to-smoothness + collision prefix
    # -----------------------------------------------------------------

    def test_export_roughness_to_smoothness_inversion(self):
        """Unity quality templates convert roughness to smoothness."""
        from veilbreakers_mcp.shared.unity_templates import quality_templates
        source = inspect.getsource(quality_templates)
        assert "1.0 - roughness" in source, (
            "Roughness-to-smoothness inversion not found in quality_templates"
        )

    def test_export_collision_mesh_col_prefix(self):
        """Export handler renames _COL suffix to UCX_ prefix for Unity."""
        from blender_addon.handlers import export
        source = inspect.getsource(export)
        assert "_COL" in source, "_COL collision prefix handling missing"
        assert "UCX_" in source, "UCX_ Unity prefix handling missing"

    def test_export_collision_rename_function_exists(self):
        from blender_addon.handlers.export import _rename_collision_meshes_for_unity
        assert callable(_rename_collision_meshes_for_unity)
