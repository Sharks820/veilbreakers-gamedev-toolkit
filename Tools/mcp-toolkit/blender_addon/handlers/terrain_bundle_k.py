"""Bundle K — central registrar.

Imports every Bundle K sub-module and calls each sub-registrar, landing
all material-ceiling passes on the ``TerrainPassController`` in one call.

Bundle K passes:
    stochastic_shader
    macro_color
    multiscale_breakup
    shadow_clipmap
    roughness_driver
    quixel_ingest

Not auto-registered — import this module and call
``register_bundle_k_passes()`` explicitly (follows Bundle A/J pattern).
"""

from __future__ import annotations

from . import (
    terrain_macro_color,
    terrain_multiscale_breakup,
    terrain_quixel_ingest,
    terrain_roughness_driver,
    terrain_shadow_clipmap_bake,
    terrain_stochastic_shader,
)


BUNDLE_K_PASSES = (
    "stochastic_shader",
    "macro_color",
    "multiscale_breakup",
    "shadow_clipmap",
    "roughness_driver",
    "quixel_ingest",
)


def register_bundle_k_passes() -> None:
    """Register all Bundle K passes on the TerrainPassController."""
    terrain_stochastic_shader.register_bundle_k_stochastic_shader_pass()
    terrain_macro_color.register_bundle_k_macro_color_pass()
    terrain_multiscale_breakup.register_bundle_k_multiscale_breakup_pass()
    terrain_shadow_clipmap_bake.register_bundle_k_shadow_clipmap_pass()
    terrain_roughness_driver.register_bundle_k_roughness_driver_pass()
    terrain_quixel_ingest.register_bundle_k_quixel_ingest_pass()


__all__ = [
    "BUNDLE_K_PASSES",
    "register_bundle_k_passes",
]
