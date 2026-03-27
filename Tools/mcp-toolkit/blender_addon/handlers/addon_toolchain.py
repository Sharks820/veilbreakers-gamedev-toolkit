"""External Blender addon capability detection and pipeline selection.

Pure-logic helpers are kept separate from Blender-specific inspection so the
selection logic is testable without bpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import bpy
    import addon_utils
except ImportError:  # pragma: no cover - unit tests use pure helpers only
    bpy = None  # type: ignore[assignment]
    addon_utils = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ExternalAddonSpec:
    name: str
    modules: tuple[str, ...]
    category: str
    role: str
    stability: str
    install_hint: str = ""


EXTERNAL_ADDON_SPECS: tuple[ExternalAddonSpec, ...] = (
    ExternalAddonSpec(
        name="bonsai",
        modules=("bonsai", "bl_ext.blender_org.bonsai"),
        category="interiors",
        role="Free BIM/room/wall/door/window/storey authoring",
        stability="medium",
        install_hint="Install Bonsai / BlenderBIM tooling.",
    ),
    ExternalAddonSpec(
        name="archimesh",
        modules=("archimesh", "add_mesh_archimesh", "bl_ext.blender_org.archimesh"),
        category="architecture",
        role="Bundled room, wall, door, window, stair, and cabinet tools",
        stability="safe",
        install_hint="Enable Archimesh from Blender add-ons.",
    ),
    ExternalAddonSpec(
        name="wfc_3d_generator",
        modules=("wfc_3d_generator", "wfc3d_generator", "bl_ext.blender_org.wfc_3d_generator"),
        category="layout_variation",
        role="Constraint-based non-repeating spatial/layout generation",
        stability="medium",
        install_hint="Install WFC 3D Generator from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="hifi_builder",
        modules=("hifi_builder", "hifi_architecture_builder"),
        category="architecture",
        role="Free modular architecture shell generation",
        stability="safe",
        install_hint="Install HiFi Architecture Builder from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="secret_paint",
        modules=("secret_paint", "bl_ext.blender_org.secret_paint"),
        category="scatter",
        role="Procedural painting/scatter for environment dressing",
        stability="medium",
        install_hint="Install Secret Paint from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="bagapie",
        modules=("bagapie", "Bagapie", "bl_ext.blender_org.Bagapie"),
        category="scatter",
        role="Free environment scatter and geometry helper toolkit",
        stability="medium",
        install_hint="Install BagaPie from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="ucupaint",
        modules=("ucupaint", "bl_ext.blender_org.ucupaint"),
        category="surface_detail",
        role="Free layered material and baking workflow",
        stability="safe",
        install_hint="Install Ucupaint from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="rmkit",
        modules=("rmKit", "rmkit", "bl_ext.blender_org.rmKit"),
        category="modeling_helpers",
        role="Free modeling helper toolkit",
        stability="safe",
        install_hint="Install rmKit from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="rmkit_uv",
        modules=("rmKitUV", "rmkit_uv", "rmKit_uv", "bl_ext.blender_org.rmKit_uv"),
        category="uv",
        role="Free UV workflow helper toolkit",
        stability="safe",
        install_hint="Install rmKitUV from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="edgeflow",
        modules=("EdgeFlow", "edgeflow", "bl_ext.blender_org.EdgeFlow"),
        category="modeling_helpers",
        role="Free topology smoothing and edge flow helpers",
        stability="safe",
        install_hint="Install EdgeFlow from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="univ",
        modules=("UniV", "univ", "bl_ext.blender_org.univ"),
        category="uv",
        role="Free advanced UV workflow toolkit",
        stability="safe",
        install_hint="Install UniV from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="mio3_uv",
        modules=("mio3_uv", "mio3uv", "bl_ext.blender_org.mio3_uv"),
        category="uv",
        role="Free UV editing toolkit",
        stability="safe",
        install_hint="Install Mio3 UV from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="textools",
        modules=("TexTools-Blender", "textools"),
        category="uv",
        role="Free UV, texel density, and baking utility toolkit",
        stability="medium",
        install_hint="Install TexTools addon package.",
    ),
    ExternalAddonSpec(
        name="sverchok",
        modules=("sverchok",),
        category="layout_variation",
        role="Advanced parametric and node-based geometry modeling toolkit",
        stability="medium",
        install_hint="Install Sverchok addon package.",
    ),
    ExternalAddonSpec(
        name="blenderkit",
        modules=("BlenderKit", "blenderkit"),
        category="asset_management",
        role="Online asset and material library for Blender",
        stability="medium",
        install_hint="Install BlenderKit addon package and sign in if needed.",
    ),
    ExternalAddonSpec(
        name="botaniq",
        modules=("botaniq", "engon"),
        category="foliage",
        role="High-quality tree, shrub, and plant assets",
        stability="safe",
        install_hint="Install botaniq and engon through polygoniq asset packs.",
    ),
    ExternalAddonSpec(
        name="engon",
        modules=("engon",),
        category="asset_management",
        role="polygoniq asset/browser workflow",
        stability="safe",
        install_hint="Install with botaniq or other polygoniq packs.",
    ),
    ExternalAddonSpec(
        name="geo_scatter",
        modules=("GeoScatter", "geoscatter", "GScatter", "gscatter"),
        category="scatter",
        role="Biome-aware high-quality scatter and ecosystem placement",
        stability="safe",
        install_hint="Install Geo-Scatter/GScatter addon package.",
    ),
    ExternalAddonSpec(
        name="decalmachine",
        modules=("DECALmachine",),
        category="surface_detail",
        role="Decals, trims, and surface breakup",
        stability="safe",
        install_hint="Install DECALmachine addon package.",
    ),
    ExternalAddonSpec(
        name="uvpackmaster",
        modules=("UVPackmaster3", "UVPackmaster2", "uvpackmaster3"),
        category="uv",
        role="Accelerated UV packing",
        stability="safe",
        install_hint="Install UVPackmaster addon package.",
    ),
    ExternalAddonSpec(
        name="lodgen",
        modules=("lod_gen", "lodgen", "LODGen", "bl_ext.blender_org.lod_gen"),
        category="lod",
        role="Quick Blender-side LOD generation",
        stability="safe",
        install_hint="Install Blender LOD Gen extension.",
    ),
    ExternalAddonSpec(
        name="archipack",
        modules=("archipack", "archipack_pro"),
        category="architecture",
        role="Parametric walls, doors, windows, roofs, and interiors",
        stability="medium",
        install_hint="Install Archipack addon package.",
    ),
    ExternalAddonSpec(
        name="world_creator",
        modules=("world_creator", "worldcreator", "wc_bridge"),
        category="terrain",
        role="External terrain authoring and Blender sync",
        stability="medium",
        install_hint="Install the World Creator Blender Bridge.",
    ),
    ExternalAddonSpec(
        name="terrain_mixer",
        modules=("bl_ext.blender_org.terrainmixer", "terrainmixer"),
        category="terrain",
        role="Blender-side terrain/biome authoring fallback",
        stability="safe",
        install_hint="Install Terrain Mixer from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="ant_landscape",
        modules=("antlandscape", "bl_ext.blender_org.antlandscape"),
        category="terrain",
        role="Procedural terrain and displacement blockout generator",
        stability="safe",
        install_hint="Install A.N.T. Landscape from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="srtm_terrain_importer",
        modules=("srtm_terrain_importer", "bl_ext.blender_org.srtm_terrain_importer"),
        category="terrain",
        role="Real-world terrain import from SRTM elevation data",
        stability="medium",
        install_hint="Install SRTM Terrain Importer from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="bool_tool",
        modules=("bool_tool", "bl_ext.blender_org.bool_tool"),
        category="modeling_helpers",
        role="Fast boolean authoring for hard-surface and architecture work",
        stability="safe",
        install_hint="Install Bool Tool from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="looptools",
        modules=("looptools", "bl_ext.blender_org.looptools"),
        category="modeling_helpers",
        role="Mesh cleanup and loop/surface editing helpers",
        stability="safe",
        install_hint="Install LoopTools from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="modifier_list",
        modules=("Modifier_List_Fork", "modifier_list_fork", "bl_ext.blender_org.Modifier_List_Fork"),
        category="modeling_helpers",
        role="Modifier stack management and edit-mesh modifier support",
        stability="safe",
        install_hint="Install Modifier List from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="nd_primitives",
        modules=("Non_Destructive_Primitives", "non_destructive_primitives", "bl_ext.blender_org.Non_Destructive_Primitives"),
        category="modeling_helpers",
        role="Non-destructive parametric primitive modeling",
        stability="safe",
        install_hint="Install ND Primitives from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="easymesh_batch_exporter",
        modules=("easymesh_batch_exporter", "bl_ext.blender_org.easymesh_batch_exporter"),
        category="export",
        role="Batch Unity-friendly export packaging for meshes and LODs",
        stability="medium",
        install_hint="Install EasyMesh Batch Exporter from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="gamiflow",
        modules=("gamiflow", "bl_ext.blender_org.gamiflow"),
        category="export",
        role="Game-ready unwrap, bake, anchor, and export workflow",
        stability="medium",
        install_hint="Install GamiFlow from Blender Extensions.",
    ),
    ExternalAddonSpec(
        name="texel_density_checker",
        modules=("texel_density_checker", "bl_ext.blender_org.texel_density_checker"),
        category="qa",
        role="Texel density measurement and consistency checks",
        stability="safe",
        install_hint="Install Texel Density Checker from Blender Extensions.",
    ),
)


def compute_addon_inventory(
    *,
    installed_modules: set[str],
    enabled_modules: set[str],
) -> dict[str, dict[str, Any]]:
    """Compute addon availability from installed/enabled module names."""
    inventory: dict[str, dict[str, Any]] = {}
    lowered_installed = {m.lower() for m in installed_modules}
    lowered_enabled = {m.lower() for m in enabled_modules}

    for spec in EXTERNAL_ADDON_SPECS:
        module_candidates = tuple(spec.modules)
        installed = any(mod.lower() in lowered_installed for mod in module_candidates)
        enabled = any(mod.lower() in lowered_enabled for mod in module_candidates)
        inventory[spec.name] = {
            "category": spec.category,
            "role": spec.role,
            "stability": spec.stability,
            "installed": installed,
            "enabled": enabled,
            "modules": list(module_candidates),
            "install_hint": spec.install_hint,
        }
    return inventory


def compute_pipeline_selection(
    inventory: dict[str, dict[str, Any]],
    *,
    prefer_external: bool = True,
    review_lighting: bool = True,
) -> dict[str, Any]:
    """Select the active worldbuilding stack from detected addon inventory."""
    def _available(name: str) -> bool:
        entry = inventory.get(name, {})
        return bool(entry.get("installed"))

    if prefer_external and _available("world_creator"):
        terrain = "world_creator"
    elif _available("terrain_mixer"):
        terrain = "terrain_mixer"
    else:
        terrain = "native_terrain"

    terrain_helpers = [
        name for name in ("ant_landscape", "srtm_terrain_importer")
        if _available(name)
    ]

    if prefer_external and _available("geo_scatter"):
        scatter = "geo_scatter"
    elif _available("bagapie"):
        scatter = "bagapie"
    elif _available("secret_paint"):
        scatter = "secret_paint"
    else:
        scatter = "native_scatter"

    if prefer_external and _available("botaniq"):
        vegetation_assets = "botaniq"
    else:
        vegetation_assets = "procedural_vegetation"

    if prefer_external and _available("archipack"):
        architecture = "archipack"
    elif _available("hifi_builder"):
        architecture = "hifi_builder"
    elif _available("archimesh"):
        architecture = "archimesh"
    else:
        architecture = "native_architecture"

    if prefer_external and _available("decalmachine"):
        surface_detail = "decalmachine"
    elif _available("ucupaint"):
        surface_detail = "ucupaint"
    else:
        surface_detail = "native_surface_detail"

    if prefer_external and _available("uvpackmaster"):
        uv = "uvpackmaster"
    elif _available("univ"):
        uv = "univ"
    elif _available("mio3_uv"):
        uv = "mio3_uv"
    elif _available("rmkit_uv"):
        uv = "rmkit_uv"
    else:
        uv = "native_uv"

    if prefer_external and _available("lodgen"):
        lod = "lodgen"
    else:
        lod = "native_lod"

    if _available("bonsai"):
        interior_authoring = "bonsai"
    elif architecture in {"archipack", "hifi_builder", "archimesh"}:
        interior_authoring = architecture
    else:
        interior_authoring = "native_interiors"

    if _available("wfc_3d_generator"):
        layout_variation = "wfc_3d_generator"
    else:
        layout_variation = "native_layout_variation"

    layout_helpers = [
        name for name in ("sverchok",)
        if _available(name)
    ]

    modeling_helpers = [
        name for name in (
            "rmkit",
            "edgeflow",
            "modifier_list",
            "nd_primitives",
            "bool_tool",
            "looptools",
            "sverchok",
        )
        if _available(name)
    ]

    scatter_helpers = [
        name for name in ("bagapie", "secret_paint")
        if _available(name)
    ]

    if _available("gamiflow"):
        export_packaging = "gamiflow"
    elif _available("easymesh_batch_exporter"):
        export_packaging = "easymesh_batch_exporter"
    else:
        export_packaging = "native_export_packaging"

    quality_helpers = [
        name for name in ("texel_density_checker", "textools")
        if _available(name)
    ]

    asset_sources = [
        name for name in ("blenderkit",)
        if _available(name)
    ]

    return {
        "terrain": terrain,
        "terrain_helpers": terrain_helpers,
        "scatter": scatter,
        "scatter_helpers": scatter_helpers,
        "vegetation_assets": vegetation_assets,
        "architecture": architecture,
        "interior_authoring": interior_authoring,
        "layout_variation": layout_variation,
        "layout_helpers": layout_helpers,
        "surface_detail": surface_detail,
        "uv": uv,
        "lod": lod,
        "export_packaging": export_packaging,
        "quality_helpers": quality_helpers,
        "modeling_helpers": modeling_helpers,
        "asset_sources": asset_sources,
        "lighting_preset": "forest_review" if review_lighting else "forest_transition",
    }


def build_agent_tool_contract(
    inventory: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    """Build a compact agent-facing contract for using the active toolchain."""
    def _enabled(name: str) -> bool:
        return bool(inventory.get(name, {}).get("enabled") or inventory.get(name, {}).get("installed"))

    automation_targets = {
        "terrain_authoring": selection.get("terrain", "native_terrain"),
        "terrain_helpers": list(selection.get("terrain_helpers", [])),
        "layout_variation": selection.get("layout_variation", "native_layout_variation"),
        "layout_helpers": list(selection.get("layout_helpers", [])),
        "architecture": selection.get("architecture", "native_architecture"),
        "interiors": selection.get("interior_authoring", "native_interiors"),
        "scatter": selection.get("scatter", "native_scatter"),
        "scatter_helpers": list(selection.get("scatter_helpers", [])),
        "surface_detail": selection.get("surface_detail", "native_surface_detail"),
        "uv": selection.get("uv", "native_uv"),
        "lod": selection.get("lod", "native_lod"),
        "export_packaging": selection.get("export_packaging", "native_export_packaging"),
        "quality_helpers": list(selection.get("quality_helpers", [])),
        "asset_sources": list(selection.get("asset_sources", [])),
    }

    authoring_rules = [
        "Use Blender/DCC for final meshes, UVs, materials, and export prep.",
        "Use Unity for assembly, splines, terrain validation, gameplay spacing, and runtime checks.",
        "Prefer WFC/Bonsai/Archimesh for non-repeating layouts and interior structure before falling back to procedural VB primitives.",
        "Use export packaging and texel-density helpers before considering an asset game-ready.",
    ]

    entrypoints = {
        "inspect_toolchain": "asset_pipeline action=inspect_external_toolchain",
        "configure_toolchain": "asset_pipeline action=configure_external_toolchain",
        "terrain": "asset_pipeline action=compose_map",
        "interiors": "asset_pipeline action=compose_interior",
        "architecture": "worldbuilding handlers + selected architecture addon path",
        "quality_gate": "viewport beauty checks + export/UV/LOD validation",
    }

    warnings: list[str] = []
    if _enabled("sverchok"):
        warnings.append(
            "Sverchok is installed, but Blender 5.0 background registration showed an operator registration issue. Treat it as experimental on this build."
        )
    if _enabled("blenderkit"):
        warnings.append(
            "BlenderKit is enabled, but it still requires account authentication before agents can rely on its online asset search."
        )

    return {
        "automation_targets": automation_targets,
        "authoring_rules": authoring_rules,
        "entrypoints": entrypoints,
        "warnings": warnings,
    }


def normalize_toolchain_preferences(params: dict[str, Any]) -> dict[str, Any]:
    """Normalize user/toolchain preferences into a small stable contract."""
    return {
        "prefer_external": bool(params.get("prefer_external", True)),
        "review_lighting": bool(params.get("review_lighting", True)),
        "project_label": str(params.get("project_label", "VeilBreakers")).strip() or "VeilBreakers",
    }


def _blender_module_sets() -> tuple[set[str], set[str]]:
    """Return installed and enabled addon module names from Blender."""
    installed: set[str] = set()
    enabled: set[str] = set()

    if addon_utils is not None:
        for module in addon_utils.modules():
            mod_name = str(getattr(module, "__name__", "")).strip()
            if mod_name:
                installed.add(mod_name)

    if bpy is not None:
        prefs = getattr(getattr(bpy.context, "preferences", None), "addons", {})
        for mod_name in prefs.keys():
            enabled.add(str(mod_name))

    return installed, enabled


def handle_inspect_external_toolchain(params: dict[str, Any]) -> dict[str, Any]:
    """Inspect which recommended external addons are available in Blender."""
    if bpy is None:
        return {"status": "error", "error": "bpy unavailable"}

    prefs = normalize_toolchain_preferences(params)
    installed, enabled = _blender_module_sets()
    inventory = compute_addon_inventory(
        installed_modules=installed,
        enabled_modules=enabled,
    )
    selection = compute_pipeline_selection(
        inventory,
        prefer_external=prefs["prefer_external"],
        review_lighting=prefs["review_lighting"],
    )
    agent_contract = build_agent_tool_contract(inventory, selection)
    return {
        "status": "success",
        "result": {
            "project_label": prefs["project_label"],
            "available_addons": inventory,
            "selected_pipeline": selection,
            "agent_contract": agent_contract,
        },
    }


def handle_configure_external_toolchain(params: dict[str, Any]) -> dict[str, Any]:
    """Persist addon-toolchain preferences on the current Blender scene."""
    if bpy is None:
        return {"status": "error", "error": "bpy unavailable"}

    prefs = normalize_toolchain_preferences(params)
    installed, enabled = _blender_module_sets()
    inventory = compute_addon_inventory(
        installed_modules=installed,
        enabled_modules=enabled,
    )
    selection = compute_pipeline_selection(
        inventory,
        prefer_external=prefs["prefer_external"],
        review_lighting=prefs["review_lighting"],
    )
    agent_contract = build_agent_tool_contract(inventory, selection)

    scene = bpy.context.scene
    scene["vb_external_toolchain"] = {
        "preferences": prefs,
        "inventory": inventory,
        "selection": selection,
        "agent_contract": agent_contract,
    }

    missing = [
        name for name, entry in inventory.items()
        if not entry["installed"] and name in {
            "botaniq", "geo_scatter", "decalmachine",
            "uvpackmaster", "lodgen", "archipack", "world_creator",
            "bonsai", "archimesh", "wfc_3d_generator", "hifi_builder",
            "secret_paint", "bagapie", "ucupaint", "rmkit", "rmkit_uv",
            "edgeflow", "univ", "mio3_uv", "terrain_mixer", "ant_landscape",
            "srtm_terrain_importer", "bool_tool", "looptools",
            "modifier_list", "nd_primitives", "easymesh_batch_exporter",
            "gamiflow", "texel_density_checker", "textools",
            "sverchok", "blenderkit",
        }
    ]

    return {
        "status": "success",
        "result": {
            "selection": selection,
            "agent_contract": agent_contract,
            "missing_recommended_addons": missing,
            "scene_key": "vb_external_toolchain",
        },
    }
