"""Environmental Model Library -- persistent catalog of Tripo-generated scatter models.

Manages a library of low-poly environmental scatter models for terrain instancing.
Models are generated once via Tripo AI, stored with metadata, and served to the
scatter pipeline. Each item type has 4 variations for visual diversity.

Usage::

    from veilbreakers_mcp.shared.env_model_library import EnvModelLibrary

    lib = EnvModelLibrary("/path/to/library")
    missing = lib.get_missing_models()
    # ... generate models via Tripo ...
    lib.register_variant(variant)
    scatter_set = lib.get_biome_scatter_set("thornwood_forest")
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catalog: every environmental scatter model type with generation prompts
# ---------------------------------------------------------------------------

ENV_MODEL_CATALOG: dict[str, list[dict]] = {
    "rocks": [
        {"name": "rock_small", "prompt": "small rough rock, 30cm, mossy patches", "target_tris": 200, "scale_range": (0.2, 0.5)},
        {"name": "rock_medium", "prompt": "medium jagged rock, 60cm, weathered surface", "target_tris": 400, "scale_range": (0.4, 0.8)},
        {"name": "boulder", "prompt": "large boulder, 1.5m, cracks and moss", "target_tris": 800, "scale_range": (1.0, 2.0)},
        {"name": "rock_flat", "prompt": "flat stepping stone rock, 40cm wide, mossy top", "target_tris": 150, "scale_range": (0.3, 0.6)},
    ],
    "foliage": [
        {"name": "fern", "prompt": "forest fern plant, 40cm, dark green fronds", "target_tris": 300, "scale_range": (0.3, 0.6)},
        {"name": "bush_small", "prompt": "small thorny bush, 50cm, dark leaves", "target_tris": 400, "scale_range": (0.4, 0.7)},
        {"name": "bush_large", "prompt": "large overgrown bush, 1m, tangled branches", "target_tris": 600, "scale_range": (0.8, 1.3)},
        {"name": "shrub_flowering", "prompt": "small flowering shrub, 40cm, muted purple flowers", "target_tris": 400, "scale_range": (0.3, 0.6)},
        {"name": "shrub_dead", "prompt": "dead dried shrub, leafless twisted branches, 50cm", "target_tris": 250, "scale_range": (0.4, 0.7)},
        {"name": "ivy_ground", "prompt": "ground ivy patch, low spreading, dark green leaves", "target_tris": 200, "scale_range": (0.5, 1.0)},
    ],
    "trees": [
        {"name": "tree_young", "prompt": "young sapling tree, 2m tall, thin trunk, few branches", "target_tris": 600, "scale_range": (1.5, 2.5)},
        {"name": "tree_stump", "prompt": "old cut tree stump, 40cm tall, mossy, mushrooms growing", "target_tris": 400, "scale_range": (0.3, 0.6)},
        {"name": "tree_dead_standing", "prompt": "dead standing tree, no leaves, gnarled bare branches", "target_tris": 500, "scale_range": (2.0, 4.0)},
    ],
    "ground_cover": [
        {"name": "sticks_pile", "prompt": "small pile of sticks and twigs on ground, 30cm", "target_tris": 150, "scale_range": (0.2, 0.4)},
        {"name": "fallen_log", "prompt": "fallen rotting log, 2m long, moss covered, dark bark", "target_tris": 500, "scale_range": (1.5, 3.0)},
        {"name": "fallen_branch", "prompt": "fallen tree branch on ground, 1m, broken", "target_tris": 200, "scale_range": (0.8, 1.5)},
        {"name": "leaf_pile", "prompt": "pile of dead brown leaves on ground, 40cm across", "target_tris": 100, "scale_range": (0.3, 0.6)},
        {"name": "pinecones", "prompt": "cluster of 3 pinecones on ground, brown, 15cm", "target_tris": 150, "scale_range": (0.1, 0.2)},
    ],
    "grass": [
        {"name": "grass_tall", "prompt": "tall wild grass clump, 60cm, swaying, green-brown", "target_tris": 150, "scale_range": (0.4, 0.8)},
        {"name": "grass_short", "prompt": "short meadow grass tuft, 15cm, dense green", "target_tris": 100, "scale_range": (0.1, 0.3)},
        {"name": "grass_dead", "prompt": "dead dry grass clump, 40cm, yellow-brown, brittle", "target_tris": 100, "scale_range": (0.3, 0.6)},
        {"name": "grass_swamp", "prompt": "swamp sedge grass, 50cm, dark green, partially submerged roots", "target_tris": 150, "scale_range": (0.4, 0.7)},
        {"name": "grass_alpine", "prompt": "alpine grass tuft, 20cm, sparse, wind-swept", "target_tris": 100, "scale_range": (0.15, 0.3)},
    ],
    "water_edge": [
        {"name": "reeds", "prompt": "cluster of water reeds, 1m tall, brown tops, green stalks", "target_tris": 200, "scale_range": (0.7, 1.2)},
        {"name": "cattails", "prompt": "cattail plants in water, 1.2m, brown seed heads", "target_tris": 200, "scale_range": (0.8, 1.3)},
        {"name": "lilypad", "prompt": "floating lilypad, 30cm diameter, green, water surface", "target_tris": 50, "scale_range": (0.2, 0.4)},
        {"name": "shore_driftwood", "prompt": "bleached driftwood piece on shore, 80cm, smooth weathered", "target_tris": 300, "scale_range": (0.5, 1.0)},
    ],
    "underwater": [
        {"name": "kelp", "prompt": "underwater kelp strand, 2m long, dark green, flowing", "target_tris": 200, "scale_range": (1.5, 3.0)},
        {"name": "seaweed", "prompt": "short seaweed clump on rocks, 40cm, dark brown-green", "target_tris": 150, "scale_range": (0.3, 0.6)},
        {"name": "underwater_log", "prompt": "sunken waterlogged log, 1.5m, dark, algae covered", "target_tris": 400, "scale_range": (1.0, 2.0)},
        {"name": "underwater_rock", "prompt": "smooth river rock underwater, 30cm, algae tinted", "target_tris": 150, "scale_range": (0.2, 0.5)},
        {"name": "underwater_sticks", "prompt": "tangled sticks and debris underwater, 50cm pile", "target_tris": 200, "scale_range": (0.3, 0.7)},
    ],
    "detail": [
        {"name": "mushroom_cluster", "prompt": "cluster of small mushrooms, 15cm, brown caps, forest floor", "target_tris": 200, "scale_range": (0.1, 0.2)},
        {"name": "bones_small", "prompt": "scattered small animal bones on ground, weathered white", "target_tris": 150, "scale_range": (0.2, 0.4)},
        {"name": "debris_stone", "prompt": "crumbled stone debris pile, 40cm, broken masonry", "target_tris": 250, "scale_range": (0.3, 0.6)},
    ],
}


# ---------------------------------------------------------------------------
# Biome-to-scatter mapping
# ---------------------------------------------------------------------------

BIOME_SCATTER_MAPPING: dict[str, list[str]] = {
    "thornwood_forest": [
        "rock_small", "rock_medium", "fern", "bush_small", "bush_large",
        "tree_young", "tree_stump", "fallen_log", "fallen_branch", "sticks_pile",
        "leaf_pile", "mushroom_cluster", "grass_tall", "ivy_ground",
    ],
    "corrupted_swamp": [
        "rock_small", "shrub_dead", "tree_stump", "tree_dead_standing",
        "fallen_log", "sticks_pile", "grass_swamp", "grass_dead", "bones_small",
        "reeds", "cattails", "lilypad", "seaweed", "underwater_sticks",
    ],
    "mountain_pass": [
        "rock_small", "rock_medium", "boulder", "rock_flat",
        "grass_alpine", "grass_dead", "shrub_dead", "sticks_pile",
        "fallen_branch", "debris_stone",
    ],
    "mountain_pass_summer": [
        "rock_small", "rock_medium", "boulder", "rock_flat",
        "grass_alpine", "grass_short", "bush_small", "fern",
        "fallen_branch", "sticks_pile",
    ],
    "mountain_pass_winter": [
        "rock_small", "rock_medium", "boulder", "rock_flat",
        "grass_dead", "shrub_dead", "sticks_pile", "fallen_branch",
    ],
    "ruined_fortress": [
        "rock_small", "rock_medium", "debris_stone", "bones_small",
        "grass_dead", "shrub_dead", "ivy_ground", "sticks_pile",
        "fallen_branch", "tree_stump",
    ],
    "abandoned_village": [
        "rock_small", "debris_stone", "bush_small", "shrub_dead",
        "grass_tall", "grass_dead", "fallen_branch", "sticks_pile",
        "leaf_pile", "ivy_ground",
    ],
    "veil_crack_zone": [
        "rock_small", "rock_medium", "boulder", "shrub_dead",
        "bones_small", "debris_stone", "grass_dead",
    ],
    "cemetery": [
        "rock_small", "rock_flat", "shrub_dead", "grass_dead",
        "ivy_ground", "bones_small", "sticks_pile", "leaf_pile",
        "mushroom_cluster", "tree_dead_standing",
    ],
    "battlefield": [
        "rock_small", "debris_stone", "bones_small", "grass_dead",
        "shrub_dead", "sticks_pile", "fallen_branch",
    ],
    "desert": [
        "rock_small", "rock_medium", "boulder", "rock_flat",
        "grass_dead", "shrub_dead", "bones_small", "debris_stone",
    ],
    "coastal": [
        "rock_small", "rock_medium", "rock_flat", "shore_driftwood",
        "grass_short", "grass_tall", "reeds", "lilypad",
        "seaweed", "underwater_rock", "underwater_sticks",
    ],
    "grasslands": [
        "rock_small", "rock_flat", "fern", "bush_small",
        "grass_tall", "grass_short", "shrub_flowering",
        "sticks_pile", "leaf_pile", "pinecones",
    ],
    "mushroom_forest": [
        "rock_small", "rock_medium", "fern", "bush_small",
        "mushroom_cluster", "fallen_log", "tree_stump",
        "grass_tall", "ivy_ground", "leaf_pile",
    ],
    "crystal_cavern": [
        "rock_small", "rock_medium", "boulder", "debris_stone",
        "mushroom_cluster", "underwater_rock",
    ],
    "deep_forest": [
        "rock_small", "rock_medium", "fern", "bush_small", "bush_large",
        "tree_young", "tree_stump", "fallen_log", "fallen_branch",
        "sticks_pile", "leaf_pile", "mushroom_cluster", "grass_tall",
        "ivy_ground", "pinecones",
    ],
}


# ---------------------------------------------------------------------------
# Build a fast lookup: model_name -> (category, item_def)
# ---------------------------------------------------------------------------

def _build_catalog_lookup() -> dict[str, tuple[str, dict]]:
    """Build name -> (category, item_definition) lookup from catalog."""
    lookup: dict[str, tuple[str, dict]] = {}
    for category, items in ENV_MODEL_CATALOG.items():
        for item in items:
            lookup[item["name"]] = (category, item)
    return lookup


_CATALOG_LOOKUP: dict[str, tuple[str, dict]] = _build_catalog_lookup()


# ---------------------------------------------------------------------------
# ModelVariant dataclass
# ---------------------------------------------------------------------------

@dataclass
class ModelVariant:
    """A single variant of an environmental model."""

    variant_id: int                     # 0-3
    model_name: str                     # e.g. "rock_small"
    category: str                       # e.g. "rocks"
    file_path: str                      # Path to GLB file
    target_tris: int                    # Triangle budget
    actual_tris: int                    # Actual count after decimation
    scale_range: tuple[float, float]
    generation_prompt: str
    texture_score: float                # 0-100 from post-processor
    created_at: str                     # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict."""
        d = asdict(self)
        # scale_range is a tuple -- ensure it serializes as list
        d["scale_range"] = list(self.scale_range)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelVariant:
        """Deserialize from dict (e.g. loaded from JSON)."""
        data = dict(data)  # shallow copy to avoid mutating caller
        # Normalize scale_range back to tuple
        sr = data.get("scale_range", (0.0, 1.0))
        if isinstance(sr, list):
            data["scale_range"] = tuple(sr)
        return cls(**data)


# ---------------------------------------------------------------------------
# EnvModelLibrary
# ---------------------------------------------------------------------------

class EnvModelLibrary:
    """Persistent library of Tripo-generated environmental scatter models.

    Directory layout::

        <library_dir>/
            library_index.json
            models/
                rocks/
                    rock_small_v0.glb
                    rock_small_v1.glb
                    ...
                foliage/
                    fern_v0.glb
                    ...
    """

    VARIANTS_PER_MODEL = 4
    DARK_FANTASY_PREFIX = "dark fantasy medieval weathered Gothic, "

    def __init__(self, library_dir: str | Path):
        """Initialize library at the given directory."""
        self.library_dir = Path(library_dir)
        self.models_dir = self.library_dir / "models"
        self.index_path = self.library_dir / "library_index.json"
        self._index: dict[str, list[ModelVariant]] = {}
        self._ensure_dirs()
        self._load_index()

    # -- directory helpers ---------------------------------------------------

    def _ensure_dirs(self) -> None:
        """Create library directory structure."""
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        for category in ENV_MODEL_CATALOG:
            (self.models_dir / category).mkdir(parents=True, exist_ok=True)

    # -- persistence ---------------------------------------------------------

    def _load_index(self) -> None:
        """Load library index from disk."""
        if not self.index_path.exists():
            self._index = {}
            return

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load library index: %s -- starting fresh", exc)
            self._index = {}
            return

        version = raw.get("version", 1)
        if version != 1:
            logger.warning(
                "Unknown library index version %s -- attempting load anyway", version
            )

        self._index = {}
        for model_name, variants_data in raw.get("models", {}).items():
            variants: list[ModelVariant] = []
            for vd in variants_data:
                try:
                    variants.append(ModelVariant.from_dict(vd))
                except (TypeError, KeyError) as exc:
                    logger.warning(
                        "Skipping corrupt variant for %s: %s", model_name, exc
                    )
            if variants:
                self._index[model_name] = variants

    def _save_index(self) -> None:
        """Save library index to disk (atomic write)."""
        data: dict[str, Any] = {
            "version": 1,
            "catalog_size": sum(len(v) for v in ENV_MODEL_CATALOG.values()),
            "generated_models": len(self._index),
            "total_variants": sum(len(v) for v in self._index.values()),
            "models": {},
        }
        for model_name, variants in sorted(self._index.items()):
            data["models"][model_name] = [v.to_dict() for v in variants]

        tmp = str(self.index_path) + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, str(self.index_path))
        except OSError as exc:
            logger.error("Failed to save library index: %s", exc)
            # Clean up temp file if replace failed
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- query methods -------------------------------------------------------

    def get_variants(self, model_name: str) -> list[ModelVariant]:
        """Get all variants for a model. Returns empty list if not generated."""
        return list(self._index.get(model_name, []))

    def get_random_variant(self, model_name: str, seed: int = 0) -> ModelVariant | None:
        """Get a deterministic pseudo-random variant for instancing.

        Uses seed to select consistently -- same seed always returns same variant.
        """
        variants = self._index.get(model_name, [])
        if not variants:
            return None
        idx = seed % len(variants)
        return variants[idx]

    def get_category_models(self, category: str) -> list[str]:
        """List all model names in a category from the catalog."""
        items = ENV_MODEL_CATALOG.get(category, [])
        return [item["name"] for item in items]

    def is_generated(self, model_name: str) -> bool:
        """Check if all expected variants exist for a model."""
        variants = self._index.get(model_name, [])
        return len(variants) >= self.VARIANTS_PER_MODEL

    def get_missing_models(self) -> list[dict]:
        """List all models from ENV_MODEL_CATALOG that haven't been fully generated.

        Returns list of dicts with name, category, prompt, target_tris,
        scale_range, and missing_variants count.
        """
        missing: list[dict] = []
        for category, items in ENV_MODEL_CATALOG.items():
            for item in items:
                name = item["name"]
                existing = len(self._index.get(name, []))
                if existing < self.VARIANTS_PER_MODEL:
                    missing.append({
                        "name": name,
                        "category": category,
                        "prompt": self.DARK_FANTASY_PREFIX + item["prompt"],
                        "target_tris": item["target_tris"],
                        "scale_range": list(item["scale_range"]),
                        "existing_variants": existing,
                        "missing_variants": self.VARIANTS_PER_MODEL - existing,
                    })
        return missing

    def get_generation_prompt(self, model_name: str) -> str | None:
        """Get the full dark-fantasy-prefixed generation prompt for a model."""
        lookup = _CATALOG_LOOKUP.get(model_name)
        if not lookup:
            return None
        _category, item = lookup
        return self.DARK_FANTASY_PREFIX + item["prompt"]

    # -- registration --------------------------------------------------------

    def register_variant(self, variant: ModelVariant) -> None:
        """Register a generated variant in the index.

        Validates that the variant references a known model name and that
        the variant_id is within range. Saves index to disk after registration.
        """
        if variant.model_name not in _CATALOG_LOOKUP:
            raise ValueError(
                f"Unknown model name '{variant.model_name}' -- "
                f"not found in ENV_MODEL_CATALOG"
            )

        if not (0 <= variant.variant_id < self.VARIANTS_PER_MODEL):
            raise ValueError(
                f"variant_id must be 0-{self.VARIANTS_PER_MODEL - 1}, "
                f"got {variant.variant_id}"
            )

        variants = self._index.setdefault(variant.model_name, [])

        # Replace existing variant with same ID, or append
        replaced = False
        for i, existing in enumerate(variants):
            if existing.variant_id == variant.variant_id:
                variants[i] = variant
                replaced = True
                break
        if not replaced:
            variants.append(variant)

        # Keep sorted by variant_id
        variants.sort(key=lambda v: v.variant_id)

        self._save_index()
        logger.info(
            "Registered %s v%d (%d tris, score=%.1f)",
            variant.model_name,
            variant.variant_id,
            variant.actual_tris,
            variant.texture_score,
        )

    # -- scatter pipeline integration ----------------------------------------

    def get_scatter_config(self, model_name: str) -> dict | None:
        """Get scatter-ready config for a model (paths, scale range, budget).

        Returns None if the model has no generated variants.
        """
        variants = self._index.get(model_name, [])
        if not variants:
            return None

        lookup = _CATALOG_LOOKUP.get(model_name)
        if not lookup:
            return None
        category, item = lookup

        return {
            "model_name": model_name,
            "category": category,
            "variant_count": len(variants),
            "variant_paths": [v.file_path for v in variants],
            "target_tris": item["target_tris"],
            "scale_range": list(item["scale_range"]),
            "avg_texture_score": (
                sum(v.texture_score for v in variants) / len(variants)
                if variants
                else 0.0
            ),
            "fully_generated": len(variants) >= self.VARIANTS_PER_MODEL,
        }

    def get_biome_scatter_set(self, biome_name: str) -> list[dict]:
        """Get all scatter models appropriate for a biome.

        Returns a list of scatter configs for every model assigned to this
        biome that has at least one generated variant. Models without
        generated variants are silently skipped -- use get_missing_models()
        to find what still needs generation.

        Falls back to an empty list for unknown biome names.
        """
        model_names = BIOME_SCATTER_MAPPING.get(biome_name, [])
        scatter_set: list[dict] = []
        for name in model_names:
            config = self.get_scatter_config(name)
            if config is not None:
                config["biome"] = biome_name
                scatter_set.append(config)
        return scatter_set

    def get_biome_missing(self, biome_name: str) -> list[str]:
        """List model names needed for a biome that are not yet generated."""
        model_names = BIOME_SCATTER_MAPPING.get(biome_name, [])
        return [
            name for name in model_names
            if not self.is_generated(name)
        ]

    # -- export --------------------------------------------------------------

    def export_for_unity(self, output_dir: str | Path) -> dict:
        """Export all library models organized for Unity import.

        Copies GLB files into a category-organized directory structure
        and returns a manifest of what was exported.

        Directory layout::

            <output_dir>/
                rocks/
                    rock_small_v0.glb
                    ...
                foliage/
                    ...
        """
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)

        exported: dict[str, Any] = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "categories": {},
            "total_files": 0,
            "errors": [],
        }

        for model_name, variants in sorted(self._index.items()):
            lookup = _CATALOG_LOOKUP.get(model_name)
            if not lookup:
                continue
            category, _item = lookup

            cat_dir = output / category
            cat_dir.mkdir(parents=True, exist_ok=True)

            if category not in exported["categories"]:
                exported["categories"][category] = []

            for variant in variants:
                src = Path(variant.file_path)
                if not src.exists():
                    msg = f"Missing file: {variant.file_path}"
                    logger.warning(msg)
                    exported["errors"].append(msg)
                    continue

                dst_name = f"{model_name}_v{variant.variant_id}.glb"
                dst = cat_dir / dst_name
                try:
                    shutil.copy2(str(src), str(dst))
                    exported["categories"][category].append({
                        "model_name": model_name,
                        "variant_id": variant.variant_id,
                        "file": str(dst),
                        "tris": variant.actual_tris,
                    })
                    exported["total_files"] += 1
                except OSError as exc:
                    msg = f"Failed to copy {src} -> {dst}: {exc}"
                    logger.error(msg)
                    exported["errors"].append(msg)

        # Write manifest
        manifest_path = output / "scatter_manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(exported, f, indent=2, default=str)
        except OSError as exc:
            logger.error("Failed to write manifest: %s", exc)

        return exported

    # -- serialization -------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize full library state for inspection / reporting."""
        catalog_stats: dict[str, dict[str, Any]] = {}
        for category, items in ENV_MODEL_CATALOG.items():
            generated = 0
            total_variants = 0
            for item in items:
                variants = self._index.get(item["name"], [])
                total_variants += len(variants)
                if len(variants) >= self.VARIANTS_PER_MODEL:
                    generated += 1
            catalog_stats[category] = {
                "total_models": len(items),
                "generated": generated,
                "total_variants": total_variants,
                "expected_variants": len(items) * self.VARIANTS_PER_MODEL,
            }

        total_catalog = sum(len(v) for v in ENV_MODEL_CATALOG.values())
        total_generated = sum(
            1 for name in _CATALOG_LOOKUP if self.is_generated(name)
        )

        return {
            "library_dir": str(self.library_dir),
            "total_catalog_models": total_catalog,
            "total_generated": total_generated,
            "total_variants": sum(len(v) for v in self._index.values()),
            "completion_pct": round(
                (total_generated / total_catalog * 100) if total_catalog else 0, 1
            ),
            "categories": catalog_stats,
            "biomes_available": list(BIOME_SCATTER_MAPPING.keys()),
            "models": {
                name: [v.to_dict() for v in variants]
                for name, variants in sorted(self._index.items())
            },
        }

    # -- utility -------------------------------------------------------------

    def expected_file_path(self, model_name: str, variant_id: int) -> Path:
        """Return the expected GLB file path for a model variant.

        Useful for callers that need to know where to write the file
        before registering it.
        """
        lookup = _CATALOG_LOOKUP.get(model_name)
        if not lookup:
            raise ValueError(f"Unknown model name: {model_name}")
        category, _item = lookup
        return self.models_dir / category / f"{model_name}_v{variant_id}.glb"

    def get_catalog_entry(self, model_name: str) -> dict | None:
        """Get the raw catalog entry for a model name."""
        lookup = _CATALOG_LOOKUP.get(model_name)
        if not lookup:
            return None
        category, item = lookup
        return {
            "name": item["name"],
            "category": category,
            "prompt": item["prompt"],
            "full_prompt": self.DARK_FANTASY_PREFIX + item["prompt"],
            "target_tris": item["target_tris"],
            "scale_range": list(item["scale_range"]),
        }

    @staticmethod
    def list_biomes() -> list[str]:
        """List all available biome names."""
        return sorted(BIOME_SCATTER_MAPPING.keys())

    @staticmethod
    def list_categories() -> list[str]:
        """List all model categories from the catalog."""
        return list(ENV_MODEL_CATALOG.keys())
