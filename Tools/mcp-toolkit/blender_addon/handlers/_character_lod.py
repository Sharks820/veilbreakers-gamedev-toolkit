"""Character-aware LOD retopology and armor seam ring generation.

Pure-logic module (NO bpy imports). Provides:
- character_aware_lod: LOD chain that preserves face/hand detail while reducing body
- generate_seam_ring: Thin overlap ring meshes for hiding armor seam gaps

All functions return MeshSpec dicts compatible with procedural_meshes.
Fulfils CHAR-04 and CHAR-05 requirements.
"""

from __future__ import annotations

import math
from typing import Any

from .procedural_meshes import _make_result, MeshSpec

# ---------------------------------------------------------------------------
# CHAR-04: Character-aware LOD retopology
# ---------------------------------------------------------------------------

# Vertex importance weights by body region (Y-ratio ranges)
# Higher weight = more likely to be preserved during decimation
_REGION_WEIGHTS: dict[str, dict[str, Any]] = {
    "face": {"y_min": 0.87, "y_max": 1.00, "weight": 3.0},
    "hands": {"y_min": 0.35, "y_max": 0.50, "x_threshold": 0.70, "weight": 2.0},
    "feet": {"y_min": 0.00, "y_max": 0.05, "weight": 1.5},
    "body": {"y_min": 0.05, "y_max": 0.87, "weight": 1.0},
}


def _compute_vertex_importance(
    verts: list[tuple[float, float, float]],
    character_type: str = "hero",
) -> list[float]:
    """Compute importance weight per vertex based on body region.

    Face vertices get 3x weight, hands 2x, feet 1.5x, body 1.0x.
    For bosses, head importance is even higher (readability at distance).

    Args:
        verts: List of vertex positions.
        character_type: One of 'hero', 'boss', 'npc'.

    Returns:
        List of importance weights (one per vertex).
    """
    if not verts:
        return []

    ys = [v[1] for v in verts]
    xs = [v[0] for v in verts]
    min_y = min(ys)
    max_y = max(ys)
    height = max_y - min_y
    if height <= 0:
        return [1.0] * len(verts)

    min_x = min(xs)
    max_x = max(xs)
    width = max_x - min_x
    x_mid = (min_x + max_x) / 2.0

    # Boss face importance is boosted for readability
    face_weight = 4.0 if character_type == "boss" else 3.0

    weights: list[float] = []
    for v in verts:
        y_ratio = (v[1] - min_y) / height
        x_ratio = abs(v[0] - x_mid) / max(width / 2.0, 0.001)

        if y_ratio >= _REGION_WEIGHTS["face"]["y_min"]:
            weights.append(face_weight)
        elif (
            _REGION_WEIGHTS["hands"]["y_min"] <= y_ratio <= _REGION_WEIGHTS["hands"]["y_max"]
            and x_ratio >= _REGION_WEIGHTS["hands"]["x_threshold"]
        ):
            weights.append(_REGION_WEIGHTS["hands"]["weight"])
        elif y_ratio <= _REGION_WEIGHTS["feet"]["y_max"]:
            weights.append(_REGION_WEIGHTS["feet"]["weight"])
        else:
            weights.append(_REGION_WEIGHTS["body"]["weight"])

    return weights


def _compute_face_importance(
    faces: list[tuple[int, ...]],
    vertex_weights: list[float],
) -> list[float]:
    """Compute importance for each face as average of its vertex weights."""
    face_importance: list[float] = []
    for face in faces:
        if not face:
            face_importance.append(0.0)
            continue
        valid = [vertex_weights[i] for i in face if i < len(vertex_weights)]
        avg = sum(valid) / max(len(valid), 1)
        face_importance.append(avg)
    return face_importance


def character_aware_lod(
    mesh_spec: MeshSpec,
    character_type: str = "hero",
    lod_ratios: list[float] | None = None,
) -> list[MeshSpec]:
    """Generate LOD chain that preserves face/hand detail.

    Vertex importance: face=3x, hand=2x, feet=1.5x weight.
    Decimation preferentially removes lower-importance body/extremity faces.

    Args:
        mesh_spec: Source MeshSpec with vertices, faces, uvs, metadata.
        character_type: One of 'hero', 'boss', 'npc'.
        lod_ratios: Decimation ratios per LOD. Default [1.0, 0.5, 0.25].

    Returns:
        List of MeshSpec dicts, one per LOD level, with metadata names
        suffixed _LOD0, _LOD1, _LOD2 etc.

    Fulfils CHAR-04 requirement.
    """
    if lod_ratios is None:
        lod_ratios = [1.0, 0.5, 0.25]

    verts = mesh_spec.get("vertices", [])
    faces = mesh_spec.get("faces", [])
    uvs = mesh_spec.get("uvs", [])
    base_name = mesh_spec.get("metadata", {}).get("name", "Character")

    if not verts or not faces:
        return []

    # Compute vertex importance
    vertex_weights = _compute_vertex_importance(verts, character_type)
    face_importance = _compute_face_importance(faces, vertex_weights)

    # Sort face indices by importance (ascending = least important first)
    sorted_face_indices = sorted(
        range(len(faces)),
        key=lambda i: face_importance[i],
    )

    total_faces = len(faces)
    lod_specs: list[MeshSpec] = []

    for level, ratio in enumerate(lod_ratios):
        keep_count = max(1, int(math.ceil(total_faces * ratio)))
        keep_count = min(keep_count, total_faces)

        if ratio >= 1.0:
            # LOD0: keep all faces
            kept_face_indices = list(range(total_faces))
        else:
            # Remove least important faces first
            remove_count = total_faces - keep_count
            removed_set = set(sorted_face_indices[:remove_count])
            kept_face_indices = [
                i for i in range(total_faces) if i not in removed_set
            ]

        # Build kept faces and compact vertices
        kept_faces = [faces[i] for i in kept_face_indices]
        used_vert_indices = sorted(set(idx for face in kept_faces for idx in face))
        index_remap = {old: new for new, old in enumerate(used_vert_indices)}
        lod_verts = [verts[i] for i in used_vert_indices]
        lod_faces = [
            tuple(index_remap[i] for i in face) for face in kept_faces
        ]

        # Remap UVs based on format
        lod_uvs: list[tuple[float, float]] = []
        if uvs:
            if len(uvs) == len(verts):
                # Per-vertex UVs: remap to compacted vertices
                lod_uvs = [uvs[i] for i in used_vert_indices]
            else:
                # Per-face-corner UVs: keep only UVs for kept faces
                # Each face contributes len(face) UV entries in order
                uv_offset = 0
                for fi in range(len(faces)):
                    face_uv_count = len(faces[fi])
                    if fi in set(kept_face_indices):
                        lod_uvs.extend(uvs[uv_offset:uv_offset + face_uv_count])
                    uv_offset += face_uv_count

        lod_spec: MeshSpec = {
            "vertices": lod_verts,
            "faces": lod_faces,
            "uvs": lod_uvs if lod_uvs else [],
            "metadata": {
                **mesh_spec.get("metadata", {}),
                "name": f"{base_name}_LOD{level}",
                "poly_count": len(lod_faces),
                "vertex_count": len(lod_verts),
                "lod_level": level,
                "lod_ratio": ratio,
                "character_type": character_type,
            },
        }
        lod_specs.append(lod_spec)

    return lod_specs


# ---------------------------------------------------------------------------
# CHAR-05: Armor seam ring generation
# ---------------------------------------------------------------------------

# Joint type specifications: position and typical radius
_JOINT_SPECS: dict[str, dict[str, float]] = {
    "neck": {"y_ratio": 0.87, "x_offset": 0.0, "default_inner": 0.055, "default_outer": 0.075},
    "wrist_l": {"y_ratio": 0.42, "x_offset": -0.30, "default_inner": 0.025, "default_outer": 0.035},
    "wrist_r": {"y_ratio": 0.42, "x_offset": 0.30, "default_inner": 0.025, "default_outer": 0.035},
    "ankle_l": {"y_ratio": 0.06, "x_offset": -0.10, "default_inner": 0.035, "default_outer": 0.050},
    "ankle_r": {"y_ratio": 0.06, "x_offset": 0.10, "default_inner": 0.035, "default_outer": 0.050},
    "waist": {"y_ratio": 0.50, "x_offset": 0.0, "default_inner": 0.15, "default_outer": 0.18},
    "upper_arm_l": {"y_ratio": 0.75, "x_offset": -0.22, "default_inner": 0.04, "default_outer": 0.055},
    "upper_arm_r": {"y_ratio": 0.75, "x_offset": 0.22, "default_inner": 0.04, "default_outer": 0.055},
}


def generate_seam_ring(
    joint_type: str = "neck",
    inner_radius: float | None = None,
    outer_radius: float | None = None,
    segments: int = 16,
    height: float = 0.02,
    character_height: float = 1.8,
    seed: int = 0,
) -> MeshSpec:
    """Generate a thin overlap ring mesh for hiding armor seam gaps.

    Creates a torus-slice ring that conforms to the joint's typical radius.
    Placed at the correct Y position for the specified joint type.

    Args:
        joint_type: Joint location. One of: neck, wrist_l, wrist_r,
                    ankle_l, ankle_r, waist, upper_arm_l, upper_arm_r.
        inner_radius: Inner radius of the ring. None = use default for joint.
        outer_radius: Outer radius of the ring. None = use default for joint.
        segments: Number of segments around the ring circumference.
        height: Vertical height (thickness) of the ring.
        character_height: Character height for positioning.
        seed: Random seed for reproducibility.

    Returns:
        MeshSpec with seam ring geometry.

    Fulfils CHAR-05 requirement.
    """
    joint_spec = _JOINT_SPECS.get(joint_type)
    if joint_spec is None:
        # Default to neck if unknown joint type
        joint_spec = _JOINT_SPECS["neck"]

    r_inner = inner_radius if inner_radius is not None else joint_spec["default_inner"]
    r_outer = outer_radius if outer_radius is not None else joint_spec["default_outer"]

    # Position the ring at the joint location
    ring_y = character_height * joint_spec["y_ratio"]
    ring_x = joint_spec["x_offset"]

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    half_h = height / 2.0

    # Generate two concentric rings at top and bottom of the height
    # Inner ring bottom, inner ring top, outer ring bottom, outer ring top
    for ring_idx, (r, y_off) in enumerate([
        (r_inner, -half_h),
        (r_inner, half_h),
        (r_outer, -half_h),
        (r_outer, half_h),
    ]):
        for seg in range(segments):
            angle = 2.0 * math.pi * seg / segments
            x = ring_x + r * math.cos(angle)
            z = r * math.sin(angle)
            y = ring_y + y_off

            vertices.append((x, y, z))

            # UV mapping: u = angle fraction, v = ring index
            uv_u = seg / segments
            uv_v = ring_idx / 3.0
            uvs.append((uv_u, uv_v))

    # Face indices for the 4 rings of vertices
    ib = 0             # inner bottom
    it = segments      # inner top
    ob = 2 * segments  # outer bottom
    ot = 3 * segments  # outer top

    for seg in range(segments):
        s2 = (seg + 1) % segments

        # Inner wall (inner bottom to inner top)
        faces.append((ib + seg, ib + s2, it + s2, it + seg))

        # Outer wall (outer bottom to outer top)
        faces.append((ob + seg, ot + seg, ot + s2, ob + s2))

        # Top face (inner top to outer top)
        faces.append((it + seg, it + s2, ot + s2, ot + seg))

        # Bottom face (inner bottom to outer bottom)
        faces.append((ib + seg, ob + seg, ob + s2, ib + s2))

    return _make_result(
        name=f"SeamRing_{joint_type}",
        vertices=vertices,
        faces=faces,
        uvs=uvs,
        category="armor_seam",
        joint_type=joint_type,
        inner_radius=r_inner,
        outer_radius=r_outer,
        segments=segments,
        ring_height=height,
    )
