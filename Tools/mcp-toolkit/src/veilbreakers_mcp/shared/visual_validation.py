"""Visual quality validation for rendered screenshots and contact sheets."""

from __future__ import annotations

import math
import os
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
