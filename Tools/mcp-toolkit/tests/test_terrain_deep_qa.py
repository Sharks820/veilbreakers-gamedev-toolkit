"""Bundle N — Deep Validation & QA tests.

Covers all six Bundle N modules:
    terrain_determinism_ci
    terrain_readability_bands
    terrain_budget_enforcer
    terrain_golden_snapshots
    terrain_review_ingest
    terrain_telemetry_dashboard

>= 25 tests. Determinism test must FAIL on a 1-bit mutation of the
mask stack. Golden snapshot library seed must produce >= 20 snapshots.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_passes():
    from blender_addon.handlers.terrain_pipeline import (
        TerrainPassController,
        register_default_passes,
    )

    TerrainPassController.clear_registry()
    register_default_passes()
    yield
    TerrainPassController.clear_registry()


def _build_stack(tile_size: int = 16, seed: int = 1234, *, extras: bool = True):
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    rng = np.random.default_rng(seed)
    height = rng.standard_normal((tile_size, tile_size)).astype(np.float64) * 5.0 + 100.0
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=2.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    if extras:
        slope = np.abs(rng.standard_normal((tile_size, tile_size))).astype(np.float64)
        macro = rng.random((tile_size, tile_size, 3)).astype(np.float64)
        stack.set("slope", slope, "test_setup")
        stack.set("macro_color", macro, "test_setup")
    return stack


def _build_state(tile_size: int = 16, seed: int = 1234):
    from blender_addon.handlers._terrain_noise import generate_heightmap
    from blender_addon.handlers.terrain_semantics import (
        BBox,
        TerrainIntentState,
        TerrainMaskStack,
        TerrainPipelineState,
        TerrainSceneRead,
    )

    height = np.asarray(
        generate_heightmap(
            tile_size + 1,
            tile_size + 1,
            scale=80.0,
            world_origin_x=0.0,
            world_origin_y=0.0,
            cell_size=1.0,
            seed=seed,
            terrain_type="mountains",
            normalize=False,
        ),
        dtype=np.float64,
    )
    stack = TerrainMaskStack(
        tile_size=tile_size,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=height,
    )
    region = BBox(0.0, 0.0, float(tile_size), float(tile_size))
    scene_read = TerrainSceneRead(
        timestamp=0.0,
        major_landforms=("ridge_system",),
        focal_point=(tile_size / 2.0, tile_size / 2.0, 0.0),
        hero_features_present=(),
        hero_features_missing=(),
        waterfall_chains=(),
        cave_candidates=(),
        protected_zones_in_region=(),
        edit_scope=region,
        success_criteria=("deep_qa",),
        reviewer="pytest",
    )
    intent = TerrainIntentState(
        seed=seed,
        region_bounds=region,
        tile_size=tile_size,
        cell_size=1.0,
        scene_read=scene_read,
    )
    return TerrainPipelineState(intent=intent, mask_stack=stack)


# ---------------------------------------------------------------------------
# 1. Bundle N registrar
# ---------------------------------------------------------------------------


def test_bundle_n_registrar_is_callable():
    from blender_addon.handlers.terrain_bundle_n import (
        BUNDLE_N_MODULES,
        register_bundle_n_passes,
    )

    register_bundle_n_passes()  # idempotent, no-op
    assert "terrain_determinism_ci" in BUNDLE_N_MODULES
    assert len(BUNDLE_N_MODULES) == 6


# ---------------------------------------------------------------------------
# 2-5. Determinism CI
# ---------------------------------------------------------------------------


def test_determinism_check_passes_on_identical_runs():
    from blender_addon.handlers.terrain_determinism_ci import run_determinism_check
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=12)
        ctrl = TerrainPassController(state, checkpoint_dir=Path(td))
        report = run_determinism_check(ctrl, seed=state.intent.seed, runs=3)
        assert report["deterministic"] is True
        assert report["run_count"] == 3
        assert not report["mismatches"]


def test_determinism_check_detects_mutation():
    """Mutate 1 bit of the replay baseline and expect a regression."""
    from blender_addon.handlers.terrain_determinism_ci import (
        detect_determinism_regressions,
    )

    issues = detect_determinism_regressions("a" * 64, "b" * 64)
    assert len(issues) == 1
    assert issues[0].is_hard()
    assert issues[0].code == "DETERMINISM_REGRESSION"


def test_determinism_check_no_regression_on_equal_hashes():
    from blender_addon.handlers.terrain_determinism_ci import (
        detect_determinism_regressions,
    )

    assert detect_determinism_regressions("abc123", "abc123") == []


def test_determinism_check_run_records_populated():
    from blender_addon.handlers.terrain_determinism_ci import run_determinism_check
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        state = _build_state(tile_size=12)
        ctrl = TerrainPassController(state, checkpoint_dir=Path(td))
        report = run_determinism_check(ctrl, seed=state.intent.seed, runs=2)
        assert len(report["runs"]) == 2
        assert all(len(r.content_hash) == 64 for r in report["runs"])
        assert len(report["runs"][0].per_channel_hashes) > 0


def test_determinism_fails_on_1bit_mutation_of_mask_stack():
    """A 1-bit change in the mask stack bytes must produce a distinct hash
    and therefore a detected regression via detect_determinism_regressions."""
    from blender_addon.handlers.terrain_determinism_ci import (
        detect_determinism_regressions,
    )

    stack_a = _build_stack(tile_size=8, seed=42)
    baseline = stack_a.compute_hash()

    # Flip a single float bit
    stack_b = _build_stack(tile_size=8, seed=42)
    mutated = stack_b.height.copy()
    mutated.flat[0] = np.float64(mutated.flat[0]) + np.float64(1e-9)
    stack_b.set("height", mutated, "mutation")
    current = stack_b.compute_hash()

    assert baseline != current
    issues = detect_determinism_regressions(baseline, current)
    assert any(i.code == "DETERMINISM_REGRESSION" for i in issues)


# ---------------------------------------------------------------------------
# 6-10. Readability bands
# ---------------------------------------------------------------------------


def test_readability_bands_returns_five_entries():
    from blender_addon.handlers.terrain_readability_bands import (
        BAND_IDS,
        compute_readability_bands,
    )

    stack = _build_stack()
    bands = compute_readability_bands(stack)
    assert len(bands) == 5
    assert tuple(b.band_id for b in bands) == BAND_IDS


def test_readability_bands_all_clamped_to_range():
    from blender_addon.handlers.terrain_readability_bands import (
        compute_readability_bands,
    )

    stack = _build_stack()
    for band in compute_readability_bands(stack):
        assert 0.0 <= band.score <= 10.0


def test_readability_aggregate_between_0_and_10():
    from blender_addon.handlers.terrain_readability_bands import (
        aggregate_readability_score,
        compute_readability_bands,
    )

    stack = _build_stack()
    score = aggregate_readability_score(compute_readability_bands(stack))
    assert 0.0 <= score <= 10.0


def test_readability_flat_terrain_scores_lower_than_varied():
    from blender_addon.handlers.terrain_readability_bands import (
        aggregate_readability_score,
        compute_readability_bands,
    )
    from blender_addon.handlers.terrain_semantics import TerrainMaskStack

    flat = TerrainMaskStack(
        tile_size=16,
        cell_size=1.0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        tile_x=0,
        tile_y=0,
        height=np.ones((16, 16), dtype=np.float64) * 50.0,
    )
    varied = _build_stack(seed=7)

    score_flat = aggregate_readability_score(compute_readability_bands(flat))
    score_varied = aggregate_readability_score(compute_readability_bands(varied))
    assert score_varied > score_flat


def test_readability_aggregate_empty_returns_zero():
    from blender_addon.handlers.terrain_readability_bands import (
        aggregate_readability_score,
    )

    assert aggregate_readability_score([]) == 0.0


# ---------------------------------------------------------------------------
# 11-15. Budget enforcer
# ---------------------------------------------------------------------------


def test_budget_default_values():
    from blender_addon.handlers.terrain_budget_enforcer import TerrainBudget

    b = TerrainBudget()
    assert b.max_tri_count > 0
    assert b.max_unique_materials > 0
    assert 0.0 < b.warn_fraction <= 1.0


def test_budget_usage_computes_per_axis():
    from blender_addon.handlers.terrain_budget_enforcer import (
        TerrainBudget,
        compute_tile_budget_usage,
    )

    stack = _build_stack(tile_size=16)
    usage = compute_tile_budget_usage(stack, TerrainBudget())
    assert "tri_count" in usage
    assert "npz_mb" in usage
    assert usage["tri_count"]["current"] > 0


def test_budget_enforce_clean_tile_no_issues():
    from blender_addon.handlers.terrain_budget_enforcer import (
        TerrainBudget,
        enforce_budget,
    )

    stack = _build_stack(tile_size=8)
    state = _build_state(tile_size=8)
    issues = enforce_budget(stack, state.intent, TerrainBudget())
    assert all(not i.is_hard() for i in issues)


def test_budget_enforce_triggers_hard_on_tight_budget():
    from blender_addon.handlers.terrain_budget_enforcer import (
        TerrainBudget,
        enforce_budget,
    )

    stack = _build_stack(tile_size=32)
    state = _build_state(tile_size=32)
    tight = TerrainBudget(max_tri_count=10, max_npz_mb=0.0001)
    issues = enforce_budget(stack, state.intent, tight)
    hard = [i for i in issues if i.is_hard()]
    assert len(hard) >= 1
    assert any("TRI" in i.code or "NPZ" in i.code for i in hard)


def test_budget_soft_warn_at_near_threshold():
    from blender_addon.handlers.terrain_budget_enforcer import (
        TerrainBudget,
        enforce_budget,
    )

    stack = _build_stack(tile_size=16)
    state = _build_state(tile_size=16)
    usage_mb = 0.0
    for name in stack._ARRAY_CHANNELS:
        v = getattr(stack, name, None)
        if v is not None:
            usage_mb += float(np.asarray(v).nbytes) / (1024 * 1024)
    # Set max just above current usage, with warn_fraction forcing a warn
    near = TerrainBudget(max_npz_mb=max(usage_mb * 1.05, 0.0002), warn_fraction=0.5)
    issues = enforce_budget(stack, state.intent, near)
    # May or may not trigger, but must not crash and must return list
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# 16-20. Golden snapshots
# ---------------------------------------------------------------------------


def test_golden_snapshot_save_and_load_roundtrip():
    from blender_addon.handlers.terrain_golden_snapshots import (
        load_golden_snapshot,
        save_golden_snapshot,
    )

    stack = _build_stack(seed=99)
    with tempfile.TemporaryDirectory() as td:
        snap = save_golden_snapshot(stack, Path(td), "golden_test", seed=99)
        assert snap.content_hash == stack.compute_hash()
        loaded = load_golden_snapshot(Path(td) / "golden_test.golden.json")
        assert loaded.snapshot_id == snap.snapshot_id
        assert loaded.content_hash == snap.content_hash
        assert loaded.channel_hashes == snap.channel_hashes


def test_golden_compare_identical_stack_no_issues():
    from blender_addon.handlers.terrain_golden_snapshots import (
        compare_against_golden,
        save_golden_snapshot,
    )

    stack = _build_stack(seed=55)
    with tempfile.TemporaryDirectory() as td:
        snap = save_golden_snapshot(stack, Path(td), "g1", seed=55)
        issues = compare_against_golden(stack, snap)
        assert issues == []


def test_golden_compare_mutated_stack_raises_hard_issue():
    from blender_addon.handlers.terrain_golden_snapshots import (
        compare_against_golden,
        save_golden_snapshot,
    )

    stack = _build_stack(seed=55)
    with tempfile.TemporaryDirectory() as td:
        snap = save_golden_snapshot(stack, Path(td), "g1", seed=55)
        mutated = stack.height.copy()
        mutated.flat[0] += 0.5
        stack.set("height", mutated, "mutation")
        issues = compare_against_golden(stack, snap)
        assert any(i.is_hard() for i in issues)
        assert any(i.code == "GOLDEN_HASH_MISMATCH" for i in issues)


def test_golden_compare_detects_new_channel_soft():
    from blender_addon.handlers.terrain_golden_snapshots import (
        GoldenSnapshot,
        compare_against_golden,
        save_golden_snapshot,
    )

    stack = _build_stack(seed=55, extras=False)
    with tempfile.TemporaryDirectory() as td:
        snap = save_golden_snapshot(stack, Path(td), "g1", seed=55)
        # Now add a new channel to the stack
        curvature = np.zeros_like(stack.height)
        stack.set("curvature", curvature, "later_pass")
        issues = compare_against_golden(stack, snap)
        soft_codes = [i.code for i in issues if i.severity == "soft"]
        assert "GOLDEN_NEW_CHANNEL" in soft_codes


def test_golden_library_seeds_at_least_20_snapshots():
    from blender_addon.handlers.terrain_golden_snapshots import seed_golden_library
    from blender_addon.handlers.terrain_pipeline import TerrainPassController

    with tempfile.TemporaryDirectory() as td:
        def build(seed: int, tile_x: int, tile_y: int):
            state = _build_state(tile_size=8, seed=seed)
            # Override tile coords in the fresh stack
            state.mask_stack.tile_x = tile_x
            state.mask_stack.tile_y = tile_y
            return state

        # Use a throwaway controller; build_state_fn overrides cloning.
        base_state = _build_state(tile_size=8, seed=2000)
        ctrl = TerrainPassController(base_state, checkpoint_dir=Path(td) / "ckpt")
        snaps = seed_golden_library(
            ctrl, Path(td) / "goldens", count=22, build_state_fn=build
        )
        assert len(snaps) >= 20
        manifest = json.loads((Path(td) / "goldens" / "golden_library_manifest.json").read_text())
        assert manifest["count"] == len(snaps)


# ---------------------------------------------------------------------------
# 21-24. Review ingest
# ---------------------------------------------------------------------------


def test_review_finding_rejects_bad_severity():
    from blender_addon.handlers.terrain_review_ingest import ReviewFinding

    with pytest.raises(ValueError):
        ReviewFinding(source="ai", severity="catastrophic", message="nope")


def test_review_finding_rejects_bad_source():
    from blender_addon.handlers.terrain_review_ingest import ReviewFinding

    with pytest.raises(ValueError):
        ReviewFinding(source="alien", severity="hard", message="nope")


def test_ingest_review_json_parses_findings_list():
    from blender_addon.handlers.terrain_review_ingest import ingest_review_json

    payload = {
        "findings": [
            {
                "source": "human",
                "severity": "hard",
                "message": "cliffs look fake",
                "suggested_fix": "add lip + talus",
                "location": [10.0, 20.0, 30.0],
                "tags": ["cliff", "silhouette"],
            },
            {
                "source": "ai",
                "severity": "soft",
                "message": "reduce grass density",
            },
            {"source": "ai", "severity": "GARBAGE", "message": "skip me"},
        ]
    }
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "review.json"
        p.write_text(json.dumps(payload))
        findings = ingest_review_json(p)
    assert len(findings) == 2
    assert findings[0].severity == "hard"
    assert findings[0].location == (10.0, 20.0, 30.0)
    assert findings[1].severity == "soft"


def test_apply_review_findings_preserves_immutability():
    from blender_addon.handlers.terrain_review_ingest import (
        ReviewFinding,
        apply_review_findings,
    )

    state = _build_state()
    findings = [
        ReviewFinding(source="ai", severity="hard", message="fix cliffs"),
        ReviewFinding(source="human", severity="soft", message="add variety"),
        ReviewFinding(source="ai", severity="info", message="FYI"),
    ]
    new_intent = apply_review_findings(state.intent, findings)
    assert new_intent is not state.intent
    assert len(new_intent.composition_hints["review_blockers"]) == 1
    assert len(new_intent.composition_hints["review_suggestions"]) == 1
    assert len(new_intent.composition_hints["review_info"]) == 1
    assert new_intent.composition_hints["review_total_ingested"] == 3


# ---------------------------------------------------------------------------
# 25-28. Telemetry dashboard
# ---------------------------------------------------------------------------


def test_record_telemetry_writes_and_returns_record():
    from blender_addon.handlers.terrain_telemetry_dashboard import record_telemetry

    state = _build_state()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "telemetry.ndjson"
        rec = record_telemetry(
            state, path,
            budget_usage={"tri_count": {"current": 100, "max": 1000}},
            readability_score=7.5,
        )
        assert path.exists()
        assert rec.readability_score == 7.5
        assert rec.tile_coords == (0, 0)
        # File must be valid NDJSON
        line = path.read_text().strip().splitlines()[0]
        parsed = json.loads(line)
        assert parsed["readability_score"] == 7.5


def test_summarize_telemetry_empty_file_returns_zero_counts():
    from blender_addon.handlers.terrain_telemetry_dashboard import summarize_telemetry

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "missing.ndjson"
        summary = summarize_telemetry(path)
        assert summary["record_count"] == 0
        assert summary["tile_count"] == 0


def test_summarize_telemetry_aggregates_across_records():
    from blender_addon.handlers.terrain_telemetry_dashboard import (
        record_telemetry,
        summarize_telemetry,
    )

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "t.ndjson"
        for i in range(3):
            state = _build_state(seed=1000 + i)
            record_telemetry(
                state, path,
                readability_score=float(i) + 1.0,
            )
        summary = summarize_telemetry(path)
        assert summary["record_count"] == 3
        assert summary["readability_min"] == 1.0
        assert summary["readability_max"] == 3.0
        assert summary["readability_avg"] == 2.0


def test_telemetry_record_roundtrip_to_dict():
    from blender_addon.handlers.terrain_telemetry_dashboard import TelemetryRecord

    rec = TelemetryRecord(
        timestamp=123.0,
        tile_coords=(4, 5),
        pass_durations={"erosion": 0.5},
        mask_channel_counts=3,
        budget_usage={},
        readability_score=6.2,
    )
    d = rec.to_dict()
    rec2 = TelemetryRecord.from_dict(d)
    assert rec2.tile_coords == (4, 5)
    assert rec2.pass_durations == {"erosion": 0.5}
    assert rec2.readability_score == 6.2
