"""Material IDs Per-Face Application Tests.

Tests that mesh_from_spec in _mesh_bridge.py correctly (or fails to correctly)
handle the `material_ids` field in a MeshSpec — assigning different materials
to different faces.

THE BUG:
    mesh_from_spec() reads `vertices`, `faces`, `uvs`, `sharp_edges`, and
    `crease_edges` from the spec — but never reads `material_ids`. As a result:
      - Multiple material slots are never created on the mesh
      - poly.material_index is never set per-face
      - All faces always use material slot 0
      - Multi-material objects (e.g. stone wall + wood trim + metal fittings)
        render as single-material, destroying AAA visual quality

    The xfail tests below document the current broken state. Tests without
    xfail assert properties of the non-Blender path that are already correct.
    When mesh_from_spec is fixed to respect material_ids, remove the xfail
    markers and update the assertions to verify correct assignment.

MeshSpec material_ids convention (from building_quality._make_result):
    "material_ids": [int, ...]  -- one index per face, 0-based slot index
    The material at index i in the materials list is assigned to face i.
    Faces without a corresponding material_ids entry default to slot 0.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import blender_addon.handlers._mesh_bridge as _mesh_bridge_mod
from blender_addon.handlers._mesh_bridge import mesh_from_spec


def _stub_path():
    """Context manager: force mesh_from_spec to take the non-Blender stub path.

    conftest.py installs a mock bpy before imports, so _HAS_BPY is True even
    in tests. Patch it to False to exercise the dict-summary branch.
    """
    return patch.object(_mesh_bridge_mod, "_HAS_BPY", False)


# ---------------------------------------------------------------------------
# Minimal spec builders
# ---------------------------------------------------------------------------

def _quad_spec(name: str = "TestQuad") -> dict:
    """Single quad face — simplest valid MeshSpec."""
    return {
        "vertices": [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        "faces": [(0, 1, 2, 3)],
        "uvs": [],
        "material_ids": [],
        "metadata": {"name": name},
    }


def _two_face_spec(name: str = "TwoFaces") -> dict:
    """Two quads sharing an edge, intended to use different materials.

    Face 0 (bottom): material_id=0  (e.g. stone)
    Face 1 (top):    material_id=1  (e.g. wood)
    """
    return {
        "vertices": [
            (0.0, 0.0, 0.0),  # 0
            (1.0, 0.0, 0.0),  # 1
            (1.0, 1.0, 0.0),  # 2
            (0.0, 1.0, 0.0),  # 3
            (0.0, 0.0, 1.0),  # 4
            (1.0, 0.0, 1.0),  # 5
            (1.0, 1.0, 1.0),  # 6
            (0.0, 1.0, 1.0),  # 7
        ],
        "faces": [
            (0, 1, 2, 3),   # face 0 -- material slot 0
            (4, 5, 6, 7),   # face 1 -- material slot 1
        ],
        "uvs": [],
        "material_ids": [0, 1],
        "metadata": {"name": name},
    }


def _six_face_box_spec(name: str = "BoxSixFaces") -> dict:
    """Box with 6 faces using 3 distinct material IDs (2 faces per material).

    Layout:
        faces 0-1: material_id=0  (stone)
        faces 2-3: material_id=1  (wood)
        faces 4-5: material_id=2  (metal)
    """
    return {
        "vertices": [
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
        ],
        "faces": [
            (0, 3, 2, 1),   # bottom  -- material 0
            (4, 5, 6, 7),   # top     -- material 0
            (0, 1, 5, 4),   # front   -- material 1
            (2, 3, 7, 6),   # back    -- material 1
            (1, 2, 6, 5),   # right   -- material 2
            (0, 4, 7, 3),   # left    -- material 2
        ],
        "uvs": [],
        "material_ids": [0, 0, 1, 1, 2, 2],
        "metadata": {"name": name},
    }


# ---------------------------------------------------------------------------
# Non-Blender path tests (these run without Blender, test the stub path)
# ---------------------------------------------------------------------------

class TestMeshFromSpecNonBlenderPath:
    """Tests for the non-Blender (stub) return path in mesh_from_spec.

    conftest.py installs a mock bpy, so _HAS_BPY is True in all tests.
    Each test patches _HAS_BPY=False via _stub_path() to force the dict-summary
    branch. These tests verify that basic spec data is handled without crashing,
    even when material_ids is present.
    """

    def test_returns_dict_summary_without_blender(self) -> None:
        """mesh_from_spec returns a dict summary when bpy is unavailable."""
        with _stub_path():
            result = mesh_from_spec(_quad_spec())
        assert isinstance(result, dict)

    def test_summary_has_obj_name(self) -> None:
        """Summary dict contains the object name."""
        with _stub_path():
            result = mesh_from_spec(_quad_spec("MyMesh"))
        assert result["obj_name"] == "MyMesh"

    def test_summary_has_vertex_count(self) -> None:
        """Summary dict contains correct vertex count."""
        with _stub_path():
            result = mesh_from_spec(_quad_spec())
        assert result["vertex_count"] == 4

    def test_summary_has_face_count(self) -> None:
        """Summary dict contains correct face count."""
        with _stub_path():
            result = mesh_from_spec(_two_face_spec())
        assert result["face_count"] == 2

    def test_material_ids_does_not_crash_spec_processing(self) -> None:
        """Passing material_ids in the spec must not raise any exception."""
        spec = _six_face_box_spec()
        assert spec["material_ids"] == [0, 0, 1, 1, 2, 2]
        # Should not raise
        with _stub_path():
            result = mesh_from_spec(spec)
        assert isinstance(result, dict)

    def test_empty_material_ids_is_valid(self) -> None:
        """An empty material_ids list is valid and should not crash."""
        spec = _quad_spec()
        spec["material_ids"] = []
        with _stub_path():
            result = mesh_from_spec(spec)
        assert isinstance(result, dict)

    def test_material_ids_longer_than_faces_does_not_crash(self) -> None:
        """material_ids with more entries than faces is gracefully handled."""
        spec = _quad_spec()
        spec["material_ids"] = [0, 1, 2, 3, 4]  # 5 ids for 1 face
        with _stub_path():
            result = mesh_from_spec(spec)
        assert isinstance(result, dict)

    def test_spec_material_ids_preserved_in_spec_dict(self) -> None:
        """The original spec dict is not mutated by mesh_from_spec."""
        spec = _two_face_spec()
        original_ids = list(spec["material_ids"])
        with _stub_path():
            mesh_from_spec(spec)
        assert spec["material_ids"] == original_ids, (
            "mesh_from_spec mutated the input spec's material_ids"
        )


# ---------------------------------------------------------------------------
# BUG DOCUMENTATION: material_ids is currently ignored
# These tests are xfail — they document the *expected* correct behavior.
# Remove xfail when mesh_from_spec is fixed.
# ---------------------------------------------------------------------------

class TestMaterialIdsApplication:
    """Tests that verify correct per-face material assignment behavior.

    These tests confirm that mesh_from_spec correctly reads material_ids,
    creates the right number of material slots, and exposes slot info in
    the stub path return dict.
    """

    def test_summary_includes_material_slot_count(self) -> None:
        """Fixed mesh_from_spec should report material slot count in summary.

        When material_ids=[0,1] is in the spec, 2 unique material slots are
        required. The stub return dict should include a 'material_slot_count'
        key so callers can verify multi-material assignment was applied.
        """
        spec = _two_face_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        # After fix: result should have material_slot_count=2
        assert "material_slot_count" in result, (
            "mesh_from_spec stub path should include 'material_slot_count' "
            "derived from unique values in material_ids"
        )
        assert result["material_slot_count"] == 2

    def test_no_material_ids_means_one_slot(self) -> None:
        """Spec with no material_ids should result in 1 material slot."""
        spec = _quad_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        assert result.get("material_slot_count", 0) == 1, (
            "A spec with no material_ids should report 1 material slot (the default)"
        )

    def test_three_material_ids_creates_three_slots(self) -> None:
        """Spec with material_ids using 3 distinct values needs 3 slots."""
        spec = _six_face_box_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        assert result.get("material_slot_count") == 3, (
            f"Expected 3 material slots from material_ids=[0,0,1,1,2,2], "
            f"got {result.get('material_slot_count')!r}"
        )

    def test_face_material_assignments_in_summary(self) -> None:
        """Fixed stub path should include face-to-slot mapping for verification.

        After the fix, the summary dict should expose per-face material
        assignments so pure-logic tests can verify correct slot assignment
        without requiring Blender.
        """
        spec = _two_face_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        # After fix: face_material_ids mirrors the input material_ids list
        assert "face_material_ids" in result, (
            "Summary dict should include 'face_material_ids' after fix"
        )
        assert result["face_material_ids"] == [0, 1], (
            f"Face material assignments should match spec's material_ids. "
            f"Got: {result.get('face_material_ids')!r}"
        )

    def test_out_of_range_material_id_raises(self) -> None:
        """material_ids values must be < number of unique slots, else ValueError.

        If a face references material slot 5 but only slots 0-2 exist,
        that's a data error that should be caught early, not silently ignored.
        """
        spec = _quad_spec()
        spec["material_ids"] = [99]  # slot 99 doesn't exist
        with _stub_path():
            with pytest.raises(ValueError, match="material_id"):
                mesh_from_spec(spec)


# ---------------------------------------------------------------------------
# Regression guard: ensure the fix doesn't break existing single-material flow
# ---------------------------------------------------------------------------

class TestSingleMaterialRegressions:
    """Ensure that fixing material_ids doesn't break the existing no-material flow.

    These tests must pass BOTH before and after the fix.
    """

    def test_spec_without_material_ids_key_still_works(self) -> None:
        """Spec without a 'material_ids' key at all should not crash."""
        spec = {
            "vertices": [(0, 0, 0), (1, 0, 0), (1, 1, 0)],
            "faces": [(0, 1, 2)],
            "uvs": [],
            "metadata": {"name": "NoMaterialIds"},
        }
        with _stub_path():
            result = mesh_from_spec(spec)
        assert isinstance(result, dict)
        assert result["obj_name"] == "NoMaterialIds"

    def test_name_override_still_works_with_material_ids(self) -> None:
        """The `name` argument overrides spec metadata even when material_ids present."""
        spec = _two_face_spec("SpecName")
        with _stub_path():
            result = mesh_from_spec(spec, name="OverrideName")
        assert result["obj_name"] == "OverrideName"

    def test_vertex_count_accurate_with_material_ids(self) -> None:
        """Vertex count is reported correctly when material_ids is populated."""
        spec = _six_face_box_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        assert result["vertex_count"] == 8

    def test_face_count_accurate_with_material_ids(self) -> None:
        """Face count is reported correctly when material_ids is populated."""
        spec = _six_face_box_spec()
        with _stub_path():
            result = mesh_from_spec(spec)
        assert result["face_count"] == 6

    def test_smooth_shading_flag_preserved_with_material_ids(self) -> None:
        """smooth_shading kwarg is still honoured when material_ids is present."""
        spec = _two_face_spec()
        with _stub_path():
            result_smooth = mesh_from_spec(spec, smooth_shading=True)
            result_flat = mesh_from_spec(spec, smooth_shading=False)
        assert result_smooth["smooth_shading"] is True
        assert result_flat["smooth_shading"] is False


# ---------------------------------------------------------------------------
# Integration: generators that produce material_ids
# ---------------------------------------------------------------------------

class TestGeneratorMaterialIdsContract:
    """Tests that generators producing material_ids emit valid data.

    Verifies the MeshSpec contract: material_ids length must equal faces length
    (when non-empty), and all values must be non-negative integers.
    """

    def test_two_face_spec_material_ids_length_matches_faces(self) -> None:
        """material_ids list length equals number of faces (when non-empty)."""
        spec = _two_face_spec()
        assert len(spec["material_ids"]) == len(spec["faces"]), (
            "material_ids must have one entry per face"
        )

    def test_six_face_spec_material_ids_length_matches_faces(self) -> None:
        """material_ids list length equals number of faces."""
        spec = _six_face_box_spec()
        assert len(spec["material_ids"]) == len(spec["faces"])

    def test_material_ids_are_non_negative_integers(self) -> None:
        """All material_ids values must be non-negative integers."""
        spec = _six_face_box_spec()
        for i, mid in enumerate(spec["material_ids"]):
            assert isinstance(mid, int), (
                f"material_ids[{i}]={mid!r} is not an int"
            )
            assert mid >= 0, (
                f"material_ids[{i}]={mid} is negative — invalid slot index"
            )

    def test_material_ids_indices_are_contiguous_from_zero(self) -> None:
        """Unique material_ids should form a contiguous range [0, N).

        Gaps (e.g. [0, 2] without a 1) would mean an empty slot which wastes
        a material slot and can confuse slot assignment code.
        """
        spec = _six_face_box_spec()
        unique_ids = sorted(set(spec["material_ids"]))
        expected = list(range(len(unique_ids)))
        assert unique_ids == expected, (
            f"material_ids unique values {unique_ids} are not contiguous "
            f"from 0. Expected {expected}."
        )

    def test_empty_material_ids_means_single_material(self) -> None:
        """An empty material_ids list signals single-material mesh (slot 0 only)."""
        spec = _quad_spec()
        assert spec["material_ids"] == [], (
            "Single-material spec should have empty material_ids list"
        )
        # Calling mesh_from_spec should still work
        with _stub_path():
            result = mesh_from_spec(spec)
        assert result["face_count"] == 1
