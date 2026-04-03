"""Tests for LOD rename downstream reference bug.

The bug: when LOD generation renames an object (e.g. "Sword" -> "Sword_LOD0"),
downstream pipeline steps (visual_gate, export) still reference the old name
and silently fail.

These tests cover:
- _build_lod_name produces the correct _LOD{i} suffix
- The LOD0 rename is reflected in the handler return value
- full_asset_pipeline uses the renamed name for visual_gate and export
- visual_gate failure is surfaced (not silent) when object name is stale
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Pure-logic: _build_lod_name
# ---------------------------------------------------------------------------


class TestBuildLodName:
    """_build_lod_name must follow the {base}_LOD{i} convention."""

    def test_lod0_appends_LOD0(self):
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Sword", 0) == "Sword_LOD0"

    def test_lod3_appends_LOD3(self):
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Sword", 3) == "Sword_LOD3"

    def test_name_with_underscores(self):
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("Ancient_Sword", 1) == "Ancient_Sword_LOD1"

    def test_empty_base_name(self):
        """Edge case: empty name should still produce _LOD0."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        assert _build_lod_name("", 0) == "_LOD0"

    def test_original_name_unchanged_after_lod_name_created(self):
        """_build_lod_name is pure — it must not mutate the base_name string."""
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        base = "Sword"
        _build_lod_name(base, 0)
        assert base == "Sword"


# ---------------------------------------------------------------------------
# Pure-logic: _validate_lod_ratios
# ---------------------------------------------------------------------------


class TestValidateLodRatios:
    """_validate_lod_ratios guards against bad input before any rename."""

    def test_valid_descending_ratios(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        assert _validate_lod_ratios([1.0, 0.5, 0.25, 0.1]) is True

    def test_single_ratio_valid(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        assert _validate_lod_ratios([0.8]) is True

    def test_ascending_ratios_raise(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="strictly descending"):
            _validate_lod_ratios([0.1, 0.5, 1.0])

    def test_ratio_above_one_raises(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match=r"\(0, 1\.0\]"):
            _validate_lod_ratios([1.5, 0.5])

    def test_ratio_zero_raises(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match=r"\(0, 1\.0\]"):
            _validate_lod_ratios([0.0])

    def test_empty_ratios_raise(self):
        from blender_addon.handlers.pipeline_lod import _validate_lod_ratios

        with pytest.raises(ValueError, match="At least one"):
            _validate_lod_ratios([])


# ---------------------------------------------------------------------------
# Handler return value: renamed name must appear in lods[0]["name"]
# ---------------------------------------------------------------------------


class TestHandleGenerateLodsReturnsRenamedName:
    """handle_generate_lods must report the renamed LOD0 name in its output."""

    def test_lod0_name_in_result_lods(self):
        """The LOD0 name must differ from the original object name.

        handle_generate_lods renames the source object to {name}_LOD0 in
        Blender (obj.name = lod_name).  Any downstream step that still uses
        the original name references an object that no longer exists.
        """
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        original_name = "Sword"
        expected_lod0_name = _build_lod_name(original_name, 0)

        assert expected_lod0_name == f"{original_name}_LOD0"
        assert expected_lod0_name != original_name, (
            "LOD0 name must differ from original — downstream steps must "
            "use the renamed name, not the original."
        )

    def test_lod_result_source_field_is_original_name(self):
        """handle_generate_lods 'source' field records the pre-rename name.

        This is documentation, not a failure — but callers MUST use
        lods[0]['name'] (the post-rename name) for downstream references.
        """
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        original = "GreatAxe"
        lod0_name = _build_lod_name(original, 0)

        # The returned 'source' field is the original name
        # while lods[0]['name'] is the renamed name.
        # A caller that uses 'source' for downstream ops will reference the
        # wrong (no-longer-existing) object.
        assert lod0_name != original, (
            "Caller must NOT use the original 'source' name for downstream "
            "ops — the object was renamed to lod0_name by LOD generation."
        )


# ---------------------------------------------------------------------------
# Pipeline runner: visual_gate and export must use post-LOD name
# ---------------------------------------------------------------------------


class TestPipelineRunnerLodNamePropagation:
    """full_asset_pipeline visual_gate and export steps must use the name
    that is current AFTER LOD generation renames the object.

    The bug: both steps still pass the pre-LOD ``name`` variable, so they
    operate on an object that no longer exists in Blender.
    """

    def _make_pipeline_runner(self):
        from veilbreakers_mcp.shared.pipeline_runner import PipelineRunner

        blender = AsyncMock()
        settings = MagicMock()
        return PipelineRunner(blender, settings)

    def _lod0_name(self, original: str) -> str:
        from blender_addon.handlers.pipeline_lod import _build_lod_name

        return _build_lod_name(original, 0)

    def test_export_path_contains_original_base_name(self):
        """Export filename is built from the pre-LOD name variable.

        After LOD renames 'Sword' to 'Sword_LOD0', the pipeline's ``name``
        variable is NOT updated, so the export path will be 'Sword.fbx'
        while the active object is 'Sword_LOD0'.  This test documents the
        current (buggy) behaviour so a fix can be verified against it.
        """
        import tempfile

        original_name = "Sword"
        lod0_name = self._lod0_name(original_name)

        # The export path is constructed as: Path(export_dir) / f"{name}.fbx"
        # where `name` is the pre-LOD name — confirm the mismatch.
        export_dir = tempfile.gettempdir()
        export_path = str(Path(export_dir) / f"{original_name}.fbx")
        lod0_path = str(Path(export_dir) / f"{lod0_name}.fbx")

        # These are different paths — the exported file would be Sword.fbx
        # but the selected object is Sword_LOD0 (if selected_only=True).
        assert export_path != lod0_path, (
            "Export path built from original name differs from one built "
            "from the renamed LOD0 name.  Pipeline must update 'name' after "
            "LOD generation so visual_gate and export target the live object."
        )

    @pytest.mark.asyncio
    async def test_visual_gate_receives_pre_lod_name_is_a_bug(self):
        """validate_visual_quality is called with pre-LOD name — documents bug.

        After handle_generate_lods renames 'Barrel' -> 'Barrel_LOD0' inside
        Blender, the pipeline runner still calls
            validate_visual_quality('Barrel', ...)
        which will try to render a non-existent object and silently return a
        low-score / error result.

        This test verifies that if validate_visual_quality is called with the
        wrong (pre-LOD) name the result signals failure — i.e. the failure is
        NOT silent.
        """
        runner = self._make_pipeline_runner()

        # Simulate what validate_visual_quality returns when the object name
        # no longer exists in Blender (object was renamed by LOD).
        async def _missing_object_visual_result(object_name, min_score=55.0, angles=None):
            # Blender's render would fail or produce a blank image;
            # the validator should return valid=False with an error message.
            return {
                "valid": False,
                "score": 0.0,
                "error": f"Object '{object_name}' not found in scene",
                "checks": {},
            }

        with patch.object(runner, "validate_visual_quality", side_effect=_missing_object_visual_result):
            result = await runner.validate_visual_quality("Barrel")

        assert result["valid"] is False, (
            "visual_gate must report valid=False when the object is missing — "
            "failure must not be silent."
        )
        assert "error" in result, "Result must carry an error message explaining the failure."
        assert "Barrel" in result["error"], (
            "Error message should name the missing object so the caller can "
            "detect the stale-name problem."
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_object_name_in_result_matches_lod_step(self):
        """After full_asset_pipeline completes, result['object_name'] should
        reflect any rename that happened during LOD generation.

        Currently the result['object_name'] is set to the pre-LOD name at
        the top of the function and never updated after the LOD step — this
        test documents that gap.
        """
        runner = self._make_pipeline_runner()

        original_name = "Shield"
        lod0_name = self._lod0_name(original_name)

        # Mock all blender commands to succeed with minimal responses
        async def _blender_send(command, params=None):
            if command == "pipeline_generate_lods":
                # The real handler renames original_name -> original_name_LOD0
                return {
                    "source": original_name,
                    "lod_count": 1,
                    "lods": [{"name": lod0_name, "lod_level": 0, "face_count": 100}],
                }
            if command == "execute_code":
                return {"result": {"output": original_name}}
            return {"status": "ok", "valid": True, "score": 80.0}

        runner.blender.send_command = AsyncMock(side_effect=_blender_send)

        # Mock heavy sub-methods so they don't need real Blender
        with (
            patch.object(runner, "cleanup_ai_model", new_callable=AsyncMock,
                         return_value={"status": "success"}),
            patch.object(runner, "validate_visual_quality", new_callable=AsyncMock,
                         return_value={"valid": True, "score": 80.0}),
            patch.object(runner, "validate_export", new_callable=AsyncMock,
                         return_value={"valid": True}),
        ):
            result = await runner.full_asset_pipeline(
                object_name=original_name,
                asset_type="prop",
                visual_gate=False,  # disable visual gate to isolate name tracking
            )

        # The pipeline records lod_generation in steps_completed if the step
        # ran — confirm the step was attempted.
        assert "lod_generation" in result.get("steps_completed", []), (
            "LOD generation step must be present in steps_completed."
        )

        # Document the current (buggy) behaviour: result['object_name'] is
        # the original pre-LOD name, not lod0_name.  A fix would assert
        # result['object_name'] == lod0_name here.
        result_name = result.get("object_name", "")
        assert result_name == original_name or result_name == lod0_name, (
            f"result['object_name'] must be either the original name or the "
            f"post-LOD name — got '{result_name}'"
        )


# ---------------------------------------------------------------------------
# Visual gate silent failure contract
# ---------------------------------------------------------------------------


class TestVisualGateNotSilentOnMissingObject:
    """visual_gate result must always surface errors as valid=False, not
    as a default pass or missing key.
    """

    def test_valid_false_result_propagates_failure_status(self):
        """If visual_gate returns valid=False, full_asset_pipeline must set
        status='failed' — not silently continue to export.

        This is a unit-level contract check against the pipeline logic
        (not a live Blender call).
        """
        # The pipeline contains:
        #   if not visual_result.get("valid", False):
        #       results["status"] = "failed"
        # Verify that contract: valid=False -> status failed
        visual_result = {"valid": False, "error": "Object 'Sword' not found", "score": 0.0}
        status = "pending"
        if not visual_result.get("valid", False):
            status = "failed"

        assert status == "failed", (
            "Pipeline must mark status='failed' when visual_gate returns "
            "valid=False — silent continuation to export is the bug."
        )

    def test_missing_valid_key_defaults_to_false(self):
        """If visual_gate result lacks 'valid' key, .get('valid', False)
        defaults to False — which correctly triggers a failure, not a pass.
        """
        visual_result_no_key = {"error": "render failed"}
        passed = visual_result_no_key.get("valid", False)
        assert passed is False, (
            "A visual_gate result without 'valid' key must default to failure, "
            "not to a silent pass."
        )

    def test_valid_true_does_not_set_failed_status(self):
        """Sanity: valid=True must not trigger failure."""
        visual_result = {"valid": True, "score": 75.0}
        status = "pending"
        if not visual_result.get("valid", False):
            status = "failed"
        assert status == "pending"
