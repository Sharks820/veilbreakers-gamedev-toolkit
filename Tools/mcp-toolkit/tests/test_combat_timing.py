"""Tests for combat timing system (FromSoft-style animation feel).

Validates ANIM3-01, ANIM3-02, ANIM3-05 requirements:
- Combat timing presets and configure_combat_timing
- Animation event generation with brand parameterization
- Root motion refinement (smoothing, drift snapping)
- Combined combat animation data generation

All pure-logic -- no Blender required.
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers._combat_timing import (
    COMBAT_TIMING_PRESETS,
    VALID_BRANDS,
    configure_combat_timing,
    generate_animation_events,
    generate_combat_animation_data,
    refine_root_motion,
)


# ---------------------------------------------------------------------------
# TestCombatTimingPresets (ANIM3-01)
# ---------------------------------------------------------------------------


class TestCombatTimingPresets:
    """Test COMBAT_TIMING_PRESETS data integrity."""

    def test_all_seven_types_present(self):
        expected = {
            "light_attack", "heavy_attack", "charged_attack",
            "combo_finisher", "dodge_roll", "parry", "block",
        }
        assert set(COMBAT_TIMING_PRESETS.keys()) == expected

    @pytest.mark.parametrize("attack_type", list(COMBAT_TIMING_PRESETS.keys()))
    def test_total_equals_sum_of_phases(self, attack_type):
        preset = COMBAT_TIMING_PRESETS[attack_type]
        assert preset["total"] == (
            preset["anticipation"] + preset["active"] + preset["recovery"]
        )

    @pytest.mark.parametrize("attack_type", list(COMBAT_TIMING_PRESETS.keys()))
    def test_all_required_fields_present(self, attack_type):
        preset = COMBAT_TIMING_PRESETS[attack_type]
        required = {
            "anticipation", "active", "recovery", "total",
            "hit_frame", "vfx_frame", "sound_frame",
            "camera_shake_frame", "hitstop_frames",
        }
        assert required.issubset(preset.keys())

    def test_light_attack_timing(self):
        la = COMBAT_TIMING_PRESETS["light_attack"]
        assert la["anticipation"] == 6
        assert la["active"] == 3
        assert la["recovery"] == 8
        assert la["total"] == 17

    def test_heavy_attack_timing(self):
        ha = COMBAT_TIMING_PRESETS["heavy_attack"]
        assert ha["anticipation"] == 12
        assert ha["active"] == 4
        assert ha["recovery"] == 15
        assert ha["total"] == 31

    def test_dodge_roll_no_hit_frame(self):
        dr = COMBAT_TIMING_PRESETS["dodge_roll"]
        assert dr["hit_frame"] == -1

    def test_block_zero_active(self):
        bl = COMBAT_TIMING_PRESETS["block"]
        assert bl["active"] == 0
        assert bl["hit_frame"] == -1

    def test_hit_frames_within_active_phase(self):
        """Hit frames should be within the active phase for attacks."""
        for name, preset in COMBAT_TIMING_PRESETS.items():
            if preset["hit_frame"] < 0:
                continue  # dodge/block have no hit frame
            assert preset["hit_frame"] >= preset["anticipation"], (
                f"{name}: hit_frame {preset['hit_frame']} < anticipation {preset['anticipation']}"
            )
            active_end = preset["anticipation"] + preset["active"]
            assert preset["hit_frame"] < active_end, (
                f"{name}: hit_frame {preset['hit_frame']} >= active_end {active_end}"
            )


# ---------------------------------------------------------------------------
# TestConfigureCombatTiming (ANIM3-01)
# ---------------------------------------------------------------------------


class TestConfigureCombatTiming:
    """Test configure_combat_timing function."""

    def test_default_30fps(self):
        config = configure_combat_timing("light_attack")
        assert config["fps"] == 30
        assert config["attack_type"] == "light_attack"
        assert config["frames"]["anticipation"] == 6
        assert config["frames"]["active"] == 3
        assert config["frames"]["recovery"] == 8
        assert config["total_frames"] == 17

    def test_60fps_scaling(self):
        config = configure_combat_timing("light_attack", fps=60)
        assert config["fps"] == 60
        # At 60fps, frames double from 30fps reference
        assert config["frames"]["anticipation"] == 12
        assert config["frames"]["active"] == 6
        assert config["frames"]["recovery"] == 16
        assert config["total_frames"] == 34

    def test_24fps_scaling(self):
        config = configure_combat_timing("heavy_attack", fps=24)
        assert config["fps"] == 24
        # At 24fps: scale = 24/30 = 0.8
        # anticipation: round(12 * 0.8) = 10
        assert config["frames"]["anticipation"] == 10

    def test_custom_timing_override(self):
        config = configure_combat_timing(
            "light_attack",
            custom_timing={"anticipation": 10, "active": 5},
        )
        assert config["frames"]["anticipation"] == 10
        assert config["frames"]["active"] == 5
        assert config["frames"]["recovery"] == 8
        assert config["total_frames"] == 23

    def test_normalized_times_sum_to_one(self):
        config = configure_combat_timing("heavy_attack")
        times = config["times"]
        assert times["anticipation_start"] == pytest.approx(0.0)
        assert times["recovery_end"] == pytest.approx(1.0)
        # Phases are contiguous
        assert times["anticipation_end"] == pytest.approx(times["active_start"])
        assert times["active_end"] == pytest.approx(times["recovery_start"])

    def test_phase_ranges(self):
        config = configure_combat_timing("light_attack")
        ranges = config["phase_ranges"]
        assert ranges["anticipation"] == (0, 5)
        assert ranges["active"] == (6, 8)
        assert ranges["recovery"] == (9, 16)

    def test_block_no_active_range(self):
        config = configure_combat_timing("block")
        assert config["phase_ranges"]["active"] is None

    def test_duration_seconds(self):
        config = configure_combat_timing("light_attack", fps=30)
        assert config["total_duration_seconds"] == pytest.approx(17 / 30.0)

    def test_invalid_attack_type_raises(self):
        with pytest.raises(ValueError, match="Unknown attack type"):
            configure_combat_timing("nonexistent")

    def test_invalid_fps_raises(self):
        with pytest.raises(ValueError, match="fps must be >= 1"):
            configure_combat_timing("light_attack", fps=0)

    def test_total_recalculated_on_override(self):
        """Total should be recalculated when phases are overridden."""
        config = configure_combat_timing(
            "light_attack",
            custom_timing={"anticipation": 20, "active": 10, "recovery": 5},
        )
        assert config["total_frames"] == 35


# ---------------------------------------------------------------------------
# TestGenerateAnimationEvents (ANIM3-02)
# ---------------------------------------------------------------------------


class TestGenerateAnimationEvents:
    """Test generate_animation_events function."""

    def test_light_attack_events(self):
        timing = configure_combat_timing("light_attack")
        events = generate_animation_events(timing, brand="IRON")
        assert isinstance(events, list)
        assert len(events) > 0

    def test_all_event_types_have_required_fields(self):
        timing = configure_combat_timing("heavy_attack")
        events = generate_animation_events(timing, brand="SAVAGE")
        required = {"frame", "event_type", "function_name", "string_param", "float_param", "int_param"}
        for ev in events:
            assert required.issubset(ev.keys()), f"Missing fields in event: {ev}"

    def test_hit_event_present_for_attacks(self):
        """Attacks with hit frames should produce hit events."""
        timing = configure_combat_timing("light_attack")
        events = generate_animation_events(timing, brand="IRON")
        hit_events = [e for e in events if e["event_type"] == "hit"]
        assert len(hit_events) == 1
        assert hit_events[0]["frame"] == timing["frames"]["hit_frame"]

    def test_no_hit_event_for_dodge(self):
        timing = configure_combat_timing("dodge_roll")
        events = generate_animation_events(timing, brand="IRON")
        hit_events = [e for e in events if e["event_type"] == "hit"]
        assert len(hit_events) == 0

    def test_brand_parameterization(self):
        timing = configure_combat_timing("heavy_attack")
        events_iron = generate_animation_events(timing, brand="IRON")
        events_surge = generate_animation_events(timing, brand="SURGE")
        # VFX string params should differ by brand
        vfx_iron = [e for e in events_iron if e["event_type"] == "vfx_spawn"]
        vfx_surge = [e for e in events_surge if e["event_type"] == "vfx_spawn"]
        assert len(vfx_iron) == 1
        assert len(vfx_surge) == 1
        assert vfx_iron[0]["string_param"] != vfx_surge[0]["string_param"]
        assert "sparks" in vfx_iron[0]["string_param"]
        assert "lightning" in vfx_surge[0]["string_param"]

    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_accepted(self, brand):
        timing = configure_combat_timing("light_attack")
        events = generate_animation_events(timing, brand=brand)
        assert len(events) > 0

    def test_invalid_brand_raises(self):
        timing = configure_combat_timing("light_attack")
        with pytest.raises(ValueError, match="Unknown brand"):
            generate_animation_events(timing, brand="FAKE")

    def test_events_sorted_by_frame(self):
        timing = configure_combat_timing("charged_attack")
        events = generate_animation_events(timing, brand="VOID")
        frames = [e["frame"] for e in events]
        assert frames == sorted(frames)

    def test_hitstop_event_present_for_heavy(self):
        timing = configure_combat_timing("heavy_attack")
        events = generate_animation_events(timing, brand="IRON")
        hitstop = [e for e in events if e["event_type"] == "hitstop"]
        assert len(hitstop) == 1
        assert hitstop[0]["int_param"] == timing["frames"]["hitstop_frames"]

    def test_camera_shake_event(self):
        timing = configure_combat_timing("heavy_attack")
        events = generate_animation_events(timing, brand="IRON")
        shake = [e for e in events if e["event_type"] == "camera_shake"]
        assert len(shake) == 1
        assert shake[0]["float_param"] > 0

    def test_footstep_events_for_dodge_roll(self):
        timing = configure_combat_timing("dodge_roll")
        events = generate_animation_events(timing, brand="IRON")
        footsteps = [e for e in events if e["event_type"] == "footstep"]
        assert len(footsteps) == 2

    def test_sound_trigger_present(self):
        timing = configure_combat_timing("light_attack")
        events = generate_animation_events(timing, brand="IRON")
        sounds = [e for e in events if e["event_type"] == "sound_trigger"]
        assert len(sounds) == 1
        assert "OnAnimSoundTrigger" in sounds[0]["function_name"]


# ---------------------------------------------------------------------------
# TestRefineRootMotion (ANIM3-05)
# ---------------------------------------------------------------------------


class TestRefineRootMotion:
    """Test refine_root_motion function."""

    def test_smooths_y_axis_spike(self):
        """A spike in Y should be smoothed by averaging."""
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 2.0, "x": 0.0, "y": 1.0, "z": 0.0},  # spike
            {"frame": 3.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 4.0, "x": 0.0, "y": 0.0, "z": 0.0},
        ]
        refined = refine_root_motion(kf, smoothing_passes=1)
        # The spike at frame 2 should be reduced
        assert refined[2]["y"] < 1.0
        assert refined[2]["y"] > 0.0  # not eliminated, just smoothed

    def test_snaps_small_xz_drift(self):
        """Tiny horizontal movements should be snapped to zero."""
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.005, "y": 0.0, "z": 0.003},
            {"frame": 2.0, "x": 0.008, "y": 0.0, "z": 0.006},
            {"frame": 3.0, "x": 0.009, "y": 0.0, "z": 0.007},
        ]
        refined = refine_root_motion(kf, drift_threshold=0.01)
        # Small increments should be snapped
        assert refined[1]["x"] == 0.0
        assert refined[1]["z"] == 0.0

    def test_preserves_large_movements(self):
        """Movements above threshold should not be snapped."""
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.0, "y": 0.0, "z": 0.5},
            {"frame": 2.0, "x": 0.0, "y": 0.0, "z": 1.0},
            {"frame": 3.0, "x": 0.0, "y": 0.0, "z": 1.5},
        ]
        refined = refine_root_motion(kf, drift_threshold=0.01)
        assert refined[1]["z"] == pytest.approx(0.5)
        assert refined[2]["z"] == pytest.approx(1.0)
        assert refined[3]["z"] == pytest.approx(1.5)

    def test_does_not_mutate_input(self):
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.005, "y": 0.5, "z": 0.0},
            {"frame": 2.0, "x": 0.0, "y": 1.0, "z": 0.0},
            {"frame": 3.0, "x": 0.0, "y": 0.0, "z": 0.0},
        ]
        original_y1 = kf[1]["y"]
        refine_root_motion(kf)
        assert kf[1]["y"] == original_y1  # input unchanged

    def test_empty_keyframes_raises(self):
        with pytest.raises(ValueError, match="keyframes list must not be empty"):
            refine_root_motion([])

    def test_negative_passes_raises(self):
        kf = [{"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0}]
        with pytest.raises(ValueError, match="smoothing_passes must be >= 0"):
            refine_root_motion(kf, smoothing_passes=-1)

    def test_zero_passes_only_drift_snap(self):
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.5, "z": 0.0},
            {"frame": 1.0, "x": 0.005, "y": 1.0, "z": 0.0},
            {"frame": 2.0, "x": 0.008, "y": 0.0, "z": 0.0},
            {"frame": 3.0, "x": 0.0, "y": 0.0, "z": 0.0},
        ]
        refined = refine_root_motion(kf, smoothing_passes=0, drift_threshold=0.01)
        # Y should NOT be smoothed with 0 passes
        assert refined[1]["y"] == pytest.approx(1.0)
        # But XZ drift should still be snapped
        assert refined[1]["x"] == 0.0

    def test_two_frame_keyframes(self):
        """With only 2 frames, smoothing can't apply but drift snap should."""
        kf = [
            {"frame": 0.0, "x": 0.005, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.008, "y": 0.0, "z": 0.0},
        ]
        refined = refine_root_motion(kf, drift_threshold=0.01)
        assert len(refined) == 2

    def test_loop_boundary_cleanup(self):
        """First and last frames should match for clean loops."""
        kf = [
            {"frame": 0.0, "x": 0.0, "y": 0.005, "z": 0.0},
            {"frame": 1.0, "x": 0.0, "y": 0.1, "z": 0.0},
            {"frame": 2.0, "x": 0.0, "y": 0.2, "z": 0.0},
            {"frame": 3.0, "x": 0.0, "y": 0.005, "z": 0.0},
        ]
        refined = refine_root_motion(kf, drift_threshold=0.01)
        # First frame Y near zero should snap to zero
        assert refined[0]["y"] == 0.0


# ---------------------------------------------------------------------------
# TestGenerateCombatAnimationData (combined)
# ---------------------------------------------------------------------------


class TestGenerateCombatAnimationData:
    """Test generate_combat_animation_data combined function."""

    def test_basic_output_structure(self):
        result = generate_combat_animation_data("light_attack", brand="IRON")
        assert "timing" in result
        assert "events" in result
        assert "root_motion" in result
        assert "metadata" in result

    def test_metadata_fields(self):
        result = generate_combat_animation_data("heavy_attack", brand="SURGE", fps=60)
        meta = result["metadata"]
        assert meta["attack_type"] == "heavy_attack"
        assert meta["brand"] == "SURGE"
        assert meta["fps"] == 60
        assert meta["total_frames"] > 0
        assert meta["total_duration"] > 0
        assert meta["event_count"] > 0

    def test_default_root_motion_generated(self):
        result = generate_combat_animation_data("light_attack")
        rm = result["root_motion"]
        assert len(rm) == result["timing"]["total_frames"]

    def test_custom_root_motion_refined(self):
        custom_rm = [
            {"frame": 0.0, "x": 0.0, "y": 0.0, "z": 0.0},
            {"frame": 1.0, "x": 0.0, "y": 0.5, "z": 0.0},
            {"frame": 2.0, "x": 0.0, "y": 1.0, "z": 0.0},
            {"frame": 3.0, "x": 0.0, "y": 0.0, "z": 0.0},
        ]
        result = generate_combat_animation_data(
            "light_attack", root_motion_keyframes=custom_rm,
        )
        assert len(result["root_motion"]) == 4

    @pytest.mark.parametrize("attack_type", list(COMBAT_TIMING_PRESETS.keys()))
    def test_all_attack_types_generate(self, attack_type):
        result = generate_combat_animation_data(attack_type)
        assert result["metadata"]["attack_type"] == attack_type
        assert len(result["events"]) > 0

    @pytest.mark.parametrize("brand", sorted(VALID_BRANDS))
    def test_all_brands_with_heavy_attack(self, brand):
        result = generate_combat_animation_data("heavy_attack", brand=brand)
        assert result["metadata"]["brand"] == brand

    def test_custom_timing_propagates(self):
        result = generate_combat_animation_data(
            "light_attack",
            custom_timing={"anticipation": 20},
        )
        assert result["timing"]["frames"]["anticipation"] == 20

    def test_root_motion_forward_lunge_in_active(self):
        """Default root motion should have forward movement during active phase."""
        result = generate_combat_animation_data("heavy_attack")
        rm = result["root_motion"]
        timing = result["timing"]
        active_start_frame = timing["frames"]["anticipation"]
        active_end_frame = active_start_frame + timing["frames"]["active"]
        # Find max Z during active phase
        active_z = [kf["z"] for kf in rm if active_start_frame <= kf["frame"] < active_end_frame]
        if active_z:
            assert max(active_z) > 0, "Should have forward movement during active phase"
