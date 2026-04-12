"""Rebuild Riftpass_01 with viewport-gated terrain authoring."""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vb_bridge import blender  # noqa: E402


SEED = 42017
TILE_SIZE = 256
RESOLUTION = 257
CELL_SIZE = 1.0
OUT_DIR = Path.home() / "AppData" / "Local" / "Temp" / "riftpass_01_rebuild"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def compose_sheet(paths: list[str], out_path: Path, columns: int = 3) -> str:
    images = [Image.open(path).convert("RGB") for path in paths]
    if not images:
        raise RuntimeError(f"no images to compose for {out_path}")
    width = max(img.width for img in images)
    height = max(img.height for img in images)
    rows = math.ceil(len(images) / columns)
    canvas = Image.new("RGB", (columns * width, rows * height), (12, 12, 14))
    for index, image in enumerate(images):
        x = (index % columns) * width
        y = (index // columns) * height
        canvas.paste(image.resize((width, height)), (x, y))
    canvas.save(out_path)
    for image in images:
        image.close()
    return str(out_path)


def _json_from_output(result: dict) -> dict:
    output = result.get("output", "") if isinstance(result, dict) else ""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"execute_code returned no parsable output: {result}")
    return json.loads(lines[-1])


def exec_json(code: str) -> dict:
    return _json_from_output(blender("execute_code", code=code))


def build_heightmap() -> np.ndarray:
    world = np.linspace(0.0, 256.0, RESOLUTION, dtype=np.float64)
    world_x, world_y = np.meshgrid(world, world)
    xg = world_x - 128.0
    yg = world_y - 128.0

    edge_base = 18.0 + 0.012 * world_y + 0.004 * np.sin(world_x / 26.0)
    height = edge_base.copy()

    def gaussian(cx: float, cy: float, sx: float, sy: float, amp: float) -> np.ndarray:
        return amp * np.exp(-(((xg - cx) / sx) ** 2 + ((yg - cy) / sy) ** 2))

    def ridge(cx: float, cy: float, sx: float, sy: float, angle_deg: float, amp: float) -> np.ndarray:
        theta = np.deg2rad(angle_deg)
        dx = xg - cx
        dy = yg - cy
        u = dx * np.cos(theta) + dy * np.sin(theta)
        v = -dx * np.sin(theta) + dy * np.cos(theta)
        return amp * np.exp(-((u / sx) ** 2 + (v / sy) ** 2))

    def warped_ridge(
        cx: float,
        cy: float,
        sx: float,
        sy: float,
        angle_deg: float,
        amp: float,
        warp_amp: float,
        warp_scale: float,
    ) -> np.ndarray:
        theta = np.deg2rad(angle_deg)
        dx = xg - cx
        dy = yg - cy
        u = dx * np.cos(theta) + dy * np.sin(theta)
        v = -dx * np.sin(theta) + dy * np.cos(theta)
        warp = warp_amp * np.sin(u / warp_scale) + 0.45 * warp_amp * np.sin((u + v) / (warp_scale * 0.7))
        return amp * np.exp(-((u / sx) ** 2 + ((v + warp) / sy) ** 2))

    def polyline_distance(points: np.ndarray) -> np.ndarray:
        distance = np.full_like(height, 1.0e9)
        for a, b in zip(points[:-1], points[1:]):
            ax, ay = a
            bx, by = b
            abx = bx - ax
            aby = by - ay
            denom = max(abx * abx + aby * aby, 1.0e-9)
            t = ((xg - ax) * abx + (yg - ay) * aby) / denom
            t = np.clip(t, 0.0, 1.0)
            px = ax + t * abx
            py = ay + t * aby
            distance = np.minimum(distance, np.sqrt((xg - px) ** 2 + (yg - py) ** 2))
        return distance

    # Broad glacial shoulders framing a mountain corridor instead of isolated cones.
    height += warped_ridge(-98.0, 18.0, 154.0, 34.0, 68.0, 24.0, 8.0, 34.0)
    height += warped_ridge(-82.0, 84.0, 122.0, 30.0, 18.0, 18.0, 7.0, 30.0)
    height += warped_ridge(-74.0, -52.0, 116.0, 30.0, 42.0, 16.0, 6.0, 28.0)
    height += warped_ridge(62.0, 26.0, 144.0, 28.0, 76.0, 26.0, 9.0, 30.0)
    height += warped_ridge(88.0, 78.0, 112.0, 24.0, 24.0, 14.0, 5.0, 28.0)
    height += warped_ridge(76.0, -62.0, 108.0, 26.0, 30.0, 14.0, 5.0, 28.0)
    height += ridge(-8.0, 96.0, 186.0, 22.0, 4.0, 11.0)
    height += ridge(18.0, -112.0, 188.0, 22.0, 10.0, 10.0)

    # Secondary summits and spurs break up the corridor walls without forming spheres.
    height += gaussian(-92.0, 28.0, 24.0, 18.0, 10.0)
    height += gaussian(-66.0, 66.0, 22.0, 18.0, 8.0)
    height += gaussian(-54.0, -36.0, 26.0, 20.0, 7.0)
    height += gaussian(58.0, 18.0, 28.0, 22.0, 7.5)
    height += gaussian(76.0, 56.0, 24.0, 18.0, 6.5)
    height += gaussian(64.0, -42.0, 28.0, 20.0, 6.0)

    # Main glacial trough from the northwest into the lower basin.
    pass_points = np.array([
        [-110.0, 84.0],
        [-82.0, 62.0],
        [-46.0, 34.0],
        [-10.0, 6.0],
        [10.0, -24.0],
        [18.0, -60.0],
        [20.0, -98.0],
    ], dtype=np.float64)
    pass_dist = polyline_distance(pass_points)
    pass_envelope = np.exp(-(((xg + 6.0) / 132.0) ** 2 + ((yg + 4.0) / 146.0) ** 2))
    height -= 21.0 * np.exp(-(pass_dist / 47.0) ** 2) * pass_envelope
    height -= 6.2 * np.exp(-(pass_dist / 24.0) ** 2) * pass_envelope
    height -= 7.5 * gaussian(-6.0, -28.0, 74.0, 42.0, 1.0)
    trough_floor = gaussian(-14.0, -10.0, 78.0, 58.0, 1.0)
    height -= 6.5 * trough_floor
    height += 5.6 * gaussian(-12.0, -6.0, 58.0, 52.0, 1.0)

    # Inner channel running along the floor keeps the pass readable from above.
    corridor_points = np.array([
        [-96.0, 74.0],
        [-58.0, 44.0],
        [-18.0, 14.0],
        [6.0, -14.0],
        [16.0, -46.0],
        [18.0, -82.0],
    ], dtype=np.float64)
    corridor_dist = polyline_distance(corridor_points)
    height -= 3.6 * np.exp(-(corridor_dist / 14.0) ** 2)

    # Hanging side-valley that spills over the eastern wall into the main trough.
    headwater_points = np.array([
        [58.0, 106.0],
        [52.0, 74.0],
        [42.0, 42.0],
        [28.0, 12.0],
        [18.0, -10.0],
    ], dtype=np.float64)
    headwater_dist = polyline_distance(headwater_points)
    height -= 17.0 * np.exp(-(headwater_dist / 10.0) ** 2)
    height -= 6.5 * np.exp(-(headwater_dist / 21.0) ** 2)
    height -= 8.0 * gaussian(40.0, 48.0, 32.0, 24.0, 1.0)
    height += 8.5 * gaussian(14.0, 30.0, 26.0, 64.0, 1.0)
    height += 9.0 * gaussian(52.0, 26.0, 24.0, 56.0, 1.0)

    # Eastern cliff/headwall with ledges and a recessed alcove entrance.
    cliff_band = 1.0 / (1.0 + np.exp(-(xg - 18.0) / 9.0))
    cliff_shape = np.exp(-((yg + 4.0) / 78.0) ** 2)
    cliff_shelves = (
        0.72
        + 0.18 * np.sin((yg + 18.0) / 10.0)
        + 0.11 * np.sin((xg + 0.7 * yg) / 13.5)
        + 0.07 * np.cos((0.5 * xg - yg) / 9.5)
    )
    height += 13.5 * cliff_band * cliff_shape
    height += 5.2 * cliff_band * cliff_shape * cliff_shelves
    height += 4.5 * gaussian(32.0, 2.0, 26.0, 34.0, 1.0)
    entrance_alcove = gaussian(32.0, -6.0, 24.0, 15.0, 1.0)
    height -= 8.2 * entrance_alcove
    height -= 4.0 * gaussian(42.0, 10.0, 18.0, 16.0, 1.0)

    # Waterfall drop, outflow river, and lower basin.
    river_points = np.array([
        [18.0, 8.0],
        [17.0, -8.0],
        [16.0, -22.0],
        [14.0, -40.0],
        [13.0, -58.0],
        [16.0, -76.0],
        [19.0, -92.0],
        [24.0, -108.0],
    ], dtype=np.float64)
    river_dist = polyline_distance(river_points)
    height -= 15.2 * np.exp(-(river_dist / 7.8) ** 2)
    height -= 4.4 * np.exp(-(river_dist / 14.0) ** 2)
    lip_shelf = gaussian(18.0, -8.0, 14.0, 10.0, 1.0)
    plunge_face = gaussian(15.5, -28.0, 10.5, 15.0, 1.0)
    plunge_pool = gaussian(16.0, -48.0, 13.0, 16.0, 1.0)
    basin = gaussian(24.0, -108.0, 32.0, 24.0, 1.0)
    height += 8.0 * lip_shelf
    height -= 15.5 * plunge_face
    height -= 11.0 * plunge_pool
    height -= 17.0 * basin
    height -= 5.0 * gaussian(6.0, -96.0, 28.0, 18.0, 1.0)

    # Tributaries, avalanche chutes, and wall fractures keep the geology broken up.
    tributary_a = np.abs((yg + 2.0) - 0.54 * (xg + 18.0))
    tributary_b = np.abs((yg - 18.0) + 0.42 * (xg + 64.0))
    tributary_c = np.abs((yg + 56.0) - 0.36 * (xg + 88.0))
    east_fracture = np.abs((yg + 10.0) + 0.92 * (xg - 34.0))
    height -= 5.2 * np.exp(-(tributary_a / 7.8) ** 2) * np.exp(-(((xg + 8.0) / 84.0) ** 2))
    height -= 4.8 * np.exp(-(tributary_b / 8.0) ** 2) * np.exp(-(((xg + 42.0) / 72.0) ** 2))
    height -= 4.2 * np.exp(-(tributary_c / 8.8) ** 2) * np.exp(-(((xg + 48.0) / 82.0) ** 2))
    height -= 4.6 * np.exp(-(east_fracture / 6.8) ** 2) * np.exp(-(((xg - 26.0) / 44.0) ** 2))

    # Additional terrace/bench breakup prevents blobby mountain silhouettes.
    bench_noise = (
        1.2 * np.sin((yg - 0.25 * xg) / 6.2)
        + 0.75 * np.cos((yg + 0.38 * xg) / 8.8)
        + 0.55 * np.sin((0.45 * xg - yg) / 11.5)
    )
    wall_mask = np.clip((cliff_band - 0.2) / 0.8, 0.0, 1.0) * cliff_shape
    height += bench_noise * wall_mask * 2.3

    # Faceted rock breakup with stronger detail only on elevated or steep terrain.
    broad_noise = (
        1.7 * np.sin(xg / 24.0) * np.cos(yg / 31.0)
        + 1.2 * np.sin((xg + 0.35 * yg) / 37.0)
        + 0.8 * np.cos((xg - 1.1 * yg) / 48.0)
    )
    detail_noise = (
        1.35 * np.sin((2.4 * xg + yg) / 10.8)
        + 0.95 * np.cos((xg - 1.8 * yg) / 12.5)
        + 0.75 * np.sin((xg + 1.2 * yg) / 8.8)
    )
    ledge_noise = 0.85 * np.sin((yg - 0.24 * xg) / 5.9) + 0.6 * np.cos((yg + 0.16 * xg) / 8.2)
    rock_mask = np.clip((height - edge_base - 7.0) / 20.0, 0.0, 1.0)
    slope_focus = np.clip((xg - 2.0) / 52.0, 0.0, 1.0) * np.exp(-((yg + 2.0) / 88.0) ** 2)
    height += broad_noise * rock_mask * 0.85
    height += detail_noise * np.maximum(rock_mask * 0.52, slope_focus * 0.82)
    height += ledge_noise * slope_focus * 1.4

    # Enforce shared-tile continuity: exact edge match, 16-cell seam guard blend.
    seam_guard = 16
    row_index = np.broadcast_to(np.arange(RESOLUTION, dtype=np.float64)[:, None], height.shape)
    col_index = np.broadcast_to(np.arange(RESOLUTION, dtype=np.float64)[None, :], height.shape)
    edge_distance = np.minimum.reduce([
        row_index,
        col_index,
        (RESOLUTION - 1) - row_index,
        (RESOLUTION - 1) - col_index,
    ])
    edge_blend = np.clip(edge_distance / float(seam_guard), 0.0, 1.0)
    height = edge_base + (height - edge_base) * edge_blend
    height[0, :] = edge_base[0, :]
    height[-1, :] = edge_base[-1, :]
    height[:, 0] = edge_base[:, 0]
    height[:, -1] = edge_base[:, -1]
    return height


def terrain_scene_read() -> dict:
    return {
        "timestamp": 0.0,
        "major_landforms": ["mountain_pass", "cliff", "waterfall", "river", "basin", "cave"],
        "focal_point": [12.0, -32.0, 28.0],
        "hero_features_missing": ["cliffside_cave", "volumetric_waterfall", "readable_pass"],
        "cave_candidates": [[31.0, -4.0, 28.0]],
        "waterfall_chains": [{
            "chain_id": "waterfall_chain_0",
            "lip_position": [18.0, -10.0, 34.0],
            "pool_position": [15.0, -48.0, 12.0],
            "drop_height": 28.0,
        }],
        "success_criteria": [
            "readable cliff",
            "traversable cave",
            "believable volumetric waterfall",
            "stable water treatment",
            "non-grainy geological terrain",
            "adjacent-tile seam continuity",
        ],
        "reviewer": "codex",
    }


def apply_review_lighting() -> dict:
    code = r"""
import bpy, json, math
from mathutils import Vector

target = Vector((8.0, -26.0, 26.0))

for obj in list(bpy.data.objects):
    if obj.name.startswith("RiftpassReview_"):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and hasattr(bpy.data, "lights"):
            try:
                bpy.data.lights.remove(data)
            except Exception:
                pass

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"

if scene.world is None:
    scene.world = bpy.data.worlds.new("RiftpassWorld")
scene.world.use_nodes = True
nodes = scene.world.node_tree.nodes
bg = nodes.get("Background")
if bg is not None:
    bg.inputs["Color"].default_value = (0.028, 0.034, 0.046, 1.0)
    bg.inputs["Strength"].default_value = 0.36

def aim_light(obj, point):
    direction = point - obj.location
    if direction.length > 1e-6:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

lights = []
specs = [
    ("RiftpassReview_Key", "AREA", (90.0, -84.0, 108.0), 52000.0, (0.92, 0.94, 1.0)),
    ("RiftpassReview_Fill", "AREA", (-104.0, -10.0, 78.0), 18000.0, (0.62, 0.70, 0.82)),
    ("RiftpassReview_Rim", "AREA", (54.0, 104.0, 86.0), 24000.0, (0.74, 0.82, 0.96)),
]
for name, light_type, location, energy, color in specs:
    data = bpy.data.lights.new(name, light_type)
    data.energy = energy
    data.color = color
    if light_type == "AREA":
        data.shape = "RECTANGLE"
        data.size = 24.0
        data.size_y = 24.0
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    aim_light(obj, target)
    lights.append({"name": obj.name, "location": tuple(round(v, 3) for v in obj.location), "rotation": tuple(round(v, 3) for v in obj.rotation_euler)})

sun = bpy.data.lights.new("RiftpassReview_Sun", "SUN")
sun.energy = 2.4
sun.angle = 0.08
sun_obj = bpy.data.objects.new("RiftpassReview_Sun", sun)
sun_obj.location = (-26.0, -54.0, 126.0)
sun_obj.rotation_euler = (math.radians(44.0), 0.0, math.radians(36.0))
bpy.context.scene.collection.objects.link(sun_obj)
lights.append({"name": sun_obj.name, "location": tuple(round(v, 3) for v in sun_obj.location), "rotation": tuple(round(v, 3) for v in sun_obj.rotation_euler)})

print(json.dumps({"lights": lights}))
"""
    return exec_json(code)


def apply_terrain_material() -> dict:
    code = r"""
import bpy, json

obj = bpy.data.objects.get("Riftpass_01_Terrain")
if obj is None:
    raise RuntimeError("terrain not found")

mat_name = "Riftpass_01_Terrain_Mat"
mat = bpy.data.materials.get(mat_name)
if mat is None:
    mat = bpy.data.materials.new(mat_name)
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

out = nodes.new("ShaderNodeOutputMaterial")
out.location = (1100, 0)
bsdf = nodes.new("ShaderNodeBsdfPrincipled")
bsdf.location = (860, 0)
links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

texcoord = nodes.new("ShaderNodeTexCoord")
texcoord.location = (-1200, 120)
mapping = nodes.new("ShaderNodeMapping")
mapping.location = (-1020, 120)
mapping.inputs["Scale"].default_value = (0.06, 0.06, 0.06)
links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])

pos = nodes.new("ShaderNodeNewGeometry")
pos.location = (-1200, -320)
sep_pos = nodes.new("ShaderNodeSeparateXYZ")
sep_pos.location = (-1020, -320)
links.new(pos.outputs["Position"], sep_pos.inputs["Vector"])

normal = nodes.new("ShaderNodeSeparateXYZ")
normal.location = (-1020, -80)
links.new(pos.outputs["Normal"], normal.inputs["Vector"])

slope_map = nodes.new("ShaderNodeMapRange")
slope_map.location = (-820, -80)
slope_map.inputs["From Min"].default_value = 1.0
slope_map.inputs["From Max"].default_value = 0.1
slope_map.inputs["To Min"].default_value = 0.0
slope_map.inputs["To Max"].default_value = 1.0
links.new(normal.outputs["Z"], slope_map.inputs["Value"])

height_map = nodes.new("ShaderNodeMapRange")
height_map.location = (-820, -320)
height_map.inputs["From Min"].default_value = -6.0
height_map.inputs["From Max"].default_value = 76.0
height_map.inputs["To Min"].default_value = 0.0
height_map.inputs["To Max"].default_value = 1.0
links.new(sep_pos.outputs["Z"], height_map.inputs["Value"])

noise_large = nodes.new("ShaderNodeTexNoise")
noise_large.location = (-780, 140)
noise_large.inputs["Scale"].default_value = 3.0
noise_large.inputs["Detail"].default_value = 5.0
noise_large.inputs["Roughness"].default_value = 0.55
links.new(mapping.outputs["Vector"], noise_large.inputs["Vector"])

noise_fine = nodes.new("ShaderNodeTexNoise")
noise_fine.location = (-780, 340)
noise_fine.inputs["Scale"].default_value = 11.0
noise_fine.inputs["Detail"].default_value = 8.0
noise_fine.inputs["Roughness"].default_value = 0.63
links.new(mapping.outputs["Vector"], noise_fine.inputs["Vector"])

rock_ramp = nodes.new("ShaderNodeValToRGB")
rock_ramp.location = (-540, 180)
rock_ramp.color_ramp.elements[0].position = 0.18
rock_ramp.color_ramp.elements[0].color = (0.19, 0.17, 0.15, 1.0)
rock_ramp.color_ramp.elements[1].position = 0.88
rock_ramp.color_ramp.elements[1].color = (0.43, 0.39, 0.34, 1.0)
links.new(noise_large.outputs["Fac"], rock_ramp.inputs["Fac"])

ground_ramp = nodes.new("ShaderNodeValToRGB")
ground_ramp.location = (-540, 420)
ground_ramp.color_ramp.elements[0].position = 0.18
ground_ramp.color_ramp.elements[0].color = (0.11, 0.14, 0.08, 1.0)
ground_ramp.color_ramp.elements[1].position = 0.92
ground_ramp.color_ramp.elements[1].color = (0.26, 0.30, 0.16, 1.0)
links.new(noise_fine.outputs["Fac"], ground_ramp.inputs["Fac"])

mix_ground = nodes.new("ShaderNodeMixRGB")
mix_ground.location = (-260, 360)
mix_ground.blend_type = "MIX"
links.new(height_map.outputs["Result"], mix_ground.inputs["Fac"])
links.new(ground_ramp.outputs["Color"], mix_ground.inputs["Color1"])
links.new(rock_ramp.outputs["Color"], mix_ground.inputs["Color2"])

mix_slope = nodes.new("ShaderNodeMixRGB")
mix_slope.location = (40, 140)
links.new(slope_map.outputs["Result"], mix_slope.inputs["Fac"])
links.new(mix_ground.outputs["Color"], mix_slope.inputs["Color1"])
links.new(rock_ramp.outputs["Color"], mix_slope.inputs["Color2"])

rough_mix = nodes.new("ShaderNodeMix")
rough_mix.data_type = "FLOAT"
rough_mix.location = (340, -120)
rough_mix.inputs["A"].default_value = 0.88
rough_mix.inputs["B"].default_value = 0.56
links.new(slope_map.outputs["Result"], rough_mix.inputs["Factor"])

wet_mix = nodes.new("ShaderNodeMix")
wet_mix.data_type = "FLOAT"
wet_mix.location = (600, -220)
wet_mix.inputs["B"].default_value = 0.34
links.new(height_map.outputs["Result"], wet_mix.inputs["Factor"])
links.new(rough_mix.outputs["Result"], wet_mix.inputs["A"])

bsdf.inputs["Specular IOR Level"].default_value = 0.34
bsdf.inputs["Base Color"].default_value = (0.24, 0.22, 0.19, 1.0)
links.new(mix_slope.outputs["Color"], bsdf.inputs["Base Color"])
links.new(wet_mix.outputs["Result"], bsdf.inputs["Roughness"])
bsdf.inputs["Normal"].default_value = (0.0, 0.0, 1.0)

obj.data.materials.clear()
obj.data.materials.append(mat)
print(json.dumps({"material": mat.name, "slots": len(obj.data.materials)}))
"""
    return exec_json(code)


def summarize_terrain_health(terrain_health: dict) -> dict:
    return {
        "ok": bool(terrain_health.get("ok")),
        "shared_height_range": terrain_health.get("shared_height_range"),
        "populated_channels": terrain_health.get("populated_channels", []),
        "results": [
            {
                "pass_name": result.get("pass_name"),
                "status": result.get("status"),
                "metrics": result.get("metrics", {}),
                "issues": result.get("issues", []),
            }
            for result in terrain_health.get("results", [])
        ],
    }


def sample_height(heightmap: np.ndarray, local_x: float, local_y: float) -> float:
    u = (local_x + 128.0) / 256.0
    v = (local_y + 128.0) / 256.0
    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))
    col_f = u * (RESOLUTION - 1)
    row_f = v * (RESOLUTION - 1)
    c0 = min(max(int(col_f), 0), RESOLUTION - 2)
    r0 = min(max(int(row_f), 0), RESOLUTION - 2)
    c1 = c0 + 1
    r1 = r0 + 1
    cf = col_f - c0
    rf = row_f - r0
    h00 = float(heightmap[r0, c0])
    h10 = float(heightmap[r0, c1])
    h01 = float(heightmap[r1, c0])
    h11 = float(heightmap[r1, c1])
    return (
        h00 * (1.0 - cf) * (1.0 - rf)
        + h10 * cf * (1.0 - rf)
        + h01 * (1.0 - cf) * rf
        + h11 * cf * rf
    )


def compute_seam_report(heightmap: np.ndarray) -> dict:
    world = np.linspace(0.0, 256.0, RESOLUTION, dtype=np.float64)
    west_expected = 18.0 + 0.012 * world + 0.004 * np.sin(0.0 / 26.0)
    east_expected = 18.0 + 0.012 * world + 0.004 * np.sin(256.0 / 26.0)
    south_expected = 18.0 + 0.012 * 0.0 + 0.004 * np.sin(world / 26.0)
    north_expected = 18.0 + 0.012 * 256.0 + 0.004 * np.sin(world / 26.0)
    west = heightmap[:, 0]
    east = heightmap[:, -1]
    south = heightmap[0, :]
    north = heightmap[-1, :]
    report = {
        "west": {"max_delta": float(np.max(np.abs(west - west_expected))), "mean_delta": float(np.mean(np.abs(west - west_expected)))},
        "east": {"max_delta": float(np.max(np.abs(east - east_expected))), "mean_delta": float(np.mean(np.abs(east - east_expected)))},
        "south": {"max_delta": float(np.max(np.abs(south - south_expected))), "mean_delta": float(np.mean(np.abs(south - south_expected)))},
        "north": {"max_delta": float(np.max(np.abs(north - north_expected))), "mean_delta": float(np.mean(np.abs(north - north_expected)))},
    }
    report["seam_ok"] = all(side["max_delta"] < 1e-5 for side in report.values())
    return report


def sample_terrain_world_height(local_x: float, local_y: float, terrain_name: str = "Riftpass_01_Terrain") -> float:
    result = exec_json(
        f"""
import bpy, json
from mathutils import Vector

obj = bpy.data.objects.get({json.dumps(terrain_name)})
if obj is None:
    raise RuntimeError("terrain not found")

depsgraph = bpy.context.evaluated_depsgraph_get()
start = Vector(({float(local_x)}, {float(local_y)}, 4000.0))
direction = Vector((0.0, 0.0, -1.0))
hit, location, normal, face_index = obj.ray_cast(start, direction, distance=8000.0, depsgraph=depsgraph)
if not hit:
    raise RuntimeError(f"ray cast missed terrain at ({float(local_x)}, {float(local_y)})")
world_location = obj.matrix_world @ location
print(json.dumps({{"z": float(world_location.z)}}))
"""
    )
    return float(result["z"])


def build_feature_spec(heightmap: np.ndarray, scene_sampler=None) -> dict:
    def world_sample(x: float, y: float) -> float:
        if scene_sampler is not None:
            return float(scene_sampler(x, y))
        return sample_height(heightmap, x, y)

    entrance_xy = (31.0, -4.0)
    entrance_z = world_sample(*entrance_xy) + 5.3
    lip_xy = (18.0, -10.0)
    lip_z = world_sample(*lip_xy) + 3.8
    plunge_xy = (15.5, -48.0)
    plunge_z = world_sample(*plunge_xy) + 1.4
    pool_xy = (24.0, -108.0)
    pool_z = world_sample(*pool_xy) + 1.2
    river_xy = [(15.0, -50.0), (14.5, -64.0), (16.0, -78.0), (18.5, -90.0), (22.0, -100.0), (26.0, -108.0)]
    river_surface_points = [[x, y, world_sample(x, y) + 1.15] for x, y in river_xy]

    def terrain_part(x: float, y: float, offset_z: float, radius: float) -> dict:
        return {"co": [x, y, world_sample(x, y) + offset_z], "radius": radius}

    return {
        "cliff_parts": [
            terrain_part(26.0, -20.0, 4.0, 11.0),
            terrain_part(32.0, -8.0, 5.6, 11.5),
            terrain_part(40.0, 6.0, 7.2, 11.0),
            terrain_part(50.0, 20.0, 8.4, 10.0),
            terrain_part(56.0, 34.0, 8.8, 9.0),
        ],
        "cave_parts": [
            {"co": [31.0, -4.0, entrance_z], "radius": 6.4},
            {"co": [41.0, 3.0, entrance_z + 0.5], "radius": 5.8},
            {"co": [52.0, 12.0, entrance_z + 1.1], "radius": 5.3},
            {"co": [66.0, 24.0, entrance_z + 1.8], "radius": 9.8},
            {"co": [78.0, 34.0, entrance_z + 1.2], "radius": 5.4},
        ],
        "waterfall_parts": [
            {"co": [18.0, -12.0, lip_z + 5.8], "radius": 3.9},
            {"co": [17.4, -20.0, lip_z + 1.6], "radius": 3.8},
            {"co": [16.5, -30.0, lip_z - 6.2], "radius": 3.7},
            {"co": [15.6, -40.0, lip_z - 13.2], "radius": 3.6},
            {"co": [15.2, -49.0, plunge_z + 3.5], "radius": 4.3},
            {"co": [15.6, -56.0, plunge_z + 1.8], "radius": 3.2},
        ],
        "river_surface_points": river_surface_points,
        "river_widths": [9.2, 10.0, 11.2, 13.4, 16.2, 18.0],
        "pool_center": [24.0, -108.0, pool_z],
        "pool_radius_x": 23.0,
        "pool_radius_y": 17.0,
        "mist_center": [15.0, -50.0, plunge_z + 4.5],
        "hero_rocks": [
            {"parts": [
                {"co": [27.0, -44.0, world_sample(27.0, -44.0) + 1.0], "radius": 1.6},
                {"co": [29.8, -41.6, world_sample(29.8, -41.6) + 0.9], "radius": 1.2},
                {"co": [25.2, -42.0, world_sample(25.2, -42.0) + 0.9], "radius": 1.0},
                {"co": [27.8, -46.0, world_sample(27.8, -46.0) + 0.8], "radius": 0.9},
            ]},
            {"parts": [
                {"co": [32.0, -84.0, world_sample(32.0, -84.0) + 0.9], "radius": 1.9},
                {"co": [35.5, -81.0, world_sample(35.5, -81.0) + 0.8], "radius": 1.4},
                {"co": [30.0, -81.2, world_sample(30.0, -81.2) + 0.8], "radius": 1.0},
            ]},
            {"parts": [
                {"co": [2.0, -108.0, world_sample(2.0, -108.0) + 0.8], "radius": 1.5},
                {"co": [-1.2, -110.0, world_sample(-1.2, -110.0) + 0.7], "radius": 1.0},
                {"co": [4.0, -111.4, world_sample(4.0, -111.4) + 0.7], "radius": 0.9},
            ]},
        ],
    }


def apply_post_erosion_features(heightmap: np.ndarray) -> np.ndarray:
    world = np.linspace(0.0, 256.0, RESOLUTION, dtype=np.float64)
    world_x, world_y = np.meshgrid(world, world)
    xg = world_x - 128.0
    yg = world_y - 128.0
    edge_base = 18.0 + 0.012 * world_y + 0.004 * np.sin(world_x / 26.0)

    def gaussian(cx: float, cy: float, sx: float, sy: float, amp: float) -> np.ndarray:
        return amp * np.exp(-(((xg - cx) / sx) ** 2 + ((yg - cy) / sy) ** 2))

    def polyline_distance(points: np.ndarray) -> np.ndarray:
        distance = np.full_like(heightmap, 1.0e9)
        for a, b in zip(points[:-1], points[1:]):
            ax, ay = a
            bx, by = b
            abx = bx - ax
            aby = by - ay
            denom = max(abx * abx + aby * aby, 1.0e-9)
            t = ((xg - ax) * abx + (yg - ay) * aby) / denom
            t = np.clip(t, 0.0, 1.0)
            px = ax + t * abx
            py = ay + t * aby
            distance = np.minimum(distance, np.sqrt((xg - px) ** 2 + (yg - py) ** 2))
        return distance

    delta = np.zeros_like(heightmap, dtype=np.float64)

    headwater = np.array([
        [58.0, 106.0],
        [52.0, 72.0],
        [42.0, 40.0],
        [29.0, 10.0],
        [18.0, -10.0],
    ], dtype=np.float64)
    headwater_dist = polyline_distance(headwater)
    delta -= 13.5 * np.exp(-(headwater_dist / 8.8) ** 2)
    delta -= 4.6 * np.exp(-(headwater_dist / 18.5) ** 2)
    delta -= 6.2 * gaussian(41.0, 48.0, 28.0, 22.0, 1.0)
    delta += 6.0 * gaussian(16.0, 30.0, 26.0, 52.0, 1.0)
    delta += 7.0 * gaussian(49.0, 28.0, 20.0, 40.0, 1.0)

    river = np.array([
        [18.0, -10.0],
        [16.0, -26.0],
        [15.0, -48.0],
        [16.0, -68.0],
        [19.0, -88.0],
        [24.0, -108.0],
    ], dtype=np.float64)
    river_dist = polyline_distance(river)
    delta -= 11.8 * np.exp(-(river_dist / 6.5) ** 2)
    delta -= 3.6 * np.exp(-(river_dist / 12.8) ** 2)
    delta += 6.6 * gaussian(18.0, -8.0, 12.0, 8.0, 1.0)
    delta -= 15.0 * gaussian(15.5, -28.0, 9.0, 12.0, 1.0)
    delta -= 11.0 * gaussian(15.5, -48.0, 11.0, 15.0, 1.0)
    delta -= 12.0 * gaussian(24.0, -108.0, 26.0, 18.0, 1.0)

    cliff_band = 1.0 / (1.0 + np.exp(-(xg - 18.0) / 8.0))
    cliff_shape = np.exp(-((yg + 4.0) / 72.0) ** 2)
    cliff_noise = 0.7 * np.sin((yg + 18.0) / 9.0) + 0.4 * np.cos((xg - 0.5 * yg) / 10.0)
    delta += 2.8 * cliff_band * cliff_shape
    delta += 1.6 * cliff_band * cliff_shape * cliff_noise
    delta -= 5.6 * gaussian(31.0, -4.0, 18.0, 12.0, 1.0)

    seam_guard = 16
    row_index = np.broadcast_to(np.arange(RESOLUTION, dtype=np.float64)[:, None], heightmap.shape)
    col_index = np.broadcast_to(np.arange(RESOLUTION, dtype=np.float64)[None, :], heightmap.shape)
    edge_distance = np.minimum.reduce([
        row_index,
        col_index,
        (RESOLUTION - 1) - row_index,
        (RESOLUTION - 1) - col_index,
    ])
    edge_blend = np.clip(edge_distance / float(seam_guard), 0.0, 1.0)
    corrected = heightmap + delta * edge_blend
    corrected = edge_base + (corrected - edge_base) * edge_blend
    corrected[0, :] = edge_base[0, :]
    corrected[-1, :] = edge_base[-1, :]
    corrected[:, 0] = edge_base[:, 0]
    corrected[:, -1] = edge_base[:, -1]
    return corrected


def author_manual_dressing(heightmap: np.ndarray, scene_sampler=None) -> dict:
    def world_sample(x: float, y: float) -> float:
        if scene_sampler is not None:
            return float(scene_sampler(x, y))
        return sample_height(heightmap, x, y)

    tree_xy = [(-36.0, -70.0), (-22.0, -84.0), (-6.0, -98.0), (10.0, -108.0), (28.0, -110.0), (46.0, -98.0), (54.0, -78.0), (40.0, -64.0), (8.0, -76.0), (-18.0, -62.0)]
    shrub_xy = [(-30.0, -92.0), (-18.0, -102.0), (-2.0, -110.0), (18.0, -112.0), (36.0, -104.0), (48.0, -90.0), (32.0, -72.0), (12.0, -68.0)]
    reed_xy = [(22.0, -96.0), (28.0, -104.0), (36.0, -100.0), (16.0, -92.0), (8.0, -98.0)]
    log_xy = [(-8.0, -88.0), (34.0, -86.0), (20.0, -70.0)]
    stone_xy = [(-28.0, -78.0), (-10.0, -96.0), (6.0, -104.0), (24.0, -106.0), (42.0, -94.0), (30.0, -66.0)]

    payload = {
        "trees": [{"name": f"RiftDress_Tree_{idx+1:02d}", "position": [x, y, world_sample(x, y)]} for idx, (x, y) in enumerate(tree_xy)],
        "shrubs": [{"name": f"RiftDress_Shrub_{idx+1:02d}", "position": [x, y, world_sample(x, y)]} for idx, (x, y) in enumerate(shrub_xy)],
        "reeds": [{"name": f"RiftDress_Reed_{idx+1:02d}", "position": [x, y, world_sample(x, y)]} for idx, (x, y) in enumerate(reed_xy)],
        "logs": [{"name": f"RiftDress_Log_{idx+1:02d}", "position": [x, y, world_sample(x, y)]} for idx, (x, y) in enumerate(log_xy)],
        "stones": [{"name": f"RiftDress_Stone_{idx+1:02d}", "position": [x, y, world_sample(x, y)]} for idx, (x, y) in enumerate(stone_xy)],
    }
    return exec_json(
        """
import bpy, json, math
from mathutils import Vector

payload = json.loads(r'''"""
        + json.dumps(payload)
        + """''')

coll = bpy.data.collections.get("Riftpass_01_Dressing")
if coll is None:
    coll = bpy.data.collections.new("Riftpass_01_Dressing")
    bpy.context.scene.collection.children.link(coll)

for obj in list(bpy.data.objects):
    if obj.name.startswith("RiftDress_"):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        try:
            if obj.type == "MESH" and data is not None:
                bpy.data.meshes.remove(data)
        except Exception:
            pass

def ensure_mat(name, color, roughness):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat

bark = ensure_mat("RiftDress_Bark", (0.20, 0.15, 0.10, 1.0), 0.92)
needle = ensure_mat("RiftDress_Needles", (0.11, 0.16, 0.10, 1.0), 0.88)
shrub = ensure_mat("RiftDress_Shrub", (0.16, 0.20, 0.12, 1.0), 0.86)
stone = ensure_mat("RiftDress_Stone", (0.28, 0.26, 0.23, 1.0), 0.9)
reed = ensure_mat("RiftDress_Reed", (0.22, 0.28, 0.14, 1.0), 0.8)
log_mat = ensure_mat("RiftDress_Log", (0.24, 0.18, 0.12, 1.0), 0.9)

def link(obj):
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    for user_coll in list(obj.users_collection):
        if user_coll != coll:
            user_coll.objects.unlink(obj)

def assign(obj, mat):
    if obj.type == "MESH":
        obj.data.materials.clear()
        obj.data.materials.append(mat)

def join_named(name, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    link(joined)
    return joined

counts = {"trees": 0, "shrubs": 0, "reeds": 0, "logs": 0, "stones": 0}

for idx, entry in enumerate(payload["trees"]):
    x, y, z = entry["position"]
    scale = 0.95 + (idx % 3) * 0.16
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=9, radius=0.28 * scale, depth=3.8 * scale, location=(x, y, z + 1.9 * scale))
    trunk = bpy.context.active_object
    assign(trunk, bark)
    link(trunk)
    parts.append(trunk)
    for cone_idx, (radius, depth, zoff) in enumerate(((1.9, 3.8, 4.0), (1.5, 3.4, 5.7), (1.1, 2.8, 7.0))):
        bpy.ops.mesh.primitive_cone_add(vertices=9, radius1=radius * scale, radius2=0.0, depth=depth * scale, location=(x, y, z + zoff * scale))
        cone = bpy.context.active_object
        assign(cone, needle)
        link(cone)
        parts.append(cone)
    joined = join_named(entry["name"], parts)
    joined.rotation_euler[2] = (idx * 0.41) % math.tau
    counts["trees"] += 1

for idx, entry in enumerate(payload["shrubs"]):
    x, y, z = entry["position"]
    parts = []
    for offset in ((0.0, 0.0, 0.72), (0.7, 0.22, 0.62), (-0.58, 0.28, 0.58)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.82, location=(x + offset[0], y + offset[1], z + offset[2]))
        obj = bpy.context.active_object
        obj.scale = (1.0, 0.82, 0.72)
        assign(obj, shrub)
        link(obj)
        parts.append(obj)
    join_named(entry["name"], parts)
    counts["shrubs"] += 1

for idx, entry in enumerate(payload["reeds"]):
    x, y, z = entry["position"]
    parts = []
    for stem_idx in range(6):
        ang = (stem_idx / 6.0) * math.tau
        dx = math.cos(ang) * 0.35
        dy = math.sin(ang) * 0.28
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.05, depth=1.6, location=(x + dx, y + dy, z + 0.96))
        stem = bpy.context.active_object
        stem.rotation_euler[0] = math.radians(6.0 + stem_idx)
        stem.rotation_euler[1] = math.radians(-4.0 + stem_idx)
        assign(stem, reed)
        link(stem)
        parts.append(stem)
    join_named(entry["name"], parts)
    counts["reeds"] += 1

for idx, entry in enumerate(payload["logs"]):
    x, y, z = entry["position"]
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.22, depth=3.4, location=(x, y, z + 0.42))
    obj = bpy.context.active_object
    obj.rotation_euler = (math.radians(86.0), 0.0, (idx * 0.63) % math.tau)
    assign(obj, log_mat)
    link(obj)
    obj.name = entry["name"]
    counts["logs"] += 1

for idx, entry in enumerate(payload["stones"]):
    x, y, z = entry["position"]
    parts = []
    for off_idx, offset in enumerate(((0.0, 0.0, 0.52), (0.42, -0.18, 0.46), (-0.34, 0.26, 0.42))):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x + offset[0], y + offset[1], z + offset[2]))
        obj = bpy.context.active_object
        obj.scale = (
            0.76 + 0.14 * ((idx + off_idx) % 3),
            0.62 + 0.10 * ((idx + off_idx + 1) % 3),
            0.42 + 0.12 * ((idx + off_idx + 2) % 3),
        )
        obj.rotation_euler = (
            math.radians(6.0 * (idx + off_idx)),
            math.radians(13.0 * off_idx),
            math.radians(19.0 * (idx + off_idx)),
        )
        assign(obj, stone)
        link(obj)
        parts.append(obj)
    joined = join_named(entry["name"], parts)
    joined.rotation_euler[2] = math.radians(idx * 9.0)
    counts["stones"] += 1

print(json.dumps({"collection": coll.name, "counts": counts, "instance_count": sum(counts.values())}))
"""
    )


def render_isolated_contact_sheet(object_name: str, out_path: Path, *, columns: int = 3) -> str:
    state = exec_json(
        f"""
import bpy, json
states = []
target_name = {json.dumps(object_name)}
for obj in bpy.data.objects:
    states.append({{"name": obj.name, "hide_render": bool(obj.hide_render)}})
    obj.hide_render = obj.name != target_name
print(json.dumps({{"states": states}}))
"""
    )
    try:
        result = blender("render_contact_sheet", object_name=object_name, resolution=[640, 640], skip_beauty=True)
        return compose_sheet(result["paths"], out_path, columns=columns)
    finally:
        exec_json(
            f"""
import bpy, json
for state in json.loads(r'''{json.dumps(state["states"])}'''):
    obj = bpy.data.objects.get(state["name"])
    if obj is not None:
        obj.hide_render = bool(state["hide_render"])
print(json.dumps({{"restored": True}}))
"""
        )


def build_terrain_only() -> dict:
    authored_height = build_heightmap()
    stage1_pipeline = [
        "macro_world",
        "structural_masks",
        "erosion",
    ]
    stage2_pipeline = [
        "structural_masks",
        "cliffs",
        "caves",
        "waterfalls",
        "materials_v2",
        "navmesh",
        "prepare_heightmap_raw_u16",
        "validation_full",
    ]

    erosion_stage = blender(
        "env_run_terrain_pass",
        tile_size=TILE_SIZE,
        cell_size=CELL_SIZE,
        seed=SEED,
        tile_x=0,
        tile_y=0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        height=authored_height.tolist(),
        terrain_type="mountains",
        pipeline=stage1_pipeline,
        scene_read=terrain_scene_read(),
        composition_hints={"unity_export_opt_out": False},
        return_height=True,
    )
    if not erosion_stage.get("ok"):
        raise RuntimeError(json.dumps(erosion_stage, indent=2))

    post_erosion_height = apply_post_erosion_features(np.asarray(erosion_stage["height"], dtype=np.float64))
    terrain_health = blender(
        "env_run_terrain_pass",
        tile_size=TILE_SIZE,
        cell_size=CELL_SIZE,
        seed=SEED,
        tile_x=0,
        tile_y=0,
        world_origin_x=0.0,
        world_origin_y=0.0,
        height=post_erosion_height.tolist(),
        terrain_type="mountains",
        pipeline=stage2_pipeline,
        scene_read=terrain_scene_read(),
        composition_hints={"unity_export_opt_out": False},
        return_height=True,
    )
    if not terrain_health.get("ok"):
        raise RuntimeError(json.dumps(terrain_health, indent=2))

    healthy_height = np.asarray(terrain_health["height"], dtype=np.float64)
    blender("clear_scene")
    terrain_result = blender(
        "env_generate_terrain",
        name="Riftpass_01_Terrain",
        terrain_type="mountains",
        resolution=RESOLUTION,
        scale=256.0,
        height_scale=1.0,
        seed=SEED,
        erosion="none",
        location=[0.0, 0.0, 0.0],
        heightmap=healthy_height.tolist(),
        cliff_overlays=False,
        cliff_threshold_deg=60.0,
    )

    node_info = exec_json(
        r"""
import bpy, json
node = bpy.data.objects.get("Riftpass_01_Node")
if node is None:
    node = bpy.data.objects.new("Riftpass_01_Node", None)
    bpy.context.scene.collection.objects.link(node)
terrain = bpy.data.objects["Riftpass_01_Terrain"]
terrain.parent = node
terrain.location = (0.0, 0.0, 0.0)
terrain.rotation_euler = (0.0, 0.0, 0.0)
terrain.scale = (1.0, 1.0, 1.0)
print(json.dumps({
    "terrain_location": tuple(round(v, 4) for v in terrain.location),
    "terrain_dims": tuple(round(v, 4) for v in terrain.dimensions),
    "node": node.name,
}))
"""
    )

    lighting = apply_review_lighting()
    material = apply_terrain_material()
    seam_report = compute_seam_report(healthy_height)

    terrain_contact = blender("render_contact_sheet", object_name="Riftpass_01_Terrain", resolution=[640, 640], skip_beauty=True)
    terrain_contact_sheet = compose_sheet(
        terrain_contact["paths"],
        OUT_DIR / "terrain_contact_sheet.png",
        columns=3,
    )
    terrain_ortho = blender("render_orthographic_views", object_name="Riftpass_01_Terrain", resolution=[640, 640])
    terrain_ortho_sheet = compose_sheet(
        terrain_ortho["paths"],
        OUT_DIR / "terrain_ortho_sheet.png",
        columns=2,
    )
    blend_result = blender("save_project", filepath=str(OUT_DIR / "Riftpass_01_stage_terrain.blend"))
    terrain_health_summary = summarize_terrain_health(terrain_health)
    summary = {
        "seed": SEED,
        "tile_contract": {
            "grid_origin": [0.0, 0.0],
            "tile_x": 0,
            "tile_y": 0,
            "tile_size": 256,
            "cell_size": 1.0,
            "resolution": 257,
            "strict_tile_contract": True,
            "verify_adjacent_seams": True,
            "scene_read_space": "local_centered",
            "seam_guard_cells": 16,
        },
        "pipeline": stage1_pipeline + ["manual_post_erosion_authoring"] + stage2_pipeline,
        "terrain_stage_erosion": summarize_terrain_health(erosion_stage),
        "terrain_health": terrain_health_summary,
        "seam_report": seam_report,
        "terrain_result": terrain_result,
        "node_info": node_info,
        "lighting": lighting,
        "material": material,
        "contact_sheet": terrain_contact_sheet,
        "orthographic_sheet": terrain_ortho_sheet,
        "blend": blend_result,
    }
    (OUT_DIR / "terrain_stage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "stage": "terrain",
        "ok": terrain_health_summary["ok"],
        "seam_ok": seam_report["seam_ok"],
        "contact_sheet": terrain_contact_sheet,
        "orthographic_sheet": terrain_ortho_sheet,
    }, indent=2))
    summary["heightmap"] = healthy_height
    return summary


def build_full_node() -> dict:
    terrain_summary = build_terrain_only()
    heightmap = terrain_summary.pop("heightmap")
    scene_height_cache: dict[tuple[float, float], float] = {}

    def scene_sampler(x: float, y: float) -> float:
        key = (round(x, 3), round(y, 3))
        if key not in scene_height_cache:
            scene_height_cache[key] = sample_terrain_world_height(x, y)
        return scene_height_cache[key]

    feature_spec = build_feature_spec(heightmap, scene_sampler=scene_sampler)
    spec_path = OUT_DIR / "riftpass_feature_spec.json"
    spec_path.write_text(json.dumps(feature_spec, indent=2), encoding="utf-8")

    runtime_path = ROOT / "riftpass_runtime_builder.py"
    runtime_source = runtime_path.read_text(encoding="utf-8")
    embedded_spec = json.dumps(feature_spec)
    runtime_result = exec_json(
        runtime_source
        + "\n"
        + f"spec = json.loads(r'''{embedded_spec}''')\n"
        + "result = build_from_spec(spec)\n"
        + "print(json.dumps(result))\n"
    )

    hero_contact_paths = {}
    for key in ("cliff", "cave_route", "waterfall", "river"):
        obj_name = runtime_result[key]
        out_path = OUT_DIR / f"{obj_name}_contact.png"
        hero_contact_paths[key] = render_isolated_contact_sheet(obj_name, out_path, columns=3)
    exec_json(
        f"""
import bpy, json
obj = bpy.data.objects.get("{runtime_result['cave_route']}")
if obj is not None:
    obj.hide_render = True
print(json.dumps({{"cave_route_hidden": obj is not None}}))
"""
    )

    vegetation_result = author_manual_dressing(heightmap, scene_sampler=scene_sampler)

    vegetation_probe = exec_json(
        r"""
import bpy, json
checks = []
for prefix in ("RiftDress_Tree_", "RiftDress_Shrub_", "RiftDress_Reed_", "RiftDress_Log_", "RiftDress_Stone_"):
    objs = [o for o in bpy.data.objects if o.name.startswith(prefix)][:8]
    checks.extend({"name": o.name, "location": [round(v, 3) for v in o.location]} for o in objs)
print(json.dumps({"samples": checks}))
"""
    )

    final_scene_contact = blender("render_contact_sheet", object_name="Riftpass_01_Terrain", resolution=[640, 640], skip_beauty=True)
    final_scene_contact_sheet = compose_sheet(
        final_scene_contact["paths"],
        OUT_DIR / "riftpass_full_contact.png",
        columns=3,
    )
    final_scene_ortho = blender("render_orthographic_views", object_name="Riftpass_01_Terrain", resolution=[640, 640])
    final_scene_ortho_sheet = compose_sheet(
        final_scene_ortho["paths"],
        OUT_DIR / "riftpass_full_ortho.png",
        columns=2,
    )

    blend_path = OUT_DIR / "Riftpass_01_final.blend"
    final_blend = blender("save_project", filepath=str(blend_path))
    summary = {
        "terrain": terrain_summary,
        "hero_objects": runtime_result,
        "hero_contact_sheets": hero_contact_paths,
        "full_scene_contact_sheet": final_scene_contact_sheet,
        "full_scene_orthographic_sheet": final_scene_ortho_sheet,
        "vegetation": vegetation_result,
        "vegetation_probe": vegetation_probe,
        "blend": final_blend,
        "feature_spec_path": str(spec_path),
    }
    (OUT_DIR / "full_build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({
        "stage": "full_build",
        "terrain_ok": terrain_summary["terrain_health"]["ok"],
        "hero_objects": runtime_result,
        "vegetation_instances": vegetation_result.get("instance_count"),
        "full_scene_contact_sheet": final_scene_contact_sheet,
    }, indent=2))
    return summary


if __name__ == "__main__":
    build_full_node()
