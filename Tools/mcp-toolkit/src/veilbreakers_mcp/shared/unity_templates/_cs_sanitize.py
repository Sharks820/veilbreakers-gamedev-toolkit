"""Shared C# string sanitization utilities for Unity template generators."""

from __future__ import annotations

import re


def sanitize_cs_string(value: str) -> str:
    """Escape a value for safe embedding inside a C# string literal."""
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    return value


def sanitize_cs_identifier(value: str) -> str:
    """Sanitize a value for use as a C# identifier.

    Strips all characters that are not alphanumeric or underscore.
    Prepends '_' if result starts with a digit. Returns '_unnamed'
    if nothing remains.
    """
    result = re.sub(r"[^a-zA-Z0-9_]", "", value)
    if not result:
        return "_unnamed"
    if result[0].isdigit():
        result = "_" + result
    return result
