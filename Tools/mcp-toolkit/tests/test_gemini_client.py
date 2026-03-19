"""Unit tests for Gemini visual review client.

Tests GeminiReviewClient in stub mode (no API key) and verifies
the expected return structure.
"""

import pytest

from veilbreakers_mcp.shared.gemini_client import GeminiReviewClient


# ---------------------------------------------------------------------------
# Stub mode (no API key)
# ---------------------------------------------------------------------------


class TestGeminiReviewClientStubMode:
    """Tests for GeminiReviewClient when no API key is provided."""

    def test_stub_returns_dict(self):
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert isinstance(result, dict)

    def test_stub_has_quality_score(self):
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert "quality_score" in result
        assert result["quality_score"] == 0.0

    def test_stub_has_issues_list(self):
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert "issues" in result
        assert isinstance(result["issues"], list)

    def test_stub_has_suggestions_list(self):
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)

    def test_stub_has_summary(self):
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert "summary" in result
        assert "no API key" in result["summary"].lower() or "unavailable" in result["summary"].lower()

    def test_none_api_key_is_stub_mode(self):
        client = GeminiReviewClient(api_key=None)
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="Review this screenshot",
        )
        assert result["quality_score"] == 0.0

    def test_default_api_key_is_stub_mode(self):
        """When no api_key arg given and no env var, should be stub mode."""
        import os
        # Ensure env var is not set for this test
        old_val = os.environ.pop("GEMINI_API_KEY", None)
        try:
            client = GeminiReviewClient()
            result = client.review_screenshot(
                image_path="fake/path.png",
                prompt="Review this",
            )
            assert result["quality_score"] == 0.0
        finally:
            if old_val is not None:
                os.environ["GEMINI_API_KEY"] = old_val


# ---------------------------------------------------------------------------
# Constructor / configuration
# ---------------------------------------------------------------------------


class TestGeminiReviewClientConfig:
    """Tests for GeminiReviewClient configuration."""

    def test_accepts_api_key_string(self):
        client = GeminiReviewClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"

    def test_empty_string_is_stub(self):
        client = GeminiReviewClient(api_key="")
        assert client.stub_mode is True

    def test_valid_key_is_not_stub(self):
        client = GeminiReviewClient(api_key="real-key")
        assert client.stub_mode is False

    def test_review_screenshot_returns_all_keys(self):
        """Verify the complete return structure regardless of mode."""
        client = GeminiReviewClient(api_key="")
        result = client.review_screenshot(
            image_path="fake/path.png",
            prompt="test prompt",
        )
        expected_keys = {"quality_score", "issues", "suggestions", "summary"}
        assert expected_keys.issubset(result.keys())
