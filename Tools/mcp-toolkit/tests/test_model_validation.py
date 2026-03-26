"""Tests for model file validation helpers."""

from __future__ import annotations

import json
import struct

from veilbreakers_mcp.shared.model_validation import validate_generated_model_file


def _write_glb(path, *, materials: int = 1) -> None:
    gltf = {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{}],
        "meshes": [{}],
        "materials": [{} for _ in range(materials)],
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * pad

    chunk_header = struct.pack("<I4s", len(json_bytes), b"JSON")
    total_len = 12 + len(chunk_header) + len(json_bytes)
    header = struct.pack("<III", 0x46546C67, 2, total_len)

    path.write_bytes(header + chunk_header + json_bytes)


def test_valid_glb_passes(tmp_path):
    path = tmp_path / "model.glb"
    _write_glb(path)

    result = validate_generated_model_file(str(path))

    assert result["valid"] is True
    assert result["format"] == "glb"
    assert result["checks"]["json_chunk"]["meshes"] == 1


def test_missing_file_fails(tmp_path):
    result = validate_generated_model_file(str(tmp_path / "missing.glb"))

    assert result["valid"] is False
    assert "File not found" in result["error"]


def test_empty_file_fails(tmp_path):
    path = tmp_path / "empty.glb"
    path.write_bytes(b"")

    result = validate_generated_model_file(str(path))

    assert result["valid"] is False
    assert "File is empty" in result["error"]
