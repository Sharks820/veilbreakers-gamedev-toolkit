"""Tests for Skin Modifier-based character body generation.

Validates:
- All 8 humanoid body type skeletons have valid vertex/edge structure
- Edge connectivity (no disconnected components) for all types
- Symmetry (left/right mirror within tolerance) for humanoid and monster
- Proportions (head:body ratio, arm span:height ratio)
- Generated Blender code is valid Python (ast.parse)
- All body types produce different skeleton vertex positions
- Radius values are positive for all vertices
- Vertex names are present for rigging
- Monster skeletons for all 6 types are well-formed
- Brand tagging works for all 10 brands
- Handler functions return correct structure
"""

from __future__ import annotations

import ast
import math

import pytest

from blender_addon.handlers.character_skin_modifier import (
    VALID_GENDERS,
    VALID_BUILDS,
    VALID_MONSTER_TYPES,
    ALL_BRANDS,
    BODY_SKELETONS,
    MONSTER_SKELETONS,
    BUILD_MULTIPLIERS,
    GENDER_MULTIPLIERS,
    get_skeleton,
    get_monster_skeleton,
    generate_skin_body_code,
    generate_skin_monster_code,
    handle_generate_skin_body,
    handle_generate_character_body,
    validate_skeleton_connectivity,
    validate_skeleton_symmetry,
    validate_skeleton_proportions,
)


# ---------------------------------------------------------------------------
# Parametrize over all humanoid combinations
# ---------------------------------------------------------------------------

ALL_HUMANOID_COMBOS = [
    (g, b) for g in VALID_GENDERS for b in VALID_BUILDS
]


@pytest.fixture(
    params=ALL_HUMANOID_COMBOS,
    ids=[f"{g}_{b}" for g, b in ALL_HUMANOID_COMBOS],
)
def humanoid_skeleton(request):
    """Get skeleton for each gender/build combo."""
    gender, build = request.param
    return get_skeleton(gender, build), gender, build


@pytest.fixture(
    params=list(VALID_MONSTER_TYPES),
    ids=list(VALID_MONSTER_TYPES),
)
def monster_skeleton(request):
    """Get skeleton for each monster type."""
    monster_type = request.param
    return get_monster_skeleton(monster_type), monster_type


# ---------------------------------------------------------------------------
# Test: Skeleton structure validity
# ---------------------------------------------------------------------------


class TestSkeletonStructure:
    """Verify all skeleton definitions have valid vertex/edge structure."""

    def test_has_vertices(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        assert len(skel["vertices"]) > 0, f"{gender}_{build}: no vertices"

    def test_has_edges(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        assert len(skel["edges"]) > 0, f"{gender}_{build}: no edges"

    def test_has_radii(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        assert len(skel["radii"]) == len(skel["vertices"]), (
            f"{gender}_{build}: radii count != vertex count"
        )

    def test_has_names(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        assert len(skel["names"]) == len(skel["vertices"]), (
            f"{gender}_{build}: names count != vertex count"
        )

    def test_vertices_are_3tuples(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        for i, v in enumerate(skel["vertices"]):
            assert len(v) == 3, f"{gender}_{build}: vertex {i} has {len(v)} components"
            for c in v:
                assert isinstance(c, (int, float)), (
                    f"{gender}_{build}: vertex {i} has non-numeric component"
                )
                assert math.isfinite(c), (
                    f"{gender}_{build}: vertex {i} has non-finite component"
                )

    def test_radii_are_2tuples(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        for i, r in enumerate(skel["radii"]):
            assert len(r) == 2, f"{gender}_{build}: radius {i} has {len(r)} components"

    def test_edge_indices_valid(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        n = len(skel["vertices"])
        for ei, (a, b) in enumerate(skel["edges"]):
            assert 0 <= a < n, f"{gender}_{build}: edge {ei} index {a} out of range"
            assert 0 <= b < n, f"{gender}_{build}: edge {ei} index {b} out of range"
            assert a != b, f"{gender}_{build}: edge {ei} is self-loop ({a}, {b})"

    def test_names_are_nonempty_strings(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        for i, name in enumerate(skel["names"]):
            assert isinstance(name, str), (
                f"{gender}_{build}: name {i} is not a string"
            )
            assert len(name) > 0, (
                f"{gender}_{build}: name {i} is empty"
            )

    def test_names_are_unique(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        names = skel["names"]
        assert len(names) == len(set(names)), (
            f"{gender}_{build}: duplicate vertex names found"
        )


# ---------------------------------------------------------------------------
# Test: Positive radii
# ---------------------------------------------------------------------------


class TestPositiveRadii:
    """Verify all radius values are positive."""

    def test_humanoid_radii_positive(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        for i, (rx, ry) in enumerate(skel["radii"]):
            assert rx > 0, f"{gender}_{build}: vertex {i} rx={rx} <= 0"
            assert ry > 0, f"{gender}_{build}: vertex {i} ry={ry} <= 0"

    def test_monster_radii_positive(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        for i, (rx, ry) in enumerate(skel["radii"]):
            assert rx > 0, f"{monster_type}: vertex {i} rx={rx} <= 0"
            assert ry > 0, f"{monster_type}: vertex {i} ry={ry} <= 0"


# ---------------------------------------------------------------------------
# Test: Connectivity
# ---------------------------------------------------------------------------


class TestConnectivity:
    """Verify all skeletons are fully connected (no isolated components)."""

    def test_humanoid_connected(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        errors = validate_skeleton_connectivity(skel)
        assert not errors, f"{gender}_{build}: {errors}"

    def test_monster_connected(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        errors = validate_skeleton_connectivity(skel)
        assert not errors, f"{monster_type}: {errors}"


# ---------------------------------------------------------------------------
# Test: Symmetry
# ---------------------------------------------------------------------------


class TestSymmetry:
    """Verify left/right mirror symmetry within tolerance."""

    def test_humanoid_symmetry(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        errors = validate_skeleton_symmetry(skel, tolerance=0.002)
        assert not errors, f"{gender}_{build}: {errors}"

    def test_monster_symmetry(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        # Serpent has no mirror symmetry, skip
        if monster_type == "serpent":
            pytest.skip("Serpent has no lateral symmetry")
        errors = validate_skeleton_symmetry(skel, tolerance=0.002)
        assert not errors, f"{monster_type}: {errors}"


# ---------------------------------------------------------------------------
# Test: Proportions
# ---------------------------------------------------------------------------


class TestProportions:
    """Verify anatomical proportions for humanoid skeletons."""

    def test_humanoid_proportions(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        errors = validate_skeleton_proportions(skel)
        assert not errors, f"{gender}_{build}: {errors}"

    def test_height_approximately_1_8m(self, humanoid_skeleton):
        skel, gender, build = humanoid_skeleton
        positions = skel["vertices"]
        names = skel["names"]
        name_map = {n: i for i, n in enumerate(names)}

        head_top_idx = name_map.get("HeadTop")
        toe_names = [n for n in names if "Toe" in n]

        if head_top_idx is not None and toe_names:
            top_z = positions[head_top_idx][2]
            min_z = min(positions[name_map[tn]][2] for tn in toe_names)
            height = top_z - min_z
            # Allow 1.5-2.0m range across all builds
            assert 1.5 < height < 2.0, (
                f"{gender}_{build}: height={height:.3f}m outside [1.5, 2.0]"
            )

    def test_arms_at_shoulder_height(self, humanoid_skeleton):
        """Arms should start at approximately shoulder height (T-pose)."""
        skel, gender, build = humanoid_skeleton
        names = skel["names"]
        positions = skel["vertices"]
        name_map = {n: i for i, n in enumerate(names)}

        chest_idx = name_map.get("Chest")
        l_shoulder_idx = name_map.get("LeftShoulder")
        r_shoulder_idx = name_map.get("RightShoulder")

        if chest_idx is not None and l_shoulder_idx is not None:
            chest_z = positions[chest_idx][2]
            l_shoulder_z = positions[l_shoulder_idx][2]
            # Shoulder should be within 0.15m of chest height
            assert abs(l_shoulder_z - chest_z) < 0.15, (
                f"{gender}_{build}: left shoulder z={l_shoulder_z:.3f} "
                f"too far from chest z={chest_z:.3f}"
            )

        if chest_idx is not None and r_shoulder_idx is not None:
            chest_z = positions[chest_idx][2]
            r_shoulder_z = positions[r_shoulder_idx][2]
            assert abs(r_shoulder_z - chest_z) < 0.15, (
                f"{gender}_{build}: right shoulder z={r_shoulder_z:.3f} "
                f"too far from chest z={chest_z:.3f}"
            )


# ---------------------------------------------------------------------------
# Test: Different body types produce different skeletons
# ---------------------------------------------------------------------------


class TestBodyTypeVariation:
    """Verify that different gender/build combos produce different skeletons."""

    def test_different_builds_different_positions(self):
        """Each build should produce at least some different vertex positions."""
        skeletons = {}
        for build in VALID_BUILDS:
            skeletons[build] = get_skeleton("male", build)

        for b1 in VALID_BUILDS:
            for b2 in VALID_BUILDS:
                if b1 >= b2:
                    continue
                v1 = skeletons[b1]["vertices"]
                v2 = skeletons[b2]["vertices"]
                # At least one vertex should differ
                has_diff = False
                for p1, p2 in zip(v1, v2):
                    if any(abs(a - b) > 0.001 for a, b in zip(p1, p2)):
                        has_diff = True
                        break
                assert has_diff, f"Builds {b1} and {b2} have identical positions"

    def test_different_builds_different_radii(self):
        """Each build should produce different radii."""
        skeletons = {}
        for build in VALID_BUILDS:
            skeletons[build] = get_skeleton("male", build)

        for b1 in VALID_BUILDS:
            for b2 in VALID_BUILDS:
                if b1 >= b2:
                    continue
                r1 = skeletons[b1]["radii"]
                r2 = skeletons[b2]["radii"]
                has_diff = False
                for (rx1, ry1), (rx2, ry2) in zip(r1, r2):
                    if abs(rx1 - rx2) > 0.0001 or abs(ry1 - ry2) > 0.0001:
                        has_diff = True
                        break
                assert has_diff, f"Builds {b1} and {b2} have identical radii"

    def test_different_genders_different_radii(self):
        """Male vs female should differ in at least shoulder/hip radii."""
        male = get_skeleton("male", "average")
        female = get_skeleton("female", "average")
        # Check that at least one radius differs
        has_diff = False
        for (mrx, mry), (frx, fry) in zip(male["radii"], female["radii"]):
            if abs(mrx - frx) > 0.0001 or abs(mry - fry) > 0.0001:
                has_diff = True
                break
        assert has_diff, "Male and female average have identical radii"

    def test_male_wider_shoulders(self):
        """Male should have wider shoulders than female."""
        male = get_skeleton("male", "average")
        female = get_skeleton("female", "average")

        m_names = male["names"]
        f_names = female["names"]

        m_chest_idx = m_names.index("Chest")
        f_chest_idx = f_names.index("Chest")

        m_chest_rx = male["radii"][m_chest_idx][0]
        f_chest_rx = female["radii"][f_chest_idx][0]

        assert m_chest_rx > f_chest_rx, (
            f"Male chest rx={m_chest_rx:.4f} should be > female chest rx={f_chest_rx:.4f}"
        )

    def test_female_wider_hips(self):
        """Female should have wider hips than male."""
        male = get_skeleton("male", "average")
        female = get_skeleton("female", "average")

        m_names = male["names"]
        f_names = female["names"]

        m_hips_idx = m_names.index("Hips")
        f_hips_idx = f_names.index("Hips")

        m_hips_rx = male["radii"][m_hips_idx][0]
        f_hips_rx = female["radii"][f_hips_idx][0]

        assert f_hips_rx > m_hips_rx, (
            f"Female hips rx={f_hips_rx:.4f} should be > male hips rx={m_hips_rx:.4f}"
        )


# ---------------------------------------------------------------------------
# Test: Monster skeleton structure
# ---------------------------------------------------------------------------


class TestMonsterSkeletonStructure:
    """Verify all 6 monster skeletons are well-formed."""

    def test_has_vertices(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        assert len(skel["vertices"]) > 0, f"{monster_type}: no vertices"

    def test_has_edges(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        assert len(skel["edges"]) > 0, f"{monster_type}: no edges"

    def test_has_names(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        assert len(skel["names"]) == len(skel["vertices"])

    def test_has_radii(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        assert len(skel["radii"]) == len(skel["vertices"])

    def test_edge_indices_valid(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        n = len(skel["vertices"])
        for ei, (a, b) in enumerate(skel["edges"]):
            assert 0 <= a < n, f"{monster_type}: edge {ei} index {a} out of range"
            assert 0 <= b < n, f"{monster_type}: edge {ei} index {b} out of range"

    def test_names_unique(self, monster_skeleton):
        skel, monster_type = monster_skeleton
        names = skel["names"]
        assert len(names) == len(set(names)), f"{monster_type}: duplicate names"

    def test_scale_multiplies_positions(self):
        """Scale=2.0 should roughly double vertex positions."""
        skel1 = get_monster_skeleton("bipedal", scale=1.0)
        skel2 = get_monster_skeleton("bipedal", scale=2.0)
        for p1, p2 in zip(skel1["vertices"], skel2["vertices"]):
            for a, b in zip(p1, p2):
                assert abs(b - a * 2.0) < 0.001, (
                    f"Scale 2x: expected {a * 2.0:.4f}, got {b:.4f}"
                )

    def test_scale_multiplies_radii(self):
        """Scale=2.0 should double radii."""
        skel1 = get_monster_skeleton("quadruped", scale=1.0)
        skel2 = get_monster_skeleton("quadruped", scale=2.0)
        for (rx1, ry1), (rx2, ry2) in zip(skel1["radii"], skel2["radii"]):
            assert abs(rx2 - rx1 * 2.0) < 0.001
            assert abs(ry2 - ry1 * 2.0) < 0.001


# ---------------------------------------------------------------------------
# Test: Monster types are biologically plausible
# ---------------------------------------------------------------------------


class TestMonsterPlausibility:
    """Verify monster skeletons are biologically plausible."""

    def test_serpent_has_no_limbs(self):
        """Serpent should be a pure spine chain with no branches."""
        skel = get_monster_skeleton("serpent")
        names = skel["names"]
        # No arm/leg related names
        for name in names:
            assert "Leg" not in name, f"Serpent has limb vertex: {name}"
            assert "Arm" not in name, f"Serpent has arm vertex: {name}"
            assert "Hand" not in name, f"Serpent has hand vertex: {name}"
            assert "Foot" not in name, f"Serpent has foot vertex: {name}"

    def test_arachnid_has_8_legs(self):
        """Arachnid should have 8 leg chains (4 left + 4 right after mirror)."""
        skel = get_monster_skeleton("arachnid")
        names = skel["names"]
        leg_tips = [n for n in names if n.endswith("_Tip")]
        assert len(leg_tips) == 8, (
            f"Arachnid should have 8 leg tips, got {len(leg_tips)}: {leg_tips}"
        )

    def test_quadruped_has_4_legs(self):
        """Quadruped should have 4 legs after mirror."""
        skel = get_monster_skeleton("quadruped")
        names = skel["names"]
        feet = [n for n in names if "Foot" in n or "Toe" in n]
        # Should have front+rear x left+right = 4 feet + 4 toes
        assert len(feet) >= 4, (
            f"Quadruped should have >= 4 foot/toe vertices, got {len(feet)}"
        )

    def test_avian_has_wings(self):
        """Avian should have wing vertices."""
        skel = get_monster_skeleton("avian")
        names = skel["names"]
        wings = [n for n in names if "Wing" in n]
        assert len(wings) >= 4, (
            f"Avian should have >= 4 wing vertices (L+R), got {len(wings)}"
        )

    def test_blob_has_tentacles(self):
        """Blob should have tentacle chains."""
        skel = get_monster_skeleton("blob")
        names = skel["names"]
        tentacles = [n for n in names if "Tent" in n]
        assert len(tentacles) >= 6, (
            f"Blob should have >= 6 tentacle vertices, got {len(tentacles)}"
        )

    def test_bipedal_has_two_arms_two_legs(self):
        """Bipedal should have 2 arms and 2 legs after mirror."""
        skel = get_monster_skeleton("bipedal")
        names = skel["names"]
        hands = [n for n in names if "Hand" in n]
        feet = [n for n in names if "Foot" in n or "Toe" in n]
        assert len(hands) == 2, f"Bipedal should have 2 hands, got {len(hands)}"
        assert len(feet) >= 2, f"Bipedal should have >= 2 feet, got {len(feet)}"


# ---------------------------------------------------------------------------
# Test: Brand tagging
# ---------------------------------------------------------------------------


class TestBrandTagging:
    """Verify brand vertex group tagging works for all brands."""

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_brand_creates_brand_groups(self, brand):
        skel = get_monster_skeleton("bipedal", brand=brand)
        assert "brand_groups" in skel, f"Brand {brand}: no brand_groups"
        assert "brand_surface" in skel["brand_groups"], (
            f"Brand {brand}: no brand_surface group"
        )
        assert len(skel["brand_groups"]["brand_surface"]) > 0, (
            f"Brand {brand}: empty brand_surface group"
        )

    @pytest.mark.parametrize("brand", ALL_BRANDS)
    def test_brand_name_stored(self, brand):
        skel = get_monster_skeleton("bipedal", brand=brand)
        assert skel.get("brand") == brand

    def test_no_brand_no_groups(self):
        skel = get_monster_skeleton("bipedal", brand=None)
        assert "brand_groups" not in skel


# ---------------------------------------------------------------------------
# Test: Generated code is valid Python
# ---------------------------------------------------------------------------


class TestCodeGeneration:
    """Verify generated Blender code is valid Python via ast.parse."""

    @pytest.mark.parametrize(
        "gender,build",
        ALL_HUMANOID_COMBOS,
        ids=[f"{g}_{b}" for g, b in ALL_HUMANOID_COMBOS],
    )
    def test_humanoid_code_valid_python(self, gender, build):
        code = generate_skin_body_code(gender, build)
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"{gender}_{build}: generated code has syntax error: {e}")

    @pytest.mark.parametrize("monster_type", VALID_MONSTER_TYPES)
    def test_monster_code_valid_python(self, monster_type):
        code = generate_skin_monster_code(monster_type)
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"{monster_type}: generated code has syntax error: {e}")

    @pytest.mark.parametrize("monster_type", VALID_MONSTER_TYPES)
    @pytest.mark.parametrize("brand", ["IRON", "VOID", None])
    def test_monster_code_with_brand_valid(self, monster_type, brand):
        code = generate_skin_monster_code(monster_type, brand=brand)
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(
                f"{monster_type} brand={brand}: syntax error: {e}"
            )

    def test_code_only_uses_allowed_imports(self):
        """Verify code only imports bpy, bmesh, math (allowed by sandbox)."""
        code = generate_skin_body_code("male", "average")
        tree = ast.parse(code)
        allowed_modules = {"bpy", "bmesh", "mathutils", "math", "json"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed_modules, (
                        f"Disallowed import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed_modules, (
                    f"Disallowed import from: {node.module}"
                )

    def test_monster_code_only_uses_allowed_imports(self):
        code = generate_skin_monster_code("bipedal")
        tree = ast.parse(code)
        allowed_modules = {"bpy", "bmesh", "mathutils", "math", "json"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in allowed_modules, (
                        f"Disallowed import: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed_modules, (
                    f"Disallowed import from: {node.module}"
                )

    def test_code_contains_skin_modifier(self):
        """Generated code must use the Skin modifier."""
        code = generate_skin_body_code("male", "average")
        assert "'SKIN'" in code or '"SKIN"' in code, "No SKIN modifier in code"

    def test_code_contains_subdivision(self):
        """Generated code must use Subdivision Surface."""
        code = generate_skin_body_code("male", "average")
        assert "'SUBSURF'" in code or '"SUBSURF"' in code, "No SUBSURF in code"

    def test_code_contains_smooth_shading(self):
        """Generated code must apply smooth shading."""
        code = generate_skin_body_code("male", "average")
        assert "shade_smooth" in code, "No smooth shading in code"

    def test_code_contains_vertex_groups(self):
        """Generated code must create vertex groups for rigging."""
        code = generate_skin_body_code("male", "average")
        assert "vertex_groups" in code, "No vertex groups in code"

    def test_subdivision_level_clamped(self):
        """Subdivision level should be clamped to [1, 3]."""
        code_low = generate_skin_body_code("male", "average", subdivision_level=0)
        assert "subsurf_mod.levels = 1" in code_low

        code_high = generate_skin_body_code("male", "average", subdivision_level=5)
        assert "subsurf_mod.levels = 3" in code_high


# ---------------------------------------------------------------------------
# Test: Rigging vertex names
# ---------------------------------------------------------------------------


class TestRiggingNames:
    """Verify vertex names follow standard rigging conventions."""

    REQUIRED_HUMANOID_BONES = [
        "Hips", "Spine", "Chest", "Neck", "Head",
        "LeftShoulder", "LeftUpperArm", "LeftForeArm", "LeftHand",
        "RightShoulder", "RightUpperArm", "RightForeArm", "RightHand",
        "LeftUpLeg", "LeftLeg", "LeftFoot",
        "RightUpLeg", "RightLeg", "RightFoot",
    ]

    def test_humanoid_has_all_required_bones(self):
        skel = get_skeleton("male", "average")
        names = set(skel["names"])
        for bone_name in self.REQUIRED_HUMANOID_BONES:
            assert bone_name in names, f"Missing required bone name: {bone_name}"

    def test_all_builds_have_same_bone_names(self):
        """All 8 humanoid combos should have the same set of bone names."""
        reference = set(get_skeleton("male", "average")["names"])
        for gender in VALID_GENDERS:
            for build in VALID_BUILDS:
                skel = get_skeleton(gender, build)
                current = set(skel["names"])
                assert current == reference, (
                    f"{gender}_{build} has different bone names. "
                    f"Missing: {reference - current}, Extra: {current - reference}"
                )


# ---------------------------------------------------------------------------
# Test: Handler functions
# ---------------------------------------------------------------------------


class TestHandlers:
    """Verify handler functions return correct structure."""

    def test_handle_generate_skin_body_returns_dict(self):
        result = handle_generate_skin_body({"gender": "male", "build": "average"})
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "code" in result
        assert "skeleton_vertex_count" in result
        assert "next_steps" in result

    def test_handle_generate_skin_body_defaults(self):
        result = handle_generate_skin_body({})
        assert result["gender"] == "male"
        assert result["build"] == "average"
        assert result["name"] == "CharacterBody"

    def test_handle_generate_character_body_humanoid(self):
        result = handle_generate_character_body({
            "gender": "female", "build": "slim",
        })
        assert result["status"] == "success"
        assert "code" in result

    def test_handle_generate_character_body_monster(self):
        result = handle_generate_character_body({
            "monster_type": "quadruped",
            "scale": 1.5,
            "brand": "IRON",
        })
        assert result["status"] == "success"
        assert result["monster_type"] == "quadruped"
        assert result["brand"] == "IRON"
        assert "code" in result

    def test_handler_code_is_parseable(self):
        result = handle_generate_skin_body({
            "gender": "male", "build": "heavy",
        })
        ast.parse(result["code"])

    def test_handler_monster_code_is_parseable(self):
        result = handle_generate_character_body({
            "monster_type": "arachnid",
            "brand": "DREAD",
        })
        ast.parse(result["code"])


# ---------------------------------------------------------------------------
# Test: BODY_SKELETONS pre-computed dict
# ---------------------------------------------------------------------------


class TestBodySkeletonsDict:
    """Verify the pre-computed BODY_SKELETONS dict is correct."""

    def test_has_all_8_combos(self):
        expected_keys = {f"{g}_{b}" for g in VALID_GENDERS for b in VALID_BUILDS}
        assert set(BODY_SKELETONS.keys()) == expected_keys

    def test_each_entry_is_valid_skeleton(self):
        for key, skel in BODY_SKELETONS.items():
            assert "vertices" in skel, f"{key}: missing vertices"
            assert "edges" in skel, f"{key}: missing edges"
            assert "radii" in skel, f"{key}: missing radii"
            assert "names" in skel, f"{key}: missing names"


# ---------------------------------------------------------------------------
# Test: MONSTER_SKELETONS registry
# ---------------------------------------------------------------------------


class TestMonsterSkeletonsRegistry:
    """Verify the MONSTER_SKELETONS registry is correct."""

    def test_has_all_6_types(self):
        for mt in VALID_MONSTER_TYPES:
            assert mt in MONSTER_SKELETONS, f"Missing monster type: {mt}"

    def test_each_entry_has_required_fields(self):
        for mt, data in MONSTER_SKELETONS.items():
            assert "vertices" in data, f"{mt}: missing vertices"
            assert "edges" in data, f"{mt}: missing edges"
            assert "description" in data, f"{mt}: missing description"


# ---------------------------------------------------------------------------
# Test: Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Verify error handling for invalid inputs."""

    def test_invalid_gender_raises(self):
        with pytest.raises(ValueError, match="Invalid gender"):
            get_skeleton("nonbinary", "average")

    def test_invalid_build_raises(self):
        with pytest.raises(ValueError, match="Invalid build"):
            get_skeleton("male", "muscular")

    def test_invalid_monster_type_raises(self):
        with pytest.raises(ValueError, match="Invalid monster_type"):
            get_monster_skeleton("dragon")


# ---------------------------------------------------------------------------
# Test: Elder spine curve
# ---------------------------------------------------------------------------


class TestElderSpineCurve:
    """Verify elder build has forward spine lean."""

    def test_elder_spine_forward_offset(self):
        """Elder should have non-zero Y offset on spine vertices."""
        average = get_skeleton("male", "average")
        elder = get_skeleton("male", "elder")

        avg_names = average["names"]
        eld_names = elder["names"]

        # Spine1 should have forward lean in elder
        spine1_idx = avg_names.index("Spine1")
        avg_y = average["vertices"][spine1_idx][1]
        eld_y = elder["vertices"][spine1_idx][1]

        # Elder should have more forward lean (positive Y)
        assert eld_y > avg_y, (
            f"Elder Spine1 y={eld_y:.4f} should be > average y={avg_y:.4f}"
        )


# ---------------------------------------------------------------------------
# Test: Heavy build is larger
# ---------------------------------------------------------------------------


class TestHeavyBuild:
    """Verify heavy build produces larger radii than slim."""

    def test_heavy_torso_wider_than_slim(self):
        heavy = get_skeleton("male", "heavy")
        slim = get_skeleton("male", "slim")

        names = heavy["names"]
        chest_idx = names.index("Chest")

        heavy_rx = heavy["radii"][chest_idx][0]
        slim_rx = slim["radii"][chest_idx][0]

        assert heavy_rx > slim_rx, (
            f"Heavy chest rx={heavy_rx:.4f} should be > slim rx={slim_rx:.4f}"
        )

    def test_heavy_limbs_thicker_than_slim(self):
        heavy = get_skeleton("male", "heavy")
        slim = get_skeleton("male", "slim")

        names = heavy["names"]
        arm_idx = names.index("LeftUpperArm")

        heavy_rx = heavy["radii"][arm_idx][0]
        slim_rx = slim["radii"][arm_idx][0]

        assert heavy_rx > slim_rx, (
            f"Heavy arm rx={heavy_rx:.4f} should be > slim rx={slim_rx:.4f}"
        )
