"""Bundle J — central registrar.

Imports every Bundle J sub-module and calls each sub-registrar, landing
all ecosystem spine passes on the ``TerrainPassController`` in one call.

Bundle J passes (in canonical execution order):
    audio_zones
    wildlife_zones
    gameplay_zones
    wind_field
    cloud_shadow
    decals
    navmesh
    ecotones

Not auto-registered — import this module and call
``register_bundle_j_passes()`` explicitly (follows the Bundle A pattern).
"""

from __future__ import annotations

from . import (
    terrain_audio_zones,
    terrain_cloud_shadow,
    terrain_decal_placement,
    terrain_ecotone_graph,
    terrain_gameplay_zones,
    terrain_navmesh_export,
    terrain_wildlife_zones,
    terrain_wind_field,
)


BUNDLE_J_PASSES = (
    "audio_zones",
    "wildlife_zones",
    "gameplay_zones",
    "wind_field",
    "cloud_shadow",
    "decals",
    "navmesh",
    "ecotones",
)


def register_bundle_j_passes() -> None:
    """Register all eight Bundle J passes on the TerrainPassController."""
    terrain_audio_zones.register_bundle_j_audio_zones_pass()
    terrain_wildlife_zones.register_bundle_j_wildlife_zones_pass()
    terrain_gameplay_zones.register_bundle_j_gameplay_zones_pass()
    terrain_wind_field.register_bundle_j_wind_field_pass()
    terrain_cloud_shadow.register_bundle_j_cloud_shadow_pass()
    terrain_decal_placement.register_bundle_j_decals_pass()
    terrain_navmesh_export.register_bundle_j_navmesh_pass()
    terrain_ecotone_graph.register_bundle_j_ecotones_pass()


__all__ = [
    "BUNDLE_J_PASSES",
    "register_bundle_j_passes",
]
