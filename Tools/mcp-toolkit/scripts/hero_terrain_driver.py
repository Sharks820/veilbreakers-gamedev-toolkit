#!/usr/bin/env python
"""Build a hero terrain node step-by-step through the live Blender bridge.

This bypasses the monolithic ``compose_map`` transaction so terrain iteration can
focus on the actual weak spots: silhouette, river/basin grounding, and cave
integration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-blend", type=Path)
    return parser.parse_args()


async def _run(spec_path: Path, output_path: Path, save_blend: Path | None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    import veilbreakers_mcp.blender_server as bs
    from veilbreakers_mcp.blender_server import (
        _apply_hero_mountain_shaping,
        _blend_path_points_to_terminal_water_level,
        _build_location_generation_params,
        _map_point_to_world_xy,
        _normalize_validation_profiles,
        _position_generated_object,
        _retarget_cave_anchor_to_relief,
        _run_terrain_visual_gate,
        _sample_terrain_height,
        _sample_terrain_relief_profile,
        _shape_hero_cave_ridge,
        _stabilize_hero_terrain_patch,
        _temper_hero_peak_outliers,
    )
    from veilbreakers_mcp.shared.blender_client import BlenderConnection

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    blender = BlenderConnection(timeout=600)

    map_name = str(spec.get("name", "HeroTerrain"))
    terrain_cfg = dict(spec.get("terrain", {}) or {})
    water_cfg = dict(spec.get("water", {}) or {})
    locations = list(spec.get("locations", []) or [])

    terrain_name = f"{map_name}_Terrain"
    terrain_size = float(terrain_cfg.get("size", 320.0))
    terrain_resolution = int(terrain_cfg.get("resolution", 448))
    terrain_preset = str(terrain_cfg.get("preset", "hills"))
    terrain_location = tuple(terrain_cfg.get("location", (0.0, 0.0)))[:2]
    terrain_loc_3d = (
        float(terrain_location[0]),
        float(terrain_location[1]),
        0.0,
    )
    map_seed = int(spec.get("seed", 0))

    result: dict[str, Any] = {
        "status": "partial",
        "map_name": map_name,
        "steps_completed": [],
        "steps_failed": [],
        "warnings": [],
        "objects_created": [],
        "locations": [],
        "terrain_visual_verification": {},
    }

    def _flush() -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    def _step_ok(name: str) -> None:
        result["steps_completed"].append(name)
        _flush()

    def _step_fail(name: str, exc: Exception) -> None:
        result["steps_failed"].append({"step": name, "error": str(exc)})
        _flush()

    def _downsample_curve_points(points: list[list[float]], *, max_points: int = 12) -> list[list[float]]:
        if len(points) <= max_points:
            return [list(point[:3]) for point in points]
        chosen: list[list[float]] = []
        used: set[int] = set()
        for slot in range(max_points):
            raw_index = round(slot * (len(points) - 1) / max(max_points - 1, 1))
            index = max(0, min(int(raw_index), len(points) - 1))
            if index in used:
                continue
            used.add(index)
            chosen.append(list(points[index][:3]))
        if chosen[0] != list(points[0][:3]):
            chosen.insert(0, list(points[0][:3]))
        if chosen[-1] != list(points[-1][:3]):
            chosen.append(list(points[-1][:3]))
        return chosen

    async def _reproject_water_surface_from_bed(
        surface_points: list[list[float]],
        bed_points: list[list[float]],
        *,
        min_water_depth: float,
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Clamp river water back onto the terrain after extra deforms.

        ``env_carve_river`` returns a good first pass, but later spline deforms
        can leave the visible water floating above the re-shaped channel. Sample
        the final terrain bed and rebuild the visible water column from that.
        """
        count = min(len(surface_points), len(bed_points))
        if count <= 0:
            return (
                [list(point[:3]) for point in surface_points],
                [list(point[:3]) for point in bed_points],
            )

        conformed_surface: list[list[float]] = []
        conformed_bed: list[list[float]] = []
        prev_surface_z: float | None = None
        water_depth_floor = max(float(min_water_depth), 0.65)
        for index in range(count):
            sx, sy, sz = (float(v) for v in surface_points[index][:3])
            bx, by, bz = (float(v) for v in bed_points[index][:3])
            sampled_bed_z = float(await _sample_terrain_height(blender, terrain_name, bx, by))
            water_column = max(float(sz) - float(bz), water_depth_floor)
            surface_z = sampled_bed_z + water_column
            if prev_surface_z is not None:
                # Keep the river monotonically descending toward the basin.
                surface_z = min(surface_z, prev_surface_z - 0.02)
            conformed_bed.append([bx, by, sampled_bed_z])
            conformed_surface.append([sx, sy, surface_z])
            prev_surface_z = surface_z
        return conformed_surface, conformed_bed

    def _trim_curve_tail(
        points: list[list[float]],
        *,
        points_to_trim: int,
        fallback_tail: list[float] | None = None,
    ) -> list[list[float]]:
        """Remove the tail section of a river curve before it enters the lake."""
        if len(points) <= max(points_to_trim, 1):
            trimmed = [list(point[:3]) for point in points[:1]]
        else:
            trimmed = [list(point[:3]) for point in points[:-points_to_trim]]
        if fallback_tail is not None:
            tail = [float(fallback_tail[0]), float(fallback_tail[1]), float(fallback_tail[2])]
            if not trimmed or any(abs(trimmed[-1][idx] - tail[idx]) > 1e-5 for idx in range(3)):
                trimmed.append(tail)
        return trimmed

    planned_cave_candidates: list[tuple[float, float, float]] = []
    planned_cave_locations: list[dict[str, Any]] = []
    for loc in locations:
        if str(loc.get("type", "")).strip().lower() != "cave":
            continue
        position = loc.get("position") or loc.get("center") or [terrain_size * 0.25, 0.0]
        anchor_x, anchor_y = _map_point_to_world_xy(
            position,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
        )
        planned_cave_candidates.append((anchor_x, anchor_y, 0.0))
        planned_cave_locations.append(
            {
                "name": str(loc.get("name", "HeroCave")),
                "anchor": (anchor_x, anchor_y),
                "radius": float(loc.get("radius", 22.0)),
                "source": loc,
            }
        )

    try:
        await blender.send_command("clear_scene", {})
        _step_ok("scene_cleared")
    except Exception as exc:
        _step_fail("scene_cleared", exc)
        _flush()
        return 1

    try:
        terrain_params = {
            "name": terrain_name,
            "terrain_type": terrain_preset,
            "resolution": terrain_resolution,
            "height_scale": float(terrain_cfg.get("height_scale", 84.0)),
            "scale": terrain_size,
            "seed": map_seed,
            "erosion": "hydraulic" if terrain_cfg.get("erosion", True) else "none",
            "erosion_iterations": int(terrain_cfg.get("erosion_iterations", 10000)),
            "cliff_overlays": bool(terrain_cfg.get("cliff_overlays", False)),
            "use_controller": True,
            "object_location": list(terrain_loc_3d),
            "scene_read": {
                "timestamp": 0.0,
                "reviewer": "hero_terrain_driver",
                "cave_candidates": [list(c) for c in planned_cave_candidates],
            } if planned_cave_candidates else None,
        }
        terrain_result = await blender.send_command("env_generate_terrain", terrain_params)
        _step_ok("terrain_generated")
        result["objects_created"].append(terrain_name)
        await blender.send_command(
            "material_create_procedural",
            {
                "object_name": terrain_name,
                "material_key": "dirt" if terrain_preset == "hills" else "cliff_rock",
                "name": f"{terrain_name}_Review",
            },
        )
        _step_ok("terrain_review_material")
        hero_steps = await _apply_hero_mountain_shaping(
            blender,
            terrain_name=terrain_name,
            map_spec=spec,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
            terrain_preset=terrain_preset,
            height_scale=float(terrain_params["height_scale"]),
            cave_anchor=planned_cave_locations[0]["anchor"] if planned_cave_locations else None,
        )
        result["steps_completed"].extend(hero_steps)
        spike_cleanup = await _temper_hero_peak_outliers(
            blender,
            terrain_name,
            percentile=0.991,
            blend=0.78,
            prominence_threshold=max(float(terrain_params["height_scale"]) * 0.085, 5.2),
            passes=2,
        )
        if int(spike_cleanup.get("affected_vertices", 0)) > 0:
            result["steps_completed"].append("hero_peak_cleanup")
        _step_ok("hero_terrain_shaped")
    except Exception as exc:
        _step_fail("terrain", exc)
        _flush()
        return 1

    hero_cave_anchor_overrides: dict[str, dict[str, float]] = {}
    for planned in planned_cave_locations:
        cave_name = planned["name"]
        anchor_x, anchor_y = planned["anchor"]
        loc_radius = float(planned["radius"])
        entrance_width = float(planned["source"].get("entrance_width", 13.0))
        entrance_height = float(planned["source"].get("entrance_height", 9.0))
        try:
            retargeted = await _retarget_cave_anchor_to_relief(
                blender,
                terrain_name,
                anchor_x=float(anchor_x),
                anchor_y=float(anchor_y),
                terrain_size=terrain_size,
                terrain_location=terrain_location,
                search_radius=max(loc_radius * 0.72, entrance_width * 1.55, 12.0),
                sample_radius=max(entrance_width * 0.88, 7.5),
            )
            hero_cave_anchor_overrides[cave_name] = {
                "x": float(retargeted["x"]),
                "y": float(retargeted["y"]),
                "z": float(retargeted["z"]),
                "outward_x": float(retargeted.get("outward_x", 0.0)),
                "outward_y": float(retargeted.get("outward_y", 1.0)),
                "slope_drop": float(retargeted.get("slope_drop", 0.0)),
            }
            await _shape_hero_cave_ridge(
                blender,
                terrain_name,
                cave_name=cave_name,
                anchor_x=float(retargeted["x"]),
                anchor_y=float(retargeted["y"]),
                loc_radius=loc_radius,
                entrance_width=entrance_width,
                entrance_height=entrance_height,
                terrain_location=terrain_location,
            )
            terrace_center_x = float(retargeted["x"]) - float(retargeted.get("outward_x", 0.0)) * max(entrance_width * 0.72, 5.2)
            terrace_center_y = float(retargeted["y"]) - float(retargeted.get("outward_y", 1.0)) * max(entrance_width * 0.72, 5.2)
            await blender.send_command(
                "terrain_flatten_zone",
                {
                    "object_name": terrain_name,
                    "center_x": terrace_center_x,
                    "center_y": terrace_center_y,
                    "radius_x": max(entrance_width * 0.96, 6.4),
                    "radius_y": max(entrance_width * 0.74, 4.8),
                    "blend_distance": max(entrance_width * 0.88, 5.2),
                    "target_height": float(retargeted["z"]) - max(entrance_height * 0.06, 0.35),
                },
            )
            cave_spike_cleanup = await _temper_hero_peak_outliers(
                blender,
                terrain_name,
                percentile=0.993,
                blend=0.82,
                prominence_threshold=max(entrance_height * 0.66, 4.8),
                passes=2,
            )
            if int(cave_spike_cleanup.get("affected_vertices", 0)) > 0:
                result["steps_completed"].append(f"hero_cliff_cleanup_{cave_name}")
            _step_ok(f"hero_cliff_{cave_name}")
        except Exception as exc:
            _step_fail(f"hero_cliff_{cave_name}", exc)

    river_surfaces: list[dict[str, Any]] = []
    basin_center_world: tuple[float, float] | None = None
    basin_radius = float(water_cfg.get("basin_radius", 40.0))
    basin_depth = float(water_cfg.get("basin_depth", 12.0))
    basin_aspect_y = float(water_cfg.get("basin_aspect_y", 1.18))
    water_level = float(water_cfg.get("water_level", -24.0))

    for index, river in enumerate(water_cfg.get("rivers", []) or []):
        try:
            source = bs._map_point_to_terrain_cell(
                river.get("source", [0.0, terrain_size * 0.3]),
                terrain_size=terrain_size,
                resolution=terrain_resolution,
                terrain_location=terrain_location,
            )
            destination = bs._map_point_to_terrain_cell(
                river.get("destination", [0.0, -terrain_size * 0.3]),
                terrain_size=terrain_size,
                resolution=terrain_resolution,
                terrain_location=terrain_location,
            )
            waypoints = [
                list(
                    bs._map_point_to_terrain_cell(
                        point,
                        terrain_size=terrain_size,
                        resolution=terrain_resolution,
                        terrain_location=terrain_location,
                    )
                )
                for point in river.get("waypoints", []) or []
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            river_result = await blender.send_command(
                "env_carve_river",
                {
                    "terrain_name": terrain_name,
                    "source": list(source),
                    "destination": list(destination),
                    "waypoints": waypoints,
                    "width": max(3, int(round(float(river.get("width", 10.0))))),
                    "depth": float(river.get("depth", 8.0)),
                    "seed": map_seed + index,
                },
            )
            _step_ok(f"river_{index}")
            river_path_points = list(river_result.get("path_points", []) or [])
            river_bed_points = list(river_result.get("bed_points", []) or [])
            if len(river_path_points) >= 2:
                smoothing_curve = _downsample_curve_points(river_bed_points or river_path_points, max_points=14)
                river_width = float(river.get("width", 10.0))
                river_depth = float(river.get("depth", 8.0))
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": smoothing_curve,
                        "mode": "flatten",
                        "depth": 0.0,
                        "width": max(river_width * 1.10, 10.0),
                        "falloff": 0.84,
                        "samples_per_segment": 12,
                    },
                )
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": smoothing_curve,
                        "mode": "carve",
                        "depth": max(river_depth * 0.44, 2.2),
                        "width": max(river_width * 1.34, 11.0),
                        "falloff": 0.88,
                        "samples_per_segment": 12,
                    },
                )
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": smoothing_curve,
                        "mode": "smooth",
                        "depth": 0.0,
                        "width": max(river_width * 2.10, 18.0),
                        "falloff": 0.97,
                        "samples_per_segment": 12,
                    },
                )
                conformed_surface, conformed_bed = await _reproject_water_surface_from_bed(
                    river_path_points,
                    river_bed_points or river_path_points,
                    min_water_depth=max(river_depth * 0.42, 0.9),
                )
                river_surfaces.append(
                    {
                        "name": f"{map_name}_River_{index}",
                        "path_points": conformed_surface,
                        "bed_points": conformed_bed,
                        "width": max(river_width * 0.90, 6.9),
                        "depth": river_depth,
                    }
                )
        except Exception as exc:
            _step_fail(f"river_{index}", exc)

    try:
        basin_center_raw = water_cfg.get("basin_center", [0.0, -terrain_size * 0.32])
        basin_center_world = _map_point_to_world_xy(
            basin_center_raw,
            terrain_size=terrain_size,
            terrain_location=terrain_location,
        )
        await blender.send_command(
            "env_carve_water_basin",
            {
                "terrain_name": terrain_name,
                "center": list(basin_center_world),
                "water_level": water_level,
                "radius": basin_radius,
                "depth": basin_depth,
                "shore_width": float(water_cfg.get("shore_width", basin_radius * 1.5)),
                "aspect_y": basin_aspect_y,
                "containment_rim": True,
                "containment_rim_height": max(basin_depth * 0.46, 3.8),
            },
        )
        _step_ok("water_basin")

        rim_angles = [math.tau * i / 12.0 for i in range(12)]
        rim_points = [
            [
                basin_center_world[0] + math.cos(angle) * basin_radius * 0.98,
                basin_center_world[1] + math.sin(angle) * basin_radius * basin_aspect_y * 0.98,
                water_level + max(basin_depth * 0.38, 2.2),
            ]
            for angle in rim_angles
        ]
        rim_points.append(rim_points[0])
        await blender.send_command(
            "terrain_spline_deform",
            {
                "object_name": terrain_name,
                "spline_points": rim_points,
                "mode": "raise",
                "depth": max(basin_depth * 0.52, 3.4),
                "width": max(basin_radius * 0.30, 7.2),
                "falloff": 0.82,
                "samples_per_segment": 12,
            },
        )
        await blender.send_command(
            "terrain_spline_deform",
            {
                "object_name": terrain_name,
                "spline_points": rim_points,
                "mode": "smooth",
                "depth": 0.0,
                "width": max(basin_radius * 0.40, 10.0),
                "falloff": 0.96,
                "samples_per_segment": 12,
            },
        )

        for river_surface in river_surfaces:
            path_points = _blend_path_points_to_terminal_water_level(
                river_surface["path_points"],
                water_level,
            )
            bed_points = _blend_path_points_to_terminal_water_level(
                list(river_surface.get("bed_points", []) or river_surface["path_points"]),
                water_level - max(basin_depth * 0.32, 2.2),
            )
            if len(path_points) >= 2:
                tail_dx = float(path_points[-1][0]) - float(path_points[-2][0])
                tail_dy = float(path_points[-1][1]) - float(path_points[-2][1])
            else:
                tail_dx, tail_dy = 0.0, -1.0
            tail_len = max(math.hypot(tail_dx, tail_dy), 1e-6)
            flow_dx = tail_dx / tail_len
            flow_dy = tail_dy / tail_len
            basin_a = basin_radius * 0.92
            basin_b = basin_radius * basin_aspect_y * 0.92
            rim_scale = 1.0 / math.sqrt(
                (flow_dx * flow_dx) / max(basin_a * basin_a, 1e-6)
                + (flow_dy * flow_dy) / max(basin_b * basin_b, 1e-6)
            )
            basin_entry_x = basin_center_world[0] - flow_dx * rim_scale
            basin_entry_y = basin_center_world[1] - flow_dy * rim_scale
            connector_start = path_points[max(0, len(path_points) - 4)]
            basin_entry_bed = water_level - max(basin_depth * 0.24, 1.6)
            river_bank_join = [
                basin_entry_x - flow_dx * max(float(river_surface["width"]) * 0.72, 4.0),
                basin_entry_y - flow_dy * max(float(river_surface["width"]) * 0.72, 4.0),
                water_level + 0.02,
            ]
            path_points = (
                path_points[: max(0, len(path_points) - 4)]
                + [
                    connector_start,
                    [
                        connector_start[0] * 0.42 + basin_entry_x * 0.58,
                        connector_start[1] * 0.42 + basin_entry_y * 0.58,
                        connector_start[2] * 0.38 + water_level * 0.62,
                    ],
                    [
                        path_points[-1][0] * 0.26 + basin_entry_x * 0.74,
                        path_points[-1][1] * 0.26 + basin_entry_y * 0.74,
                        path_points[-1][2] * 0.24 + water_level * 0.76,
                    ],
                    [basin_entry_x, basin_entry_y, water_level],
                ]
            )
            bed_connector_start = bed_points[max(0, len(bed_points) - 4)]
            inlet_curve = (
                bed_points[: max(0, len(bed_points) - 4)]
                + [
                    bed_connector_start,
                    [
                        bed_connector_start[0] * 0.46 + basin_entry_x * 0.54,
                        bed_connector_start[1] * 0.46 + basin_entry_y * 0.54,
                        bed_connector_start[2] * 0.58 + basin_entry_bed * 0.42,
                    ],
                    [
                        bed_points[-1][0] * 0.24 + basin_entry_x * 0.76,
                        bed_points[-1][1] * 0.24 + basin_entry_y * 0.76,
                        bed_points[-1][2] * 0.34 + basin_entry_bed * 0.66,
                    ],
                    [basin_entry_x, basin_entry_y, basin_entry_bed],
                ]
            )
            path_points, bed_points = await _reproject_water_surface_from_bed(
                path_points,
                bed_points,
                min_water_depth=max(float(river_surface.get("depth", 6.0)) * 0.36, 0.8),
            )
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": inlet_curve[-6:],
                    "mode": "flatten",
                    "width": max(float(river_surface["width"]) * 1.72, 11.0),
                    "depth": 0.0,
                    "falloff": 0.90,
                    "samples_per_segment": 12,
                },
            )
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": inlet_curve[-6:],
                    "mode": "carve",
                    "depth": max(basin_depth * 0.18, float(river_surface["width"]) * 0.24, 1.4),
                    "width": max(float(river_surface["width"]) * 1.84, 12.0),
                    "falloff": 0.90,
                    "samples_per_segment": 12,
                },
            )
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": inlet_curve[-6:],
                    "mode": "smooth",
                    "depth": 0.0,
                    "width": max(float(river_surface["width"]) * 2.48, 16.0),
                    "falloff": 0.98,
                    "samples_per_segment": 12,
                },
            )
            visible_river_points = _trim_curve_tail(
                path_points,
                points_to_trim=3,
                fallback_tail=river_bank_join,
            )
            await blender.send_command(
                "env_create_water",
                {
                    "name": river_surface["name"],
                    "terrain_name": terrain_name,
                    "path_points": visible_river_points,
                    "water_level": water_level,
                    "width": float(river_surface["width"]),
                    "cross_sections": 18,
                    "preview_fast": False,
                    "surface_only": True,
                },
            )
            _step_ok(river_surface["name"])
            result["objects_created"].append(river_surface["name"])

        await blender.send_command(
            "env_create_water",
            {
                "name": f"{map_name}_Water",
                "terrain_name": terrain_name,
                "water_level": water_level,
                "preview_fast": False,
                "mask_center": list(basin_center_world),
                "mask_radius": basin_radius * 0.82,
                "mask_aspect_y": basin_aspect_y,
                "surface_only": True,
            },
        )
        _step_ok("water_plane")
        result["objects_created"].append(f"{map_name}_Water")
        water_spike_cleanup = await _temper_hero_peak_outliers(
            blender,
            terrain_name,
            percentile=0.994,
            blend=0.84,
            prominence_threshold=max(basin_depth * 0.45, 5.0),
            passes=1,
        )
        if int(water_spike_cleanup.get("affected_vertices", 0)) > 0:
            result["steps_completed"].append("water_edge_cleanup")
    except Exception as exc:
        _step_fail("water", exc)

    for index, planned in enumerate(planned_cave_locations):
        loc = planned["source"]
        cave_name = planned["name"]
        try:
            loc_radius = float(planned["radius"])
            entrance_width = float(loc.get("entrance_width", 13.0))
            entrance_height = float(loc.get("entrance_height", 9.2))
            entrance_depth = float(loc.get("entrance_depth", 20.0))
            override = hero_cave_anchor_overrides.get(cave_name)
            anchor_x = float(override["x"] if override else planned["anchor"][0])
            anchor_y = float(override["y"] if override else planned["anchor"][1])
            anchor_z = float(override["z"] if override else 0.0)

            relief_profile = await _sample_terrain_relief_profile(
                blender,
                terrain_name,
                anchor_x,
                anchor_y,
                radius=max(entrance_width * 0.78, loc_radius * 0.54, 9.0),
                sample_count=8,
                fallback_vector=(terrain_location[0] - anchor_x, terrain_location[1] - anchor_y),
            )
            if override and abs(float(override.get("outward_x", 0.0))) + abs(float(override.get("outward_y", 0.0))) > 1e-6:
                face_x = float(override.get("outward_x", 0.0))
                face_y = float(override.get("outward_y", 1.0))
            else:
                uphill_x, uphill_y = relief_profile["uphill_vector"]
                face_x, face_y = -uphill_x, -uphill_y
            face_len = max(math.hypot(face_x, face_y), 1e-6)
            face_x /= face_len
            face_y /= face_len
            tunnel_x, tunnel_y = -face_x, -face_y
            perp_x, perp_y = -tunnel_y, tunnel_x
            entrance_rotation_z = math.atan2(-face_x, face_y)
            anchor_z = await _sample_terrain_height(blender, terrain_name, anchor_x, anchor_y)
            cave_material_key = str(
                loc.get(
                    "material_key",
                    "wet_rock" if str(terrain_cfg.get("preset", "")).strip().lower() in {"coastal", "swamp"} else "cliff_rock",
                )
            )
            chamber_material_key = str(loc.get("chamber_material_key", "wet_rock"))

            terrace_center_x = anchor_x - face_x * max(entrance_width * 0.92, 6.0)
            terrace_center_y = anchor_y - face_y * max(entrance_width * 0.92, 6.0)
            await blender.send_command(
                "terrain_flatten_zone",
                {
                    "object_name": terrain_name,
                    "center_x": terrace_center_x,
                    "center_y": terrace_center_y,
                    "radius_x": max(entrance_width * 1.42, 9.0),
                    "radius_y": max(entrance_width * 0.98, 6.4),
                    "blend_distance": max(entrance_width * 1.26, 7.0),
                    "target_height": anchor_z - max(entrance_height * 0.10, 0.45),
                },
            )

            tunnel_curve = [
                [
                    anchor_x - face_x * max(entrance_width * 1.36, 7.2),
                    anchor_y - face_y * max(entrance_width * 1.36, 7.2),
                    anchor_z - 0.16,
                ],
                [anchor_x, anchor_y, anchor_z - 0.42],
                [
                    anchor_x + tunnel_x * max(entrance_depth * 0.34, 4.8),
                    anchor_y + tunnel_y * max(entrance_depth * 0.34, 4.8),
                    anchor_z - max(entrance_height * 0.28, 1.4),
                ],
                [
                    anchor_x + tunnel_x * max(entrance_depth * 0.74, 8.2),
                    anchor_y + tunnel_y * max(entrance_depth * 0.74, 8.2),
                    anchor_z - max(entrance_height * 0.72, 3.6),
                ],
                [
                    anchor_x + tunnel_x * max(entrance_depth * 1.12, 11.0),
                    anchor_y + tunnel_y * max(entrance_depth * 1.12, 11.0),
                    anchor_z - max(entrance_height * 1.08, 5.6),
                ],
            ]
            for command in (
                {
                    "mode": "flatten",
                    "width": max(entrance_width * 1.22, 7.2),
                    "depth": 0.0,
                    "falloff": 0.84,
                },
                {
                    "mode": "carve",
                    "width": max(entrance_width * 1.34, 7.0),
                    "depth": max(entrance_height * 0.82, entrance_depth * 0.28, 3.0),
                    "falloff": 0.90,
                },
                {
                    "mode": "carve",
                    "spline_points": tunnel_curve[:4],
                    "width": max(entrance_width * 0.98, 5.2),
                    "depth": max(entrance_height * 0.36, 1.7),
                    "falloff": 0.88,
                },
                {
                    "mode": "smooth",
                    "width": max(entrance_width * 1.76, 9.8),
                    "depth": 0.0,
                    "falloff": 0.97,
                },
            ):
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": command.get("spline_points", tunnel_curve),
                        "mode": command["mode"],
                        "width": command["width"],
                        "depth": command["depth"],
                        "falloff": command["falloff"],
                        "samples_per_segment": 12,
                    },
                )

            frame_curve = [
                [anchor_x - perp_x * entrance_width * 0.98 - tunnel_x * entrance_depth * 0.16, anchor_y - perp_y * entrance_width * 0.98 - tunnel_y * entrance_depth * 0.16, anchor_z + entrance_height * 0.06],
                [anchor_x - perp_x * entrance_width * 0.86 + tunnel_x * entrance_depth * 0.18, anchor_y - perp_y * entrance_width * 0.86 + tunnel_y * entrance_depth * 0.18, anchor_z + entrance_height * 0.42],
                [anchor_x + tunnel_x * entrance_depth * 0.26, anchor_y + tunnel_y * entrance_depth * 0.26, anchor_z + entrance_height * 0.84],
                [anchor_x + perp_x * entrance_width * 0.86 + tunnel_x * entrance_depth * 0.18, anchor_y + perp_y * entrance_width * 0.86 + tunnel_y * entrance_depth * 0.18, anchor_z + entrance_height * 0.42],
                [anchor_x + perp_x * entrance_width * 0.98 - tunnel_x * entrance_depth * 0.16, anchor_y + perp_y * entrance_width * 0.98 - tunnel_y * entrance_depth * 0.16, anchor_z + entrance_height * 0.06],
            ]
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": frame_curve,
                    "mode": "raise",
                    "depth": max(entrance_height * 0.74, 3.4),
                    "falloff": 0.82,
                    "width": max(entrance_width * 1.58, 8.6),
                    "samples_per_segment": 12,
                },
            )
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": frame_curve,
                    "mode": "smooth",
                    "depth": 0.0,
                    "falloff": 0.96,
                    "width": max(entrance_width * 1.86, 10.4),
                    "samples_per_segment": 12,
                },
            )
            for side_sign in (-1.0, 1.0):
                buttress_curve = [
                    [
                        anchor_x + perp_x * side_sign * entrance_width * 1.04 - tunnel_x * entrance_depth * 0.08,
                        anchor_y + perp_y * side_sign * entrance_width * 1.04 - tunnel_y * entrance_depth * 0.08,
                        anchor_z + entrance_height * 0.08,
                    ],
                    [
                        anchor_x + perp_x * side_sign * entrance_width * 0.84 + tunnel_x * entrance_depth * 0.16,
                        anchor_y + perp_y * side_sign * entrance_width * 0.84 + tunnel_y * entrance_depth * 0.16,
                        anchor_z + entrance_height * 0.58,
                    ],
                    [
                        anchor_x + perp_x * side_sign * entrance_width * 0.66 + tunnel_x * entrance_depth * 0.40,
                        anchor_y + perp_y * side_sign * entrance_width * 0.66 + tunnel_y * entrance_depth * 0.40,
                        anchor_z + entrance_height * 0.22,
                    ],
                ]
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": buttress_curve,
                        "mode": "raise",
                        "depth": max(entrance_height * 0.48, 2.4),
                        "falloff": 0.86,
                        "width": max(entrance_width * 1.02, 5.8),
                        "samples_per_segment": 12,
                    },
                )
                await blender.send_command(
                    "terrain_spline_deform",
                    {
                        "object_name": terrain_name,
                        "spline_points": buttress_curve,
                        "mode": "smooth",
                        "depth": 0.0,
                        "falloff": 0.96,
                        "width": max(entrance_width * 1.30, 7.2),
                        "samples_per_segment": 12,
                    },
                )
            cave_patch_fix = await _stabilize_hero_terrain_patch(
                blender,
                terrain_name,
                center_x=anchor_x + tunnel_x * max(entrance_depth * 0.58, 7.0),
                center_y=anchor_y + tunnel_y * max(entrance_depth * 0.58, 7.0),
                radius=max(entrance_width * 1.46, 10.0),
                floor_z=anchor_z - max(entrance_height * 1.04, 6.2),
                blend=0.92,
            )
            if int(cave_patch_fix.get("affected_vertices", 0)) > 0:
                result["steps_completed"].append(f"terrain_patch_fix_{cave_name}")
            cave_mouth_clamp = await _stabilize_hero_terrain_patch(
                blender,
                terrain_name,
                center_x=anchor_x,
                center_y=anchor_y,
                radius=max(entrance_width * 2.10, 22.0),
                floor_z=anchor_z - max(entrance_height * 1.40, 12.0),
                ceiling_z=anchor_z + max(entrance_height * 0.60, 4.4),
                blend=0.96,
            )
            if int(cave_mouth_clamp.get("affected_vertices", 0)) > 0:
                result["steps_completed"].append(f"terrain_mouth_clamp_{cave_name}")

            portal_name = f"{cave_name}_Portal"
            portal_location = [
                anchor_x + tunnel_x * max(entrance_depth * 0.60, entrance_width * 0.58, 6.4),
                anchor_y + tunnel_y * max(entrance_depth * 0.60, entrance_width * 0.58, 6.4),
                anchor_z - max(entrance_height * 0.34, 1.6),
            ]
            await blender.send_command(
                "create_object",
                {
                    "name": portal_name,
                    "mesh_type": "plane",
                    "position": portal_location,
                    "rotation": [math.pi * 0.5, 0.0, entrance_rotation_z],
                    "scale": [
                        max(entrance_width * 0.44, 2.6),
                        max(entrance_height * 0.36, 1.8),
                        1.0,
                    ],
                },
            )
            await blender.send_command(
                "material_create",
                {
                    "name": f"{portal_name}_Material",
                    "base_color": [0.02, 0.024, 0.028, 1.0],
                    "metallic": 0.0,
                    "roughness": 0.96,
                },
            )
            await blender.send_command(
                "material_assign",
                {
                    "name": f"{portal_name}_Material",
                    "object_name": portal_name,
                },
            )
            result["objects_created"].append(portal_name)
            entrance_name = portal_name
            entrance_result = {
                "name": portal_name,
                "mode": "terrain_portal",
                "location": [round(value, 3) for value in portal_location],
            }

            loc_params = _build_location_generation_params(loc, map_spec=spec, map_seed=map_seed, index=index)
            chamber_name = f"{cave_name}_Chamber"
            loc_params["name"] = chamber_name
            loc_params["width"] = int(max(18, min(int(loc_params.get("width", 24)), 24)))
            loc_params["height"] = int(max(18, min(int(loc_params.get("height", 24)), 24)))
            loc_params["cell_size"] = float(loc.get("cell_size", 0.92))
            loc_params["wall_height"] = float(loc.get("wall_height", 4.8))
            chamber_result = await blender.send_command("world_generate_cave", loc_params)
            chamber_x = anchor_x + tunnel_x * max(entrance_depth * 0.92, loc_radius * 0.54, 9.0)
            chamber_y = anchor_y + tunnel_y * max(entrance_depth * 0.92, loc_radius * 0.54, 9.0)
            chamber_surface_z = await _sample_terrain_height(blender, terrain_name, chamber_x, chamber_y)
            connector_curve = [
                [float(tunnel_curve[-2][0]), float(tunnel_curve[-2][1]), float(tunnel_curve[-2][2]) - 0.20],
                [float(tunnel_curve[-1][0]), float(tunnel_curve[-1][1]), float(tunnel_curve[-1][2]) - 0.34],
                [
                    chamber_x,
                    chamber_y,
                    chamber_surface_z - max(entrance_height * 0.72, 4.4),
                ],
            ]
            await blender.send_command(
                "terrain_spline_deform",
                {
                    "object_name": terrain_name,
                    "spline_points": connector_curve,
                    "mode": "carve",
                    "depth": max(entrance_height * 0.56, 3.0),
                    "falloff": 0.92,
                    "width": max(entrance_width * 1.06, 5.8),
                    "samples_per_segment": 12,
                },
            )
            chamber_position = (
                chamber_x,
                chamber_y,
                chamber_surface_z - max(entrance_height * 1.12, entrance_depth * 0.56, loc_radius * 0.42, 13.5),
            )
            await _position_generated_object(blender, chamber_name, chamber_position)
            await blender.send_command(
                "material_create_procedural",
                {
                    "object_name": chamber_name,
                    "material_key": chamber_material_key,
                    "name": f"{chamber_name}_Material",
                },
            )
            await blender.send_command(
                "set_visibility",
                {
                    "name": chamber_name,
                    "visible": False,
                    "render_visible": False,
                },
            )
            result["objects_created"].append(chamber_name)
            result["locations"].append(
                {
                    "name": entrance_name,
                    "type": "cave",
                    "anchor": [round(anchor_x, 3), round(anchor_y, 3), round(anchor_z, 3)],
                    "radius": loc_radius,
                    "result": {
                        "entrance": entrance_result,
                        "chamber": chamber_result,
                    },
                }
            )
            _step_ok(f"location_mesh_{cave_name}")
        except Exception as exc:
            _step_fail(f"location_{cave_name}", exc)

    try:
        final_cleanup = await _temper_hero_peak_outliers(
            blender,
            terrain_name,
            percentile=0.996,
            blend=0.88,
            prominence_threshold=4.0,
            passes=3,
        )
        if int(final_cleanup.get("affected_vertices", 0)) > 0:
            result["steps_completed"].append("hero_final_cleanup")
    except Exception as exc:
        _step_fail("hero_final_cleanup", exc)

    try:
        biome = spec.get("biome")
        if biome:
            await blender.send_command("env_paint_terrain", {"name": terrain_name, "height_scale": float(terrain_cfg.get("height_scale", 84.0))})
            await blender.send_command("terrain_create_biome_material", {"biome_name": biome, "object_name": terrain_name})
            await blender.send_command("setup_dark_fantasy_lighting", {"object_name": terrain_name, "preset": "terrain_review"})
            _step_ok("biome_painted")
            _step_ok("lighting_ready")
    except Exception as exc:
        _step_fail("biome_lighting", exc)

    try:
        terrain_gate = await _run_terrain_visual_gate(
            blender,
            map_spec=spec,
            terrain_result=terrain_result if isinstance(terrain_result, dict) else {},
            object_names=result["objects_created"],
            location_results=result["locations"],
            validation_profiles=_normalize_validation_profiles(spec.get("terrain_visual_profiles")) or ["terrain_readability", "terrain_river", "terrain_cave"],
            min_score=int(spec.get("terrain_visual_min_score", 60)),
            screenshot_prefix=f"{map_name}_hero_driver_gate",
            object_name=terrain_name,
        )
        result["terrain_visual_verification"] = terrain_gate
        result["status"] = "success" if terrain_gate.get("passed", False) else "partial"
    except Exception as exc:
        _step_fail("terrain_visual_verification", exc)

    if save_blend is not None:
        try:
            await blender.send_command(
                "save_project",
                {
                    "filepath": str(save_blend),
                    "incremental": False,
                    "copy": False,
                    "compress": True,
                    "verify": True,
                    "compute_hash": False,
                },
            )
            _step_ok("project_saved")
            result["saved_blend"] = str(save_blend)
        except Exception as exc:
            _step_fail("project_saved", exc)

    _flush()
    print(json.dumps(result, indent=2, default=str))
    return 0


def main() -> int:
    args = _parse_args()
    return asyncio.run(_run(args.spec, args.output, args.save_blend))


if __name__ == "__main__":
    raise SystemExit(main())
