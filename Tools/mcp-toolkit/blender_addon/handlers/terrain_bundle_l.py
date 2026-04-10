"""Bundle L — central registrar.

Imports every Bundle L sub-module and registers its pass with
``TerrainPassController``. Follows the Bundle A / J pattern: not
auto-registered on import — callers must call
``register_bundle_l_passes()`` explicitly.

Bundle L passes (canonical execution order):
    horizon_lod
    fog_masks
    god_ray_hints
"""

from __future__ import annotations

from . import (
    terrain_fog_masks,
    terrain_god_ray_hints,
    terrain_horizon_lod,
)


BUNDLE_L_PASSES = (
    "horizon_lod",
    "fog_masks",
    "god_ray_hints",
)


def register_bundle_l_passes() -> None:
    """Register all three Bundle L passes on the TerrainPassController."""
    terrain_horizon_lod.register_bundle_l_horizon_lod_pass()
    terrain_fog_masks.register_bundle_l_fog_masks_pass()
    terrain_god_ray_hints.register_bundle_l_god_ray_hints_pass()


__all__ = [
    "BUNDLE_L_PASSES",
    "register_bundle_l_passes",
]
