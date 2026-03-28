"""Tests for the Unity code tool boundary writes."""

from __future__ import annotations

import asyncio
import json


class TestUnityCodeModifyScript:
    """Verify modify_script writes both backup and updated content safely."""

    def test_modify_script_uses_shared_write_helper(self, tmp_path, monkeypatch):
        """Modify-script should write backup and edited code through the shared writer."""
        from veilbreakers_mcp.shared.config import Settings
        from veilbreakers_mcp.unity_tools import _common, code

        project_root = tmp_path
        source_path = project_root / "Assets" / "Scripts" / "Player.cs"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("original source", encoding="utf-8")

        settings = Settings(unity_project_path=str(project_root))
        monkeypatch.setattr(_common, "settings", settings, raising=False)
        monkeypatch.setattr(code, "settings", settings, raising=False)
        monkeypatch.setattr(
            code,
            "modify_script",
            lambda **kwargs: ("modified source", ["changed"]),
            raising=False,
        )

        result = asyncio.run(
            code.unity_code(
                action="modify_script",
                script_path="Assets/Scripts/Player.cs",
            )
        )

        payload = json.loads(result)
        assert payload["status"] == "success"
        assert source_path.read_text(encoding="utf-8") == "modified source"
        assert (project_root / "Assets" / "Scripts" / "Player.cs.bak").exists()
        assert (project_root / "Assets" / "Scripts" / "Player.cs.bak").read_text(encoding="utf-8") == "original source"
