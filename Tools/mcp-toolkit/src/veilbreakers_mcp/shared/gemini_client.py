"""Gemini visual review client for Unity screenshot quality assessment.

Provides GeminiReviewClient that sends screenshots to Google's Gemini API
for visual quality review. Falls back to stub mode when no API key is
configured, returning a placeholder response.

Pattern follows fal_client.py's graceful degradation approach.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any


class GeminiReviewClient:
    """Client for Gemini-powered visual quality review of screenshots.

    Args:
        api_key: Google Gemini API key. If empty/None, runs in stub mode.
    """

    def __init__(self, api_key: str | None = None) -> None:
        if api_key is None:
            api_key = os.environ.get("GEMINI_API_KEY", "")
        self.api_key: str = api_key
        self.stub_mode: bool = not bool(api_key)

    def review_screenshot(
        self,
        image_path: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Review a screenshot using Gemini vision model.

        Args:
            image_path: Path to the screenshot image file.
            prompt: Review prompt describing what to assess.

        Returns:
            Dict with keys:
                - quality_score (float): 0.0 to 1.0 quality rating
                - issues (list[str]): Identified issues
                - suggestions (list[str]): Improvement suggestions
                - summary (str): Brief text summary
        """
        if self.stub_mode:
            return self._stub_response()

        return self._call_gemini(image_path, prompt)

    def _stub_response(self) -> dict[str, Any]:
        """Return placeholder response when no API key is configured."""
        return {
            "quality_score": 0.0,
            "issues": [],
            "suggestions": [],
            "summary": "Gemini review unavailable (no API key)",
        }

    def _call_gemini(self, image_path: str, prompt: str) -> dict[str, Any]:
        """Send image to Gemini API for visual review.

        Uses google-generativeai SDK if available, falls back to
        httpx-based REST API call.
        """
        try:
            return self._call_via_sdk(image_path, prompt)
        except ImportError:
            return self._call_via_rest(image_path, prompt)
        except Exception as exc:
            return {
                "quality_score": 0.0,
                "issues": [f"Gemini API error: {exc}"],
                "suggestions": [],
                "summary": f"Gemini review failed: {exc}",
            }

    def _call_via_sdk(self, image_path: str, prompt: str) -> dict[str, Any]:
        """Call Gemini using the google-generativeai SDK."""
        import google.generativeai as genai  # type: ignore[import-untyped]

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Read image
        image_data = Path(image_path).read_bytes()

        review_prompt = (
            f"{prompt}\n\n"
            "Respond in JSON format with these keys:\n"
            '- "quality_score": float from 0.0 to 1.0\n'
            '- "issues": list of identified issues as strings\n'
            '- "suggestions": list of improvement suggestions as strings\n'
            '- "summary": brief text summary\n'
        )

        response = model.generate_content(
            [
                review_prompt,
                {"mime_type": "image/png", "data": image_data},
            ]
        )

        return self._parse_response(response.text)

    def _call_via_rest(self, image_path: str, prompt: str) -> dict[str, Any]:
        """Call Gemini via REST API using httpx."""
        import httpx

        image_data = Path(image_path).read_bytes()
        b64_image = base64.b64encode(image_data).decode("utf-8")

        review_prompt = (
            f"{prompt}\n\n"
            "Respond in JSON format with these keys:\n"
            '- "quality_score": float from 0.0 to 1.0\n'
            '- "issues": list of identified issues as strings\n'
            '- "suggestions": list of improvement suggestions as strings\n'
            '- "summary": brief text summary\n'
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": review_prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ]
        }

        response = httpx.post(url, json=payload, timeout=60.0)
        response.raise_for_status()

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return self._parse_response(text)

    @staticmethod
    def _parse_response(text: str) -> dict[str, Any]:
        """Parse Gemini response text into structured dict."""
        # Try to extract JSON from the response
        # Gemini sometimes wraps JSON in markdown code blocks
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # Remove markdown code block
            lines = cleaned.split("\n")
            # Remove first and last lines (``` markers)
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                if line.strip() == "```" and in_block:
                    break
                if in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)

        try:
            result = json.loads(cleaned)
            # Ensure required keys exist with defaults
            return {
                "quality_score": float(result.get("quality_score", 0.0)),
                "issues": list(result.get("issues", [])),
                "suggestions": list(result.get("suggestions", [])),
                "summary": str(result.get("summary", "")),
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            # If parsing fails, return the raw text as summary
            return {
                "quality_score": 0.0,
                "issues": ["Could not parse Gemini response"],
                "suggestions": [],
                "summary": text[:500],
            }
