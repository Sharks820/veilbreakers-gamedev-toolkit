"""Tests for cliff geometry generation (55-03 Task 2).

Verifies that _cliff_face_mesh_spec and _ledge_mesh_spec produce real
geometry (vertices, faces, material indices) rather than empty placeholders,
and that insert_hero_cliff_meshes records mesh specs on side_effects.
"""

import numpy as np
import pytest

from blender_addon.handlers.terrain_semantics import (
    BBox,
    TerrainIntentState,
    TerrainMaskStack,
    TerrainPipelineState,
)
from blender_addon.handlers.terrain_cliffs import (
    CliffStructure,
    _cliff_face_mesh_spec,
    _ledge_mesh_spec,
    insert_hero_cliff_meshes,
    add_cliff_ledges,
    build_talus_field,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stack(size: int = 32) -> TerrainMaskStack:
    """Build a stack with a cliff-like height ramp."""
    rng = np.random.default_rng(99)
    # Height ramp: low at top rows, high at bottom rows (cliff in the middle)
    height = np.zeros((size, size), dtype=np.float64)
    for r in range(size):
        height[r, :] = float(r) * 2.0  # 0..62 m
    height += rng.uniform(-0.5, 0.5, size=(size, size))
    return TerrainMaskStack(
        tile_size=size - 1,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )


def _make_state(stack: TerrainMaskStack | None = None) -> TerrainPipelineState:
    if stack is None:
        stack = _make_stack()
    intent = TerrainIntentState(
        seed=42,
        region_bounds=BBox(min_x=0.0, min_y=0.0,
                           max_x=float(stack.tile_size),
                           max_y=float(stack.tile_size)),
        tile_size=stack.tile_size,
        cell_size=stack.cell_size,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


def _make_cliff(stack: TerrainMaskStack, tier: str = "hero") -> CliffStructure:
    """Build a synthetic cliff spanning the middle rows of the stack."""
    size = stack.height.shape[0]
    face_mask = np.zeros((size, size), dtype=bool)
    # Cliff face in rows 10-20
    face_mask[10:20, 5:25] = True
    lip = np.array([[10, c] for c in range(5, 25)], dtype=np.int32)
    h = np.asarray(stack.height, dtype=np.float64)
    bounds = BBox(
        min_x=stack.world_origin_x + 5.0,
        min_y=stack.world_origin_y + 10.0,
        max_x=stack.world_origin_x + 25.0,
        max_y=stack.world_origin_y + 20.0,
    )
    return CliffStructure(
        cliff_id="cliff_test_00",
        lip_polyline=lip,
        face_mask=face_mask,
        ledges=[],
        talus_mask=None,
        world_bounds=bounds,
        tier=tier,
        max_height_m=float(h[face_mask].max()),
        min_height_m=float(h[face_mask].min()),
        cell_count=int(face_mask.sum()),
    )


# ---------------------------------------------------------------------------
# _cliff_face_mesh_spec
# ---------------------------------------------------------------------------


class TestCliffFaceMeshSpec:
    """Cliff face geometry must produce valid vertices and faces."""

    def test_produces_vertices_and_faces(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        assert len(spec["vertices"]) > 0, "No vertices generated"
        assert len(spec["faces"]) > 0, "No faces generated"

    def test_face_indices_valid(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        num_verts = len(spec["vertices"])
        for face in spec["faces"]:
            for idx in face:
                assert 0 <= idx < num_verts

    def test_material_indices_match_faces(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        assert len(spec["material_indices"]) == len(spec["faces"])

    def test_z_range_within_cliff_bounds(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        zs = [v[2] for v in spec["vertices"]]
        # Z values should span the cliff's height range (with some roughness tolerance)
        assert min(zs) >= cliff.min_height_m - 1.0
        assert max(zs) <= cliff.max_height_m + 1.0

    def test_has_overhang_at_top(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, overhang_fraction=0.3, seed=42)
        # Material index 2 = overhang zone; should have some
        assert 2 in spec["material_indices"], "No overhang material zone"

    def test_deterministic_with_seed(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        s1 = _cliff_face_mesh_spec(cliff, stack, seed=123)
        s2 = _cliff_face_mesh_spec(cliff, stack, seed=123)
        assert s1["vertices"] == s2["vertices"]
        assert s1["faces"] == s2["faces"]

    def test_different_seed_different_output(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        s1 = _cliff_face_mesh_spec(cliff, stack, seed=1)
        s2 = _cliff_face_mesh_spec(cliff, stack, seed=999)
        assert s1["vertices"] != s2["vertices"]

    def test_empty_for_tiny_z_span(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        cliff.min_height_m = 10.0
        cliff.max_height_m = 10.1  # < 0.5m span
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        assert spec["vertices"] == []

    def test_empty_for_no_bounds(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        cliff.world_bounds = None
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        assert spec["vertices"] == []

    def test_cliff_id_in_result(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _cliff_face_mesh_spec(cliff, stack, seed=42)
        assert spec["cliff_id"] == "cliff_test_00"


# ---------------------------------------------------------------------------
# _ledge_mesh_spec
# ---------------------------------------------------------------------------


class TestLedgeMeshSpec:
    """Ledge geometry for cliff horizontal interruptions."""

    def test_produces_geometry_when_ledge_exists(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        # Add a ledge
        cliff = add_cliff_ledges(cliff, count=1, height=stack.height)
        assert len(cliff.ledges) >= 1
        spec = _ledge_mesh_spec(cliff, stack, 0, seed=42)
        assert len(spec["vertices"]) > 0
        assert len(spec["faces"]) > 0

    def test_empty_for_invalid_index(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        spec = _ledge_mesh_spec(cliff, stack, 99, seed=42)
        assert spec["vertices"] == []

    def test_ledge_z_within_cliff_range(self):
        stack = _make_stack()
        cliff = _make_cliff(stack)
        cliff = add_cliff_ledges(cliff, count=2, height=stack.height)
        for li in range(len(cliff.ledges)):
            spec = _ledge_mesh_spec(cliff, stack, li, seed=42)
            if spec["vertices"]:
                assert spec["ledge_z"] >= cliff.min_height_m - 1.0
                assert spec["ledge_z"] <= cliff.max_height_m + 1.0


# ---------------------------------------------------------------------------
# insert_hero_cliff_meshes (integration)
# ---------------------------------------------------------------------------


class TestInsertHeroCliffMeshes:
    """insert_hero_cliff_meshes must produce mesh specs, not just intents."""

    def test_generates_mesh_spec_side_effects(self):
        stack = _make_stack()
        state = _make_state(stack)
        cliff = _make_cliff(stack, tier="hero")
        cliff = add_cliff_ledges(cliff, count=1, height=stack.height)
        build_talus_field(cliff, stack)

        intents = insert_hero_cliff_meshes(state, [cliff])
        assert len(intents) >= 1

        # Should have cliff_mesh_spec entries in side_effects
        mesh_specs = [s for s in state.side_effects if s.startswith("cliff_mesh_spec:")]
        assert len(mesh_specs) >= 1, "No cliff_mesh_spec side effects recorded"

        # Face mesh spec should be present
        face_specs = [s for s in mesh_specs if ":face:" in s]
        assert len(face_specs) == 1

    def test_skips_non_hero_cliffs(self):
        stack = _make_stack()
        state = _make_state(stack)
        cliff = _make_cliff(stack, tier="secondary")
        intents = insert_hero_cliff_meshes(state, [cliff])
        assert len(intents) == 0

    def test_records_talus_scatter(self):
        stack = _make_stack()
        state = _make_state(stack)
        cliff = _make_cliff(stack, tier="hero")
        build_talus_field(cliff, stack)
        insert_hero_cliff_meshes(state, [cliff])
        talus_entries = [s for s in state.side_effects if s.startswith("cliff_talus_scatter:")]
        # Should have talus if talus_mask was generated
        if cliff.talus_mask is not None and cliff.talus_mask.any():
            assert len(talus_entries) >= 1

    def test_backward_compatible_intent_strings(self):
        """Original intent format must still be emitted for integration tests."""
        stack = _make_stack()
        state = _make_state(stack)
        cliff = _make_cliff(stack, tier="hero")
        intents = insert_hero_cliff_meshes(state, [cliff])
        assert any("insert_hero_cliff_mesh:" in i for i in intents)
