"""Regression tests for furniture placement rotations.

These tests document the correct rotation behavior — items placed against
a wall must face TOWARD the room interior, not toward the wall they back
against.

Both _building_grammar._pick_wall_position and
settlement_generator._furnish_interior contain 180-degree rotation bugs
that cause wall-placed furniture to face the wall.  These tests FAIL with
the current code and will start passing once the rotation bug is fixed.

Math background (Blender Z-up, default -Y forward):
  Given a Z-axis rotation R, the forward vector is:
      forward = (-sin(R), -cos(R))
  For an item to face the room interior the dot product of the forward
  vector with the direction from the item toward the room center must be
  POSITIVE (> 0).
"""

import math
import sys
import os
import random

import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

# Ensure the mcp-toolkit source tree is importable.
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, _TOOLKIT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _forward_vector(rotation_z: float) -> tuple[float, float]:
    """Return the 2-D forward direction for a Blender Z-axis rotation.

    In Blender, the -Y axis is forward at rotation 0.  After rotating R
    radians around Z:
        forward = (-sin(R), -cos(R))
    """
    return (-math.sin(rotation_z), -math.cos(rotation_z))


def _dot2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _normalize2(v: tuple[float, float]) -> tuple[float, float]:
    mag = math.sqrt(v[0] ** 2 + v[1] ** 2)
    if mag < 1e-9:
        return (0.0, 0.0)
    return (v[0] / mag, v[1] / mag)


def _dir_to_center(
    item_x: float, item_y: float, center_x: float, center_y: float
) -> tuple[float, float]:
    return _normalize2((center_x - item_x, center_y - item_y))


# ---------------------------------------------------------------------------
# Test 1 — _pick_wall_position: wall items face room interior
# ---------------------------------------------------------------------------

class TestWallItemsFaceRoomInterior:
    """_pick_wall_position must return rotations that face the room center."""

    # Room dimensions for all sub-tests
    ROOM_WIDTH = 10.0
    ROOM_DEPTH = 10.0
    ITEM_SX = 0.6
    ITEM_SY = 0.4
    WALL_MARGIN = 0.3

    def _check_wall(self, wall_id: int, expected_description: str):
        from blender_addon.handlers._building_grammar import _pick_wall_position

        rng = random.Random(42)
        room_cx = self.ROOM_WIDTH / 2.0
        room_cy = self.ROOM_DEPTH / 2.0

        failures = []
        for trial in range(20):
            x, y, rot, _, _ = _pick_wall_position(
                wall_id,
                self.ITEM_SX,
                self.ITEM_SY,
                self.ROOM_WIDTH,
                self.ROOM_DEPTH,
                self.WALL_MARGIN,
                rng,
            )
            fwd = _forward_vector(rot)
            d2c = _dir_to_center(x, y, room_cx, room_cy)
            dot = _dot2(fwd, d2c)
            if dot <= 0.0:
                failures.append(
                    f"trial {trial}: pos=({x:.3f},{y:.3f}) rot={rot:.4f} "
                    f"fwd=({fwd[0]:.3f},{fwd[1]:.3f}) "
                    f"dir_to_center=({d2c[0]:.3f},{d2c[1]:.3f}) "
                    f"dot={dot:.4f} (expected > 0)"
                )

        assert not failures, (
            f"Wall {wall_id} ({expected_description}) items face the wall, "
            f"not the interior.\n" + "\n".join(failures)
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_front_wall_faces_interior(self):
        """Items on the front wall (wall_id=0, y near 0) must face +Y (toward center)."""
        self._check_wall(0, "front wall y=0")

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_back_wall_faces_interior(self):
        """Items on the back wall (wall_id=1, y near depth) must face -Y (toward center)."""
        self._check_wall(1, "back wall y=depth")

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_left_wall_faces_interior(self):
        """Items on the left wall (wall_id=2, x near 0) must face +X (toward center)."""
        self._check_wall(2, "left wall x=0")

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_right_wall_faces_interior(self):
        """Items on the right wall (wall_id=3, x near width) must face -X (toward center)."""
        self._check_wall(3, "right wall x=width")

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_non_square_room_all_walls(self):
        """Rotation direction must be correct for a non-square (6 x 12) room."""
        from blender_addon.handlers._building_grammar import _pick_wall_position

        width, depth = 6.0, 12.0
        room_cx, room_cy = width / 2.0, depth / 2.0
        rng = random.Random(99)

        for wall_id in range(4):
            for trial in range(10):
                x, y, rot, _, _ = _pick_wall_position(
                    wall_id, 0.5, 0.4, width, depth, 0.3, rng
                )
                fwd = _forward_vector(rot)
                d2c = _dir_to_center(x, y, room_cx, room_cy)
                dot = _dot2(fwd, d2c)
                assert dot > 0.0, (
                    f"Non-square room: wall {wall_id} trial {trial} "
                    f"pos=({x:.3f},{y:.3f}) rot={rot:.4f} dot={dot:.4f}"
                )


# ---------------------------------------------------------------------------
# Test 2 — generate_interior_layout: chairs face table anchor
# ---------------------------------------------------------------------------

class TestChairsFaceTableCluster:
    """Chairs placed in a table cluster must face the table, not away from it."""

    def test_chairs_face_table_anchor(self):
        """Chair rotations must point toward the table anchor, not away from it.

        The correct formula is:
            rot = atan2(dy, dx) + pi/2
        The current (buggy) formula is:
            rot = atan2(dy, dx) - pi/2
        which produces a 180-degree rotation error.
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout

        # Tavern rooms are guaranteed to have a table+chairs cluster.
        items = generate_interior_layout(
            room_type="tavern", width=8.0, depth=8.0, seed=7
        )

        tables = [i for i in items if "table" in i["type"]]
        chairs = [i for i in items if "chair" in i["type"]]

        assert tables, "No tables found — test precondition failed."
        assert chairs, "No chairs found — test precondition failed."

        # Use the first table as the reference anchor.
        tx, ty, _ = tables[0]["position"]

        failures = []
        for chair in chairs:
            cx, cy, _ = chair["position"]
            rot = chair["rotation"]

            # Vector from chair to table (where the chair should be looking).
            dx = tx - cx
            dy = ty - cy

            # Expected rotation: atan2(dy, dx) + pi/2
            expected_rot = math.atan2(dy, dx) + math.pi / 2

            # Normalize both angles to [-pi, pi] for comparison.
            def _norm(a: float) -> float:
                while a > math.pi:
                    a -= 2 * math.pi
                while a < -math.pi:
                    a += 2 * math.pi
                return a

            diff = abs(_norm(rot - expected_rot))
            # Allow 15-degree tolerance for randomness, but not 180 degrees.
            if diff > math.radians(15) and abs(diff - math.pi) < math.radians(15):
                failures.append(
                    f"Chair at ({cx:.3f},{cy:.3f}) rot={rot:.4f} "
                    f"expected~{expected_rot:.4f} diff={diff:.4f} rad "
                    "(180-degree bug detected)"
                )

        assert not failures, (
            "Chairs face AWAY from the table (180-degree rotation bug):\n"
            + "\n".join(failures)
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_face_anchor_formula_produces_inward_facing(self):
        """Directly validate the face_anchor rotation formula used in Phase 2.

        The formula `atan2(ay - py, ax - px) - pi/2` produces a forward
        vector pointing AWAY from the anchor.  It must be `+ pi/2`.
        """
        # Simulate: anchor (table) at center, chair placed to the right.
        ax, ay = 4.0, 4.0   # anchor (table) position
        px, py = 5.5, 4.0   # member (chair) position (to the right of table)

        # Buggy formula (current code):
        buggy_rot = math.atan2(ay - py, ax - px) - math.pi / 2
        buggy_fwd = _forward_vector(buggy_rot)
        dir_to_anchor = _normalize2((ax - px, ay - py))
        buggy_dot = _dot2(buggy_fwd, dir_to_anchor)

        # Correct formula:
        correct_rot = math.atan2(ay - py, ax - px) + math.pi / 2
        correct_fwd = _forward_vector(correct_rot)
        correct_dot = _dot2(correct_fwd, dir_to_anchor)

        # The buggy formula must be facing away (dot <= 0) — confirms the bug exists.
        assert buggy_dot <= 0.0, (
            f"Expected buggy formula to face away from anchor but got dot={buggy_dot:.4f}"
        )
        # The correct formula must face toward anchor (dot > 0).
        assert correct_dot > 0.0, (
            f"Correct formula should face toward anchor but got dot={correct_dot:.4f}"
        )


# ---------------------------------------------------------------------------
# Test 3 — Corner items face room center
# ---------------------------------------------------------------------------

class TestCornerItemsFaceRoomCenter:
    """Corner items must have rotations that face toward the room center, not hardcoded 0."""

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_corner_items_not_hardcoded_zero(self):
        """Corner items placed in each quadrant must not all have rotation=0.

        A hardcoded rotation of 0.0 only faces the room interior for one
        corner (the front-right corner of the default orientation).  All
        other corners produce the wrong facing direction.
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout

        # Use a room type likely to have corner items (e.g., storage).
        items = generate_interior_layout(
            room_type="storage", width=8.0, depth=8.0, seed=3
        )

        if not items:
            pytest.skip("No items generated for storage room — cannot test corners.")

        corner_items = _classify_corner_items(items, room_width=8.0, room_depth=8.0)

        if not corner_items:
            pytest.skip("No corner items found — cannot test corner rotations.")

        failures = []
        room_cx, room_cy = 4.0, 4.0
        for item in corner_items:
            x, y, _ = item["position"]
            rot = item["rotation"]
            fwd = _forward_vector(rot)
            d2c = _dir_to_center(x, y, room_cx, room_cy)
            dot = _dot2(fwd, d2c)
            if dot <= 0.0:
                failures.append(
                    f"Corner item '{item['type']}' at ({x:.3f},{y:.3f}) "
                    f"rot={rot:.4f} dot={dot:.4f} faces away from center"
                )

        assert not failures, (
            "Corner items face away from room center:\n" + "\n".join(failures)
        )

    def test_corner_rotation_covers_all_quadrants(self):
        """Items placed in different room quadrants must have different rotations.

        If all corners have rot=0.0 (or a single hardcoded value), items
        in at least three of the four corners will face the wrong direction.
        This test verifies the rotation varies by corner quadrant.
        """
        from blender_addon.handlers._building_grammar import generate_interior_layout

        all_rotations: set[float] = set()
        for seed in range(5):
            items = generate_interior_layout(
                room_type="storage", width=8.0, depth=8.0, seed=seed
            )
            corner_items = _classify_corner_items(items, room_width=8.0, room_depth=8.0)
            for item in corner_items:
                # Round to 2 decimal places to group near-identical values.
                all_rotations.add(round(item["rotation"], 2))

        if not all_rotations:
            pytest.skip("No corner items found across seeds.")

        assert len(all_rotations) > 1, (
            f"All corner items have the same rotation ({all_rotations}). "
            "Corner items likely use a hardcoded rotation instead of computing "
            "direction toward room center."
        )


def _classify_corner_items(
    items: list[dict], room_width: float, room_depth: float, threshold: float = 2.5
) -> list[dict]:
    """Return items placed in the corner zone of the room.

    A corner zone is defined as within `threshold` meters of any room corner.
    """
    corners = [
        (0.0, 0.0),
        (room_width, 0.0),
        (0.0, room_depth),
        (room_width, room_depth),
    ]
    result = []
    for item in items:
        x, y, _ = item["position"]
        for cx, cy in corners:
            if math.sqrt((x - cx) ** 2 + (y - cy) ** 2) < threshold:
                result.append(item)
                break
    return result


# ---------------------------------------------------------------------------
# Test 4 — settlement_generator._furnish_interior wall rotations
# ---------------------------------------------------------------------------

class TestSettlementFurnishWallRotations:
    """_furnish_interior wall placements must face the room interior."""

    def _run_furnish(
        self, room_type: str, rx_min: float, ry_min: float, rx_max: float, ry_max: float
    ) -> list[dict]:
        from blender_addon.handlers.settlement_generator import _furnish_interior

        rng = random.Random(17)
        room_bounds = {"min": (rx_min, ry_min), "max": (rx_max, ry_max)}
        return _furnish_interior(rng, room_type, room_bounds)

    def _check_all_items_face_center(
        self,
        items: list[dict],
        rx_min: float,
        ry_min: float,
        rx_max: float,
        ry_max: float,
        label: str,
    ) -> list[str]:
        center_x = (rx_min + rx_max) / 2.0
        center_y = (ry_min + ry_max) / 2.0

        failures = []
        for item in items:
            if "rotation" not in item:
                continue
            rot = item["rotation"]
            pos = item.get("position", (0.0, 0.0))
            if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                ix, iy = float(pos[0]), float(pos[1])
            else:
                continue

            fwd = _forward_vector(rot)
            d2c = _dir_to_center(ix, iy, center_x, center_y)
            # Items at exact center have no meaningful facing direction — skip.
            if abs(d2c[0]) < 0.01 and abs(d2c[1]) < 0.01:
                continue
            dot = _dot2(fwd, d2c)
            if dot <= 0.0:
                failures.append(
                    f"[{label}] '{item['type']}' at ({ix:.3f},{iy:.3f}) "
                    f"rot={rot:.4f} dot={dot:.4f}"
                )
        return failures

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_bedroom_wall_items_face_interior(self):
        """Bedroom wall items from _furnish_interior must face the room center."""
        items = self._run_furnish("bedroom", 0.0, 0.0, 8.0, 8.0)
        assert items, "No furniture placed in bedroom — precondition failed."
        failures = self._check_all_items_face_center(
            items, 0.0, 0.0, 8.0, 8.0, "bedroom"
        )
        assert not failures, (
            "Bedroom wall items face away from room center (rotation bug):\n"
            + "\n".join(failures)
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_kitchen_wall_items_face_interior(self):
        """Kitchen wall items from _furnish_interior must face the room center."""
        items = self._run_furnish("kitchen", 2.0, 3.0, 10.0, 11.0)
        assert items, "No furniture placed in kitchen — precondition failed."
        failures = self._check_all_items_face_center(
            items, 2.0, 3.0, 10.0, 11.0, "kitchen"
        )
        assert not failures, (
            "Kitchen wall items face away from room center (rotation bug):\n"
            + "\n".join(failures)
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_smithy_wall_items_face_interior(self):
        """Smithy wall items from _furnish_interior must face the room center."""
        items = self._run_furnish("smithy", 0.0, 0.0, 10.0, 12.0)
        assert items, "No furniture placed in smithy — precondition failed."
        failures = self._check_all_items_face_center(
            items, 0.0, 0.0, 10.0, 12.0, "smithy"
        )
        assert not failures, (
            "Smithy wall items face away from room center (rotation bug):\n"
            + "\n".join(failures)
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_multiple_seeds_all_walls_face_interior(self):
        """Multiple seeds and room types must all produce inward-facing wall items."""
        room_configs = [
            ("bedroom", 0.0, 0.0, 8.0, 8.0),
            ("kitchen", 0.0, 0.0, 9.0, 9.0),
            ("storage", 0.0, 0.0, 6.0, 7.0),
        ]
        from blender_addon.handlers.settlement_generator import _furnish_interior

        all_failures = []
        for room_type, rx_min, ry_min, rx_max, ry_max in room_configs:
            for seed in range(5):
                rng = random.Random(seed)
                room_bounds = {"min": (rx_min, ry_min), "max": (rx_max, ry_max)}
                items = _furnish_interior(rng, room_type, room_bounds)
                failures = self._check_all_items_face_center(
                    items, rx_min, ry_min, rx_max, ry_max,
                    f"{room_type} seed={seed}"
                )
                all_failures.extend(failures)

        assert not all_failures, (
            f"{len(all_failures)} wall items face away from room center:\n"
            + "\n".join(all_failures[:20])
            + (f"\n... and {len(all_failures) - 20} more" if len(all_failures) > 20 else "")
        )

    @pytest.mark.xfail(reason="INT-001/INT-002: 180° rotation bug, fix in Phase 7", strict=True)
    def test_north_wall_item_rotation(self):
        """Item on the north wall (high Y) must face -Y (toward room interior).

        North wall placement in settlement_generator uses rot=0.0.
        In Blender, rot=0.0 gives forward=(0,-1) which is -Y.
        For a room where north is at the top (high Y), -Y points toward
        room interior from a north-wall-adjacent item.  This asserts the
        invariant directly so a future refactor cannot break it silently.
        """
        from blender_addon.handlers.settlement_generator import _furnish_interior

        # Use a deterministic seed that reliably places something on north wall.
        rng = random.Random(0)
        room_bounds = {"min": (0.0, 0.0), "max": (10.0, 10.0)}
        items = _furnish_interior(rng, "bedroom", room_bounds)

        # Find items near the north wall (y close to ry_max=10.0).
        north_items = [
            i for i in items
            if isinstance(i.get("position"), (list, tuple))
            and float(i["position"][1]) > 7.0  # within 3m of north wall
        ]

        if not north_items:
            pytest.skip("No items placed near north wall with seed=0.")

        for item in north_items:
            rot = item["rotation"]
            fwd = _forward_vector(rot)
            # From near y=10, room center y=5, direction to center is (0, -1).
            # Forward vector must have negative Y component.
            assert fwd[1] < 0.0, (
                f"North-wall item '{item['type']}' rot={rot:.4f} "
                f"has forward=({fwd[0]:.3f},{fwd[1]:.3f}), "
                f"expected fwd.y < 0 (facing toward room interior)"
            )
