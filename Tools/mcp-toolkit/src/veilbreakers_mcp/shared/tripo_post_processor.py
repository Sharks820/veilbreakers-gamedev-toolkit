"""Tripo post-processor: extract textures, de-light, validate, and score.

Orchestrates the complete post-download chain for a Tripo GLB model:
  1. Extract PBR channel maps (albedo, orm, normal) from the GLB binary.
  2. De-light the albedo to remove baked-in Tripo lighting artifacts.
  3. Validate the (de-lit) albedo against VeilBreakers dark fantasy palette rules.
  4. Validate ORM roughness map for sufficient variation.
  5. Compute a 0-100 channel completeness + quality score.

Also provides ``score_variants()`` to rank a list of post-processing results
so the best Tripo variant can be selected automatically.

Exports:
    post_process_tripo_model  -- Full post-processing pipeline for one GLB.
    score_variants            -- Sort variant results by channel_score (best first).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from veilbreakers_mcp.shared.delight import delight_albedo
from veilbreakers_mcp.shared.glb_texture_extractor import extract_glb_textures
from veilbreakers_mcp.shared.palette_validator import (
    validate_palette,
    validate_roughness_map,
)


# ---------------------------------------------------------------------------
# Scoring weights (sum = 100)
# ---------------------------------------------------------------------------

_SCORE_HAS_ALBEDO = 25
_SCORE_HAS_ORM = 25
_SCORE_HAS_NORMAL = 25
_SCORE_PALETTE_PASSED = 15
_SCORE_ROUGHNESS_PASSED = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_channels(
    channels: dict[str, str],
    palette_passed: bool,
    roughness_passed: bool,
) -> int:
    """Compute a 0-100 quality score from channel completeness and validation.

    Scoring breakdown:
        25 pts -- albedo present
        25 pts -- orm present
        25 pts -- normal present
        15 pts -- palette validation passed
        10 pts -- roughness validation passed
    """
    score = 0
    if "albedo" in channels or "albedo_delit" in channels:
        score += _SCORE_HAS_ALBEDO
    if "orm" in channels:
        score += _SCORE_HAS_ORM
    if "normal" in channels:
        score += _SCORE_HAS_NORMAL
    if palette_passed:
        score += _SCORE_PALETTE_PASSED
    if roughness_passed:
        score += _SCORE_ROUGHNESS_PASSED
    return score


# ---------------------------------------------------------------------------
# Public API: post_process_tripo_model
# ---------------------------------------------------------------------------

async def post_process_tripo_model(
    glb_path: str,
    out_dir: str,
    asset_type: str = "prop",
) -> dict[str, Any]:
    """Extract textures, de-light albedo, validate palette, and score one GLB.

    Args:
        glb_path:   Absolute path to the downloaded Tripo GLB file.
        out_dir:    Output directory for extracted textures.  A ``textures/``
                    subdirectory will be created inside it.
        asset_type: Asset type hint (currently unused, reserved for future
                    per-type rule overrides).

    Returns:
        Dict with keys:
            channels:             {albedo, orm, normal, ...} paths that exist.
            albedo_delit:         Path to de-lit albedo, or None.
            palette_validation:   {passed, issues, stats} from validate_palette.
            roughness_validation: {passed, variance, ...} from validate_roughness_map.
            channel_score:        Integer 0-100.
            texture_dir:          Path to the textures subdirectory.
    """
    texture_dir = Path(out_dir) / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    texture_dir_str = str(texture_dir)

    result: dict[str, Any] = {
        "channels": {},
        "albedo_delit": None,
        "palette_validation": {"passed": False, "issues": [], "stats": {}},
        "roughness_validation": {"passed": False, "variance": 0.0},
        "channel_score": 0,
        "texture_dir": texture_dir_str,
    }

    # ------------------------------------------------------------------
    # Step 1: Extract GLB textures
    # ------------------------------------------------------------------
    try:
        channels = extract_glb_textures(glb_path, texture_dir_str)
    except Exception as exc:  # noqa: BLE001
        result["extraction_error"] = str(exc)
        return result

    result["channels"] = channels

    # ------------------------------------------------------------------
    # Step 2: De-light albedo (only if albedo was extracted)
    # ------------------------------------------------------------------
    albedo_delit_path: str | None = None
    if "albedo" in channels:
        delit_out = str(texture_dir / "albedo_delit.png")
        try:
            delight_result = delight_albedo(channels["albedo"], delit_out)
            if delight_result.get("correction_applied"):
                albedo_delit_path = delit_out
                result["albedo_delit"] = albedo_delit_path
        except Exception:  # noqa: BLE001
            pass  # Non-fatal; proceed with raw albedo for validation

    # ------------------------------------------------------------------
    # Step 3: Validate palette
    # ------------------------------------------------------------------
    albedo_for_validation = albedo_delit_path or channels.get("albedo")
    palette_result: dict[str, Any] = {"passed": False, "issues": [], "stats": {}}
    if albedo_for_validation and os.path.isfile(albedo_for_validation):
        try:
            palette_result = validate_palette(albedo_for_validation)
        except Exception:  # noqa: BLE001
            pass  # Non-fatal; keep default failed result
    result["palette_validation"] = palette_result

    # ------------------------------------------------------------------
    # Step 4: Validate roughness (ORM green channel proxy)
    # ------------------------------------------------------------------
    roughness_result: dict[str, Any] = {"passed": False, "variance": 0.0}
    orm_path = channels.get("orm")
    if orm_path and os.path.isfile(orm_path):
        try:
            roughness_result = validate_roughness_map(orm_path)
        except Exception:  # noqa: BLE001
            pass  # Non-fatal; keep default failed result
    result["roughness_validation"] = roughness_result

    # ------------------------------------------------------------------
    # Step 5: Score
    # ------------------------------------------------------------------
    result["channel_score"] = _score_channels(
        channels,
        palette_passed=palette_result.get("passed", False),
        roughness_passed=roughness_result.get("passed", False),
    )

    return result


# ---------------------------------------------------------------------------
# Public API: score_variants
# ---------------------------------------------------------------------------

def score_variants(post_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort a list of post-processing results by ``channel_score`` (best first).

    Ties are broken by the number of channels present (more = better).

    Args:
        post_results: List of dicts as returned by ``post_process_tripo_model``.

    Returns:
        New list sorted by descending channel_score.  The best variant is
        at index 0.
    """

    def _sort_key(r: dict[str, Any]) -> tuple[int, int]:
        score = r.get("channel_score", 0)
        channel_count = len(r.get("channels", {}))
        return (score, channel_count)

    return sorted(post_results, key=_sort_key, reverse=True)
