"""LRU mask cache for terrain iteration velocity (Bundle M).

Caches expensive intermediate mask computations keyed by
(pass_name, intent_hash, region, tile_coords) so re-running a pass over
unchanged inputs returns instantly.

Pure Python + numpy. No bpy.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

import numpy as np

from .terrain_semantics import (
    BBox,
    PassDefinition,
    PassResult,
    TerrainPipelineState,
)


# ---------------------------------------------------------------------------
# Cache key construction
# ---------------------------------------------------------------------------


def cache_key_for_pass(
    pass_name: str,
    intent: Any,
    region: Optional[BBox],
    tile_coords: Optional[tuple] = None,
) -> str:
    """Build a stable cache key for a pass invocation.

    ``intent`` may be a TerrainIntentState (we call ``.intent_hash()``),
    a raw string, or any json-serializable object.
    """
    if hasattr(intent, "intent_hash") and callable(intent.intent_hash):
        intent_digest = intent.intent_hash()
    else:
        intent_digest = hashlib.sha256(
            json.dumps(intent, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    region_tuple = region.to_tuple() if region is not None else None
    payload = json.dumps(
        {
            "pass": pass_name,
            "intent": intent_digest,
            "region": region_tuple,
            "tile": list(tile_coords) if tile_coords is not None else None,
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# MaskCache (LRU)
# ---------------------------------------------------------------------------


class MaskCache:
    """LRU cache for pass results / mask computations.

    Stores arbitrary values keyed by string. Supports a max-entry cap
    with oldest-first eviction. Tracks hit/miss counters for speedup
    measurement.
    """

    def __init__(self, max_entries: int = 128) -> None:
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        self._max = max(1, int(max_entries))
        self.hits: int = 0
        self.misses: int = 0

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str) -> Optional[Any]:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
            return
        self._data[key] = value
        if len(self._data) > self._max:
            self._data.popitem(last=False)

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any]) -> Any:
        """Return cached entry for key, or compute + cache it."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute_fn()
        self.put(key, value)
        return value

    def invalidate(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys with a given string prefix. Returns count."""
        matched = [k for k in self._data.keys() if k.startswith(prefix)]
        for k in matched:
            del self._data[k]
        return len(matched)

    def invalidate_all(self) -> None:
        self._data.clear()

    def stats(self) -> Dict[str, int]:
        total = self.hits + self.misses
        hit_rate_pct = int((self.hits * 100) / total) if total > 0 else 0
        return {
            "entries": len(self._data),
            "max_entries": self._max,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_pct": hit_rate_pct,
        }


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _snapshot_produced_channels(
    state: TerrainPipelineState,
    channels: tuple,
) -> Dict[str, Optional[np.ndarray]]:
    snap: Dict[str, Optional[np.ndarray]] = {}
    for ch in channels:
        val = state.mask_stack.get(ch)
        snap[ch] = None if val is None else np.array(val, copy=True)
    return snap


def _restore_produced_channels(
    state: TerrainPipelineState,
    snap: Dict[str, Optional[np.ndarray]],
    pass_name: str,
) -> None:
    for ch, val in snap.items():
        if val is None:
            continue
        state.mask_stack.set(ch, np.array(val, copy=True), pass_name)


def pass_with_cache(
    pass_def: PassDefinition,
    state: TerrainPipelineState,
    region: Optional[BBox],
    cache: MaskCache,
) -> PassResult:
    """Run a pass function, using the cache to skip computation on hit.

    Cached entry stores a dict with:
        - 'result': the PassResult
        - 'produced': snapshot of produced channels (ndarrays)

    On cache hit the stored channel snapshots are re-applied to the
    current mask stack so downstream passes see a consistent state.
    """
    key = cache_key_for_pass(
        pass_def.name,
        state.intent,
        region,
        (state.tile_x, state.tile_y),
    )
    cached = cache.get(key)
    if cached is not None:
        _restore_produced_channels(state, cached["produced"], pass_def.name)
        return cached["result"]

    result = pass_def.func(state, region)
    produced_snap = _snapshot_produced_channels(state, pass_def.produces_channels)
    cache.put(key, {"result": result, "produced": produced_snap})
    return result


__all__ = [
    "MaskCache",
    "cache_key_for_pass",
    "pass_with_cache",
]
