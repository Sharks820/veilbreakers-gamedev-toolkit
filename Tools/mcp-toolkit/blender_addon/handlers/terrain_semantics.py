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

import enum
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
# Bundle A supplements (Addendum 1.B.1 + Addendum 2.A + Addendum 3)
# ---------------------------------------------------------------------------


class ErosionStrategy(enum.Enum):
    """Erosion orchestration strategy (Addendum 3.B.1).

    EXACT — erode full world heightmap, then split. Bit-exact seams.
    TILED_PADDED — per-tile erosion with overlap margins.
    TILED_DISTRIBUTED_HALO — distributed erosion with halo blending for
        worlds too large to erode in a single pass.
    """

    EXACT = "exact"
    TILED_PADDED = "tiled_padded"
    TILED_DISTRIBUTED_HALO = "tiled_distributed_halo"


@dataclass(frozen=True)
class SectorOrigin:
    """Km-scale anchor for floating-origin coordinate system (Addendum 3.B.2).

    For worlds > 10 km, raw world coordinates lose float32 precision at
    the render boundary. Sectors carry their own anchor so tile world
    coordinates are stored relative to a nearby km-scale origin.
    """

    name: str
    world_x_m: float
    world_y_m: float


@dataclass
class WorldHeightTransform:
    """Normalized ↔ world heights adapter (Addendum 3.B.6).

    Path solvers (river A*, road placement) operate on ``[0, 1]`` heights
    for math simplicity. This adapter makes the conversion explicit and
    reversible so that signed/negative-elevation world heights round-trip
    without collapsing to zero — the persistent scatter-altitude bug.
    """

    world_min: float
    world_max: float
    world_range: float = 0.0

    def __post_init__(self) -> None:
        rng = float(self.world_max) - float(self.world_min)
        # Guard against degenerate/zero range — keep adapter usable.
        self.world_range = rng if rng != 0.0 else 1.0
        self.world_min = float(self.world_min)
        self.world_max = float(self.world_max)

    def to_normalized(self, world_heights: np.ndarray) -> np.ndarray:
        arr = np.asarray(world_heights, dtype=np.float64)
        return (arr - self.world_min) / self.world_range

    def from_normalized(self, normalized: np.ndarray) -> np.ndarray:
        arr = np.asarray(normalized, dtype=np.float64)
        return arr * self.world_range + self.world_min


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
    cave_height_delta: Optional[np.ndarray] = None
    waterfall_lip_candidate: Optional[np.ndarray] = None
    waterfall_pool_delta: Optional[np.ndarray] = None
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

    # Bundle A supplements (Addendum 1.B.1 erosion mask preservation)
    sediment_accumulation_at_base: Optional[np.ndarray] = None
    pool_deepening_delta: Optional[np.ndarray] = None

    # -- Unity integratable channels (AAA round-trip contract) --
    # Per-layer splatmap weights (Unity Terrain Layer alphamaps). Shape (H, W, L).
    splatmap_weights_layer: Optional[np.ndarray] = None
    # 16-bit quantized heightmap for Unity .raw import. uint16 shape (H, W).
    heightmap_raw_u16: Optional[np.ndarray] = None
    # Navmesh area classification: walkable/unwalkable/jump/climb per cell.
    navmesh_area_id: Optional[np.ndarray] = None
    # Physics collider tag: solid / trigger / nocollide.
    physics_collider_mask: Optional[np.ndarray] = None
    # Lightmap UV chart grouping for Unity Progressive GPU lightmapper.
    lightmap_uv_chart_id: Optional[np.ndarray] = None
    # LOD bias + streaming priority per cell (Unity Addressables).
    lod_bias: Optional[np.ndarray] = None
    # Grass/foliage/detail density per type. dict[type] -> (H, W) float32.
    detail_density: Optional[Dict[str, np.ndarray]] = None
    # Tree instance spawn list. Stored as ndarray of shape (N, 5):
    # (x, y, z, rot, prototype_id). Unity consumer: TerrainData.treeInstances.
    tree_instance_points: Optional[np.ndarray] = None
    # Baked ambient occlusion (not computed from curvature).
    ambient_occlusion_bake: Optional[np.ndarray] = None

    # -- World-unit scalar metadata (required for Unity .raw round-trip) --
    height_min_m: Optional[float] = None
    height_max_m: Optional[float] = None
    # "z-up" or "y-up" — VeilBreakers pipeline is Z-UP end-to-end.
    coordinate_system: str = "z-up"
    # Semantic Unity export schema version for PR round-trip compatibility.
    unity_export_schema_version: str = "1.0"

    # Versioning and provenance
    schema_version: str = "1.0"
    content_hash: Optional[str] = None
    dirty_channels: Set[str] = field(default_factory=set)
    populated_by_pass: Dict[str, str] = field(default_factory=dict)

    # Set of channel names that are scalar ndarrays (not dict-of-ndarray).
    # Used by compute_hash / to_npz / from_npz — any new ndarray field MUST
    # be added here or it will be silently dropped on serialization.
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
            "cave_height_delta",
            "waterfall_lip_candidate",
            "waterfall_pool_delta",
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
            # Bundle A supplements (Addendum 1.B.1)
            "sediment_accumulation_at_base",
            "pool_deepening_delta",
            # Unity-ready channels
            "splatmap_weights_layer",
            "heightmap_raw_u16",
            "navmesh_area_id",
            "physics_collider_mask",
            "lightmap_uv_chart_id",
            "lod_bias",
            "tree_instance_points",
            "ambient_occlusion_bake",
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
        # Auto-populate world-unit height range if not already set
        if self.height_min_m is None:
            self.height_min_m = float(h.min()) if h.size else 0.0
        if self.height_max_m is None:
            self.height_max_m = float(h.max()) if h.size else 0.0
        if self.coordinate_system not in ("z-up", "y-up"):
            raise ValueError(
                f"coordinate_system must be 'z-up' or 'y-up', got {self.coordinate_system!r}"
            )
        # Addendum 2.A.1 tile-resolution contract:
        # when tile_size > 0 the height field SHOULD be (tile_size + 1, tile_size + 1)
        # (power-of-2+1 Unity-compatible shared-edge contract). Legacy callers
        # created stacks with shape == (tile_size, tile_size); those are still
        # accepted for backward compat, but a shape that matches neither is a bug.
        # tile_size == 0 is allowed for non-tile mask stacks.
        if self.tile_size and self.tile_size > 0:
            ts = int(self.tile_size)
            expected_new = (ts + 1, ts + 1)
            expected_legacy = (ts, ts)
            # Only enforce the square tile contract for square shapes — legacy
            # non-tile mask stacks (e.g. rows != cols) are allowed through.
            if h.shape[0] == h.shape[1] and h.shape not in (expected_new, expected_legacy):
                raise ValueError(
                    f"TerrainMaskStack height shape {h.shape} violates tile "
                    f"resolution contract: tile_size={self.tile_size} requires "
                    f"{expected_new} (new Addendum 2.A.1 contract) or "
                    f"{expected_legacy} (legacy)."
                )

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

    # -- Unity export manifest -------------------------------------------------

    UNITY_EXPORT_CHANNELS: Tuple[str, ...] = (
        "height",
        "splatmap_weights_layer",
        "heightmap_raw_u16",
        "navmesh_area_id",
        "physics_collider_mask",
        "lightmap_uv_chart_id",
        "lod_bias",
        "tree_instance_points",
        "ambient_occlusion_bake",
        "wind_field",
        "cloud_shadow",
        "traversability",
        "gameplay_zone",
        "audio_reverb_class",
    )

    def unity_export_manifest(self) -> Dict[str, Any]:
        """Return a dict describing everything Unity needs to round-trip this tile.

        Consumed by a future ``unity_export`` pass (Bundle K/N). Every
        Unity-visible contract lives here — if you add a new Unity-ready
        channel, update ``UNITY_EXPORT_CHANNELS`` AND this manifest so the
        Unity-side importer knows to look for it.
        """
        populated: Dict[str, Any] = {}
        for ch in self.UNITY_EXPORT_CHANNELS:
            arr = self.get(ch)
            if arr is None:
                continue
            arr_np = np.asarray(arr)
            populated[ch] = {
                "dtype": str(arr_np.dtype),
                "shape": list(arr_np.shape),
                "populated_by_pass": self.populated_by_pass.get(ch),
            }
        # Per-type detail layers (dict channel)
        if self.detail_density:
            populated["detail_density"] = {
                k: {"dtype": str(np.asarray(v).dtype), "shape": list(np.asarray(v).shape)}
                for k, v in self.detail_density.items()
            }
        return {
            "schema_version": self.unity_export_schema_version,
            "coordinate_system": self.coordinate_system,
            "tile_size": self.tile_size,
            "cell_size_m": float(self.cell_size),
            "world_origin_x_m": float(self.world_origin_x),
            "world_origin_y_m": float(self.world_origin_y),
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "height_min_m": float(self.height_min_m) if self.height_min_m is not None else None,
            "height_max_m": float(self.height_max_m) if self.height_max_m is not None else None,
            "world_tile_extent_m": float(self.tile_size) * float(self.cell_size),
            "populated_channels": populated,
            "content_hash": self.content_hash or self.compute_hash(),
        }

    # -- hashing ------------------------------------------------------------

    def compute_hash(self) -> str:
        """Deterministic content hash across all populated channels.

        Uses SHA-256 over channel name, dtype, shape, and raw bytes. The
        hash covers the coordinate contract (tile coords + origin),
        Unity-export scalar metadata (height_min/max, coordinate_system,
        unity_export_schema_version), and every populated channel.
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
                "height_min_m": float(self.height_min_m) if self.height_min_m is not None else None,
                "height_max_m": float(self.height_max_m) if self.height_max_m is not None else None,
                "coordinate_system": self.coordinate_system,
                "unity_export_schema_version": self.unity_export_schema_version,
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
    composition_hints: Dict[str, Any] = field(default_factory=dict)  # REVIEW-IGNORE PY-COR-17: frozen+mutable is safe here — callers treat as read-only, intent_hash() uses sorted items

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

    # Unity-ready round-trip metadata — needed to reconstruct a tile's
    # world-space contract without re-reading the mask stack.
    world_bounds: Optional[BBox] = None
    height_min_m: Optional[float] = None
    height_max_m: Optional[float] = None
    cell_size_m: Optional[float] = None
    tile_size: Optional[int] = None
    coordinate_system: str = "z-up"
    unity_export_schema_version: str = "1.0"
    splatmap_layer_ids: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# 5.11 PassDefinition
# ---------------------------------------------------------------------------


@dataclass
class QualityGate:
    """A declarative post-pass quality check.

    The ``check`` callable runs after a pass completes successfully. It
    receives the fresh ``PassResult`` and the mutated ``TerrainMaskStack``
    and returns a list of ``ValidationIssue``. Any hard issue downgrades
    the pass status to ``"failed"``; soft issues downgrade to ``"warning"``.

    Use quality gates for visual-semantic checks that go beyond
    "did the function return a value":
        - cliffs: does every registered cliff have lip+face+ledges+talus?
        - erosion: wetness mask populated in >= 5% of cells?
        - materials: no single material dominates > 80% of the tile?
        - waterfalls: each chain has lip → plunge → pool → outflow?

    A gate is the mechanism by which AI agents enforce AAA quality.
    If a gate does not exist, the quality is not enforced — write one.
    """

    name: str
    check: Callable[["PassResult", "TerrainMaskStack"], List["ValidationIssue"]]
    description: str = ""
    blocking: bool = True  # if False, issues become warnings regardless of severity


@dataclass
class PassDefinition:
    """Static metadata describing a pass: contracts + behavior flags.

    This is the single source of enforcement for Rule 1 of the agent
    protocol ("all mutating terrain operations route through
    TerrainPassController"). Any code that wants to mutate terrain must
    wrap itself in a PassDefinition and register it.
    """

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

    # Quality enforcement
    quality_gate: Optional[QualityGate] = None
    # Optional visual validator — a callable that given the mask stack
    # returns a visual signature (e.g. a low-res thumbnail byte string)
    # used by future bundles for visual-diff regression. Signature
    # is stored on the mask stack after the pass.
    visual_validator: Optional[Callable[["TerrainMaskStack"], bytes]] = None
    # Short human-readable description for agent logs and protocol docs.
    description: str = ""


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
    "ErosionStrategy",
    "SectorOrigin",
    "WorldHeightTransform",
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
