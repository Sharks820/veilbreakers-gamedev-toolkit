"""Pipeline state persistence -- checkpoint read/write for compose_map resume.

Pure Python module with no bpy dependency (except ``emit_scene_hierarchy``
which requires ``bpy.data.objects``).  All other functions work offline
and are testable without a Blender connection.

Checkpoint JSON schema
----------------------
::

    {
        "version": 1,
        "map_name": "Thornveil Region",
        "seed": 42,
        "created_at": "2026-04-01T12:00:00Z",
        "updated_at": "2026-04-01T12:05:00Z",
        "location_count": 3,
        "steps_completed": ["scene_cleared", "terrain_generated", ...],
        "created_objects": ["Map_Terrain", "Map_Water", ...],
        "location_results": [...],
        "interior_results": [...],
        "params_snapshot": {...}
    }
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

_CHECKPOINT_VERSION = 1


# ---------------------------------------------------------------------------
# Public API -- pure Python, no bpy
# ---------------------------------------------------------------------------


def save_pipeline_checkpoint(
    checkpoint_dir: str,
    state: dict,
) -> str:
    """Write pipeline state to a JSON checkpoint file.

    Parameters
    ----------
    checkpoint_dir : str
        Directory to write the checkpoint file into.  Created if missing.
    state : dict
        Mutable pipeline state dict.  Must contain ``map_name`` key.

    Returns
    -------
    str
        Absolute path of the written checkpoint file.
    """
    os.makedirs(checkpoint_dir, exist_ok=True)
    map_name = state.get("map_name", "unnamed")
    safe_name = map_name.replace(" ", "_").replace("/", "_")
    path = os.path.join(checkpoint_dir, f"{safe_name}_checkpoint.json")

    payload = {
        "version": _CHECKPOINT_VERSION,
        "map_name": map_name,
        "seed": state.get("seed"),
        "created_at": state.get("created_at", _now_iso()),
        "updated_at": _now_iso(),
        "location_count": state.get("location_count", 0),
        "steps_completed": list(state.get("steps_completed", [])),
        "steps_failed": list(state.get("steps_failed", [])),
        "created_objects": list(state.get("created_objects", [])),
        "location_results": list(state.get("location_results", [])),
        "interior_results": list(state.get("interior_results", [])),
        "params_snapshot": state.get("params_snapshot", {}),
    }

    # Atomic write: write to temp file then rename to prevent corruption on crash
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path), suffix=".tmp", prefix="ckpt_"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
        os.replace(tmp_path, path)  # atomic on all platforms
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return os.path.abspath(path)


def load_pipeline_checkpoint(
    checkpoint_dir: str,
    map_name: str,
) -> dict | None:
    """Load a previously saved checkpoint.

    Parameters
    ----------
    checkpoint_dir : str
        Directory containing checkpoint files.
    map_name : str
        The map name used when saving.

    Returns
    -------
    dict or None
        Parsed checkpoint dict, or ``None`` if no checkpoint exists.
    """
    safe_name = map_name.replace(" ", "_").replace("/", "_")
    path = os.path.join(checkpoint_dir, f"{safe_name}_checkpoint.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def delete_pipeline_checkpoint(
    checkpoint_dir: str,
    map_name: str,
) -> bool:
    """Remove a checkpoint file.

    Returns ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    safe_name = map_name.replace(" ", "_").replace("/", "_")
    path = os.path.join(checkpoint_dir, f"{safe_name}_checkpoint.json")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def validate_checkpoint_compatibility(
    checkpoint: dict,
    current_spec: dict,
) -> tuple[bool, str]:
    """Check whether a saved checkpoint is compatible with a new generation request.

    Parameters
    ----------
    checkpoint : dict
        Loaded checkpoint data.
    current_spec : dict
        The new ``map_spec`` being requested.  Must contain ``seed`` and
        ``locations`` list.

    Returns
    -------
    (bool, str)
        ``(True, "")`` if compatible, ``(False, reason)`` otherwise.
    """
    cp_seed = checkpoint.get("seed")
    req_seed = current_spec.get("seed")
    if cp_seed is not None and req_seed is not None and cp_seed != req_seed:
        return False, f"Seed mismatch: checkpoint has {cp_seed}, request has {req_seed}"

    cp_count = checkpoint.get("location_count", 0)
    req_locations = current_spec.get("locations", [])
    if cp_count != len(req_locations):
        return False, (
            f"Location count mismatch: checkpoint has {cp_count}, "
            f"request has {len(req_locations)}"
        )

    return True, ""


def get_remaining_steps(
    checkpoint: dict,
    all_steps: list[str],
) -> list[str]:
    """Return the subset of *all_steps* not yet completed in *checkpoint*.

    Parameters
    ----------
    checkpoint : dict
        Loaded checkpoint with ``steps_completed`` key.
    all_steps : list of str
        Ordered list of all expected step names.

    Returns
    -------
    list of str
        Steps from *all_steps* not in ``checkpoint["steps_completed"]``.
    """
    completed = set(checkpoint.get("steps_completed", []))
    # Also exclude failed steps to prevent infinite retry loops
    failed_steps = {
        entry["step"] if isinstance(entry, dict) else str(entry)
        for entry in checkpoint.get("steps_failed", [])
    }
    skip = completed | failed_steps
    return [s for s in all_steps if s not in skip]


def derive_addressable_groups(
    map_name: str,
    location_results: list[dict],
) -> list[dict]:
    """Derive Unity Addressable groups from compose_map output.

    Creates one group per location type plus a base terrain group.

    Parameters
    ----------
    map_name : str
        Name of the map for group naming.
    location_results : list of dict
        Location result dicts from compose_map.

    Returns
    -------
    list of dict
        Each entry has ``group_name``, ``group_type``, and ``objects`` list.
    """
    groups: list[dict] = [
        {
            "group_name": f"{map_name}_terrain_base",
            "group_type": "terrain",
            "distance_tier": "near",
            "objects": [],
        }
    ]

    seen_types: set[str] = set()
    for loc in location_results:
        loc_type = loc.get("type", "unknown")
        loc_name = loc.get("name", "unnamed")
        if loc_type not in seen_types:
            seen_types.add(loc_type)
            groups.append({
                "group_name": f"{map_name}_{loc_type}s",
                "group_type": loc_type,
                "distance_tier": "mid",
                "objects": [loc_name],
            })
        else:
            # Append to existing group
            for g in groups:
                if g["group_type"] == loc_type:
                    g["objects"].append(loc_name)
                    break

    # Add interiors group if any interior results exist
    groups.append({
        "group_name": f"{map_name}_interiors",
        "group_type": "interior",
        "distance_tier": "far",
        "objects": [],
    })

    return groups


# ---------------------------------------------------------------------------
# bpy-dependent function (guarded import)
# ---------------------------------------------------------------------------


def emit_scene_hierarchy(
    map_name: str,
    location_results: list[dict],
) -> dict:
    """Emit the current Blender scene hierarchy as a JSON-serialisable dict.

    Requires ``bpy`` to be available (i.e. running inside Blender).
    Raises ``RuntimeError`` if called outside Blender.

    Parameters
    ----------
    map_name : str
        Map name for the hierarchy root entry.
    location_results : list of dict
        Location dicts with ``name`` and ``type`` keys.

    Returns
    -------
    dict
        ``{map_name, generated_at, objects: [{name, type, district, world_position, ...}]}``
    """
    try:
        import bpy
    except ImportError:
        raise RuntimeError(
            "emit_scene_hierarchy requires bpy (Blender Python).  "
            "Call this function only from within a Blender session."
        )

    objects: list[dict] = []
    for obj in bpy.data.objects:
        if obj.type not in {"MESH", "EMPTY", "LIGHT", "CAMERA"}:
            continue

        # Determine district from location results
        district = ""
        for loc in location_results:
            loc_name = loc.get("name", "")
            if obj.name.startswith(loc_name) or loc_name in obj.name:
                district = loc.get("type", "")
                break

        objects.append({
            "name": obj.name,
            "type": obj.type,
            "district": district,
            "world_position": [
                round(obj.matrix_world.translation.x, 4),
                round(obj.matrix_world.translation.y, 4),
                round(obj.matrix_world.translation.z, 4),
            ],
            "world_rotation_euler": [
                round(obj.rotation_euler.x, 4),
                round(obj.rotation_euler.y, 4),
                round(obj.rotation_euler.z, 4),
            ],
            "world_scale": [
                round(obj.scale.x, 4),
                round(obj.scale.y, 4),
                round(obj.scale.z, 4),
            ],
        })

    return {
        "map_name": map_name,
        "generated_at": _now_iso(),
        "objects": objects,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
