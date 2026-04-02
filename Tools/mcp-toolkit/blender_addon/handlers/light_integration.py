"""Light source integration system for automatic light placement near
light-emitting props.

NO bpy/bmesh imports. Fully testable without Blender.

Computes matching light sources for placed props that naturally emit light
(torches, campfires, lanterns, etc.), with appropriate color, energy, radius,
and optional flicker animation metadata.

Provides:
  - LIGHT_PROP_MAP: 8 light-emitting prop definitions with light parameters
  - compute_light_placements: For each placed prop, compute a matching light
  - merge_nearby_lights: Merge overlapping lights for performance
  - compute_light_budget: Estimate performance cost of light placements
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Light Prop Definitions -- 8 light-emitting props
# ---------------------------------------------------------------------------

LIGHT_PROP_MAP: dict[str, dict[str, Any]] = {
    "torch_sconce": {
        "type": "point",
        "color": (1.0, 0.8, 0.5),
        "energy": 50,
        "radius": 5.0,
        "flicker": True,
        "offset_z": 2.0,
        "shadow": True,
    },
    "campfire": {
        "type": "point",
        "color": (1.0, 0.7, 0.3),
        "energy": 100,
        "radius": 8.0,
        "flicker": True,
        "offset_z": 0.5,
        "shadow": True,
    },
    "lantern": {
        "type": "point",
        "color": (1.0, 0.9, 0.7),
        "energy": 30,
        "radius": 4.0,
        "flicker": False,
        "offset_z": 1.5,
        "shadow": True,
    },
    "candelabra": {
        "type": "point",
        "color": (1.0, 0.85, 0.6),
        "energy": 20,
        "radius": 3.0,
        "flicker": True,
        "offset_z": 1.2,
        "shadow": False,
    },
    "brazier": {
        "type": "point",
        "color": (1.0, 0.6, 0.2),
        "energy": 80,
        "radius": 6.0,
        "flicker": True,
        "offset_z": 0.8,
        "shadow": True,
    },
    "crystal_light": {
        "type": "point",
        "color": (0.6, 0.8, 1.0),
        "energy": 40,
        "radius": 5.0,
        "flicker": False,
        "offset_z": 1.0,
        "shadow": True,
    },
    "window": {
        "type": "area",
        "color": (0.8, 0.9, 1.0),
        "energy": 30,
        "radius": 3.0,
        "direction": "inward",
        "flicker": False,
        "offset_z": 2.5,
        "shadow": True,
    },
    "fireplace": {
        "type": "area",
        "color": (1.0, 0.7, 0.3),
        "energy": 120,
        "radius": 6.0,
        "flicker": True,
        "offset_z": 0.5,
        "shadow": True,
    },
}

# Props that can appear in scenes but don't emit light
_NON_LIGHT_PROPS = frozenset([
    "chest", "barrel", "crate", "table", "chair", "bookshelf",
    "bed", "rug", "banner", "statue", "pillar", "door",
])


# ---------------------------------------------------------------------------
# Flicker animation presets
# ---------------------------------------------------------------------------

FLICKER_PRESETS: dict[str, dict[str, Any]] = {
    "gentle": {
        "frequency": 2.0,
        "amplitude": 0.1,
        "pattern": "sine",
    },
    "torch": {
        "frequency": 4.0,
        "amplitude": 0.25,
        "pattern": "noise",
    },
    "campfire": {
        "frequency": 3.0,
        "amplitude": 0.3,
        "pattern": "noise",
    },
    "dying": {
        "frequency": 1.5,
        "amplitude": 0.5,
        "pattern": "fade",
    },
}

# Map prop types to flicker presets
_PROP_FLICKER_MAP: dict[str, str] = {
    "torch_sconce": "torch",
    "campfire": "campfire",
    "candelabra": "gentle",
    "brazier": "campfire",
    "fireplace": "campfire",
}


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_light_placements(
    prop_positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each placed prop that emits light, compute a matching light source.

    Parameters
    ----------
    prop_positions : list of dict
        Each dict has at minimum: ``type`` (str), ``position`` (x, y) or (x, y, z).
        Optional: ``scale`` (float, affects energy), ``on`` (bool, default True).

    Returns
    -------
    list of dict
        Light placement dicts with: ``light_type``, ``position`` (x, y, z),
        ``color`` (r, g, b), ``energy``, ``radius``, ``shadow``, ``flicker``
        (dict or None), ``source_prop`` (str).
    """
    lights: list[dict[str, Any]] = []

    for prop in prop_positions:
        prop_type = prop.get("type", "")
        if prop_type not in LIGHT_PROP_MAP:
            continue

        # Allow disabling individual lights
        if not prop.get("on", True):
            continue

        light_def = LIGHT_PROP_MAP[prop_type]
        pos = prop.get("position", (0, 0))

        # Handle 2D or 3D positions
        if len(pos) == 2:
            light_pos = (pos[0], pos[1], light_def["offset_z"])
        else:
            light_pos = (pos[0], pos[1], pos[2] + light_def["offset_z"])

        # Scale affects energy
        scale = prop.get("scale", 1.0)
        energy = light_def["energy"] * scale

        # Build flicker data
        flicker_data = None
        if light_def.get("flicker", False):
            preset_name = _PROP_FLICKER_MAP.get(prop_type, "gentle")
            flicker_data = dict(FLICKER_PRESETS[preset_name])

        lights.append({
            "light_type": light_def["type"],
            "position": (
                round(light_pos[0], 3),
                round(light_pos[1], 3),
                round(light_pos[2], 3),
            ),
            "color": light_def["color"],
            "energy": round(energy, 2),
            "radius": light_def["radius"],
            "shadow": light_def.get("shadow", True),
            "flicker": flicker_data,
            "source_prop": prop_type,
        })

    return lights


def merge_nearby_lights(
    lights: list[dict[str, Any]],
    merge_distance: float = 2.0,
) -> list[dict[str, Any]]:
    """Merge overlapping lights for performance optimization.

    Lights within ``merge_distance`` of each other are combined: position is
    averaged, energy is summed, radius takes the maximum, and color is
    averaged weighted by energy.

    Parameters
    ----------
    lights : list of dict
        Light placements from ``compute_light_placements``.
    merge_distance : float
        Maximum distance for merging (default 2.0).

    Returns
    -------
    list of dict
        Merged light placements (fewer lights, same coverage).
    """
    if not lights:
        return []

    used = [False] * len(lights)
    merged: list[dict[str, Any]] = []

    for i in range(len(lights)):
        if used[i]:
            continue

        cluster = [i]
        cluster_members = [lights[i]]
        used[i] = True

        for j in range(i + 1, len(lights)):
            if used[j]:
                continue
            pj = lights[j]["position"]
            # Check distance against ANY member in the cluster, not just the seed
            close_to_cluster = any(
                math.sqrt(
                    (pj[0] - member["position"][0]) ** 2
                    + (pj[1] - member["position"][1]) ** 2
                    + (pj[2] - member["position"][2]) ** 2
                ) < merge_distance
                for member in cluster_members
            )
            if close_to_cluster:
                cluster.append(j)
                cluster_members.append(lights[j])
                used[j] = True

        if len(cluster) == 1:
            merged.append(dict(lights[i]))
        else:
            # Merge cluster
            total_energy = sum(lights[k]["energy"] for k in cluster)
            avg_pos = [0.0, 0.0, 0.0]
            avg_color = [0.0, 0.0, 0.0]
            max_radius = 0.0
            has_shadow = False
            has_flicker = None

            for k in cluster:
                lk = lights[k]
                w = lk["energy"] / total_energy if total_energy > 0 else 1.0 / len(cluster)
                for d in range(3):
                    avg_pos[d] += lk["position"][d] * w
                    avg_color[d] += lk["color"][d] * w
                max_radius = max(max_radius, lk["radius"])
                if lk.get("shadow"):
                    has_shadow = True
                if lk.get("flicker") and has_flicker is None:
                    has_flicker = lk["flicker"]

            merged.append({
                "light_type": "point",
                "position": (
                    round(avg_pos[0], 3),
                    round(avg_pos[1], 3),
                    round(avg_pos[2], 3),
                ),
                "color": (
                    round(avg_color[0], 3),
                    round(avg_color[1], 3),
                    round(avg_color[2], 3),
                ),
                "energy": round(total_energy, 2),
                "radius": max_radius,
                "shadow": has_shadow,
                "flicker": has_flicker,
                "source_prop": "merged",
                "merged_count": len(cluster),
            })

    return merged


def compute_light_budget(
    lights: list[dict[str, Any]],
    shadow_cost: float = 3.0,
    flicker_cost: float = 0.5,
) -> dict[str, Any]:
    """Estimate performance cost of light placements.

    Parameters
    ----------
    lights : list of dict
        Light placements.
    shadow_cost : float
        Relative cost multiplier for shadow-casting lights.
    flicker_cost : float
        Additional cost for animated flickering lights.

    Returns
    -------
    dict
        Budget summary: total_lights, shadow_lights, flicker_lights,
        estimated_cost, recommendation.
    """
    total = len(lights)
    shadow_count = sum(1 for l in lights if l.get("shadow", False))
    flicker_count = sum(1 for l in lights if l.get("flicker") is not None)

    base_cost = total
    cost = base_cost + shadow_count * shadow_cost + flicker_count * flicker_cost

    # Recommendations based on typical game budgets
    if cost <= 20:
        recommendation = "excellent"
    elif cost <= 50:
        recommendation = "good"
    elif cost <= 100:
        recommendation = "acceptable"
    elif cost <= 200:
        recommendation = "heavy - consider merging"
    else:
        recommendation = "excessive - merge and reduce shadows"

    return {
        "total_lights": total,
        "shadow_lights": shadow_count,
        "flicker_lights": flicker_count,
        "estimated_cost": round(cost, 2),
        "recommendation": recommendation,
    }
