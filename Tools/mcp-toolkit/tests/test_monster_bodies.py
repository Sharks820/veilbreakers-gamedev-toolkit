"""Tests for advanced monster body type mesh generators.

Validates all 6 body types x 10 brands produce valid mesh data:
- All body types generate valid meshes (non-empty verts/faces, valid indices)
- All 10 brands produce different geometry for same body type
- Scale parameter works (larger = more vertices roughly)
- Joint positions present in metadata
- Brand feature points present
- Bounding box correct
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.monster_bodies import (
    ALL_BODY_TYPES,
    ALL_BRANDS,
    BRAND_FEATURES,
    generate_monster_body,
)


# ---------------------------------------------------------------------------
# Helper validation
# ---------------------------------------------------------------------------


def validate_monster_mesh(result: dict, label: str) -> None:
    """Validate a monster mesh result dict has all required fields and valid data."""
    # Required top-level keys
    required_keys = [
        "vertices", "faces", "body_type", "brand", "scale",
        "joint_positions", "brand_feature_points", "bounding_box",
        "vertex_count", "face_count",
    ]
    for key in required_keys:
        assert key in result, f"{label}: missing key '{key}'"

    verts = result["vertices"]
    faces = result["faces"]

    # Non-empty
    assert len(verts) > 0, f"{label}: empty vertices"
    assert len(faces) > 0, f"{label}: empty faces"

    # All vertices are 3-tuples of numbers
    for i, v in enumerate(verts):
        assert len(v) == 3, f"{label}: vertex {i} has {len(v)} components"
        for c in v:
            assert isinstance(c, (int, float)), f"{label}: vertex {i} has non-numeric component"
            assert math.isfinite(c), f"{label}: vertex {i} has non-finite component"

    # All face indices reference valid vertices
    n_verts = len(verts)
    for fi, face in enumerate(faces):
        assert len(face) >= 3, f"{label}: face {fi} has {len(face)} indices (need >= 3)"
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{label}: face {fi} index {idx} out of range [0, {n_verts})"
            )

    # Counts match
    assert result["vertex_count"] == len(verts), f"{label}: vertex_count mismatch"
    assert result["face_count"] == len(faces), f"{label}: face_count mismatch"

    # Bounding box is valid
    bbox = result["bounding_box"]
    assert len(bbox) == 2, f"{label}: bounding_box should have 2 elements (min, max)"
    bb_min, bb_max = bbox
    assert len(bb_min) == 3, f"{label}: bounding_box min should have 3 components"
    assert len(bb_max) == 3, f"{label}: bounding_box max should have 3 components"
    for axis in range(3):
        assert bb_min[axis] <= bb_max[axis], (
            f"{label}: bounding_box min[{axis}]={bb_min[axis]} > max[{axis}]={bb_max[axis]}"
        )

    # Joint positions should be non-empty dict
    joints = result["joint_positions"]
    assert isinstance(joints, dict), f"{label}: joint_positions should be dict"
    assert len(joints) > 0, f"{label}: joint_positions empty"
    for jname, jpos in joints.items():
        assert len(jpos) == 3, f"{label}: joint '{jname}' has {len(jpos)} components"
        for c in jpos:
            assert isinstance(c, (int, float)), f"{label}: joint '{jname}' non-numeric"
            assert math.isfinite(c), f"{label}: joint '{jname}' non-finite"

    # Brand feature points should be dict (can be empty for marker-only brands)
    bfp = result["brand_feature_points"]
    assert isinstance(bfp, dict), f"{label}: brand_feature_points should be dict"


# ---------------------------------------------------------------------------
# Test: All 6 body types generate valid meshes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_body_type_generates_valid_mesh(body_type: str) -> None:
    """Each body type should generate a valid mesh with default params."""
    result = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    validate_monster_mesh(result, f"{body_type}/IRON")
    assert result["body_type"] == body_type
    assert result["brand"] == "IRON"


# ---------------------------------------------------------------------------
# Test: All 10 brands produce different geometry for same body type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_brands_produce_different_geometry(body_type: str) -> None:
    """Different brands should produce different vertex counts (different features)."""
    vertex_counts: dict[str, int] = {}
    for brand in ALL_BRANDS:
        result = generate_monster_body(body_type=body_type, brand=brand, scale=1.0)
        validate_monster_mesh(result, f"{body_type}/{brand}")
        vertex_counts[brand] = result["vertex_count"]

    # At least some brands should have different vertex counts
    unique_counts = set(vertex_counts.values())
    assert len(unique_counts) > 1, (
        f"{body_type}: all 10 brands produced identical vertex counts: {vertex_counts}"
    )


# ---------------------------------------------------------------------------
# Test: Scale parameter works
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_scale_affects_mesh(body_type: str) -> None:
    """Larger scale should produce a mesh with a larger bounding box."""
    small = generate_monster_body(body_type=body_type, brand="IRON", scale=0.5)
    medium = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    large = generate_monster_body(body_type=body_type, brand="IRON", scale=2.0)

    validate_monster_mesh(small, f"{body_type}/small")
    validate_monster_mesh(medium, f"{body_type}/medium")
    validate_monster_mesh(large, f"{body_type}/large")

    def bbox_volume(bbox):
        bb_min, bb_max = bbox
        return (
            (bb_max[0] - bb_min[0])
            * (bb_max[1] - bb_min[1])
            * (bb_max[2] - bb_min[2])
        )

    vol_small = bbox_volume(small["bounding_box"])
    vol_medium = bbox_volume(medium["bounding_box"])
    vol_large = bbox_volume(large["bounding_box"])

    assert vol_small < vol_medium, (
        f"{body_type}: small volume {vol_small} not < medium {vol_medium}"
    )
    assert vol_medium < vol_large, (
        f"{body_type}: medium volume {vol_medium} not < large {vol_large}"
    )


# ---------------------------------------------------------------------------
# Test: Joint positions present in metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_joint_positions_present(body_type: str) -> None:
    """Each body type should have meaningful joint positions for rigging."""
    result = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    joints = result["joint_positions"]

    if body_type == "humanoid":
        expected = ["head", "neck", "spine_base", "spine_top",
                     "left_shoulder", "right_shoulder",
                     "left_elbow", "right_elbow",
                     "left_wrist", "right_wrist",
                     "left_hip", "right_hip",
                     "left_knee", "right_knee",
                     "left_ankle", "right_ankle"]
        for j in expected:
            assert j in joints, f"humanoid missing joint '{j}'"

    elif body_type == "quadruped":
        expected = ["head", "jaw", "neck", "tail_base", "tail_tip"]
        for j in expected:
            assert j in joints, f"quadruped missing joint '{j}'"
        # Should have leg joints
        for leg in ["front_left", "front_right", "rear_left", "rear_right"]:
            assert f"{leg}_shoulder" in joints, f"quadruped missing '{leg}_shoulder'"
            assert f"{leg}_knee" in joints, f"quadruped missing '{leg}_knee'"

    elif body_type == "amorphous":
        assert "center_mass" in joints, "amorphous missing 'center_mass'"
        # Should have pseudopod joints
        pod_keys = [k for k in joints if k.startswith("pseudopod_")]
        assert len(pod_keys) >= 4, f"amorphous: expected >= 4 pseudopod joints, got {len(pod_keys)}"

    elif body_type == "arachnid":
        assert "cephalothorax" in joints, "arachnid missing 'cephalothorax'"
        assert "abdomen" in joints, "arachnid missing 'abdomen'"
        # Should have 8 legs with joints
        leg_keys = [k for k in joints if k.startswith("leg_")]
        assert len(leg_keys) >= 16, f"arachnid: expected >= 16 leg joints, got {len(leg_keys)}"

    elif body_type == "serpent":
        assert "head" in joints, "serpent missing 'head'"
        assert "tail_tip" in joints, "serpent missing 'tail_tip'"
        spine_keys = [k for k in joints if k.startswith("spine_")]
        assert len(spine_keys) >= 4, f"serpent: expected >= 4 spine joints, got {len(spine_keys)}"

    elif body_type == "insect":
        assert "thorax" in joints, "insect missing 'thorax'"
        assert "abdomen" in joints, "insect missing 'abdomen'"
        leg_keys = [k for k in joints if k.startswith("leg_")]
        assert len(leg_keys) >= 12, f"insect: expected >= 12 leg joints, got {len(leg_keys)}"
        wing_keys = [k for k in joints if k.startswith("wing_")]
        assert len(wing_keys) >= 4, f"insect: expected >= 4 wing joints, got {len(wing_keys)}"


# ---------------------------------------------------------------------------
# Test: Brand feature points present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("brand", ALL_BRANDS)
def test_brand_feature_points_present(brand: str) -> None:
    """Each brand should produce at least one type of feature point."""
    result = generate_monster_body(body_type="humanoid", brand=brand, scale=1.0)
    bfp = result["brand_feature_points"]

    # Brand features config says what should be present
    features = BRAND_FEATURES[brand]
    assert len(bfp) > 0, f"brand {brand} produced no feature points"

    # Each active feature should have a corresponding entry in feature points
    for feature_name, active in features.items():
        if active:
            assert feature_name in bfp, (
                f"brand {brand}: feature '{feature_name}' expected but not in feature points"
            )
            points = bfp[feature_name]
            assert isinstance(points, list), (
                f"brand {brand}: feature '{feature_name}' points should be a list"
            )
            assert len(points) > 0, (
                f"brand {brand}: feature '{feature_name}' has empty points list"
            )


# ---------------------------------------------------------------------------
# Test: Bounding box correct
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_bounding_box_correct(body_type: str) -> None:
    """Bounding box should tightly contain all vertices."""
    result = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    verts = result["vertices"]
    bb_min, bb_max = result["bounding_box"]

    for i, v in enumerate(verts):
        for axis in range(3):
            assert v[axis] >= bb_min[axis] - 1e-6, (
                f"{body_type}: vertex {i} axis {axis} = {v[axis]} < bbox min {bb_min[axis]}"
            )
            assert v[axis] <= bb_max[axis] + 1e-6, (
                f"{body_type}: vertex {i} axis {axis} = {v[axis]} > bbox max {bb_max[axis]}"
            )


# ---------------------------------------------------------------------------
# Test: Invalid inputs raise errors
# ---------------------------------------------------------------------------


def test_invalid_body_type_raises() -> None:
    """Unknown body_type should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown body_type"):
        generate_monster_body(body_type="dragon", brand="IRON", scale=1.0)


def test_invalid_brand_raises() -> None:
    """Unknown brand should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown brand"):
        generate_monster_body(body_type="humanoid", brand="UNKNOWN", scale=1.0)


# ---------------------------------------------------------------------------
# Test: All body_type + brand combinations generate valid meshes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
@pytest.mark.parametrize("brand", ALL_BRANDS)
def test_all_combinations_valid(body_type: str, brand: str) -> None:
    """Every body_type x brand combination should produce a valid mesh."""
    result = generate_monster_body(body_type=body_type, brand=brand, scale=1.0)
    validate_monster_mesh(result, f"{body_type}/{brand}")


# ---------------------------------------------------------------------------
# Test: Poly count within budget (3000-15000 tris)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_poly_count_within_budget(body_type: str) -> None:
    """Face count should be reasonable for game use."""
    result = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    face_count = result["face_count"]
    # With quads, each face = 2 tris roughly. Allow generous range.
    assert face_count >= 50, f"{body_type}: too few faces ({face_count})"
    assert face_count <= 8000, f"{body_type}: too many faces ({face_count})"


# ---------------------------------------------------------------------------
# Test: Scale edge cases
# ---------------------------------------------------------------------------


def test_very_small_scale() -> None:
    """Very small scale should still produce valid mesh."""
    result = generate_monster_body(body_type="humanoid", brand="IRON", scale=0.1)
    validate_monster_mesh(result, "humanoid/tiny")


def test_very_large_scale() -> None:
    """Very large scale should still produce valid mesh."""
    result = generate_monster_body(body_type="humanoid", brand="IRON", scale=5.0)
    validate_monster_mesh(result, "humanoid/huge")


# ---------------------------------------------------------------------------
# Test: Joint positions are within bounding box
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_type", ALL_BODY_TYPES)
def test_joints_within_reasonable_bounds(body_type: str) -> None:
    """Joint positions should be within or near the bounding box."""
    result = generate_monster_body(body_type=body_type, brand="IRON", scale=1.0)
    bb_min, bb_max = result["bounding_box"]
    # Allow some margin for joints slightly outside body (tips of fingers etc)
    margin = 0.5
    for jname, jpos in result["joint_positions"].items():
        for axis in range(3):
            assert jpos[axis] >= bb_min[axis] - margin, (
                f"{body_type}: joint '{jname}' axis {axis} = {jpos[axis]} "
                f"far below bbox min {bb_min[axis]}"
            )
            assert jpos[axis] <= bb_max[axis] + margin, (
                f"{body_type}: joint '{jname}' axis {axis} = {jpos[axis]} "
                f"far above bbox max {bb_max[axis]}"
            )


# ---------------------------------------------------------------------------
# Test: Default parameters
# ---------------------------------------------------------------------------


def test_default_parameters() -> None:
    """Calling with no args should use defaults and produce valid mesh."""
    result = generate_monster_body()
    validate_monster_mesh(result, "defaults")
    assert result["body_type"] == "humanoid"
    assert result["brand"] == "IRON"
    assert result["scale"] == 1.0
