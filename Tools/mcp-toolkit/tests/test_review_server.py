import json
import sys
from pathlib import Path
import urllib.error

import pytest


class TestReviewServer:
    def test_build_review_messages_includes_diff_and_context(self):
        from veilbreakers_mcp.review_server import _build_review_messages

        messages = _build_review_messages(
            diff="diff --git a/foo b/foo",
            context="terrain continuity export",
            instructions="focus on seams",
        )

        assert messages[0]["role"] == "system"
        assert "code reviewer" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "terrain continuity export" in messages[1]["content"]
        assert "focus on seams" in messages[1]["content"]
        assert "diff --git a/foo b/foo" in messages[1]["content"]

    def test_extract_completion_text_handles_string_content(self):
        from veilbreakers_mcp.review_server import _extract_completion_text

        response = {
            "choices": [
                {"message": {"content": "No findings."}},
            ]
        }
        assert _extract_completion_text(response) == "No findings."

    def test_extract_completion_text_handles_content_array(self):
        from veilbreakers_mcp.review_server import _extract_completion_text

        response = {
            "choices": [
                {"message": {"content": [{"text": "First "}, {"text": "second"}]}},
            ]
        }
        assert _extract_completion_text(response) == "First second"

    def test_cli_fallback_uses_openrouter_command(self, monkeypatch, tmp_path):
        from veilbreakers_mcp.review_server import _run_review

        echo_script = tmp_path / "echo_stdin.py"
        echo_script.write_text(
            "import sys\n"
            "data = sys.stdin.read()\n"
            "sys.stdout.write(data)\n"
        )

        monkeypatch.setenv(
            "OPENROUTER_COMMAND",
            f'"{sys.executable}" "{echo_script}"',
        )
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        result = _run_review(
            diff="hello world",
            context="context",
            instructions="instructions",
            model="qwen/qwen3.6-plus:free",
        )

        assert "hello world" in result
        assert "context" in result
        assert "instructions" in result

    def test_cli_fallback_uses_gemini_command_for_gemini_models(self, monkeypatch, tmp_path):
        from veilbreakers_mcp.review_server import _run_review

        echo_script = tmp_path / "echo_stdin.py"
        echo_script.write_text(
            "import sys\n"
            "data = sys.stdin.read()\n"
            "sys.stdout.write(data)\n"
        )

        monkeypatch.setenv(
            "GEMINI_COMMAND",
            f'"{sys.executable}" "{echo_script}"',
        )
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        result = _run_review(
            diff="hello gemini",
            context="context",
            instructions="instructions",
            model="gemini-3.1-flash-lite-preview",
        )

        assert "hello gemini" in result
        assert "context" in result
        assert "instructions" in result

    def test_missing_config_raises_helpful_error(self, monkeypatch):
        from veilbreakers_mcp.review_server import _run_review

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_COMMAND", raising=False)

        with pytest.raises(RuntimeError, match="No OpenRouter API key configured"):
            _run_review(diff="x", model="qwen/qwen3.6-plus:free")

    def test_resolve_provider_routes_openrouter_glm_and_gemini(self):
        from veilbreakers_mcp.review_server import _resolve_provider

        assert _resolve_provider("qwen/qwen3.6-plus:free") == "openrouter"
        assert _resolve_provider("glm-5.0-turbo") == "glm"
        assert _resolve_provider("gemini-3.1-flash-lite-preview") == "gemini"

    def test_resolve_cli_model_maps_requested_gemini_alias(self):
        from veilbreakers_mcp.review_server import _resolve_cli_model

        assert _resolve_cli_model("gemini", "gemini-3.1-flash-lite-preview") == "gemini-3-flash-preview"

    def test_resolve_api_model_maps_glm_alias(self):
        from veilbreakers_mcp.review_server import _resolve_api_model

        assert _resolve_api_model("glm", "glm-5.0-turbo") == "glm-5-turbo"

    def test_missing_glm_config_raises_helpful_error(self, monkeypatch):
        from veilbreakers_mcp.review_server import _run_review

        monkeypatch.delenv("GLM_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        monkeypatch.delenv("GLM_COMMAND", raising=False)
        monkeypatch.delenv("ZAI_COMMAND", raising=False)

        with pytest.raises(RuntimeError, match="No GLM API key configured"):
            _run_review(diff="x", model="glm-5.0-turbo")

    def test_glm_retries_transient_429(self, monkeypatch):
        from veilbreakers_mcp import review_server as srv

        calls = {"count": 0}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "No findings."}}]}).encode("utf-8")

        def fake_urlopen(request, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {"Retry-After": "0"},
                    None,
                )
            return _FakeResponse()

        monkeypatch.setenv("GLM_API_KEY", "test-key")
        monkeypatch.setattr(srv.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(srv.time, "sleep", lambda _: None)

        result = srv._invoke_glm_api(
            [{"role": "user", "content": "hi"}],
            "glm-5.0-turbo",
            temperature=0.0,
            max_tokens=32,
        )

        assert result == "No findings."
        assert calls["count"] == 2

    def test_openrouter_retries_transient_429(self, monkeypatch):
        from veilbreakers_mcp import review_server as srv

        calls = {"count": 0}

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "No findings."}}]}).encode("utf-8")

        def fake_urlopen(request, timeout):
            calls["count"] += 1
            if calls["count"] == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    429,
                    "rate limited",
                    {"Retry-After": "0"},
                    None,
                )
            return _FakeResponse()

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr(srv.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(srv.time, "sleep", lambda _: None)

        result = srv._invoke_openrouter_api(
            [{"role": "user", "content": "hi"}],
            "qwen/qwen3.6-plus:free",
            temperature=0.0,
            max_tokens=32,
        )

        assert result == "No findings."
        assert calls["count"] == 2

    def test_consensus_merges_shared_findings(self, monkeypatch):
        from veilbreakers_mcp import review_server as srv

        outputs = {
            "qwen/qwen3.6-plus:free": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "extract_tile is used without an import",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.92,
                },
                {
                    "title": "Redundant height range resolution",
                    "severity": "Low",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_terrain_tile",
                    "evidence": "dead assignment before overwrite",
                    "recommendation": "Remove the first assignment.",
                    "confidence": 0.55,
                },
            ],
            "glm-5.0-turbo": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "extract_tile is referenced",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.95,
                }
            ],
            "gemini-3.1-flash-lite-preview": [],
        }

        def fake_review(*, model, **kwargs):
            return outputs[model]

        monkeypatch.setattr(srv, "_run_structured_review", fake_review)

        report = json.loads(
            srv.review_consensus(
                diff="diff --git a/foo b/foo",
                models=[
                    "qwen/qwen3.6-plus:free",
                    "glm-5.0-turbo",
                    "gemini-3.1-flash-lite-preview",
                ],
                min_agreement=2,
            )
        )

        assert report["min_agreement"] == 2
        assert len(report["models"]) == 3
        assert report["models"][0]["model"] == "qwen/qwen3.6-plus:free"
        assert len(report["consensus_findings"]) == 1
        assert report["consensus_findings"][0]["agreement"] == 2
        assert report["consensus_findings"][0]["title"] == "Missing import in environment.py"
        assert len(report["model_specific_findings"]) == 1
        assert report["model_specific_findings"][0]["title"] == "Redundant height range resolution"

    def test_consensus_scores_against_ground_truth(self, monkeypatch, tmp_path):
        from veilbreakers_mcp import review_server as srv

        outputs = {
            "qwen/qwen3.6-plus:free": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "extract_tile is used without an import",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.92,
                },
                {
                    "title": "Noise normalization drift",
                    "severity": "Medium",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/_terrain_noise.py",
                    "function": "generate_heightmap",
                    "evidence": "model over-reports normalization",
                    "recommendation": "Use a shared normalization contract.",
                    "confidence": 0.61,
                },
            ],
            "glm-5.0-turbo": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "same issue",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.95,
                }
            ],
            "gemini-3.1-flash-lite-preview": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "same issue",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.94,
                },
                {
                    "title": "Overly broad heightmap check",
                    "severity": "Low",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_terrain_tile",
                    "evidence": "not actually a bug",
                    "recommendation": "Ignore this.",
                    "confidence": 0.12,
                },
            ],
        }

        truth_file = tmp_path / "truth.json"
        truth_file.write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "title": "Missing import in environment.py",
                            "severity": "High",
                            "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                            "function": "handle_generate_world_terrain",
                        }
                    ]
                }
            )
        )

        def fake_review(*, model, **kwargs):
            return outputs[model]

        monkeypatch.setattr(srv, "_run_structured_review", fake_review)

        report = json.loads(
            srv.review_consensus(
                diff="diff --git a/foo b/foo",
                models=[
                    "qwen/qwen3.6-plus:free",
                    "glm-5.0-turbo",
                    "gemini-3.1-flash-lite-preview",
                ],
                min_agreement=2,
                truth_path=str(truth_file),
                save_dir=str(tmp_path / "history"),
            )
        )

        assert report["evaluation"]["truth_count"] == 1
        assert report["evaluation"]["models"]["qwen/qwen3.6-plus:free"]["true_positive_count"] == 1
        assert report["evaluation"]["models"]["qwen/qwen3.6-plus:free"]["false_positive_count"] == 1
        assert report["evaluation"]["models"]["qwen/qwen3.6-plus:free"]["recall"] == 1.0
        assert report["evaluation"]["models"]["qwen/qwen3.6-plus:free"]["precision"] == 0.5
        assert report["evaluation"]["models"]["gemini-3.1-flash-lite-preview"]["true_positive_count"] == 1
        assert report["evaluation"]["models"]["gemini-3.1-flash-lite-preview"]["false_positive_count"] == 1

        summary = json.loads(
            srv.review_history_summary(
                history_dir=str(tmp_path / "history"),
                top_n=5,
            )
        )

        assert summary["model_stats"]["qwen/qwen3.6-plus:free"]["precision"] == 0.5
        assert summary["model_stats"]["gemini-3.1-flash-lite-preview"]["recall"] == 1.0

    def test_consensus_rejects_bad_agreement(self):
        from veilbreakers_mcp.review_server import review_consensus

        with pytest.raises(ValueError, match="min_agreement cannot exceed"):
            review_consensus(
                diff="x",
                models=["qwen/qwen3.6-plus:free"],
                min_agreement=2,
            )

    def test_consensus_can_save_and_summarize_history(self, monkeypatch, tmp_path):
        from veilbreakers_mcp import review_server as srv

        outputs = {
            "qwen/qwen3.6-plus:free": [
                {
                    "title": "Shared seam bug",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "seam validation references the wrong range",
                    "recommendation": "Use a shared range contract.",
                    "confidence": 0.9,
                }
            ],
            "glm-5.0-turbo": [
                {
                    "title": "Shared seam bug",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "same bug",
                    "recommendation": "Use a shared range contract.",
                    "confidence": 0.95,
                }
            ],
            "gemini-3.1-flash-lite-preview": [],
        }

        def fake_review(*, model, **kwargs):
            return outputs[model]

        monkeypatch.setattr(srv, "_run_structured_review", fake_review)

        save_dir = tmp_path / "review-history"
        report = json.loads(
            srv.review_consensus(
                diff="diff --git a/foo b/foo",
                models=[
                    "qwen/qwen3.6-plus:free",
                    "glm-5.0-turbo",
                    "gemini-3.1-flash-lite-preview",
                ],
                min_agreement=2,
                save_dir=str(save_dir),
            )
        )

        assert "saved_to" in report
        saved_path = Path(report["saved_to"])
        assert saved_path.exists()

        summary = json.loads(
            srv.review_history_summary(
                history_dir=str(save_dir),
                top_n=5,
            )
        )

        assert summary["history_runs"] == 1
        assert summary["model_stats"]["qwen/qwen3.6-plus:free"]["runs"] == 1
        assert summary["model_stats"]["glm-5.0-turbo"]["runs"] == 1
        assert summary["top_recurring_findings"][0]["count"] == 1

    def test_scoring_reports_other_matches(self, monkeypatch, tmp_path):
        from veilbreakers_mcp import review_server as srv

        outputs = {
            "qwen/qwen3.6-plus:free": [
                {
                    "title": "Missing import in environment.py",
                    "severity": "High",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_world_terrain",
                    "evidence": "extract_tile is used without an import",
                    "recommendation": "Import extract_tile from _terrain_world.",
                    "confidence": 0.92,
                },
                {
                    "title": "Tile range assumption should be documented",
                    "severity": "Low",
                    "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                    "function": "handle_generate_terrain_tile",
                    "evidence": "reviewer correctly noticed a design concern",
                    "recommendation": "Document the expected range contract.",
                    "confidence": 0.41,
                },
            ],
            "glm-5.0-turbo": [],
            "gemini-3.1-flash-lite-preview": [],
        }

        truth_file = tmp_path / "truth.json"
        truth_file.write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "title": "Missing import in environment.py",
                            "severity": "High",
                            "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                            "function": "handle_generate_world_terrain",
                            "category": "real",
                        },
                        {
                            "title": "Tile range assumption should be documented",
                            "severity": "Low",
                            "file": "Tools/mcp-toolkit/blender_addon/handlers/environment.py",
                            "function": "handle_generate_terrain_tile",
                            "category": "other",
                            "classification": "design_concern",
                        },
                    ]
                }
            )
        )

        def fake_review(*, model, **kwargs):
            return outputs[model]

        monkeypatch.setattr(srv, "_run_structured_review", fake_review)

        report = json.loads(
            srv.review_consensus(
                diff="diff --git a/foo b/foo",
                models=[
                    "qwen/qwen3.6-plus:free",
                    "glm-5.0-turbo",
                    "gemini-3.1-flash-lite-preview",
                ],
                min_agreement=1,
                truth_path=str(truth_file),
            )
        )

        model_metrics = report["evaluation"]["models"]["qwen/qwen3.6-plus:free"]
        assert model_metrics["true_positive_count"] == 1
        assert model_metrics["other_match_count"] == 1
        assert model_metrics["false_positive_count"] == 0
        assert model_metrics["strict_accuracy"] == 0.5
        assert model_metrics["useful_signal_rate"] == 1.0
        assert model_metrics["other_breakdown"] == {"design_concern": 1}
        assert model_metrics["other_matches"][0]["title"] == "Tile range assumption should be documented"
        assert model_metrics["other_matches"][0]["classification"] == "design_concern"
