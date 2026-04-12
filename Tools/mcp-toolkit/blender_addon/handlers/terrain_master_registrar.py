"""Master registrar for the VeilBreakers terrain pipeline.

Single-call entrypoint that brings up every registered pass across
bundles A–O. Use this from Blender-side startup, tests, or the MCP
handler bridge to ensure the full pipeline is available.

Usage:
    from blender_addon.handlers.terrain_master_registrar import (
        register_all_terrain_passes,
    )
    register_all_terrain_passes()
    # Now TerrainPassController.PASS_REGISTRY contains every pass.

Individual bundle registrars remain callable for tests that want to
exercise a single bundle in isolation.

Bundle inventory (complete A–O):
    A — foundation (terrain_pipeline.register_default_passes)
    B — cliffs + materials (terrain_cliffs, terrain_materials_v2)
    C — waterfall hydrology (terrain_waterfalls)
    D — validation + checkpoints (terrain_validation, terrain_checkpoints)
    E — scatter intelligence (terrain_assets)
    F — cave archetypes (terrain_caves)
    G — banded noise (terrain_banded)
    H — composition & intent (terrain_saliency/morphology/framing/
                              hierarchy/rhythm/negative_space)
    I — geology plausibility (terrain_geology_validator)
    J — ecosystem spine (terrain_bundle_j)
    K — material ceiling (terrain_bundle_k)
    L — atmosphere & horizon (terrain_bundle_l)
    M — iteration velocity (extension modules, no new passes)
    N — deep validation & QA (terrain_bundle_n)
    O — water + vegetation depth (terrain_bundle_o)
"""

from __future__ import annotations

from typing import Callable, List

# ---------------------------------------------------------------------------
# Bundle registrar lookup — one import per bundle
# ---------------------------------------------------------------------------


def _safe_import_registrar(module_path: str, attr: str) -> Callable[[], None] | None:
    """Return a callable bundle registrar, or None if the module is missing.

    This lets the master registrar degrade gracefully if a bundle is being
    rebuilt in a worktree or selectively disabled — the rest still loads.
    """
    try:
        module = __import__(module_path, fromlist=[attr])
        fn = getattr(module, attr, None)
        return fn if callable(fn) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Master registrar
# ---------------------------------------------------------------------------


def register_all_terrain_passes(*, strict: bool = False) -> List[str]:
    """Invoke every bundle registrar. Returns the list of bundles loaded.

    Parameters
    ----------
    strict : bool
        If True, raise on any missing bundle registrar. If False (default),
        silently skip missing bundles so partial environments still work.
    """
    loaded: List[str] = []

    # Bundle A — foundation (always required)
    from .terrain_pipeline import register_default_passes

    register_default_passes()
    loaded.append("A")

    registrars: list[tuple[str, str, str]] = [
        ("B-cliffs", "blender_addon.handlers.terrain_cliffs", "register_bundle_b_passes"),
        ("B-materials", "blender_addon.handlers.terrain_materials_v2", "register_bundle_b_material_passes"),
        ("C", "blender_addon.handlers.terrain_waterfalls", "register_bundle_c_passes"),
        ("D", "blender_addon.handlers.terrain_validation", "register_bundle_d_passes"),
        ("E", "blender_addon.handlers.terrain_assets", "register_bundle_e_passes"),
        ("F", "blender_addon.handlers.terrain_caves", "register_bundle_f_passes"),
        ("G", "blender_addon.handlers.terrain_banded", "register_bundle_g_passes"),
        ("H-saliency", "blender_addon.handlers.terrain_saliency", "register_saliency_pass"),
        ("H-framing", "blender_addon.handlers.terrain_framing", "register_framing_pass"),
        ("H-hierarchy", "blender_addon.handlers.terrain_hierarchy", "register_bundle_h_hierarchy"),
        ("H-rhythm", "blender_addon.handlers.terrain_rhythm", "register_bundle_h_rhythm"),
        ("H-negative_space", "blender_addon.handlers.terrain_negative_space", "register_bundle_h_negative_space"),
        ("I", "blender_addon.handlers.terrain_geology_validator", "register_bundle_i_passes"),
        ("J", "blender_addon.handlers.terrain_bundle_j", "register_bundle_j_passes"),
        ("K", "blender_addon.handlers.terrain_bundle_k", "register_bundle_k_passes"),
        ("L", "blender_addon.handlers.terrain_bundle_l", "register_bundle_l_passes"),
        ("N", "blender_addon.handlers.terrain_bundle_n", "register_bundle_n_passes"),
        ("O", "blender_addon.handlers.terrain_bundle_o", "register_bundle_o_passes"),
    ]

    for label, module_path, attr in registrars:
        fn = _safe_import_registrar(module_path, attr)
        if fn is not None:
            try:
                fn()
                loaded.append(label)
            except Exception as exc:
                if strict:
                    raise
                # Soft failure — continue loading the rest
                loaded.append(f"{label}:SKIPPED({exc!r})")
        elif strict:
            raise ImportError(f"Bundle {label} registrar not found: {module_path}.{attr}")

    return loaded


__all__ = ["register_all_terrain_passes"]
