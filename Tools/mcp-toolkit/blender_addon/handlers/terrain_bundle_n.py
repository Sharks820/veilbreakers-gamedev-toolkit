"""Bundle N — central registrar.

Imports every Bundle N sub-module and exposes a single
``register_bundle_n_passes`` entry point. Bundle N's modules are pure
QA / validation helpers — none of them register mutating passes on the
``TerrainPassController``, so this function is mostly a no-op that
simply validates that every module imports cleanly.

Follows the Bundle L registrar pattern.
"""

from __future__ import annotations

from . import (
    terrain_budget_enforcer,
    terrain_determinism_ci,
    terrain_golden_snapshots,
    terrain_readability_bands,
    terrain_review_ingest,
    terrain_telemetry_dashboard,
)


BUNDLE_N_MODULES = (
    "terrain_determinism_ci",
    "terrain_readability_bands",
    "terrain_budget_enforcer",
    "terrain_golden_snapshots",
    "terrain_review_ingest",
    "terrain_telemetry_dashboard",
)


def register_bundle_n_passes() -> None:
    """Bundle N has no mutating passes — just verify modules loaded.

    This mirrors the Bundle L/K API surface so orchestration code can
    uniformly call ``register_bundle_X_passes()`` across the whole
    terrain pipeline. All Bundle N functionality is exposed via
    direct function imports, not pass registration.
    """
    _ = terrain_determinism_ci.run_determinism_check
    _ = terrain_readability_bands.compute_readability_bands
    _ = terrain_budget_enforcer.enforce_budget
    _ = terrain_golden_snapshots.save_golden_snapshot
    _ = terrain_review_ingest.ingest_review_json
    _ = terrain_telemetry_dashboard.record_telemetry


__all__ = [
    "BUNDLE_N_MODULES",
    "register_bundle_n_passes",
]
