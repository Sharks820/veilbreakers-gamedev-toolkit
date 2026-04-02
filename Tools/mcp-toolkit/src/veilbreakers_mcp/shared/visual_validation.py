"""Visual quality validation for rendered screenshots and contact sheets."""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


def analyze_render_image(filepath: str) -> dict:
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

            brightness_score = max(0.0, 100.0 - abs(gray_mean - 120.0) * 0.9)
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
            if gray_mean < 28.0:
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
            }
            result["issues"] = issues
            result["score"] = round(score, 3)
            result["valid"] = len(issues) == 0 and score >= 55.0
    except (OSError, ValueError) as exc:
        result["issues"].append(str(exc))

    return result


def aaa_verify_map(screenshot_paths: list[str], min_score: int = 60) -> dict:
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
    per_angle: list[dict] = []
    failed_angles: list[int] = []

    for angle_id, path in enumerate(screenshot_paths):
        base_result = analyze_render_image(path)
        angle_issues = list(base_result.get("issues", []))

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
            angle_score >= min_score
            and "default_material_detected" not in angle_issues
            and "floating_geometry_suspected" not in angle_issues
        )
        if not angle_passed:
            failed_angles.append(angle_id)

        per_angle.append({
            "angle_id": angle_id,
            "score": round(angle_score, 3),
            "issues": angle_issues,
            "passed": angle_passed,
        })

    total_score = (
        sum(a["score"] for a in per_angle) / len(per_angle) if per_angle else 0.0
    )

    return {
        "passed": len(failed_angles) == 0,
        "total_score": round(total_score, 3),
        "per_angle": per_angle,
        "failed_angles": failed_angles,
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
