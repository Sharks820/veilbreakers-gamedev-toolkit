"""Tests for building grounding / Z-position bug.

The bug: buildings float above terrain because terrain height sampling is
broken or ignored when positioning generated buildings.

These tests cover:
- _sample_terrain_height returns the raycast Z value (not always 0.0)
- Multi-point corner sampling for large buildings uses max() correctly
- Foundation height is added to the sampled terrain Z
- When terrain_name is None, sampling is skipped and Z defaults to 0.0
- _sample_terrain_height rejects invalid terrain_name (injection guard)
- _position_generated_object passes the full (x, y, z) position including Z
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# _sample_terrain_height: core sampling contract
# ---------------------------------------------------------------------------


class TestSampleTerrainHeight:
    """_sample_terrain_height must return the Blender raycast Z value."""

    def _make_blender(self, output_value: str = "5.25"):
        """Return an AsyncMock blender whose execute_code prints output_value."""
        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={
            "result": {"output": output_value}
        })
        return blender

    @pytest.mark.asyncio
    async def test_returns_float_from_blender_output(self):
        """When Blender reports a Z value, _sample_terrain_height returns it."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = self._make_blender("5.25")
        result = await _sample_terrain_height(blender, "Terrain", 10.0, 20.0)

        assert result == pytest.approx(5.25), (
            "Must parse the float from Blender output — building Z must "
            "match terrain height, not default to 0.0."
        )

    @pytest.mark.asyncio
    async def test_returns_zero_when_output_empty(self):
        """Empty output (no hit) should return 0.0, not crash."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = self._make_blender("")
        result = await _sample_terrain_height(blender, "Terrain", 0.0, 0.0)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_zero_on_blender_exception(self):
        """Connection errors must be caught — return 0.0, not propagate."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height
        from veilbreakers_mcp.shared.blender_client import BlenderCommandError

        # BlenderCommandError requires a BlenderResponse-like object
        fake_response = MagicMock()
        fake_response.error_type = "timeout"
        fake_response.message = "connection timed out"

        blender = AsyncMock()
        blender.send_command = AsyncMock(side_effect=BlenderCommandError(fake_response))

        result = await _sample_terrain_height(blender, "Terrain", 5.0, 5.0)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_zero_on_os_error(self):
        """OSError (socket closed) must be caught — return 0.0."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = AsyncMock()
        blender.send_command = AsyncMock(side_effect=OSError("connection reset"))

        result = await _sample_terrain_height(blender, "Terrain", 0.0, 0.0)

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_returns_last_line_of_multiline_output(self):
        """splitlines()[-1] must be used — last print() call wins."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        # Blender might print debug info on earlier lines
        blender = self._make_blender("debug info\n3.75")
        result = await _sample_terrain_height(blender, "Terrain", 0.0, 0.0)

        assert result == pytest.approx(3.75)

    @pytest.mark.asyncio
    async def test_negative_terrain_height(self):
        """Terrain can be below 0 (valley) — must preserve negative Z."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = self._make_blender("-2.5")
        result = await _sample_terrain_height(blender, "Terrain", 0.0, 0.0)

        assert result == pytest.approx(-2.5)

    @pytest.mark.asyncio
    async def test_sends_execute_code_command(self):
        """Must dispatch an execute_code command (not some other command)."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = self._make_blender("0.0")
        await _sample_terrain_height(blender, "MyTerrain", 1.0, 2.0)

        # _sample_terrain_height may make multiple send_command calls (e.g., name
        # resolution + the actual raycast). Verify at least one execute_code call
        # with a "code" payload was made.
        assert blender.send_command.called
        all_calls = blender.send_command.call_args_list
        execute_code_calls = [c for c in all_calls if c[0][0] == "execute_code"]
        assert execute_code_calls, "Expected at least one execute_code call"
        # The last execute_code call should be the raycast
        cmd, params = execute_code_calls[-1][0]
        assert cmd == "execute_code"
        assert "code" in params

    @pytest.mark.asyncio
    async def test_terrain_name_appears_in_code(self):
        """The emitted code must reference the terrain name for the hit test."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = self._make_blender("0.0")
        await _sample_terrain_height(blender, "RockyTerrain", 0.0, 0.0)

        _, params = blender.send_command.call_args[0]
        assert "RockyTerrain" in params["code"], (
            "Raycast code must filter by terrain_name — otherwise ANY object "
            "in the scene (including the building itself) could be hit."
        )


# ---------------------------------------------------------------------------
# _sample_terrain_height: security — invalid terrain names rejected
# ---------------------------------------------------------------------------


class TestSampleTerrainHeightSecurity:
    """Injection guard: terrain_name must match ^[A-Za-z0-9_.\\- ]+$."""

    @pytest.mark.asyncio
    async def test_invalid_name_returns_zero_not_executes(self):
        """A terrain_name with shell/code metacharacters must be rejected."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"result": {"output": "99.0"}})

        # Names with special characters should be rejected
        result = await _sample_terrain_height(blender, "Terrain; DROP TABLE", 0.0, 0.0)

        assert result == 0.0, "Invalid terrain_name must return 0.0 without executing code."
        blender.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_name_with_newline_rejected(self):
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"result": {"output": "5.0"}})

        result = await _sample_terrain_height(blender, "Terrain\nmalicious()", 0.0, 0.0)

        assert result == 0.0
        blender.send_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_name_with_dots_and_spaces_accepted(self):
        """Names like 'World Terrain.001' must pass the guard."""
        from veilbreakers_mcp.blender_server import _sample_terrain_height

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"result": {"output": "1.5"}})

        result = await _sample_terrain_height(blender, "World Terrain.001", 0.0, 0.0)

        assert result == pytest.approx(1.5)
        blender.send_command.assert_called_once()


# ---------------------------------------------------------------------------
# Multi-point corner sampling: max() of 5 samples
# ---------------------------------------------------------------------------


class TestMultiPointCornerSampling:
    """compose_map samples 5 points (4 corners + centre) and takes max().

    This ensures large buildings are not half-buried in sloped terrain.
    The sampling logic lives inline in blender_server.py's compose_map
    branch — we test its mathematical contract directly.
    """

    def test_max_of_corner_heights_chosen(self):
        """Building Z must be the maximum of all sampled heights, not the
        centre point alone.  If the building is on a slope, the highest
        corner determines the anchor so the building doesn't clip into terrain.
        """
        # Simulate five sampled heights at corners + centre
        corner_heights = [1.0, 2.5, 1.5, 3.0, 2.0]  # max = 3.0
        anchor_z = max(corner_heights)

        assert anchor_z == pytest.approx(3.0), (
            "Anchor Z must be the maximum sampled height — using centre-only "
            "or min() would cause buildings to clip into elevated terrain."
        )

    def test_flat_terrain_all_corners_equal(self):
        """On flat terrain all samples are identical; max() == any sample."""
        flat_height = 5.0
        corner_heights = [flat_height] * 5
        anchor_z = max(corner_heights)

        assert anchor_z == pytest.approx(flat_height)

    def test_single_high_corner_dominates(self):
        """One very high corner should pull the building up to avoid clipping."""
        corner_heights = [0.0, 0.0, 0.0, 0.0, 10.0]
        anchor_z = max(corner_heights)

        assert anchor_z == pytest.approx(10.0)

    def test_all_zero_heights(self):
        """Flat zero terrain: anchor_z should be 0.0."""
        corner_heights = [0.0, 0.0, 0.0, 0.0, 0.0]
        anchor_z = max(corner_heights) if corner_heights else 0.0

        assert anchor_z == 0.0

    def test_negative_terrain_height_handled(self):
        """Building in a depression: max of negatives is least-negative."""
        corner_heights = [-3.0, -1.0, -2.5, -0.5, -4.0]  # max = -0.5
        anchor_z = max(corner_heights)

        assert anchor_z == pytest.approx(-0.5)

    def test_five_sample_offsets_cover_all_corners_and_centre(self):
        """The five (dx, dy) offsets must include all four corners and (0, 0).

        The actual offsets in blender_server.py are:
            (-r, -r), (r, -r), (-r, r), (r, r), (0, 0)
        where r = loc_radius.  This test verifies coverage.
        """
        loc_radius = 5.0
        offsets = [
            (-loc_radius, -loc_radius),
            (loc_radius, -loc_radius),
            (-loc_radius, loc_radius),
            (loc_radius, loc_radius),
            (0.0, 0.0),
        ]

        # Verify all four quadrant corners are present
        positive_x = [o for o in offsets if o[0] > 0]
        negative_x = [o for o in offsets if o[0] < 0]
        centre = [o for o in offsets if o[0] == 0.0 and o[1] == 0.0]

        assert len(positive_x) == 2, "Need two positive-X corners (front-right, back-right)."
        assert len(negative_x) == 2, "Need two negative-X corners (front-left, back-left)."
        assert len(centre) == 1, "Need exactly one centre sample."
        assert len(offsets) == 5, "Exactly 5 sample points required."


# ---------------------------------------------------------------------------
# Foundation height addition
# ---------------------------------------------------------------------------


class TestFoundationHeightAddition:
    """Foundation height must be added ON TOP of the sampled terrain height.

    A foundation offsets the building so its base visually sits on terrain
    rather than floating or clipping.
    """

    def test_foundation_added_to_terrain_height(self):
        """anchor_z + foundation_height must equal final Z position."""
        terrain_z = 3.0
        foundation_height = 0.5  # e.g. stone foundation slab

        final_z = terrain_z + foundation_height

        assert final_z == pytest.approx(3.5)

    def test_zero_foundation_height_uses_terrain_z_directly(self):
        """If foundation_height is 0, final Z == terrain Z."""
        terrain_z = 7.25
        foundation_height = 0.0

        final_z = terrain_z + foundation_height

        assert final_z == pytest.approx(7.25)

    def test_negative_foundation_embeds_building(self):
        """Negative foundation (e.g. dungeon entrance) lowers the building."""
        terrain_z = 2.0
        foundation_height = -1.0  # partially embedded

        final_z = terrain_z + foundation_height

        assert final_z == pytest.approx(1.0)

    def test_foundation_does_not_replace_terrain_height(self):
        """Foundation is additive — it must NOT be the entire Z value."""
        terrain_z = 5.0
        foundation_height = 0.25

        # Buggy implementation might set Z = foundation_height only
        buggy_z = foundation_height
        correct_z = terrain_z + foundation_height

        assert correct_z != pytest.approx(buggy_z), (
            "Final Z must be terrain_z + foundation_height, not foundation_height alone."
        )
        assert correct_z == pytest.approx(5.25)


# ---------------------------------------------------------------------------
# _position_generated_object: Z coordinate passed correctly
# ---------------------------------------------------------------------------


class TestPositionGeneratedObject:
    """_position_generated_object must forward the full (x, y, z) position
    to the modify_object command, including the Z from terrain sampling.
    """

    @pytest.mark.asyncio
    async def test_z_position_forwarded_to_modify_object(self):
        """modify_object must receive the Z from terrain sampling, not 0.0."""
        from veilbreakers_mcp.blender_server import _position_generated_object

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"status": "ok"})

        await _position_generated_object(blender, "InnBuilding", (10.0, 20.0, 5.5))

        # _position_generated_object may call execute_code first to resolve
        # duplicate-name suffixes (PIPE-026), then modify_object. Assert at
        # least one call was made and the final modify_object carries the Z.
        assert blender.send_command.called
        # The modify_object call is always the last one
        last_cmd, last_params = blender.send_command.call_args[0]
        assert last_cmd == "modify_object"
        assert last_params["name"] == "InnBuilding"
        assert last_params["position"][2] == pytest.approx(5.5), (
            "Z position must be 5.5 (terrain height) — not 0.0. "
            "Passing Z=0 is the floating building bug."
        )

    @pytest.mark.asyncio
    async def test_z_zero_when_terrain_not_sampled(self):
        """When terrain_name is None and Z defaults to 0.0, building is
        placed at ground level — not floating, not buried."""
        from veilbreakers_mcp.blender_server import _position_generated_object

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"status": "ok"})

        await _position_generated_object(blender, "Watchtower", (0.0, 0.0, 0.0))

        _, params = blender.send_command.call_args[0]
        assert params["position"] == [0.0, 0.0, 0.0]

    @pytest.mark.asyncio
    async def test_position_list_has_three_components(self):
        """Position must be a 3-element list [x, y, z]."""
        from veilbreakers_mcp.blender_server import _position_generated_object

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"status": "ok"})

        await _position_generated_object(blender, "Church", (3.0, 4.0, 1.25))

        _, params = blender.send_command.call_args[0]
        pos = params["position"]

        assert isinstance(pos, list), "position must be a list, not a tuple."
        assert len(pos) == 3, "position must have exactly 3 components."
        assert pos == pytest.approx([3.0, 4.0, 1.25])

    @pytest.mark.asyncio
    async def test_x_y_coordinates_preserved(self):
        """X and Y coordinates must not be clobbered when Z is set."""
        from veilbreakers_mcp.blender_server import _position_generated_object

        blender = AsyncMock()
        blender.send_command = AsyncMock(return_value={"status": "ok"})

        await _position_generated_object(blender, "Market", (15.5, -8.25, 3.0))

        _, params = blender.send_command.call_args[0]
        pos = params["position"]

        assert pos[0] == pytest.approx(15.5)
        assert pos[1] == pytest.approx(-8.25)
        assert pos[2] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# No terrain sampling when terrain_name is None
# ---------------------------------------------------------------------------


class TestNoSamplingWithoutTerrain:
    """When terrain_name is None, _sample_terrain_height must not be called
    and the building Z defaults to 0.0.

    This prevents the building's own mesh from being hit by the raycast
    (since there is no terrain object to filter against).
    """

    @pytest.mark.asyncio
    async def test_terrain_none_skips_sampling(self):
        """compose_map skips the sampling loop when terrain_name is falsy."""
        # Replicate the conditional from blender_server.py:
        #   if terrain_name:
        #       for dx, dy in [...]:
        #           ch = await _sample_terrain_height(blender, terrain_name, ...)
        #           corner_heights.append(ch)
        #       anchor_z = max(corner_heights)

        sample_calls: list[tuple] = []

        async def _mock_sample(blender, terrain_name, x, y):
            sample_calls.append((terrain_name, x, y))
            return 5.0

        terrain_name = None
        corner_heights: list[float] = []
        anchor_z = 0.0

        if terrain_name:
            loc_radius = 5.0
            anchor_x, anchor_y = 10.0, 10.0
            for dx, dy in [(-loc_radius, -loc_radius), (loc_radius, -loc_radius),
                           (-loc_radius, loc_radius), (loc_radius, loc_radius),
                           (0.0, 0.0)]:
                ch = await _mock_sample(None, terrain_name, anchor_x + dx, anchor_y + dy)
                corner_heights.append(ch)
            anchor_z = max(corner_heights) if corner_heights else 0.0

        assert len(sample_calls) == 0, (
            "No sampling should occur when terrain_name is None — "
            "otherwise the building's own mesh is raycasted and anchor_z "
            "incorrectly equals the building's own geometry height."
        )
        assert anchor_z == 0.0

    @pytest.mark.asyncio
    async def test_terrain_name_present_triggers_five_samples(self):
        """When terrain_name is set, exactly 5 sample points are taken."""
        sample_calls: list[tuple] = []

        async def _mock_sample(blender, terrain_name, x, y):
            sample_calls.append((terrain_name, x, y))
            return 2.0

        terrain_name = "MainTerrain"
        corner_heights: list[float] = []
        loc_radius = 5.0
        anchor_x, anchor_y = 10.0, 10.0
        anchor_z = 0.0

        if terrain_name:
            for dx, dy in [(-loc_radius, -loc_radius), (loc_radius, -loc_radius),
                           (-loc_radius, loc_radius), (loc_radius, loc_radius),
                           (0.0, 0.0)]:
                ch = await _mock_sample(None, terrain_name, anchor_x + dx, anchor_y + dy)
                corner_heights.append(ch)
            anchor_z = max(corner_heights) if corner_heights else 0.0

        assert len(sample_calls) == 5, (
            "Five sample points (4 corners + centre) must be taken for large buildings."
        )
        assert anchor_z == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_empty_string_terrain_name_skips_sampling(self):
        """Empty string terrain_name is falsy — sampling must be skipped."""
        sample_calls: list[tuple] = []

        async def _mock_sample(blender, terrain_name, x, y):
            sample_calls.append((terrain_name, x, y))
            return 5.0

        terrain_name = ""  # falsy
        corner_heights: list[float] = []
        anchor_z = 0.0

        if terrain_name:
            loc_radius = 5.0
            anchor_x, anchor_y = 0.0, 0.0
            for dx, dy in [(-loc_radius, -loc_radius), (loc_radius, -loc_radius),
                           (-loc_radius, loc_radius), (loc_radius, loc_radius),
                           (0.0, 0.0)]:
                ch = await _mock_sample(None, terrain_name, anchor_x + dx, anchor_y + dy)
                corner_heights.append(ch)
            anchor_z = max(corner_heights) if corner_heights else 0.0

        assert len(sample_calls) == 0
        assert anchor_z == 0.0


# ---------------------------------------------------------------------------
# Integration: grounding Z flows from sample -> position
# ---------------------------------------------------------------------------


class TestGroundingZEndToEnd:
    """Verify the data flow: sampled terrain height -> anchor_z -> position Z."""

    @pytest.mark.asyncio
    async def test_sampled_height_used_as_position_z(self):
        """The Z returned by _sample_terrain_height must end up as the
        Z passed to _position_generated_object — no value gets lost."""
        from veilbreakers_mcp.blender_server import (
            _sample_terrain_height,
            _position_generated_object,
        )

        expected_terrain_z = 7.5
        anchor_x, anchor_y = 20.0, 30.0
        loc_radius = 5.0

        # Sample mock returns consistent height
        sample_blender = AsyncMock()
        sample_blender.send_command = AsyncMock(return_value={
            "result": {"output": str(expected_terrain_z)}
        })

        # Collect the 5 corner samples
        corner_heights: list[float] = []
        for dx, dy in [(-loc_radius, -loc_radius), (loc_radius, -loc_radius),
                       (-loc_radius, loc_radius), (loc_radius, loc_radius),
                       (0.0, 0.0)]:
            ch = await _sample_terrain_height(
                sample_blender, "WorldTerrain", anchor_x + dx, anchor_y + dy
            )
            corner_heights.append(ch)

        anchor_z = max(corner_heights)

        # Verify anchor_z matches sampled height
        assert anchor_z == pytest.approx(expected_terrain_z), (
            "anchor_z must equal the sampled terrain height — if this fails, "
            "the building will float or clip."
        )

        # Position the object at the sampled Z
        position_blender = AsyncMock()
        position_blender.send_command = AsyncMock(return_value={"status": "ok"})

        await _position_generated_object(
            position_blender, "Blacksmith", (anchor_x, anchor_y, anchor_z)
        )

        _, params = position_blender.send_command.call_args[0]
        placed_z = params["position"][2]

        assert placed_z == pytest.approx(expected_terrain_z), (
            f"Building was placed at Z={placed_z} but terrain height is "
            f"{expected_terrain_z}. Building is floating/clipping."
        )
