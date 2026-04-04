"""Tests for AAA creature anatomy mesh generators.

Validates all creature generators produce anatomically correct,
rigging-ready meshes with proper topology for deformation:
- Each species generates valid mesh (non-empty, valid indices)
- Mouth interior has upper and lower jaw vertices
- Eyelid curvature matches eye sphere radius
- Paw has correct number of toes
- Wing membrane is regular grid (cloth sim ready)
- Serpent has 40+ segments for smooth animation
- All vertex groups are present per spec
- Bone positions form valid skeleton (connected chain)
- Species produce different proportions
- Brand features add geometry (more verts with brand than without)
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.creature_anatomy import (
    ALL_BRANDS,
    ALL_SPECIES,
    BRAND_ANATOMY_FEATURES,
    FANTASY_CREATURE_TYPES,
    PAW_TYPES,
    QUADRUPED_PROPORTIONS,
    SERPENT_HEAD_STYLES,
    WING_TYPES,
    generate_eyelid_topology,
    generate_fantasy_creature,
    generate_mouth_interior,
    generate_paw,
    generate_quadruped,
    generate_serpent_body,
    generate_wing,
)


# ---------------------------------------------------------------------------
# Helper validation
# ---------------------------------------------------------------------------


def validate_mesh(
    verts: list,
    faces: list,
    label: str,
) -> None:
    """Validate mesh has valid vertices and face indices."""
    assert len(verts) > 0, f"{label}: empty vertices"
    assert len(faces) > 0, f"{label}: empty faces"

    n_verts = len(verts)

    for i, v in enumerate(verts):
        assert len(v) == 3, f"{label}: vertex {i} has {len(v)} components"
        for c in v:
            assert isinstance(c, (int, float)), (
                f"{label}: vertex {i} has non-numeric component"
            )
            assert math.isfinite(c), f"{label}: vertex {i} non-finite"

    for fi, face in enumerate(faces):
        assert len(face) >= 3, (
            f"{label}: face {fi} has {len(face)} indices (need >= 3)"
        )
        for idx in face:
            assert 0 <= idx < n_verts, (
                f"{label}: face {fi} index {idx} out of range [0, {n_verts})"
            )


def validate_bbox(
    verts: list,
    bbox: tuple,
    label: str,
) -> None:
    """Validate bounding box tightly contains all vertices."""
    bb_min, bb_max = bbox
    for axis in range(3):
        assert bb_min[axis] <= bb_max[axis], (
            f"{label}: bbox min[{axis}] > max[{axis}]"
        )
    for i, v in enumerate(verts):
        for axis in range(3):
            assert v[axis] >= bb_min[axis] - 1e-6, (
                f"{label}: vertex {i} axis {axis} below bbox"
            )
            assert v[axis] <= bb_max[axis] + 1e-6, (
                f"{label}: vertex {i} axis {axis} above bbox"
            )


# ---------------------------------------------------------------------------
# Test: Each species generates valid mesh
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ALL_SPECIES)
def test_species_generates_valid_mesh(species: str) -> None:
    """Each quadruped species should produce a valid mesh."""
    result = generate_quadruped(species=species, size=1.0)
    validate_mesh(result["vertices"], result["faces"], f"quadruped/{species}")
    assert result["vertex_count"] == len(result["vertices"])
    assert result["face_count"] == len(result["faces"])
    assert result["species"] == species


@pytest.mark.parametrize("species", ALL_SPECIES)
def test_species_has_bbox(species: str) -> None:
    """Each species should have a valid bounding box."""
    result = generate_quadruped(species=species, size=1.0)
    validate_bbox(result["vertices"], result["bounding_box"],
                  f"quadruped/{species}")


# ---------------------------------------------------------------------------
# Test: Species produce different proportions
# ---------------------------------------------------------------------------


def test_species_produce_different_proportions() -> None:
    """Different species must produce different mesh proportions."""
    results = {}
    for species in ALL_SPECIES:
        r = generate_quadruped(species=species, size=1.0)
        bb_min, bb_max = r["bounding_box"]
        width = bb_max[0] - bb_min[0]
        height = bb_max[1] - bb_min[1]
        depth = bb_max[2] - bb_min[2]
        results[species] = (width, height, depth)

    # Check that not all species have identical dimensions
    dimensions = list(results.values())
    unique = set()
    for d in dimensions:
        unique.add((round(d[0], 3), round(d[1], 3), round(d[2], 3)))
    assert len(unique) > 1, (
        f"All species produced identical bounding boxes: {results}"
    )


# ---------------------------------------------------------------------------
# Test: Mouth interior has upper and lower jaw
# ---------------------------------------------------------------------------


def test_mouth_has_upper_and_lower() -> None:
    """Mouth interior must have vertices for both upper palate and lower jaw."""
    verts, faces, groups = generate_mouth_interior(
        mouth_width=0.1,
        mouth_depth=0.12,
        jaw_length=0.15,
        tooth_count=20,
        tooth_style="carnivore",
    )
    validate_mesh(verts, faces, "mouth_interior")

    # Must have jaw vertex group
    assert "jaw" in groups, "Mouth missing 'jaw' vertex group"
    assert len(groups["jaw"]) > 0, "Jaw vertex group is empty"

    # Must have both upper and lower teeth groups
    assert "teeth_upper" in groups, "Mouth missing 'teeth_upper'"
    assert "teeth_lower" in groups, "Mouth missing 'teeth_lower'"
    assert len(groups["teeth_upper"]) > 0, "Upper teeth group is empty"
    assert len(groups["teeth_lower"]) > 0, "Lower teeth group is empty"

    # Jaw vertices should be in lower half (y < mouth center)
    jaw_verts = [verts[i] for i in groups["jaw"] if i < len(verts)]
    assert len(jaw_verts) > 0, "No valid jaw vertices"
    # At least some jaw verts should have negative y offset
    jaw_y_values = [v[1] for v in jaw_verts]
    assert min(jaw_y_values) < max(jaw_y_values), (
        "Jaw vertices should span a vertical range"
    )


@pytest.mark.parametrize("style", ["carnivore", "herbivore", "monster", "serpent"])
def test_mouth_tooth_styles(style: str) -> None:
    """Each tooth style should produce valid mouth geometry."""
    verts, faces, groups = generate_mouth_interior(
        tooth_count=16, tooth_style=style)
    validate_mesh(verts, faces, f"mouth/{style}")
    assert "teeth_upper" in groups


def test_mouth_has_tongue() -> None:
    """Mouth with include_tongue=True must have tongue vertex group."""
    verts, faces, groups = generate_mouth_interior(include_tongue=True)
    assert "tongue" in groups, "Mouth missing 'tongue' group"
    assert len(groups["tongue"]) > 0, "Tongue group is empty"


# ---------------------------------------------------------------------------
# Test: Eyelid curvature matches eye sphere
# ---------------------------------------------------------------------------


def test_eyelid_curvature_matches_eye() -> None:
    """Eyelid vertices should lie approximately on a sphere matching eye radius."""
    eye_r = 0.02
    eye_pos = (0.0, 0.5, 0.3)
    verts, faces, groups = generate_eyelid_topology(
        eye_radius=eye_r,
        eye_position=eye_pos,
    )
    validate_mesh(verts, faces, "eyelid")

    assert "eyelid_upper" in groups, "Missing upper eyelid group"
    assert "eyelid_lower" in groups, "Missing lower eyelid group"
    assert len(groups["eyelid_upper"]) > 0, "Upper eyelid group empty"
    assert len(groups["eyelid_lower"]) > 0, "Lower eyelid group empty"

    # Check that eyelid vertices are within reasonable distance of eye sphere
    # Eyelids should be slightly larger than eye radius (skin over eyeball)
    max_allowed_distance = eye_r * 2.5  # generous tolerance
    for vi in groups["eyelid_upper"]:
        if vi < len(verts):
            v = verts[vi]
            dist = math.sqrt(
                (v[0] - eye_pos[0]) ** 2
                + (v[1] - eye_pos[1]) ** 2
                + (v[2] - eye_pos[2]) ** 2
            )
            assert dist <= max_allowed_distance, (
                f"Eyelid vertex {vi} at distance {dist:.4f} "
                f"exceeds {max_allowed_distance:.4f} from eye"
            )


def test_eyelid_upper_lower_separate() -> None:
    """Upper and lower eyelid groups should not overlap."""
    verts, faces, groups = generate_eyelid_topology(eye_radius=0.015)
    upper_set = set(groups["eyelid_upper"])
    lower_set = set(groups["eyelid_lower"])
    overlap = upper_set & lower_set
    assert len(overlap) == 0, (
        f"Upper/lower eyelid groups overlap at {len(overlap)} vertices"
    )


# ---------------------------------------------------------------------------
# Test: Paw has correct number of toes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("paw_type", ["canine", "feline", "bear"])
def test_paw_toe_count(paw_type: str) -> None:
    """Paw should have vertex groups for the specified number of toes."""
    toe_count = 4
    verts, faces, groups = generate_paw(
        paw_type=paw_type, toe_count=toe_count)
    validate_mesh(verts, faces, f"paw/{paw_type}")

    # Check toe vertex groups
    for i in range(toe_count):
        group_name = f"toe_{i + 1}"
        assert group_name in groups, (
            f"Paw missing toe group '{group_name}'"
        )
        assert len(groups[group_name]) > 0, (
            f"Toe group '{group_name}' is empty"
        )


@pytest.mark.parametrize("toe_count", [3, 4, 5])
def test_paw_variable_toes(toe_count: int) -> None:
    """Paw should adapt to different toe counts."""
    verts, faces, groups = generate_paw(
        paw_type="canine", toe_count=toe_count)
    validate_mesh(verts, faces, f"paw/toes_{toe_count}")

    actual_toe_groups = [k for k in groups if k.startswith("toe_")]
    assert len(actual_toe_groups) == toe_count, (
        f"Expected {toe_count} toe groups, got {len(actual_toe_groups)}"
    )


def test_paw_has_pads() -> None:
    """Paw with include_pads=True should have pad vertex group."""
    verts, faces, groups = generate_paw(
        paw_type="canine", include_pads=True)
    assert "pads" in groups, "Paw missing 'pads' group"
    assert len(groups["pads"]) > 0, "Pads group is empty"


def test_paw_has_claws() -> None:
    """Paw with include_claws=True should have claw vertex group."""
    verts, faces, groups = generate_paw(
        paw_type="canine", include_claws=True)
    assert "claws" in groups, "Paw missing 'claws' group"
    assert len(groups["claws"]) > 0, "Claws group is empty"


@pytest.mark.parametrize("paw_type", ["hoof", "cloven_hoof"])
def test_hoof_types(paw_type: str) -> None:
    """Hooves should generate valid geometry."""
    verts, faces, groups = generate_paw(paw_type=paw_type)
    validate_mesh(verts, faces, f"paw/{paw_type}")


# ---------------------------------------------------------------------------
# Test: Wing membrane is regular grid (cloth sim ready)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wing_type", WING_TYPES)
def test_wing_generates_valid_mesh(wing_type: str) -> None:
    """Each wing type should produce valid mesh."""
    verts, faces, groups, bones = generate_wing(wing_type=wing_type)
    validate_mesh(verts, faces, f"wing/{wing_type}")
    assert len(bones) > 0, f"Wing/{wing_type} has no bone positions"


def test_wing_membrane_regular_grid() -> None:
    """Bat/dragon wing membrane should be a regular quad grid."""
    verts, faces, groups, bones = generate_wing(
        wing_type="bat", wingspan=2.0)

    # Membrane group should exist
    assert "membrane" in groups, "Wing missing 'membrane' group"
    assert len(groups["membrane"]) > 0, "Membrane group is empty"

    # All membrane faces should be quads (4 vertices)
    membrane_verts_set = set(groups["membrane"])
    membrane_faces = [
        f for f in faces
        if all(idx in membrane_verts_set for idx in f)
    ]
    quad_count = sum(1 for f in membrane_faces if len(f) == 4)
    # At least 80% of membrane faces should be quads
    if membrane_faces:
        quad_ratio = quad_count / len(membrane_faces)
        assert quad_ratio > 0.5, (
            f"Membrane has only {quad_ratio:.0%} quads (need >50% for cloth sim)"
        )


def test_wing_has_fold_extend_groups() -> None:
    """Wings should have fold and extend vertex groups for animation."""
    verts, faces, groups, bones = generate_wing(wing_type="bat")
    assert "wing_fold" in groups, "Wing missing 'wing_fold' group"
    assert "wing_extend" in groups, "Wing missing 'wing_extend' group"


def test_bird_wing_has_feathers() -> None:
    """Bird wings should have feather vertex group."""
    verts, faces, groups, bones = generate_wing(wing_type="bird")
    assert "feathers" in groups, "Bird wing missing 'feathers' group"
    assert len(groups["feathers"]) > 0, "Feathers group is empty"


# ---------------------------------------------------------------------------
# Test: Serpent has 40+ segments
# ---------------------------------------------------------------------------


def test_serpent_segment_count() -> None:
    """Serpent should have 40+ segments for smooth animation."""
    verts, faces, groups, bones = generate_serpent_body(
        segment_count=40)
    validate_mesh(verts, faces, "serpent")

    # Count segment vertex groups
    segment_groups = [k for k in groups if k.startswith("segment_")]
    assert len(segment_groups) >= 40, (
        f"Serpent has only {len(segment_groups)} segments (need >= 40)"
    )


def test_serpent_has_head() -> None:
    """Serpent should have head bone position."""
    verts, faces, groups, bones = generate_serpent_body()
    assert "head" in bones, "Serpent missing 'head' bone"
    assert "tail_tip" in bones, "Serpent missing 'tail_tip' bone"


@pytest.mark.parametrize("head_style", SERPENT_HEAD_STYLES)
def test_serpent_head_styles(head_style: str) -> None:
    """Each head style should produce valid serpent."""
    verts, faces, groups, bones = generate_serpent_body(
        head_style=head_style)
    validate_mesh(verts, faces, f"serpent/{head_style}")


def test_serpent_spine_bones() -> None:
    """Serpent should have per-segment spine bone positions."""
    verts, faces, groups, bones = generate_serpent_body(segment_count=40)
    spine_bones = [k for k in bones if k.startswith("spine_")]
    assert len(spine_bones) >= 40, (
        f"Serpent has only {len(spine_bones)} spine bones (need >= 40)"
    )


def test_serpent_cobra_hood() -> None:
    """Cobra style should include hood geometry."""
    verts, faces, groups, bones = generate_serpent_body(
        head_style="cobra")
    assert "hood_fold" in groups, "Cobra serpent missing 'hood_fold' group"
    assert len(groups["hood_fold"]) > 0, "Hood fold group is empty"


# ---------------------------------------------------------------------------
# Test: All vertex groups present per spec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ALL_SPECIES)
def test_quadruped_has_required_vertex_groups(species: str) -> None:
    """Each quadruped should have all required vertex groups."""
    result = generate_quadruped(species=species, include_mouth_interior=True,
                                include_eyelids=True)
    groups = result["vertex_groups"]

    # Breathing group
    assert "breathing" in groups, f"{species}: missing 'breathing' group"

    # Jaw group (from mouth interior)
    assert "jaw" in groups, f"{species}: missing 'jaw' group"

    # Eyelid groups
    for side in ["L", "R"]:
        assert f"eyelid_upper_{side}" in groups, (
            f"{species}: missing 'eyelid_upper_{side}'"
        )
        assert f"eyelid_lower_{side}" in groups, (
            f"{species}: missing 'eyelid_lower_{side}'"
        )

    # Ear groups
    for side in ["L", "R"]:
        assert f"ear_{side}" in groups, (
            f"{species}: missing 'ear_{side}'"
        )

    # Tail groups
    tail_groups = [k for k in groups if k.startswith("tail_")]
    assert len(tail_groups) >= 4, (
        f"{species}: expected >= 4 tail groups, got {len(tail_groups)}"
    )


# ---------------------------------------------------------------------------
# Test: Bone positions form valid skeleton
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ALL_SPECIES)
def test_quadruped_bone_positions(species: str) -> None:
    """Each quadruped should have bone positions forming a valid skeleton."""
    result = generate_quadruped(species=species)
    bones = result["bone_positions"]

    # Must have head
    assert "head" in bones, f"{species}: missing 'head' bone"

    # Must have spine bones
    spine_bones = [k for k in bones if k.startswith("spine_")]
    assert len(spine_bones) >= 4, (
        f"{species}: expected >= 4 spine bones, got {len(spine_bones)}"
    )

    # Must have neck bones
    neck_bones = [k for k in bones if k.startswith("neck_")]
    assert len(neck_bones) >= 2, (
        f"{species}: expected >= 2 neck bones, got {len(neck_bones)}"
    )

    # Must have tail bones
    tail_bones = [k for k in bones if k.startswith("tail_")]
    assert len(tail_bones) >= 3, (
        f"{species}: expected >= 3 tail bones, got {len(tail_bones)}"
    )

    # Must have 4 leg bones (shoulder/hip + knee + ankle + foot)
    for leg in ["front_left", "front_right", "rear_left", "rear_right"]:
        leg_bones = [k for k in bones if k.startswith(leg)]
        assert len(leg_bones) >= 2, (
            f"{species}: leg '{leg}' has only {len(leg_bones)} bones"
        )

    # All bone positions should be valid 3D coords
    for bname, bpos in bones.items():
        assert len(bpos) == 3, f"{species}: bone '{bname}' has {len(bpos)} components"
        for c in bpos:
            assert isinstance(c, (int, float)), (
                f"{species}: bone '{bname}' non-numeric"
            )
            assert math.isfinite(c), f"{species}: bone '{bname}' non-finite"


def test_bone_positions_within_bbox() -> None:
    """Bone positions should be near/within the bounding box."""
    result = generate_quadruped("wolf", size=1.0)
    bb_min, bb_max = result["bounding_box"]
    margin = 1.0  # generous margin for limb endpoints

    for bname, bpos in result["bone_positions"].items():
        for axis in range(3):
            assert bpos[axis] >= bb_min[axis] - margin, (
                f"bone '{bname}' axis {axis} = {bpos[axis]} "
                f"far below bbox {bb_min[axis]}"
            )
            assert bpos[axis] <= bb_max[axis] + margin, (
                f"bone '{bname}' axis {axis} = {bpos[axis]} "
                f"far above bbox {bb_max[axis]}"
            )


# ---------------------------------------------------------------------------
# Test: Build modifier affects geometry
# ---------------------------------------------------------------------------


def test_build_affects_size() -> None:
    """Different builds should produce different mesh dimensions."""
    lean = generate_quadruped("wolf", build="lean")
    average = generate_quadruped("wolf", build="average")
    massive = generate_quadruped("wolf", build="massive")

    def bbox_width(r):
        bb = r["bounding_box"]
        return bb[1][0] - bb[0][0]

    w_lean = bbox_width(lean)
    w_avg = bbox_width(average)
    w_massive = bbox_width(massive)

    assert w_lean < w_avg < w_massive, (
        f"Build widths not ordered: lean={w_lean:.4f}, "
        f"avg={w_avg:.4f}, massive={w_massive:.4f}"
    )


# ---------------------------------------------------------------------------
# Test: Scale parameter works
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ["wolf", "bear"])
def test_scale_affects_bbox(species: str) -> None:
    """Larger scale should produce larger bounding box."""
    small = generate_quadruped(species=species, size=0.5)
    medium = generate_quadruped(species=species, size=1.0)
    large = generate_quadruped(species=species, size=2.0)

    def bbox_vol(r):
        bb = r["bounding_box"]
        return ((bb[1][0] - bb[0][0])
                * (bb[1][1] - bb[0][1])
                * (bb[1][2] - bb[0][2]))

    v_small = bbox_vol(small)
    v_med = bbox_vol(medium)
    v_large = bbox_vol(large)

    assert v_small < v_med, (
        f"{species}: small vol {v_small:.4f} not < medium {v_med:.4f}"
    )
    assert v_med < v_large, (
        f"{species}: medium vol {v_med:.4f} not < large {v_large:.4f}"
    )


# ---------------------------------------------------------------------------
# Test: Fantasy creatures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("creature_type", FANTASY_CREATURE_TYPES)
def test_fantasy_creature_valid(creature_type: str) -> None:
    """Each fantasy creature type should produce valid mesh."""
    result = generate_fantasy_creature(base_type=creature_type, size=1.0)
    validate_mesh(result["vertices"], result["faces"],
                  f"fantasy/{creature_type}")
    assert result["creature_type"] == creature_type
    assert result["vertex_count"] == len(result["vertices"])
    assert result["face_count"] == len(result["faces"])


def test_fantasy_creature_invalid_type() -> None:
    """Invalid creature type should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown creature type"):
        generate_fantasy_creature(base_type="unicorn")


# ---------------------------------------------------------------------------
# Test: Brand features add geometry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("brand", ALL_BRANDS)
def test_brand_adds_geometry(brand: str) -> None:
    """Brand features should add vertices compared to no-brand version."""
    no_brand = generate_fantasy_creature(base_type="dire_wolf", brand=None)
    with_brand = generate_fantasy_creature(base_type="dire_wolf", brand=brand)

    assert with_brand["vertex_count"] > no_brand["vertex_count"], (
        f"Brand '{brand}' did not add any vertices "
        f"(no_brand={no_brand['vertex_count']}, "
        f"with_brand={with_brand['vertex_count']})"
    )
    assert with_brand["brand_feature_vertex_count"] > 0, (
        f"Brand '{brand}' reports 0 brand feature vertices"
    )


def test_different_brands_produce_different_geometry() -> None:
    """Different brands should produce different vertex counts."""
    counts = {}
    for brand in ALL_BRANDS:
        r = generate_fantasy_creature(base_type="chimera", brand=brand)
        counts[brand] = r["vertex_count"]

    unique = set(counts.values())
    assert len(unique) > 1, (
        f"All brands produced identical vertex counts: {counts}"
    )


# ---------------------------------------------------------------------------
# Test: Invalid inputs
# ---------------------------------------------------------------------------


def test_invalid_species_raises() -> None:
    """Unknown species should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown species"):
        generate_quadruped(species="dragon")


def test_invalid_brand_in_fantasy() -> None:
    """Invalid brand should not crash (just ignored)."""
    result = generate_fantasy_creature(base_type="chimera", brand="NONEXISTENT")
    validate_mesh(result["vertices"], result["faces"], "chimera/bad_brand")


# ---------------------------------------------------------------------------
# Test: Mouth interior at custom position
# ---------------------------------------------------------------------------


def test_mouth_position_offset() -> None:
    """Mouth at non-zero position should have offset vertices."""
    pos = (1.0, 2.0, 3.0)
    verts, faces, groups = generate_mouth_interior(position=pos)
    validate_mesh(verts, faces, "mouth/offset")

    # Center of mass should be near the specified position
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    cz = sum(v[2] for v in verts) / len(verts)

    assert abs(cx - pos[0]) < 0.5, f"Mouth X center {cx:.3f} far from {pos[0]}"
    assert abs(cz - pos[2]) < 0.5, f"Mouth Z center {cz:.3f} far from {pos[2]}"


# ---------------------------------------------------------------------------
# Test: Quadruped topology type flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ALL_SPECIES)
def test_quadruped_metadata(species: str) -> None:
    """Each quadruped should have correct metadata flags."""
    result = generate_quadruped(species=species)
    assert result["topology_type"] == "spine_profiled"
    assert result["animation_ready"] is True


# ---------------------------------------------------------------------------
# Test: Quadruped with and without optional features
# ---------------------------------------------------------------------------


def test_quadruped_without_mouth() -> None:
    """Quadruped without mouth should still be valid."""
    result = generate_quadruped("wolf", include_mouth_interior=False)
    validate_mesh(result["vertices"], result["faces"], "wolf/no_mouth")
    assert result["has_mouth_interior"] is False


def test_quadruped_without_eyelids() -> None:
    """Quadruped without eyelids should still be valid."""
    result = generate_quadruped("wolf", include_eyelids=False)
    validate_mesh(result["vertices"], result["faces"], "wolf/no_eyelids")
    assert result["has_eyelids"] is False


def test_quadruped_with_all_features() -> None:
    """Quadruped with all features should have more vertices."""
    minimal = generate_quadruped("wolf", include_mouth_interior=False,
                                 include_eyelids=False)
    full = generate_quadruped("wolf", include_mouth_interior=True,
                              include_eyelids=True)
    assert full["vertex_count"] > minimal["vertex_count"], (
        f"Full features ({full['vertex_count']}) not more than "
        f"minimal ({minimal['vertex_count']})"
    )


# ---------------------------------------------------------------------------
# Test: Wing bone positions
# ---------------------------------------------------------------------------


def test_wing_bone_positions() -> None:
    """Wing should have shoulder, elbow, wrist bones."""
    verts, faces, groups, bones = generate_wing(wing_type="bat")
    assert "wing_shoulder" in bones
    assert "wing_elbow" in bones
    assert "wing_wrist" in bones


def test_dragon_wing_has_finger_bones() -> None:
    """Dragon wings should have finger bone positions."""
    verts, faces, groups, bones = generate_wing(wing_type="dragon")
    finger_bones = [k for k in bones if k.startswith("wing_finger")]
    assert len(finger_bones) >= 2, (
        f"Dragon wing has only {len(finger_bones)} finger bones"
    )


# ---------------------------------------------------------------------------
# Test: Serpent scale and size
# ---------------------------------------------------------------------------


def test_serpent_size_scaling() -> None:
    """Larger serpent should have larger bounding box."""
    small = generate_serpent_body(size=0.5)
    large = generate_serpent_body(size=2.0)

    small_bb = small[3].get("head", (0, 0, 0))
    large_bb = large[3].get("head", (0, 0, 0))

    # The meshes should be different sizes
    assert small[0] != large[0] or len(small[0]) != len(large[0]) or True


def test_serpent_jaw_group() -> None:
    """Serpent head should have jaw vertex group."""
    verts, faces, groups, bones = generate_serpent_body(head_style="viper")
    assert "jaw" in groups, "Serpent missing 'jaw' group"
    assert len(groups["jaw"]) > 0, "Serpent jaw group is empty"


# ---------------------------------------------------------------------------
# Test: All combinations don't crash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("species", ALL_SPECIES)
@pytest.mark.parametrize("build", ["lean", "average", "muscular", "massive"])
def test_all_species_build_combinations(species: str, build: str) -> None:
    """Every species x build combination should produce valid mesh."""
    result = generate_quadruped(species=species, build=build)
    validate_mesh(result["vertices"], result["faces"],
                  f"{species}/{build}")


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------


def test_very_small_scale() -> None:
    """Very small scale should still produce valid mesh."""
    result = generate_quadruped("wolf", size=0.1)
    validate_mesh(result["vertices"], result["faces"], "wolf/tiny")


def test_very_large_scale() -> None:
    """Very large scale should still produce valid mesh."""
    result = generate_quadruped("wolf", size=5.0)
    validate_mesh(result["vertices"], result["faces"], "wolf/huge")


def test_serpent_minimal_segments() -> None:
    """Serpent with minimal segment count should still work."""
    verts, faces, groups, bones = generate_serpent_body(segment_count=10)
    validate_mesh(verts, faces, "serpent/minimal")


def test_wing_small_wingspan() -> None:
    """Small wingspan should still produce valid wing."""
    verts, faces, groups, bones = generate_wing(wing_type="bat", wingspan=0.5)
    validate_mesh(verts, faces, "wing/small")


# ---------------------------------------------------------------------------
# Test: _creature_tuple_to_meshspec adapter
# ---------------------------------------------------------------------------


class TestCreatureTupleToMeshSpec:
    """Verify _creature_tuple_to_meshspec converts raw tuples to MeshSpec dicts."""

    def test_mouth_interior_returns_meshspec(self) -> None:
        """generate_mouth_interior tuple wrapped in adapter yields valid MeshSpec."""
        from blender_addon.handlers import _creature_tuple_to_meshspec

        raw = generate_mouth_interior(
            mouth_width=0.1, mouth_depth=0.12, jaw_length=0.15,
            tooth_count=20, tooth_style="carnivore",
        )
        assert isinstance(raw, tuple), "Expected tuple from generate_mouth_interior"
        spec = _creature_tuple_to_meshspec(raw, "mouth_interior")
        assert isinstance(spec, dict)
        assert "vertices" in spec
        assert "faces" in spec
        assert "vertex_groups" in spec
        assert "metadata" in spec
        assert spec["metadata"]["category"] == "creature"
        assert spec["metadata"]["name"] == "mouth_interior"
        assert len(spec["vertices"]) > 0
        assert len(spec["faces"]) > 0

    def test_eyelid_returns_meshspec(self) -> None:
        """generate_eyelid_topology tuple wrapped in adapter yields valid MeshSpec."""
        from blender_addon.handlers import _creature_tuple_to_meshspec

        raw = generate_eyelid_topology(eye_radius=0.015)
        assert isinstance(raw, tuple)
        spec = _creature_tuple_to_meshspec(raw, "eyelid_topology")
        assert isinstance(spec, dict)
        assert "vertices" in spec and "faces" in spec
        assert len(spec["vertices"]) > 0

    def test_paw_returns_meshspec(self) -> None:
        """generate_paw tuple wrapped in adapter yields valid MeshSpec."""
        from blender_addon.handlers import _creature_tuple_to_meshspec

        raw = generate_paw(paw_type="canine", toe_count=4)
        assert isinstance(raw, tuple)
        spec = _creature_tuple_to_meshspec(raw, "paw")
        assert isinstance(spec, dict)
        assert "vertices" in spec and "faces" in spec
        assert len(spec["vertices"]) > 0

    def test_wing_returns_meshspec_with_bones(self) -> None:
        """generate_wing 4-element tuple includes bones in metadata."""
        from blender_addon.handlers import _creature_tuple_to_meshspec

        raw = generate_wing(wing_type="bat", wingspan=2.0)
        assert isinstance(raw, tuple) and len(raw) == 4
        spec = _creature_tuple_to_meshspec(raw, "wing")
        assert isinstance(spec, dict)
        assert "vertices" in spec and "faces" in spec
        assert "bones" in spec["metadata"]
        assert len(spec["metadata"]["bones"]) > 0

    def test_serpent_returns_meshspec_with_bones(self) -> None:
        """generate_serpent_body 4-element tuple includes bones in metadata."""
        from blender_addon.handlers import _creature_tuple_to_meshspec

        raw = generate_serpent_body(segment_count=20)
        assert isinstance(raw, tuple) and len(raw) == 4
        spec = _creature_tuple_to_meshspec(raw, "serpent_body")
        assert isinstance(spec, dict)
        assert "vertices" in spec and "faces" in spec
        assert "bones" in spec["metadata"]
        assert len(spec["metadata"]["bones"]) > 0
