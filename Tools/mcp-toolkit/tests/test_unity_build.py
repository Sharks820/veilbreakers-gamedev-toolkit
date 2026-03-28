"""Tests for the Unity build tool boundary writes."""

from __future__ import annotations

import asyncio
import json


class TestUnityBuildWrites:
    """Verify repo-root Unity build outputs use the shared write helper."""

    def test_generate_ci_pipeline_writes_root_workflow(self, tmp_path, monkeypatch):
        """CI pipeline generation should write a root-level workflow file."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common, build

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )
        monkeypatch.setattr(
            build,
            "generate_github_actions_workflow",
            lambda **kwargs: "name: test-workflow\n",
            raising=False,
        )

        result = asyncio.run(
            build.unity_build(
                action="generate_ci_pipeline",
                ci_provider="github",
                ci_platforms=["StandaloneWindows64"],
                run_tests=False,
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        out_path = tmp_path / ".github" / "workflows" / "unity-build.yml"
        assert out_path.exists()
        assert out_path.read_text(encoding="utf-8") == "name: test-workflow\n"
        assert payload["file_path"] == str(out_path)

    def test_generate_store_metadata_writes_root_file(self, tmp_path, monkeypatch):
        """Store metadata generation should write to the shared root boundary."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common, build

        monkeypatch.setattr(
            _common,
            "settings",
            Settings(unity_project_path=str(tmp_path)),
            raising=False,
        )
        monkeypatch.setattr(
            build,
            "generate_store_metadata",
            lambda **kwargs: "# Store Metadata\n",
            raising=False,
        )

        result = asyncio.run(
            build.unity_build(
                action="generate_store_metadata",
                game_title="VeilBreakers",
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        out_path = tmp_path / "StoreMetadata" / "STORE_LISTING.md"
        assert out_path.exists()
        assert out_path.read_text(encoding="utf-8") == "# Store Metadata\n"
        assert payload["file_path"] == str(out_path)
