"""Skin Modifier-based character body generation for AAA quality.

Replaces primitive assembly with continuous organic mesh generation.
Bodies are defined as skeleton vertices with per-vertex radii.
The Skin Modifier generates smooth, unified mesh surfaces.

Pipeline: Skeleton -> Skin Modifier -> Subdivision -> Smooth -> Mesh

Benefits over primitive assembly:
- Zero junction artifacts (continuous surface)
- Automatic branch smoothing at shoulders/hips
- Quad-dominant output
- Elliptical cross-sections via per-vertex (rx, ry) radii
- Animation-ready topology

Body types: male/female x heavy/average/slim/elder (8 humanoid combos)
Monster types: bipedal/quadruped/serpent/arachnid/avian/blob (6 monster archetypes)
"""

from __future__ import annotations

import ast
import math
from typing import Any

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Vec3 = tuple[float, float, float]
Radius2 = tuple[float, float]
SkeletonVertex = dict[str, Any]  # {"name": str, "pos": Vec3, "radius": Radius2}
SkeletonDef = dict[str, Any]  # {"vertices": [...], "edges": [...]}

# ---------------------------------------------------------------------------
# Valid enumerations
# ---------------------------------------------------------------------------

VALID_GENDERS = ("male", "female")
VALID_BUILDS = ("heavy", "average", "slim", "elder")
VALID_MONSTER_TYPES = ("bipedal", "quadruped", "serpent", "arachnid", "avian", "blob")

ALL_BRANDS = [
    "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
    "LEECH", "GRACE", "MEND", "RUIN", "VOID",
]

# ---------------------------------------------------------------------------
# Humanoid body skeleton definitions
#
# Coordinate system: Z-up, Y-forward, X-right
# Heights calibrated for ~1.8m human (7.5 head proportions realistic,
# 8 head proportions heroic -- we use 7.75 as a compromise)
#
# Each skeleton vertex has:
#   - name: used for rigging vertex groups
#   - pos: (x, y, z) world position
#   - radius: (rx, ry) skin modifier elliptical radii
#
# Edges define the skeleton connectivity (tree structure).
# ---------------------------------------------------------------------------

# Base male average skeleton -- all other body types are derived via
# multipliers applied to positions and radii.
_BASE_SKELETON_VERTICES: list[SkeletonVertex] = [
    # --- Spine chain (indices 0-5) ---
    {"name": "Hips",        "pos": (0.0, 0.0, 0.95),   "radius": (0.140, 0.100)},   # 0
    {"name": "Spine",       "pos": (0.0, 0.0, 1.05),   "radius": (0.120, 0.090)},   # 1
    {"name": "Spine1",      "pos": (0.0, 0.0, 1.15),   "radius": (0.130, 0.095)},   # 2
    {"name": "Chest",       "pos": (0.0, 0.0, 1.25),   "radius": (0.150, 0.100)},   # 3
    {"name": "Neck",        "pos": (0.0, 0.0, 1.42),   "radius": (0.048, 0.048)},   # 4
    {"name": "Head",        "pos": (0.0, 0.0, 1.52),   "radius": (0.095, 0.095)},   # 5
    {"name": "HeadTop",     "pos": (0.0, 0.0, 1.68),   "radius": (0.060, 0.060)},   # 6

    # --- Left arm chain (indices 7-10) ---
    {"name": "LeftShoulder",  "pos": (-0.080, 0.0, 1.37), "radius": (0.045, 0.035)},  # 7
    {"name": "LeftUpperArm",  "pos": (-0.220, 0.0, 1.33), "radius": (0.055, 0.050)},  # 8
    {"name": "LeftForeArm",   "pos": (-0.440, 0.0, 1.10), "radius": (0.038, 0.042)},  # 9
    {"name": "LeftHand",      "pos": (-0.600, 0.0, 0.92), "radius": (0.030, 0.018)},  # 10

    # --- Right arm chain (indices 11-14) -- mirror of left ---
    {"name": "RightShoulder", "pos": (0.080, 0.0, 1.37),  "radius": (0.045, 0.035)},  # 11
    {"name": "RightUpperArm", "pos": (0.220, 0.0, 1.33),  "radius": (0.055, 0.050)},  # 12
    {"name": "RightForeArm",  "pos": (0.440, 0.0, 1.10),  "radius": (0.038, 0.042)},  # 13
    {"name": "RightHand",     "pos": (0.600, 0.0, 0.92),  "radius": (0.030, 0.018)},  # 14

    # --- Left leg chain (indices 15-18) ---
    {"name": "LeftUpLeg",   "pos": (-0.100, 0.0, 0.90), "radius": (0.072, 0.068)},  # 15
    {"name": "LeftLeg",     "pos": (-0.100, 0.0, 0.52), "radius": (0.048, 0.052)},  # 16
    {"name": "LeftFoot",    "pos": (-0.100, 0.0, 0.08), "radius": (0.032, 0.038)},  # 17
    {"name": "LeftToeBase", "pos": (-0.100, 0.10, 0.02),"radius": (0.028, 0.014)},  # 18

    # --- Right leg chain (indices 19-22) -- mirror of left ---
    {"name": "RightUpLeg",   "pos": (0.100, 0.0, 0.90), "radius": (0.072, 0.068)},  # 19
    {"name": "RightLeg",     "pos": (0.100, 0.0, 0.52), "radius": (0.048, 0.052)},  # 20
    {"name": "RightFoot",    "pos": (0.100, 0.0, 0.08), "radius": (0.032, 0.038)},  # 21
    {"name": "RightToeBase", "pos": (0.100, 0.10, 0.02),"radius": (0.028, 0.014)},  # 22
]

_BASE_SKELETON_EDGES: list[tuple[int, int]] = [
    # Spine: Hips -> Spine -> Spine1 -> Chest -> Neck -> Head -> HeadTop
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
    # Left arm: Chest -> LeftShoulder -> LeftUpperArm -> LeftForeArm -> LeftHand
    (3, 7), (7, 8), (8, 9), (9, 10),
    # Right arm: Chest -> RightShoulder -> RightUpperArm -> RightForeArm -> RightHand
    (3, 11), (11, 12), (12, 13), (13, 14),
    # Left leg: Hips -> LeftUpLeg -> LeftLeg -> LeftFoot -> LeftToeBase
    (0, 15), (15, 16), (16, 17), (17, 18),
    # Right leg: Hips -> RightUpLeg -> RightLeg -> RightFoot -> RightToeBase
    (0, 19), (19, 20), (20, 21), (21, 22),
]


# ---------------------------------------------------------------------------
# Build multiplier definitions
#
# Each build modifies base skeleton positions and radii.
# Format: {param_name: value}
# ---------------------------------------------------------------------------

BUILD_MULTIPLIERS: dict[str, dict[str, float]] = {
    "heavy": {
        "limb_radius": 1.20,
        "torso_width": 1.30,
        "torso_depth": 1.15,
        "belly_factor": 1.25,
        "height_mult": 1.02,
        "spine_forward": 0.0,
    },
    "average": {
        "limb_radius": 1.00,
        "torso_width": 1.00,
        "torso_depth": 1.00,
        "belly_factor": 1.00,
        "height_mult": 1.00,
        "spine_forward": 0.0,
    },
    "slim": {
        "limb_radius": 0.85,
        "torso_width": 0.85,
        "torso_depth": 0.88,
        "belly_factor": 0.90,
        "height_mult": 1.01,
        "spine_forward": 0.0,
    },
    "elder": {
        "limb_radius": 0.88,
        "torso_width": 0.95,
        "torso_depth": 0.92,
        "belly_factor": 1.00,
        "height_mult": 0.97,
        "spine_forward": 0.04,
    },
}

# Gender modifiers applied AFTER build multipliers
GENDER_MULTIPLIERS: dict[str, dict[str, float]] = {
    "male": {
        "shoulder_width": 1.10,
        "hip_width": 0.90,
        "chest_rx": 1.05,
        "pelvis_rx": 0.95,
    },
    "female": {
        "shoulder_width": 0.90,
        "hip_width": 1.10,
        "chest_rx": 1.00,
        "pelvis_rx": 1.10,
    },
}

# Vertex name groups for region classification
_SPINE_NAMES = {"Hips", "Spine", "Spine1", "Chest", "Neck"}
_HEAD_NAMES = {"Head", "HeadTop"}
_LEFT_ARM_NAMES = {"LeftShoulder", "LeftUpperArm", "LeftForeArm", "LeftHand"}
_RIGHT_ARM_NAMES = {"RightShoulder", "RightUpperArm", "RightForeArm", "RightHand"}
_LEFT_LEG_NAMES = {"LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"}
_RIGHT_LEG_NAMES = {"RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"}


# ---------------------------------------------------------------------------
# Skeleton construction
# ---------------------------------------------------------------------------


def _is_limb_vertex(name: str) -> bool:
    """Check if a vertex name belongs to a limb (arm or leg)."""
    return name in (_LEFT_ARM_NAMES | _RIGHT_ARM_NAMES
                    | _LEFT_LEG_NAMES | _RIGHT_LEG_NAMES)


def _is_torso_vertex(name: str) -> bool:
    """Check if a vertex name belongs to the torso/spine region."""
    return name in _SPINE_NAMES


def _is_leg_vertex(name: str) -> bool:
    """Check if a vertex name belongs to a leg chain."""
    return name in (_LEFT_LEG_NAMES | _RIGHT_LEG_NAMES)


def _is_shoulder_vertex(name: str) -> bool:
    """Check if a vertex is a shoulder/upper arm vertex."""
    return name in {"LeftShoulder", "LeftUpperArm", "RightShoulder", "RightUpperArm"}


def _is_hip_vertex(name: str) -> bool:
    """Check if a vertex is in the hip/upper leg region."""
    return name in {"LeftUpLeg", "RightUpLeg", "Hips"}


def get_skeleton(gender: str, build: str) -> SkeletonDef:
    """Get a complete skeleton definition for a gender + build combination.

    Applies build and gender multipliers to the base skeleton to produce
    anatomically correct proportions.

    Args:
        gender: 'male' or 'female'
        build: 'heavy', 'average', 'slim', or 'elder'

    Returns:
        SkeletonDef with 'vertices' (list of positions), 'edges',
        'radii' (list of (rx, ry) tuples), and 'names' (list of str).
    """
    if gender not in VALID_GENDERS:
        raise ValueError(f"Invalid gender {gender!r}. Must be one of {VALID_GENDERS}")
    if build not in VALID_BUILDS:
        raise ValueError(f"Invalid build {build!r}. Must be one of {VALID_BUILDS}")

    bm = BUILD_MULTIPLIERS[build]
    gm = GENDER_MULTIPLIERS[gender]

    height_mult = bm["height_mult"]
    limb_r = bm["limb_radius"]
    torso_w = bm["torso_width"]
    torso_d = bm["torso_depth"]
    belly = bm["belly_factor"]
    spine_fwd = bm["spine_forward"]

    shoulder_w = gm["shoulder_width"]
    hip_w = gm["hip_width"]
    chest_rx = gm["chest_rx"]
    pelvis_rx = gm["pelvis_rx"]

    positions: list[Vec3] = []
    radii: list[Radius2] = []
    names: list[str] = []

    for vert in _BASE_SKELETON_VERTICES:
        name = vert["name"]
        bx, by, bz = vert["pos"]
        brx, bry = vert["radius"]

        # --- Apply height scaling ---
        z = bz * height_mult
        x = bx
        y = by

        # --- Apply spine forward lean (elder hunch) ---
        if _is_torso_vertex(name) or name in _HEAD_NAMES:
            # Proportion of spine height above hips used for lean curve
            spine_base_z = 0.95 * height_mult
            spine_top_z = 1.42 * height_mult
            if z > spine_base_z:
                t = min((z - spine_base_z) / max(spine_top_z - spine_base_z, 0.01), 1.0)
                y += spine_fwd * math.sin(t * math.pi) * (spine_top_z - spine_base_z)

        # --- Apply gender shoulder/hip width ---
        if _is_shoulder_vertex(name):
            x *= shoulder_w
        elif _is_hip_vertex(name):
            x *= hip_w
        # Arm/leg positions scale with their respective anchor widths
        elif name in {"LeftForeArm", "LeftHand"}:
            x *= shoulder_w
        elif name in {"RightForeArm", "RightHand"}:
            x *= shoulder_w
        elif name in {"LeftLeg", "LeftFoot", "LeftToeBase"}:
            x *= hip_w
        elif name in {"RightLeg", "RightFoot", "RightToeBase"}:
            x *= hip_w

        # --- Apply radius multipliers ---
        rx = brx
        ry = bry

        if _is_limb_vertex(name):
            rx *= limb_r
            ry *= limb_r
        elif _is_torso_vertex(name):
            rx *= torso_w
            ry *= torso_d
            # Belly region: Spine and Spine1 get extra girth
            if name in {"Spine", "Spine1"}:
                rx *= belly
                ry *= belly * 0.9  # belly is wider than deep

        # Gender chest/pelvis shaping
        if name == "Chest":
            rx *= chest_rx
        elif name == "Hips":
            rx *= pelvis_rx

        positions.append((x, y, z))
        radii.append((rx, ry))
        names.append(name)

    return {
        "vertices": positions,
        "edges": list(_BASE_SKELETON_EDGES),
        "radii": radii,
        "names": names,
    }


# ---------------------------------------------------------------------------
# Blender code generation for Skin Modifier pipeline
# ---------------------------------------------------------------------------


def generate_skin_body_code(
    gender: str,
    build: str,
    name: str = "CharacterBody",
    subdivision_level: int = 2,
) -> str:
    """Generate Blender Python code that creates a Skin Modifier body.

    This code is designed to be executed via the blender_execute tool.
    Only uses allowed imports: bpy, bmesh, mathutils, math.

    Args:
        gender: 'male' or 'female'
        build: 'heavy', 'average', 'slim', or 'elder'
        name: Object name in Blender
        subdivision_level: Subdivision Surface modifier level (1-3)

    Returns:
        Complete Python script as a string, ready for blender_execute.
    """
    skeleton = get_skeleton(gender, build)

    verts_str = repr(skeleton["vertices"])
    edges_str = repr(skeleton["edges"])
    radii_str = repr(skeleton["radii"])
    names_str = repr(skeleton["names"])
    subdiv = max(1, min(3, subdivision_level))
    render_subdiv = min(subdiv + 1, 4)

    name_literal = repr(name)
    gender_literal = repr(gender)
    build_literal = repr(build)

    code = f'''import bpy
import bmesh
import math

# ---- Create skeleton mesh ----
mesh_data = bpy.data.meshes.new({name_literal} + "_skeleton")
verts = {verts_str}
edges = {edges_str}
mesh_data.from_pydata(verts, edges, [])
mesh_data.update()

obj = bpy.data.objects.new({name_literal}, mesh_data)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# ---- Skin Modifier ----
skin_mod = obj.modifiers.new("Skin", 'SKIN')
skin_mod.branch_smoothing = 0.75

# Set per-vertex radii for anatomical proportions
radii = {radii_str}
for i, vert in enumerate(obj.data.vertices):
    sv = obj.data.skin_vertices[0].data[i]
    sv.radius = radii[i]

# Mark root vertex (Hips = index 0) as the skin root
obj.data.skin_vertices[0].data[0].use_root = True

# ---- Mirror Modifier for perfect symmetry ----
mirror_mod = obj.modifiers.new("Mirror", 'MIRROR')
mirror_mod.use_axis[0] = True
mirror_mod.use_bisect_axis[0] = True
mirror_mod.merge_threshold = 0.005

# ---- Subdivision Surface for smoothness ----
subsurf_mod = obj.modifiers.new("Subsurf", 'SUBSURF')
subsurf_mod.levels = {subdiv}
subsurf_mod.render_levels = {render_subdiv}
subsurf_mod.quality = 3

# ---- Apply modifiers in order: Skin -> Mirror -> Subsurf ----
bpy.ops.object.modifier_apply(modifier="Skin")
bpy.ops.object.modifier_apply(modifier="Mirror")
bpy.ops.object.modifier_apply(modifier="Subsurf")

# ---- Smooth shading ----
bpy.ops.object.shade_smooth()

# ---- Auto-generate vertex groups for rigging ----
names = {names_str}
positions = {verts_str}

# Create vertex groups named after skeleton vertices
for vg_name in names:
    if vg_name not in obj.vertex_groups:
        obj.vertex_groups.new(name=vg_name)

# Assign vertices to groups based on proximity to skeleton positions
for vi, mv in enumerate(obj.data.vertices):
    vx, vy, vz = mv.co.x, mv.co.y, mv.co.z
    best_dist = float('inf')
    best_name = names[0]
    for si, spos in enumerate(positions):
        dx = vx - spos[0]
        dy = vy - spos[1]
        dz = vz - spos[2]
        d = math.sqrt(dx*dx + dy*dy + dz*dz)
        if d < best_dist:
            best_dist = d
            best_name = names[si]
    vg = obj.vertex_groups.get(best_name)
    if vg is not None:
        weight = max(0.0, 1.0 - best_dist * 5.0)
        if weight > 0.05:
            vg.add([vi], weight, 'ADD')

# ---- Report mesh stats ----
poly_count = len(obj.data.polygons)
vert_count = len(obj.data.vertices)
edge_count = len(obj.data.edges)

# Count quads vs tris
quad_count = sum(1 for p in obj.data.polygons if len(p.vertices) == 4)
tri_count = sum(1 for p in obj.data.polygons if len(p.vertices) == 3)

result = {{
    "object_name": {name_literal},
    "vertex_count": vert_count,
    "edge_count": edge_count,
    "polygon_count": poly_count,
    "quad_count": quad_count,
    "tri_count": tri_count,
    "quad_ratio": quad_count / max(poly_count, 1),
    "gender": {gender_literal},
    "build": {build_literal},
    "vertex_group_count": len(obj.vertex_groups),
}}
print("SKIN_BODY_RESULT:" + str(result))
'''
    return code


# ---------------------------------------------------------------------------
# Monster skeleton definitions
# ---------------------------------------------------------------------------


def _mirror_skeleton_x(
    vertices: list[SkeletonVertex],
    edges: list[tuple[int, int]],
    mirror_prefix_map: dict[str, str] | None = None,
) -> tuple[list[SkeletonVertex], list[tuple[int, int]]]:
    """Mirror left-side vertices to create right-side, updating edges.

    Only mirrors vertices whose names start with 'L_'.
    Creates mirrored 'R_' versions.
    """
    if mirror_prefix_map is None:
        mirror_prefix_map = {"L_": "R_"}

    new_verts = list(vertices)
    new_edges = list(edges)
    remap: dict[int, int] = {}

    for src_prefix, dst_prefix in mirror_prefix_map.items():
        for i, v in enumerate(vertices):
            if v["name"].startswith(src_prefix):
                mirror_idx = len(new_verts)
                remap[i] = mirror_idx
                new_verts.append({
                    "name": dst_prefix + v["name"][len(src_prefix):],
                    "pos": (-v["pos"][0], v["pos"][1], v["pos"][2]),
                    "radius": v["radius"],
                })

    # Mirror edges
    for a, b in edges:
        if a in remap or b in remap:
            ma = remap.get(a, a)
            mb = remap.get(b, b)
            if (ma, mb) not in new_edges and (mb, ma) not in new_edges:
                new_edges.append((ma, mb))

    return new_verts, new_edges


# Bipedal monster: humanoid proportions but beast-like -- broader, more
# hunched, with heavier limbs.

_BIPEDAL_SKELETON_VERTICES: list[SkeletonVertex] = [
    {"name": "Hips",        "pos": (0.0, 0.0, 0.85),   "radius": (0.160, 0.120)},  # 0
    {"name": "Spine",       "pos": (0.0, 0.02, 0.98),   "radius": (0.140, 0.110)},  # 1
    {"name": "Chest",       "pos": (0.0, 0.04, 1.15),   "radius": (0.180, 0.130)},  # 2
    {"name": "Neck",        "pos": (0.0, 0.06, 1.32),   "radius": (0.070, 0.065)},  # 3
    {"name": "Head",        "pos": (0.0, 0.08, 1.45),   "radius": (0.120, 0.110)},  # 4
    {"name": "Jaw",         "pos": (0.0, 0.14, 1.40),   "radius": (0.075, 0.060)},  # 5
    # Left arm
    {"name": "L_Shoulder",  "pos": (-0.20, 0.0, 1.25),  "radius": (0.070, 0.065)},  # 6
    {"name": "L_UpperArm",  "pos": (-0.34, 0.0, 1.10),  "radius": (0.060, 0.058)},  # 7
    {"name": "L_ForeArm",   "pos": (-0.48, 0.0, 0.90),  "radius": (0.045, 0.048)},  # 8
    {"name": "L_Hand",      "pos": (-0.58, 0.0, 0.78),  "radius": (0.050, 0.025)},  # 9
    # Left leg
    {"name": "L_UpLeg",     "pos": (-0.12, 0.0, 0.80),  "radius": (0.085, 0.080)},  # 10
    {"name": "L_Leg",       "pos": (-0.12, 0.0, 0.45),  "radius": (0.058, 0.062)},  # 11
    {"name": "L_Foot",      "pos": (-0.12, 0.0, 0.08),  "radius": (0.040, 0.045)},  # 12
    {"name": "L_Toe",       "pos": (-0.12, 0.14, 0.02), "radius": (0.035, 0.018)},  # 13
]

_BIPEDAL_SKELETON_EDGES: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5),   # spine + jaw
    (2, 6), (6, 7), (7, 8), (8, 9),            # left arm
    (0, 10), (10, 11), (11, 12), (12, 13),     # left leg
]

# Quadruped: wolf/horse/bear body -- horizontal spine, 4 legs, tail

_QUADRUPED_SKELETON_VERTICES: list[SkeletonVertex] = [
    # Spine runs along Y axis (front to back), body height on Z
    {"name": "Pelvis",      "pos": (0.0, -0.50, 0.70),  "radius": (0.130, 0.110)},  # 0
    {"name": "SpineRear",   "pos": (0.0, -0.30, 0.72),  "radius": (0.140, 0.120)},  # 1
    {"name": "SpineMid",    "pos": (0.0, -0.05, 0.75),  "radius": (0.150, 0.130)},  # 2
    {"name": "SpineFront",  "pos": (0.0,  0.20, 0.78),  "radius": (0.145, 0.125)},  # 3
    {"name": "Shoulders",   "pos": (0.0,  0.40, 0.80),  "radius": (0.135, 0.115)},  # 4
    {"name": "Neck",        "pos": (0.0,  0.52, 0.95),  "radius": (0.075, 0.070)},  # 5
    {"name": "Head",        "pos": (0.0,  0.62, 1.05),  "radius": (0.090, 0.080)},  # 6
    {"name": "Snout",       "pos": (0.0,  0.78, 1.02),  "radius": (0.050, 0.040)},  # 7
    # Tail
    {"name": "Tail1",       "pos": (0.0, -0.58, 0.72),  "radius": (0.045, 0.040)},  # 8
    {"name": "Tail2",       "pos": (0.0, -0.72, 0.75),  "radius": (0.030, 0.028)},  # 9
    {"name": "TailTip",     "pos": (0.0, -0.88, 0.78),  "radius": (0.015, 0.012)},  # 10
    # Left front leg
    {"name": "L_FrontUpLeg",  "pos": (-0.10, 0.35, 0.65), "radius": (0.050, 0.048)},  # 11
    {"name": "L_FrontLeg",    "pos": (-0.10, 0.36, 0.38), "radius": (0.035, 0.038)},  # 12
    {"name": "L_FrontFoot",   "pos": (-0.10, 0.38, 0.08), "radius": (0.028, 0.032)},  # 13
    {"name": "L_FrontToe",    "pos": (-0.10, 0.44, 0.02), "radius": (0.022, 0.012)},  # 14
    # Left rear leg
    {"name": "L_RearUpLeg",   "pos": (-0.10, -0.45, 0.58), "radius": (0.058, 0.055)}, # 15
    {"name": "L_RearLeg",     "pos": (-0.10, -0.44, 0.32), "radius": (0.038, 0.042)}, # 16
    {"name": "L_RearFoot",    "pos": (-0.10, -0.42, 0.08), "radius": (0.030, 0.035)}, # 17
    {"name": "L_RearToe",     "pos": (-0.10, -0.38, 0.02), "radius": (0.024, 0.014)}, # 18
]

_QUADRUPED_SKELETON_EDGES: list[tuple[int, int]] = [
    # Spine
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
    # Tail
    (0, 8), (8, 9), (9, 10),
    # Left front leg
    (4, 11), (11, 12), (12, 13), (13, 14),
    # Left rear leg
    (0, 15), (15, 16), (16, 17), (17, 18),
]

# Serpent: long spine chain with varying radius, no limbs

_SERPENT_SKELETON_VERTICES: list[SkeletonVertex] = [
    {"name": "Head",      "pos": (0.0, 0.80, 0.55),  "radius": (0.080, 0.065)},  # 0
    {"name": "Neck",      "pos": (0.0, 0.65, 0.50),  "radius": (0.060, 0.055)},  # 1
    {"name": "Spine0",    "pos": (0.0, 0.45, 0.35),  "radius": (0.075, 0.065)},  # 2
    {"name": "Spine1",    "pos": (0.0, 0.25, 0.22),  "radius": (0.090, 0.078)},  # 3
    {"name": "Spine2",    "pos": (0.0, 0.05, 0.15),  "radius": (0.095, 0.082)},  # 4
    {"name": "Spine3",    "pos": (0.0, -0.15, 0.12), "radius": (0.092, 0.080)},  # 5
    {"name": "Spine4",    "pos": (0.0, -0.35, 0.14), "radius": (0.085, 0.075)},  # 6
    {"name": "Spine5",    "pos": (0.0, -0.55, 0.18), "radius": (0.075, 0.068)},  # 7
    {"name": "Spine6",    "pos": (0.0, -0.72, 0.22), "radius": (0.060, 0.055)},  # 8
    {"name": "Spine7",    "pos": (0.0, -0.85, 0.28), "radius": (0.045, 0.042)},  # 9
    {"name": "TailBase",  "pos": (0.0, -0.95, 0.32), "radius": (0.032, 0.030)},  # 10
    {"name": "TailTip",   "pos": (0.0, -1.10, 0.38), "radius": (0.015, 0.012)},  # 11
]

_SERPENT_SKELETON_EDGES: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
    (6, 7), (7, 8), (8, 9), (9, 10), (10, 11),
]

# Arachnid / Spider: central body with 8 leg chains

_ARACHNID_SKELETON_VERTICES: list[SkeletonVertex] = [
    # Central body
    {"name": "Abdomen",    "pos": (0.0, -0.15, 0.35), "radius": (0.140, 0.120)},  # 0
    {"name": "Thorax",     "pos": (0.0,  0.08, 0.40), "radius": (0.110, 0.095)},  # 1
    {"name": "Head",       "pos": (0.0,  0.22, 0.42), "radius": (0.065, 0.060)},  # 2
    {"name": "Mandible",   "pos": (0.0,  0.32, 0.38), "radius": (0.030, 0.020)},  # 3
    # Left legs 1-4 (front to back) -- 3 segments each
    # Leg 1 (front-most)
    {"name": "L_Leg1_Hip",   "pos": (-0.10, 0.12, 0.38), "radius": (0.025, 0.022)},  # 4
    {"name": "L_Leg1_Mid",   "pos": (-0.28, 0.20, 0.50), "radius": (0.018, 0.016)},  # 5
    {"name": "L_Leg1_Tip",   "pos": (-0.42, 0.15, 0.05), "radius": (0.010, 0.008)},  # 6
    # Leg 2
    {"name": "L_Leg2_Hip",   "pos": (-0.10, 0.05, 0.38), "radius": (0.028, 0.024)},  # 7
    {"name": "L_Leg2_Mid",   "pos": (-0.32, 0.06, 0.52), "radius": (0.020, 0.018)},  # 8
    {"name": "L_Leg2_Tip",   "pos": (-0.48, 0.02, 0.05), "radius": (0.012, 0.010)},  # 9
    # Leg 3
    {"name": "L_Leg3_Hip",   "pos": (-0.10, -0.02, 0.36), "radius": (0.028, 0.024)}, # 10
    {"name": "L_Leg3_Mid",   "pos": (-0.30, -0.05, 0.50), "radius": (0.020, 0.018)}, # 11
    {"name": "L_Leg3_Tip",   "pos": (-0.45, -0.08, 0.05), "radius": (0.012, 0.010)}, # 12
    # Leg 4 (rear-most)
    {"name": "L_Leg4_Hip",   "pos": (-0.10, -0.10, 0.34), "radius": (0.026, 0.022)}, # 13
    {"name": "L_Leg4_Mid",   "pos": (-0.28, -0.18, 0.48), "radius": (0.018, 0.016)}, # 14
    {"name": "L_Leg4_Tip",   "pos": (-0.40, -0.22, 0.05), "radius": (0.010, 0.008)}, # 15
]

_ARACHNID_SKELETON_EDGES: list[tuple[int, int]] = [
    # Body chain
    (0, 1), (1, 2), (2, 3),
    # Left legs from thorax
    (1, 4), (4, 5), (5, 6),
    (1, 7), (7, 8), (8, 9),
    (1, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15),
]

# Avian: body with wing chains

_AVIAN_SKELETON_VERTICES: list[SkeletonVertex] = [
    # Body
    {"name": "Tail",       "pos": (0.0, -0.30, 0.45), "radius": (0.045, 0.035)},  # 0
    {"name": "Hips",       "pos": (0.0, -0.12, 0.50), "radius": (0.085, 0.075)},  # 1
    {"name": "Chest",      "pos": (0.0,  0.08, 0.58), "radius": (0.095, 0.085)},  # 2
    {"name": "Keel",       "pos": (0.0,  0.10, 0.48), "radius": (0.060, 0.070)},  # 3
    {"name": "Neck",       "pos": (0.0,  0.20, 0.72), "radius": (0.035, 0.032)},  # 4
    {"name": "Head",       "pos": (0.0,  0.28, 0.82), "radius": (0.045, 0.040)},  # 5
    {"name": "Beak",       "pos": (0.0,  0.38, 0.80), "radius": (0.018, 0.012)},  # 6
    # Left wing
    {"name": "L_WingShoulder", "pos": (-0.08, 0.05, 0.60), "radius": (0.035, 0.025)},  # 7
    {"name": "L_WingMid",     "pos": (-0.30, 0.02, 0.65), "radius": (0.020, 0.008)},  # 8
    {"name": "L_WingTip",     "pos": (-0.55, -0.02, 0.68),"radius": (0.010, 0.004)},  # 9
    # Left leg
    {"name": "L_UpLeg",    "pos": (-0.06, -0.08, 0.42), "radius": (0.035, 0.032)},  # 10
    {"name": "L_Leg",      "pos": (-0.06, -0.05, 0.22), "radius": (0.018, 0.020)},  # 11
    {"name": "L_Foot",     "pos": (-0.06,  0.02, 0.04), "radius": (0.022, 0.012)},  # 12
]

_AVIAN_SKELETON_EDGES: list[tuple[int, int]] = [
    # Body
    (0, 1), (1, 2), (2, 3), (2, 4), (4, 5), (5, 6),
    # Left wing
    (2, 7), (7, 8), (8, 9),
    # Left leg
    (1, 10), (10, 11), (11, 12),
]

# Blob / Amorphous: central mass with tentacle chains

_BLOB_SKELETON_VERTICES: list[SkeletonVertex] = [
    # Central mass
    {"name": "Core",       "pos": (0.0, 0.0, 0.30),  "radius": (0.180, 0.160)},   # 0
    {"name": "UpperMass",  "pos": (0.0, 0.0, 0.50),  "radius": (0.150, 0.140)},   # 1
    {"name": "TopNode",    "pos": (0.0, 0.0, 0.65),  "radius": (0.080, 0.075)},   # 2
    # Tentacles (left side, will be mirrored)
    {"name": "L_Tent1_Base", "pos": (-0.15, 0.10, 0.28), "radius": (0.045, 0.040)},  # 3
    {"name": "L_Tent1_Mid",  "pos": (-0.30, 0.18, 0.20), "radius": (0.030, 0.028)},  # 4
    {"name": "L_Tent1_Tip",  "pos": (-0.48, 0.22, 0.12), "radius": (0.015, 0.012)},  # 5
    {"name": "L_Tent2_Base", "pos": (-0.14, -0.10, 0.25),"radius": (0.042, 0.038)},  # 6
    {"name": "L_Tent2_Mid",  "pos": (-0.28, -0.20, 0.18),"radius": (0.028, 0.025)},  # 7
    {"name": "L_Tent2_Tip",  "pos": (-0.44, -0.28, 0.10),"radius": (0.014, 0.010)},  # 8
    # Front tentacle (not mirrored)
    {"name": "FrontTent_Base", "pos": (0.0, 0.18, 0.35), "radius": (0.040, 0.035)},  # 9
    {"name": "FrontTent_Mid",  "pos": (0.0, 0.35, 0.28), "radius": (0.025, 0.022)},  # 10
    {"name": "FrontTent_Tip",  "pos": (0.0, 0.48, 0.20), "radius": (0.012, 0.010)},  # 11
]

_BLOB_SKELETON_EDGES: list[tuple[int, int]] = [
    # Central mass
    (0, 1), (1, 2),
    # Left tentacle 1
    (0, 3), (3, 4), (4, 5),
    # Left tentacle 2
    (0, 6), (6, 7), (7, 8),
    # Front tentacle
    (0, 9), (9, 10), (10, 11),
]


# ---------------------------------------------------------------------------
# Monster skeleton registry and lookup
# ---------------------------------------------------------------------------


MONSTER_SKELETONS: dict[str, dict[str, Any]] = {
    "bipedal": {
        "vertices": _BIPEDAL_SKELETON_VERTICES,
        "edges": _BIPEDAL_SKELETON_EDGES,
        "mirror_prefix": "L_",
        "description": "Humanoid beast with heavy proportions",
    },
    "quadruped": {
        "vertices": _QUADRUPED_SKELETON_VERTICES,
        "edges": _QUADRUPED_SKELETON_EDGES,
        "mirror_prefix": "L_",
        "description": "Four-legged beast (wolf/bear/horse)",
    },
    "serpent": {
        "vertices": _SERPENT_SKELETON_VERTICES,
        "edges": _SERPENT_SKELETON_EDGES,
        "mirror_prefix": None,
        "description": "Long spine chain, no limbs",
    },
    "arachnid": {
        "vertices": _ARACHNID_SKELETON_VERTICES,
        "edges": _ARACHNID_SKELETON_EDGES,
        "mirror_prefix": "L_",
        "description": "Central body with 8 legs (spider)",
    },
    "avian": {
        "vertices": _AVIAN_SKELETON_VERTICES,
        "edges": _AVIAN_SKELETON_EDGES,
        "mirror_prefix": "L_",
        "description": "Bird body with wing chains",
    },
    "blob": {
        "vertices": _BLOB_SKELETON_VERTICES,
        "edges": _BLOB_SKELETON_EDGES,
        "mirror_prefix": "L_",
        "description": "Amorphous mass with tentacle chains",
    },
}


def get_monster_skeleton(
    monster_type: str,
    scale: float = 1.0,
    brand: str | None = None,
) -> SkeletonDef:
    """Get a complete monster skeleton definition.

    Args:
        monster_type: One of VALID_MONSTER_TYPES
        scale: Size multiplier (1.0 = default)
        brand: Optional VeilBreakers brand for vertex group tagging

    Returns:
        SkeletonDef with 'vertices', 'edges', 'radii', 'names',
        and optionally 'brand_groups' for brand feature attachment.
    """
    if monster_type not in VALID_MONSTER_TYPES:
        raise ValueError(
            f"Invalid monster_type {monster_type!r}. "
            f"Must be one of {VALID_MONSTER_TYPES}"
        )

    skel_data = MONSTER_SKELETONS[monster_type]
    base_verts = skel_data["vertices"]
    base_edges = skel_data["edges"]
    mirror_prefix = skel_data["mirror_prefix"]

    # Apply mirroring for types that have it
    if mirror_prefix:
        full_verts, full_edges = _mirror_skeleton_x(
            base_verts, base_edges,
            mirror_prefix_map={mirror_prefix: "R_" if mirror_prefix == "L_" else mirror_prefix},
        )
    else:
        full_verts = list(base_verts)
        full_edges = list(base_edges)

    # Apply scale
    positions: list[Vec3] = []
    radii: list[Radius2] = []
    names: list[str] = []

    for v in full_verts:
        px, py, pz = v["pos"]
        rx, ry = v["radius"]
        positions.append((px * scale, py * scale, pz * scale))
        radii.append((rx * scale, ry * scale))
        names.append(v["name"])

    result: SkeletonDef = {
        "vertices": positions,
        "edges": full_edges,
        "radii": radii,
        "names": names,
        "monster_type": monster_type,
        "scale": scale,
    }

    # Brand vertex group tagging
    if brand and brand in ALL_BRANDS:
        # Tag surface regions for brand feature attachment
        brand_groups: dict[str, list[int]] = {}
        # Body core vertices get brand features
        core_indices = [
            i for i, n in enumerate(names)
            if not any(n.endswith(suffix) for suffix in ("_Tip", "_Toe", "Tip"))
        ]
        brand_groups["brand_surface"] = core_indices
        result["brand_groups"] = brand_groups
        result["brand"] = brand

    return result


def generate_skin_monster_code(
    monster_type: str,
    name: str = "MonsterBody",
    scale: float = 1.0,
    brand: str | None = None,
    subdivision_level: int = 2,
) -> str:
    """Generate Blender Python code for a monster body via Skin Modifier.

    Args:
        monster_type: One of VALID_MONSTER_TYPES
        name: Object name in Blender
        scale: Size multiplier
        brand: Optional brand for vertex group tagging
        subdivision_level: Subdivision level (1-3)

    Returns:
        Complete Python script string for blender_execute.
    """
    skeleton = get_monster_skeleton(monster_type, scale=scale, brand=brand)

    verts_str = repr(skeleton["vertices"])
    edges_str = repr(skeleton["edges"])
    radii_str = repr(skeleton["radii"])
    names_str = repr(skeleton["names"])
    subdiv = max(1, min(3, subdivision_level))
    render_subdiv = min(subdiv + 1, 4)

    name_literal = repr(name)
    monster_type_literal = repr(monster_type)
    brand_literal = repr(brand or 'none')

    # Determine if mirror should be used based on type
    use_mirror = MONSTER_SKELETONS[monster_type]["mirror_prefix"] is not None

    mirror_block = ""
    if use_mirror:
        mirror_block = '''
# ---- Mirror Modifier for symmetry ----
mirror_mod = obj.modifiers.new("Mirror", 'MIRROR')
mirror_mod.use_axis[0] = True
mirror_mod.use_bisect_axis[0] = True
mirror_mod.merge_threshold = 0.005
'''

    apply_mirror = ""
    if use_mirror:
        apply_mirror = 'bpy.ops.object.modifier_apply(modifier="Mirror")\n'

    brand_group_block = ""
    if brand and brand in ALL_BRANDS:
        brand_group_block = f'''
# ---- Brand vertex group for VFX attachment ----
brand_vg = obj.vertex_groups.new(name="brand_{brand.lower()}")
for vi in range(len(obj.data.vertices)):
    brand_vg.add([vi], 0.5, 'ADD')
'''

    code = f'''import bpy
import bmesh
import math

# ---- Create skeleton mesh ----
mesh_data = bpy.data.meshes.new({name_literal} + "_skeleton")
verts = {verts_str}
edges = {edges_str}
mesh_data.from_pydata(verts, edges, [])
mesh_data.update()

obj = bpy.data.objects.new({name_literal}, mesh_data)
bpy.context.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# ---- Skin Modifier ----
skin_mod = obj.modifiers.new("Skin", 'SKIN')
skin_mod.branch_smoothing = 0.80

# Set per-vertex radii
radii = {radii_str}
for i, vert in enumerate(obj.data.vertices):
    sv = obj.data.skin_vertices[0].data[i]
    sv.radius = radii[i]

# Mark root vertex (index 0) as the skin root
obj.data.skin_vertices[0].data[0].use_root = True
{mirror_block}
# ---- Subdivision Surface ----
subsurf_mod = obj.modifiers.new("Subsurf", 'SUBSURF')
subsurf_mod.levels = {subdiv}
subsurf_mod.render_levels = {render_subdiv}
subsurf_mod.quality = 3

# ---- Apply modifiers ----
bpy.ops.object.modifier_apply(modifier="Skin")
{apply_mirror}bpy.ops.object.modifier_apply(modifier="Subsurf")

# ---- Smooth shading ----
bpy.ops.object.shade_smooth()

# ---- Vertex groups for rigging ----
names = {names_str}
positions = {verts_str}

for vg_name in names:
    if vg_name not in obj.vertex_groups:
        obj.vertex_groups.new(name=vg_name)

for vi, mv in enumerate(obj.data.vertices):
    vx, vy, vz = mv.co.x, mv.co.y, mv.co.z
    best_dist = float('inf')
    best_name = names[0]
    for si, spos in enumerate(positions):
        dx = vx - spos[0]
        dy = vy - spos[1]
        dz = vz - spos[2]
        d = math.sqrt(dx*dx + dy*dy + dz*dz)
        if d < best_dist:
            best_dist = d
            best_name = names[si]
    vg = obj.vertex_groups.get(best_name)
    if vg is not None:
        weight = max(0.0, 1.0 - best_dist * 5.0)
        if weight > 0.05:
            vg.add([vi], weight, 'ADD')
{brand_group_block}
# ---- Report ----
poly_count = len(obj.data.polygons)
vert_count = len(obj.data.vertices)
quad_count = sum(1 for p in obj.data.polygons if len(p.vertices) == 4)
tri_count = sum(1 for p in obj.data.polygons if len(p.vertices) == 3)

result = {{
    "object_name": {name_literal},
    "monster_type": {monster_type_literal},
    "brand": {brand_literal},
    "scale": {scale},
    "vertex_count": vert_count,
    "polygon_count": poly_count,
    "quad_count": quad_count,
    "tri_count": tri_count,
    "quad_ratio": quad_count / max(poly_count, 1),
    "vertex_group_count": len(obj.vertex_groups),
}}
print("SKIN_MONSTER_RESULT:" + str(result))
'''
    return code


# ---------------------------------------------------------------------------
# Unified body skeletons lookup (for BODY_SKELETONS export)
# ---------------------------------------------------------------------------


BODY_SKELETONS: dict[str, SkeletonDef] = {}

# Pre-compute all 8 humanoid body type skeletons
for _g in VALID_GENDERS:
    for _b in VALID_BUILDS:
        _key = f"{_g}_{_b}"
        BODY_SKELETONS[_key] = get_skeleton(_g, _b)


# ---------------------------------------------------------------------------
# Handler functions (called from Blender addon command dispatch)
# ---------------------------------------------------------------------------


def handle_generate_skin_body(params: dict) -> dict:
    """Generate Blender Python code for Skin Modifier character body.

    Returns the code string plus metadata. The code must be sent to
    blender_execute for actual mesh creation.

    Params:
        gender: 'male' | 'female' (default 'male')
        build: 'heavy' | 'average' | 'slim' | 'elder' (default 'average')
        name: str (object name, default 'CharacterBody')
        subdivision_level: int (1-3, default 2)
    """
    gender = params.get("gender", "male")
    build = params.get("build", "average")
    name = params.get("name", "CharacterBody")
    subdiv = params.get("subdivision_level", 2)

    code = generate_skin_body_code(gender, build, name, subdiv)
    skeleton = get_skeleton(gender, build)

    return {
        "status": "success",
        "code": code,
        "skeleton_vertex_count": len(skeleton["vertices"]),
        "skeleton_edge_count": len(skeleton["edges"]),
        "skeleton_names": skeleton["names"],
        "gender": gender,
        "build": build,
        "name": name,
        "subdivision_level": subdiv,
        "pipeline": "skin_modifier",
        "next_steps": [
            f"Execute the returned code via blender_execute to create '{name}'",
            "Use blender_viewport contact_sheet to verify the result",
            "Proceed to UV unwrap -> texture -> rig -> animate",
        ],
    }


def handle_generate_character_body(params: dict) -> dict:
    """Generate a character body directly as a Blender command.

    This is the handler registered in COMMAND_HANDLERS. It constructs
    the Skin Modifier code and returns it for execution.

    Params:
        gender: 'male' | 'female' (default 'male')
        build: 'heavy' | 'average' | 'slim' | 'elder' (default 'average')
        name: str (object name, default 'CharacterBody')
        subdivision_level: int (1-3, default 2)
        monster_type: str (if set, generates monster body instead)
        scale: float (for monsters, default 1.0)
        brand: str (for monsters, optional VeilBreakers brand)
    """
    monster_type = params.get("monster_type")

    if monster_type:
        # Monster body path
        name = params.get("name", "MonsterBody")
        scale = params.get("scale", 1.0)
        brand = params.get("brand")
        subdiv = params.get("subdivision_level", 2)

        code = generate_skin_monster_code(
            monster_type, name=name, scale=scale,
            brand=brand, subdivision_level=subdiv,
        )
        skeleton = get_monster_skeleton(monster_type, scale=scale, brand=brand)

        return {
            "status": "success",
            "code": code,
            "skeleton_vertex_count": len(skeleton["vertices"]),
            "skeleton_edge_count": len(skeleton["edges"]),
            "skeleton_names": skeleton["names"],
            "monster_type": monster_type,
            "scale": scale,
            "brand": brand,
            "name": name,
            "subdivision_level": subdiv,
            "pipeline": "skin_modifier",
            "next_steps": [
                f"Execute the returned code via blender_execute to create '{name}'",
                "Use blender_viewport contact_sheet to verify the result",
                "Apply brand features if needed",
            ],
        }

    # Humanoid body path
    gender = params.get("gender", "male")
    build = params.get("build", "average")
    name = params.get("name", "CharacterBody")
    subdiv = params.get("subdivision_level", 2)

    return handle_generate_skin_body({
        "gender": gender,
        "build": build,
        "name": name,
        "subdivision_level": subdiv,
    })


# ---------------------------------------------------------------------------
# Skeleton validation utilities (used by tests and pipeline)
# ---------------------------------------------------------------------------


def validate_skeleton_connectivity(skeleton: SkeletonDef) -> list[str]:
    """Check that all vertices are connected (no disconnected components).

    Returns list of error strings (empty = valid).
    """
    n = len(skeleton["vertices"])
    if n == 0:
        return ["Empty skeleton"]

    edges = skeleton["edges"]
    if not edges:
        return ["No edges in skeleton"] if n > 1 else []

    # BFS from vertex 0
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for a, b in edges:
        if a < n and b < n:
            adj[a].append(b)
            adj[b].append(a)

    visited: set[int] = set()
    queue = [0]
    visited.add(0)
    while queue:
        node = queue.pop(0)
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    errors = []
    unvisited = set(range(n)) - visited
    if unvisited:
        unvisited_names = [skeleton["names"][i] for i in sorted(unvisited)]
        errors.append(
            f"Disconnected vertices: {unvisited_names}"
        )
    return errors


def validate_skeleton_symmetry(
    skeleton: SkeletonDef,
    tolerance: float = 0.001,
) -> list[str]:
    """Check left/right mirror symmetry within tolerance.

    Returns list of error strings (empty = symmetric).
    """
    errors = []
    names = skeleton["names"]
    positions = skeleton["vertices"]
    radii = skeleton["radii"]

    # Build name->index map
    name_map: dict[str, int] = {}
    for i, n in enumerate(names):
        name_map[n] = i

    # Find Left/Right pairs
    left_prefixes = ["Left", "L_"]
    right_prefixes = ["Right", "R_"]

    for i, name in enumerate(names):
        mirror_name = None
        for lp, rp in zip(left_prefixes, right_prefixes):
            if name.startswith(lp):
                mirror_name = rp + name[len(lp):]
                break

        if mirror_name and mirror_name in name_map:
            j = name_map[mirror_name]
            px, py, pz = positions[i]
            mx, my, mz = positions[j]

            # X should be negated, Y and Z should match
            if abs(px + mx) > tolerance:
                errors.append(
                    f"X asymmetry: {name} x={px:.4f} vs {mirror_name} x={mx:.4f}"
                )
            if abs(py - my) > tolerance:
                errors.append(
                    f"Y asymmetry: {name} y={py:.4f} vs {mirror_name} y={my:.4f}"
                )
            if abs(pz - mz) > tolerance:
                errors.append(
                    f"Z asymmetry: {name} z={pz:.4f} vs {mirror_name} z={mz:.4f}"
                )

            # Radii should match
            lrx, lry = radii[i]
            mrx, mry = radii[j]
            if abs(lrx - mrx) > tolerance:
                errors.append(
                    f"Radius X asymmetry: {name} rx={lrx:.4f} vs {mirror_name} rx={mrx:.4f}"
                )
            if abs(lry - mry) > tolerance:
                errors.append(
                    f"Radius Y asymmetry: {name} ry={lry:.4f} vs {mirror_name} ry={mry:.4f}"
                )

    return errors


def validate_skeleton_proportions(skeleton: SkeletonDef) -> list[str]:
    """Check basic anatomical proportion rules for humanoid skeletons.

    Returns list of error strings (empty = valid).
    """
    errors = []
    names = skeleton["names"]
    positions = skeleton["vertices"]

    name_map: dict[str, int] = {}
    for i, n in enumerate(names):
        name_map[n] = i

    # Only validate humanoid proportions (need Head and Hips)
    if "Head" not in name_map or "Hips" not in name_map:
        return []  # Not a humanoid skeleton, skip proportion checks

    head_idx = name_map.get("Head")
    head_top_idx = name_map.get("HeadTop")
    hips_idx = name_map.get("Hips")

    if head_idx is not None and hips_idx is not None:
        head_z = positions[head_idx][2]
        hips_z = positions[hips_idx][2]

        # Head should be above hips
        if head_z <= hips_z:
            errors.append(f"Head ({head_z:.3f}) not above Hips ({hips_z:.3f})")

    # Check total height is reasonable for humanoid (~1.5-2.2m)
    if head_top_idx is not None:
        total_height = positions[head_top_idx][2]
        foot_names = [n for n in names if "Foot" in n or "Toe" in n]
        if foot_names:
            min_z = min(positions[name_map[fn]][2] for fn in foot_names)
            body_height = total_height - min_z
            if body_height < 0.5:
                errors.append(f"Body height too short: {body_height:.3f}m")
            if body_height > 3.0:
                errors.append(f"Body height too tall: {body_height:.3f}m")

    # Check arm span vs height (should be roughly similar for humanoid)
    l_hand = name_map.get("LeftHand")
    r_hand = name_map.get("RightHand")
    if l_hand is not None and r_hand is not None and head_top_idx is not None:
        arm_span = abs(positions[l_hand][0] - positions[r_hand][0])
        foot_names = [n for n in names if "Foot" in n or "Toe" in n]
        if foot_names:
            min_z = min(positions[name_map[fn]][2] for fn in foot_names)
            body_height = positions[head_top_idx][2] - min_z
            if body_height > 0:
                ratio = arm_span / body_height
                # Arm span should be 0.5-1.3x height
                if ratio < 0.5:
                    errors.append(f"Arm span too narrow: ratio={ratio:.2f}")
                if ratio > 1.3:
                    errors.append(f"Arm span too wide: ratio={ratio:.2f}")

    return errors
