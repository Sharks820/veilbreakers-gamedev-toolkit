"""Model Vault -- persistent catalog of every Tripo-generated model.

No model is ever deleted without explicit user approval.
Every generation (all 4 variants) is logged with metadata,
file paths, and status. The vault is a JSON file that persists
across sessions.

Usage::

    from veilbreakers_mcp.shared.model_vault import ModelVault

    vault = ModelVault("/path/to/project")
    vault.register_generation(prompt, task_ids, models, metadata)
    vault.list_all()
    vault.mark_selected(generation_id, variant="v2")
    vault.mark_rejected(generation_id, variant="v3", reason="bad topology")
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VAULT_FILENAME = "tripo_model_vault.json"


class ModelVault:
    """Persistent catalog of all Tripo-generated models."""

    def __init__(self, project_root: str | None = None):
        if project_root:
            self._vault_dir = Path(project_root) / "Assets" / "Art" / "3D_Models"
        else:
            self._vault_dir = Path(".")
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        self._vault_path = self._vault_dir / VAULT_FILENAME
        self._data = self._load()

    def _load(self) -> dict:
        if self._vault_path.exists():
            try:
                with open(self._vault_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load vault: %s — starting fresh", exc)
        return {"version": 1, "generations": []}

    def _save(self) -> None:
        """Atomic write to prevent corruption."""
        tmp = str(self._vault_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)
        os.replace(tmp, str(self._vault_path))

    def register_generation(
        self,
        prompt: str,
        task_ids: list[str],
        models: list[dict],
        *,
        action: str = "generate_3d",
        asset_type: str = "prop",
        building_type: str | None = None,
        building_style: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Register a new generation with all its variants.

        Returns a generation_id for future reference.
        """
        gen_id = f"gen_{int(time.time())}_{task_ids[0][:8] if task_ids else 'unknown'}"

        variants = []
        for m in models:
            variant = {
                "task_id": m.get("task_id", ""),
                "variant_tag": m.get("variant", ""),
                "path": m.get("path", ""),
                "size_bytes": m.get("size_bytes", 0),
                "verified": m.get("verified", False),
                "error": m.get("error"),
                "status": "available" if m.get("verified") else "failed",
                "selected": False,
                "rejected": False,
                "reject_reason": None,
                "texture_channels": m.get("texture_channels", {}),
                "post_process": m.get("post_process"),
            }
            # Verify file still exists
            if variant["path"] and os.path.exists(variant["path"]):
                variant["file_exists"] = True
            else:
                variant["file_exists"] = False
                if variant["status"] == "available":
                    variant["status"] = "file_missing"
            variants.append(variant)

        entry = {
            "generation_id": gen_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": prompt,
            "action": action,
            "asset_type": asset_type,
            "building_type": building_type,
            "building_style": building_style,
            "all_task_ids": task_ids,
            "variant_count": len(models),
            "verified_count": sum(1 for m in models if m.get("verified")),
            "variants": variants,
            "extra": extra_metadata or {},
        }

        self._data["generations"].append(entry)
        self._save()
        logger.info(
            "Vault: registered %s with %d variants (%d verified)",
            gen_id, len(models), entry["verified_count"],
        )
        return gen_id

    def mark_selected(self, generation_id: str, variant_tag: str) -> bool:
        """Mark a variant as the user's chosen model."""
        for gen in self._data["generations"]:
            if gen["generation_id"] == generation_id:
                for v in gen["variants"]:
                    if v["variant_tag"] == variant_tag:
                        v["selected"] = True
                        v["status"] = "selected"
                        self._save()
                        return True
        return False

    def mark_rejected(
        self, generation_id: str, variant_tag: str, reason: str = ""
    ) -> bool:
        """Mark a variant as rejected (but DO NOT delete the file)."""
        for gen in self._data["generations"]:
            if gen["generation_id"] == generation_id:
                for v in gen["variants"]:
                    if v["variant_tag"] == variant_tag:
                        v["rejected"] = True
                        v["reject_reason"] = reason
                        v["status"] = "rejected"
                        self._save()
                        return True
        return False

    def list_all(self) -> list[dict]:
        """Return all generations with summary info."""
        results = []
        for gen in self._data["generations"]:
            results.append({
                "generation_id": gen["generation_id"],
                "timestamp": gen["timestamp"],
                "prompt": gen["prompt"][:80],
                "action": gen["action"],
                "asset_type": gen.get("asset_type"),
                "building_type": gen.get("building_type"),
                "variants": len(gen["variants"]),
                "verified": gen["verified_count"],
                "selected": sum(1 for v in gen["variants"] if v.get("selected")),
                "rejected": sum(1 for v in gen["variants"] if v.get("rejected")),
            })
        return results

    def list_unreviewed(self) -> list[dict]:
        """Return variants that haven't been selected or rejected yet."""
        unreviewed = []
        for gen in self._data["generations"]:
            for v in gen["variants"]:
                if (
                    v.get("verified")
                    and not v.get("selected")
                    and not v.get("rejected")
                ):
                    unreviewed.append({
                        "generation_id": gen["generation_id"],
                        "prompt": gen["prompt"][:80],
                        "variant_tag": v["variant_tag"],
                        "path": v["path"],
                        "file_exists": os.path.exists(v["path"]) if v["path"] else False,
                        "size_mb": round(v.get("size_bytes", 0) / 1024 / 1024, 1),
                    })
        return unreviewed

    def get_generation(self, generation_id: str) -> dict | None:
        """Get full details of a specific generation."""
        for gen in self._data["generations"]:
            if gen["generation_id"] == generation_id:
                return gen
        return None

    def get_all_file_paths(self) -> list[str]:
        """Return every model file path in the vault — for protection against cleanup."""
        paths = []
        for gen in self._data["generations"]:
            for v in gen["variants"]:
                if v.get("path"):
                    paths.append(v["path"])
        return paths

    def prune_old_generations(
        self,
        *,
        keep_last: int = 200,
        remove_missing_files: bool = True,
    ) -> dict:
        """MISC-008: Prune vault to prevent unbounded growth.

        Removes entries whose model files are missing from disk (optional) and
        keeps only the most recent ``keep_last`` generations.  Entries that
        have a selected variant are never pruned regardless of age.

        Args:
            keep_last: Maximum number of generations to retain.
            remove_missing_files: If True, also prune entries where ALL
                variants have missing files (and none are selected).

        Returns:
            Dict with ``removed_missing`` and ``removed_old`` counts.
        """
        gens = self._data["generations"]
        removed_missing = 0
        removed_old = 0

        if remove_missing_files:
            surviving = []
            for gen in gens:
                any_selected = any(v.get("selected") for v in gen["variants"])
                if any_selected:
                    surviving.append(gen)
                    continue
                any_file_present = any(
                    v.get("path") and os.path.exists(v["path"])
                    for v in gen["variants"]
                )
                if any_file_present:
                    surviving.append(gen)
                else:
                    removed_missing += 1
                    logger.info(
                        "Vault prune: removing %s (all files missing)",
                        gen["generation_id"],
                    )
            gens = surviving

        if len(gens) > keep_last:
            # Keep selected entries plus the tail of the list (most recent)
            selected = [g for g in gens if any(v.get("selected") for v in g["variants"])]
            unselected = [g for g in gens if not any(v.get("selected") for v in g["variants"])]
            keep_unselected = max(keep_last - len(selected), 0)
            dropped = unselected[:-keep_unselected] if keep_unselected else unselected
            removed_old = len(dropped)
            gens = selected + unselected[-keep_unselected:] if keep_unselected else selected

        self._data["generations"] = gens
        if removed_missing or removed_old:
            self._save()
            logger.info(
                "Vault pruned: %d missing-file entries, %d old entries removed",
                removed_missing,
                removed_old,
            )
        return {"removed_missing": removed_missing, "removed_old": removed_old}

    def verify_files(self) -> dict:
        """Check all vault entries and report missing files."""
        missing = []
        present = []
        for gen in self._data["generations"]:
            for v in gen["variants"]:
                if v.get("path"):
                    if os.path.exists(v["path"]):
                        present.append(v["path"])
                        v["file_exists"] = True
                    else:
                        missing.append({
                            "generation_id": gen["generation_id"],
                            "variant": v["variant_tag"],
                            "path": v["path"],
                        })
                        v["file_exists"] = False
        self._save()
        return {
            "total_files": len(present) + len(missing),
            "present": len(present),
            "missing": len(missing),
            "missing_details": missing,
        }
