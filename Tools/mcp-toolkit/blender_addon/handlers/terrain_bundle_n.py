"""Bundle N — central registrar.

Imports every Bundle N sub-module and exposes a single
``register_bundle_n_passes`` entry point. Bundle N's modules are pure
QA / validation helpers — none of them register mutating passes on the
``TerrainPassController``, so this function validates that every module
imports cleanly and its expected callable is present.

Follows the Bundle L registrar pattern.
"""

from __future__ import annotations

import logging

from . import (
    terrain_budget_enforcer,
    terrain_determinism_ci,
    terrain_golden_snapshots,
    terrain_readability_bands,
    terrain_review_ingest,
    terrain_telemetry_dashboard,
)

logger = logging.getLogger(__name__)

BUNDLE_N_MODULES = (
    "terrain_determinism_ci",
    "terrain_readability_bands",
    "terrain_budget_enforcer",
    "terrain_golden_snapshots",
    "terrain_review_ingest",
    "terrain_telemetry_dashboard",
)

# Map module objects to the callable name they must expose.
_EXPECTED_CALLABLES: dict[str, tuple[object, str]] = {
    "terrain_determinism_ci": (terrain_determinism_ci, "run_determinism_check"),
    "terrain_readability_bands": (terrain_readability_bands, "compute_readability_bands"),
    "terrain_budget_enforcer": (terrain_budget_enforcer, "enforce_budget"),
    "terrain_golden_snapshots": (terrain_golden_snapshots, "save_golden_snapshot"),
    "terrain_review_ingest": (terrain_review_ingest, "ingest_review_json"),
    "terrain_telemetry_dashboard": (terrain_telemetry_dashboard, "record_telemetry"),
}


def register_bundle_n_passes() -> None:
    """Bundle N has no mutating passes — verify modules loaded and wired.

    This mirrors the Bundle L/K API surface so orchestration code can
    uniformly call ``register_bundle_X_passes()`` across the whole
    terrain pipeline. All Bundle N functionality is exposed via
    direct function imports, not pass registration.

    Validates that each module exposes its expected callable. Logs a
    warning if a callable is missing (rather than silently discarding
    the check result into ``_``).
    """
    for mod_name, (mod_obj, attr_name) in _EXPECTED_CALLABLES.items():
        fn = getattr(mod_obj, attr_name, None)
        if fn is None or not callable(fn):
            logger.warning(
                "Bundle N module %s missing expected callable '%s'",
                mod_name,
                attr_name,
            )


__all__ = [
    "BUNDLE_N_MODULES",
    "register_bundle_n_passes",
]
