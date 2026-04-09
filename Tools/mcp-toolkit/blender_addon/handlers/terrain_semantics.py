"""Core semantic dataclasses for the VeilBreakers terrain pipeline.

This module is the single source of truth for terrain data contracts.
Every pass, validator, and handler in the terrain pipeline consumes or
produces instances of these types.

Bundle A — Foundation. See docs/terrain_ultra_implementation_plan_2026-04-08.md §5
for the authoritative specification. Any signature changes here require a
plan revision.

NO bpy / bmesh / Blender imports. Pure Python + numpy. Fully unit-testable
outside Blender.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
)

import numpy as np


# ---------------------------------------------------------------------------
# Support types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BBox:
    """Axis-aligned world-space bounding box in meters.

    Coordinates are world-space meters. Use ``contains``/``intersects``
    for protected-zone and region-scope checks.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def __post_init__(self) -> None:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError(
                f"BBox inverted: min=({self.min_x},{self.min_y}) "
                f"max=({self.max_x},{self.max_y})"
            )

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.min_x + self.max_x) * 0.5, (self.min_y + self.max_y) * 0.5)

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.min_x, self.min_y, self.max_x, self.max_y)

    def contains_point(self, x: float, y: float) -> bool:
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y

    def intersects(self, other: "BBox") -> bool:
        return not (
            other.max_x < self.min_x
            or other.min_x > self.max_x
            or other.max_y < self.min_y
            or other.min_y > self.max_y
        )

    def to_cell_slice(
        self,
        world_origin_x: float,
        world_origin_y: float,
        cell_size: float,
        grid_shape: Tuple[int, int],
    ) -> Tuple[slice, slice]:
        """Convert this BBox to numpy (row, col) slices for a grid."""
        rows, cols = grid_shape
        c0 = max(0, int(np.floor((self.min_x - world_origin_x) / cell_size)))
        c1 = min(cols, int(np.ceil((self.max_x - world_origin_x) / cell_size)) + 1)
        r0 = max(0, int(np.floor((self.min_y - world_origin_y) / cell_size)))
        r1 = min(rows, int(np.ceil((self.max_y - world_origin_y) / cell_size)) + 1)
        return slice(r0, r1), slice(c0, c1)


@dataclass(frozen=True)
class HeroFeatureRef:
    """Reference to an already-placed hero feature in the scene."""

    feature_id: str
    feature_kind: str
    world_position: Tuple[float, float, float]
    blender_object_name: Optional[str] = None


@dataclass(frozen=True)
class WaterfallChainRef:
    """Reference to a detected or placed waterfall chain."""

    chain_id: str
    lip_position: Tuple[float, float, float]
    pool_position: Tuple[float, float, float]
    drop_height: float


@dataclass(frozen=True)
class HeroFeatureBudget:
    """Per-feature resource budget (tri count, world footprint)."""

    max_tris: int
    max_footprint_meters: float
    max_vertex_color_channels: int = 4


# ---------------------------------------------------------------------------
# 5.1 TerrainMaskStack
# ---------------------------------------------------------------------------


@dataclass
class TerrainMaskStack:
    """Unified mask registry. Every signal the pipeline computes lives here.

    Channels are populated incrementally as passes run. Use ``.get()`` and
    ``.set()`` to read/write channels with provenance tracking. Fields are
    kept as Optional[np.ndarray] rather than a dict so static analysis
    and downstream pass contracts can type-check against them.
    """

    # Shape and coordinate contract
    tile_size: int
    cell_size: float
    world_origin_x: float
    world_origin_y: float
    tile_x: int
    tile_y: int

    # Core height channel (always present)
    height: np.ndarray

    # Structural masks (Pass 2)
    slope: Optional[np.ndarray] = None
    curvature: Optional[np.ndarray] = None
    concavity: Optional[np.ndarray] = None
    convexity: Optional[np.ndarray] = None
    ridge: Optional[np.ndarray] = None
    basin: Optional[np.ndarray] = None
    saliency_macro: Optional[np.ndarray] = None

    # Hero candidate masks (Pass 3)
    cliff_candidate: Optional[np.ndarray] = None
    cave_candidate: Optional[np.ndarray] = None
    waterfall_lip_candidate: Optional[np.ndarray] = None
    hero_exclusion: Optional[np.ndarray] = None

    # Erosion-derived masks (Pass 4)
    erosion_amount: Optional[np.ndarray] = None
    deposition_amount: Optional[np.ndarray] = None
    wetness: Optional[np.ndarray] = None
    talus: Optional[np.ndarray] = None
    drainage: Optional[np.ndarray] = None
    bank_instability: Optional[np.ndarray] = None

    # Water masks (Pass 5)
    flow_direction: Optional[np.ndarray] = None
    flow_accumulation: Optional[np.ndarray] = None
    water_surface: Optional[np.ndarray] = None
    foam: Optional[np.ndarray] = None
    mist: Optional[np.ndarray] = None
    wet_rock: Optional[np.ndarray] = None
    tidal: Optional[np.ndarray] = None

    # Material-zoning masks (Pass 7)
    biome_id: Optional[np.ndarray] = None
    material_weights: Optional[np.ndarray] = None
    roughness_variation: Optional[np.ndarray] = None
    macro_color: Optional[np.ndarray] = None

    # Ecosystem masks (Pass 9)
    audio_reverb_class: Optional[np.ndarray] = None
    wildlife_affinity: Optional[Dict[str, np.ndarray]] = None
    gameplay_zone: Optional[np.ndarray] = None
    wind_field: Optional[np.ndarray] = None
    cloud_shadow: Optional[np.ndarray] = None
    traversability: Optional[np.ndarray] = None
    decal_density: Optional[Dict[str, np.ndarray]] = None

    # Geology plausibility (Bundle I)
    strata_orientation: Optional[np.ndarray] = None
    rock_hardness: Optional[np.ndarray] = None
    snow_line_factor: Optional[np.ndarray] = None

    # Versioning and provenance
    schema_version: str = "1.0"
    content_hash: Optional[str] = None
    dirty_channels: Set[str] = field(default_factory=set)
    populated_by_pass: Dict[str, str] = field(default_factory=dict)

    # Set of channel names that are scalar ndarrays (not dict-of-ndarray)
    _ARRAY_CHANNELS: "Tuple[str, ...]" = field(
        init=False,
        repr=False,
        compare=False,
        default=(
            "height",
            "slope",
            "curvature",
            "concavity",
            "convexity",
            "ridge",
            "basin",
            "saliency_macro",
            "cliff_candidate",
            "cave_candidate",
            "waterfall_lip_candidate",
            "hero_exclusion",
            "erosion_amount",
            "deposition_amount",
            "wetness",
            "talus",
            "drainage",
            "bank_instability",
            "flow_direction",
            "flow_accumulation",
            "water_surface",
            "foam",
            "mist",
            "wet_rock",
            "tidal",
            "biome_id",
            "material_weights",
            "roughness_variation",
            "macro_color",
            "audio_reverb_class",
            "gameplay_zone",
            "wind_field",
            "cloud_shadow",
            "traversability",
            "strata_orientation",
            "rock_hardness",
            "snow_line_factor",
        ),
    )

    def __post_init__(self) -> None:
        if self.height is None:
            raise ValueError("TerrainMaskStack requires a populated 'height' channel")
        h = np.asarray(self.height)
        if h.ndim != 2:
            raise ValueError(
                f"height must be 2D (got shape {h.shape}); mask stack is tile-local"
            )
        # Always track 'height' as populated at construction time
        self.populated_by_pass.setdefault("height", "__init__")

    # -- core accessors -----------------------------------------------------

    def get(self, channel: str) -> Optional[np.ndarray]:
        """Return the named channel, or None if not yet populated.

        Supports scalar ndarray channels plus dict-valued channels
        (``wildlife_affinity``, ``decal_density``) via explicit key suffix
        ``channel[key]``.
        """
        if "[" in channel and channel.endswith("]"):
            base, key = channel[:-1].split("[", 1)
            container = getattr(self, base, None)
            if isinstance(container, dict):
                return container.get(key)
            return None
        return getattr(self, channel, None)

    def set(self, channel: str, value: np.ndarray, pass_name: str) -> None:
        """Store a channel value, record provenance, clear dirty flag."""
        if not hasattr(self, channel):
            raise AttributeError(f"Unknown mask channel: {channel}")
        setattr(self, channel, value)
        self.populated_by_pass[channel] = pass_name
        self.dirty_channels.discard(channel)
        # Any mutation invalidates cached hash
        self.content_hash = None

    def mark_dirty(self, channel: str) -> None:
        self.dirty_channels.add(channel)
        self.content_hash = None

    def mark_clean(self, channel: str) -> None:
        self.dirty_channels.discard(channel)

    def assert_channels_present(self, channels: List[str]) -> None:
        missing = [
            c
            for c in channels
            if self.get(c) is None
        ]
        if missing:
            raise KeyError(
                f"TerrainMaskStack missing required channels: {missing}"
            )

    # -- hashing ------------------------------------------------------------

    def compute_hash(self) -> str:
        """Deterministic content hash across all populated channels.

        Uses SHA-256 over channel name, dtype, shape, and raw bytes. The
        hash also covers the coordinate contract (tile coords + origin)
        so two stacks with identical signals but different locations do
        not collide.
        """
        hasher = hashlib.sha256()
        header = json.dumps(
            {
                "schema_version": self.schema_version,
                "tile_size": self.tile_size,
                "cell_size": float(self.cell_size),
                "world_origin_x": float(self.world_origin_x),
                "world_origin_y": float(self.world_origin_y),
                "tile_x": self.tile_x,
                "tile_y": self.tile_y,
            },
            sort_keys=True,
        ).encode("utf-8")
        hasher.update(header)

        for name in self._ARRAY_CHANNELS:
            val = getattr(self, name, None)
            if val is None:
                continue
            arr = np.ascontiguousarray(val)
            hasher.update(name.encode("utf-8"))
            hasher.update(str(arr.dtype).encode("utf-8"))
            hasher.update(repr(arr.shape).encode("utf-8"))
            hasher.update(arr.tobytes())

        for dict_field in ("wildlife_affinity", "decal_density"):
            container = getattr(self, dict_field, None)
            if not container:
                continue
            for k in sorted(container.keys()):
                arr = np.ascontiguousarray(container[k])
                hasher.update(f"{dict_field}[{k}]".encode("utf-8"))
                hasher.update(str(arr.dtype).encode("utf-8"))
                hasher.update(repr(arr.shape).encode("utf-8"))
                hasher.update(arr.tobytes())

        digest = hasher.hexdigest()
        self.content_hash = digest
        return digest

    # -- persistence --------------------------------------------------------

    def to_npz(self, path: Path) -> None:
        """Save all populated channels to a .npz archive."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays: Dict[str, np.ndarray] = {}
        for name in self._ARRAY_CHANNELS:
            val = getattr(self, name, None)
            if val is not None:
                arrays[name] = np.asarray(val)
        meta = {
            "schema_version": self.schema_version,
            "tile_size": self.tile_size,
            "cell_size": self.cell_size,
            "world_origin_x": self.world_origin_x,
            "world_origin_y": self.world_origin_y,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "populated_by_pass": dict(self.populated_by_pass),
            "dirty_channels": sorted(self.dirty_channels),
            "content_hash": self.compute_hash(),
        }
        arrays["__meta__"] = np.array(json.dumps(meta), dtype=object)
        np.savez_compressed(path, **arrays)

    @classmethod
    def from_npz(cls, path: Path) -> "TerrainMaskStack":
        path = Path(path)
        with np.load(path, allow_pickle=True) as data:
            meta_raw = data["__meta__"].item()
            meta = json.loads(meta_raw)
            height = np.array(data["height"])
            stack = cls(
                tile_size=int(meta["tile_size"]),
                cell_size=float(meta["cell_size"]),
                world_origin_x=float(meta["world_origin_x"]),
                world_origin_y=float(meta["world_origin_y"]),
                tile_x=int(meta["tile_x"]),
                tile_y=int(meta["tile_y"]),
                height=height,
            )
            for name in cls._ARRAY_CHANNELS:
                if name == "height":
                    continue
                if name in data.files:
                    setattr(stack, name, np.array(data[name]))
            stack.populated_by_pass.update(meta.get("populated_by_pass", {}))
            stack.dirty_channels.update(meta.get("dirty_channels", []))
            stack.schema_version = meta.get("schema_version", "1.0")
            return stack


# ---------------------------------------------------------------------------
# 5.6 ProtectedZoneSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtectedZoneSpec:
    """A region of the world that restricts which passes may mutate it."""

    zone_id: str
    bounds: BBox
    kind: str
    allowed_mutations: FrozenSet[str] = frozenset()
    forbidden_mutations: FrozenSet[str] = frozenset()
    description: str = ""

    def permits(self, pass_name: str) -> bool:
        if pass_name in self.forbidden_mutations:
            return False
        if self.allowed_mutations and pass_name not in self.allowed_mutations:
            return False
        return True


# ---------------------------------------------------------------------------
# 5.7 TerrainAnchor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerrainAnchor:
    """Named world-space empty with optional Blender object binding."""

    name: str
    world_position: Tuple[float, float, float]
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    anchor_kind: str = "generic"
    radius: float = 0.0
    blender_object_name: Optional[str] = None


# ---------------------------------------------------------------------------
# 5.4 HeroFeatureSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeroFeatureSpec:
    """Authored hero feature intent — a cliff, cave, waterfall, arch, canyon, etc."""

    feature_id: str
    feature_kind: str
    world_position: Tuple[float, float, float]
    orientation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    bounds: Optional[BBox] = None
    anchor_name: Optional[str] = None
    tier: str = "secondary"
    silhouette_vantages: Tuple[Tuple[float, float, float], ...] = ()
    exclusion_radius: float = 0.0
    budget: Optional[HeroFeatureBudget] = None
    parameters: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5.5 WaterSystemSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WaterSystemSpec:
    """Global water authoring parameters for a region."""

    network_seed: int
    min_drainage_area: float = 500.0
    river_threshold: float = 2000.0
    lake_min_area: float = 100.0
    meander_amplitude: float = 0.0
    bank_asymmetry: float = 0.0
    tidal_range: float = 0.0
    hero_waterfalls: Tuple[str, ...] = ()
    braided_channels: bool = False
    estuaries: bool = False
    karst_springs: bool = False
    perched_lakes: bool = False
    hot_springs: bool = False
    wetlands: bool = False
    seasonal_state: str = "normal"


# ---------------------------------------------------------------------------
# 5.3 TerrainSceneRead
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerrainSceneRead:
    """Structured scene-understanding snapshot required before any mutation.

    The orchestrator refuses to run mutating passes without this attached
    to the current ``TerrainIntentState``.
    """

    timestamp: float
    major_landforms: Tuple[str, ...]
    focal_point: Tuple[float, float, float]
    hero_features_present: Tuple[HeroFeatureRef, ...]
    hero_features_missing: Tuple[str, ...]
    waterfall_chains: Tuple[WaterfallChainRef, ...]
    cave_candidates: Tuple[Tuple[float, float, float], ...]
    protected_zones_in_region: Tuple[str, ...]
    edit_scope: BBox
    success_criteria: Tuple[str, ...]
    reviewer: str


# ---------------------------------------------------------------------------
# 5.2 TerrainIntentState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TerrainIntentState:
    """Immutable authoring intent. Captured before any mutation runs."""

    seed: int
    region_bounds: BBox
    tile_size: int
    cell_size: float

    anchors: Tuple[TerrainAnchor, ...] = ()
    protected_zones: Tuple[ProtectedZoneSpec, ...] = ()
    hero_feature_specs: Tuple[HeroFeatureSpec, ...] = ()
    water_system_spec: Optional[WaterSystemSpec] = None
    quality_profile: str = "production"
    biome_rules: Optional[str] = None

    scene_read: Optional[TerrainSceneRead] = None

    morphology_templates: Tuple[str, ...] = ()
    noise_profile: str = "dark_fantasy_default"
    erosion_profile: str = "temperate"
    composition_hints: Dict[str, Any] = field(default_factory=dict)

    def with_scene_read(self, scene_read: TerrainSceneRead) -> "TerrainIntentState":
        """Return a copy of this intent with scene_read attached."""
        from dataclasses import replace as _replace

        return _replace(self, scene_read=scene_read)

    def intent_hash(self) -> str:
        """Deterministic hash of authoring intent (excluding scene_read)."""
        payload = {
            "seed": self.seed,
            "region_bounds": self.region_bounds.to_tuple(),
            "tile_size": self.tile_size,
            "cell_size": self.cell_size,
            "quality_profile": self.quality_profile,
            "biome_rules": self.biome_rules,
            "noise_profile": self.noise_profile,
            "erosion_profile": self.erosion_profile,
            "hero_feature_specs": [
                (
                    h.feature_id,
                    h.feature_kind,
                    h.world_position,
                    h.tier,
                )
                for h in self.hero_feature_specs
            ],
            "protected_zones": [
                (z.zone_id, z.bounds.to_tuple(), z.kind) for z in self.protected_zones
            ],
            "anchors": [(a.name, a.world_position, a.anchor_kind) for a in self.anchors],
            "composition_hints": sorted(self.composition_hints.items()),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()


# ---------------------------------------------------------------------------
# 5.9 ValidationIssue
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    code: str
    severity: str  # "hard" | "soft" | "info"
    location: Optional[Tuple[float, float, float]] = None
    affected_feature: Optional[str] = None
    message: str = ""
    remediation: Optional[str] = None

    def is_hard(self) -> bool:
        return self.severity == "hard"


# ---------------------------------------------------------------------------
# 5.8 PassResult
# ---------------------------------------------------------------------------


@dataclass
class PassResult:
    pass_name: str
    status: str  # "ok" | "warning" | "failed"
    duration_seconds: float
    produced_channels: Tuple[str, ...] = ()
    consumed_channels: Tuple[str, ...] = ()
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    seed_used: int = 0
    content_hash_before: Optional[str] = None
    content_hash_after: Optional[str] = None
    checkpoint_path: Optional[str] = None

    def ok(self) -> bool:
        return self.status == "ok"


# ---------------------------------------------------------------------------
# 5.13 TerrainCheckpoint
# ---------------------------------------------------------------------------


@dataclass
class TerrainCheckpoint:
    checkpoint_id: str
    pass_name: str
    timestamp: float
    intent_hash: str
    mask_stack_path: Path
    geometry_snapshot_path: Optional[Path]  # None if Blender snapshot not available
    content_hash: str
    parent_checkpoint_id: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 5.11 PassDefinition
# ---------------------------------------------------------------------------


@dataclass
class PassDefinition:
    """Static metadata describing a pass: contracts + behavior flags."""

    name: str
    func: Callable[["TerrainPipelineState", Optional[BBox]], PassResult]
    requires_channels: Tuple[str, ...] = ()
    produces_channels: Tuple[str, ...] = ()
    requires_features: Tuple[str, ...] = ()
    idempotent: bool = True
    deterministic: bool = True
    may_modify_geometry: bool = False
    may_add_geometry: bool = False
    respects_protected_zones: bool = True
    supports_region_scope: bool = True
    seed_namespace: str = ""
    requires_scene_read: bool = False


# ---------------------------------------------------------------------------
# Pipeline state (mutable runtime container)
# ---------------------------------------------------------------------------


@dataclass
class TerrainPipelineState:
    """Mutable runtime state that flows through the pass orchestrator.

    Holds the immutable intent, the current (mutable) mask stack, the
    checkpoint history, and the pass history. Passed by reference into
    each pass function.
    """

    intent: TerrainIntentState
    mask_stack: TerrainMaskStack
    checkpoints: List[TerrainCheckpoint] = field(default_factory=list)
    pass_history: List[PassResult] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)

    @property
    def tile_x(self) -> int:
        return self.mask_stack.tile_x

    @property
    def tile_y(self) -> int:
        return self.mask_stack.tile_y

    def record_pass(self, result: PassResult) -> None:
        self.pass_history.append(result)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class SceneReadRequired(RuntimeError):
    """Raised when a pass tries to run without an attached TerrainSceneRead."""


class ProtectedZoneViolation(RuntimeError):
    """Raised when a pass attempts to mutate a zone it is not permitted to touch."""


class PassContractError(RuntimeError):
    """Raised when a pass's produced/consumed channels violate its definition."""


class UnknownPassError(KeyError):
    """Raised when a pass name is not registered with the controller."""


__all__ = [
    "BBox",
    "HeroFeatureRef",
    "WaterfallChainRef",
    "HeroFeatureBudget",
    "TerrainMaskStack",
    "ProtectedZoneSpec",
    "TerrainAnchor",
    "HeroFeatureSpec",
    "WaterSystemSpec",
    "TerrainSceneRead",
    "TerrainIntentState",
    "ValidationIssue",
    "PassResult",
    "TerrainCheckpoint",
    "PassDefinition",
    "TerrainPipelineState",
    "SceneReadRequired",
    "ProtectedZoneViolation",
    "PassContractError",
    "UnknownPassError",
]
