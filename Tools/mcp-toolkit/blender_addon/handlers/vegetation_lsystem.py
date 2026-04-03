"""L-System vegetation pipeline for VeilBreakers dark fantasy environments.

Provides procedural tree generation using Lindenmayer systems, leaf card
placement, wind vertex color baking for Unity shaders, billboard impostor
mesh generation, and GPU instancing export preparation.

All core functions are pure-logic (no bpy dependency) for testability.
Handler functions that create Blender objects import bpy only at call time.

Gap coverage: #54 (L-system trees), #29 (botanical accuracy), #37 (tree
variety), #55 (wind vertex colors), #56 (billboard impostors),
#19/item44 (GPU instancing).
"""

from __future__ import annotations

import json
import math
import random as _random
from typing import Any


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vec3 = tuple[float, float, float]
MeshSpec = dict[str, Any]


# ---------------------------------------------------------------------------
# L-System grammar definitions per tree type
# ---------------------------------------------------------------------------

LSYSTEM_GRAMMARS: dict[str, dict[str, Any]] = {
    "oak": {
        "axiom": "F",
        "rules": {"F": "FF[+F][-F]F[+F]"},
        "default_iterations": 5,
        "branch_angle": 25.0,
        "branch_ratio": 0.7,
        "trunk_ratio": 0.85,
        "gravity": 0.1,
        "randomness": 0.2,
        "leaf_density": 0.8,
        "description": "Broad, spreading canopy with thick trunk",
    },
    "pine": {
        "axiom": "F",
        "rules": {"F": "FF[++F][--F][+F][-F]"},
        "default_iterations": 5,
        "branch_angle": 30.0,
        "branch_ratio": 0.6,
        "trunk_ratio": 0.9,
        "gravity": 0.05,
        "randomness": 0.1,
        "leaf_density": 0.9,
        "description": "Tall conical shape with regular branch whorls",
    },
    "birch": {
        "axiom": "F",
        "rules": {"F": "F[+F]F[-F]"},
        "default_iterations": 6,
        "branch_angle": 20.0,
        "branch_ratio": 0.65,
        "trunk_ratio": 0.88,
        "gravity": 0.15,
        "randomness": 0.15,
        "leaf_density": 0.7,
        "description": "Slender trunk with delicate branching",
    },
    "willow": {
        "axiom": "F",
        "rules": {"F": "F[+F][-F][+F][-F]"},
        "default_iterations": 5,
        "branch_angle": 35.0,
        "branch_ratio": 0.75,
        "trunk_ratio": 0.8,
        "gravity": 0.6,
        "randomness": 0.2,
        "leaf_density": 0.85,
        "description": "Heavy drooping branches, weeping form",
    },
    "dead": {
        "axiom": "F",
        "rules": {"F": "F[+F][-F]"},
        "default_iterations": 5,
        "branch_angle": 30.0,
        "branch_ratio": 0.6,
        "trunk_ratio": 0.82,
        "gravity": 0.05,
        "randomness": 0.4,
        "leaf_density": 0.0,
        "description": "Bare twisted branches, no foliage",
    },
    "ancient": {
        "axiom": "F",
        "rules": {"F": "FF[+F][-F]F[+F][-F]"},
        "default_iterations": 4,
        "branch_angle": 22.0,
        "branch_ratio": 0.75,
        "trunk_ratio": 0.8,
        "gravity": 0.15,
        "randomness": 0.25,
        "leaf_density": 0.6,
        "description": "Massive gnarled trunk, thick sprawling branches",
    },
    "twisted": {
        "axiom": "F",
        "rules": {"F": "F[++F][--F]"},
        "default_iterations": 6,
        "branch_angle": 40.0,
        "branch_ratio": 0.65,
        "trunk_ratio": 0.85,
        "gravity": 0.1,
        "randomness": 0.5,
        "leaf_density": 0.3,
        "description": "Wind-swept asymmetric form, sparse foliage",
    },
}


# ---------------------------------------------------------------------------
# L-System string expansion
# ---------------------------------------------------------------------------

def expand_lsystem(
    axiom: str,
    rules: dict[str, str],
    iterations: int,
) -> str:
    """Expand an L-system grammar for a given number of iterations.

    Args:
        axiom: Starting string (e.g., 'F').
        rules: Production rules mapping characters to replacement strings.
        iterations: Number of expansion iterations.

    Returns:
        Expanded L-system string.
    """
    current = axiom
    for _ in range(iterations):
        next_str: list[str] = []
        for ch in current:
            next_str.append(rules.get(ch, ch))
        current = "".join(next_str)
    return current


# ---------------------------------------------------------------------------
# Turtle interpreter -- converts L-system string to branch segments
# ---------------------------------------------------------------------------

def _rotate_vector(
    vx: float, vy: float, vz: float,
    axis_x: float, axis_y: float, axis_z: float,
    angle_rad: float,
) -> tuple[float, float, float]:
    """Rotate vector (vx, vy, vz) around axis by angle using Rodrigues' formula."""
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Normalize axis
    al = math.sqrt(axis_x ** 2 + axis_y ** 2 + axis_z ** 2)
    if al < 1e-12:
        return (vx, vy, vz)
    ax, ay, az = axis_x / al, axis_y / al, axis_z / al

    # Rodrigues' rotation
    dot = vx * ax + vy * ay + vz * az
    cross_x = ay * vz - az * vy
    cross_y = az * vx - ax * vz
    cross_z = ax * vy - ay * vx

    rx = vx * cos_a + cross_x * sin_a + ax * dot * (1.0 - cos_a)
    ry = vy * cos_a + cross_y * sin_a + ay * dot * (1.0 - cos_a)
    rz = vz * cos_a + cross_z * sin_a + az * dot * (1.0 - cos_a)

    return (rx, ry, rz)


class _TurtleState:
    """Turtle state for L-system interpretation."""
    __slots__ = ("x", "y", "z", "dx", "dy", "dz", "radius", "depth",
                 "right_x", "right_y", "right_z")

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        # Direction (initially pointing up: +Z)
        self.dx = 0.0
        self.dy = 0.0
        self.dz = 1.0
        # Right vector (initially +X)
        self.right_x = 1.0
        self.right_y = 0.0
        self.right_z = 0.0
        self.radius = 1.0
        self.depth = 0

    def copy(self) -> "_TurtleState":
        s = _TurtleState()
        s.x, s.y, s.z = self.x, self.y, self.z
        s.dx, s.dy, s.dz = self.dx, self.dy, self.dz
        s.right_x, s.right_y, s.right_z = self.right_x, self.right_y, self.right_z
        s.radius = self.radius
        s.depth = self.depth
        return s


class BranchSegment:
    """A single branch segment connecting two points.

    Attributes:
        start: (x, y, z) start position.
        end: (x, y, z) end position.
        start_radius: Radius at start.
        end_radius: Radius at end.
        depth: Branching depth (0=trunk, higher=smaller branches).
        is_tip: Whether this segment is a branch tip (potential leaf site).
        parent_index: Index of the parent segment (-1 for root).
    """
    __slots__ = ("start", "end", "start_radius", "end_radius",
                 "depth", "is_tip", "parent_index")

    def __init__(
        self,
        start: Vec3,
        end: Vec3,
        start_radius: float,
        end_radius: float,
        depth: int,
        is_tip: bool = False,
        parent_index: int = -1,
    ) -> None:
        self.start = start
        self.end = end
        self.start_radius = start_radius
        self.end_radius = end_radius
        self.depth = depth
        self.is_tip = is_tip
        self.parent_index = parent_index


def interpret_lsystem(
    lstring: str,
    branch_angle: float = 25.0,
    branch_ratio: float = 0.7,
    trunk_ratio: float = 0.85,
    trunk_radius: float = 0.3,
    segment_length: float = 1.0,
    gravity: float = 0.1,
    randomness: float = 0.2,
    seed: int = 42,
) -> list[BranchSegment]:
    """Interpret an L-system string into branch segments using turtle graphics.

    Args:
        lstring: Expanded L-system string.
        branch_angle: Angle in degrees for + and - turns.
        branch_ratio: Child/parent radius ratio at branch points.
        trunk_ratio: Radius reduction along trunk (sequential F's).
        trunk_radius: Starting trunk radius.
        segment_length: Length of each 'F' step.
        gravity: Droop factor (0=none, 1=heavy drooping).
        randomness: Random variation factor (0=perfect, 1=wild).
        seed: Random seed.

    Returns:
        List of BranchSegment objects representing the tree structure.
    """
    rng = _random.Random(seed)
    segments: list[BranchSegment] = []
    stack: list[_TurtleState] = []
    parent_stack: list[int] = []

    state = _TurtleState()
    state.radius = trunk_radius
    current_parent = -1

    angle_rad = math.radians(branch_angle)

    for ch in lstring:
        if ch == "F":
            # Move forward and create segment
            length = segment_length * (1.0 + rng.gauss(0.0, randomness * 0.2))

            # Apply gravity (pull direction toward -Z)
            if gravity > 0:
                grav_amount = gravity * (1.0 - 1.0 / (1.0 + state.depth * 0.5))
                state.dz -= grav_amount * 0.1
                # Renormalize direction
                dl = math.sqrt(state.dx ** 2 + state.dy ** 2 + state.dz ** 2)
                if dl > 1e-12:
                    state.dx /= dl
                    state.dy /= dl
                    state.dz /= dl

            new_x = state.x + state.dx * length
            new_y = state.y + state.dy * length
            new_z = state.z + state.dz * length

            end_radius = state.radius * trunk_ratio

            seg = BranchSegment(
                start=(state.x, state.y, state.z),
                end=(new_x, new_y, new_z),
                start_radius=state.radius,
                end_radius=end_radius,
                depth=state.depth,
                is_tip=False,
                parent_index=current_parent,
            )
            segments.append(seg)
            current_parent = len(segments) - 1

            state.x, state.y, state.z = new_x, new_y, new_z
            state.radius = end_radius

        elif ch == "+":
            # Turn right around the right vector
            random_angle = angle_rad * (1.0 + rng.gauss(0.0, randomness * 0.3))
            state.dx, state.dy, state.dz = _rotate_vector(
                state.dx, state.dy, state.dz,
                state.right_x, state.right_y, state.right_z,
                random_angle,
            )

        elif ch == "-":
            # Turn left around the right vector
            random_angle = angle_rad * (1.0 + rng.gauss(0.0, randomness * 0.3))
            state.dx, state.dy, state.dz = _rotate_vector(
                state.dx, state.dy, state.dz,
                state.right_x, state.right_y, state.right_z,
                -random_angle,
            )

        elif ch == "[":
            # Push state (start a branch)
            stack.append(state.copy())
            parent_stack.append(current_parent)
            state.depth += 1
            state.radius *= branch_ratio

            # Add random rotation around the trunk axis for 3D branching
            spin_angle = rng.uniform(0, 2.0 * math.pi)
            state.dx, state.dy, state.dz = _rotate_vector(
                state.dx, state.dy, state.dz,
                0, 0, 1,  # Spin around world up
                spin_angle * 0.3,
            )
            # Also rotate the right vector
            state.right_x, state.right_y, state.right_z = _rotate_vector(
                state.right_x, state.right_y, state.right_z,
                0, 0, 1,
                spin_angle * 0.3,
            )

        elif ch == "]":
            # Pop state (end branch) -- mark last segment as tip
            if segments and segments[-1].depth >= state.depth:
                segments[-1].is_tip = True

            if stack:
                state = stack.pop()
            if parent_stack:
                current_parent = parent_stack.pop()

    # Mark final segment as tip
    if segments:
        segments[-1].is_tip = True

    return segments


# ---------------------------------------------------------------------------
# Branch-to-mesh conversion (truncated cones)
# ---------------------------------------------------------------------------

def _generate_cylinder_ring(
    center: Vec3,
    direction: Vec3,
    radius: float,
    segments: int = 6,
) -> list[Vec3]:
    """Generate a ring of vertices perpendicular to a direction vector.

    Args:
        center: Center point of the ring.
        direction: Direction the cylinder extends along.
        radius: Ring radius.
        segments: Number of vertices around the ring.

    Returns:
        List of (x, y, z) vertex positions.
    """
    dx, dy, dz = direction
    dl = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dl < 1e-12:
        dx, dy, dz = 0.0, 0.0, 1.0
    else:
        dx, dy, dz = dx / dl, dy / dl, dz / dl

    # Find a perpendicular vector
    if abs(dx) < 0.9:
        perp_x, perp_y, perp_z = 1.0, 0.0, 0.0
    else:
        perp_x, perp_y, perp_z = 0.0, 1.0, 0.0

    # Cross product: direction x perp = right
    rx = dy * perp_z - dz * perp_y
    ry = dz * perp_x - dx * perp_z
    rz = dx * perp_y - dy * perp_x
    rl = math.sqrt(rx * rx + ry * ry + rz * rz)
    if rl > 1e-12:
        rx, ry, rz = rx / rl, ry / rl, rz / rl

    # Cross product: direction x right = up
    ux = dy * rz - dz * ry
    uy = dz * rx - dx * rz
    uz = dx * ry - dy * rx

    verts: list[Vec3] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        vx = center[0] + radius * (cos_a * rx + sin_a * ux)
        vy = center[1] + radius * (cos_a * ry + sin_a * uy)
        vz = center[2] + radius * (cos_a * rz + sin_a * uz)
        verts.append((vx, vy, vz))

    return verts


def branches_to_mesh(
    segments: list[BranchSegment],
    ring_segments: int = 6,
    min_radius_for_geometry: float = 0.01,
) -> MeshSpec:
    """Convert branch segments to a mesh specification (truncated cones).

    Pure-logic function.

    Args:
        segments: List of BranchSegment objects.
        ring_segments: Vertex count per cross-section ring.
        min_radius_for_geometry: Minimum radius to generate geometry for.

    Returns:
        MeshSpec dict with 'vertices', 'faces', 'branch_depths', 'tip_indices'.
    """
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    branch_depths: list[int] = []
    tip_positions: list[Vec3] = []
    tip_directions: list[Vec3] = []
    tip_radii: list[float] = []

    for seg in segments:
        if seg.start_radius < min_radius_for_geometry and seg.end_radius < min_radius_for_geometry:
            if seg.is_tip:
                tip_positions.append(seg.end)
                dx = seg.end[0] - seg.start[0]
                dy = seg.end[1] - seg.start[1]
                dz = seg.end[2] - seg.start[2]
                dl = math.sqrt(dx * dx + dy * dy + dz * dz)
                if dl > 1e-12:
                    tip_directions.append((dx / dl, dy / dl, dz / dl))
                else:
                    tip_directions.append((0.0, 0.0, 1.0))
                tip_radii.append(max(seg.start_radius, seg.end_radius))
            continue

        direction = (
            seg.end[0] - seg.start[0],
            seg.end[1] - seg.start[1],
            seg.end[2] - seg.start[2],
        )

        # Generate start and end rings
        ring_start = _generate_cylinder_ring(
            seg.start, direction, max(seg.start_radius, min_radius_for_geometry),
            ring_segments,
        )
        ring_end = _generate_cylinder_ring(
            seg.end, direction, max(seg.end_radius, min_radius_for_geometry),
            ring_segments,
        )

        base_idx = len(vertices)
        vertices.extend(ring_start)
        vertices.extend(ring_end)

        # Create faces connecting the two rings (quads)
        for i in range(ring_segments):
            i_next = (i + 1) % ring_segments
            v0 = base_idx + i
            v1 = base_idx + i_next
            v2 = base_idx + ring_segments + i_next
            v3 = base_idx + ring_segments + i
            faces.append((v0, v1, v2, v3))

        # Record branch depth for all vertices in this segment
        for _ in range(ring_segments * 2):
            branch_depths.append(seg.depth)

        if seg.is_tip:
            tip_positions.append(seg.end)
            dl = math.sqrt(
                direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2
            )
            if dl > 1e-12:
                tip_directions.append((
                    direction[0] / dl, direction[1] / dl, direction[2] / dl,
                ))
            else:
                tip_directions.append((0.0, 0.0, 1.0))
            tip_radii.append(seg.end_radius)

    return {
        "vertices": vertices,
        "faces": faces,
        "branch_depths": branch_depths,
        "tip_positions": tip_positions,
        "tip_directions": tip_directions,
        "tip_radii": tip_radii,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "segment_count": len(segments),
    }


# ---------------------------------------------------------------------------
# Root generation
# ---------------------------------------------------------------------------

def generate_roots(
    trunk_base: Vec3,
    trunk_radius: float,
    num_roots: int = 5,
    root_length: float = 2.0,
    root_radius_ratio: float = 0.3,
    seed: int = 42,
) -> list[BranchSegment]:
    """Generate visible root segments at the base of a tree.

    Pure-logic function.

    Args:
        trunk_base: (x, y, z) position of the trunk base.
        trunk_radius: Trunk radius at the base.
        num_roots: Number of visible roots (3-8 recommended).
        root_length: How far roots extend from the trunk.
        root_radius_ratio: Root radius as fraction of trunk radius.
        seed: Random seed.

    Returns:
        List of BranchSegment objects representing roots.
    """
    rng = _random.Random(seed)
    roots: list[BranchSegment] = []
    base_x, base_y, base_z = trunk_base

    for i in range(num_roots):
        # Distribute roots around the trunk
        base_angle = 2.0 * math.pi * i / num_roots
        angle = base_angle + rng.uniform(-0.3, 0.3)

        # Root direction: outward and slightly downward
        dx = math.cos(angle)
        dy = math.sin(angle)
        dz = rng.uniform(-0.4, -0.1)  # Roots angle downward

        # Normalize
        dl = math.sqrt(dx * dx + dy * dy + dz * dz)
        dx, dy, dz = dx / dl, dy / dl, dz / dl

        length = root_length * rng.uniform(0.7, 1.3)
        start_r = trunk_radius * root_radius_ratio * rng.uniform(0.8, 1.2)
        end_r = start_r * 0.3

        # Start slightly offset from exact center
        start = (
            base_x + dx * trunk_radius * 0.5,
            base_y + dy * trunk_radius * 0.5,
            base_z,
        )
        end = (
            base_x + dx * length,
            base_y + dy * length,
            base_z + dz * length,
        )

        roots.append(BranchSegment(
            start=start, end=end,
            start_radius=start_r, end_radius=end_r,
            depth=0, is_tip=True, parent_index=-1,
        ))

    return roots


# ---------------------------------------------------------------------------
# 1. L-System Tree Generator (main entry point)
# ---------------------------------------------------------------------------

def generate_lsystem_tree(params: dict) -> dict:
    """Generate a botanical tree using L-system branching rules.

    Pure-logic function (no Blender dependency). Returns a mesh specification
    dict that can be used to create Blender geometry.

    Params:
        tree_type: str -- 'oak' | 'pine' | 'birch' | 'willow' | 'dead' |
                         'ancient' | 'twisted'.
        iterations: int -- Branching depth (4-8, default from grammar).
        trunk_radius: float -- Starting trunk radius (default 0.3).
        branch_angle: float -- Degrees (default from grammar).
        branch_ratio: float -- Child/parent radius ratio (default from grammar).
        gravity: float -- Droop factor (default from grammar).
        randomness: float -- Variation (default from grammar).
        seed: int -- Random seed (default 42).
        leaf_density: float -- 0-1 (default from grammar).
        segment_length: float -- Length per F step (default 1.0).
        ring_segments: int -- Vertices per cross-section (default 6).
        generate_roots: bool -- Whether to generate visible roots (default True).

    Returns:
        Dict with:
          vertices: list of [x, y, z]
          faces: list of index tuples
          branch_depths: per-vertex branch depth
          tip_positions: branch tip locations
          tip_directions: branch tip direction vectors
          tip_radii: branch tip radii
          tree_type: type name
          metadata: grammar info
    """
    tree_type = params.get("tree_type", "oak")
    if tree_type not in LSYSTEM_GRAMMARS:
        raise ValueError(
            f"Unknown tree_type: {tree_type!r}. "
            f"Valid: {sorted(LSYSTEM_GRAMMARS)}"
        )

    grammar = LSYSTEM_GRAMMARS[tree_type]
    iterations = params.get("iterations", grammar["default_iterations"])
    trunk_radius = params.get("trunk_radius", 0.3)
    branch_angle = params.get("branch_angle", grammar["branch_angle"])
    branch_ratio = params.get("branch_ratio", grammar["branch_ratio"])
    gravity = params.get("gravity", grammar["gravity"])
    randomness = params.get("randomness", grammar["randomness"])
    seed = params.get("seed", 42)
    leaf_density = params.get("leaf_density", grammar["leaf_density"])
    segment_length = params.get("segment_length", 1.0)
    ring_segments = params.get("ring_segments", 6)
    do_roots = params.get("generate_roots", True)

    # MISC-020: cap iterations to 6 (was 8); oak at 8 iterations produces
    # ~4.7M verts which is unusable in a game scene. 6 iterations gives
    # AAA-quality detail (~290K verts) while remaining real-time viable.
    iterations = max(1, min(iterations, 6))

    # Expand L-system
    lstring = expand_lsystem(grammar["axiom"], grammar["rules"], iterations)

    # Interpret to branch segments
    segments = interpret_lsystem(
        lstring,
        branch_angle=branch_angle,
        branch_ratio=branch_ratio,
        trunk_ratio=grammar.get("trunk_ratio", 0.85),
        trunk_radius=trunk_radius,
        segment_length=segment_length,
        gravity=gravity,
        randomness=randomness,
        seed=seed,
    )

    # Add roots
    root_segments: list[BranchSegment] = []
    if do_roots and segments:
        root_segments = generate_roots(
            trunk_base=(0.0, 0.0, 0.0),
            trunk_radius=trunk_radius,
            num_roots=max(3, min(5, int(trunk_radius * 10))),
            root_length=trunk_radius * 5.0,
            seed=seed,
        )

    all_segments = segments + root_segments
    mesh = branches_to_mesh(all_segments, ring_segments)

    mesh["tree_type"] = tree_type
    mesh["leaf_density"] = leaf_density
    mesh["metadata"] = {
        "grammar": tree_type,
        "iterations": iterations,
        "lstring_length": len(lstring),
        "total_segments": len(all_segments),
        "branch_segments": len(segments),
        "root_segments": len(root_segments),
        "description": grammar["description"],
    }

    return mesh


# ---------------------------------------------------------------------------
# 2. Leaf Card Generator
# ---------------------------------------------------------------------------

# Leaf type presets
_LEAF_PRESETS: dict[str, dict[str, Any]] = {
    "broadleaf": {
        "cards_per_tip": 3,
        "card_size": (0.4, 0.4),
        "spread": 0.3,
        "description": "Broad flat leaves in clusters",
    },
    "needle": {
        "cards_per_tip": 6,
        "card_size": (0.15, 0.5),
        "spread": 0.2,
        "description": "Thin needle clusters for conifers",
    },
    "palm": {
        "cards_per_tip": 2,
        "card_size": (0.6, 1.2),
        "spread": 0.5,
        "description": "Large palm fronds",
    },
    "fern": {
        "cards_per_tip": 4,
        "card_size": (0.3, 0.6),
        "spread": 0.4,
        "description": "Fern fronds",
    },
    "vine": {
        "cards_per_tip": 5,
        "card_size": (0.2, 0.3),
        "spread": 0.6,
        "description": "Small vine leaves trailing down",
    },
}


def generate_leaf_cards(
    branch_tips: list[dict[str, Any]],
    leaf_type: str = "broadleaf",
    density: float = 0.8,
    seed: int = 42,
) -> MeshSpec:
    """Generate leaf card quads at branch tip positions.

    Pure-logic function -- no Blender dependency.

    Args:
        branch_tips: List of dicts with 'position' [x,y,z],
                    'direction' [dx,dy,dz], 'radius' float.
        leaf_type: 'broadleaf' | 'needle' | 'palm' | 'fern' | 'vine'.
        density: Probability of placing leaves at each tip (0-1).
        seed: Random seed.

    Returns:
        MeshSpec dict with vertices and faces for leaf card quads.
        Each leaf is a quad (2 triangles) with random rotation/scale.
    """
    if leaf_type not in _LEAF_PRESETS:
        raise ValueError(
            f"Unknown leaf_type: {leaf_type!r}. "
            f"Valid: {sorted(_LEAF_PRESETS)}"
        )

    preset = _LEAF_PRESETS[leaf_type]
    cards_per_tip = preset["cards_per_tip"]
    card_w, card_h = preset["card_size"]
    spread = preset["spread"]

    rng = _random.Random(seed)
    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []

    for tip in branch_tips:
        if rng.random() > density:
            continue

        pos = tip.get("position", (0, 0, 0))
        direction = tip.get("direction", (0, 0, 1))
        tip_radius = tip.get("radius", 0.1)

        px, py, pz = float(pos[0]), float(pos[1]), float(pos[2])
        dx, dy, dz = float(direction[0]), float(direction[1]), float(direction[2])

        for _card in range(cards_per_tip):
            if rng.random() > density:
                continue

            # Random offset from tip position
            offset_x = rng.gauss(0.0, spread) * tip_radius * 3.0
            offset_y = rng.gauss(0.0, spread) * tip_radius * 3.0
            offset_z = rng.gauss(0.0, spread * 0.5) * tip_radius * 2.0

            cx = px + offset_x
            cy = py + offset_y
            cz = pz + offset_z

            # Random rotation for the card
            rot_angle = rng.uniform(0, 2.0 * math.pi)
            tilt = rng.uniform(-0.3, 0.3)

            # Scale variation
            scale = rng.uniform(0.7, 1.3)
            w = card_w * scale
            h = card_h * scale

            # Generate quad corners (oriented toward the branch direction with randomness)
            cos_r = math.cos(rot_angle)
            sin_r = math.sin(rot_angle)

            # Compute a right and up vector for the card
            # Use the direction as approximate normal, then tilt
            if abs(dz) < 0.9:
                up_x, up_y, up_z = 0.0, 0.0, 1.0
            else:
                up_x, up_y, up_z = 1.0, 0.0, 0.0

            # Right = direction cross up
            rx = dy * up_z - dz * up_y
            ry = dz * up_x - dx * up_z
            rz = dx * up_y - dy * up_x
            rl = math.sqrt(rx * rx + ry * ry + rz * rz)
            if rl > 1e-12:
                rx, ry, rz = rx / rl, ry / rl, rz / rl

            # Recompute up = right cross direction
            ux = ry * dz - rz * dy
            uy = rz * dx - rx * dz
            uz = rx * dy - ry * dx

            # Apply rotation around direction
            final_rx = rx * cos_r + ux * sin_r
            final_ry = ry * cos_r + uy * sin_r
            final_rz = rz * cos_r + uz * sin_r

            final_ux = -rx * sin_r + ux * cos_r
            final_uy = -ry * sin_r + uy * cos_r
            final_uz = -rz * sin_r + uz * cos_r

            # Apply tilt
            final_ux += dz * tilt
            final_uz -= dx * tilt

            hw = w * 0.5
            hh = h * 0.5

            base_idx = len(vertices)
            vertices.append((cx - hw * final_rx - hh * final_ux,
                             cy - hw * final_ry - hh * final_uy,
                             cz - hw * final_rz - hh * final_uz))
            vertices.append((cx + hw * final_rx - hh * final_ux,
                             cy + hw * final_ry - hh * final_uy,
                             cz + hw * final_rz - hh * final_uz))
            vertices.append((cx + hw * final_rx + hh * final_ux,
                             cy + hw * final_ry + hh * final_uy,
                             cz + hw * final_rz + hh * final_uz))
            vertices.append((cx - hw * final_rx + hh * final_ux,
                             cy - hw * final_ry + hh * final_uy,
                             cz - hw * final_rz + hh * final_uz))

            faces.append((base_idx, base_idx + 1, base_idx + 2, base_idx + 3))

    return {
        "vertices": vertices,
        "faces": faces,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "leaf_type": leaf_type,
        "cards_generated": len(faces),
    }


# ---------------------------------------------------------------------------
# 3. Wind Vertex Color Baking
# ---------------------------------------------------------------------------

def bake_wind_vertex_colors(tree_mesh_spec: MeshSpec) -> MeshSpec:
    """Bake wind animation weights into vertex colors.

    Pure-logic function -- no Blender dependency.

    Channel mapping:
      R = primary sway (0 at trunk, 1 at branch tips -- radial distance
          from base, normalized).
      G = secondary sway (leaf flutter: 1 for tip verts, 0 for trunk).
      B = phase offset (random per branch for desynchronized motion).

    Unity shader reads these vertex colors for GPU-based wind animation.

    Args:
        tree_mesh_spec: MeshSpec dict from generate_lsystem_tree or
                       branches_to_mesh. Must contain 'vertices' and
                       'branch_depths'.

    Returns:
        Updated MeshSpec with 'wind_colors' key added: list of (R, G, B)
        tuples per vertex, all values clamped to [0, 1].
    """
    vertices = tree_mesh_spec.get("vertices", [])
    branch_depths = tree_mesh_spec.get("branch_depths", [])

    if not vertices:
        tree_mesh_spec["wind_colors"] = []
        return tree_mesh_spec

    # Find height range and max radial distance from center
    z_values = [v[2] for v in vertices]
    min_z = min(z_values)
    max_z = max(z_values)
    height_range = max_z - min_z if max_z > min_z else 1.0

    # Find tree center at base
    base_threshold = min_z + height_range * 0.1
    base_verts = [(v[0], v[1]) for v in vertices if v[2] <= base_threshold]
    if base_verts:
        center_x = sum(v[0] for v in base_verts) / len(base_verts)
        center_y = sum(v[1] for v in base_verts) / len(base_verts)
    else:
        center_x = sum(v[0] for v in vertices) / len(vertices)
        center_y = sum(v[1] for v in vertices) / len(vertices)

    # Find max radial distance
    max_dist = 0.0
    for vx, vy, _vz in vertices:
        d = math.sqrt((vx - center_x) ** 2 + (vy - center_y) ** 2)
        if d > max_dist:
            max_dist = d
    if max_dist < 1e-6:
        max_dist = 1.0

    # Find max branch depth
    max_depth = max(branch_depths) if branch_depths else 1
    if max_depth == 0:
        max_depth = 1

    colors: list[tuple[float, float, float]] = []

    for i, (vx, vy, vz) in enumerate(vertices):
        # R: Primary sway -- distance from trunk base (radial + height)
        radial_dist = math.sqrt((vx - center_x) ** 2 + (vy - center_y) ** 2)
        height_norm = (vz - min_z) / height_range
        r = min(1.0, max(0.0, (radial_dist / max_dist) * 0.5 + height_norm * 0.5))

        # G: Secondary sway / leaf flutter -- based on branch depth
        depth = branch_depths[i] if i < len(branch_depths) else 0
        g = min(1.0, max(0.0, depth / max_depth))

        # B: Phase offset -- hash based on position for deterministic
        #    but varied per-branch desynchronization
        phase_hash = math.sin(vx * 12.9898 + vy * 78.233 + vz * 37.719) * 43758.5453
        b = min(1.0, max(0.0, phase_hash - math.floor(phase_hash)))

        colors.append((r, g, b))

    tree_mesh_spec["wind_colors"] = colors
    return tree_mesh_spec


# ---------------------------------------------------------------------------
# 4. Billboard Impostor Generation
# ---------------------------------------------------------------------------

def generate_billboard_impostor(params: dict) -> MeshSpec:
    """Generate billboard impostor mesh for ultra-low LOD trees.

    Pure-logic function -- generates the impostor mesh geometry.
    Actual texture capture/rendering requires Blender (returned in next_steps).

    Params:
        object_name: str -- Source tree object name (for metadata).
        num_views: int -- Number of views around the tree (8 or 12).
        resolution: int -- Texture atlas resolution per view (default 256).
        height: float -- Tree height for billboard sizing (default 5.0).
        width: float -- Tree width for billboard sizing (default 3.0).
        impostor_type: str -- 'cross' (2 intersecting quads) or
                             'octahedral' (8-face low-poly mesh).

    Returns:
        MeshSpec with impostor geometry and UV layout metadata.
    """
    num_views = params.get("num_views", 8)
    resolution = params.get("resolution", 256)
    tree_height = params.get("height", 5.0)
    tree_width = params.get("width", 3.0)
    impostor_type = params.get("impostor_type", "cross")
    object_name = params.get("object_name", "tree")

    vertices: list[Vec3] = []
    faces: list[tuple[int, ...]] = []
    uvs: list[tuple[float, float]] = []

    half_w = tree_width * 0.5
    half_h = tree_height * 0.5
    center_z = tree_height * 0.5

    if impostor_type == "cross":
        # Cross-billboard: 2 intersecting quads at 90 degrees
        for angle_deg in [0.0, 90.0]:
            angle = math.radians(angle_deg)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)

            base_idx = len(vertices)

            # 4 corners of a vertical quad
            vertices.append((-half_w * cos_a, -half_w * sin_a, 0.0))
            vertices.append((half_w * cos_a, half_w * sin_a, 0.0))
            vertices.append((half_w * cos_a, half_w * sin_a, tree_height))
            vertices.append((-half_w * cos_a, -half_w * sin_a, tree_height))

            faces.append((base_idx, base_idx + 1, base_idx + 2, base_idx + 3))

            # UVs for this quad
            u_offset = 0.0 if angle_deg == 0.0 else 0.5
            uvs.extend([
                (u_offset, 0.0),
                (u_offset + 0.5, 0.0),
                (u_offset + 0.5, 1.0),
                (u_offset, 1.0),
            ])

    elif impostor_type == "octahedral":
        # Octahedral impostor: 8-sided prism approximation
        for i in range(num_views):
            angle = 2.0 * math.pi * i / num_views
            next_angle = 2.0 * math.pi * (i + 1) / num_views

            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            cos_b = math.cos(next_angle)
            sin_b = math.sin(next_angle)

            base_idx = len(vertices)

            # Quad face of the prism
            vertices.append((half_w * cos_a, half_w * sin_a, 0.0))
            vertices.append((half_w * cos_b, half_w * sin_b, 0.0))
            vertices.append((half_w * cos_b, half_w * sin_b, tree_height))
            vertices.append((half_w * cos_a, half_w * sin_a, tree_height))

            faces.append((base_idx, base_idx + 1, base_idx + 2, base_idx + 3))

            # UV layout: each view gets a section of the atlas
            u_start = i / num_views
            u_end = (i + 1) / num_views
            uvs.extend([
                (u_start, 0.0),
                (u_end, 0.0),
                (u_end, 1.0),
                (u_start, 1.0),
            ])

    else:
        raise ValueError(
            f"Unknown impostor_type: {impostor_type!r}. "
            f"Valid: ['cross', 'octahedral']"
        )

    return {
        "vertices": vertices,
        "faces": faces,
        "uvs": uvs,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "impostor_type": impostor_type,
        "num_views": num_views,
        "atlas_resolution": resolution,
        "object_name": object_name,
        "tree_dimensions": {"width": tree_width, "height": tree_height},
        "next_steps": [
            f"Render {num_views} views of '{object_name}' to texture atlas",
            "Assign atlas texture to impostor material with alpha cutout",
            "Set up LOD group: full tree -> impostor at distance",
        ],
    }


# ---------------------------------------------------------------------------
# 5. GPU Instancing Export
# ---------------------------------------------------------------------------

def prepare_gpu_instancing_export(params: dict) -> dict:
    """Prepare vegetation scatter data for GPU instancing in Unity.

    Pure-logic function.

    Params:
        instances: list of dicts with:
            mesh_name: str
            position: [x, y, z]
            rotation: [rx, ry, rz] (Euler degrees)
            scale: [sx, sy, sz] or float
            lod_level: int (0=highest detail)
        output_path: str -- JSON output path.
        format: str -- 'json' or 'binary' (default 'json').

    Returns:
        Dict with instance buffer summary and export metadata.
    """
    instances = params.get("instances", [])
    output_path = params.get("output_path", "vegetation_instances.json")
    export_format = params.get("format", "json")

    if not instances:
        return {
            "status": "empty",
            "instance_count": 0,
            "output_path": output_path,
        }

    # Group instances by mesh name for batched rendering
    mesh_groups: dict[str, list[dict[str, Any]]] = {}
    for inst in instances:
        mesh_name = inst.get("mesh_name", "unknown")
        if mesh_name not in mesh_groups:
            mesh_groups[mesh_name] = []

        pos = inst.get("position", [0, 0, 0])
        rot = inst.get("rotation", [0, 0, 0])
        scale = inst.get("scale", [1, 1, 1])
        if isinstance(scale, (int, float)):
            scale = [scale, scale, scale]
        lod = inst.get("lod_level", 0)

        mesh_groups[mesh_name].append({
            "position": [float(pos[0]), float(pos[1]), float(pos[2])],
            "rotation": [float(rot[0]), float(rot[1]), float(rot[2])],
            "scale": [float(scale[0]), float(scale[1]), float(scale[2])],
            "lod_level": int(lod),
        })

    # Compute bounds for culling
    all_positions = [
        inst.get("position", [0, 0, 0]) for inst in instances
    ]
    min_x = min(p[0] for p in all_positions)
    max_x = max(p[0] for p in all_positions)
    min_y = min(p[1] for p in all_positions)
    max_y = max(p[1] for p in all_positions)
    min_z = min(p[2] for p in all_positions)
    max_z = max(p[2] for p in all_positions)

    # LOD distribution
    lod_counts: dict[int, int] = {}
    for inst in instances:
        lod = inst.get("lod_level", 0)
        lod_counts[lod] = lod_counts.get(lod, 0) + 1

    export_data = {
        "version": "1.0",
        "instance_count": len(instances),
        "mesh_groups": {
            name: {
                "count": len(group),
                "instances": group,
            }
            for name, group in mesh_groups.items()
        },
        "bounds": {
            "min": [min_x, min_y, min_z],
            "max": [max_x, max_y, max_z],
        },
        "lod_distribution": lod_counts,
    }

    return {
        "status": "success",
        "instance_count": len(instances),
        "mesh_group_count": len(mesh_groups),
        "mesh_groups": {name: len(group) for name, group in mesh_groups.items()},
        "bounds": export_data["bounds"],
        "lod_distribution": lod_counts,
        "output_path": output_path,
        "format": export_format,
        "export_data": export_data,
    }
