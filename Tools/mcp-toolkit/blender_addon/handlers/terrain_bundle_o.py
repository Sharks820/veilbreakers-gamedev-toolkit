"""Bundle O — central registrar.

Imports the two Bundle O modules (water variants + vegetation depth)
and exposes a single ``register_bundle_o_passes`` entry point following
the Bundle K / L / N registrar pattern.
"""

from __future__ import annotations

from . import terrain_vegetation_depth, terrain_water_variants


BUNDLE_O_MODULES = (
    "terrain_water_variants",
    "terrain_vegetation_depth",
)


def register_bundle_o_passes() -> None:
    """Register the Bundle O passes on the controller.

    Registers:
        - ``water_variants`` (produces water_surface, wetness)
        - ``vegetation_depth`` (populates stack.detail_density dict)
    """
    terrain_water_variants.register_water_variants_pass()
    terrain_vegetation_depth.register_vegetation_depth_pass()


__all__ = [
    "BUNDLE_O_MODULES",
    "register_bundle_o_passes",
]
