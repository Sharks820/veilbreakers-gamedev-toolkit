"""Unit tests for glb_texture_extractor module.

All tests build minimal valid GLB binaries in-memory (no Blender required).
Tests cover both the pygltflib path and the struct-reader fallback path.
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from veilbreakers_mcp.shared.glb_texture_extractor import (
    _read_glb_chunks,
    extract_glb_textures,
    get_glb_texture_count,
)


# ---------------------------------------------------------------------------
# Helpers: minimal GLB binary builder
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes (8 bytes)
_JPG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 12  # JPEG magic (16 bytes)

_GLB_MAGIC = 0x46546C67  # "glTF"
_JSON_CHUNK_TYPE = 0x4E4F534A
_BIN_CHUNK_TYPE = 0x004E4942


def _pad4(data: bytes) -> bytes:
    """Pad *data* to a 4-byte boundary with null bytes."""
    remainder = len(data) % 4
    if remainder:
        data += b"\x00" * (4 - remainder)
    return data


def _build_glb(gltf_dict: dict, bin_data: bytes = b"") -> bytes:
    """Assemble a minimal GLB binary from a glTF JSON dict and a binary blob."""
    json_bytes = _pad4(json.dumps(gltf_dict).encode("utf-8"))
    bin_bytes = _pad4(bin_data)

    json_chunk = struct.pack("<II", len(json_bytes), _JSON_CHUNK_TYPE) + json_bytes

    total = 12  # header
    total += 8 + len(json_bytes)
    if bin_bytes:
        total += 8 + len(bin_bytes)

    header = struct.pack("<III", _GLB_MAGIC, 2, total)

    result = header + json_chunk
    if bin_bytes:
        bin_chunk = struct.pack("<II", len(bin_bytes), _BIN_CHUNK_TYPE) + bin_bytes
        result += bin_chunk

    return result


def _glb_with_images(image_payloads: list[bytes]) -> bytes:
    """Build a GLB with *image_payloads* embedded in buffer views.

    The payloads are concatenated into the BIN chunk.  All images reference
    bufferView 0, 1, 2, ... in order.
    """
    # Build binary blob: concatenate all payloads (with 4-byte alignment)
    blob = b""
    buffer_views = []
    for payload in image_payloads:
        bv = {"byteOffset": len(blob), "byteLength": len(payload)}
        buffer_views.append(bv)
        blob += payload
        # Align to 4 bytes
        remainder = len(blob) % 4
        if remainder:
            blob += b"\x00" * (4 - remainder)

    # Build image descriptors
    images = [
        {"mimeType": "image/png", "bufferView": i}
        for i in range(len(image_payloads))
    ]

    return buffer_views, images, blob


def _single_image_glb(albedo_payload: bytes) -> bytes:
    """Build a minimal GLB with one albedo image."""
    bvs, imgs, blob = _glb_with_images([albedo_payload])

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": bvs,
        "images": imgs,
        "textures": [{"source": 0}],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0}
                }
            }
        ],
    }
    return _build_glb(gltf, blob)


def _two_image_glb(albedo_payload: bytes, orm_payload: bytes) -> bytes:
    """Build a GLB with albedo + ORM images."""
    bvs, imgs, blob = _glb_with_images([albedo_payload, orm_payload])

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": bvs,
        "images": imgs,
        "textures": [{"source": 0}, {"source": 1}],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicRoughnessTexture": {"index": 1},
                }
            }
        ],
    }
    return _build_glb(gltf, blob)


def _albedo_only_glb(albedo_payload: bytes) -> bytes:
    """Build a GLB with only albedo (no normal, no ORM)."""
    return _single_image_glb(albedo_payload)


def _albedo_normal_orm_glb(
    albedo_payload: bytes,
    normal_payload: bytes,
    orm_payload: bytes,
) -> bytes:
    """Build a GLB with albedo + normal + ORM images."""
    bvs, imgs, blob = _glb_with_images(
        [albedo_payload, normal_payload, orm_payload]
    )

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": bvs,
        "images": imgs,
        "textures": [{"source": 0}, {"source": 1}, {"source": 2}],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicRoughnessTexture": {"index": 2},
                },
                "normalTexture": {"index": 1},
            }
        ],
    }
    return _build_glb(gltf, blob)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1: extract albedo from minimal GLB
# ---------------------------------------------------------------------------

def test_extracts_albedo_from_minimal_glb(tmp: Path) -> None:
    """extract_glb_textures writes albedo PNG to disk and returns its path."""
    albedo_bytes = _PNG_MAGIC + b"\x00" * 24  # minimal "PNG" payload
    glb_data = _single_image_glb(albedo_bytes)

    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)
    out_dir = str(tmp / "textures")

    # Force struct path regardless of pygltflib availability
    with mock.patch(
        "veilbreakers_mcp.shared.glb_texture_extractor._HAS_PYGLTFLIB", False
    ):
        result = extract_glb_textures(str(glb_path), out_dir)

    assert "albedo" in result, f"Expected 'albedo' key, got: {result}"
    assert os.path.isfile(result["albedo"]), "Albedo file should exist on disk"


# ---------------------------------------------------------------------------
# Test 2: extract ORM separate from albedo
# ---------------------------------------------------------------------------

def test_extracts_orm_separate_from_albedo(tmp: Path) -> None:
    """extract_glb_textures extracts both albedo and orm when GLB has two images."""
    albedo_bytes = _PNG_MAGIC + b"\x01" * 16
    orm_bytes = _PNG_MAGIC + b"\x02" * 16

    glb_data = _two_image_glb(albedo_bytes, orm_bytes)
    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)
    out_dir = str(tmp / "textures")

    with mock.patch(
        "veilbreakers_mcp.shared.glb_texture_extractor._HAS_PYGLTFLIB", False
    ):
        result = extract_glb_textures(str(glb_path), out_dir)

    assert "albedo" in result
    assert "orm" in result
    # Verify both files exist
    assert os.path.isfile(result["albedo"])
    assert os.path.isfile(result["orm"])
    # Verify content differs (different files)
    assert result["albedo"] != result["orm"]


# ---------------------------------------------------------------------------
# Test 3: handles missing normal gracefully
# ---------------------------------------------------------------------------

def test_handles_missing_normal_gracefully(tmp: Path) -> None:
    """No KeyError when GLB has only albedo (no normal texture)."""
    albedo_bytes = _PNG_MAGIC + b"\x00" * 16
    glb_data = _albedo_only_glb(albedo_bytes)

    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)
    out_dir = str(tmp / "textures")

    with mock.patch(
        "veilbreakers_mcp.shared.glb_texture_extractor._HAS_PYGLTFLIB", False
    ):
        result = extract_glb_textures(str(glb_path), out_dir)

    assert "normal" not in result, "normal should not be in result when absent"
    assert "albedo" in result


# ---------------------------------------------------------------------------
# Test 4: buffer view offset alignment
# ---------------------------------------------------------------------------

def test_buffer_view_offset_alignment(tmp: Path) -> None:
    """Images at non-zero byteOffset are extracted correctly."""
    # Build a blob where ORM starts at a non-zero offset (after albedo + padding)
    albedo_bytes = _PNG_MAGIC + b"\x11" * 20  # 28 bytes
    orm_bytes = _PNG_MAGIC + b"\x22" * 20     # 28 bytes

    # Manual blob: albedo at 0, orm at offset 32 (padded to 4-byte boundary)
    padded_albedo = albedo_bytes + b"\x00" * ((4 - len(albedo_bytes) % 4) % 4)
    blob = padded_albedo + orm_bytes

    bv_albedo = {"byteOffset": 0, "byteLength": len(albedo_bytes)}
    bv_orm = {"byteOffset": len(padded_albedo), "byteLength": len(orm_bytes)}

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [bv_albedo, bv_orm],
        "images": [
            {"mimeType": "image/png", "bufferView": 0},
            {"mimeType": "image/png", "bufferView": 1},
        ],
        "textures": [{"source": 0}, {"source": 1}],
        "materials": [
            {
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicRoughnessTexture": {"index": 1},
                }
            }
        ],
    }

    padded_blob = blob + (b"\x00" * ((4 - len(blob) % 4) % 4))
    glb_data = _build_glb(gltf, padded_blob)
    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)
    out_dir = str(tmp / "textures")

    with mock.patch(
        "veilbreakers_mcp.shared.glb_texture_extractor._HAS_PYGLTFLIB", False
    ):
        result = extract_glb_textures(str(glb_path), out_dir)

    assert "albedo" in result
    assert "orm" in result

    # Verify the extracted ORM starts with the correct magic bytes
    orm_content = Path(result["orm"]).read_bytes()
    assert orm_content[:8] == _PNG_MAGIC, "ORM bytes should start with PNG magic"

    # Verify albedo content is correct
    albedo_content = Path(result["albedo"]).read_bytes()
    assert albedo_content[:8] == _PNG_MAGIC


# ---------------------------------------------------------------------------
# Test 5: get_glb_texture_count
# ---------------------------------------------------------------------------

def test_get_glb_texture_count(tmp: Path) -> None:
    """get_glb_texture_count returns the number of embedded images."""
    albedo_bytes = _PNG_MAGIC + b"\x00" * 8
    orm_bytes = _PNG_MAGIC + b"\x00" * 8
    normal_bytes = _PNG_MAGIC + b"\x00" * 8

    _, imgs, blob = _glb_with_images([albedo_bytes, orm_bytes, normal_bytes])

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(blob)}],
        "bufferViews": [
            {"byteOffset": 0, "byteLength": len(albedo_bytes)},
            {"byteOffset": len(albedo_bytes), "byteLength": len(orm_bytes)},
            {"byteOffset": len(albedo_bytes) + len(orm_bytes), "byteLength": len(normal_bytes)},
        ],
        "images": imgs,
    }

    padded_blob = blob + (b"\x00" * ((4 - len(blob) % 4) % 4))
    glb_data = _build_glb(gltf, padded_blob)
    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)

    count = get_glb_texture_count(str(glb_path))
    assert count == 3, f"Expected 3 images, got {count}"


def test_get_glb_texture_count_zero_for_no_images(tmp: Path) -> None:
    """get_glb_texture_count returns 0 when no images are embedded."""
    gltf = {"asset": {"version": "2.0"}}
    glb_data = _build_glb(gltf)
    glb_path = tmp / "empty.glb"
    glb_path.write_bytes(glb_data)

    count = get_glb_texture_count(str(glb_path))
    assert count == 0


# ---------------------------------------------------------------------------
# Test 6: fallback when pygltflib absent
# ---------------------------------------------------------------------------

def test_fallback_when_pygltflib_absent(tmp: Path) -> None:
    """extract_glb_textures uses the struct reader when pygltflib unavailable."""
    albedo_bytes = _PNG_MAGIC + b"\xAB" * 16
    orm_bytes = _PNG_MAGIC + b"\xCD" * 16
    normal_bytes = _PNG_MAGIC + b"\xEF" * 16

    glb_data = _albedo_normal_orm_glb(albedo_bytes, normal_bytes, orm_bytes)
    glb_path = tmp / "model.glb"
    glb_path.write_bytes(glb_data)
    out_dir = str(tmp / "textures_fallback")

    with mock.patch(
        "veilbreakers_mcp.shared.glb_texture_extractor._HAS_PYGLTFLIB", False
    ):
        result = extract_glb_textures(str(glb_path), out_dir)

    # All three channels should be extracted via the fallback
    assert "albedo" in result, f"albedo missing; got keys: {list(result.keys())}"
    assert "normal" in result, f"normal missing; got keys: {list(result.keys())}"
    assert "orm" in result, f"orm missing; got keys: {list(result.keys())}"

    # Files should exist
    for channel, path in result.items():
        assert os.path.isfile(path), f"File missing for channel '{channel}': {path}"
