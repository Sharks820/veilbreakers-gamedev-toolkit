"""Bundle C supplement — volumetric waterfall contract + 7 functional objects.

Extends ``terrain_waterfalls`` with an authoritative volumetric-geometry
profile and a named-object contract, per Addendum 1.B.3 of
docs/terrain_ultra_implementation_plan_2026-04-08.md and Addendum 2.J's
dual-nature clause.

A "waterfall" is both:
  * a physical 3D volumetric mesh (thick tapered prism, rounded front),
  * a set of functional objects (sheet, pool, foam, mist, splash, material zone).

This module provides pure-numpy validators for both facets. No bpy imports.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .terrain_semantics import ValidationIssue


# ---------------------------------------------------------------------------
# Volumetric profile
# ---------------------------------------------------------------------------


@dataclass
class WaterfallVolumetricProfile:
    """Authoritative geometry budget for volumetric waterfall sheets.

    Fields
    ------
    vertex_density_per_meter:
        Minimum vertex count per vertical drop-meter required to preserve
        the rounded-front silhouette and avoid the "flat plane" regression
        called out in feedback_waterfall_must_have_volume.md.
    front_curvature_radius_ratio:
        Front-face curvature radius expressed as a fraction of the sheet
        width. 0.0 = flat plane, 0.5 = half-pipe. Bundle C requires
        >= 0.15 for "rounded front" readability.
    min_non_coplanar_front_fraction:
        Minimum fraction of front-face vertex normals that must deviate
        from a shared plane. Values below this mean the front collapsed
        into a billboard — forbidden.
    """

    vertex_density_per_meter: float = 48.0
    front_curvature_radius_ratio: float = 0.15
    min_non_coplanar_front_fraction: float = 0.30


# ---------------------------------------------------------------------------
# Functional objects contract
# ---------------------------------------------------------------------------


@dataclass
class WaterfallFunctionalObjects:
    """The 7 named objects every waterfall chain must publish.

    Addendum 1.B.3 mandates that each chain expose each of these as a
    distinct Blender object (or Unity GameObject) so downstream systems
    (audio zones, decal placement, splash VFX, wet-rock shader, camera
    anchors) can look them up by suffix.
    """

    river_surface: str
    sheet_volume: str
    impact_pool: str
    foam_layer: str
    mist_volume: str
    splash_particles: str
    wet_rock_material_zone: str

    def as_list(self) -> List[str]:
        return [
            self.river_surface,
            self.sheet_volume,
            self.impact_pool,
            self.foam_layer,
            self.mist_volume,
            self.splash_particles,
            self.wet_rock_material_zone,
        ]


# Suffix → field mapping (canonical object name template: WF_{id}_{suffix}).
FUNCTIONAL_SUFFIXES: Tuple[str, ...] = (
    "river_surface",
    "sheet_volume",
    "impact_pool",
    "foam_layer",
    "mist_volume",
    "splash_particles",
    "wet_rock_material_zone",
)


def build_waterfall_functional_object_names(
    chain_id: str,
) -> WaterfallFunctionalObjects:
    """Return the canonical names for all 7 functional objects of a chain."""
    if not chain_id:
        raise ValueError("chain_id must be non-empty")
    prefix = f"WF_{chain_id}_"
    return WaterfallFunctionalObjects(
        river_surface=prefix + "river_surface",
        sheet_volume=prefix + "sheet_volume",
        impact_pool=prefix + "impact_pool",
        foam_layer=prefix + "foam_layer",
        mist_volume=prefix + "mist_volume",
        splash_particles=prefix + "splash_particles",
        wet_rock_material_zone=prefix + "wet_rock_material_zone",
    )


# ---------------------------------------------------------------------------
# Volumetric validator
# ---------------------------------------------------------------------------


def validate_waterfall_volumetric(
    profile: WaterfallVolumetricProfile,
    vertex_count: int,
    drop_m: float,
    front_normals_cos: Sequence[float],
) -> List[ValidationIssue]:
    """Validate that a waterfall sheet is a real 3D volumetric mesh.

    ``front_normals_cos`` is a sequence of cosine angles (dot products
    against a fitted front-plane normal) — values close to 1.0 mean
    flat/coplanar, deviation indicates curvature. The *non-coplanar
    fraction* is defined as fraction with cosine <= 0.98.
    """
    issues: List[ValidationIssue] = []

    drop_m = max(float(drop_m), 0.0)
    required_verts = int(math.ceil(profile.vertex_density_per_meter * drop_m))
    if vertex_count < required_verts:
        issues.append(
            ValidationIssue(
                code="WATERFALL_VERTEX_DENSITY_TOO_LOW",
                severity="hard",
                affected_feature="waterfall",
                message=(
                    f"vertex_count={vertex_count} < required "
                    f"{required_verts} (={profile.vertex_density_per_meter}*"
                    f"{drop_m:.2f}m)"
                ),
                remediation="Subdivide sheet geometry along drop axis.",
            )
        )

    if not front_normals_cos:
        issues.append(
            ValidationIssue(
                code="WATERFALL_FRONT_NORMALS_MISSING",
                severity="hard",
                affected_feature="waterfall",
                message="front_normals_cos sequence is empty",
            )
        )
        return issues

    # Spec: a front-vertex normal is "non-coplanar" when its raw dot product
    # with the mean-front-normal is < 0.95. `abs()` would treat backfacing
    # coplanar normals (dot ≈ -1) as curved, which is wrong.
    n = len(front_normals_cos)
    non_coplanar = sum(1 for c in front_normals_cos if float(c) < 0.95)
    frac = non_coplanar / n
    if frac < profile.min_non_coplanar_front_fraction:
        issues.append(
            ValidationIssue(
                code="WATERFALL_FRONT_COPLANAR",
                severity="hard",
                affected_feature="waterfall",
                message=(
                    f"non-coplanar front fraction {frac:.3f} < required "
                    f"{profile.min_non_coplanar_front_fraction:.3f} — sheet "
                    f"is a flat billboard, not a volumetric prism"
                ),
                remediation=(
                    "Taper thickness across span and round the front face."
                ),
            )
        )

    # Spec (Bundle C §3.2): rounded front requires curvature radius ratio
    # >= 0.15 × width. Negative is always invalid; [0.0, 0.15) is a flat front.
    min_curvature = 0.15
    if profile.front_curvature_radius_ratio < min_curvature:
        issues.append(
            ValidationIssue(
                code="WATERFALL_CURVATURE_RATIO_INVALID",
                severity="hard",
                affected_feature="waterfall",
                message=(
                    f"front_curvature_radius_ratio="
                    f"{profile.front_curvature_radius_ratio} must be >= "
                    f"{min_curvature} (0.15 × width per Bundle C §3.2)"
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Anchor screen-space validator
# ---------------------------------------------------------------------------


def validate_waterfall_anchor_screen_space(
    chain_lip_pos: Tuple[float, float, float],
    anchor_pos: Tuple[float, float, float],
    anchor_radius: float,
    vantage_position: Tuple[float, float, float],
) -> List[ValidationIssue]:
    """Ensure the camera anchor stays within the lip's anchor radius.

    This guards the "screen-space anchoring" contract from Addendum 2.J:
    if the anchor drifts too far from the chain lip (relative to the
    vantage), the feature no longer reads as a waterfall in frame.
    """
    issues: List[ValidationIssue] = []

    lip = tuple(float(v) for v in chain_lip_pos)
    anc = tuple(float(v) for v in anchor_pos)
    if len(lip) != 3 or len(anc) != 3:
        issues.append(
            ValidationIssue(
                code="WATERFALL_ANCHOR_DIM",
                severity="hard",
                affected_feature="waterfall",
                message="chain_lip_pos and anchor_pos must be 3-tuples",
            )
        )
        return issues

    # World-distance drift between the anchor and the lip.
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(lip, anc)))
    if anchor_radius <= 0:
        issues.append(
            ValidationIssue(
                code="WATERFALL_ANCHOR_RADIUS_INVALID",
                severity="hard",
                affected_feature="waterfall",
                message=f"anchor_radius={anchor_radius} must be positive",
            )
        )
        return issues

    if dist > float(anchor_radius):
        issues.append(
            ValidationIssue(
                code="WATERFALL_ANCHOR_DRIFT",
                severity="hard",
                affected_feature="waterfall",
                location=anc,
                message=(
                    f"anchor drift {dist:.2f}m exceeds radius "
                    f"{anchor_radius:.2f}m from chain lip"
                ),
                remediation="Reposition the anchor or widen anchor_radius.",
            )
        )

    # Vantage sanity: the anchor should lie between the lip and the
    # vantage, not behind the vantage. If the dot product of (anc-lip)
    # and (vantage-lip) is negative, the anchor is on the wrong side.
    vlip = tuple(v - L for v, L in zip(vantage_position, lip))
    alip = tuple(a - L for a, L in zip(anc, lip))
    dot = sum(v * a for v, a in zip(vlip, alip))
    vmag = math.sqrt(sum(v * v for v in vlip))
    if vmag > 1e-6 and dot < 0:
        issues.append(
            ValidationIssue(
                code="WATERFALL_ANCHOR_BEHIND_VANTAGE",
                severity="soft",
                affected_feature="waterfall",
                message="anchor is on the opposite side of the lip from the vantage",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Functional-object naming enforcement
# ---------------------------------------------------------------------------


_NAME_RE = re.compile(r"^WF_(?P<chain>[^_]+(?:_[^_]+)*?)_(?P<suffix>[a-z_]+)$")


def enforce_functional_object_naming(
    object_names: Sequence[str],
    chain_id: str,
) -> List[ValidationIssue]:
    """Check that every object belongs to ``chain_id`` and has a valid suffix.

    Objects that don't match the ``WF_<chain_id>_<suffix>`` template, or
    whose suffix is not one of the 7 canonical suffixes, yield hard issues.
    Additionally, missing required suffixes yield one hard issue per gap.
    """
    issues: List[ValidationIssue] = []
    expected_prefix = f"WF_{chain_id}_"

    seen: set[str] = set()
    for name in object_names:
        if not name.startswith(expected_prefix):
            issues.append(
                ValidationIssue(
                    code="WATERFALL_OBJECT_WRONG_CHAIN",
                    severity="hard",
                    affected_feature="waterfall",
                    message=(
                        f"object {name!r} does not start with "
                        f"prefix {expected_prefix!r}"
                    ),
                )
            )
            continue
        suffix = name[len(expected_prefix) :]
        if suffix not in FUNCTIONAL_SUFFIXES:
            issues.append(
                ValidationIssue(
                    code="WATERFALL_OBJECT_UNKNOWN_SUFFIX",
                    severity="hard",
                    affected_feature="waterfall",
                    message=(
                        f"object {name!r} has unknown suffix {suffix!r}; "
                        f"expected one of {FUNCTIONAL_SUFFIXES}"
                    ),
                )
            )
            continue
        seen.add(suffix)

    missing = [s for s in FUNCTIONAL_SUFFIXES if s not in seen]
    for m in missing:
        issues.append(
            ValidationIssue(
                code="WATERFALL_FUNCTIONAL_OBJECT_MISSING",
                severity="hard",
                affected_feature="waterfall",
                message=(
                    f"required functional object with suffix {m!r} missing "
                    f"from chain {chain_id!r}"
                ),
            )
        )

    return issues


__all__ = [
    "WaterfallVolumetricProfile",
    "WaterfallFunctionalObjects",
    "FUNCTIONAL_SUFFIXES",
    "build_waterfall_functional_object_names",
    "validate_waterfall_volumetric",
    "validate_waterfall_anchor_screen_space",
    "enforce_functional_object_naming",
]
