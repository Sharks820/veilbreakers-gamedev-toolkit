"""Tests for vegetation_lsystem.py: L-system tree generation, leaf card
placement, wind vertex color baking, L-system string expansion, branch
topology connectivity, and billboard impostor generation.

All pure-logic -- no Blender dependency.
"""

import math

import pytest

from blender_addon.handlers.vegetation_lsystem import (
    LSYSTEM_GRAMMARS,
    BranchSegment,
    bake_wind_vertex_colors,
    branches_to_mesh,
    expand_lsystem,
    generate_billboard_impostor,
    generate_leaf_cards,
    generate_lsystem_tree,
    generate_roots,
    interpret_lsystem,
    prepare_gpu_instancing_export,
)


# ===================================================================
# L-system string expansion
# ===================================================================


class TestExpandLsystem:
    """Test L-system grammar expansion."""

    def test_single_iteration_f_rule(self):
        """Single iteration of F->FF produces 'FF'."""
        result = expand_lsystem("F", {"F": "FF"}, 1)
        assert result == "FF"

    def test_two_iterations_f_rule(self):
        """Two iterations of F->FF produces 'FFFF'."""
        result = expand_lsystem("F", {"F": "FF"}, 2)
        assert result == "FFFF"

    def test_oak_grammar_growth(self):
        """Oak grammar expands to longer strings with iterations."""
        grammar = LSYSTEM_GRAMMARS["oak"]
        r1 = expand_lsystem(grammar["axiom"], grammar["rules"], 1)
        r2 = expand_lsystem(grammar["axiom"], grammar["rules"], 2)
        r3 = expand_lsystem(grammar["axiom"], grammar["rules"], 3)
        assert len(r1) < len(r2) < len(r3)

    def test_brackets_preserved(self):
        """Brackets in rules are preserved through expansion."""
        result = expand_lsystem("F", {"F": "F[+F][-F]"}, 1)
        assert "[" in result
        assert "]" in result
        assert "+" in result
        assert "-" in result

    def test_zero_iterations_returns_axiom(self):
        """Zero iterations returns the axiom unchanged."""
        result = expand_lsystem("F", {"F": "FF"}, 0)
        assert result == "F"

    def test_unknown_chars_pass_through(self):
        """Characters without rules pass through unchanged."""
        result = expand_lsystem("AXF", {"F": "FF"}, 1)
        assert result == "AXFF"

    def test_all_grammars_expand(self):
        """All built-in grammars expand without error."""
        for name, grammar in LSYSTEM_GRAMMARS.items():
            result = expand_lsystem(
                grammar["axiom"], grammar["rules"],
                grammar["default_iterations"],
            )
            assert len(result) > 0, f"Grammar '{name}' produced empty string"
            assert "F" in result, f"Grammar '{name}' has no F segments"

    def test_exponential_growth(self):
        """F->FF should double length each iteration."""
        for i in range(1, 6):
            result = expand_lsystem("F", {"F": "FF"}, i)
            assert len(result) == 2 ** i


# ===================================================================
# L-system interpretation (turtle graphics)
# ===================================================================


class TestInterpretLsystem:
    """Test turtle interpretation of L-system strings."""

    def test_single_f_produces_one_segment(self):
        """Single 'F' produces one branch segment."""
        segments = interpret_lsystem("F", seed=42)
        assert len(segments) == 1
        seg = segments[0]
        assert seg.start == (0.0, 0.0, 0.0)
        assert abs(seg.end[2] - 1.0) < 0.5  # Should extend upward

    def test_ff_produces_two_segments(self):
        """'FF' produces two connected segments."""
        segments = interpret_lsystem("FF", seed=42)
        assert len(segments) == 2
        # End of first should be start of second
        assert segments[0].end == segments[1].start

    def test_branch_increases_depth(self):
        """'F[+F]' produces segments where the branched one has depth 1."""
        segments = interpret_lsystem("F[+F]", seed=42)
        assert len(segments) == 2
        assert segments[0].depth == 0  # Trunk
        assert segments[1].depth == 1  # Branch

    def test_branch_reduces_radius(self):
        """Branching reduces the radius by branch_ratio."""
        segments = interpret_lsystem("F[+F]", branch_ratio=0.5,
                                      trunk_radius=1.0, seed=42)
        assert segments[1].start_radius < segments[0].start_radius

    def test_tips_are_marked(self):
        """Branch endpoints are marked as tips."""
        segments = interpret_lsystem("F[+F][-F]", seed=42)
        tips = [s for s in segments if s.is_tip]
        assert len(tips) >= 2  # At least the two branch ends

    def test_gravity_pulls_down(self):
        """With high gravity, direction vector tilts downward over iterations."""
        # Compare average tip Z with gravity=0 vs gravity=0.9
        lstring = expand_lsystem("F", LSYSTEM_GRAMMARS["willow"]["rules"], 4)
        segs_no_grav = interpret_lsystem(lstring, gravity=0.0, seed=42,
                                          branch_angle=35.0)
        segs_gravity = interpret_lsystem(lstring, gravity=0.9, seed=42,
                                          branch_angle=35.0)

        tips_no = [s for s in segs_no_grav if s.is_tip]
        tips_gv = [s for s in segs_gravity if s.is_tip]

        if tips_no and tips_gv:
            avg_z_no = sum(t.end[2] for t in tips_no) / len(tips_no)
            avg_z_gv = sum(t.end[2] for t in tips_gv) / len(tips_gv)
            # With gravity, average tip height should be lower
            assert avg_z_gv < avg_z_no

    def test_randomness_affects_output(self):
        """Different seeds produce different branch geometry."""
        lstring = "F[+F][-F]F[+F]"
        s1 = interpret_lsystem(lstring, seed=42)
        s2 = interpret_lsystem(lstring, seed=99)
        # At least one segment end should differ
        ends1 = [s.end for s in s1]
        ends2 = [s.end for s in s2]
        assert ends1 != ends2

    def test_parent_indices_valid(self):
        """Parent indices form a valid tree structure."""
        lstring = expand_lsystem("F", LSYSTEM_GRAMMARS["oak"]["rules"], 3)
        segments = interpret_lsystem(lstring, seed=42)
        for i, seg in enumerate(segments):
            assert seg.parent_index < i or seg.parent_index == -1


# ===================================================================
# Branch-to-mesh conversion
# ===================================================================


class TestBranchesToMesh:
    """Test conversion of branch segments to mesh geometry."""

    def _simple_segments(self) -> list[BranchSegment]:
        """Create a simple two-segment tree."""
        return [
            BranchSegment(
                start=(0, 0, 0), end=(0, 0, 2),
                start_radius=0.3, end_radius=0.25,
                depth=0, is_tip=False, parent_index=-1,
            ),
            BranchSegment(
                start=(0, 0, 2), end=(1, 0, 3),
                start_radius=0.2, end_radius=0.1,
                depth=1, is_tip=True, parent_index=0,
            ),
        ]

    def test_produces_vertices_and_faces(self):
        """Mesh has non-empty vertices and faces."""
        mesh = branches_to_mesh(self._simple_segments())
        assert len(mesh["vertices"]) > 0
        assert len(mesh["faces"]) > 0

    def test_face_indices_valid(self):
        """All face vertex indices are within bounds."""
        mesh = branches_to_mesh(self._simple_segments())
        num_verts = len(mesh["vertices"])
        for face in mesh["faces"]:
            for idx in face:
                assert 0 <= idx < num_verts

    def test_vertex_count_matches(self):
        """vertex_count metadata matches actual vertex list length."""
        mesh = branches_to_mesh(self._simple_segments())
        assert mesh["vertex_count"] == len(mesh["vertices"])

    def test_tips_identified(self):
        """Tip positions are extracted from tip segments."""
        mesh = branches_to_mesh(self._simple_segments())
        assert len(mesh["tip_positions"]) > 0

    def test_branch_depths_per_vertex(self):
        """Branch depth is recorded for each vertex."""
        mesh = branches_to_mesh(self._simple_segments())
        assert len(mesh["branch_depths"]) == len(mesh["vertices"])

    def test_ring_segments_affect_vertex_count(self):
        """More ring segments produce more vertices per branch."""
        segs = self._simple_segments()
        m6 = branches_to_mesh(segs, ring_segments=6)
        m12 = branches_to_mesh(segs, ring_segments=12)
        assert m12["vertex_count"] > m6["vertex_count"]


# ===================================================================
# Root generation
# ===================================================================


class TestGenerateRoots:
    """Test visible root segment generation."""

    def test_produces_requested_count(self):
        """Generates the requested number of root segments."""
        roots = generate_roots((0, 0, 0), 0.5, num_roots=5, seed=42)
        assert len(roots) == 5

    def test_roots_start_near_trunk(self):
        """Root starts are near the trunk base."""
        roots = generate_roots((0, 0, 0), 0.5, num_roots=4, seed=42)
        for root in roots:
            dist = math.sqrt(root.start[0] ** 2 + root.start[1] ** 2)
            assert dist < 1.0  # Within reasonable trunk distance

    def test_roots_extend_outward(self):
        """Root ends are further from center than starts."""
        roots = generate_roots((0, 0, 0), 0.5, num_roots=4, seed=42)
        for root in roots:
            start_dist = math.sqrt(root.start[0] ** 2 + root.start[1] ** 2)
            end_dist = math.sqrt(root.end[0] ** 2 + root.end[1] ** 2)
            assert end_dist > start_dist

    def test_roots_angle_downward(self):
        """Root ends are at or below the base Z level."""
        roots = generate_roots((0, 0, 0), 0.5, num_roots=4, seed=42)
        for root in roots:
            assert root.end[2] <= root.start[2]

    def test_roots_taper(self):
        """Root end radius is smaller than start radius."""
        roots = generate_roots((0, 0, 0), 0.5, num_roots=4, seed=42)
        for root in roots:
            assert root.end_radius < root.start_radius


# ===================================================================
# Full tree generation
# ===================================================================


class TestGenerateLsystemTree:
    """Test the full L-system tree generation pipeline."""

    def test_all_tree_types_produce_mesh(self):
        """All built-in tree types generate valid meshes."""
        for tree_type in LSYSTEM_GRAMMARS:
            result = generate_lsystem_tree({
                "tree_type": tree_type,
                "iterations": 3,  # Low for speed
                "seed": 42,
            })
            assert result["vertex_count"] > 0
            assert result["face_count"] > 0
            assert result["tree_type"] == tree_type

    def test_invalid_tree_type_raises(self):
        """Invalid tree type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tree_type"):
            generate_lsystem_tree({"tree_type": "banana_palm"})

    def test_iterations_capped_at_8(self):
        """Iterations are capped at 8 to prevent excessive geometry."""
        result = generate_lsystem_tree({
            "tree_type": "oak",
            "iterations": 20,
            "seed": 42,
        })
        assert result["metadata"]["iterations"] == 8

    def test_seed_determinism(self):
        """Same seed produces identical tree."""
        r1 = generate_lsystem_tree({"tree_type": "pine", "seed": 42, "iterations": 3})
        r2 = generate_lsystem_tree({"tree_type": "pine", "seed": 42, "iterations": 3})
        assert r1["vertices"] == r2["vertices"]
        assert r1["faces"] == r2["faces"]

    def test_different_seeds_differ(self):
        """Different seeds produce different trees."""
        r1 = generate_lsystem_tree({"tree_type": "oak", "seed": 42, "iterations": 3})
        r2 = generate_lsystem_tree({"tree_type": "oak", "seed": 99, "iterations": 3})
        assert r1["vertices"] != r2["vertices"]

    def test_dead_tree_has_no_leaf_density(self):
        """Dead tree type has leaf_density=0."""
        result = generate_lsystem_tree({"tree_type": "dead", "iterations": 3})
        assert result["leaf_density"] == 0.0

    def test_roots_generated_by_default(self):
        """Roots are generated by default."""
        result = generate_lsystem_tree({"tree_type": "oak", "iterations": 3})
        assert result["metadata"]["root_segments"] > 0

    def test_roots_can_be_disabled(self):
        """Roots can be disabled."""
        result = generate_lsystem_tree({
            "tree_type": "oak", "iterations": 3,
            "generate_roots": False,
        })
        assert result["metadata"]["root_segments"] == 0

    def test_metadata_present(self):
        """Result includes metadata about the generation."""
        result = generate_lsystem_tree({"tree_type": "birch", "iterations": 3})
        meta = result["metadata"]
        assert "grammar" in meta
        assert "iterations" in meta
        assert "lstring_length" in meta
        assert "total_segments" in meta

    def test_tree_has_height(self):
        """Generated tree has non-trivial vertical extent."""
        result = generate_lsystem_tree({
            "tree_type": "pine", "iterations": 4, "seed": 42,
        })
        z_values = [v[2] for v in result["vertices"]]
        height = max(z_values) - min(z_values)
        assert height > 1.0  # At least 1 unit tall

    def test_tree_faces_are_quads(self):
        """All faces are quads (4 vertices each)."""
        result = generate_lsystem_tree({
            "tree_type": "oak", "iterations": 3, "seed": 42,
        })
        for face in result["faces"]:
            assert len(face) == 4


# ===================================================================
# Leaf card generation
# ===================================================================


class TestGenerateLeafCards:
    """Test leaf card quad generation at branch tips."""

    def _make_tips(self, count: int = 5) -> list[dict]:
        """Create simple branch tip data."""
        tips = []
        for i in range(count):
            angle = 2.0 * math.pi * i / count
            tips.append({
                "position": [math.cos(angle) * 2, math.sin(angle) * 2, 5.0 + i],
                "direction": [0, 0, 1],
                "radius": 0.1,
            })
        return tips

    def test_produces_quads(self):
        """Each leaf card is a quad (4 vertices)."""
        result = generate_leaf_cards(self._make_tips(), "broadleaf", density=1.0)
        assert result["vertex_count"] > 0
        for face in result["faces"]:
            assert len(face) == 4

    def test_vertex_count_is_4x_face_count(self):
        """Each face has 4 unique vertices."""
        result = generate_leaf_cards(self._make_tips(), "broadleaf", density=1.0)
        assert result["vertex_count"] == result["face_count"] * 4

    def test_density_affects_count(self):
        """Lower density produces fewer leaf cards."""
        r_full = generate_leaf_cards(self._make_tips(10), "broadleaf",
                                      density=1.0, seed=42)
        r_sparse = generate_leaf_cards(self._make_tips(10), "broadleaf",
                                        density=0.2, seed=42)
        assert r_sparse["cards_generated"] <= r_full["cards_generated"]

    def test_zero_density_produces_no_cards(self):
        """Zero density produces no leaf cards."""
        result = generate_leaf_cards(self._make_tips(), "broadleaf", density=0.0)
        assert result["cards_generated"] == 0

    def test_all_leaf_types(self):
        """All leaf types generate valid output."""
        for leaf_type in ["broadleaf", "needle", "palm", "fern", "vine"]:
            result = generate_leaf_cards(
                self._make_tips(), leaf_type, density=1.0, seed=42,
            )
            assert result["leaf_type"] == leaf_type

    def test_invalid_leaf_type_raises(self):
        """Invalid leaf type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown leaf_type"):
            generate_leaf_cards([], "cactus_spine")

    def test_empty_tips_produces_no_cards(self):
        """Empty tip list produces no cards."""
        result = generate_leaf_cards([], "broadleaf", density=1.0)
        assert result["cards_generated"] == 0

    def test_needle_type_more_cards_per_tip(self):
        """Needle leaf type generates more cards per tip than broadleaf."""
        tips = self._make_tips(3)
        r_broad = generate_leaf_cards(tips, "broadleaf", density=1.0, seed=42)
        r_needle = generate_leaf_cards(tips, "needle", density=1.0, seed=42)
        # Needle has 6 cards_per_tip vs broadleaf's 3
        assert r_needle["cards_generated"] >= r_broad["cards_generated"]


# ===================================================================
# Wind vertex color baking
# ===================================================================


class TestBakeWindVertexColors:
    """Test wind animation weight vertex color computation."""

    def _make_tree_mesh(self) -> dict:
        """Create a simple tree mesh spec for testing."""
        # Trunk vertices at bottom, branch vertices at top
        vertices = [
            (0.0, 0.0, 0.0),   # Trunk base
            (0.1, 0.0, 0.0),
            (-0.1, 0.0, 0.0),
            (0.0, 0.0, 2.0),   # Trunk top
            (0.05, 0.0, 2.0),
            (-0.05, 0.0, 2.0),
            (1.0, 0.0, 3.0),   # Branch tip
            (0.9, 0.0, 3.0),
            (-1.0, 0.0, 3.5),  # Another tip
            (-0.9, 0.0, 3.5),
        ]
        branch_depths = [0, 0, 0, 0, 0, 0, 2, 2, 2, 2]
        return {
            "vertices": vertices,
            "branch_depths": branch_depths,
            "faces": [],
        }

    def test_colors_have_correct_count(self):
        """One color per vertex."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        assert len(result["wind_colors"]) == len(mesh["vertices"])

    def test_color_channels_in_0_1(self):
        """All RGB channels are clamped to [0, 1]."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        for r, g, b in result["wind_colors"]:
            assert 0.0 <= r <= 1.0, f"R out of range: {r}"
            assert 0.0 <= g <= 1.0, f"G out of range: {g}"
            assert 0.0 <= b <= 1.0, f"B out of range: {b}"

    def test_trunk_base_low_sway(self):
        """Trunk base vertices have low primary sway (R channel)."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        # First 3 vertices are trunk base
        for i in range(3):
            r, g, b = result["wind_colors"][i]
            assert r < 0.5  # Low sway at base

    def test_branch_tips_high_sway(self):
        """Branch tip vertices have high primary sway (R channel)."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        # Last 4 vertices are branch tips
        tip_r_values = [result["wind_colors"][i][0] for i in range(6, 10)]
        avg_r = sum(tip_r_values) / len(tip_r_values)
        assert avg_r > 0.3  # Higher sway at tips

    def test_secondary_sway_matches_depth(self):
        """G channel (secondary sway) correlates with branch depth."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        # Trunk depth=0 should have low G, branch depth=2 should have high G
        trunk_g = result["wind_colors"][0][1]
        branch_g = result["wind_colors"][6][1]
        assert branch_g > trunk_g

    def test_phase_offset_varies(self):
        """B channel (phase offset) varies across vertices."""
        mesh = self._make_tree_mesh()
        result = bake_wind_vertex_colors(mesh)
        b_values = [c[2] for c in result["wind_colors"]]
        # Not all the same (deterministic hash should produce variation)
        assert len(set(round(b, 4) for b in b_values)) > 1

    def test_empty_mesh_returns_empty(self):
        """Empty mesh returns empty wind colors."""
        mesh = {"vertices": [], "branch_depths": [], "faces": []}
        result = bake_wind_vertex_colors(mesh)
        assert result["wind_colors"] == []


# ===================================================================
# Billboard impostor generation
# ===================================================================


class TestGenerateBillboardImpostor:
    """Test billboard impostor mesh generation."""

    def test_cross_billboard_has_8_verts(self):
        """Cross billboard has 2 quads = 8 vertices."""
        result = generate_billboard_impostor({
            "impostor_type": "cross",
            "height": 5.0,
            "width": 3.0,
        })
        assert result["vertex_count"] == 8
        assert result["face_count"] == 2

    def test_octahedral_impostor(self):
        """Octahedral impostor has correct face count."""
        result = generate_billboard_impostor({
            "impostor_type": "octahedral",
            "num_views": 8,
        })
        assert result["face_count"] == 8
        assert result["vertex_count"] == 32  # 8 quads * 4 verts

    def test_has_uvs(self):
        """Impostor includes UV coordinates."""
        result = generate_billboard_impostor({"impostor_type": "cross"})
        assert len(result["uvs"]) == result["vertex_count"]

    def test_has_next_steps(self):
        """Result includes next_steps for rendering."""
        result = generate_billboard_impostor({"impostor_type": "cross"})
        assert len(result["next_steps"]) > 0

    def test_invalid_impostor_type_raises(self):
        """Invalid impostor type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown impostor_type"):
            generate_billboard_impostor({"impostor_type": "hexagonal"})

    def test_12_view_octahedral(self):
        """12-view octahedral impostor has 12 faces."""
        result = generate_billboard_impostor({
            "impostor_type": "octahedral",
            "num_views": 12,
        })
        assert result["face_count"] == 12


# ===================================================================
# GPU instancing export
# ===================================================================


class TestPrepareGpuInstancingExport:
    """Test GPU instancing data preparation."""

    def _make_instances(self, count: int = 100) -> list[dict]:
        """Create test vegetation instances."""
        instances = []
        for i in range(count):
            instances.append({
                "mesh_name": f"tree_{i % 3}",
                "position": [i * 2.0, i * 1.5, 0.0],
                "rotation": [0, 0, i * 30.0],
                "scale": 1.0 + (i % 5) * 0.1,
                "lod_level": i % 3,
            })
        return instances

    def test_groups_by_mesh_name(self):
        """Instances are grouped by mesh name."""
        result = prepare_gpu_instancing_export({
            "instances": self._make_instances(),
        })
        assert result["mesh_group_count"] == 3  # tree_0, tree_1, tree_2

    def test_computes_bounds(self):
        """Bounding box is computed from positions."""
        result = prepare_gpu_instancing_export({
            "instances": self._make_instances(10),
        })
        bounds = result["bounds"]
        assert bounds["min"][0] == 0.0
        assert bounds["max"][0] > 0.0

    def test_lod_distribution(self):
        """LOD distribution is tallied correctly."""
        result = prepare_gpu_instancing_export({
            "instances": self._make_instances(9),
        })
        lod = result["lod_distribution"]
        assert 0 in lod
        assert 1 in lod
        assert 2 in lod

    def test_empty_instances(self):
        """Empty instance list returns empty status."""
        result = prepare_gpu_instancing_export({"instances": []})
        assert result["status"] == "empty"
        assert result["instance_count"] == 0

    def test_scalar_scale_expanded(self):
        """Scalar scale values are expanded to [x, y, z]."""
        result = prepare_gpu_instancing_export({
            "instances": [{
                "mesh_name": "t",
                "position": [0, 0, 0],
                "scale": 2.5,
            }],
        })
        export_data = result["export_data"]
        inst = export_data["mesh_groups"]["t"]["instances"][0]
        assert inst["scale"] == [2.5, 2.5, 2.5]

    def test_instance_count_matches(self):
        """Total instance count matches input."""
        instances = self._make_instances(50)
        result = prepare_gpu_instancing_export({"instances": instances})
        assert result["instance_count"] == 50


# ===================================================================
# Integration: full pipeline from generation to wind colors
# ===================================================================


class TestFullPipeline:
    """Test the complete tree generation -> leaf cards -> wind colors pipeline."""

    def test_oak_tree_full_pipeline(self):
        """Generate oak tree, add leaves, bake wind colors."""
        # Step 1: Generate tree
        tree = generate_lsystem_tree({
            "tree_type": "oak",
            "iterations": 3,
            "seed": 42,
        })
        assert tree["vertex_count"] > 0

        # Step 2: Generate leaf cards from tips
        tips = [
            {"position": p, "direction": d, "radius": r}
            for p, d, r in zip(
                tree["tip_positions"],
                tree["tip_directions"],
                tree["tip_radii"],
            )
        ]
        leaves = generate_leaf_cards(
            tips, leaf_type="broadleaf", density=0.8, seed=42,
        )
        assert leaves["cards_generated"] >= 0

        # Step 3: Bake wind colors
        tree_with_wind = bake_wind_vertex_colors(tree)
        assert len(tree_with_wind["wind_colors"]) == tree["vertex_count"]

        # All colors in range
        for r, g, b in tree_with_wind["wind_colors"]:
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0

    def test_dead_tree_no_leaves(self):
        """Dead tree type should have leaf_density=0, no leaves generated."""
        tree = generate_lsystem_tree({
            "tree_type": "dead",
            "iterations": 3,
            "seed": 42,
        })
        assert tree["leaf_density"] == 0.0

        tips = [
            {"position": p, "direction": d, "radius": r}
            for p, d, r in zip(
                tree["tip_positions"],
                tree["tip_directions"],
                tree["tip_radii"],
            )
        ]
        leaves = generate_leaf_cards(tips, density=0.0, seed=42)
        assert leaves["cards_generated"] == 0


# ===================================================================
# L-system scatter integration (VEGETATION_GENERATOR_MAP wiring)
# ===================================================================


class TestLsystemScatterIntegration:
    """Test that VEGETATION_GENERATOR_MAP uses L-system trees, not sphere clusters."""

    def test_vegetation_map_tree_calls_lsystem(self):
        """VEGETATION_GENERATOR_MAP['tree'] entry uses _lsystem_tree_generator."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        gen_func, gen_kwargs = VEGETATION_GENERATOR_MAP["tree"]
        # The function name should indicate L-system, not generate_tree_mesh
        assert "lsystem" in gen_func.__name__.lower(), (
            f"Expected L-system generator, got {gen_func.__name__}"
        )

    def test_all_tree_types_mapped_to_lsystem(self):
        """All 7 tree type entries map to L-system grammars."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        tree_keys = [
            "tree", "tree_healthy", "tree_boundary", "tree_blighted",
            "tree_dead", "tree_twisted", "pine_tree",
        ]
        for key in tree_keys:
            gen_func, gen_kwargs = VEGETATION_GENERATOR_MAP[key]
            assert "lsystem" in gen_func.__name__.lower(), (
                f"'{key}' uses {gen_func.__name__}, expected L-system generator"
            )

    def test_lsystem_tree_produces_rich_mesh(self):
        """Calling the generator for 'tree_healthy' produces mesh with > 100 vertices."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        gen_func, gen_kwargs = VEGETATION_GENERATOR_MAP["tree_healthy"]
        spec = gen_func(**gen_kwargs, seed=42)
        assert len(spec["vertices"]) > 100, (
            f"Expected > 100 vertices, got {len(spec['vertices'])} "
            "(may still be using sphere cluster generator)"
        )

    def test_lsystem_tree_has_branch_metadata(self):
        """L-system tree output contains generator='lsystem_tree' metadata."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        gen_func, gen_kwargs = VEGETATION_GENERATOR_MAP["tree"]
        spec = gen_func(**gen_kwargs, seed=42)
        assert spec["metadata"]["generator"] == "lsystem_tree", (
            "Expected metadata.generator='lsystem_tree'"
        )

    def test_lsystem_leaf_cards_attached(self):
        """L-system tree with leaf_type='broadleaf' has more vertices than without."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        gen_func_healthy, kwargs_healthy = VEGETATION_GENERATOR_MAP["tree_healthy"]
        gen_func_dead, kwargs_dead = VEGETATION_GENERATOR_MAP["tree_dead"]

        spec_with_leaves = gen_func_healthy(**kwargs_healthy, seed=42)
        spec_no_leaves = gen_func_dead(**kwargs_dead, seed=42)

        # Healthy tree has leaf cards, dead does not (leaf_type=None)
        assert len(spec_with_leaves["vertices"]) > len(spec_no_leaves["vertices"]), (
            "Tree with leaves should have more vertices than dead tree"
        )

    def test_iterations_capped_at_4_for_scatter(self):
        """VEGETATION_GENERATOR_MAP tree entries have iterations <= 4."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        tree_keys = [
            "tree", "tree_healthy", "tree_boundary", "tree_blighted",
            "tree_dead", "tree_twisted", "pine_tree",
        ]
        for key in tree_keys:
            _, gen_kwargs = VEGETATION_GENERATOR_MAP[key]
            iters = gen_kwargs.get("iterations", 99)
            assert iters <= 4, (
                f"'{key}' has iterations={iters}, expected <= 4 for scatter"
            )

    def test_dead_tree_has_no_leaf_type(self):
        """tree_dead entry has leaf_type=None (dead trees have no leaves)."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        _, gen_kwargs = VEGETATION_GENERATOR_MAP["tree_dead"]
        assert gen_kwargs.get("leaf_type") is None, (
            f"Dead tree should have leaf_type=None, got {gen_kwargs.get('leaf_type')}"
        )

    def test_each_tree_type_returns_valid_meshspec(self):
        """Every tree entry returns dict with vertices and faces keys."""
        from blender_addon.handlers._mesh_bridge import VEGETATION_GENERATOR_MAP
        tree_keys = [
            "tree", "tree_healthy", "tree_boundary", "tree_blighted",
            "tree_dead", "tree_twisted", "pine_tree",
        ]
        for key in tree_keys:
            gen_func, gen_kwargs = VEGETATION_GENERATOR_MAP[key]
            spec = gen_func(**gen_kwargs, seed=42)
            assert "vertices" in spec, f"'{key}' missing 'vertices'"
            assert "faces" in spec, f"'{key}' missing 'faces'"
            assert len(spec["vertices"]) > 0, f"'{key}' has empty vertices"
            assert len(spec["faces"]) > 0, f"'{key}' has empty faces"

    def test_prop_map_tree_entries_use_lsystem(self):
        """PROP_GENERATOR_MAP dead_tree and tree_twisted also use L-system."""
        from blender_addon.handlers._mesh_bridge import PROP_GENERATOR_MAP
        for key in ["dead_tree", "tree_twisted"]:
            gen_func, _ = PROP_GENERATOR_MAP[key]
            assert "lsystem" in gen_func.__name__.lower(), (
                f"PROP_GENERATOR_MAP['{key}'] uses {gen_func.__name__}, "
                "expected L-system generator"
            )
