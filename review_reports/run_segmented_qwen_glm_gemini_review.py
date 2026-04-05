from __future__ import annotations

import json
import subprocess
from pathlib import Path

from veilbreakers_mcp.review_server import review_consensus


ROOT = Path(r"C:\Users\Conner\OneDrive\Documents\veilbreakers-gamedev-toolkit")
REPORT_DIR = ROOT / "review_reports"

SEGMENTS = [
    {
        "name": "terrain_core",
        "files": [
            "Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py",
            "Tools/mcp-toolkit/blender_addon/handlers/_terrain_depth.py",
            "Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py",
            "Tools/mcp-toolkit/blender_addon/handlers/environment_scatter.py",
            "Tools/mcp-toolkit/blender_addon/handlers/terrain_materials.py",
        ],
        "context": (
            "Current branch: feature/terrain-world-foundation. "
            "Review this terrain-core patch segment for correctness, world-space math, "
            "rectangular-terrain handling, sampling, slope, scatter, and splat/material regressions."
        ),
    },
    {
        "name": "terrain_orchestration",
        "files": [
            "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
            "Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py",
        ],
        "context": (
            "Current branch: feature/terrain-world-foundation. "
            "Review this terrain orchestration segment for export normalization bugs, "
            "planner/world-anchor issues, tiled-world wiring, and runtime contract regressions."
        ),
    },
    {
        "name": "terrain_tests",
        "files": [
            "Tools/mcp-toolkit/tests/test_compose_planners.py",
            "Tools/mcp-toolkit/tests/test_environment_handlers.py",
            "Tools/mcp-toolkit/tests/test_environment_scatter_handlers.py",
            "Tools/mcp-toolkit/tests/test_functional_unity_tools.py",
            "Tools/mcp-toolkit/tests/test_mesh_bridge.py",
            "Tools/mcp-toolkit/tests/test_terrain_depth.py",
            "Tools/mcp-toolkit/tests/test_terrain_noise.py",
        ],
        "context": (
            "Current branch: feature/terrain-world-foundation. "
            "Review this test segment for missing coverage, stale assertions, "
            "and tests that no longer match the intended production behavior."
        ),
    },
]

MODELS = [
    "qwen/qwen3.6-plus:free",
    "glm-5.0-turbo",
    "gemini-3.1-flash-lite-preview",
]

INSTRUCTIONS = (
    "Review as a senior engineer. Focus on real bugs, regressions, missing wiring, "
    "or real coverage gaps in this patch segment. Ignore stylistic nits."
)


def build_diff(files: list[str]) -> str:
    completed = subprocess.run(
        ["git", "diff", "--", *files],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"segments": []}

    for segment in SEGMENTS:
        name = str(segment["name"])
        diff = build_diff(list(segment["files"]))
        diff_path = REPORT_DIR / f"{name}.patch"
        diff_path.write_text(diff, encoding="utf-8")

        report_json = review_consensus(
            diff=diff,
            context=str(segment["context"]),
            instructions=INSTRUCTIONS,
            models=MODELS,
            min_agreement=2,
            max_tokens=1600,
            save_path=str(REPORT_DIR / f"{name}_review.json"),
        )
        report = json.loads(report_json)
        summary["segments"].append(
            {
                "name": name,
                "report_path": report.get("saved_to"),
                "consensus_count": len(report.get("consensus_findings", [])),
                "model_specific_count": len(report.get("model_specific_findings", [])),
                "models": [
                    {
                        "model": model.get("model"),
                        "status": model.get("status"),
                        "finding_count": model.get("finding_count"),
                        "error": model.get("error"),
                    }
                    for model in report.get("models", [])
                ],
            }
        )

    summary_path = REPORT_DIR / "segmented_review_summary_20260405.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
