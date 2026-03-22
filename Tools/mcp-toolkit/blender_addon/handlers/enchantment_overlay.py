"""Enchantment and infusion visual overlay system for VeilBreakers equipment.

Computes per-vertex emission masks and particle spawn positions for the
10 VeilBreakers brand enchantment types. All functions are pure Python/math
-- no ``bpy`` dependency -- for testability.

Provides:
  - BRAND_ENCHANTMENT_PATTERNS: visual pattern definitions per brand
  - compute_enchantment_overlay(): Per-vertex emission mask for brand enchant
  - generate_floating_rune_positions(): Orbiting rune mesh positions
  - get_brand_pattern(): Retrieve pattern data for a brand
  - compute_pattern_density(): Pattern-specific vertex weight computation
"""

from __future__ import annotations

import math
import random
from typing import Any


# ---------------------------------------------------------------------------
# Brand enchantment pattern definitions
# ---------------------------------------------------------------------------

BRAND_ENCHANTMENT_PATTERNS: dict[str, dict[str, Any]] = {
    "IRON": {
        "pattern": "chain_links",
        "emission_color": (0.55, 0.35, 0.22),
        "emission_strength": 0.5,
        "particle": "sparks",
        "pulse_speed": 0.0,  # static
        "coverage": 0.3,  # 30% of surface shows pattern
    },
    "SAVAGE": {
        "pattern": "claw_marks",
        "emission_color": (0.71, 0.18, 0.18),
        "emission_strength": 0.6,
        "particle": "blood_mist",
        "pulse_speed": 0.0,
        "coverage": 0.25,
    },
    "SURGE": {
        "pattern": "lightning_arcs",
        "emission_color": (0.24, 0.55, 0.86),
        "emission_strength": 1.0,
        "particle": "electric_sparks",
        "pulse_speed": 3.0,  # fast flicker
        "coverage": 0.4,
    },
    "VENOM": {
        "pattern": "acid_drip",
        "emission_color": (0.31, 0.71, 0.24),
        "emission_strength": 0.4,
        "particle": "toxic_bubbles",
        "pulse_speed": 0.5,
        "coverage": 0.35,
    },
    "DREAD": {
        "pattern": "shadow_tendrils",
        "emission_color": (0.24, 0.47, 0.27),
        "emission_strength": 0.3,
        "particle": "dark_wisps",
        "pulse_speed": 0.8,
        "coverage": 0.5,
    },
    "LEECH": {
        "pattern": "pulsing_veins",
        "emission_color": (0.55, 0.53, 0.20),
        "emission_strength": 0.5,
        "particle": "drain_tendrils",
        "pulse_speed": 1.2,  # rhythmic pulse
        "coverage": 0.45,
    },
    "GRACE": {
        "pattern": "radiant_glow",
        "emission_color": (0.86, 0.86, 0.94),
        "emission_strength": 1.2,
        "particle": "light_motes",
        "pulse_speed": 0.3,  # gentle glow
        "coverage": 0.8,  # broad glow
    },
    "MEND": {
        "pattern": "healing_pulse",
        "emission_color": (0.78, 0.67, 0.31),
        "emission_strength": 0.8,
        "particle": "golden_sparkles",
        "pulse_speed": 0.6,
        "coverage": 0.6,
    },
    "RUIN": {
        "pattern": "crack_embers",
        "emission_color": (0.86, 0.47, 0.16),
        "emission_strength": 1.5,
        "particle": "ember_flakes",
        "pulse_speed": 0.2,  # slow burn
        "coverage": 0.35,
    },
    "VOID": {
        "pattern": "reality_distortion",
        "emission_color": (0.16, 0.08, 0.24),
        "emission_strength": 0.6,
        "particle": "void_fragments",
        "pulse_speed": 2.0,  # erratic
        "coverage": 0.55,
    },
}

# All valid brand names
VALID_BRANDS = frozenset(BRAND_ENCHANTMENT_PATTERNS.keys())


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _hash_position(x: float, y: float, z: float, seed: int) -> float:
    """Deterministic hash-based noise for position."""
    h = seed
    h ^= int(x * 73856093) & 0xFFFFFFFF
    h ^= int(y * 19349663) & 0xFFFFFFFF
    h ^= int(z * 83492791) & 0xFFFFFFFF
    h = ((h * 2654435761) & 0xFFFFFFFF)
    return h / 0xFFFFFFFF  # [0, 1]


def _compute_edge_factor(
    vertex_index: int,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
) -> float:
    """Compute how 'edge-like' a vertex is (0 = interior, 1 = sharp edge).

    Vertices shared by fewer faces or with more divergent normals score higher.
    """
    adjacent_faces = [f for f in faces if vertex_index in f]
    if len(adjacent_faces) <= 1:
        return 1.0
    if len(adjacent_faces) >= 6:
        return 0.1

    # Compute face normals and check divergence
    normals: list[tuple[float, float, float]] = []
    for face in adjacent_faces:
        if len(face) >= 3:
            v0 = vertices[face[0]]
            v1 = vertices[face[1]]
            v2 = vertices[face[2]]
            e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            n = (
                e1[1] * e2[2] - e1[2] * e2[1],
                e1[2] * e2[0] - e1[0] * e2[2],
                e1[0] * e2[1] - e1[1] * e2[0],
            )
            length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
            if length > 1e-9:
                normals.append((n[0] / length, n[1] / length, n[2] / length))

    if len(normals) < 2:
        return 0.5

    # Average dot product between consecutive normals
    total_dot = 0.0
    for i in range(len(normals)):
        for j in range(i + 1, len(normals)):
            dot = sum(normals[i][k] * normals[j][k] for k in range(3))
            total_dot += dot
    num_pairs = len(normals) * (len(normals) - 1) / 2
    avg_dot = total_dot / num_pairs if num_pairs > 0 else 1.0

    # Lower dot = more edge-like
    return max(0.0, min(1.0, 1.0 - avg_dot))


# ---------------------------------------------------------------------------
# Core enchantment functions
# ---------------------------------------------------------------------------

def get_brand_pattern(brand: str) -> dict[str, Any]:
    """Retrieve enchantment pattern data for a brand.

    Args:
        brand: Brand name (e.g. 'IRON', 'SURGE').

    Returns:
        Copy of the brand pattern dict.

    Raises:
        ValueError: If the brand name is unknown.
    """
    brand_upper = brand.upper()
    if brand_upper not in BRAND_ENCHANTMENT_PATTERNS:
        raise ValueError(
            f"Unknown brand '{brand}'. "
            f"Valid brands: {sorted(BRAND_ENCHANTMENT_PATTERNS.keys())}"
        )
    return dict(BRAND_ENCHANTMENT_PATTERNS[brand_upper])


def compute_pattern_density(
    vertex: tuple[float, float, float],
    pattern: str,
    seed: int = 0,
) -> float:
    """Compute pattern-specific weight for a vertex position.

    Different enchantment patterns use different spatial distribution
    algorithms to create their visual effects.

    Args:
        vertex: (x, y, z) position.
        pattern: Pattern name from brand definition.
        seed: Random seed for deterministic output.

    Returns:
        Pattern density weight in [0, 1].
    """
    x, y, z = vertex
    h = _hash_position(x, y, z, seed)

    if pattern == "chain_links":
        # Horizontal bands
        band = math.sin(y * 20.0 + seed * 0.1) * 0.5 + 0.5
        return band * h

    elif pattern == "claw_marks":
        # Diagonal scratches
        diag = math.sin((x + y) * 15.0 + seed * 0.1) * 0.5 + 0.5
        return diag * (1.0 if h > 0.6 else 0.0)

    elif pattern == "lightning_arcs":
        # Branching lightning: high frequency noise
        freq = math.sin(x * 30.0) * math.cos(z * 30.0) + math.sin(y * 25.0)
        return max(0.0, min(1.0, abs(freq) * h))

    elif pattern == "acid_drip":
        # Downward flow: stronger at top, dripping down
        height_factor = max(0.0, y * 2.0 + 0.5)
        drip = math.sin(x * 10.0 + z * 10.0 + seed) * 0.5 + 0.5
        return min(1.0, height_factor * drip * h)

    elif pattern == "shadow_tendrils":
        # Organic tendrils from center
        dist = math.sqrt(x * x + z * z)
        tendril = math.sin(math.atan2(z, x + 0.001) * 5.0 + dist * 10.0) * 0.5 + 0.5
        return tendril * h

    elif pattern == "pulsing_veins":
        # Vein-like network following edges
        vein = abs(math.sin(x * 12.0 + seed * 0.3) * math.sin(z * 12.0 + seed * 0.7))
        return min(1.0, vein * 2.0) * h

    elif pattern == "radiant_glow":
        # Uniform soft glow with subtle variation
        return 0.5 + 0.5 * math.sin(x * 3.0 + y * 3.0 + z * 3.0 + seed * 0.1)

    elif pattern == "healing_pulse":
        # Expanding ring pulse
        dist = math.sqrt(x * x + y * y + z * z)
        pulse = math.sin(dist * 8.0 + seed * 0.5) * 0.5 + 0.5
        return pulse

    elif pattern == "crack_embers":
        # Cracks with glowing edges
        crack = abs(math.sin(x * 20.0 + z * 15.0 + seed * 0.2))
        return 1.0 if crack > 0.85 else crack * 0.3

    elif pattern == "reality_distortion":
        # Chaotic, shifting pattern
        chaos = (
            math.sin(x * 17.0 + seed * 1.1) *
            math.cos(y * 23.0 + seed * 0.7) *
            math.sin(z * 19.0 + seed * 1.3)
        )
        return abs(chaos)

    # Fallback: uniform noise
    return h


def compute_enchantment_overlay(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    brand: str,
    intensity: float = 1.0,
    seed: int = 0,
) -> dict[str, Any]:
    """Compute per-vertex emission mask for brand enchantment.

    Calculates emission weights based on the brand's pattern type, vertex
    position, and edge geometry. Also determines particle spawn positions
    at high-emission vertices.

    Args:
        vertices: List of (x, y, z) vertex positions.
        faces: List of face index tuples.
        brand: Brand name (e.g. 'IRON', 'SURGE').
        intensity: Global intensity multiplier (default 1.0).
        seed: Random seed for deterministic output.

    Returns:
        Dict with keys:
        - 'emission_weights': per-vertex emission weight list [0, 1]
        - 'emission_color': brand emission color (r, g, b)
        - 'emission_strength': brand emission strength * intensity
        - 'particle_positions': list of (x, y, z) spawn positions
        - 'particle_type': brand particle type name
        - 'pattern': brand pattern name
        - 'metadata': statistics about the overlay
    """
    pattern_data = get_brand_pattern(brand)
    brand_upper = brand.upper()
    pattern_name = pattern_data["pattern"]
    coverage = pattern_data["coverage"]

    intensity = max(0.0, min(5.0, intensity))

    # Compute per-vertex emission weights
    emission_weights: list[float] = []
    rng = random.Random(seed)

    for i, vertex in enumerate(vertices):
        # Base pattern density
        density = compute_pattern_density(vertex, pattern_name, seed)

        # Edge factor: enchantments glow brighter at edges
        edge = _compute_edge_factor(i, vertices, faces)
        edge_boost = 1.0 + edge * 0.5

        # Coverage threshold: only vertices above threshold glow
        threshold_noise = _hash_position(
            vertex[0] + 100, vertex[1] + 100, vertex[2] + 100, seed + 7
        )
        active = 1.0 if threshold_noise < coverage else 0.0

        weight = density * edge_boost * active * intensity
        emission_weights.append(max(0.0, min(1.0, weight)))

    # Determine particle spawn positions at high-emission vertices
    particle_threshold = 0.6
    particle_positions: list[tuple[float, float, float]] = []
    for i, weight in enumerate(emission_weights):
        if weight >= particle_threshold:
            # Offset slightly outward from surface for particle spawning
            if i < len(vertices):
                vx, vy, vz = vertices[i]
                # Small random offset
                px = vx + rng.uniform(-0.01, 0.01)
                py = vy + rng.uniform(0.0, 0.02)
                pz = vz + rng.uniform(-0.01, 0.01)
                particle_positions.append((px, py, pz))

    # Statistics
    active_count = sum(1 for w in emission_weights if w > 0.01)
    avg_weight = sum(emission_weights) / len(emission_weights) if emission_weights else 0.0

    return {
        "emission_weights": emission_weights,
        "emission_color": pattern_data["emission_color"],
        "emission_strength": pattern_data["emission_strength"] * intensity,
        "particle_positions": particle_positions,
        "particle_type": pattern_data["particle"],
        "pattern": pattern_name,
        "pulse_speed": pattern_data["pulse_speed"],
        "metadata": {
            "brand": brand_upper,
            "intensity": intensity,
            "active_vertices": active_count,
            "total_vertices": len(vertices),
            "coverage_pct": active_count / len(vertices) if vertices else 0.0,
            "avg_emission_weight": avg_weight,
            "particle_spawn_count": len(particle_positions),
            "seed": seed,
        },
    }


def generate_floating_rune_positions(
    center: tuple[float, float, float],
    radius: float = 0.3,
    count: int = 4,
    brand: str = "IRON",
) -> list[dict[str, Any]]:
    """Generate positions for floating rune meshes orbiting equipment.

    Computes evenly-spaced orbital positions around the center point,
    with per-brand visual parameters for the rune glyphs.

    Args:
        center: (x, y, z) center of orbit.
        radius: Orbital radius.
        count: Number of rune positions to generate.
        brand: Brand name for rune visual style.

    Returns:
        List of dicts, each with:
        - 'position': (x, y, z) rune position
        - 'rotation': (rx, ry, rz) initial rotation in radians
        - 'orbit_angle': angle in radians around orbit
        - 'brand': brand name
        - 'emission_color': rune glow color
        - 'glyph_index': which glyph variant to use (0..count-1)
    """
    brand_upper = brand.upper()
    pattern_data = get_brand_pattern(brand_upper)
    count = max(1, count)

    runes: list[dict[str, Any]] = []
    for i in range(count):
        angle = (math.tau / count) * i
        # Orbit in the XZ plane, offset vertically
        px = center[0] + math.cos(angle) * radius
        py = center[1] + math.sin(angle * 0.5) * radius * 0.2  # slight bob
        pz = center[2] + math.sin(angle) * radius

        # Rune faces toward center
        face_angle = angle + math.pi  # face inward

        runes.append({
            "position": (px, py, pz),
            "rotation": (0.0, face_angle, math.sin(angle) * 0.1),
            "orbit_angle": angle,
            "brand": brand_upper,
            "emission_color": pattern_data["emission_color"],
            "glyph_index": i % count,
        })

    return runes
