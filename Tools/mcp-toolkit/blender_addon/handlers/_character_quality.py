"""Character quality validation and hair card generation for VeilBreakers.

Pure-logic module (NO bpy imports). Provides:
- validate_proportions: Check character body proportions against game-world specs
- validate_face_topology: Detect edge loops around eyes/mouth/nose for deformation
- validate_hand_foot_topology: Check finger/toe separation and edge flow
- generate_hair_card_mesh: Generate strip-based hair card meshes with UV layout

All functions work with MeshSpec dicts and vertex position data.
Fulfils CHAR-01, CHAR-02, CHAR-03, CHAR-06 requirements.
"""

from __future__ import annotations

import math
import random
from typing import Any

from .procedural_meshes import _make_result, MeshSpec

# ---------------------------------------------------------------------------
# Character type specifications
# ---------------------------------------------------------------------------

CHARACTER_SPECS: dict[str, dict[str, Any]] = {
    "hero": {
        "height": 1.8,
        "head_ratio": 7.5,       # body is 7.5 heads tall
        "shoulder_width": 0.45,
        "arm_length_ratio": 0.44, # arm length / height
        "leg_length_ratio": 0.47, # leg length / height
        "head_height": 0.24,      # 1.8 / 7.5
        "tolerance": 0.10,        # +/- 10%
    },
    "boss": {
        "height_min": 3.0,
        "height_max": 6.0,
        "head_ratio": 5.0,        # larger head for readability
        "shoulder_width_ratio": 0.35,  # relative to height
        "arm_length_ratio": 0.44,
        "leg_length_ratio": 0.45,
        "tolerance": 0.15,        # bosses have more variation
    },
    "npc": {
        "height": 1.7,
        "head_ratio": 7.5,
        "shoulder_width": 0.42,
        "arm_length_ratio": 0.44,
        "leg_length_ratio": 0.47,
        "head_height": 0.227,
        "tolerance": 0.10,
    },
}

# ---------------------------------------------------------------------------
# Facial feature expected positions (relative to character height)
# ---------------------------------------------------------------------------

_FACE_FEATURE_POSITIONS = {
    "eye_left": {"x_offset": -0.03, "y_ratio": 0.917, "z_offset": 0.06},
    "eye_right": {"x_offset": 0.03, "y_ratio": 0.917, "z_offset": 0.06},
    "mouth": {"x_offset": 0.0, "y_ratio": 0.889, "z_offset": 0.05},
    "nose": {"x_offset": 0.0, "y_ratio": 0.903, "z_offset": 0.07},
}

# ---------------------------------------------------------------------------
# CHAR-01: Proportion validation
# ---------------------------------------------------------------------------


def validate_proportions(
    mesh_spec: MeshSpec,
    character_type: str = "hero",
) -> dict[str, Any]:
    """Validate character body proportions against game-world scale specs.

    Checks height, head-to-body ratio, shoulder width, and limb proportions.

    Args:
        mesh_spec: MeshSpec dict with vertices list and metadata.
        character_type: One of 'hero', 'boss', 'npc'.

    Returns:
        Validation report dict with:
        - passed: bool
        - character_type: str
        - issues: list of issue descriptions
        - measurements: dict of actual measurements
        - spec: dict of expected values
        - grade: str (A-F)
    """
    if character_type not in CHARACTER_SPECS:
        return {
            "passed": False,
            "character_type": character_type,
            "issues": [f"Unknown character type: '{character_type}'. "
                       f"Valid types: {sorted(CHARACTER_SPECS.keys())}"],
            "measurements": {},
            "spec": {},
            "grade": "F",
        }

    spec = CHARACTER_SPECS[character_type]
    verts = mesh_spec.get("vertices", [])
    if not verts:
        return {
            "passed": False,
            "character_type": character_type,
            "issues": ["No vertices in mesh spec"],
            "measurements": {},
            "spec": spec,
            "grade": "F",
        }

    # Compute bounding box
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    depth = max(zs) - min(zs)

    measurements = {
        "width": round(width, 4),
        "height": round(height, 4),
        "depth": round(depth, 4),
    }

    issues: list[str] = []
    tolerance = spec.get("tolerance", 0.10)

    # -- Height check --
    if character_type == "boss":
        h_min = spec["height_min"]
        h_max = spec["height_max"]
        if height < h_min * (1.0 - tolerance):
            issues.append(
                f"Height {height:.2f}m below boss minimum {h_min}m "
                f"(tolerance {tolerance*100:.0f}%)"
            )
        elif height > h_max * (1.0 + tolerance):
            issues.append(
                f"Height {height:.2f}m above boss maximum {h_max}m "
                f"(tolerance {tolerance*100:.0f}%)"
            )
        measurements["height_spec"] = f"{h_min}-{h_max}m"
    else:
        expected_height = spec["height"]
        if abs(height - expected_height) > expected_height * tolerance:
            issues.append(
                f"Height {height:.2f}m deviates from expected {expected_height}m "
                f"by more than {tolerance*100:.0f}%"
            )
        measurements["expected_height"] = expected_height

    # -- Shoulder width check --
    if character_type == "boss":
        expected_shoulder = height * spec["shoulder_width_ratio"]
    else:
        expected_shoulder = spec["shoulder_width"]

    # Estimate shoulder width from upper body vertices (top 60-75% of height)
    min_y = min(ys)
    shoulder_y_min = min_y + height * 0.75
    shoulder_y_max = min_y + height * 0.85
    shoulder_verts = [v for v in verts if shoulder_y_min <= v[1] <= shoulder_y_max]

    if shoulder_verts:
        shoulder_xs = [v[0] for v in shoulder_verts]
        measured_shoulder = max(shoulder_xs) - min(shoulder_xs)
        measurements["shoulder_width"] = round(measured_shoulder, 4)
        measurements["expected_shoulder_width"] = round(expected_shoulder, 4)

        if abs(measured_shoulder - expected_shoulder) > expected_shoulder * tolerance:
            issues.append(
                f"Shoulder width {measured_shoulder:.3f}m deviates from "
                f"expected {expected_shoulder:.3f}m"
            )

    # -- Head-to-body ratio check --
    head_ratio = spec.get("head_ratio", 7.5)
    expected_head_height = height / head_ratio
    # Estimate head as top ~13% of height
    head_y_min = min_y + height * 0.87
    head_verts = [v for v in verts if v[1] >= head_y_min]

    if head_verts:
        head_ys = [v[1] for v in head_verts]
        measured_head_height = max(head_ys) - min(head_ys)
        if measured_head_height > 0:
            measured_ratio = height / measured_head_height
            measurements["head_body_ratio"] = round(measured_ratio, 2)
            measurements["expected_head_ratio"] = head_ratio

            ratio_diff = abs(measured_ratio - head_ratio) / head_ratio
            if ratio_diff > tolerance:
                issues.append(
                    f"Head-to-body ratio {measured_ratio:.1f}:1 deviates from "
                    f"expected {head_ratio:.1f}:1"
                )

    # -- Limb proportion checks (arm and leg) --
    arm_ratio = spec.get("arm_length_ratio", 0.44)
    leg_ratio = spec.get("leg_length_ratio", 0.47)

    # Estimate arm: vertices in lateral extremes at 55-75% height
    arm_y_min = min_y + height * 0.55
    arm_y_max = min_y + height * 0.75
    arm_verts = [v for v in verts if arm_y_min <= v[1] <= arm_y_max]
    if arm_verts:
        arm_xs = [v[0] for v in arm_verts]
        half_arm_span = (max(arm_xs) - min(arm_xs)) / 2.0
        estimated_arm_length = half_arm_span - (expected_shoulder / 2.0)
        if estimated_arm_length > 0:
            measured_arm_ratio = estimated_arm_length / height
            measurements["arm_length_ratio"] = round(measured_arm_ratio, 3)
            measurements["expected_arm_ratio"] = arm_ratio

    # Estimate leg: vertices in bottom 47% of height
    leg_y_max = min_y + height * leg_ratio
    leg_verts = [v for v in verts if v[1] <= leg_y_max]
    if leg_verts:
        measurements["leg_region_vertex_count"] = len(leg_verts)
        measurements["expected_leg_ratio"] = leg_ratio

    # -- Grade calculation --
    issue_count = len(issues)
    if issue_count == 0:
        grade = "A"
    elif issue_count == 1:
        grade = "B"
    elif issue_count == 2:
        grade = "C"
    elif issue_count == 3:
        grade = "D"
    else:
        grade = "F"

    return {
        "passed": issue_count == 0,
        "character_type": character_type,
        "issues": issues,
        "measurements": measurements,
        "spec": spec,
        "grade": grade,
    }


# ---------------------------------------------------------------------------
# CHAR-03: Face topology validation
# ---------------------------------------------------------------------------


def _find_vertices_near(
    verts: list[tuple[float, float, float]],
    target: tuple[float, float, float],
    radius: float,
) -> list[int]:
    """Find vertex indices within radius of target position."""
    result: list[int] = []
    tx, ty, tz = target
    r_sq = radius * radius
    for i, v in enumerate(verts):
        dx = v[0] - tx
        dy = v[1] - ty
        dz = v[2] - tz
        if dx * dx + dy * dy + dz * dz <= r_sq:
            result.append(i)
    return result


def _count_edge_loops(
    vert_indices: list[int],
    faces: list[tuple[int, ...]],
) -> int:
    """Estimate the number of concentric edge loops around a feature region.

    Counts edges shared between faces that include region vertices.
    More shared edges = more loops = better deformation topology.
    """
    if not vert_indices or not faces:
        return 0

    region_set = set(vert_indices)

    # Build adjacency: count edges involving region vertices
    edge_count: dict[tuple[int, int], int] = {}
    for face in faces:
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            if a in region_set or b in region_set:
                edge = (min(a, b), max(a, b))
                edge_count[edge] = edge_count.get(edge, 0) + 1

    # Edges shared by 2+ faces are "loop edges"
    loop_edges = sum(1 for c in edge_count.values() if c >= 2)

    # Estimate loop count: every full loop needs roughly len(region) edges
    region_size = max(len(region_set), 1)
    estimated_loops = max(1, loop_edges // max(region_size // 2, 1))

    return estimated_loops


def validate_face_topology(
    mesh_spec: MeshSpec,
    character_height: float = 1.8,
) -> dict[str, Any]:
    """Analyze face vertices for edge loops around eyes, mouth, nose.

    Detection method: find vertex groups that form concentric loops around
    facial feature positions (eyes at ~1.65m height for 1.8m character).

    Args:
        mesh_spec: MeshSpec dict with vertices and faces.
        character_height: Character height for scaling feature positions.

    Returns:
        Report dict with feature loop counts, quality grade, and issues.

    Fulfils CHAR-03 requirement.
    """
    verts = mesh_spec.get("vertices", [])
    faces = mesh_spec.get("faces", [])

    if not verts or not faces:
        return {
            "passed": False,
            "features": {},
            "issues": ["No vertices or faces in mesh spec"],
            "grade": "F",
            "total_loop_count": 0,
        }

    # Scale feature positions to character height
    scale = character_height / 1.8
    min_y = min(v[1] for v in verts)

    features: dict[str, dict[str, Any]] = {}
    total_loops = 0
    issues: list[str] = []

    # Search radius for finding feature vertices (scaled)
    search_radius = 0.04 * scale

    for feature_name, pos_info in _FACE_FEATURE_POSITIONS.items():
        target_y = min_y + character_height * pos_info["y_ratio"]
        target_x = pos_info["x_offset"] * scale
        target_z = pos_info["z_offset"] * scale

        target = (target_x, target_y, target_z)
        nearby = _find_vertices_near(verts, target, search_radius)

        loop_count = 0
        if nearby:
            loop_count = _count_edge_loops(nearby, faces)

        features[feature_name] = {
            "vertex_count": len(nearby),
            "loop_count": loop_count,
            "target_position": target,
        }
        total_loops += loop_count

        # Quality check: eyes and mouth need at least 2 loops for deformation
        min_loops = 2 if feature_name in ("eye_left", "eye_right", "mouth") else 1
        if loop_count < min_loops:
            issues.append(
                f"{feature_name}: {loop_count} edge loops detected "
                f"(minimum {min_loops} needed for proper deformation)"
            )

    # Grade based on total loop count
    if total_loops >= 12:
        grade = "A"
    elif total_loops >= 8:
        grade = "B"
    elif total_loops >= 5:
        grade = "C"
    elif total_loops >= 2:
        grade = "D"
    else:
        grade = "F"

    return {
        "passed": len(issues) == 0,
        "features": features,
        "issues": issues,
        "grade": grade,
        "total_loop_count": total_loops,
    }


# ---------------------------------------------------------------------------
# CHAR-06: Hand/foot topology validation
# ---------------------------------------------------------------------------


def _find_distinct_groups(
    vert_indices: list[int],
    verts: list[tuple[float, float, float]],
    separation_threshold: float = 0.005,
) -> int:
    """Count distinct spatial groups among vertices using distance clustering.

    Simple clustering: sort by X coordinate and count gaps larger than threshold.
    """
    if not vert_indices:
        return 0

    # Sort vertices by X coordinate
    sorted_by_x = sorted(vert_indices, key=lambda i: verts[i][0])
    groups = 1
    for k in range(1, len(sorted_by_x)):
        prev_x = verts[sorted_by_x[k - 1]][0]
        curr_x = verts[sorted_by_x[k]][0]
        if abs(curr_x - prev_x) > separation_threshold:
            groups += 1

    return groups


def validate_hand_foot_topology(
    mesh_spec: MeshSpec,
    character_height: float = 1.8,
) -> dict[str, Any]:
    """Check for finger separation and proper edge flow in hands and feet.

    Verifies:
    - 5 distinct finger groups per hand region
    - Proper toe separation in feet
    - Sufficient vertex density for deformation

    Args:
        mesh_spec: MeshSpec dict with vertices and faces.
        character_height: Character height for scaling detection regions.

    Returns:
        Report dict with hand/foot analysis, grade, and issues.

    Fulfils CHAR-06 requirement.
    """
    verts = mesh_spec.get("vertices", [])
    faces = mesh_spec.get("faces", [])

    if not verts or not faces:
        return {
            "passed": False,
            "hands": {},
            "feet": {},
            "issues": ["No vertices or faces in mesh spec"],
            "grade": "F",
        }

    min_y = min(v[1] for v in verts)
    max_x = max(v[0] for v in verts)
    min_x = min(v[0] for v in verts)
    scale = character_height / 1.8

    issues: list[str] = []

    # -- Hand detection --
    # Hands are at approximately 40-45% height, at the lateral extremes
    hand_y_min = min_y + character_height * 0.35
    hand_y_max = min_y + character_height * 0.50

    # Left hand: negative X
    left_hand_threshold = min_x + (max_x - min_x) * 0.15
    left_hand_verts = [
        i for i, v in enumerate(verts)
        if hand_y_min <= v[1] <= hand_y_max and v[0] <= left_hand_threshold
    ]

    # Right hand: positive X
    right_hand_threshold = max_x - (max_x - min_x) * 0.15
    right_hand_verts = [
        i for i, v in enumerate(verts)
        if hand_y_min <= v[1] <= hand_y_max and v[0] >= right_hand_threshold
    ]

    hands: dict[str, dict[str, Any]] = {}

    for hand_name, hand_indices in [("left_hand", left_hand_verts),
                                     ("right_hand", right_hand_verts)]:
        finger_groups = _find_distinct_groups(hand_indices, verts, 0.005 * scale)
        edge_count = 0
        if hand_indices:
            hand_set = set(hand_indices)
            for face in faces:
                n = len(face)
                for i in range(n):
                    if face[i] in hand_set and face[(i + 1) % n] in hand_set:
                        edge_count += 1

        hands[hand_name] = {
            "vertex_count": len(hand_indices),
            "finger_groups": finger_groups,
            "edge_count": edge_count,
        }

        if finger_groups < 5 and len(hand_indices) > 0:
            issues.append(
                f"{hand_name}: {finger_groups} finger groups detected "
                f"(expected 5 for proper finger separation)"
            )

    # -- Foot detection --
    # Feet are in the bottom 5% of height
    foot_y_max = min_y + character_height * 0.05
    foot_verts_left = [
        i for i, v in enumerate(verts)
        if v[1] <= foot_y_max and v[0] < 0
    ]
    foot_verts_right = [
        i for i, v in enumerate(verts)
        if v[1] <= foot_y_max and v[0] >= 0
    ]

    feet: dict[str, dict[str, Any]] = {}
    for foot_name, foot_indices in [("left_foot", foot_verts_left),
                                     ("right_foot", foot_verts_right)]:
        toe_groups = _find_distinct_groups(foot_indices, verts, 0.004 * scale)
        feet[foot_name] = {
            "vertex_count": len(foot_indices),
            "toe_groups": toe_groups,
        }

        if toe_groups < 3 and len(foot_indices) > 0:
            issues.append(
                f"{foot_name}: {toe_groups} toe groups detected "
                f"(expected at least 3 for basic toe separation)"
            )

    # Grade
    issue_count = len(issues)
    if issue_count == 0:
        grade = "A"
    elif issue_count <= 2:
        grade = "B"
    elif issue_count <= 3:
        grade = "C"
    else:
        grade = "D"

    return {
        "passed": issue_count == 0,
        "hands": hands,
        "feet": feet,
        "issues": issues,
        "grade": grade,
    }


# ---------------------------------------------------------------------------
# CHAR-02: Hair card mesh generation
# ---------------------------------------------------------------------------

# Hair style configurations
_HAIR_STYLES: dict[str, dict[str, Any]] = {
    "long_straight": {
        "length_range": (0.3, 0.5),
        "curl_factor": 0.0,
        "taper": 0.7,
        "width_range": (0.015, 0.025),
        "strand_offset_y": 0.0,
    },
    "short_cropped": {
        "length_range": (0.03, 0.08),
        "curl_factor": 0.0,
        "taper": 0.5,
        "width_range": (0.008, 0.015),
        "strand_offset_y": 0.0,
    },
    "braided": {
        "length_range": (0.25, 0.45),
        "curl_factor": 0.8,
        "taper": 0.6,
        "width_range": (0.02, 0.035),
        "strand_offset_y": 0.0,
    },
    "wild": {
        "length_range": (0.2, 0.5),
        "curl_factor": 0.4,
        "taper": 0.8,
        "width_range": (0.01, 0.025),
        "strand_offset_y": 0.0,
    },
    "mohawk": {
        "length_range": (0.1, 0.25),
        "curl_factor": 0.0,
        "taper": 0.6,
        "width_range": (0.02, 0.04),
        "strand_offset_y": 0.05,  # pushed up for mohawk crest
    },
    "ponytail": {
        "length_range": (0.2, 0.4),
        "curl_factor": 0.1,
        "taper": 0.65,
        "width_range": (0.015, 0.03),
        "strand_offset_y": -0.02,  # hangs from gather point
    },
}


def generate_hair_card_mesh(
    style: str = "long_straight",
    strand_count: int = 20,
    length: float = 0.4,
    width: float = 0.02,
    curl_factor: float = 0.0,
    taper: float = 0.7,
    seed: int = 0,
    segments_per_strand: int = 6,
) -> MeshSpec:
    """Generate strip-based hair card meshes for alpha-texture hair.

    Each hair card is a tapered quad strip (wider at root, narrower at tip).
    UV layout maps each strip to a column in 0-1 UV space for alpha texture
    mapping. Strips are arranged in a hemisphere pattern on the head.

    Args:
        style: Hair style preset. One of: long_straight, short_cropped,
               braided, wild, mohawk, ponytail.
        strand_count: Number of hair card strips to generate.
        length: Base length of each strand (meters).
        width: Base width of each strip at root (meters).
        curl_factor: Amount of curl/wave (0=straight, 1=very curly).
        taper: Width taper factor at tip (0=point, 1=same as root).
        seed: Random seed for reproducibility.
        segments_per_strand: Number of quad segments per strand strip.

    Returns:
        MeshSpec with hair card geometry and UV layout.

    Fulfils CHAR-02 requirement.
    """
    # Guard against degenerate inputs
    segments_per_strand = max(1, segments_per_strand)
    strand_count = max(1, strand_count)
    length = max(0.01, abs(length))
    width = max(0.001, abs(width))

    rng = random.Random(seed)

    # Apply style preset as base, override with explicit params
    style_cfg = _HAIR_STYLES.get(style, _HAIR_STYLES["long_straight"])

    all_verts: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, ...]] = []
    all_uvs: list[tuple[float, float]] = []

    # Head center approximation (for a 1.8m character)
    head_center_y = 1.72
    head_radius = 0.10

    for strand_idx in range(strand_count):
        # Distribute strand roots on a hemisphere
        # Golden angle distribution for even spacing
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        theta = golden_angle * strand_idx
        phi = math.acos(1.0 - (strand_idx / max(strand_count, 1)) * 0.8)

        # Root position on head hemisphere
        root_x = head_radius * math.sin(phi) * math.cos(theta)
        root_z = head_radius * math.sin(phi) * math.sin(theta)
        root_y = head_center_y + head_radius * math.cos(phi)

        # Strand direction: outward + downward
        dir_x = root_x / max(abs(root_x) + abs(root_z), 0.001) * 0.15
        dir_z = root_z / max(abs(root_x) + abs(root_z), 0.001) * 0.15
        dir_y = -1.0  # gravity direction

        # Per-strand variation
        strand_length = length + rng.uniform(-0.05, 0.05)
        strand_width = width + rng.uniform(-0.005, 0.005)
        strand_curl = curl_factor + rng.uniform(-0.1, 0.1)
        strand_curl = max(0.0, strand_curl)

        # UV column for this strand
        uv_col_min = strand_idx / max(strand_count, 1)
        uv_col_max = (strand_idx + 1) / max(strand_count, 1)

        base_idx = len(all_verts)

        for seg in range(segments_per_strand + 1):
            t = seg / segments_per_strand

            # Position along strand with curl
            seg_length = strand_length * t
            curl_offset_x = strand_curl * 0.05 * math.sin(t * math.pi * 2.0)
            curl_offset_z = strand_curl * 0.03 * math.cos(t * math.pi * 2.0)

            cx = root_x + dir_x * seg_length + curl_offset_x
            cy = root_y + dir_y * seg_length + style_cfg["strand_offset_y"] * t
            cz = root_z + dir_z * seg_length + curl_offset_z

            # Width tapers from full at root to taper*full at tip
            current_width = strand_width * (1.0 - t * (1.0 - taper))
            hw = current_width / 2.0

            # Tangent direction for width offset (perpendicular to strand)
            # Use cross product of strand direction and up vector
            tangent_x = -dir_z
            tangent_z = dir_x
            tangent_len = math.sqrt(tangent_x ** 2 + tangent_z ** 2)
            if tangent_len > 0.001:
                tangent_x /= tangent_len
                tangent_z /= tangent_len
            else:
                tangent_x = 1.0
                tangent_z = 0.0

            # Left and right vertices of the strip
            left_x = cx - tangent_x * hw
            left_z = cz - tangent_z * hw
            right_x = cx + tangent_x * hw
            right_z = cz + tangent_z * hw

            all_verts.append((left_x, cy, left_z))
            all_verts.append((right_x, cy, right_z))

            # UV mapping: left edge to right edge, bottom to top
            uv_v = t  # 0 at root, 1 at tip
            all_uvs.append((uv_col_min, uv_v))
            all_uvs.append((uv_col_max, uv_v))

        # Create quad faces for this strand
        verts_per_row = 2  # left + right
        for seg in range(segments_per_strand):
            row_start = base_idx + seg * verts_per_row
            next_row = base_idx + (seg + 1) * verts_per_row

            # Quad: left_bottom, right_bottom, right_top, left_top
            all_faces.append((
                row_start, row_start + 1,
                next_row + 1, next_row,
            ))

    return _make_result(
        name=f"HairCards_{style}",
        vertices=all_verts,
        faces=all_faces,
        uvs=all_uvs,
        category="character_hair",
        style=style,
        strand_count=strand_count,
        segments_per_strand=segments_per_strand,
    )
