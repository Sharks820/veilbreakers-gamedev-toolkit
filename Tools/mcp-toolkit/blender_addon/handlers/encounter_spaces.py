"""Pure-logic encounter space template system for combat layout generation.

NO bpy/bmesh imports. Fully testable without Blender.

Provides pre-designed encounter templates (ambush corridors, arenas, gauntlets,
siege approaches, puzzle rooms, boss chambers, etc.) and computes full spatial
layouts with cover, enemy spawns, hazards, entry/exit points, and trigger volumes.

Provides:
  - ENCOUNTER_TEMPLATES: 8 encounter template definitions
  - compute_encounter_layout: resolve template to concrete positions
  - validate_encounter_layout: verify sightlines, spacing, reachability
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Encounter Template Definitions -- 8 templates
# ---------------------------------------------------------------------------

ENCOUNTER_TEMPLATES: dict[str, dict[str, Any]] = {
    "ambush_corridor": {
        "shape": "narrow_corridor",
        "width": 3.0,
        "length": 15.0,
        "cover_positions": [(1.2, 3, 0), (-1.2, 6, 0), (1.2, 9, 0), (-1.2, 12, 0)],
        "enemy_spawn_positions": [(0, 13, 0), (1.2, 14.5, 0), (-1.2, 14.5, 0)],
        "player_entry": (0, 0, 0),
        "player_exit": (0, 15, 0),
        "trigger_volume": {"center": (0, 7.5, 1.5), "size": (3, 15, 3)},
        "flanking_alcoves": [
            {"position": (2.5, 5, 0), "size": (2, 2, 3)},
            {"position": (-2.5, 10, 0), "size": (2, 2, 3)},
        ],
        "difficulty": "medium",
        "min_enemies": 3,
        "max_enemies": 6,
    },
    "arena_circle": {
        "shape": "circular",
        "radius": 12.0,
        "cover_positions": "ring_8",
        "enemy_spawn_positions": "perimeter_4",
        "player_entry": (0, -10, 0),
        "player_exit": (0, 10, 0),
        "boss_position": (0, 0, 0),
        "trigger_volume": {"center": (0, 0, 2), "size": (24, 24, 4)},
        "pillars": "ring_4_inner",
        "difficulty": "hard",
        "min_enemies": 4,
        "max_enemies": 12,
    },
    "gauntlet_run": {
        "shape": "long_corridor",
        "width": 4.0,
        "length": 30.0,
        "hazard_zones": [
            {"center": (0, 5, 0), "radius": 2.0, "type": "fire_trap"},
            {"center": (0, 12, 0), "radius": 2.0, "type": "spike_trap"},
            {"center": (0, 20, 0), "radius": 2.0, "type": "poison_gas"},
        ],
        "enemy_spawn_positions": "alternating_sides",
        "flanking_positions": "alternating_alcoves",
        "player_entry": (0, 0, 0),
        "player_exit": (0, 30, 0),
        "trigger_volume": {"center": (0, 15, 1.5), "size": (4, 30, 3)},
        "checkpoint_positions": [(0, 10, 0), (0, 20, 0)],
        "difficulty": "hard",
        "min_enemies": 6,
        "max_enemies": 10,
    },
    "siege_approach": {
        "shape": "uphill_path",
        "width": 5.0,
        "length": 25.0,
        "elevation_gain": 5.0,
        "archer_positions": "elevated_flanks",
        "barricade_positions": [(0, 8, 1), (0, 16, 3)],
        "enemy_spawn_positions": [(0, 20, 4), (2, 22, 4.5), (-2, 22, 4.5)],
        "player_entry": (0, 0, 0),
        "player_exit": (0, 25, 5),
        "trigger_volume": {"center": (0, 12.5, 2.5), "size": (5, 25, 5)},
        "cover_positions": [(-2, 5, 0.5), (2, 10, 1.5), (-2, 15, 2.5)],
        "difficulty": "hard",
        "min_enemies": 5,
        "max_enemies": 8,
    },
    "puzzle_room": {
        "shape": "square_room",
        "size": 10.0,
        "mechanism_positions": [(3, 3, 0), (-3, 3, 0), (0, -3, 0)],
        "reward_position": (0, 4, 0),
        "trap_positions": [(2, 0, 0), (-2, 0, 0), (0, 2, 0)],
        "player_entry": (0, -5, 0),
        "player_exit": (0, 5, 0),
        "trigger_volume": {"center": (0, 0, 1.5), "size": (10, 10, 3)},
        "enemy_spawn_positions": [],
        "cover_positions": [],
        "difficulty": "medium",
        "min_enemies": 0,
        "max_enemies": 2,
    },
    "boss_chamber": {
        "shape": "circular",
        "radius": 18.0,
        "cover_positions": "ring_6",
        "enemy_spawn_positions": [(0, 0, 0)],
        "player_entry": (0, -16, 0),
        "player_exit": None,  # locked until boss dies
        "boss_position": (0, 5, 0),
        "trigger_volume": {"center": (0, 0, 3), "size": (36, 36, 6)},
        "phase_trigger_zones": [
            {"health_pct": 0.75, "center": (0, 0, 0), "radius": 8.0, "event": "adds_spawn"},
            {"health_pct": 0.50, "center": (0, 0, 0), "radius": 12.0, "event": "arena_hazard"},
            {"health_pct": 0.25, "center": (0, 0, 0), "radius": 16.0, "event": "enrage"},
        ],
        "pillars": "ring_6_inner",
        "difficulty": "boss",
        "min_enemies": 1,
        "max_enemies": 1,
    },
    "defensive_holdout": {
        "shape": "square_room",
        "size": 12.0,
        "cover_positions": [
            (-3, -3, 0), (3, -3, 0), (-3, 3, 0), (3, 3, 0),
            (0, -4, 0), (0, 4, 0),
        ],
        "enemy_spawn_positions": "perimeter_8",
        "player_entry": (0, 0, 0),
        "player_exit": (0, -6, 0),
        "trigger_volume": {"center": (0, 0, 1.5), "size": (12, 12, 3)},
        "defend_point": (0, 0, 0),
        "wave_spawn_delay": 15.0,
        "wave_count": 3,
        "difficulty": "hard",
        "min_enemies": 8,
        "max_enemies": 16,
    },
    "stealth_zone": {
        "shape": "irregular_room",
        "width": 15.0,
        "length": 20.0,
        "cover_positions": [
            (-5, 3, 0), (-2, 7, 0), (3, 5, 0), (5, 10, 0),
            (-4, 12, 0), (2, 14, 0), (-1, 9, 0),
        ],
        "enemy_spawn_positions": [
            (0, 5, 0), (-3, 10, 0), (4, 8, 0), (1, 13, 0),
        ],
        "patrol_routes": [
            [(0, 4, 0), (0, 8, 0), (3, 8, 0), (3, 4, 0)],
            [(-3, 9, 0), (-3, 13, 0), (0, 13, 0), (0, 9, 0)],
        ],
        "player_entry": (0, 0, 0),
        "player_exit": (0, 20, 0),
        "trigger_volume": {"center": (0, 10, 1.5), "size": (15, 20, 3)},
        "shadow_zones": [
            {"center": (-5, 5, 0), "radius": 2.0},
            {"center": (5, 12, 0), "radius": 2.5},
            {"center": (-3, 17, 0), "radius": 2.0},
        ],
        "difficulty": "medium",
        "min_enemies": 3,
        "max_enemies": 5,
    },
}


# ---------------------------------------------------------------------------
# Layout Computation
# ---------------------------------------------------------------------------

def _resolve_ring_positions(
    count: int,
    radius: float,
    center: tuple[float, float, float] = (0, 0, 0),
    start_angle: float = 0.0,
) -> list[tuple[float, float, float]]:
    """Generate evenly-spaced positions in a ring."""
    positions = []
    for i in range(count):
        angle = start_angle + (2 * math.pi * i) / count
        x = center[0] + math.cos(angle) * radius
        y = center[1] + math.sin(angle) * radius
        positions.append((x, y, center[2]))
    return positions


def _resolve_alternating_sides(
    width: float,
    length: float,
    count: int,
    rng: random.Random,
) -> list[tuple[float, float, float]]:
    """Generate positions alternating between left and right sides."""
    positions = []
    spacing = length / (count + 1)
    for i in range(count):
        y_pos = spacing * (i + 1)
        side = 1 if i % 2 == 0 else -1
        x_pos = side * (width / 2 - 0.5 + rng.uniform(-0.3, 0.3))
        positions.append((x_pos, y_pos, 0))
    return positions


def _resolve_elevated_flanks(
    width: float,
    length: float,
    elevation_gain: float,
    count: int,
    rng: random.Random,
) -> list[tuple[float, float, float]]:
    """Generate elevated flank positions along a path."""
    positions = []
    spacing = length / (count + 1)
    for i in range(count):
        y_pos = spacing * (i + 1)
        side = 1 if i % 2 == 0 else -1
        x_pos = side * (width / 2 + 2.0 + rng.uniform(0, 1.5))
        z_pos = (y_pos / length) * elevation_gain + 1.5  # elevated above path
        positions.append((x_pos, y_pos, z_pos))
    return positions


def _resolve_alternating_alcoves(
    width: float,
    length: float,
    count: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate flanking alcove positions along a corridor."""
    alcoves = []
    spacing = length / (count + 1)
    for i in range(count):
        y_pos = spacing * (i + 1)
        side = 1 if i % 2 == 0 else -1
        x_pos = side * (width / 2 + 1.5)
        alcoves.append({
            "position": (x_pos, y_pos, 0),
            "size": (2.0 + rng.uniform(-0.3, 0.3), 2.0, 3.0),
            "facing": -side,  # faces inward
        })
    return alcoves


def compute_encounter_layout(
    template_name: str,
    seed: int = 42,
    enemy_count: int | None = None,
) -> dict[str, Any]:
    """Compute positions for all encounter elements from a template.

    Parameters
    ----------
    template_name : str
        Key into ENCOUNTER_TEMPLATES.
    seed : int
        Random seed for deterministic generation.
    enemy_count : int, optional
        Override enemy count (clamped to template min/max).

    Returns
    -------
    dict with:
        "shape": str - shape type
        "bounds": dict - bounding box of the encounter space
        "cover": list of (x, y, z) - cover positions
        "enemies": list of (x, y, z) - enemy spawn positions
        "hazards": list of dict - hazard zone definitions
        "entry": (x, y, z) - player entry point
        "exit": (x, y, z) or None - player exit point
        "triggers": list of dict - trigger volumes
        "props": list of dict - additional props (pillars, alcoves, etc.)
        "difficulty": str
        "template": str - original template name
    """
    if template_name not in ENCOUNTER_TEMPLATES:
        raise ValueError(
            f"Unknown encounter template '{template_name}'. "
            f"Valid templates: {sorted(ENCOUNTER_TEMPLATES.keys())}"
        )

    template = ENCOUNTER_TEMPLATES[template_name]
    rng = random.Random(seed)
    result: dict[str, Any] = {
        "template": template_name,
        "shape": template["shape"],
        "difficulty": template.get("difficulty", "medium"),
        "entry": template["player_entry"],
        "exit": template.get("player_exit"),
        "triggers": [],
        "hazards": [],
        "props": [],
    }

    # Resolve bounds
    if template["shape"] == "circular":
        radius = template["radius"]
        result["bounds"] = {
            "min": (-radius, -radius, 0),
            "max": (radius, radius, radius * 0.3),
            "radius": radius,
        }
    elif template["shape"] in ("narrow_corridor", "long_corridor", "uphill_path"):
        w = template["width"]
        l = template["length"]
        h = template.get("elevation_gain", 3.0)
        result["bounds"] = {
            "min": (-w / 2, 0, 0),
            "max": (w / 2, l, h),
        }
    elif template["shape"] in ("square_room", "irregular_room"):
        s = template.get("size", template.get("width", 10.0))
        l = template.get("length", s)
        # Collect all defined positions to compute encompassing bounds
        all_y = [0.0]
        all_x = [0.0]
        for key in ("player_entry", "player_exit", "boss_position", "defend_point", "reward_position"):
            pt = template.get(key)
            if pt:
                all_x.append(pt[0])
                all_y.append(pt[1])
        for key in ("cover_positions", "enemy_spawn_positions", "mechanism_positions", "trap_positions"):
            pts = template.get(key, [])
            if isinstance(pts, list):
                for pt in pts:
                    if isinstance(pt, tuple) and len(pt) >= 2:
                        all_x.append(pt[0])
                        all_y.append(pt[1])
        # Bounds must cover all positions with at least room size
        x_center = (min(all_x) + max(all_x)) / 2.0
        y_center = (min(all_y) + max(all_y)) / 2.0
        half_w = max(s / 2.0, (max(all_x) - min(all_x)) / 2.0 + 1.0)
        half_l = max(l / 2.0, (max(all_y) - min(all_y)) / 2.0 + 1.0)
        result["bounds"] = {
            "min": (x_center - half_w, y_center - half_l, 0),
            "max": (x_center + half_w, y_center + half_l, 3.0),
        }

    # Resolve cover positions
    cover_spec = template.get("cover_positions", [])
    if isinstance(cover_spec, str):
        if cover_spec.startswith("ring_"):
            count = int(cover_spec.split("_")[1])
            radius = template.get("radius", 10.0) * 0.6
            cover = _resolve_ring_positions(count, radius)
        else:
            cover = []
    else:
        cover = list(cover_spec)
    result["cover"] = cover

    # Resolve enemy spawn positions
    enemy_spec = template.get("enemy_spawn_positions", [])
    if isinstance(enemy_spec, str):
        if enemy_spec.startswith("perimeter_"):
            count = int(enemy_spec.split("_")[1])
            radius = template.get("radius", template.get("size", 10.0)) * 0.45
            if template["shape"] == "circular":
                radius = template["radius"] * 0.85
            # Offset start angle so enemies don't spawn on top of entry
            # Entry is typically at the bottom (-Y), so start ring from top (+Y)
            entry = template.get("player_entry", (0, 0, 0))
            entry_angle = math.atan2(entry[1], entry[0]) if (entry[0] != 0 or entry[1] != 0) else -math.pi / 2
            # Start ring from opposite side of entry, offset by half-step
            start_angle = entry_angle + math.pi + (math.pi / count)
            enemies = _resolve_ring_positions(count, radius, start_angle=start_angle)
        elif enemy_spec == "alternating_sides":
            w = template.get("width", 4.0)
            l = template.get("length", 30.0)
            min_e = template.get("min_enemies", 4)
            max_e = template.get("max_enemies", 8)
            count = enemy_count if enemy_count is not None else rng.randint(min_e, max_e)
            count = max(min_e, min(count, max_e))
            enemies = [pos for pos in _resolve_alternating_sides(w, l, count, rng)]
        else:
            enemies = []
    else:
        enemies = list(enemy_spec)

    # Override enemy count if specified (explicit override bypasses min/max)
    if enemy_count is not None and isinstance(enemy_spec, list):
        max_e = template.get("max_enemies", len(enemies))
        count = max(0, min(enemy_count, max_e))
        if count < len(enemies):
            # Sample subset
            enemies = enemies[:count]
        elif count > len(enemies) and len(enemies) > 0:
            # Add random positions near existing spawns
            for _ in range(count - len(enemies)):
                base = enemies[rng.randint(0, len(enemies) - 1)]
                offset = (
                    base[0] + rng.uniform(-2, 2),
                    base[1] + rng.uniform(-2, 2),
                    base[2],
                )
                enemies.append(offset)

    result["enemies"] = enemies

    # Resolve hazards
    hazard_zones = template.get("hazard_zones", [])
    result["hazards"] = list(hazard_zones)

    # Resolve trigger volume
    trigger_vol = template.get("trigger_volume")
    if trigger_vol:
        result["triggers"].append({
            "type": "encounter_start",
            "center": trigger_vol["center"],
            "size": trigger_vol["size"],
        })

    # Phase triggers (boss fights)
    phase_triggers = template.get("phase_trigger_zones", [])
    for pt in phase_triggers:
        result["triggers"].append({
            "type": "phase_trigger",
            "health_pct": pt["health_pct"],
            "center": pt["center"],
            "radius": pt["radius"],
            "event": pt["event"],
        })

    # Resolve props (pillars, alcoves, etc.)
    pillar_spec = template.get("pillars")
    if isinstance(pillar_spec, str):
        parts = pillar_spec.split("_")
        # e.g. "ring_4_inner" or "ring_6_inner"
        count = int(parts[1])
        radius = template.get("radius", 10.0) * 0.4
        pillar_positions = _resolve_ring_positions(count, radius)
        for pos in pillar_positions:
            result["props"].append({
                "type": "pillar",
                "position": pos,
                "size": (0.8, 0.8, 4.0),
            })

    # Flanking alcoves
    alcoves = template.get("flanking_alcoves")
    if isinstance(alcoves, str) and alcoves == "alternating_alcoves":
        w = template.get("width", 4.0)
        l = template.get("length", 30.0)
        alcove_list = _resolve_alternating_alcoves(w, l, 4, rng)
        for alc in alcove_list:
            result["props"].append({
                "type": "alcove",
                "position": alc["position"],
                "size": alc["size"],
            })
    elif isinstance(alcoves, list):
        for alc in alcoves:
            result["props"].append({
                "type": "alcove",
                "position": alc["position"],
                "size": alc["size"],
            })

    # Barricades
    barricades = template.get("barricade_positions", [])
    for bp in barricades:
        result["props"].append({
            "type": "barricade",
            "position": bp,
            "size": (3.0, 0.5, 1.2),
        })

    # Archer positions
    archer_spec = template.get("archer_positions")
    if isinstance(archer_spec, str) and archer_spec == "elevated_flanks":
        w = template.get("width", 5.0)
        l = template.get("length", 25.0)
        eg = template.get("elevation_gain", 5.0)
        archers = _resolve_elevated_flanks(w, l, eg, 4, rng)
        result["props"].extend([
            {"type": "archer_perch", "position": pos, "size": (2, 2, 1.5)}
            for pos in archers
        ])

    # Patrol routes (stealth zones)
    patrol_routes = template.get("patrol_routes", [])
    result["patrol_routes"] = patrol_routes

    # Shadow zones
    shadow_zones = template.get("shadow_zones", [])
    result["shadow_zones"] = shadow_zones

    # Mechanism and trap positions (puzzle rooms)
    mechanisms = template.get("mechanism_positions", [])
    result["mechanisms"] = mechanisms

    traps = template.get("trap_positions", [])
    result["traps"] = traps

    # Reward position
    reward = template.get("reward_position")
    if reward:
        result["reward_position"] = reward

    # Defend point
    defend = template.get("defend_point")
    if defend:
        result["defend_point"] = defend

    # Checkpoint positions
    checkpoints = template.get("checkpoint_positions", [])
    result["checkpoints"] = checkpoints

    return result


# ---------------------------------------------------------------------------
# Layout Validation
# ---------------------------------------------------------------------------

def validate_encounter_layout(
    layout: dict[str, Any],
) -> dict[str, Any]:
    """Validate an encounter layout for gameplay quality.

    Checks:
    - Cover positions have adequate spacing (not bunched up)
    - Enemy spawns are outside player entry sightline (no spawn camping)
    - All positions within bounds
    - Minimum distance from player entry to first enemy
    - Hazards don't overlap entry point

    Parameters
    ----------
    layout : dict
        Output from compute_encounter_layout.

    Returns
    -------
    dict with:
        "valid": bool
        "issues": list of str (empty if valid)
        "metrics": dict of quality metrics
    """
    issues: list[str] = []
    metrics: dict[str, Any] = {}

    entry = layout.get("entry", (0, 0, 0))
    cover = layout.get("cover", [])
    enemies = layout.get("enemies", [])
    hazards = layout.get("hazards", [])
    bounds = layout.get("bounds", {})

    # 1. Cover spacing check
    if len(cover) >= 2:
        min_cover_dist = float("inf")
        for i in range(len(cover)):
            for j in range(i + 1, len(cover)):
                d = _dist_3d(cover[i], cover[j])
                min_cover_dist = min(min_cover_dist, d)
        metrics["min_cover_spacing"] = min_cover_dist
        if min_cover_dist < 1.5:
            issues.append(
                f"Cover positions too close: {min_cover_dist:.1f}m "
                f"(min 1.5m recommended)"
            )

    # 2. Enemy spawn distance from entry
    if enemies:
        min_enemy_dist = min(_dist_3d(entry, e) for e in enemies)
        metrics["min_enemy_distance_from_entry"] = min_enemy_dist
        if min_enemy_dist < 3.0:
            issues.append(
                f"Enemy spawn too close to entry: {min_enemy_dist:.1f}m "
                f"(min 3.0m recommended)"
            )

    # 3. Bounds check
    if bounds:
        b_min = bounds.get("min")
        b_max = bounds.get("max")
        radius = bounds.get("radius")
        all_positions = list(cover) + list(enemies)
        for pos in all_positions:
            if radius is not None:
                dist_from_center = math.sqrt(pos[0] ** 2 + pos[1] ** 2)
                if dist_from_center > radius * 1.1:
                    issues.append(
                        f"Position {pos} outside radius {radius}"
                    )
            elif b_min is not None and b_max is not None:
                for axis in range(min(len(pos), len(b_min))):
                    if pos[axis] < b_min[axis] - 0.5 or pos[axis] > b_max[axis] + 0.5:
                        issues.append(
                            f"Position {pos} outside bounds on axis {axis}"
                        )
                        break

    # 4. Hazard safety check
    for hazard in hazards:
        h_center = hazard.get("center", (0, 0, 0))
        h_radius = hazard.get("radius", 1.0)
        dist_to_entry = _dist_3d(entry, h_center)
        if dist_to_entry < h_radius + 1.0:
            issues.append(
                f"Hazard at {h_center} too close to entry "
                f"(dist={dist_to_entry:.1f}m, hazard_radius={h_radius}m)"
            )

    # 5. Overall metrics
    if enemies:
        avg_enemy_dist = sum(_dist_3d(entry, e) for e in enemies) / len(enemies)
        metrics["avg_enemy_distance_from_entry"] = avg_enemy_dist
    metrics["cover_count"] = len(cover)
    metrics["enemy_count"] = len(enemies)
    metrics["hazard_count"] = len(hazards)

    # Cover-to-enemy ratio
    if enemies:
        metrics["cover_to_enemy_ratio"] = len(cover) / len(enemies)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "metrics": metrics,
    }


def _dist_3d(
    a: tuple[float, ...],
    b: tuple[float, ...],
) -> float:
    """Euclidean distance between two 3D points."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = (a[2] if len(a) > 2 else 0) - (b[2] if len(b) > 2 else 0)
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def get_available_templates() -> list[str]:
    """Return sorted list of all available encounter templates."""
    return sorted(ENCOUNTER_TEMPLATES.keys())


def get_templates_by_difficulty(difficulty: str) -> list[str]:
    """Return templates matching a given difficulty level."""
    return sorted(
        name for name, tmpl in ENCOUNTER_TEMPLATES.items()
        if tmpl.get("difficulty") == difficulty
    )
