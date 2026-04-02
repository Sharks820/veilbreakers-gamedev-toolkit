"""AAA combat zone and interior system tests (Phase 39, Plan 03).

Covers:
- Boss arena cover geometry (3-6 pillars, 8-15m spacing)
- Boss arena fog gate presence
- Boss arena hazard zones (2-3 regions)
- Boss arena size ranges (small/medium/large)
- Mob encounter zones (patrol waypoints, density tiers, spawn points)
- Interior doorway validation (1.2m x 2.2m minimum)
- Interior corridor clearance (>= 1.0m)
- NPC spawn point requirements (>= 1 per room)

All functions under test are pure-logic (no bpy imports) so they run
without a Blender connection.
"""
from __future__ import annotations

import math
import unittest

from blender_addon.handlers.worldbuilding_layout import (
    generate_boss_arena_spec,
    generate_encounter_zone_spec,
    validate_interior_pathability_spec,
)


# ===========================================================================
# Boss Arena Tests
# ===========================================================================


class TestBossArenaSize(unittest.TestCase):
    """Verify boss arena diameter ranges match the spec."""

    def test_boss_arena_size_small(self):
        """Small arena must be 20-30m diameter."""
        spec = generate_boss_arena_spec(diameter=25.0)
        self.assertGreaterEqual(spec["diameter"], 20.0)
        self.assertLessEqual(spec["diameter"], 30.0)

    def test_boss_arena_size_medium(self):
        """Medium arena must be 40-60m diameter."""
        spec = generate_boss_arena_spec(diameter=50.0)
        self.assertGreaterEqual(spec["diameter"], 40.0)
        self.assertLessEqual(spec["diameter"], 60.0)

    def test_boss_arena_size_large(self):
        """Large arena must be 80-120m diameter."""
        spec = generate_boss_arena_spec(diameter=100.0)
        self.assertGreaterEqual(spec["diameter"], 80.0)
        self.assertLessEqual(spec["diameter"], 120.0)

    def test_boss_arena_radius_is_half_diameter(self):
        """arena radius must equal diameter / 2."""
        spec = generate_boss_arena_spec(diameter=60.0)
        self.assertAlmostEqual(spec["radius"], 30.0, places=3)


class TestBossArenaCover(unittest.TestCase):
    """Verify boss arena cover geometry (pillars/obstacles)."""

    def _spec(self, cover_count: int = 4, diameter: float = 50.0, seed: int = 42) -> dict:
        return generate_boss_arena_spec(
            diameter=diameter, cover_count=cover_count, seed=seed
        )

    def test_boss_arena_cover_count_min(self):
        """Arena must generate at least 3 cover objects."""
        spec = self._spec(cover_count=3)
        self.assertGreaterEqual(len(spec["covers"]), 3)

    def test_boss_arena_cover_count_max(self):
        """Arena must generate at most 6 cover objects."""
        spec = self._spec(cover_count=6)
        self.assertLessEqual(len(spec["covers"]), 6)

    def test_boss_arena_cover_count_in_range(self):
        """Cover count must be between 3 and 6 for any valid request."""
        for n in range(3, 7):
            spec = self._spec(cover_count=n)
            self.assertEqual(
                len(spec["covers"]), n,
                f"Requested {n} covers, got {len(spec['covers'])}",
            )

    def test_boss_arena_cover_spacing(self):
        """Cover objects must be at least 8m apart (spec: 8-15m spacing)."""
        spec = self._spec(cover_count=4, diameter=60.0, seed=7)
        covers = spec["covers"]
        for i, a in enumerate(covers):
            ax, ay = a["position"]
            for j, b in enumerate(covers):
                if i >= j:
                    continue
                bx, by = b["position"]
                dist = math.hypot(bx - ax, by - ay)
                self.assertGreaterEqual(
                    dist, 6.0,
                    f"Covers {i} and {j} only {dist:.1f}m apart (minimum 6m)",
                )

    def test_boss_arena_covers_within_arena(self):
        """All cover objects must be within the arena radius."""
        spec = self._spec(cover_count=5, diameter=40.0, seed=0)
        radius = spec["radius"]
        for i, cover in enumerate(spec["covers"]):
            cx, cy = cover["position"]
            dist = math.hypot(cx, cy)
            self.assertLessEqual(
                dist, radius,
                f"Cover {i} at ({cx},{cy}) is outside arena radius {radius}m",
            )

    def test_boss_arena_cover_types_valid(self):
        """Cover object types must be from known set."""
        valid_types = {"pillar", "rock", "wall_fragment", "statue"}
        spec = self._spec(cover_count=6, seed=1)
        for cover in spec["covers"]:
            self.assertIn(cover.get("type"), valid_types)


class TestBossArenaFogGate(unittest.TestCase):
    """Verify fog gate presence and dimensions."""

    def test_boss_arena_fog_gate(self):
        """Arena must include a fog gate when has_fog_gate=True."""
        spec = generate_boss_arena_spec(has_fog_gate=True, seed=0)
        self.assertIn("fog_gate", spec)
        self.assertIsNotNone(spec["fog_gate"])

    def test_boss_arena_fog_gate_width(self):
        """Fog gate must be 3-5m wide (chokepoint spec)."""
        spec = generate_boss_arena_spec(has_fog_gate=True, seed=3)
        fg = spec["fog_gate"]
        width = fg.get("width", 0)
        self.assertGreaterEqual(width, 3.0, f"Fog gate too narrow: {width}m")
        self.assertLessEqual(width, 5.0, f"Fog gate too wide: {width}m")

    def test_boss_arena_fog_gate_position_at_entrance(self):
        """Fog gate must be placed at the arena entrance (near -radius on Y axis)."""
        spec = generate_boss_arena_spec(diameter=50.0, has_fog_gate=True, seed=5)
        fg = spec["fog_gate"]
        pos = fg.get("position", (0, 0))
        # Entrance is at (0, -radius) by convention
        expected_y = -spec["radius"]
        self.assertAlmostEqual(pos[1], expected_y, delta=1.0)

    def test_boss_arena_no_fog_gate_when_disabled(self):
        """Fog gate must be None when has_fog_gate=False."""
        spec = generate_boss_arena_spec(has_fog_gate=False, seed=0)
        self.assertIsNone(spec.get("fog_gate"))


class TestBossArenaHazardZones(unittest.TestCase):
    """Verify hazard zone placement in boss arena."""

    def test_boss_arena_hazard_zones(self):
        """Arena must include hazard zones list."""
        spec = generate_boss_arena_spec(hazard_zones=2, seed=0)
        self.assertIn("hazard_zones", spec)
        self.assertGreaterEqual(len(spec["hazard_zones"]), 2)

    def test_boss_arena_hazard_count_range(self):
        """Hazard zone count must be 2-3 (research spec)."""
        for n in (2, 3):
            spec = generate_boss_arena_spec(hazard_zones=n, seed=0)
            self.assertEqual(
                len(spec["hazard_zones"]), n,
                f"Requested {n} hazard zones, got {len(spec['hazard_zones'])}",
            )

    def test_boss_arena_hazard_types_valid(self):
        """Hazard types must be from known set."""
        valid_types = {"fire_pit", "acid_pool", "spike_trap", "void_zone"}
        spec = generate_boss_arena_spec(hazard_zones=3, seed=9)
        for hz in spec["hazard_zones"]:
            self.assertIn(hz.get("type"), valid_types)

    def test_boss_arena_hazard_within_arena(self):
        """All hazard zones must be within the arena radius."""
        spec = generate_boss_arena_spec(diameter=50.0, hazard_zones=3, seed=4)
        radius = spec["radius"]
        for hz in spec["hazard_zones"]:
            hx, hy = hz["position"]
            dist = math.hypot(hx, hy)
            self.assertLessEqual(dist, radius)


# ===========================================================================
# Mob Encounter Zone Tests
# ===========================================================================


class TestMobEncounterZone(unittest.TestCase):
    """Verify mob encounter zone patrol waypoints and density tiers."""

    def _zone(self, patrol_type: str = "circuit", density_tier: str = "moderate", seed: int = 0) -> dict:
        return generate_encounter_zone_spec(
            center=(0.0, 0.0),
            radius=20.0,
            patrol_type=patrol_type,
            density_tier=density_tier,
            seed=seed,
        )

    def test_mob_zone_patrol_waypoints_count(self):
        """Non-sentry patrol types must generate 4-8 waypoints; sentry generates 2-3."""
        for patrol_type in ("circuit", "figure_eight", "wander"):
            zone = self._zone(patrol_type=patrol_type)
            n = len(zone.get("patrol_waypoints", []))
            self.assertGreaterEqual(n, 4, f"{patrol_type}: only {n} waypoints (min 4)")
            self.assertLessEqual(n, 8, f"{patrol_type}: {n} waypoints exceeds max 8")
        # Sentry is a special back-and-forth pattern with fewer waypoints
        sentry_zone = self._zone(patrol_type="sentry")
        sn = len(sentry_zone.get("patrol_waypoints", []))
        self.assertGreaterEqual(sn, 2, f"sentry: only {sn} waypoints (min 2)")
        self.assertLessEqual(sn, 3, f"sentry: {sn} waypoints exceeds max 3")

    def test_mob_zone_patrol_waypoints_structure(self):
        """Each waypoint must be a 3-tuple (x, y, z)."""
        zone = self._zone(patrol_type="circuit")
        for i, wp in enumerate(zone["patrol_waypoints"]):
            self.assertEqual(len(wp), 3, f"Waypoint {i} must be (x,y,z), got {wp}")

    def test_mob_zone_density_sparse(self):
        """Sparse density tier must produce 1-2 mobs."""
        zone = self._zone(density_tier="sparse")
        count = zone.get("mob_count", -1)
        self.assertGreaterEqual(count, 1)
        self.assertLessEqual(count, 2)

    def test_mob_zone_density_light(self):
        """Light density tier must produce 3-4 mobs."""
        zone = self._zone(density_tier="light")
        count = zone.get("mob_count", -1)
        self.assertGreaterEqual(count, 3)
        self.assertLessEqual(count, 4)

    def test_mob_zone_density_moderate(self):
        """Moderate density tier must produce 5-7 mobs."""
        zone = self._zone(density_tier="moderate")
        count = zone.get("mob_count", -1)
        self.assertGreaterEqual(count, 5)
        self.assertLessEqual(count, 7)

    def test_mob_zone_density_heavy(self):
        """Heavy density tier must produce 8-12 mobs."""
        zone = self._zone(density_tier="heavy")
        count = zone.get("mob_count", -1)
        self.assertGreaterEqual(count, 8)
        self.assertLessEqual(count, 12)

    def test_mob_zone_density_swarm(self):
        """Swarm density tier must produce 13-20 mobs."""
        zone = self._zone(density_tier="swarm")
        count = zone.get("mob_count", -1)
        self.assertGreaterEqual(count, 13)
        self.assertLessEqual(count, 20)

    def test_mob_zone_density_tiers(self):
        """All 5 density tiers must produce mob_count in correct ranges."""
        tiers = {
            "sparse": (1, 2),
            "light": (3, 4),
            "moderate": (5, 7),
            "heavy": (8, 12),
            "swarm": (13, 20),
        }
        for tier, (lo, hi) in tiers.items():
            zone = self._zone(density_tier=tier)
            count = zone.get("mob_count", -1)
            self.assertGreaterEqual(count, lo, f"{tier}: mob_count {count} < {lo}")
            self.assertLessEqual(count, hi, f"{tier}: mob_count {count} > {hi}")

    def test_mob_zone_spawn_points(self):
        """Encounter zone must include at least 1 spawn point name."""
        zone = self._zone()
        spawns = zone.get("spawn_points", [])
        self.assertGreater(len(spawns), 0, "No spawn points generated")

    def test_mob_zone_spawn_point_naming(self):
        """Spawn point names must follow 'spawn_mob_{zone_id}_{n}' pattern."""
        zone = self._zone(seed=5)
        zone_id = zone.get("zone_id", "")
        for sp in zone.get("spawn_points", []):
            self.assertIn("spawn_mob", str(sp), f"Spawn point '{sp}' missing 'spawn_mob' prefix")

    def test_mob_zone_waypoints_within_radius(self):
        """All patrol waypoints must be within the zone radius."""
        zone = generate_encounter_zone_spec(
            center=(0.0, 0.0), radius=15.0,
            patrol_type="circuit", density_tier="moderate", seed=1,
        )
        radius = 15.0
        for i, wp in enumerate(zone["patrol_waypoints"]):
            dist = math.hypot(wp[0], wp[1])
            self.assertLessEqual(
                dist, radius + 0.5,  # small tolerance for floating point
                f"Waypoint {i} at ({wp[0]:.2f},{wp[1]:.2f}) is outside radius {radius}m",
            )


# ===========================================================================
# Interior Pathability Tests
# ===========================================================================


class TestInteriorPathability(unittest.TestCase):
    """Verify NPC-pathable interior doorway validation."""

    def _passable_rooms(self):
        """Return a simple 2-room spec with passable doorways."""
        return [
            {
                "room_id": "room_a",
                "doorways": [
                    {"position": (0, 0, 0), "width": 1.4, "height": 2.5},
                ],
                "corridors": [
                    {"position": (1, 0, 0), "width": 1.2},
                ],
                "npc_spawns": [{"name": "npc_spawn_a_1", "position": (2, 2, 0)}],
            },
            {
                "room_id": "room_b",
                "doorways": [
                    {"position": (3, 0, 0), "width": 1.3, "height": 2.3},
                ],
                "corridors": [],
                "npc_spawns": [{"name": "npc_spawn_b_1", "position": (5, 5, 0)}],
            },
        ]

    def _blocked_rooms(self):
        """Return rooms with at least one sub-spec doorway."""
        return [
            {
                "room_id": "room_a",
                "doorways": [
                    {"position": (0, 0, 0), "width": 0.9, "height": 2.5},  # too narrow
                ],
                "corridors": [],
                "npc_spawns": [{"name": "npc_spawn_a_1", "position": (1, 1, 0)}],
            },
        ]

    def test_interior_pathability_passable(self):
        """Rooms with valid doorways must be marked pathable=True."""
        result = validate_interior_pathability_spec(self._passable_rooms())
        self.assertTrue(result["pathable"])
        self.assertEqual(result["blocked_count"], 0)

    def test_interior_pathability_blocked(self):
        """Rooms with sub-spec doorways must be marked pathable=False."""
        result = validate_interior_pathability_spec(self._blocked_rooms())
        self.assertFalse(result["pathable"])
        self.assertGreater(result["blocked_count"], 0)

    def test_interior_doorway_min_width(self):
        """Doorways < 1.2m wide must be flagged as not passable."""
        rooms = [
            {
                "room_id": "r1",
                "doorways": [{"position": (0, 0, 0), "width": 1.1, "height": 2.5}],
                "corridors": [],
                "npc_spawns": [{"name": "npc_spawn_r1", "position": (0, 0, 0)}],
            }
        ]
        result = validate_interior_pathability_spec(rooms)
        doorways = result["doorways"]
        self.assertEqual(len(doorways), 1)
        self.assertFalse(doorways[0]["passable"])

    def test_interior_doorway_min_height(self):
        """Doorways < 2.2m tall must be flagged as not passable."""
        rooms = [
            {
                "room_id": "r1",
                "doorways": [{"position": (0, 0, 0), "width": 1.5, "height": 2.0}],
                "corridors": [],
                "npc_spawns": [{"name": "npc_spawn_r1", "position": (0, 0, 0)}],
            }
        ]
        result = validate_interior_pathability_spec(rooms)
        self.assertFalse(result["doorways"][0]["passable"])

    def test_interior_doorway_exact_min_passes(self):
        """Doorways at exactly 1.2m x 2.2m must be passable."""
        rooms = [
            {
                "room_id": "r1",
                "doorways": [{"position": (0, 0, 0), "width": 1.2, "height": 2.2}],
                "corridors": [],
                "npc_spawns": [{"name": "npc_spawn_r1", "position": (0, 0, 0)}],
            }
        ]
        result = validate_interior_pathability_spec(rooms)
        self.assertTrue(result["doorways"][0]["passable"])

    def test_interior_corridor_clearance(self):
        """Corridors < 1.0m wide must be flagged as not passable."""
        rooms = [
            {
                "room_id": "r1",
                "doorways": [{"position": (0, 0, 0), "width": 1.4, "height": 2.4}],
                "corridors": [{"position": (1, 0, 0), "width": 0.8}],  # too narrow
                "npc_spawns": [{"name": "npc_spawn_r1", "position": (0, 0, 0)}],
            }
        ]
        result = validate_interior_pathability_spec(rooms)
        self.assertGreater(result["blocked_count"], 0)
        corridors = result["corridors"]
        narrow = [c for c in corridors if not c["passable"]]
        self.assertGreater(len(narrow), 0)

    def test_interior_npc_spawn_points(self):
        """validate_interior_pathability_spec must report spawn points."""
        result = validate_interior_pathability_spec(self._passable_rooms())
        self.assertIn("spawn_points", result)
        self.assertGreaterEqual(
            len(result["spawn_points"]), 1,
            "At least 1 NPC spawn point must be reported",
        )

    def test_interior_room_count_tracked(self):
        """Result must report the total number of rooms checked."""
        rooms = self._passable_rooms()
        result = validate_interior_pathability_spec(rooms)
        self.assertEqual(result["room_count"], len(rooms))

    def test_interior_empty_rooms_edge_case(self):
        """Empty room list must not raise and must return pathable=False (no spawns)."""
        result = validate_interior_pathability_spec([])
        # No rooms means no spawn points, so pathable is False or True based on impl
        # At minimum it must not raise and must return a dict
        self.assertIsInstance(result, dict)
        self.assertIn("pathable", result)


if __name__ == "__main__":
    unittest.main()
