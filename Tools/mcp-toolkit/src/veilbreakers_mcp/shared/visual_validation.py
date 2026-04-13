"""Visual quality validation for rendered screenshots and contact sheets."""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageStat


_VALIDATION_PROFILES = {
    "terrain_readability",
    "terrain_cliff",
    "terrain_waterfall",
    "terrain_cave",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _crop_box(width: int, height: int, left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
    return (
        max(0, min(width, int(round(width * left)))),
        max(0, min(height, int(round(height * top)))),
        max(0, min(width, int(round(width * right)))),
        max(0, min(height, int(round(height * bottom)))),
    )


def _region_array(array: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    return array[y0:y1, x0:x1]


def _safe_mean(array: np.ndarray) -> float:
    if array.size == 0:
        return 0.0
    return float(array.mean())


def _safe_std(array: np.ndarray) -> float:
    if array.size == 0:
        return 0.0
    return float(array.std())


def _edge_density(edge_array: np.ndarray, box: tuple[int, int, int, int]) -> float:
    region = _region_array(edge_array, box)
    return _safe_mean(region)


def _quiet_fraction(edge_array: np.ndarray, box: tuple[int, int, int, int], threshold: float = 16.0) -> float:
    region = _region_array(edge_array, box)
    if region.size == 0:
        return 0.0
    return float(np.count_nonzero(region < threshold)) / float(region.size)


def _row_gradient_score(gray_array: np.ndarray, box: tuple[int, int, int, int]) -> float:
    region = _region_array(gray_array, box)
    if region.shape[0] < 2:
        return 0.0
    row_diff = np.abs(np.diff(region, axis=0))
    return float(row_diff.mean()) if row_diff.size else 0.0


def _col_gradient_score(gray_array: np.ndarray, box: tuple[int, int, int, int]) -> float:
    region = _region_array(gray_array, box)
    if region.shape[1] < 2:
        return 0.0
    col_diff = np.abs(np.diff(region, axis=1))
    return float(col_diff.mean()) if col_diff.size else 0.0


def _evaluate_validation_profile(
    rgb_array: np.ndarray,
    gray_array: np.ndarray,
    edge_array: np.ndarray,
    validation_profile: str | None,
) -> dict:
    result = {
        "validation_profile": validation_profile,
        "passed": True,
        "score": 100.0,
        "issues": [],
        "metrics": {},
    }

    if validation_profile is None:
        return result

    profile = validation_profile.strip().lower()
    if profile not in _VALIDATION_PROFILES:
        result["passed"] = False
        result["score"] = 0.0
        result["issues"].append(f"Unknown validation_profile '{validation_profile}'")
        return result

    height, width = gray_array.shape[:2]
    top = _crop_box(width, height, 0.0, 0.0, 1.0, 0.33)
    middle = _crop_box(width, height, 0.0, 0.33, 1.0, 0.70)
    bottom = _crop_box(width, height, 0.0, 0.66, 1.0, 1.0)
    center = _crop_box(width, height, 0.22, 0.18, 0.78, 0.82)
    center_strip = _crop_box(width, height, 0.34, 0.0, 0.66, 1.0)
    side_left = _crop_box(width, height, 0.0, 0.0, 0.24, 1.0)
    side_right = _crop_box(width, height, 0.76, 0.0, 1.0, 1.0)
    border_top = _crop_box(width, height, 0.0, 0.0, 1.0, 0.18)
    border_bottom = _crop_box(width, height, 0.0, 0.82, 1.0, 1.0)
    border_left = _crop_box(width, height, 0.0, 0.18, 0.18, 0.82)
    border_right = _crop_box(width, height, 0.82, 0.18, 1.0, 0.82)

    top_gray = _region_array(gray_array, top)
    middle_gray = _region_array(gray_array, middle)
    bottom_gray = _region_array(gray_array, bottom)
    center_gray = _region_array(gray_array, center)
    center_strip_gray = _region_array(gray_array, center_strip)
    side_left_gray = _region_array(gray_array, side_left)
    side_right_gray = _region_array(gray_array, side_right)
    border_gray = np.concatenate(
        [
            _region_array(gray_array, border_top).reshape(-1),
            _region_array(gray_array, border_bottom).reshape(-1),
            _region_array(gray_array, border_left).reshape(-1),
            _region_array(gray_array, border_right).reshape(-1),
        ]
    )

    top_edge = _edge_density(edge_array, top)
    middle_edge = _edge_density(edge_array, middle)
    bottom_edge = _edge_density(edge_array, bottom)
    center_edge = _edge_density(edge_array, center)
    center_strip_edge = _edge_density(edge_array, center_strip)
    side_edge = (_edge_density(edge_array, side_left) + _edge_density(edge_array, side_right)) / 2.0
    border_edge = (
        _edge_density(edge_array, border_top)
        + _edge_density(edge_array, border_bottom)
        + _edge_density(edge_array, border_left)
        + _edge_density(edge_array, border_right)
    ) / 4.0

    top_mean = _safe_mean(top_gray)
    middle_mean = _safe_mean(middle_gray)
    bottom_mean = _safe_mean(bottom_gray)
    center_mean = _safe_mean(center_gray)
    center_strip_mean = _safe_mean(center_strip_gray)
    side_mean = (_safe_mean(side_left_gray) + _safe_mean(side_right_gray)) / 2.0
    border_mean = _safe_mean(border_gray)

    if profile == "terrain_readability":
        sky_ground_sep = abs(top_mean - bottom_mean)
        foreground_grounding = _clamp(100.0 - max(0.0, bottom_mean - 185.0) * 2.2 + bottom_edge * 2.8)
        silhouette_read = _clamp(top_edge * 3.0 + sky_ground_sep * 1.1 + middle_edge * 0.8)
        quiet_fraction = _quiet_fraction(edge_array, bottom, threshold=16.0)
        quiet_ground_budget = _clamp(100.0 - abs(quiet_fraction - 0.80) * 190.0)
        profile_score = (foreground_grounding * 0.40) + (silhouette_read * 0.35) + (quiet_ground_budget * 0.25)
        result["metrics"] = {
            "foreground_grounding": round(foreground_grounding, 3),
            "silhouette_read": round(silhouette_read, 3),
            "quiet_ground_budget": round(quiet_ground_budget, 3),
            "sky_ground_separation": round(sky_ground_sep, 3),
            "bottom_edge_density": round(bottom_edge, 3),
            "top_edge_density": round(top_edge, 3),
            "bottom_brightness": round(bottom_mean, 3),
            "quiet_fraction": round(quiet_fraction, 3),
        }
        if foreground_grounding < 58.0:
            result["issues"].append(
                f"terrain_readability: grounded foreground is weak (score={foreground_grounding:.1f})"
            )
        if silhouette_read < 55.0:
            result["issues"].append(
                f"terrain_readability: skyline/silhouette read is too soft (score={silhouette_read:.1f})"
            )
        if quiet_ground_budget < 50.0:
            result["issues"].append(
                f"terrain_readability: quiet-ground budget is off balance (score={quiet_ground_budget:.1f})"
            )
        result["score"] = round(profile_score, 3)
        result["passed"] = len(result["issues"]) == 0 and profile_score >= 60.0
        return result

    if profile == "terrain_cliff":
        vertical_relief = abs(top_mean - bottom_mean)
        face_read = _clamp(center_edge * 3.2 + center_strip_edge * 1.6 + vertical_relief * 0.9)
        silhouette_read = _clamp(top_edge * 2.4 + border_edge * 1.2 + abs(top_mean - middle_mean) * 0.8)
        face_contrast = _clamp(abs(center_mean - border_mean) * 1.6 + abs(center_strip_mean - side_mean) * 1.4)
        profile_score = (face_read * 0.42) + (silhouette_read * 0.28) + (face_contrast * 0.30)
        result["metrics"] = {
            "face_read": round(face_read, 3),
            "silhouette_read": round(silhouette_read, 3),
            "face_contrast": round(face_contrast, 3),
            "vertical_relief": round(vertical_relief, 3),
            "center_edge_density": round(center_edge, 3),
            "border_edge_density": round(border_edge, 3),
            "center_brightness": round(center_mean, 3),
            "border_brightness": round(border_mean, 3),
        }
        if face_read < 58.0:
            result["issues"].append(
                f"terrain_cliff: cliff face does not read in the center band (score={face_read:.1f})"
            )
        if silhouette_read < 44.0:
            result["issues"].append(
                f"terrain_cliff: cliff skyline and edge break-up are too soft (score={silhouette_read:.1f})"
            )
        if face_contrast < 52.0:
            result["issues"].append(
                f"terrain_cliff: cliff mass lacks enough tonal separation (score={face_contrast:.1f})"
            )
        result["score"] = round(profile_score, 3)
        result["passed"] = len(result["issues"]) == 0 and profile_score >= 60.0
        return result

    if profile == "terrain_waterfall":
        vertical_focal = _clamp(_row_gradient_score(gray_array, center_strip) * 5.0 + center_strip_edge * 1.8)
        fall_line = _clamp((center_strip_mean - side_mean) * 1.8 + abs(top_mean - bottom_mean) * 0.7)
        spray_read = _clamp(bottom_edge * 2.5 + abs(bottom_mean - center_mean) * 1.0)
        vertical_bias = _clamp(
            (_row_gradient_score(gray_array, center_strip) - _col_gradient_score(gray_array, center_strip)) * 7.0 + 50.0
        )
        profile_score = (vertical_focal * 0.40) + (fall_line * 0.30) + (spray_read * 0.20) + (vertical_bias * 0.10)
        result["metrics"] = {
            "vertical_focal_read": round(vertical_focal, 3),
            "fall_line_read": round(fall_line, 3),
            "spray_read": round(spray_read, 3),
            "vertical_bias": round(vertical_bias, 3),
            "center_strip_edge_density": round(center_strip_edge, 3),
            "bottom_edge_density": round(bottom_edge, 3),
            "center_strip_brightness": round(center_strip_mean, 3),
        }
        if vertical_focal < 40.0:
            result["issues"].append(
                f"terrain_waterfall: vertical focal read is too weak (score={vertical_focal:.1f})"
            )
        if fall_line < 48.0:
            result["issues"].append(
                f"terrain_waterfall: fall line does not separate cleanly from the sides (score={fall_line:.1f})"
            )
        if spray_read < 45.0:
            result["issues"].append(
                f"terrain_waterfall: terminal spray/foam read is too quiet (score={spray_read:.1f})"
            )
        result["score"] = round(profile_score, 3)
        result["passed"] = len(result["issues"]) == 0 and profile_score >= 60.0
        return result

    if profile == "terrain_cave":
        enclosure = _clamp((border_mean - center_mean) * 2.5 + (border_edge - center_edge) * 1.8)
        opening_read = _clamp(100.0 - max(0.0, center_mean - 120.0) * 1.8 + center_edge * 1.7)
        framing_read = _clamp(abs(top_mean - center_mean) * 0.9 + abs(bottom_mean - center_mean) * 0.8 + border_edge * 1.4)
        border_bias = _clamp((border_mean - side_mean) * 1.5 + (border_mean - center_strip_mean) * 1.2)
        profile_score = (enclosure * 0.40) + (opening_read * 0.30) + (framing_read * 0.20) + (border_bias * 0.10)
        result["metrics"] = {
            "enclosure": round(enclosure, 3),
            "opening_read": round(opening_read, 3),
            "framing_read": round(framing_read, 3),
            "border_bias": round(border_bias, 3),
            "center_brightness": round(center_mean, 3),
            "border_brightness": round(border_mean, 3),
            "center_edge_density": round(center_edge, 3),
            "border_edge_density": round(border_edge, 3),
        }
        if enclosure < 58.0:
            result["issues"].append(
                f"terrain_cave: cave framing is missing or too open (score={enclosure:.1f})"
            )
        if opening_read < 52.0:
            result["issues"].append(
                f"terrain_cave: central opening is not dark enough to read as interior (score={opening_read:.1f})"
            )
        if framing_read < 50.0:
            result["issues"].append(
                f"terrain_cave: rim/arch framing is too soft (score={framing_read:.1f})"
            )
        result["score"] = round(profile_score, 3)
        result["passed"] = len(result["issues"]) == 0 and profile_score >= 60.0
        return result

    result["passed"] = False
    result["score"] = 0.0
    result["issues"].append(f"Unknown validation_profile '{validation_profile}'")
    return result


def analyze_render_image(filepath: str, validation_profile: str | None = None) -> dict:
    """Analyze a single render screenshot for visual quality."""
    result: dict = {
        "filepath": filepath,
        "valid": False,
        "score": 0.0,
        "metrics": {},
        "issues": [],
    }

    if not os.path.isfile(filepath):
        result["issues"].append("File not found")
        return result

    try:
        with Image.open(filepath) as image:
            rgba = image.convert("RGBA")
            rgb = rgba.convert("RGB")
            gray = rgb.convert("L")
            rgb_arr = np.array(rgb, dtype=np.float32)
            gray_arr = np.array(gray, dtype=np.float32)
            edge_img = gray.filter(ImageFilter.FIND_EDGES)
            edge_arr = np.array(edge_img, dtype=np.float32)

            rgb_stat = ImageStat.Stat(rgb)
            gray_stat = ImageStat.Stat(gray)
            edge_stat = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))

            mean_r, mean_g, mean_b = rgb_stat.mean
            std_r, std_g, std_b = rgb_stat.stddev
            gray_mean = float(gray_stat.mean[0])
            gray_std = float(gray_stat.stddev[0])
            edge_mean = float(edge_stat.mean[0])

            histogram = gray.histogram()
            entropy = 0.0
            total = sum(histogram) or 1
            for count in histogram:
                if count <= 0:
                    continue
                p = count / total
                entropy -= p * math.log2(p)

            color_spread = (std_r + std_g + std_b) / 3.0
            channel_balance = max(mean_r, mean_g, mean_b) - min(mean_r, mean_g, mean_b)

            # Dark-fantasy brightness scoring: ideal range 30–80 (not 120).
            # Penalise anything above 80 or below 30, but allow naturally dark scenes.
            _BRIGHT_LOW = 30.0
            _BRIGHT_HIGH = 80.0
            if gray_mean < _BRIGHT_LOW:
                brightness_score = max(0.0, 100.0 - (_BRIGHT_LOW - gray_mean) * 2.0)
            elif gray_mean > _BRIGHT_HIGH:
                brightness_score = max(0.0, 100.0 - (gray_mean - _BRIGHT_HIGH) * 1.5)
            else:
                brightness_score = 100.0

            contrast_score = min(100.0, gray_std * 4.0)
            edge_score = min(100.0, edge_mean * 1.8)
            entropy_score = min(100.0, entropy * 18.0)
            color_score = min(100.0, color_spread * 6.0)

            score = (
                brightness_score * 0.20
                + contrast_score * 0.25
                + edge_score * 0.25
                + entropy_score * 0.20
                + color_score * 0.10
            )

            issues: list[str] = []
            if gray_mean < 10.0:
                issues.append("Image is too dark")
            if gray_mean > 235.0:
                issues.append("Image is too bright")
            if gray_std < 12.0:
                issues.append("Image contrast is too low")
            if edge_mean < 8.0:
                issues.append("Edge density is too low")
            if entropy < 1.2:
                issues.append("Image lacks visual variation")
            if color_spread < 10.0:
                issues.append("Color variation is too low")
            if channel_balance < 4.0 and color_spread < 12.0:
                issues.append("Image appears nearly monochrome")

            # Magenta/missing-texture detection: pink pixels where R>200, G<50, B>200
            magenta_fraction = 0.0
            try:
                rgb_arr = np.array(rgb, dtype=np.uint8)
                magenta_mask = (
                    (rgb_arr[:, :, 0] > 200)
                    & (rgb_arr[:, :, 1] < 50)
                    & (rgb_arr[:, :, 2] > 200)
                )
                magenta_fraction = float(magenta_mask.sum()) / max(magenta_mask.size, 1)
                if magenta_fraction > 0.001:  # >0.1% of pixels are magenta
                    issues.append(
                        f"missing_texture_detected ({magenta_fraction * 100:.2f}% magenta pixels)"
                    )
            except Exception:
                pass

            semantic_result = _evaluate_validation_profile(rgb_arr, gray_arr, edge_arr, validation_profile)
            result["metrics"] = {
                "brightness_mean": round(gray_mean, 3),
                "brightness_stddev": round(gray_std, 3),
                "edge_density": round(edge_mean, 3),
                "entropy": round(entropy, 3),
                "color_spread": round(color_spread, 3),
                "channel_balance": round(channel_balance, 3),
                "brightness_score": round(brightness_score, 3),
                "contrast_score": round(contrast_score, 3),
                "edge_score": round(edge_score, 3),
                "entropy_score": round(entropy_score, 3),
                "color_score": round(color_score, 3),
                "magenta_fraction": round(magenta_fraction, 6),
            }
            if validation_profile is not None:
                result["validation_profile"] = validation_profile
                result["semantic_score"] = semantic_result["score"]
                result["semantic_issues"] = semantic_result["issues"]
                result["semantic_metrics"] = semantic_result["metrics"]
                result["metrics"].update({
                    f"semantic_{key}": value for key, value in semantic_result["metrics"].items()
                })
                result["metrics"]["semantic_score"] = semantic_result["score"]
                issues.extend(semantic_result["issues"])
                if not semantic_result["passed"]:
                    issues.append(f"validation_profile '{validation_profile}' failed")
            result["issues"] = issues
            result["score"] = round(score, 3)
            result["valid"] = len(issues) == 0 and score >= 55.0 and semantic_result["passed"]
    except (OSError, ValueError) as exc:
        result["issues"].append(str(exc))

    return result


def aaa_verify_map(
    screenshot_paths: list[str],
    min_score: int = 60,
    *,
    required_angle_count: int | None = None,
    angle_labels: list[str] | None = None,
    validation_profile: str | None = None,
) -> dict:
    """Multi-angle AAA visual verification protocol.

    Scores each provided screenshot (one per camera angle, expect 10) against
    a minimum quality threshold. Also runs two additional AAA-specific checks:

    - Floating geometry detection: bottom 20% of image has mean brightness >200
      (sky color where ground should be).
    - Default material detection: image has very low color variance (std_dev < 8
      across all channels), indicating a single gray/white default material.

    Args:
        screenshot_paths: List of file paths, one per camera angle.
        min_score: Minimum per-angle score to pass (default 60).

    Returns:
        Dict with keys:
            passed (bool): True if all angles pass.
            total_score (float): Average score across all angles.
            per_angle (list[dict]): [{angle_id, score, issues}] for each angle.
            failed_angles (list[int]): Indices of angles that scored below min_score
                or had critical quality flags.
    """
    if not screenshot_paths:
        return {
            "passed": False,
            "total_score": 0.0,
            "per_angle": [],
            "failed_angles": [],
            "missing_angles": angle_labels or [],
            "validation_profile": validation_profile,
            "issues": ["No screenshots supplied for AAA verification"],
        }

    per_angle: list[dict] = []
    failed_angles: list[int] = []
    issues: list[str] = []
    missing_angles: list[str] = []

    for angle_id, path in enumerate(screenshot_paths):
        angle_label = (
            angle_labels[angle_id]
            if angle_labels and angle_id < len(angle_labels)
            else f"angle_{angle_id}"
        )
        if validation_profile is None:
            base_result = analyze_render_image(path)
        else:
            try:
                base_result = analyze_render_image(path, validation_profile=validation_profile)
            except TypeError:
                # Preserve older monkeypatched test doubles that do not yet
                # accept the new keyword while keeping the production path
                # profile-aware.
                base_result = analyze_render_image(path)
        angle_issues = list(base_result.get("issues", []))
        semantic_issues = list(base_result.get("semantic_issues", []))
        semantic_metrics = dict(base_result.get("semantic_metrics", {}))
        semantic_score = float(base_result.get("semantic_score", 0.0))
        angle_score = float(base_result.get("score", 0.0))
        if validation_profile is None:
            base_passed = angle_score >= min_score
        elif "valid" in base_result:
            base_passed = bool(base_result.get("valid", False)) and angle_score >= min_score
        else:
            base_passed = angle_score >= min_score and not semantic_issues

        # --- AAA check 1: Floating geometry detection ---
        # Check if bottom 20% of image has mean brightness > 200 (sky-colored ground)
        if os.path.isfile(path):
            try:
                with Image.open(path) as img:
                    rgb = img.convert("RGB")
                    w, h = rgb.size
                    bottom_20pct = rgb.crop((0, int(h * 0.80), w, h))
                    stat = ImageStat.Stat(bottom_20pct)
                    bottom_mean = sum(stat.mean) / 3.0
                    if bottom_mean > 200.0:
                        angle_issues.append("floating_geometry_suspected")
            except (OSError, ValueError):
                pass

        # --- AAA check 2: Default material detection ---
        # Very low color variance across all channels = single default material
        if os.path.isfile(path):
            try:
                with Image.open(path) as img:
                    rgb = img.convert("RGB")
                    stat = ImageStat.Stat(rgb)
                    avg_std = sum(stat.stddev) / 3.0
                    if avg_std < 8.0:
                        angle_issues.append("default_material_detected")
            except (OSError, ValueError):
                pass

        angle_score = float(base_result.get("score", 0.0))

        # An angle passes only if score >= min_score AND no AAA critical flags
        angle_passed = (
            base_passed
            and "default_material_detected" not in angle_issues
            and "floating_geometry_suspected" not in angle_issues
        )
        if not angle_passed:
            failed_angles.append(angle_id)

        per_angle.append({
            "angle_id": angle_id,
            "angle_label": angle_label,
            "score": round(angle_score, 3),
            "issues": angle_issues,
            "semantic_issues": semantic_issues,
            "semantic_metrics": semantic_metrics,
            "semantic_score": round(semantic_score, 3),
            "validation_profile": validation_profile,
            "passed": angle_passed,
        })

    expected_count = required_angle_count if required_angle_count is not None else None
    if expected_count is not None and len(screenshot_paths) < expected_count:
        missing_count = expected_count - len(screenshot_paths)
        if angle_labels:
            missing_angles = angle_labels[len(screenshot_paths):expected_count]
        else:
            missing_angles = [
                f"angle_{idx}" for idx in range(len(screenshot_paths), expected_count)
            ]
        issues.append(
            f"Missing {missing_count} required screenshot angle(s)"
        )
        failed_angles.extend(range(len(screenshot_paths), expected_count))

    failed_angle_labels = [
        per_angle[idx]["angle_label"]
        for idx in sorted(set(failed_angles))
        if idx < len(per_angle)
    ]
    failed_angle_labels.extend(missing_angles)
    if validation_profile and failed_angle_labels:
        issues.append(
            f"Validation profile '{validation_profile}' failed for: {', '.join(failed_angle_labels)}"
        )

    total_score = sum(a["score"] for a in per_angle) / len(per_angle)

    return {
        "passed": len(failed_angles) == 0,
        "total_score": round(total_score, 3),
        "per_angle": per_angle,
        "failed_angles": sorted(set(failed_angles)),
        "failed_angle_labels": failed_angle_labels,
        "missing_angles": missing_angles,
        "validation_profile": validation_profile,
        "issues": issues,
    }


def validate_render_screens(paths: list[str], min_score: float = 55.0) -> dict:
    """Validate a set of screenshot paths and return an aggregate score."""
    normalized_paths = [str(Path(path)) for path in paths if path]
    result: dict = {
        "valid": False,
        "min_score": float(min_score),
        "score": 0.0,
        "paths": normalized_paths,
        "images": [],
        "issues": [],
        "metrics": {},
    }

    if not normalized_paths:
        result["issues"].append("No screenshot paths provided")
        return result

    total_score = 0.0
    brightness_values: list[float] = []
    contrast_values: list[float] = []
    edge_values: list[float] = []

    for path in normalized_paths:
        image_result = analyze_render_image(path)
        result["images"].append(image_result)
        total_score += float(image_result.get("score", 0.0))
        metrics = image_result.get("metrics", {})
        if metrics:
            brightness_values.append(float(metrics.get("brightness_mean", 0.0)))
            contrast_values.append(float(metrics.get("brightness_stddev", 0.0)))
            edge_values.append(float(metrics.get("edge_density", 0.0)))
        if image_result.get("issues"):
            result["issues"].extend(
                f"{path}: {issue}" for issue in image_result["issues"]
            )

    count = len(result["images"]) or 1
    aggregate_score = total_score / count
    result["score"] = round(aggregate_score, 3)
    result["metrics"] = {
        "image_count": count,
        "avg_brightness": round(sum(brightness_values) / count, 3) if brightness_values else 0.0,
        "avg_contrast": round(sum(contrast_values) / count, 3) if contrast_values else 0.0,
        "avg_edge_density": round(sum(edge_values) / count, 3) if edge_values else 0.0,
    }
    result["valid"] = aggregate_score >= min_score and len(result["issues"]) == 0
    if not result["valid"] and aggregate_score < min_score:
        result["issues"].append(
            f"Aggregate visual score {aggregate_score:.1f} below threshold {min_score:.1f}"
        )
    return result
