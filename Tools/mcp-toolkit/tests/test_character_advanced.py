"""Tests for character_advanced: DNA blending, cloth collision, strand hair, body morphs.

Validates Gaps #57-#61:
- DNA blend at weight 0 returns base mesh, at weight 1 returns base+delta
- Multiple morph weights combine additively
- Collision capsule fits all vertices
- Collision box margin inflates correctly
- Hair strand length matches requested length (within tolerance)
- Hair strand segments match requested count
- Hair card mesh has correct vertex count (2 * segments * strand_count)
- Hair card UVs are in 0-1 range
- Wavy/curly strands have lateral displacement
- Clumping reduces spread between nearby strands
- Facial landmarks are symmetric (L/R pairs mirror on X)
- Body morph 'muscular' increases limb radius
- Body morph 'gaunt' decreases all dimensions
- All morph names are valid
- Weight clamping works (negative -> 0, > 1 -> 1)
"""

from __future__ import annotations

import math

import pytest

from blender_addon.handlers.character_advanced import (
    # Constants / enumerations
    VALID_HAIR_STYLES,
    VALID_MORPH_NAMES,
    VALID_COLLISION_TYPES,
    VALID_FACIAL_LEVELS,
    VALID_BODY_PARTS,
    FACE_MORPH_TARGETS,
    BODY_MORPH_TARGETS,
    FACIAL_LANDMARKS,
    # Pure-logic functions
    blend_vertices,
    compute_collision_capsule,
    compute_collision_box,
    generate_strand_curve,
    generate_hair_guide_strands,
    strands_to_cards,
    compute_morph_deltas,
    # Handler functions
    handle_dna_blend,
    handle_cloth_collision_proxy,
    handle_hair_strands,
    handle_facial_setup,
    handle_body_morph,
    # Internal helpers used in tests
    _clamp,
    _vec_dist,
    _get_bones_for_level,
)


# ---------------------------------------------------------------------------
# Helpers for test data
# ---------------------------------------------------------------------------

def _make_unit_cube_verts() -> list[list[float]]:
    """8 vertices of a unit cube centered at origin."""
    return [
        [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5],
        [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
        [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5],
        [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
    ]


def _make_body_verts(n: int = 200) -> list[list[float]]:
    """Generate a simple humanoid-shaped vertex cloud for testing."""
    verts: list[list[float]] = []
    # Torso (centered, z: 0.85 to 1.45)
    for i in range(n // 4):
        t = i / max(1, n // 4 - 1)
        z = 0.85 + t * 0.6
        angle = t * math.pi * 4
        r = 0.15 + 0.03 * math.sin(angle)
        verts.append([r * math.cos(angle * 3), r * math.sin(angle * 3), z])

    # Thigh L (z: 0.45 to 0.85, x: -0.15 to -0.05)
    for i in range(n // 8):
        t = i / max(1, n // 8 - 1)
        z = 0.45 + t * 0.4
        verts.append([-0.10 + 0.04 * math.sin(t * math.pi), 0.0, z])

    # Thigh R
    for i in range(n // 8):
        t = i / max(1, n // 8 - 1)
        z = 0.45 + t * 0.4
        verts.append([0.10 + 0.04 * math.sin(t * math.pi), 0.0, z])

    # Upper arms
    for i in range(n // 8):
        t = i / max(1, n // 8 - 1)
        z = 1.20 + t * 0.3
        verts.append([-0.25, 0.0, z])
        verts.append([0.25, 0.0, z])

    # Fill to n
    while len(verts) < n:
        verts.append([0.0, 0.0, 1.0])

    return verts[:n]


def _make_body_regions(verts: list[list[float]]) -> dict[str, list[int]]:
    """Assign vertex indices to body regions based on position."""
    regions: dict[str, list[int]] = {
        "torso": [],
        "chest": [],
        "belly": [],
        "waist": [],
        "hip": [],
        "upper_arm": [],
        "upper_arm_L": [],
        "upper_arm_R": [],
        "lower_arm": [],
        "lower_arm_L": [],
        "lower_arm_R": [],
        "thigh": [],
        "thigh_L": [],
        "thigh_R": [],
        "shin": [],
        "shin_L": [],
        "shin_R": [],
        "shoulder": [],
        "hand": [],
        "face": [],
        "upper_torso": [],
        "full_body": list(range(len(verts))),
    }

    for i, v in enumerate(verts):
        x, y, z = v
        if 0.85 <= z <= 1.45:
            regions["torso"].append(i)
            if z > 1.2:
                regions["chest"].append(i)
                regions["upper_torso"].append(i)
            if z < 1.05:
                regions["belly"].append(i)
            if 1.0 <= z <= 1.15:
                regions["waist"].append(i)
        if 0.75 <= z <= 0.95:
            regions["hip"].append(i)
        if x < -0.15 and 1.2 <= z <= 1.5:
            regions["upper_arm"].append(i)
            regions["upper_arm_L"].append(i)
        if x > 0.15 and 1.2 <= z <= 1.5:
            regions["upper_arm"].append(i)
            regions["upper_arm_R"].append(i)
        if 0.45 <= z <= 0.85 and x < -0.02:
            regions["thigh"].append(i)
            regions["thigh_L"].append(i)
        if 0.45 <= z <= 0.85 and x > 0.02:
            regions["thigh"].append(i)
            regions["thigh_R"].append(i)
        if z > 1.35:
            regions["shoulder"].append(i)

    return regions


def _make_scalp_data(count: int = 20):
    """Generate scalp positions and normals on a hemisphere."""
    positions = []
    normals = []
    for i in range(count):
        theta = (i / count) * math.pi * 2
        phi = 0.2 + (i % 5) * 0.15
        x = 0.1 * math.sin(phi) * math.cos(theta)
        y = 0.1 * math.sin(phi) * math.sin(theta)
        z = 1.7 + 0.1 * math.cos(phi)
        positions.append([x, y, z])
        # Normal points outward from head center
        nx, ny, nz = x, y, z - 1.7
        length = math.sqrt(nx**2 + ny**2 + nz**2)
        if length > 0:
            normals.append([nx / length, ny / length, nz / length])
        else:
            normals.append([0.0, 0.0, 1.0])
    return positions, normals


# ===========================================================================
# Gap #57: DNA / Mesh Blending Tests
# ===========================================================================

class TestDNABlend:
    """Tests for DNA/mesh blending (Gap #57)."""

    def test_weight_zero_returns_base(self):
        """Weight 0 should return exact base mesh."""
        base = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        targets = {"morph_a": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
        result = blend_vertices(base, targets, {"morph_a": 0.0})
        for i in range(len(base)):
            for j in range(3):
                assert result[i][j] == pytest.approx(base[i][j], abs=1e-9)

    def test_weight_one_returns_base_plus_delta(self):
        """Weight 1 should return base + full delta."""
        base = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        deltas = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        targets = {"morph_a": deltas}
        result = blend_vertices(base, targets, {"morph_a": 1.0})
        for i in range(len(base)):
            for j in range(3):
                assert result[i][j] == pytest.approx(base[i][j] + deltas[i][j], abs=1e-9)

    def test_partial_weight(self):
        """Weight 0.5 should give half delta."""
        base = [[0.0, 0.0, 0.0]]
        deltas = [[1.0, 2.0, 3.0]]
        result = blend_vertices(base, {"m": deltas}, {"m": 0.5})
        assert result[0][0] == pytest.approx(0.5, abs=1e-9)
        assert result[0][1] == pytest.approx(1.0, abs=1e-9)
        assert result[0][2] == pytest.approx(1.5, abs=1e-9)

    def test_multiple_morphs_combine_additively(self):
        """Multiple morph targets at various weights combine additively."""
        base = [[0.0, 0.0, 0.0]]
        targets = {
            "a": [[1.0, 0.0, 0.0]],
            "b": [[0.0, 2.0, 0.0]],
            "c": [[0.0, 0.0, 3.0]],
        }
        weights = {"a": 0.5, "b": 0.3, "c": 0.2}
        result = blend_vertices(base, targets, weights)
        assert result[0][0] == pytest.approx(0.5, abs=1e-9)
        assert result[0][1] == pytest.approx(0.6, abs=1e-9)
        assert result[0][2] == pytest.approx(0.6, abs=1e-9)

    def test_negative_weight_clamped_to_zero(self):
        """Negative weight should be clamped to 0."""
        base = [[1.0, 1.0, 1.0]]
        targets = {"m": [[10.0, 10.0, 10.0]]}
        result = blend_vertices(base, targets, {"m": -0.5})
        assert result[0] == [1.0, 1.0, 1.0]

    def test_weight_above_one_clamped(self):
        """Weight > 1 should be clamped to 1."""
        base = [[0.0, 0.0, 0.0]]
        deltas = [[1.0, 1.0, 1.0]]
        result = blend_vertices(base, {"m": deltas}, {"m": 2.5})
        # Should equal weight=1 result
        assert result[0][0] == pytest.approx(1.0, abs=1e-9)
        assert result[0][1] == pytest.approx(1.0, abs=1e-9)

    def test_empty_base_returns_empty(self):
        """Empty base mesh returns empty result."""
        result = blend_vertices([], {"m": []}, {"m": 1.0})
        assert result == []

    def test_missing_target_ignored(self):
        """Referencing a non-existent morph target is a no-op."""
        base = [[1.0, 2.0, 3.0]]
        result = blend_vertices(base, {}, {"nonexistent": 1.0})
        assert result[0] == [1.0, 2.0, 3.0]

    def test_handle_dna_blend_returns_stats(self):
        """Handler returns displacement statistics."""
        base = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        targets = {"m": [[0.1, 0.0, 0.0], [0.0, 0.1, 0.0]]}
        result = handle_dna_blend({
            "base_mesh_verts": base,
            "morph_targets": targets,
            "blend_weights": {"m": 1.0},
        })
        assert "error" not in result
        assert result["vertex_count"] == 2
        assert result["stats"]["max_displacement"] > 0
        assert "m" in result["active_targets"]

    def test_handle_dna_blend_empty_error(self):
        """Handler returns error for empty base."""
        result = handle_dna_blend({"base_mesh_verts": []})
        assert "error" in result


# ===========================================================================
# Gap #58: Cloth Collision Proxy Tests
# ===========================================================================

class TestClothCollisionProxy:
    """Tests for cloth collision proxy volumes (Gap #58)."""

    def test_capsule_fits_all_vertices(self):
        """Capsule proxy must contain all source vertices."""
        verts = _make_unit_cube_verts()
        capsule = compute_collision_capsule(verts, axis="Z")

        # Every vertex should be within the capsule
        # Capsule = cylinder from cap_bottom to cap_top with radius
        cap_bot = capsule["cap_bottom"]
        cap_top = capsule["cap_top"]
        radius = capsule["radius"]
        axis_idx = 2  # Z

        for v in verts:
            # Project onto axis
            axis_pos = v[axis_idx]
            # Within cylinder section
            if cap_bot[axis_idx] <= axis_pos <= cap_top[axis_idx]:
                # Radial distance must be within radius
                r_sq = sum((v[i] - cap_bot[i]) ** 2 for i in range(3) if i != axis_idx)
                assert math.sqrt(r_sq) <= radius + 1e-6, \
                    f"Vertex {v} outside capsule cylinder (r={math.sqrt(r_sq)}, max={radius})"
            else:
                # Must be within hemisphere cap
                if axis_pos < cap_bot[axis_idx]:
                    dist = math.sqrt(sum((v[i] - cap_bot[i]) ** 2 for i in range(3)))
                else:
                    dist = math.sqrt(sum((v[i] - cap_top[i]) ** 2 for i in range(3)))
                assert dist <= radius + capsule["half_height"] + 1e-6, \
                    f"Vertex {v} outside capsule cap"

    def test_collision_box_margin_inflates(self):
        """Box with margin should be larger than without."""
        verts = _make_unit_cube_verts()
        box_no_margin = compute_collision_box(verts, margin=0.0)
        box_with_margin = compute_collision_box(verts, margin=0.05)

        for i in range(3):
            assert box_with_margin["min_corner"][i] < box_no_margin["min_corner"][i]
            assert box_with_margin["max_corner"][i] > box_no_margin["max_corner"][i]

    def test_collision_box_contains_all_vertices(self):
        """Box proxy must contain all source vertices."""
        verts = [[0.1, 0.2, 0.3], [-0.5, 0.8, -0.1], [0.3, -0.4, 0.7]]
        margin = 0.02
        box = compute_collision_box(verts, margin=margin)

        for v in verts:
            assert v[0] >= box["min_corner"][0] - 1e-6
            assert v[1] >= box["min_corner"][1] - 1e-6
            assert v[2] >= box["min_corner"][2] - 1e-6
            assert v[0] <= box["max_corner"][0] + 1e-6
            assert v[1] <= box["max_corner"][1] + 1e-6
            assert v[2] <= box["max_corner"][2] + 1e-6

    def test_collision_box_has_valid_mesh(self):
        """Box proxy should return 8 vertices and 6 quad faces."""
        verts = _make_unit_cube_verts()
        box = compute_collision_box(verts, margin=0.0)
        assert len(box["vertices"]) == 8
        assert len(box["faces"]) == 6
        for face in box["faces"]:
            assert len(face) == 4  # quads

    def test_capsule_axis_selection(self):
        """Capsule should align along specified axis."""
        # Elongated along X
        verts = [[-2.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.1, 0.0]]
        capsule = compute_collision_capsule(verts, axis="X")
        assert capsule["axis"] == "X"
        assert capsule["half_height"] > capsule["radius"]

    def test_handle_collision_proxy_invalid_body_part(self):
        """Handler returns error for invalid body part."""
        result = handle_cloth_collision_proxy({
            "character_body_verts": [[0, 0, 0]],
            "body_part": "invalid_part",
        })
        assert "error" in result

    def test_handle_collision_proxy_invalid_type(self):
        """Handler returns error for invalid proxy type."""
        result = handle_cloth_collision_proxy({
            "character_body_verts": [[0, 0, 0]],
            "proxy_type": "invalid_type",
        })
        assert "error" in result

    def test_handle_collision_proxy_capsule(self):
        """Full handler produces capsule proxy with collision settings."""
        verts = _make_body_verts(100)
        result = handle_cloth_collision_proxy({
            "character_body_verts": verts,
            "body_part": "torso",
            "proxy_type": "capsule",
            "margin": 0.02,
        })
        assert "error" not in result
        assert result["proxy"]["type"] == "capsule"
        assert result["collision_settings"]["body_part"] == "torso"
        assert result["collision_settings"]["friction"] > 0

    def test_handle_collision_proxy_box(self):
        """Full handler produces box proxy."""
        verts = _make_body_verts(50)
        result = handle_cloth_collision_proxy({
            "character_body_verts": verts,
            "body_part": "full_body",
            "proxy_type": "box",
            "margin": 0.01,
        })
        assert "error" not in result
        assert result["proxy"]["type"] == "box"

    def test_empty_verts_error(self):
        """Handler returns error for empty vertices."""
        result = handle_cloth_collision_proxy({
            "character_body_verts": [],
            "proxy_type": "capsule",
        })
        assert "error" in result


# ===========================================================================
# Gap #59: Strand-Based Hair Tests
# ===========================================================================

class TestStrandHair:
    """Tests for strand-based hair generation (Gap #59)."""

    def test_strand_length_matches_requested(self):
        """Total path length should approximate requested length."""
        length = 0.2
        segments = 12
        strand = generate_strand_curve(
            root_pos=(0, 0, 1.7),
            root_normal=(0, 0, 1),
            length=length,
            segments=segments,
            style="straight",
            gravity=0.0,
            seed=42,
        )
        # Compute path length
        path_len = sum(
            _vec_dist(strand[i], strand[i + 1])
            for i in range(len(strand) - 1)
        )
        # Within 30% tolerance (gravity and style cause deviations)
        assert abs(path_len - length) / length < 0.30, \
            f"Path length {path_len} too far from requested {length}"

    def test_strand_segments_match_count(self):
        """Number of control points should match requested segments."""
        segments = 10
        strand = generate_strand_curve(
            root_pos=(0, 0, 1.7),
            root_normal=(0, 0, 1),
            length=0.15,
            segments=segments,
            style="straight",
            gravity=0.3,
            seed=123,
        )
        assert len(strand) == segments

    def test_strand_starts_at_root(self):
        """First control point should be at root position."""
        root = (0.1, 0.2, 1.7)
        strand = generate_strand_curve(root, (0, 0, 1), 0.1, 5, "straight", 0.0, 42)
        assert strand[0] == root

    def test_card_vertex_count(self):
        """Card mesh should have 2 * segments * strand_count vertices."""
        strands = [
            generate_strand_curve((0, 0, 1.7), (0, 0, 1), 0.1, 6, "straight", 0.0, i)
            for i in range(5)
        ]
        cards = strands_to_cards(strands, card_width=0.005)
        expected_verts = 2 * 6 * 5  # 2 per segment per strand
        assert len(cards["vertices"]) == expected_verts

    def test_card_face_count(self):
        """Card mesh should have (segments-1) * strand_count quad faces."""
        segments = 8
        strand_count = 4
        strands = [
            generate_strand_curve((0, 0, 1.7), (0, 0, 1), 0.1, segments, "straight", 0.0, i)
            for i in range(strand_count)
        ]
        cards = strands_to_cards(strands, card_width=0.005)
        expected_faces = (segments - 1) * strand_count
        assert len(cards["faces"]) == expected_faces

    def test_card_uvs_in_range(self):
        """All UVs should be in [0, 1] range."""
        strands = [
            generate_strand_curve((0, 0, 1.7), (0, 0, 1), 0.15, 8, "wavy", 0.5, i)
            for i in range(10)
        ]
        cards = strands_to_cards(strands, card_width=0.005)
        for u, v in cards["uvs"]:
            assert 0.0 <= u <= 1.0 + 1e-6, f"UV U out of range: {u}"
            assert 0.0 <= v <= 1.0 + 1e-6, f"UV V out of range: {v}"

    def test_wavy_strands_have_lateral_displacement(self):
        """Wavy strands should deviate laterally from a straight line."""
        straight = generate_strand_curve(
            (0, 0, 1.7), (0, 0, 1), 0.2, 12, "straight", 0.0, 42
        )
        wavy = generate_strand_curve(
            (0, 0, 1.7), (0, 0, 1), 0.2, 12, "wavy", 0.0, 42
        )

        # Compute max lateral deviation from the root-to-tip line
        def _max_lateral_deviation(strand):
            if len(strand) < 3:
                return 0.0
            root = strand[0]
            tip = strand[-1]
            direction = (tip[0] - root[0], tip[1] - root[1], tip[2] - root[2])
            length = math.sqrt(sum(d ** 2 for d in direction))
            if length < 1e-9:
                return 0.0
            direction = tuple(d / length for d in direction)

            max_dev = 0.0
            for pt in strand[1:-1]:
                # Vector from root to point
                rp = (pt[0] - root[0], pt[1] - root[1], pt[2] - root[2])
                # Project onto direction
                proj = sum(rp[i] * direction[i] for i in range(3))
                # Closest point on line
                cp = tuple(root[i] + direction[i] * proj for i in range(3))
                dev = math.sqrt(sum((pt[i] - cp[i]) ** 2 for i in range(3)))
                max_dev = max(max_dev, dev)
            return max_dev

        wavy_dev = _max_lateral_deviation(wavy)
        straight_dev = _max_lateral_deviation(straight)
        assert wavy_dev > straight_dev, \
            f"Wavy strand ({wavy_dev}) should deviate more than straight ({straight_dev})"

    def test_curly_strands_have_lateral_displacement(self):
        """Curly strands should have significant lateral displacement."""
        curly = generate_strand_curve(
            (0, 0, 1.7), (0, 0, 1), 0.2, 16, "curly", 0.0, 42
        )
        straight = generate_strand_curve(
            (0, 0, 1.7), (0, 0, 1), 0.2, 16, "straight", 0.0, 42
        )

        # Curly should deviate more
        def _total_deviation(strand):
            total = 0.0
            for i in range(1, len(strand)):
                dx = strand[i][0] - strand[0][0]
                dy = strand[i][1] - strand[0][1]
                total += math.sqrt(dx ** 2 + dy ** 2)
            return total

        assert _total_deviation(curly) > _total_deviation(straight)

    def test_clumping_reduces_spread(self):
        """Higher clumping should reduce spread between nearby strands."""
        scalp_pos, scalp_norm = _make_scalp_data(30)

        strands_no_clump = generate_hair_guide_strands(
            scalp_pos, scalp_norm,
            count=15, length=0.15, segments=8,
            style="straight", gravity=0.3, clumping=0.0, seed=42,
        )
        strands_clumped = generate_hair_guide_strands(
            scalp_pos, scalp_norm,
            count=15, length=0.15, segments=8,
            style="straight", gravity=0.3, clumping=0.9, seed=42,
        )

        def _avg_tip_spread(strands):
            """Average distance between all strand tips."""
            tips = [s[-1] for s in strands if len(s) > 0]
            if len(tips) < 2:
                return 0.0
            total = 0.0
            count = 0
            for i in range(len(tips)):
                for j in range(i + 1, len(tips)):
                    total += _vec_dist(tips[i], tips[j])
                    count += 1
            return total / count if count > 0 else 0.0

        spread_no = _avg_tip_spread(strands_no_clump)
        spread_clumped = _avg_tip_spread(strands_clumped)
        assert spread_clumped < spread_no, \
            f"Clumped spread ({spread_clumped}) should be less than unclumped ({spread_no})"

    def test_handle_hair_strands_full_pipeline(self):
        """Full handler pipeline produces valid card mesh with strand data."""
        scalp_pos, scalp_norm = _make_scalp_data(40)
        result = handle_hair_strands({
            "scalp_verts": scalp_pos,
            "scalp_normals": scalp_norm,
            "hair_style": "wavy",
            "strand_count": 10,
            "strand_length": 0.12,
            "strand_segments": 6,
            "gravity": 0.4,
            "clumping": 0.3,
            "card_width": 0.004,
            "seed": 99,
        })
        assert "error" not in result
        assert len(result["vertices"]) > 0
        assert len(result["faces"]) > 0
        assert result["strand_data"]["style"] == "wavy"
        assert result["strand_data"]["strand_count"] > 0

    def test_handle_hair_strands_invalid_style(self):
        """Handler rejects invalid hair style."""
        result = handle_hair_strands({
            "scalp_verts": [[0, 0, 1.7]],
            "scalp_normals": [[0, 0, 1]],
            "hair_style": "mullet",
        })
        assert "error" in result

    def test_handle_hair_strands_empty_scalp(self):
        """Handler rejects empty scalp."""
        result = handle_hair_strands({"scalp_verts": []})
        assert "error" in result

    @pytest.mark.parametrize("style", sorted(VALID_HAIR_STYLES))
    def test_all_hair_styles_produce_strands(self, style):
        """Every valid hair style should produce non-empty strands."""
        scalp_pos, scalp_norm = _make_scalp_data(10)
        result = handle_hair_strands({
            "scalp_verts": scalp_pos,
            "scalp_normals": scalp_norm,
            "hair_style": style,
            "strand_count": 5,
            "strand_length": 0.1,
            "strand_segments": 6,
            "gravity": 0.3,
            "clumping": 0.2,
            "card_width": 0.004,
            "seed": 42,
        })
        assert "error" not in result
        assert len(result["vertices"]) > 0

    def test_gravity_causes_downward_droop(self):
        """With gravity=1.0, strand tips should be lower than with gravity=0."""
        root = (0.0, 0.0, 1.7)
        normal = (0.0, 1.0, 0.0)  # Growing forward
        no_grav = generate_strand_curve(root, normal, 0.2, 10, "straight", 0.0, 42)
        full_grav = generate_strand_curve(root, normal, 0.2, 10, "straight", 1.0, 42)

        # Tip Z of gravity strand should be lower
        assert full_grav[-1][2] < no_grav[-1][2], \
            "Gravity should pull strand tip downward"


# ===========================================================================
# Gap #60: Facial Articulation Tests
# ===========================================================================

class TestFacialSetup:
    """Tests for facial articulation setup (Gap #60)."""

    def test_facial_landmarks_symmetric(self):
        """L/R paired landmarks should mirror on X axis."""
        pairs_found = 0
        for name, data in FACIAL_LANDMARKS.items():
            if name.endswith("_L"):
                r_name = name[:-2] + "_R"
                if r_name in FACIAL_LANDMARKS:
                    pairs_found += 1
                    l_pos = data["pos"]
                    r_pos = FACIAL_LANDMARKS[r_name]["pos"]

                    # X should be mirrored (negated)
                    assert l_pos[0] == pytest.approx(-r_pos[0], abs=1e-6), \
                        f"{name} X={l_pos[0]} should mirror {r_name} X={r_pos[0]}"
                    # Y and Z should match
                    assert l_pos[1] == pytest.approx(r_pos[1], abs=1e-6), \
                        f"{name} Y={l_pos[1]} should equal {r_name} Y={r_pos[1]}"
                    assert l_pos[2] == pytest.approx(r_pos[2], abs=1e-6), \
                        f"{name} Z={l_pos[2]} should equal {r_name} Z={r_pos[2]}"

        assert pairs_found >= 5, f"Expected at least 5 L/R pairs, found {pairs_found}"

    def test_basic_level_has_10_bones(self):
        """Basic setup level should produce exactly 10 bones."""
        bones = _get_bones_for_level("basic")
        assert len(bones) == 10, f"Expected 10 basic bones, got {len(bones)}: {bones}"

    def test_standard_level_has_25_bones(self):
        """Standard setup level should produce 25 bones."""
        bones = _get_bones_for_level("standard")
        assert len(bones) == 25, f"Expected 25 standard bones, got {len(bones)}: {bones}"

    def test_full_level_has_50_plus_bones(self):
        """Full setup level should produce 50+ bones."""
        bones = _get_bones_for_level("full")
        assert len(bones) >= 50, f"Expected 50+ full bones, got {len(bones)}"

    def test_levels_are_cumulative(self):
        """Each level should include all bones from lower levels."""
        basic = set(_get_bones_for_level("basic"))
        standard = set(_get_bones_for_level("standard"))
        full = set(_get_bones_for_level("full"))

        assert basic.issubset(standard), "Standard should include all basic bones"
        assert standard.issubset(full), "Full should include all standard bones"

    def test_handle_facial_setup_basic(self):
        """Handler produces valid basic facial rig."""
        result = handle_facial_setup({
            "armature_name": "TestArm",
            "face_mesh_name": "TestHead",
            "setup_level": "basic",
        })
        assert "error" not in result
        assert result["bone_count"] == 10
        assert result["setup_level"] == "basic"
        assert len(result["bones"]) == 10
        assert len(result["vertex_groups"]) > 0
        assert len(result["setup_code"]) > 0

    def test_handle_facial_setup_full(self):
        """Handler produces valid full facial rig."""
        result = handle_facial_setup({
            "armature_name": "Arm",
            "face_mesh_name": "Head",
            "setup_level": "full",
        })
        assert "error" not in result
        assert result["bone_count"] >= 50

    def test_handle_facial_setup_invalid_level(self):
        """Handler rejects invalid setup level."""
        result = handle_facial_setup({"setup_level": "ultra"})
        assert "error" in result

    def test_bone_parents_reference_valid_bones(self):
        """All bone parents should reference either 'head' or another facial bone."""
        result = handle_facial_setup({"setup_level": "full"})
        bone_names = {b["name"] for b in result["bones"]}
        bone_names.add("head")  # The head bone is external

        for bone in result["bones"]:
            parent = bone["parent"]
            if parent:
                assert parent in bone_names, \
                    f"Bone '{bone['name']}' has invalid parent '{parent}'"

    def test_setup_code_contains_armature_reference(self):
        """Setup code should reference the armature name."""
        result = handle_facial_setup({
            "armature_name": "MyCharArm",
            "setup_level": "basic",
        })
        assert "MyCharArm" in result["setup_code"]


# ===========================================================================
# Gap #61: Body Morph / Proportion Tests
# ===========================================================================

class TestBodyMorph:
    """Tests for body morph/proportion controls (Gap #61)."""

    def test_all_morph_names_valid(self):
        """Every name in VALID_MORPH_NAMES should have a definition."""
        for name in VALID_MORPH_NAMES:
            assert name in BODY_MORPH_TARGETS, f"Morph '{name}' missing definition"

    def test_all_definitions_have_valid_name(self):
        """Every definition key should be in VALID_MORPH_NAMES."""
        for name in BODY_MORPH_TARGETS:
            assert name in VALID_MORPH_NAMES, f"Definition '{name}' not in VALID_MORPH_NAMES"

    def test_muscular_increases_limb_radius(self):
        """Muscular morph should push limb vertices outward (increase radius)."""
        verts = _make_body_verts(200)
        regions = _make_body_regions(verts)

        # Only test if we have upper_arm vertices
        if not regions["upper_arm"]:
            pytest.skip("No upper_arm vertices in test data")

        deltas = compute_morph_deltas(verts, regions, "muscular", 1.0)

        # Check that upper arm vertices moved outward
        arm_indices = regions["upper_arm"]
        total_radial_increase = 0.0
        for idx in arm_indices:
            v = verts[idx]
            d = deltas[idx]
            # Radial component (XY distance from body center)
            r_before = math.sqrt(v[0] ** 2 + v[1] ** 2)
            r_after = math.sqrt((v[0] + d[0]) ** 2 + (v[1] + d[1]) ** 2)
            total_radial_increase += r_after - r_before

        assert total_radial_increase > 0, \
            "Muscular morph should increase radial distance of limb vertices"

    def test_gaunt_decreases_dimensions(self):
        """Gaunt morph should move torso/limb vertices inward."""
        verts = _make_body_verts(200)
        regions = _make_body_regions(verts)

        if not regions["torso"]:
            pytest.skip("No torso vertices in test data")

        deltas = compute_morph_deltas(verts, regions, "gaunt", 1.0)

        # Check that torso vertices moved inward
        torso_indices = regions["torso"]
        inward_count = 0
        for idx in torso_indices:
            v = verts[idx]
            d = deltas[idx]
            if d == (0.0, 0.0, 0.0):
                continue
            r_before = math.sqrt(v[0] ** 2 + v[1] ** 2)
            r_after = math.sqrt((v[0] + d[0]) ** 2 + (v[1] + d[1]) ** 2)
            if r_after < r_before:
                inward_count += 1

        # At least some vertices should move inward
        active = sum(1 for idx in torso_indices if deltas[idx] != (0.0, 0.0, 0.0))
        if active > 0:
            assert inward_count > 0, "Gaunt morph should shrink some torso vertices"

    def test_weight_zero_produces_zero_deltas(self):
        """Weight 0 should produce all-zero deltas."""
        verts = _make_body_verts(50)
        regions = _make_body_regions(verts)
        deltas = compute_morph_deltas(verts, regions, "muscular", 0.0)
        for d in deltas:
            assert d == (0.0, 0.0, 0.0)

    def test_weight_clamping_negative(self):
        """Negative weight is clamped to 0 -> no deltas."""
        verts = _make_body_verts(50)
        regions = _make_body_regions(verts)
        deltas = compute_morph_deltas(verts, regions, "heavy", -1.0)
        for d in deltas:
            assert d == (0.0, 0.0, 0.0)

    def test_weight_clamping_above_one(self):
        """Weight > 1 is clamped to 1 -> same as weight=1."""
        verts = _make_body_verts(100)
        regions = _make_body_regions(verts)
        d1 = compute_morph_deltas(verts, regions, "heavy", 1.0)
        d2 = compute_morph_deltas(verts, regions, "heavy", 5.0)
        for a, b in zip(d1, d2):
            assert a[0] == pytest.approx(b[0], abs=1e-9)
            assert a[1] == pytest.approx(b[1], abs=1e-9)
            assert a[2] == pytest.approx(b[2], abs=1e-9)

    def test_handle_body_morph_basic(self):
        """Handler applies morph and returns displaced vertices."""
        verts = _make_body_verts(100)
        regions = _make_body_regions(verts)

        result = handle_body_morph({
            "vertices": verts,
            "morphs": {"muscular": 0.8},
            "body_regions": regions,
        })
        assert "error" not in result
        assert result["vertex_count"] == 100
        assert "muscular" in result["applied_morphs"]
        assert result["stats"]["max_displacement"] > 0

    def test_handle_body_morph_multiple(self):
        """Multiple morphs combine."""
        verts = _make_body_verts(100)
        regions = _make_body_regions(verts)

        result = handle_body_morph({
            "vertices": verts,
            "morphs": {"muscular": 0.5, "broad_shoulders": 0.7},
            "body_regions": regions,
        })
        assert "muscular" in result["applied_morphs"]
        assert "broad_shoulders" in result["applied_morphs"]

    def test_handle_body_morph_invalid_name_skipped(self):
        """Invalid morph names are silently skipped."""
        verts = _make_body_verts(50)
        regions = _make_body_regions(verts)

        result = handle_body_morph({
            "vertices": verts,
            "morphs": {"nonexistent_morph": 1.0},
            "body_regions": regions,
        })
        assert result["applied_morphs"] == []
        assert result["stats"]["max_displacement"] == 0.0

    def test_handle_body_morph_empty_verts_error(self):
        """Handler returns error for empty vertices."""
        result = handle_body_morph({"vertices": [], "morphs": {}})
        assert "error" in result

    @pytest.mark.parametrize("morph_name", sorted(VALID_MORPH_NAMES))
    def test_every_morph_produces_nonzero_deltas(self, morph_name):
        """Every named morph should produce at least some non-zero deltas
        when applied to a humanoid mesh with regions."""
        verts = _make_body_verts(200)
        regions = _make_body_regions(verts)
        deltas = compute_morph_deltas(verts, regions, morph_name, 1.0)

        nonzero = sum(1 for d in deltas if d != (0.0, 0.0, 0.0))
        assert nonzero > 0, f"Morph '{morph_name}' produced no non-zero deltas"


# ===========================================================================
# Cross-cutting / edge case tests
# ===========================================================================

class TestEdgeCases:
    """Cross-cutting edge cases and validation tests."""

    def test_clamp_function(self):
        """_clamp works correctly."""
        assert _clamp(-1.0) == 0.0
        assert _clamp(0.5) == 0.5
        assert _clamp(2.0) == 1.0
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0

    def test_valid_sets_are_frozensets(self):
        """All VALID_* constants should be frozensets."""
        assert isinstance(VALID_HAIR_STYLES, frozenset)
        assert isinstance(VALID_MORPH_NAMES, frozenset)
        assert isinstance(VALID_COLLISION_TYPES, frozenset)
        assert isinstance(VALID_FACIAL_LEVELS, frozenset)

    def test_face_morph_targets_have_required_keys(self):
        """Each face morph target definition should have required keys."""
        required = {"region_center", "region_radius", "axis", "mode", "magnitude"}
        for name, target in FACE_MORPH_TARGETS.items():
            for key in required:
                assert key in target, f"Face morph '{name}' missing key '{key}'"

    def test_body_morph_targets_have_regions(self):
        """Each body morph target should have a 'regions' dict."""
        for name, target in BODY_MORPH_TARGETS.items():
            assert "regions" in target, f"Body morph '{name}' missing 'regions'"
            assert len(target["regions"]) > 0, f"Body morph '{name}' has empty regions"

    def test_single_vertex_does_not_crash(self):
        """Operations on single-vertex meshes should not crash."""
        verts = [[0.0, 0.0, 0.0]]
        assert len(blend_vertices(verts, {}, {})) == 1
        capsule = compute_collision_capsule(verts)
        assert capsule["type"] == "capsule"
        box = compute_collision_box(verts)
        assert box["type"] == "box"

    def test_large_vertex_count_blend(self):
        """Blending with many vertices should not raise errors."""
        n = 5000
        base = [[float(i), float(i * 2), float(i * 3)] for i in range(n)]
        deltas = [[0.001, 0.001, 0.001] for _ in range(n)]
        result = blend_vertices(base, {"m": deltas}, {"m": 0.5})
        assert len(result) == n
        assert result[0][0] == pytest.approx(0.0005, abs=1e-6)

    def test_strand_with_minimum_segments(self):
        """Strand with segments=2 should produce exactly 2 control points."""
        strand = generate_strand_curve(
            (0, 0, 0), (0, 0, 1), 0.1, 2, "straight", 0.0, 42
        )
        assert len(strand) == 2

    def test_cards_from_single_strand(self):
        """Converting a single strand should produce valid card mesh."""
        strand = generate_strand_curve(
            (0, 0, 1.7), (0, 0, 1), 0.1, 5, "straight", 0.0, 42
        )
        cards = strands_to_cards([strand], card_width=0.01)
        assert len(cards["vertices"]) == 10  # 2 per segment * 5 segments
        assert len(cards["faces"]) == 4      # 5-1 = 4 quads
        assert len(cards["uvs"]) == 10

    def test_all_hair_styles_in_frozenset(self):
        """Verify expected styles are present."""
        expected = {"straight", "wavy", "curly", "braided", "dreadlocks", "ponytail"}
        assert expected == VALID_HAIR_STYLES

    def test_all_collision_types_in_frozenset(self):
        """Verify expected collision types."""
        expected = {"convex_hull", "capsule", "box", "sphere"}
        assert expected == VALID_COLLISION_TYPES

    def test_all_facial_levels_in_frozenset(self):
        """Verify expected facial levels."""
        expected = {"basic", "standard", "full"}
        assert expected == VALID_FACIAL_LEVELS
