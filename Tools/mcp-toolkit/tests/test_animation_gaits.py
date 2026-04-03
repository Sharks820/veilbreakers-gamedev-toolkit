"""Comprehensive tests for the pure-logic keyframe engine and all configs.

Tests cover:
- Keyframe namedtuple structure
- Cycle keyframe generation (seamless looping, correct count)
- All 5 gait types at walk and run speeds
- Fly/hover config
- Idle config
- get_gait_config routing and filtering
- Attack keyframe generation (8 types, 3-phase timing, intensity scaling)
- Reaction keyframe generation (death, hit with 4 directions, spawn)
- Custom text-to-keyframe mapping

All pure-logic -- no Blender required.
"""

import math

import pytest

from blender_addon.handlers.animation_gaits import (
    ARACHNID_RUN_CONFIG,
    ARACHNID_WALK_CONFIG,
    ATTACK_CONFIGS,
    BIPED_RUN_CONFIG,
    BIPED_WALK_CONFIG,
    FLY_HOVER_CONFIG,
    HEXAPOD_RUN_CONFIG,
    HEXAPOD_WALK_CONFIG,
    IDLE_CONFIG,
    Keyframe,
    QUADRUPED_CANTER_CONFIG,
    QUADRUPED_GALLOP_CONFIG,
    QUADRUPED_RUN_CONFIG,
    QUADRUPED_TROT_CONFIG,
    QUADRUPED_WALK_CONFIG,
    REACTION_CONFIGS,
    SERPENT_RUN_CONFIG,
    SERPENT_WALK_CONFIG,
    generate_attack_keyframes,
    generate_custom_keyframes,
    generate_cycle_keyframes,
    generate_reaction_keyframes,
    get_gait_config,
)


# ---------------------------------------------------------------------------
# TestKeyframeType
# ---------------------------------------------------------------------------


class TestKeyframeType:
    """Test the Keyframe namedtuple structure."""

    def test_keyframe_fields(self):
        kf = Keyframe(
            bone_name="DEF-thigh.L",
            channel="rotation_euler",
            axis=0,
            frame=5,
            value=0.42,
        )
        assert kf.bone_name == "DEF-thigh.L"
        assert kf.channel == "rotation_euler"
        assert kf.axis == 0
        assert kf.frame == 5
        assert kf.value == pytest.approx(0.42)

    def test_keyframe_is_tuple(self):
        kf = Keyframe("DEF-spine", "location", 2, 0, 0.1)
        assert isinstance(kf, tuple)
        assert len(kf) == 5

    def test_keyframe_unpacking(self):
        kf = Keyframe("DEF-jaw", "rotation_euler", 0, 10, 0.5)
        bone, channel, axis, frame, value = kf
        assert bone == "DEF-jaw"
        assert channel == "rotation_euler"
        assert axis == 0
        assert frame == 10
        assert value == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# TestCycleGeneration
# ---------------------------------------------------------------------------


class TestCycleGeneration:
    """Test the generate_cycle_keyframes engine."""

    def test_returns_list_of_keyframes(self):
        kfs = generate_cycle_keyframes(BIPED_WALK_CONFIG)
        assert isinstance(kfs, list)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_correct_keyframe_count(self):
        """frame_count+1 keyframes per bone."""
        config = BIPED_WALK_CONFIG
        fc = config["frame_count"]
        bone_count = len(config["bones"])
        kfs = generate_cycle_keyframes(config)
        expected = bone_count * (fc + 1)
        assert len(kfs) == expected

    def test_seamless_loop(self):
        """Frame 0 value equals frame N value for every bone (within tolerance)."""
        kfs = generate_cycle_keyframes(BIPED_WALK_CONFIG)
        fc = BIPED_WALK_CONFIG["frame_count"]

        # Group by (bone, channel, axis)
        by_bone: dict[tuple, dict[int, float]] = {}
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis)
            by_bone.setdefault(key, {})[kf.frame] = kf.value

        for key, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), (
                f"Loop not seamless for {key}: frame0={frames[0]}, frameN={frames[fc]}"
            )

    def test_offset_applied(self):
        """If offset is specified, values are shifted."""
        config = {
            "name": "test_offset",
            "frame_count": 4,
            "bones": {
                "DEF-test": {
                    "channel": "rotation_euler", "axis": 0,
                    "amplitude": 1.0, "phase": 0.0, "offset": 2.0,
                },
            },
        }
        kfs = generate_cycle_keyframes(config)
        # At frame 0, sin(0) = 0, so value should be 0 + 2.0 = 2.0
        assert kfs[0].value == pytest.approx(2.0)

    def test_zero_amplitude_gives_offset(self):
        config = {
            "name": "test_zero_amp",
            "frame_count": 4,
            "bones": {
                "DEF-test": {
                    "channel": "location", "axis": 2,
                    "amplitude": 0.0, "phase": 0.0, "offset": 1.5,
                },
            },
        }
        kfs = generate_cycle_keyframes(config)
        for kf in kfs:
            assert kf.value == pytest.approx(1.5)

    def test_channels_preserved(self):
        config = {
            "name": "test_channels",
            "frame_count": 2,
            "bones": {
                "DEF-a": {"channel": "rotation_euler", "axis": 1, "amplitude": 0.5, "phase": 0.0},
                "DEF-b": {"channel": "location", "axis": 2, "amplitude": 0.3, "phase": 0.0},
            },
        }
        kfs = generate_cycle_keyframes(config)
        a_kfs = [kf for kf in kfs if kf.bone_name == "DEF-a"]
        b_kfs = [kf for kf in kfs if kf.bone_name == "DEF-b"]
        assert all(kf.channel == "rotation_euler" and kf.axis == 1 for kf in a_kfs)
        assert all(kf.channel == "location" and kf.axis == 2 for kf in b_kfs)


# ---------------------------------------------------------------------------
# TestBipedConfigs
# ---------------------------------------------------------------------------


class TestBipedConfigs:
    """Test biped walk and run configurations."""

    def test_walk_has_required_bones(self):
        bones = BIPED_WALK_CONFIG["bones"]
        required = ["DEF-thigh.L", "DEF-thigh.R", "DEF-shin.L", "DEF-shin.R", "DEF-spine.001"]
        for bone in required:
            assert bone in bones, f"Missing required bone: {bone}"

    def test_thighs_antiphase(self):
        """Left and right thighs should have pi phase offset (first harmonic)."""
        bones = BIPED_WALK_CONFIG["bones"]
        thigh_l = bones["DEF-thigh.L"]
        thigh_r = bones["DEF-thigh.R"]
        # Support both simple phase and multi-harmonic configs
        phase_l = thigh_l["harmonics"][0]["phase"] if "harmonics" in thigh_l else thigh_l["phase"]
        phase_r = thigh_r["harmonics"][0]["phase"] if "harmonics" in thigh_r else thigh_r["phase"]
        diff = abs(phase_r - phase_l)
        assert diff == pytest.approx(math.pi, abs=1e-6)

    def test_run_higher_amplitude_than_walk(self):
        walk_cfg = BIPED_WALK_CONFIG["bones"]["DEF-thigh.L"]
        run_cfg = BIPED_RUN_CONFIG["bones"]["DEF-thigh.L"]
        # Support both simple amplitude and multi-harmonic configs
        walk_amp = sum(h["amp"] for h in walk_cfg["harmonics"]) if "harmonics" in walk_cfg else walk_cfg["amplitude"]
        run_amp = sum(h["amp"] for h in run_cfg["harmonics"]) if "harmonics" in run_cfg else run_cfg["amplitude"]
        assert run_amp > walk_amp

    def test_run_shorter_frame_count(self):
        assert BIPED_RUN_CONFIG["frame_count"] < BIPED_WALK_CONFIG["frame_count"]

    def test_walk_all_bones_def_prefixed(self):
        for bone in BIPED_WALK_CONFIG["bones"]:
            assert bone.startswith("DEF-"), f"Bone not DEF-prefixed: {bone}"

    def test_walk_cycle_loops(self):
        kfs = generate_cycle_keyframes(BIPED_WALK_CONFIG)
        fc = BIPED_WALK_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestQuadrupedConfigs
# ---------------------------------------------------------------------------


class TestQuadrupedConfigs:
    """Test quadruped 4-beat walk configuration (P2-A10)."""

    def test_walk_has_four_leg_bones(self):
        bones = QUADRUPED_WALK_CONFIG["bones"]
        leg_bones = [b for b in bones if any(
            x in b for x in ["thigh", "shin", "upper_arm", "forearm"]
        ) and "spine" not in b]
        # Should have 8 leg bones (4 upper + 4 lower)
        assert len(leg_bones) >= 4

    def test_walk_4beat_phases(self):
        """4-beat walk: LH=0, LF=pi/2, RH=pi, RF=3pi/2."""
        bones = QUADRUPED_WALK_CONFIG["bones"]
        assert bones["DEF-thigh.L"]["phase"] == pytest.approx(0.0, abs=1e-6)
        assert bones["DEF-upper_arm.L"]["phase"] == pytest.approx(math.pi / 2, abs=1e-6)
        assert bones["DEF-thigh.R"]["phase"] == pytest.approx(math.pi, abs=1e-6)
        assert bones["DEF-upper_arm.R"]["phase"] == pytest.approx(3 * math.pi / 2, abs=1e-6)

    def test_walk_frame_count_32(self):
        assert QUADRUPED_WALK_CONFIG["frame_count"] == 32

    def test_walk_amplitude_05(self):
        bones = QUADRUPED_WALK_CONFIG["bones"]
        assert bones["DEF-thigh.L"]["amplitude"] == pytest.approx(0.5)

    def test_walk_shin_phase_delay(self):
        """Shins have +0.5 phase delay from their thighs."""
        bones = QUADRUPED_WALK_CONFIG["bones"]
        assert bones["DEF-shin.L"]["phase"] == pytest.approx(0.5, abs=1e-6)

    def test_run_backward_compat_alias(self):
        """QUADRUPED_RUN_CONFIG should be QUADRUPED_GALLOP_CONFIG."""
        assert QUADRUPED_RUN_CONFIG is QUADRUPED_GALLOP_CONFIG

    def test_run_higher_amplitude_than_walk(self):
        walk_amp = QUADRUPED_WALK_CONFIG["bones"]["DEF-upper_arm.L"]["amplitude"]
        run_amp = QUADRUPED_RUN_CONFIG["bones"]["DEF-upper_arm.L"]["amplitude"]
        assert run_amp > walk_amp

    def test_spine_undulation_present(self):
        bones = QUADRUPED_WALK_CONFIG["bones"]
        spine_bones = [b for b in bones if b.startswith("DEF-spine")]
        assert len(spine_bones) >= 2

    def test_walk_cycle_loops(self):
        kfs = generate_cycle_keyframes(QUADRUPED_WALK_CONFIG)
        fc = QUADRUPED_WALK_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestQuadrupedTrotConfig
# ---------------------------------------------------------------------------


class TestQuadrupedTrotConfig:
    """Test quadruped trot configuration (diagonal pairs)."""

    def test_trot_frame_count_24(self):
        assert QUADRUPED_TROT_CONFIG["frame_count"] == 24

    def test_trot_name(self):
        assert QUADRUPED_TROT_CONFIG["name"] == "quadruped_trot"

    def test_trot_diagonal_pair_phasing(self):
        """Front-left and rear-right should be in phase."""
        bones = QUADRUPED_TROT_CONFIG["bones"]
        fl_phase = bones["DEF-upper_arm.L"]["phase"]
        rr_phase = bones["DEF-thigh.R"]["phase"]
        assert fl_phase == pytest.approx(rr_phase, abs=1e-6)

    def test_trot_opposite_diagonal_antiphase(self):
        """Diagonal pair B should be pi offset from pair A."""
        bones = QUADRUPED_TROT_CONFIG["bones"]
        fl_phase = bones["DEF-upper_arm.L"]["phase"]
        fr_phase = bones["DEF-upper_arm.R"]["phase"]
        diff = abs(fr_phase - fl_phase)
        assert diff == pytest.approx(math.pi, abs=1e-6)

    def test_trot_cycle_loops(self):
        kfs = generate_cycle_keyframes(QUADRUPED_TROT_CONFIG)
        fc = QUADRUPED_TROT_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestQuadrupedCanterConfig
# ---------------------------------------------------------------------------


class TestQuadrupedCanterConfig:
    """Test quadruped canter configuration (3-beat asymmetric)."""

    def test_canter_frame_count_20(self):
        assert QUADRUPED_CANTER_CONFIG["frame_count"] == 20

    def test_canter_name(self):
        assert QUADRUPED_CANTER_CONFIG["name"] == "quadruped_canter"

    def test_canter_3beat_phases(self):
        """RH=0, LH+RF=2pi/3, LF=4pi/3."""
        bones = QUADRUPED_CANTER_CONFIG["bones"]
        assert bones["DEF-thigh.R"]["phase"] == pytest.approx(0.0, abs=1e-6)
        assert bones["DEF-thigh.L"]["phase"] == pytest.approx(2 * math.pi / 3, abs=1e-6)
        assert bones["DEF-upper_arm.R"]["phase"] == pytest.approx(2 * math.pi / 3, abs=1e-6)
        assert bones["DEF-upper_arm.L"]["phase"] == pytest.approx(4 * math.pi / 3, abs=1e-6)

    def test_canter_amplitude_06(self):
        bones = QUADRUPED_CANTER_CONFIG["bones"]
        assert bones["DEF-thigh.R"]["amplitude"] == pytest.approx(0.6)

    def test_canter_spine_on_axis_0(self):
        bones = QUADRUPED_CANTER_CONFIG["bones"]
        assert bones["DEF-spine.001"]["axis"] == 0

    def test_canter_cycle_loops(self):
        kfs = generate_cycle_keyframes(QUADRUPED_CANTER_CONFIG)
        fc = QUADRUPED_CANTER_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestQuadrupedGallopConfig
# ---------------------------------------------------------------------------


class TestQuadrupedGallopConfig:
    """Test quadruped gallop configuration (4-beat fastest)."""

    def test_gallop_frame_count_16(self):
        assert QUADRUPED_GALLOP_CONFIG["frame_count"] == 16

    def test_gallop_name(self):
        assert QUADRUPED_GALLOP_CONFIG["name"] == "quadruped_gallop"

    def test_gallop_4beat_phases(self):
        """RH=0, LH=pi/3, RF=2pi/3, LF=pi."""
        bones = QUADRUPED_GALLOP_CONFIG["bones"]
        assert bones["DEF-thigh.R"]["phase"] == pytest.approx(0.0, abs=1e-6)
        assert bones["DEF-thigh.L"]["phase"] == pytest.approx(math.pi / 3, abs=1e-6)
        assert bones["DEF-upper_arm.R"]["phase"] == pytest.approx(2 * math.pi / 3, abs=1e-6)
        assert bones["DEF-upper_arm.L"]["phase"] == pytest.approx(math.pi, abs=1e-6)

    def test_gallop_highest_amplitude(self):
        """Gallop should have amplitude 0.9 (highest of all quadruped gaits)."""
        bones = QUADRUPED_GALLOP_CONFIG["bones"]
        assert bones["DEF-thigh.R"]["amplitude"] == pytest.approx(0.9)

    def test_gallop_larger_spine_amplitude(self):
        bones = QUADRUPED_GALLOP_CONFIG["bones"]
        assert bones["DEF-spine.001"]["amplitude"] == pytest.approx(0.1)

    def test_gallop_cycle_loops(self):
        kfs = generate_cycle_keyframes(QUADRUPED_GALLOP_CONFIG)
        fc = QUADRUPED_GALLOP_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestHexapodConfigs
# ---------------------------------------------------------------------------


class TestHexapodConfigs:
    """Test hexapod (insect) walk and run configurations."""

    def test_walk_has_six_upper_leg_bones(self):
        bones = HEXAPOD_WALK_CONFIG["bones"]
        upper_legs = [b for b in bones if b.startswith("DEF-leg_") and "lower" not in b and "foot" not in b]
        assert len(upper_legs) == 6

    def test_alternating_tripod_phasing(self):
        """Tripod A (front.L, mid.R, rear.L) phase 0; Tripod B at pi."""
        bones = HEXAPOD_WALK_CONFIG["bones"]
        tripod_a_phase = bones["DEF-leg_front.L"]["phase"]
        assert bones["DEF-leg_mid.R"]["phase"] == pytest.approx(tripod_a_phase)
        assert bones["DEF-leg_rear.L"]["phase"] == pytest.approx(tripod_a_phase)

        tripod_b_phase = bones["DEF-leg_front.R"]["phase"]
        assert bones["DEF-leg_mid.L"]["phase"] == pytest.approx(tripod_b_phase)
        assert bones["DEF-leg_rear.R"]["phase"] == pytest.approx(tripod_b_phase)

        diff = abs(tripod_b_phase - tripod_a_phase)
        assert diff == pytest.approx(math.pi, abs=1e-6)

    def test_run_higher_amplitude(self):
        walk_amp = HEXAPOD_WALK_CONFIG["bones"]["DEF-leg_front.L"]["amplitude"]
        run_amp = HEXAPOD_RUN_CONFIG["bones"]["DEF-leg_front.L"]["amplitude"]
        assert run_amp > walk_amp

    def test_walk_cycle_loops(self):
        kfs = generate_cycle_keyframes(HEXAPOD_WALK_CONFIG)
        fc = HEXAPOD_WALK_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestArachnidConfigs
# ---------------------------------------------------------------------------


class TestArachnidConfigs:
    """Test arachnid (8-legged) walk and run configurations."""

    def test_walk_has_eight_upper_leg_bones(self):
        bones = ARACHNID_WALK_CONFIG["bones"]
        upper_legs = [b for b in bones if b.startswith("DEF-leg_") and "lower" not in b and "foot" not in b]
        assert len(upper_legs) == 8

    def test_four_four_alternating_groups(self):
        """Group A (1L, 2R, 3L, 4R) at phase 0; Group B at pi."""
        bones = ARACHNID_WALK_CONFIG["bones"]
        group_a = ["DEF-leg_1.L", "DEF-leg_2.R", "DEF-leg_3.L", "DEF-leg_4.R"]
        group_b = ["DEF-leg_1.R", "DEF-leg_2.L", "DEF-leg_3.R", "DEF-leg_4.L"]

        phase_a = bones[group_a[0]]["phase"]
        for name in group_a:
            assert bones[name]["phase"] == pytest.approx(phase_a)

        phase_b = bones[group_b[0]]["phase"]
        for name in group_b:
            assert bones[name]["phase"] == pytest.approx(phase_b)

        assert abs(phase_b - phase_a) == pytest.approx(math.pi, abs=1e-6)

    def test_run_higher_amplitude(self):
        walk_amp = ARACHNID_WALK_CONFIG["bones"]["DEF-leg_1.L"]["amplitude"]
        run_amp = ARACHNID_RUN_CONFIG["bones"]["DEF-leg_1.L"]["amplitude"]
        assert run_amp > walk_amp

    def test_walk_cycle_loops(self):
        kfs = generate_cycle_keyframes(ARACHNID_WALK_CONFIG)
        fc = ARACHNID_WALK_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone

    def test_walk_upper_legs_axis_2(self):
        """Upper leg bones (not _lower) should use axis 2 for arachnid."""
        bones = ARACHNID_WALK_CONFIG["bones"]
        upper_legs = [b for b in bones if b.startswith("DEF-leg_") and "lower" not in b]
        for bone_name in upper_legs:
            assert bones[bone_name]["axis"] == 2, (
                f"{bone_name} should be axis 2, got {bones[bone_name]['axis']}"
            )

    def test_walk_lower_legs_axis_0(self):
        """Lower leg bones (_lower) should stay on axis 0."""
        bones = ARACHNID_WALK_CONFIG["bones"]
        lower_legs = [b for b in bones if "lower" in b]
        for bone_name in lower_legs:
            assert bones[bone_name]["axis"] == 0, (
                f"{bone_name} should be axis 0, got {bones[bone_name]['axis']}"
            )

    def test_run_upper_legs_axis_2(self):
        """Upper leg bones in run config should also use axis 2."""
        bones = ARACHNID_RUN_CONFIG["bones"]
        upper_legs = [b for b in bones if b.startswith("DEF-leg_") and "lower" not in b]
        for bone_name in upper_legs:
            assert bones[bone_name]["axis"] == 2, (
                f"{bone_name} should be axis 2, got {bones[bone_name]['axis']}"
            )

    def test_run_lower_legs_axis_0(self):
        """Lower leg bones in run config should stay on axis 0."""
        bones = ARACHNID_RUN_CONFIG["bones"]
        lower_legs = [b for b in bones if "lower" in b]
        for bone_name in lower_legs:
            assert bones[bone_name]["axis"] == 0, (
                f"{bone_name} should be axis 0, got {bones[bone_name]['axis']}"
            )


# ---------------------------------------------------------------------------
# TestSerpentConfigs
# ---------------------------------------------------------------------------


class TestSerpentConfigs:
    """Test serpent (no legs, wave propagation) configs."""

    def test_walk_uses_spine_chain(self):
        bones = SERPENT_WALK_CONFIG["bones"]
        spine_bones = [b for b in bones if b.startswith("DEF-spine")]
        assert len(spine_bones) >= 6, "Serpent needs long spine chain"

    def test_no_leg_bones(self):
        bones = SERPENT_WALK_CONFIG["bones"]
        leg_bones = [b for b in bones if "thigh" in b or "shin" in b or "leg" in b]
        assert len(leg_bones) == 0, "Serpent should have no leg bones"

    def test_wave_propagation_increasing_phase(self):
        """Each successive spine bone should have increasing phase offset."""
        bones = SERPENT_WALK_CONFIG["bones"]
        spine_names = sorted([b for b in bones if b.startswith("DEF-spine")])
        phases = [bones[name]["phase"] for name in spine_names]
        for i in range(1, len(phases)):
            assert phases[i] > phases[i - 1], (
                f"Phase not increasing: {spine_names[i-1]}={phases[i-1]} >= {spine_names[i]}={phases[i]}"
            )

    def test_run_higher_amplitude(self):
        walk_amp = SERPENT_WALK_CONFIG["bones"]["DEF-spine"]["amplitude"]
        run_amp = SERPENT_RUN_CONFIG["bones"]["DEF-spine"]["amplitude"]
        assert run_amp > walk_amp

    def test_walk_cycle_loops(self):
        kfs = generate_cycle_keyframes(SERPENT_WALK_CONFIG)
        fc = SERPENT_WALK_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestFlyConfig
# ---------------------------------------------------------------------------


class TestFlyConfig:
    """Test fly/hover configuration."""

    def test_has_wing_bones(self):
        bones = FLY_HOVER_CONFIG["bones"]
        wing_bones = [b for b in bones if "wing" in b]
        assert len(wing_bones) >= 4

    def test_has_frequency_amplitude_params(self):
        assert "frequency" in FLY_HOVER_CONFIG
        assert FLY_HOVER_CONFIG["frequency"] > 0

    def test_has_glide_ratio(self):
        assert "glide_ratio" in FLY_HOVER_CONFIG

    def test_has_body_bob(self):
        bones = FLY_HOVER_CONFIG["bones"]
        bob_bones = [b for b in bones if bones[b]["channel"] == "location"]
        assert len(bob_bones) >= 1

    def test_cycle_loops(self):
        kfs = generate_cycle_keyframes(FLY_HOVER_CONFIG)
        fc = FLY_HOVER_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone

    def test_frequency_affects_keyframes(self):
        """Frequency > 1 should produce different values than frequency=1."""
        config_f1 = {
            "name": "freq_test",
            "frame_count": 24,
            "frequency": 1.0,
            "bones": {
                "DEF-wing_upper.L": {
                    "channel": "rotation_euler", "axis": 0,
                    "amplitude": 0.8, "phase": 0.0,
                },
            },
        }
        config_f2 = {
            "name": "freq_test",
            "frame_count": 24,
            "frequency": 2.0,
            "bones": {
                "DEF-wing_upper.L": {
                    "channel": "rotation_euler", "axis": 0,
                    "amplitude": 0.8, "phase": 0.0,
                },
            },
        }
        kfs_f1 = generate_cycle_keyframes(config_f1)
        kfs_f2 = generate_cycle_keyframes(config_f2)

        # At frame 6 (quarter cycle), sin(pi/2)=1.0 for f=1 but sin(pi)=0 for f=2
        val_f1_6 = [kf.value for kf in kfs_f1 if kf.frame == 6][0]
        val_f2_6 = [kf.value for kf in kfs_f2 if kf.frame == 6][0]
        assert val_f1_6 == pytest.approx(0.8, abs=1e-6)  # sin(pi/2) * 0.8
        assert val_f2_6 == pytest.approx(0.0, abs=1e-6)  # sin(pi) * 0.8

    def test_integer_frequency_preserves_loop(self):
        """With integer frequency, frame 0 and frame_count should still match."""
        config = {
            "name": "freq_loop_test",
            "frame_count": 24,
            "frequency": 3.0,
            "bones": {
                "DEF-test": {
                    "channel": "rotation_euler", "axis": 0,
                    "amplitude": 1.0, "phase": 0.5,
                },
            },
        }
        kfs = generate_cycle_keyframes(config)
        by_frame = {kf.frame: kf.value for kf in kfs}
        assert by_frame[0] == pytest.approx(by_frame[24], abs=1e-6)

    def test_fly_config_frequency_is_used(self):
        """FLY_HOVER_CONFIG has frequency=1.0; setting it to 2.0 should change output."""
        config1 = get_gait_config("biped", "fly", frame_count=24)
        config2 = get_gait_config("biped", "fly", frame_count=24)
        config2["frequency"] = 2.0
        kfs1 = generate_cycle_keyframes(config1)
        kfs2 = generate_cycle_keyframes(config2)
        # The keyframes at the same frame should differ for frequency 1 vs 2
        vals1 = {(kf.bone_name, kf.frame): kf.value for kf in kfs1}
        vals2 = {(kf.bone_name, kf.frame): kf.value for kf in kfs2}
        # At frame 6 (quarter cycle), they should differ
        key = ("DEF-wing_upper.L", 6)
        assert vals1[key] != pytest.approx(vals2[key], abs=1e-3)


# ---------------------------------------------------------------------------
# TestIdleConfig
# ---------------------------------------------------------------------------


class TestIdleConfig:
    """Test idle/breathing configuration."""

    def test_has_breathing_bones(self):
        bones = IDLE_CONFIG["bones"]
        spine_bones = [b for b in bones if b.startswith("DEF-spine")]
        assert len(spine_bones) >= 2

    def test_low_amplitude(self):
        for bone_cfg in IDLE_CONFIG["bones"].values():
            assert bone_cfg["amplitude"] < 0.1, "Idle amplitude should be subtle"

    def test_longer_frame_count(self):
        assert IDLE_CONFIG["frame_count"] >= 48

    def test_cycle_loops(self):
        kfs = generate_cycle_keyframes(IDLE_CONFIG)
        fc = IDLE_CONFIG["frame_count"]
        by_bone: dict[str, dict[int, float]] = {}
        for kf in kfs:
            by_bone.setdefault(kf.bone_name, {})[kf.frame] = kf.value
        for bone, frames in by_bone.items():
            assert frames[0] == pytest.approx(frames[fc], abs=1e-6), bone


# ---------------------------------------------------------------------------
# TestGetGaitConfig
# ---------------------------------------------------------------------------


class TestGetGaitConfig:
    """Test the get_gait_config routing function."""

    @pytest.mark.parametrize("gait", ["biped", "quadruped", "hexapod", "arachnid", "serpent"])
    def test_walk_speed_returns_valid(self, gait):
        config = get_gait_config(gait, "walk")
        assert "bones" in config
        assert "frame_count" in config
        assert len(config["bones"]) > 0

    @pytest.mark.parametrize("gait", ["biped", "quadruped", "hexapod", "arachnid", "serpent"])
    def test_run_speed_returns_valid(self, gait):
        config = get_gait_config(gait, "run")
        assert "bones" in config
        assert len(config["bones"]) > 0

    def test_fly_speed_returns_fly_config(self):
        config = get_gait_config("biped", "fly")
        assert config["name"] == "fly_hover"

    def test_idle_speed_returns_idle_config(self):
        config = get_gait_config("biped", "idle")
        assert config["name"] == "idle"

    def test_unknown_gait_raises(self):
        with pytest.raises(ValueError, match="Unknown gait type"):
            get_gait_config("centipede", "walk")

    def test_unknown_speed_raises(self):
        with pytest.raises(ValueError, match="Unknown speed"):
            get_gait_config("biped", "gallop")

    def test_frame_count_override(self):
        config = get_gait_config("biped", "walk", frame_count=32)
        assert config["frame_count"] == 32

    def test_bone_name_filtering(self):
        config = get_gait_config(
            "biped", "walk",
            bone_names=["DEF-thigh.L", "DEF-thigh.R"],
        )
        assert set(config["bones"].keys()) == {"DEF-thigh.L", "DEF-thigh.R"}

    def test_returns_copy_not_original(self):
        config1 = get_gait_config("biped", "walk")
        config2 = get_gait_config("biped", "walk")
        config1["frame_count"] = 999
        assert config2["frame_count"] != 999

    def test_fly_ignores_gait_type(self):
        """fly speed returns FLY_HOVER_CONFIG regardless of gait."""
        for gait in ["biped", "quadruped", "hexapod", "arachnid", "serpent"]:
            config = get_gait_config(gait, "fly")
            assert config["name"] == "fly_hover"


# ---------------------------------------------------------------------------
# TestAttackKeyframes
# ---------------------------------------------------------------------------


class TestAttackKeyframes:
    """Test attack keyframe generation."""

    @pytest.mark.parametrize("attack_type", [
        "melee_swing", "thrust", "slam", "bite",
        "claw", "tail_whip", "wing_buffet", "breath_attack",
    ])
    def test_attack_returns_keyframes(self, attack_type):
        kfs = generate_attack_keyframes(attack_type)
        assert isinstance(kfs, list)
        assert len(kfs) > 0
        assert all(isinstance(kf, Keyframe) for kf in kfs)

    def test_unknown_attack_raises(self):
        with pytest.raises(ValueError, match="Unknown attack type"):
            generate_attack_keyframes("laser_eyes")

    def test_three_phase_timing(self):
        """Verify attack uses 3 phases: anticipation/strike/recovery."""
        config = ATTACK_CONFIGS["melee_swing"]
        phases = config["phases"]
        assert len(phases) == 3
        # Phase boundaries: 0->0.2, 0.2->0.5, 0.5->1.0
        assert phases[0]["start_pct"] == pytest.approx(0.0)
        assert phases[0]["end_pct"] == pytest.approx(0.2)
        assert phases[1]["start_pct"] == pytest.approx(0.2)
        assert phases[1]["end_pct"] == pytest.approx(0.5)
        assert phases[2]["start_pct"] == pytest.approx(0.5)
        assert phases[2]["end_pct"] == pytest.approx(1.0)

    def test_intensity_scaling(self):
        """intensity=2.0 should double all values."""
        kfs_normal = generate_attack_keyframes("melee_swing", frame_count=24, intensity=1.0)
        kfs_double = generate_attack_keyframes("melee_swing", frame_count=24, intensity=2.0)

        # Get a non-zero value from the middle of the strike phase
        normal_mid = [kf for kf in kfs_normal if kf.frame == 12 and kf.bone_name == "DEF-upper_arm.R"]
        double_mid = [kf for kf in kfs_double if kf.frame == 12 and kf.bone_name == "DEF-upper_arm.R"]

        assert len(normal_mid) > 0 and len(double_mid) > 0
        assert double_mid[0].value == pytest.approx(normal_mid[0].value * 2.0, abs=1e-6)

    def test_half_intensity(self):
        kfs_normal = generate_attack_keyframes("slam", frame_count=24, intensity=1.0)
        kfs_half = generate_attack_keyframes("slam", frame_count=24, intensity=0.5)

        normal_vals = {(kf.bone_name, kf.frame): kf.value for kf in kfs_normal}
        half_vals = {(kf.bone_name, kf.frame): kf.value for kf in kfs_half}

        # Check a sampling of values
        for key in list(normal_vals.keys())[:5]:
            if normal_vals[key] != 0.0:
                assert half_vals[key] == pytest.approx(normal_vals[key] * 0.5, abs=1e-6)

    def test_melee_swing_uses_arm_bones(self):
        kfs = generate_attack_keyframes("melee_swing")
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-upper_arm.R" in bone_names
        assert "DEF-forearm.R" in bone_names

    def test_bite_uses_jaw(self):
        kfs = generate_attack_keyframes("bite")
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-jaw" in bone_names

    def test_tail_whip_uses_tail_chain(self):
        kfs = generate_attack_keyframes("tail_whip")
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-tail" in bone_names
        assert "DEF-tail.001" in bone_names
        assert "DEF-tail.002" in bone_names
        assert "DEF-tail.003" in bone_names

    def test_wing_buffet_uses_wing_bones(self):
        kfs = generate_attack_keyframes("wing_buffet")
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-wing_upper.L" in bone_names
        assert "DEF-wing_upper.R" in bone_names

    def test_breath_attack_uses_jaw_and_head(self):
        kfs = generate_attack_keyframes("breath_attack")
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-jaw" in bone_names
        assert "DEF-spine.004" in bone_names

    def test_frame_count_parameter(self):
        kfs_24 = generate_attack_keyframes("melee_swing", frame_count=24)
        kfs_48 = generate_attack_keyframes("melee_swing", frame_count=48)
        # More frames = more keyframes
        assert len(kfs_48) > len(kfs_24)

    def test_all_attack_configs_exist(self):
        # Core 8 original configs plus extended monster attack types
        required = {
            "melee_swing", "thrust", "slam", "bite",
            "claw", "tail_whip", "wing_buffet", "breath_attack",
        }
        actual = set(ATTACK_CONFIGS.keys())
        assert required.issubset(actual), f"Missing attack configs: {required - actual}"

    def test_no_duplicate_keyframes_at_phase_boundaries(self):
        """Each (bone, channel, axis, frame) should appear at most once."""
        kfs = generate_attack_keyframes("melee_swing", frame_count=24)
        seen: set[tuple[str, str, int, int]] = set()
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis, kf.frame)
            assert key not in seen, (
                f"Duplicate keyframe at phase boundary: {key}"
            )
            seen.add(key)

    @pytest.mark.parametrize("attack_type", [
        "melee_swing", "thrust", "slam", "bite",
        "claw", "tail_whip", "wing_buffet", "breath_attack",
    ])
    def test_no_duplicates_any_attack(self, attack_type):
        """No duplicate (bone, frame) keyframes for any attack type."""
        kfs = generate_attack_keyframes(attack_type, frame_count=24)
        seen: set[tuple[str, str, int, int]] = set()
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis, kf.frame)
            assert key not in seen, (
                f"Duplicate in {attack_type} at {key}"
            )
            seen.add(key)

    def test_phase_boundary_continuity(self):
        """Value at end of phase N-1 should equal value at start of phase N."""
        kfs = generate_attack_keyframes("melee_swing", frame_count=24, intensity=1.0)
        by_bone_frame: dict[tuple[str, str, int], dict[int, float]] = {}
        for kf in kfs:
            key = (kf.bone_name, kf.channel, kf.axis)
            by_bone_frame.setdefault(key, {})[kf.frame] = kf.value
        # Phase boundary at frame 5 (20% of 24) and frame 12 (50% of 24)
        # The last frame of the previous phase is frame 4 (not 5), because
        # the fix excludes end_frame for non-final phases.
        # Phase 2 starts at frame 5, but phase 1 ends at frame 4.
        # The start_value of phase 2 for each bone should equal end_value of phase 1.
        # Since we removed duplicates, boundary frame belongs to the next phase.
        config = ATTACK_CONFIGS["melee_swing"]
        for bone_name in config["phases"][0]["bones"]:
            bone_cfg_p1 = config["phases"][0]["bones"][bone_name]
            bone_cfg_p2 = config["phases"][1]["bones"][bone_name]
            # Phase 1 end_value should equal phase 2 start_value
            assert bone_cfg_p1["end_value"] == pytest.approx(
                bone_cfg_p2["start_value"]
            ), f"Discontinuity at phase boundary for {bone_name}"


# ---------------------------------------------------------------------------
# TestReactionKeyframes
# ---------------------------------------------------------------------------


class TestReactionKeyframes:
    """Test reaction keyframe generation (death, hit, spawn)."""

    def test_death_returns_keyframes(self):
        kfs = generate_reaction_keyframes("death")
        assert isinstance(kfs, list)
        assert len(kfs) > 0

    def test_death_produces_collapse(self):
        """Death should rotate spine forward (positive X rotation)."""
        kfs = generate_reaction_keyframes("death", frame_count=24)
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine" and kf.frame == 24]
        assert len(spine_kfs) == 1
        assert spine_kfs[0].value > 0, "Spine should collapse forward"

    def test_hit_returns_keyframes(self):
        kfs = generate_reaction_keyframes("hit", direction="front")
        assert len(kfs) > 0

    @pytest.mark.parametrize("direction", ["front", "back", "left", "right"])
    def test_hit_directions(self, direction):
        kfs = generate_reaction_keyframes("hit", direction=direction, frame_count=24)
        assert len(kfs) > 0
        # Should include directional spine.001 keyframes
        dir_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert len(dir_kfs) > 0, f"No directional keyframes for direction={direction}"

    def test_hit_front_tilts_back(self):
        kfs = generate_reaction_keyframes("hit", direction="front", frame_count=24)
        # Peak at ~20% of frames (frame ~5)
        peak_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001" and kf.frame == 5]
        assert len(peak_kfs) > 0
        # Front hit = positive X rotation (tilt back)
        assert peak_kfs[0].value > 0

    def test_hit_without_direction(self):
        """Hit without direction should still produce base keyframes."""
        kfs = generate_reaction_keyframes("hit")
        assert len(kfs) > 0
        # Should have base bones but no directional spine.001
        dir_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine.001"]
        assert len(dir_kfs) == 0

    def test_spawn_returns_keyframes(self):
        kfs = generate_reaction_keyframes("spawn", frame_count=24)
        assert len(kfs) > 0

    def test_spawn_starts_compressed_ends_neutral(self):
        """Spawn should start curled (high values) and end at neutral (0)."""
        kfs = generate_reaction_keyframes("spawn", frame_count=24)
        spine_kfs = [kf for kf in kfs if kf.bone_name == "DEF-spine"]
        frame_0 = [kf for kf in spine_kfs if kf.frame == 0]
        frame_end = [kf for kf in spine_kfs if kf.frame == 24]
        assert len(frame_0) == 1 and len(frame_end) == 1
        assert abs(frame_0[0].value) > abs(frame_end[0].value)
        assert frame_end[0].value == pytest.approx(0.0, abs=1e-6)

    def test_unknown_reaction_raises(self):
        with pytest.raises(ValueError, match="Unknown reaction type"):
            generate_reaction_keyframes("explode")

    def test_death_ignores_direction(self):
        kfs1 = generate_reaction_keyframes("death", direction="front")
        kfs2 = generate_reaction_keyframes("death", direction=None)
        assert len(kfs1) == len(kfs2)

    def test_all_3_reaction_configs_exist(self):
        assert set(REACTION_CONFIGS.keys()) == {"death", "hit", "spawn"}


# ---------------------------------------------------------------------------
# TestCustomKeyframes
# ---------------------------------------------------------------------------


class TestCustomKeyframes:
    """Test text-to-keyframe custom animation mapper."""

    def test_raise_wings(self):
        kfs = generate_custom_keyframes("raise wings")
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert any("wing" in b for b in bone_names)

    def test_swing_arms(self):
        kfs = generate_custom_keyframes("swing arms")
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert any("arm" in b for b in bone_names)

    def test_multi_action_sequence(self):
        kfs = generate_custom_keyframes("raise wings then swing arms")
        assert len(kfs) > 0
        # Should have both wing and arm bones
        bone_names = {kf.bone_name for kf in kfs}
        assert any("wing" in b for b in bone_names)
        assert any("arm" in b for b in bone_names)

    def test_open_jaw(self):
        kfs = generate_custom_keyframes("open jaw")
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert "DEF-jaw" in bone_names

    def test_curl_tail(self):
        kfs = generate_custom_keyframes("curl tail")
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert any("tail" in b for b in bone_names)

    def test_nod_head(self):
        kfs = generate_custom_keyframes("nod head")
        assert len(kfs) > 0
        bone_names = {kf.bone_name for kf in kfs}
        assert any("spine.004" in b or "spine.005" in b for b in bone_names)

    def test_empty_description(self):
        kfs = generate_custom_keyframes("")
        assert kfs == []

    def test_nonsense_description(self):
        kfs = generate_custom_keyframes("xyzzy plugh")
        assert kfs == []

    def test_frame_count_parameter(self):
        kfs_48 = generate_custom_keyframes("raise wings", frame_count=48)
        kfs_96 = generate_custom_keyframes("raise wings", frame_count=96)
        assert len(kfs_96) > len(kfs_48)

    def test_bell_curve_shape(self):
        """Values should ramp up then back down within an action segment."""
        kfs = generate_custom_keyframes("raise wings", frame_count=48)
        # Filter to one bone
        bone_kfs = [kf for kf in kfs if kf.bone_name == "DEF-wing_upper.L"]
        assert len(bone_kfs) > 0
        # First and last should be near zero
        assert bone_kfs[0].value == pytest.approx(0.0, abs=1e-6)
        assert bone_kfs[-1].value == pytest.approx(0.0, abs=1e-6)
        # Middle should have peak value
        mid_idx = len(bone_kfs) // 2
        assert abs(bone_kfs[mid_idx].value) > 0

    def test_comma_separated_actions(self):
        kfs = generate_custom_keyframes("raise wings, stomp feet")
        bone_names = {kf.bone_name for kf in kfs}
        assert any("wing" in b for b in bone_names)
        assert any("foot" in b for b in bone_names)

    def test_and_connector(self):
        kfs = generate_custom_keyframes("nod head and wave arm")
        bone_names = {kf.bone_name for kf in kfs}
        assert any("spine.004" in b or "spine.005" in b for b in bone_names)
        assert any("arm" in b for b in bone_names)


# ---------------------------------------------------------------------------
# TestNoBlenderImports
# ---------------------------------------------------------------------------


class TestNoBlenderImports:
    """Verify the module has no Blender dependency."""

    def test_no_bpy_import(self):
        import inspect
        import blender_addon.handlers.animation_gaits as mod
        source = inspect.getsource(mod)
        # Should not have 'import bpy' anywhere
        assert "import bpy" not in source

    def test_no_bmesh_import(self):
        import inspect
        import blender_addon.handlers.animation_gaits as mod
        source = inspect.getsource(mod)
        assert "import bmesh" not in source

    def test_no_mathutils_import(self):
        import inspect
        import blender_addon.handlers.animation_gaits as mod
        source = inspect.getsource(mod)
        assert "import mathutils" not in source
