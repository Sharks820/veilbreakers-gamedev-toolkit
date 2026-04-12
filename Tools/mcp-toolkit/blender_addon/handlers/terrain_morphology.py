"""Morphology template library for Bundle H composition.

Defines authoring templates for common landforms (ridges, canyons, mesas,
pinnacles, spurs, valleys). Each template produces a deterministic height
delta when applied at a world position.

Pure numpy. No bpy. Z-up world meters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np

from .terrain_semantics import TerrainMaskStack


# ---------------------------------------------------------------------------
# Template dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MorphologyTemplate:
    template_id: str
    kind: str  # ridge_spur, canyon, mesa, pinnacle, spur, valley, plateau, ...
    scale_m: float  # characteristic XY extent in world meters
    aspect_ratio: float  # length/width ratio (>= 1 means elongated)
    params: Dict[str, Any] = field(default_factory=dict)  # REVIEW-IGNORE PY-COR-17: frozen+mutable safe — params treated as read-only after construction


# ---------------------------------------------------------------------------
# Default template catalog (>= 30 templates)
# ---------------------------------------------------------------------------


def _ridge_params(height_m: float, jaggedness: float) -> Dict[str, Any]:
    return {"height_m": height_m, "jaggedness": jaggedness, "sign": 1.0}


def _canyon_params(depth_m: float, rim_sharpness: float) -> Dict[str, Any]:
    return {"depth_m": depth_m, "rim_sharpness": rim_sharpness, "sign": -1.0}


def _mesa_params(height_m: float, flat_top: float) -> Dict[str, Any]:
    return {"height_m": height_m, "flat_top": flat_top, "sign": 1.0}


def _pinnacle_params(height_m: float, spike: float) -> Dict[str, Any]:
    return {"height_m": height_m, "spike": spike, "sign": 1.0}


def _spur_params(height_m: float, taper: float) -> Dict[str, Any]:
    return {"height_m": height_m, "taper": taper, "sign": 1.0}


def _valley_params(depth_m: float, broadness: float) -> Dict[str, Any]:
    return {"depth_m": depth_m, "broadness": broadness, "sign": -1.0}


DEFAULT_TEMPLATES: Tuple[MorphologyTemplate, ...] = (
    # --- Ridge variants (5) ---
    MorphologyTemplate("ridge_low_rolling", "ridge_spur", 80.0, 3.0, _ridge_params(12.0, 0.15)),
    MorphologyTemplate("ridge_sharp_spine", "ridge_spur", 120.0, 4.5, _ridge_params(40.0, 0.60)),
    MorphologyTemplate("ridge_broken_teeth", "ridge_spur", 150.0, 4.0, _ridge_params(55.0, 0.85)),
    MorphologyTemplate("ridge_snaking", "ridge_spur", 200.0, 6.0, _ridge_params(30.0, 0.35)),
    MorphologyTemplate("ridge_alpine_crest", "ridge_spur", 300.0, 5.0, _ridge_params(90.0, 0.50)),
    # --- Canyon variants (5) ---
    MorphologyTemplate("canyon_narrow_slot", "canyon", 30.0, 8.0, _canyon_params(45.0, 0.90)),
    MorphologyTemplate("canyon_wide_gorge", "canyon", 180.0, 3.0, _canyon_params(80.0, 0.55)),
    MorphologyTemplate("canyon_meander", "canyon", 220.0, 5.5, _canyon_params(50.0, 0.45)),
    MorphologyTemplate("canyon_box_end", "canyon", 90.0, 2.0, _canyon_params(65.0, 0.75)),
    MorphologyTemplate("canyon_branching", "canyon", 260.0, 4.0, _canyon_params(55.0, 0.60)),
    # --- Mesa / plateau variants (5) ---
    MorphologyTemplate("mesa_classic", "mesa", 150.0, 1.2, _mesa_params(60.0, 0.85)),
    MorphologyTemplate("mesa_stepped", "mesa", 180.0, 1.5, _mesa_params(70.0, 0.65)),
    MorphologyTemplate("mesa_fractured", "mesa", 200.0, 1.3, _mesa_params(55.0, 0.50)),
    MorphologyTemplate("plateau_vast", "mesa", 400.0, 1.1, _mesa_params(35.0, 0.95)),
    MorphologyTemplate("mesa_butte_small", "mesa", 60.0, 1.0, _mesa_params(45.0, 0.80)),
    # --- Pinnacle variants (5) ---
    MorphologyTemplate("pinnacle_needle", "pinnacle", 20.0, 1.0, _pinnacle_params(80.0, 0.95)),
    MorphologyTemplate("pinnacle_finger", "pinnacle", 30.0, 1.2, _pinnacle_params(55.0, 0.80)),
    MorphologyTemplate("pinnacle_stack", "pinnacle", 40.0, 1.1, _pinnacle_params(65.0, 0.70)),
    MorphologyTemplate("pinnacle_cluster", "pinnacle", 70.0, 1.3, _pinnacle_params(45.0, 0.65)),
    MorphologyTemplate("pinnacle_solitary_tower", "pinnacle", 50.0, 1.0, _pinnacle_params(95.0, 0.85)),
    # --- Spur variants (5) ---
    MorphologyTemplate("spur_long_tapered", "spur", 140.0, 5.0, _spur_params(35.0, 0.70)),
    MorphologyTemplate("spur_short_blunt", "spur", 60.0, 2.0, _spur_params(25.0, 0.30)),
    MorphologyTemplate("spur_forked", "spur", 160.0, 4.0, _spur_params(40.0, 0.55)),
    MorphologyTemplate("spur_hooked", "spur", 120.0, 3.5, _spur_params(30.0, 0.60)),
    MorphologyTemplate("spur_stepped_ridge", "spur", 180.0, 4.5, _spur_params(50.0, 0.65)),
    # --- Valley variants (5) ---
    MorphologyTemplate("valley_u_shaped", "valley", 220.0, 4.0, _valley_params(50.0, 0.80)),
    MorphologyTemplate("valley_v_shaped", "valley", 150.0, 3.5, _valley_params(60.0, 0.40)),
    MorphologyTemplate("valley_hanging", "valley", 100.0, 3.0, _valley_params(35.0, 0.55)),
    MorphologyTemplate("valley_glaciated", "valley", 350.0, 5.0, _valley_params(70.0, 0.85)),
    MorphologyTemplate("valley_headwater_bowl", "valley", 120.0, 1.5, _valley_params(40.0, 0.70)),
    # --- Volcanic variants (5) ---
    MorphologyTemplate("volcanic_caldera", "volcanic", 250.0, 1.1, {"height_m": 80.0, "rim_width": 0.3, "crater_depth": 0.6, "sign": 1.0}),
    MorphologyTemplate("volcanic_cinder_cone", "volcanic", 80.0, 1.0, {"height_m": 40.0, "rim_width": 0.15, "crater_depth": 0.3, "sign": 1.0}),
    MorphologyTemplate("volcanic_shield", "volcanic", 400.0, 1.2, {"height_m": 25.0, "rim_width": 0.05, "crater_depth": 0.1, "sign": 1.0}),
    MorphologyTemplate("volcanic_lava_dome", "volcanic", 60.0, 1.0, {"height_m": 55.0, "rim_width": 0.0, "crater_depth": 0.0, "sign": 1.0}),
    MorphologyTemplate("volcanic_maar", "volcanic", 120.0, 1.0, {"height_m": 10.0, "rim_width": 0.4, "crater_depth": 0.8, "sign": -1.0}),
    # --- Glacial variants (5) ---
    MorphologyTemplate("glacial_cirque", "glacial", 200.0, 1.3, {"depth_m": 60.0, "headwall": 0.8, "lip_height": 0.15, "sign": -1.0}),
    MorphologyTemplate("glacial_arete", "glacial", 300.0, 6.0, {"height_m": 70.0, "sharpness": 0.85, "sign": 1.0}),
    MorphologyTemplate("glacial_horn", "glacial", 100.0, 1.0, {"height_m": 120.0, "sharpness": 0.95, "sign": 1.0}),
    MorphologyTemplate("glacial_trough", "glacial", 350.0, 4.0, {"depth_m": 80.0, "headwall": 0.4, "lip_height": 0.0, "sign": -1.0}),
    MorphologyTemplate("glacial_drumlin", "glacial", 150.0, 3.0, {"height_m": 20.0, "sharpness": 0.3, "sign": 1.0}),
    # --- Karst variants (5) ---
    MorphologyTemplate("karst_sinkhole", "karst", 40.0, 1.0, {"depth_m": 25.0, "rim_sharpness": 0.7, "sign": -1.0}),
    MorphologyTemplate("karst_doline_field", "karst", 200.0, 1.5, {"depth_m": 15.0, "rim_sharpness": 0.5, "count": 5, "sign": -1.0}),
    MorphologyTemplate("karst_mogote", "karst", 60.0, 1.0, {"height_m": 50.0, "steepness": 0.8, "sign": 1.0}),
    MorphologyTemplate("karst_polje", "karst", 300.0, 2.0, {"depth_m": 20.0, "rim_sharpness": 0.3, "sign": -1.0}),
    MorphologyTemplate("karst_tower", "karst", 35.0, 1.0, {"height_m": 70.0, "steepness": 0.95, "sign": 1.0}),
)


# ---------------------------------------------------------------------------
# Template application
# ---------------------------------------------------------------------------


def _rng_from_seed(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed) & 0xFFFFFFFF)


def apply_morphology_template(
    stack: TerrainMaskStack,
    template: MorphologyTemplate,
    world_pos: Tuple[float, float, float],
    seed: int,
) -> np.ndarray:
    """Return a height delta implementing ``template`` centered at ``world_pos``.

    The delta is a deterministic function of (template, world_pos, seed).
    It does NOT mutate the stack — caller adds it in the pipeline.
    """
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)
    delta = np.zeros_like(h, dtype=np.float64)

    fx, fy, _fz = world_pos
    cf = (fx - stack.world_origin_x) / cell
    rf = (fy - stack.world_origin_y) / cell

    scale_cells = max(2.0, template.scale_m / cell)
    aspect = max(1.0, float(template.aspect_ratio))
    rng = _rng_from_seed(seed)
    theta = float(rng.uniform(0.0, 2.0 * np.pi))
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))

    rr, cc = np.mgrid[0:rows, 0:cols].astype(np.float64)
    dr = rr - rf
    dc = cc - cf
    # Rotate into template-local axes
    u = dc * cos_t + dr * sin_t  # "along" axis
    v = -dc * sin_t + dr * cos_t  # "across" axis

    along_sigma = scale_cells
    across_sigma = scale_cells / aspect

    radial = np.exp(
        -((u / along_sigma) ** 2 + (v / across_sigma) ** 2) * 0.5
    )

    kind = template.kind
    params = template.params
    sign = float(params.get("sign", 1.0))

    if kind == "ridge_spur":
        jag = float(params.get("jaggedness", 0.3))
        height_m = float(params.get("height_m", 20.0))
        # Narrow the across-axis so it reads as a ridge, add jagged noise
        shape = np.exp(-0.5 * (v / (across_sigma * 0.5)) ** 2)
        falloff = np.exp(-0.5 * (u / along_sigma) ** 2)
        noise = rng.standard_normal(h.shape) * jag
        delta = sign * height_m * shape * falloff * (1.0 + 0.2 * noise)
    elif kind == "canyon":
        depth_m = float(params.get("depth_m", 40.0))
        rim = float(params.get("rim_sharpness", 0.6))
        # Narrow slot across v, long along u
        core = np.exp(-0.5 * (v / (across_sigma * 0.4)) ** 2)
        length = np.exp(-0.5 * (u / along_sigma) ** 2)
        # Rim uplift at the edges
        rim_mask = np.exp(-0.5 * ((np.abs(v) - across_sigma * 0.5) / (across_sigma * 0.2)) ** 2)
        delta = sign * depth_m * core * length + rim * 0.25 * depth_m * rim_mask * length
    elif kind == "mesa":
        height_m = float(params.get("height_m", 50.0))
        flat = float(params.get("flat_top", 0.75))
        # Plateau: flat interior, steep edges. Use smoothstep-like profile.
        r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
        interior = np.clip(1.0 - r_norm / max(1e-6, flat), 0.0, 1.0)
        edge = np.clip(1.0 - r_norm, 0.0, 1.0)
        delta = sign * height_m * (flat * interior + (1.0 - flat) * edge)
    elif kind == "pinnacle":
        height_m = float(params.get("height_m", 60.0))
        spike = float(params.get("spike", 0.8))
        r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
        peaked = np.exp(-(r_norm ** (1.0 + spike * 2.0)))
        delta = sign * height_m * peaked
    elif kind == "spur":
        height_m = float(params.get("height_m", 30.0))
        taper = float(params.get("taper", 0.5))
        along = np.where(u >= 0, np.exp(-(u / along_sigma) ** (1.0 + taper)), np.exp(-(u / (along_sigma * 0.4)) ** 2))
        across = np.exp(-0.5 * (v / (across_sigma * 0.6)) ** 2)
        delta = sign * height_m * along * across
    elif kind == "valley":
        depth_m = float(params.get("depth_m", 40.0))
        broadness = float(params.get("broadness", 0.6))
        across = np.exp(-0.5 * (v / (across_sigma * (0.4 + broadness))) ** 2)
        along = np.exp(-0.5 * (u / along_sigma) ** 2)
        delta = sign * depth_m * across * along
    elif kind == "volcanic":
        height_m = float(params.get("height_m", 50.0))
        rim_w = float(params.get("rim_width", 0.2))
        crater_d = float(params.get("crater_depth", 0.4))
        r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
        # Conical rise with a crater rim and depression
        cone = np.clip(1.0 - r_norm, 0.0, 1.0)
        rim = np.exp(-((r_norm - rim_w) ** 2) / (0.02 + 1e-9))
        crater = np.where(r_norm < rim_w, crater_d * (1.0 - r_norm / max(rim_w, 1e-6)), 0.0)
        delta = sign * height_m * (cone + 0.3 * rim - crater)
    elif kind == "glacial":
        sharpness = float(params.get("sharpness", 0.7))
        height_m = float(params.get("height_m", 0.0))
        depth_m = float(params.get("depth_m", 0.0))
        headwall = float(params.get("headwall", 0.5))
        lip_height = float(params.get("lip_height", 0.0))
        if height_m > 0:
            # Arete / horn / drumlin: sharp ridge or rounded hump
            across = np.exp(-0.5 * (v / (across_sigma * (1.0 - sharpness * 0.7))) ** 2)
            along = np.exp(-0.5 * (u / along_sigma) ** 2)
            delta = sign * height_m * across * along
        else:
            # Cirque / trough: bowl shape with steep headwall
            r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
            bowl = np.clip(r_norm, 0.0, 1.0) ** (1.0 + headwall)
            lip = np.where(r_norm > 0.9, lip_height * depth_m * np.exp(-((r_norm - 1.0) ** 2) / 0.01), 0.0)
            delta = sign * depth_m * (1.0 - bowl) + lip
    elif kind == "karst":
        depth_m = float(params.get("depth_m", 0.0))
        height_m = float(params.get("height_m", 0.0))
        steepness = float(params.get("steepness", 0.7))
        rim_sharp = float(params.get("rim_sharpness", 0.5))
        count = int(params.get("count", 1))
        if height_m > 0:
            # Mogote / tower: steep-sided residual hill
            r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
            tower = np.clip(1.0 - r_norm, 0.0, 1.0) ** (0.5 + steepness * 2.0)
            delta = sign * height_m * tower
        elif count > 1:
            # Doline field: multiple small depressions
            delta = np.zeros_like(radial)
            for ci in range(count):
                offset_u = float(rng.uniform(-along_sigma * 0.6, along_sigma * 0.6))
                offset_v = float(rng.uniform(-across_sigma * 0.6, across_sigma * 0.6))
                r_local = np.sqrt(((u - offset_u) / (along_sigma * 0.3)) ** 2
                                  + ((v - offset_v) / (across_sigma * 0.3)) ** 2)
                hole = np.exp(-(r_local ** (1.0 + rim_sharp)))
                delta += sign * (depth_m / count) * hole
        else:
            # Single sinkhole / polje
            r_norm = np.sqrt((u / along_sigma) ** 2 + (v / across_sigma) ** 2)
            hole = np.exp(-(r_norm ** (1.0 + rim_sharp * 2.0)))
            delta = sign * depth_m * hole
    else:
        # Generic gaussian fallback
        height_m = float(params.get("height_m", 20.0))
        delta = sign * height_m * radial

    return delta


def list_templates_for_biome(biome: str) -> List[MorphologyTemplate]:
    """Return a filtered list of templates appropriate for ``biome``.

    The mapping is heuristic: each biome allows a subset of template kinds.
    Unknown biomes return all templates.
    """
    biome = (biome or "").lower()
    biome_kinds: Dict[str, Tuple[str, ...]] = {
        "alpine": ("ridge_spur", "pinnacle", "valley", "spur", "glacial"),
        "desert": ("mesa", "canyon", "pinnacle", "ridge_spur", "volcanic"),
        "forest": ("ridge_spur", "valley", "spur", "karst"),
        "plains": ("mesa", "valley", "spur"),
        "badlands": ("canyon", "mesa", "pinnacle", "spur", "volcanic"),
        "tundra": ("ridge_spur", "valley", "mesa", "glacial"),
        "coast": ("canyon", "pinnacle", "mesa", "spur", "karst"),
        "volcanic": ("volcanic", "canyon", "ridge_spur", "pinnacle"),
        "karst": ("karst", "canyon", "valley", "pinnacle"),
        "glacial": ("glacial", "ridge_spur", "valley", "pinnacle"),
    }
    allowed = biome_kinds.get(biome)
    if allowed is None:
        return list(DEFAULT_TEMPLATES)
    return [t for t in DEFAULT_TEMPLATES if t.kind in allowed]


def get_natural_arch_specs(
    stack: TerrainMaskStack,
    templates: tuple[str, ...] = (),
    *,
    max_arches: int = 3,
    seed: int = 42,
) -> list:
    """Return MeshSpec dicts for natural arch meshes at morphology sites.

    If ``templates`` includes any canyon-family template IDs, places arches
    at high-aspect-ratio canyon rims. Falls back to random ridge/pinnacle
    sites if no canyons are present.

    Calls ``generate_natural_arch`` from terrain_features.

    Returns a list of dicts with ``mesh_spec`` and ``world_pos`` keys.
    """
    from .terrain_features import generate_natural_arch

    rng = np.random.default_rng(seed)
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape

    # Prefer canyon-edge sites (high local curvature)
    # Compute simple Laplacian as a proxy for rim positions
    if rows < 3 or cols < 3:
        return []
    lap = np.abs(
        h[2:, 1:-1] + h[:-2, 1:-1] + h[1:-1, 2:] + h[1:-1, :-2] - 4.0 * h[1:-1, 1:-1]
    )
    threshold = float(np.percentile(lap, 95)) if lap.size else 0.0
    candidates = np.argwhere(lap > threshold)
    if len(candidates) == 0:
        return []

    # Offset by 1 because Laplacian excludes border
    candidates = candidates + 1

    indices = rng.choice(len(candidates), size=min(max_arches, len(candidates)), replace=False)
    results = []
    for idx in indices:
        r, c = int(candidates[idx][0]), int(candidates[idx][1])
        wx = stack.world_origin_x + c * stack.cell_size
        wy = stack.world_origin_y + r * stack.cell_size
        wz = float(h[r, c])
        spec = generate_natural_arch(
            span_width=rng.uniform(5.0, 12.0),
            arch_height=rng.uniform(4.0, 8.0),
            thickness=rng.uniform(1.5, 3.0),
            roughness=rng.uniform(0.2, 0.5),
            seed=int(rng.integers(0, 2**31)),
        )
        results.append({"mesh_spec": spec, "world_pos": (wx, wy, wz)})
    return results


def compose_morphology(
    stack: TerrainMaskStack,
    templates: List[MorphologyTemplate],
    positions: List[Tuple[float, float, float]],
    seed: int = 42,
    *,
    blend_mode: str = "additive",
    global_scale: float = 1.0,
) -> np.ndarray:
    """Apply multiple morphology templates and combine into a single delta.

    Parameters
    ----------
    stack : TerrainMaskStack
        Terrain stack (read-only -- the returned delta is not applied).
    templates : list of MorphologyTemplate
        Templates to apply (one per position).
    positions : list of (x, y, z) world-space positions
        Placement centres -- must have the same length as ``templates``.
    seed : int
        Base seed. Each template gets ``seed + i`` for variation.
    blend_mode : str
        ``"additive"`` sums all deltas. ``"max"`` takes the per-cell
        maximum absolute contribution (preserves sharp features).
    global_scale : float
        Multiplier applied to the final composed delta.

    Returns
    -------
    np.ndarray (H, W) float64 -- the combined height delta.
    """
    if len(templates) != len(positions):
        raise ValueError(
            f"templates ({len(templates)}) and positions ({len(positions)}) "
            f"must have the same length"
        )

    h = np.asarray(stack.height, dtype=np.float64)
    composed = np.zeros_like(h, dtype=np.float64)

    for i, (tmpl, pos) in enumerate(zip(templates, positions)):
        delta = apply_morphology_template(stack, tmpl, pos, seed + i)
        if blend_mode == "max":
            # Keep whichever has larger absolute magnitude per cell
            composed = np.where(np.abs(delta) > np.abs(composed), delta, composed)
        else:
            composed += delta

    return composed * float(global_scale)


def select_templates_for_terrain(
    stack: TerrainMaskStack,
    *,
    biome: str = "",
    max_templates: int = 5,
    seed: int = 42,
) -> List[Tuple[MorphologyTemplate, Tuple[float, float, float]]]:
    """Analyse local terrain and select appropriate templates with positions.

    Heuristic selection:
      - High local slope variance -> ridge / pinnacle templates
      - Low slope, high elevation -> mesa / plateau templates
      - Low elevation, concave -> valley / canyon templates
      - Random fill from biome-appropriate pool for remaining slots

    Returns a list of (template, world_pos) pairs ready for
    ``compose_morphology``.
    """
    rng = np.random.default_rng(int(seed) & 0xFFFFFFFF)
    h = np.asarray(stack.height, dtype=np.float64)
    rows, cols = h.shape
    cell = float(stack.cell_size)

    pool = list_templates_for_biome(biome)
    if not pool:
        pool = list(DEFAULT_TEMPLATES)

    # Compute simple terrain statistics in a coarse grid
    block = max(4, min(rows, cols) // 4)
    selections: List[Tuple[MorphologyTemplate, Tuple[float, float, float]]] = []

    kind_priority: Dict[str, List[MorphologyTemplate]] = {}
    for t in pool:
        kind_priority.setdefault(t.kind, []).append(t)

    for _ in range(max_templates):
        # Pick a random block
        r0 = int(rng.integers(0, max(1, rows - block)))
        c0 = int(rng.integers(0, max(1, cols - block)))
        patch = h[r0 : r0 + block, c0 : c0 + block]

        mean_h = float(patch.mean())
        std_h = float(patch.std())
        median_h = float(np.median(h))

        # Heuristic kind selection
        if std_h > 10.0:
            preferred = ["ridge_spur", "pinnacle", "glacial"]
        elif mean_h > median_h + 5.0 and std_h < 5.0:
            preferred = ["mesa", "volcanic"]
        elif mean_h < median_h - 5.0:
            preferred = ["valley", "canyon", "karst"]
        else:
            preferred = ["spur", "ridge_spur", "valley"]

        # Pick from preferred kinds that exist in pool
        chosen_tmpl = None
        for kind in preferred:
            candidates = kind_priority.get(kind, [])
            if candidates:
                chosen_tmpl = candidates[int(rng.integers(0, len(candidates)))]
                break
        if chosen_tmpl is None:
            chosen_tmpl = pool[int(rng.integers(0, len(pool)))]

        # World position at block centre
        wx = stack.world_origin_x + (c0 + block / 2) * cell
        wy = stack.world_origin_y + (r0 + block / 2) * cell
        wz = float(patch[block // 2, block // 2])

        selections.append((chosen_tmpl, (wx, wy, wz)))

    return selections


__all__ = [
    "MorphologyTemplate",
    "DEFAULT_TEMPLATES",
    "apply_morphology_template",
    "list_templates_for_biome",
    "get_natural_arch_specs",
    "compose_morphology",
    "select_templates_for_terrain",
]
