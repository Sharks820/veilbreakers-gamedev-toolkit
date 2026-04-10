"""Bundle N / §33 supplements — Unity export contracts (Addendum 1.B.9).

Pure stdlib + numpy. No bpy.

Codifies the bit-depth precision contract and the named terrain mesh
attributes required by the Unity shader + geometry-node consumer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .terrain_semantics import ValidationIssue


# ---------------------------------------------------------------------------
# Bit-depth contract dataclass
# ---------------------------------------------------------------------------


@dataclass
class UnityExportContract:
    """Per-file bit-depth precision contract.

    - heightmap.exr must be 32-bit float (16-bit only in preview profile)
    - mask_stack.npz channels preserve source dtype (no silent downcast)
    - shadow_clipmap.exr must be 32-bit float
    - splatmap.exr must be >= 16-bit per channel
    """

    heightmap_bit_depth: int = 32
    heightmap_encoding: str = "float"
    splatmap_bit_depth: int = 16
    shadow_clipmap_bit_depth: int = 32
    mask_stack_preserves_dtype: bool = True

    def minimum_for(self, file_kind: str) -> int:
        if file_kind == "heightmap":
            return self.heightmap_bit_depth
        if file_kind == "splatmap":
            return self.splatmap_bit_depth
        if file_kind == "shadow_clipmap":
            return self.shadow_clipmap_bit_depth
        return 0


# ---------------------------------------------------------------------------
# Named mesh attribute contract
# ---------------------------------------------------------------------------


REQUIRED_MESH_ATTRIBUTES: Tuple[str, ...] = (
    "slope_angle",
    "flow_accumulation",
    "wetness",
    "biome_id",
    "cliff_mask",
    "protected_zone_id",
)
assert len(REQUIRED_MESH_ATTRIBUTES) == 6, "§33 requires exactly 6 mesh attrs"


# Addendum 1 §33 — every exported terrain mesh must carry these 6 named
# vertex-level attributes so the Unity terrain shader can bind them.
REQUIRED_VERTEX_ATTRIBUTES: Tuple[str, ...] = (
    "position",
    "normal",
    "uv0",
    "tangent",
    "color",
    "uv1",  # lightmap UVs
)
assert len(REQUIRED_VERTEX_ATTRIBUTES) == 6, "§33 addendum requires exactly 6 vertex attrs"


def validate_mesh_attributes_present(
    attr_names: Iterable[str],
) -> List[ValidationIssue]:
    """Emit a hard issue per missing required mesh attribute."""
    present = set(attr_names)
    issues: List[ValidationIssue] = []
    for name in REQUIRED_MESH_ATTRIBUTES:
        if name not in present:
            issues.append(
                ValidationIssue(
                    code="MESH_ATTR_MISSING",
                    severity="hard",
                    affected_feature=name,
                    message=f"Required mesh attribute {name!r} missing",
                    remediation=(
                        "Bake this attribute in the Unity export pass "
                        "before writing the mesh"
                    ),
                )
            )
    return issues


def validate_vertex_attributes_present(
    attr_names: Iterable[str],
) -> List[ValidationIssue]:
    """Emit a hard issue per missing required vertex attribute (Addendum 1 §33)."""
    present = set(attr_names)
    issues: List[ValidationIssue] = []
    for name in REQUIRED_VERTEX_ATTRIBUTES:
        if name not in present:
            issues.append(
                ValidationIssue(
                    code="VERTEX_ATTR_MISSING",
                    severity="hard",
                    affected_feature=name,
                    message=f"Required vertex attribute {name!r} missing from terrain mesh",
                    remediation=(
                        "Ensure the mesh exporter writes all 6 required "
                        "vertex attributes: position, normal, uv0, tangent, "
                        "color, uv1 (lightmap UVs)"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------


def write_export_manifest(output_dir: Path, files: Dict[str, Dict[str, Any]]) -> Path:
    """Write manifest.json recording per-file {bit_depth, channels, encoding}.

    ``files`` maps filename -> metadata dict containing at minimum the
    three required keys. Any extra keys are preserved verbatim.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for fname, meta in files.items():
        for required in ("bit_depth", "channels", "encoding"):
            if required not in meta:
                raise ValueError(
                    f"manifest file {fname!r} missing required key {required!r}"
                )
    manifest_path = output_dir / "manifest.json"
    payload = {"version": "1.0", "files": files}
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return manifest_path


# ---------------------------------------------------------------------------
# Bit-depth validator
# ---------------------------------------------------------------------------


def validate_bit_depth_contract(
    contract: UnityExportContract,
    file_metadata: Dict[str, Dict[str, Any]],
) -> List[ValidationIssue]:
    """Validate per-file metadata against a UnityExportContract.

    Checks heightmap/splatmap/shadow_clipmap bit depths. Unrecognized
    files are ignored (they are not covered by the contract).
    """
    issues: List[ValidationIssue] = []

    kind_map = {
        "heightmap": ("heightmap", contract.heightmap_bit_depth),
        "heightmap.exr": ("heightmap", contract.heightmap_bit_depth),
        "splatmap": ("splatmap", contract.splatmap_bit_depth),
        "splatmap.exr": ("splatmap", contract.splatmap_bit_depth),
        "shadow_clipmap": ("shadow_clipmap", contract.shadow_clipmap_bit_depth),
        "shadow_clipmap.exr": ("shadow_clipmap", contract.shadow_clipmap_bit_depth),
    }

    for fname, meta in file_metadata.items():
        key = fname.lower()
        mapping = kind_map.get(key)
        if mapping is None:
            # Try stripped suffix
            base = key.rsplit(".", 1)[0]
            mapping = kind_map.get(base)
        if mapping is None:
            # Check for mask_stack dtype preservation (Addendum 1 §33)
            if "mask_stack" in key and contract.mask_stack_preserves_dtype:
                expected_dtype = meta.get("source_dtype")
                actual_dtype = meta.get("dtype")
                if (
                    expected_dtype
                    and actual_dtype
                    and expected_dtype != actual_dtype
                ):
                    issues.append(
                        ValidationIssue(
                            code="MASK_STACK_DTYPE_MISMATCH",
                            severity="hard",
                            affected_feature=fname,
                            message=(
                                f"{fname} dtype={actual_dtype!r} != source "
                                f"dtype={expected_dtype!r} — silent downcast"
                            ),
                            remediation=(
                                "Preserve source dtype when writing "
                                "mask_stack.npz channels"
                            ),
                        )
                    )
            continue
        kind, required = mapping
        actual = int(meta.get("bit_depth", 0))
        if actual < required:
            issues.append(
                ValidationIssue(
                    code="BIT_DEPTH_VIOLATION",
                    severity="hard",
                    affected_feature=fname,
                    message=(
                        f"{fname} bit_depth={actual} < required {required} "
                        f"for {kind}"
                    ),
                    remediation=(
                        "Re-export with the correct bit depth — preview "
                        "profile only permitted for heightmap"
                    ),
                )
            )
        if kind == "heightmap":
            enc = meta.get("encoding", "")
            if enc != contract.heightmap_encoding:
                issues.append(
                    ValidationIssue(
                        code="HEIGHTMAP_ENCODING_VIOLATION",
                        severity="hard",
                        affected_feature=fname,
                        message=(
                            f"{fname} encoding={enc!r} != "
                            f"{contract.heightmap_encoding!r}"
                        ),
                        remediation="Re-export heightmap as float",
                    )
                )
        if kind == "shadow_clipmap":
            enc = meta.get("encoding", "")
            if enc and enc != "float":
                issues.append(
                    ValidationIssue(
                        code="SHADOW_CLIPMAP_ENCODING_VIOLATION",
                        severity="hard",
                        affected_feature=fname,
                        message=(
                            f"{fname} encoding={enc!r} != 'float' — "
                            f"shadow clipmap must be 32-bit float"
                        ),
                        remediation="Re-export shadow_clipmap.exr as float32",
                    )
                )

    return issues
