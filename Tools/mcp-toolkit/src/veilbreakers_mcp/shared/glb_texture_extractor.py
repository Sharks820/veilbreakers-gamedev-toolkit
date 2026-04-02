"""GLB texture extractor -- parse PBR channel maps from GLB binary.

Extracts embedded albedo, normal, ORM (occlusion/roughness/metallic), AO,
and emissive images from a GLB file's binary chunk into standalone PNG/JPG
files on disk.  Operates entirely on the MCP side (no Blender dependency)
so textures are present before ``bpy.ops.import_scene.gltf`` is called.

Two backends are supported:
  - ``pygltflib`` (primary): cleaner API, handles alignment padding correctly.
  - Struct/JSON fallback (secondary): used if pygltflib is not installed;
    replicates the same ``byteOffset + byteLength`` slice logic.

Exports:
    extract_glb_textures     -- Extract all PBR channel maps from a GLB file.
    get_glb_texture_count    -- Return the number of embedded images in a GLB.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Optional dependency: pygltflib
# ---------------------------------------------------------------------------

try:
    import pygltflib as _pygltflib  # type: ignore[import]
    _HAS_PYGLTFLIB = True
except ImportError:
    _pygltflib = None  # type: ignore[assignment]
    _HAS_PYGLTFLIB = False


# ---------------------------------------------------------------------------
# GLB binary constants
# ---------------------------------------------------------------------------

_GLB_MAGIC = 0x46546C67  # "glTF"
_GLB_JSON_CHUNK_TYPE = 0x4E4F534A  # "JSON"
_GLB_BIN_CHUNK_TYPE = 0x004E4942   # "BIN\0"
_HEADER_SIZE = 12  # magic(4) + version(4) + length(4)
_CHUNK_HEADER_SIZE = 8  # chunkLength(4) + chunkType(4)


# ---------------------------------------------------------------------------
# Internal: struct-based GLB reader (fallback)
# ---------------------------------------------------------------------------

def _read_glb_chunks(glb_path: str) -> tuple[dict, bytes]:
    """Read the JSON descriptor and binary blob from a GLB file.

    Returns (gltf_dict, bin_blob).  Raises ValueError on malformed input.
    """
    with open(glb_path, "rb") as fh:
        data = fh.read()

    if len(data) < _HEADER_SIZE:
        raise ValueError(f"File too small to be a valid GLB: {glb_path}")

    magic, _version, _total_length = struct.unpack_from("<III", data, 0)
    if magic != _GLB_MAGIC:
        raise ValueError(f"Not a valid GLB file (bad magic): {glb_path}")

    offset = _HEADER_SIZE
    json_chunk_data: Optional[bytes] = None
    bin_chunk_data: bytes = b""

    while offset + _CHUNK_HEADER_SIZE <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += _CHUNK_HEADER_SIZE
        chunk_body = data[offset: offset + chunk_length]
        offset += chunk_length

        if chunk_type == _GLB_JSON_CHUNK_TYPE:
            json_chunk_data = chunk_body
        elif chunk_type == _GLB_BIN_CHUNK_TYPE:
            bin_chunk_data = chunk_body

    if json_chunk_data is None:
        raise ValueError(f"GLB has no JSON chunk: {glb_path}")

    gltf = json.loads(json_chunk_data.rstrip(b"\x00"))
    return gltf, bin_chunk_data


def _save_image_from_struct(
    gltf: dict,
    blob: bytes,
    img_index: int,
    out_dir: str,
    name: str,
) -> Optional[str]:
    """Slice the binary blob for image *img_index* and write it to disk.

    Returns the file path on success, None if the image has no bufferView.
    """
    images = gltf.get("images", [])
    if img_index >= len(images):
        return None

    img = images[img_index]
    bv_index = img.get("bufferView")
    if bv_index is None:
        return None

    buffer_views = gltf.get("bufferViews", [])
    if bv_index >= len(buffer_views):
        return None

    bv = buffer_views[bv_index]
    byte_offset = bv.get("byteOffset", 0)
    byte_length = bv.get("byteLength", 0)

    if byte_length <= 0:
        return None

    image_bytes = blob[byte_offset: byte_offset + byte_length]

    # Determine extension from MIME type or magic bytes
    mime = img.get("mimeType", "")
    if mime == "image/png" or image_bytes[:4] == b"\x89PNG":
        ext = ".png"
    elif mime in ("image/jpeg", "image/jpg") or image_bytes[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    else:
        ext = ".png"  # safe default

    path = os.path.join(out_dir, f"{name}{ext}")
    Path(path).write_bytes(image_bytes)

    if os.path.getsize(path) == 0:
        os.remove(path)
        return None

    return path


# ---------------------------------------------------------------------------
# Internal: pygltflib-based image saver (primary)
# ---------------------------------------------------------------------------

def _save_image_from_pygltflib(
    gltf: "_pygltflib.GLTF2",
    blob: bytes,
    img_index: int,
    out_dir: str,
    name: str,
) -> Optional[str]:
    """Save image *img_index* from a pygltflib GLTF2 object to *out_dir*."""
    if img_index is None or img_index >= len(gltf.images):
        return None

    img = gltf.images[img_index]
    bv_index = img.bufferView
    if bv_index is None:
        return None

    if bv_index >= len(gltf.bufferViews):
        return None

    bv = gltf.bufferViews[bv_index]
    byte_offset = bv.byteOffset or 0
    byte_length = bv.byteLength or 0

    if byte_length <= 0:
        return None

    image_bytes = blob[byte_offset: byte_offset + byte_length]

    mime = img.mimeType or ""
    if mime == "image/png" or image_bytes[:4] == b"\x89PNG":
        ext = ".png"
    elif mime in ("image/jpeg", "image/jpg") or image_bytes[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    else:
        ext = ".png"

    path = os.path.join(out_dir, f"{name}{ext}")
    Path(path).write_bytes(image_bytes)

    if os.path.getsize(path) == 0:
        os.remove(path)
        return None

    return path


# ---------------------------------------------------------------------------
# Internal: texture index -> source image index resolver
# ---------------------------------------------------------------------------

def _resolve_texture_source_struct(gltf: dict, tex_index: int) -> Optional[int]:
    """Resolve textures[tex_index].source -> image index (struct path)."""
    textures = gltf.get("textures", [])
    if tex_index >= len(textures):
        return None
    return textures[tex_index].get("source")


def _resolve_texture_source_pygltflib(
    gltf: "_pygltflib.GLTF2", tex_index: int
) -> Optional[int]:
    """Resolve textures[tex_index].source -> image index (pygltflib path)."""
    if tex_index >= len(gltf.textures):
        return None
    return gltf.textures[tex_index].source


# ---------------------------------------------------------------------------
# Public API: extract_glb_textures
# ---------------------------------------------------------------------------

def extract_glb_textures(glb_path: str, out_dir: str) -> dict[str, str]:
    """Extract PBR channel maps from a GLB file to *out_dir*.

    Reads ``materials[0].pbrMetallicRoughness`` plus ``normalTexture``,
    ``occlusionTexture``, and ``emissiveTexture`` and writes each embedded
    image to *out_dir* as a standalone PNG or JPG file.

    Channel naming convention:
      - ``"albedo"`` -- baseColorTexture
      - ``"orm"``    -- metallicRoughnessTexture (ORM-packed: R=AO, G=rough, B=metal)
      - ``"normal"`` -- normalTexture
      - ``"ao"``     -- occlusionTexture (only if separate from orm)
      - ``"emissive"`` -- emissiveTexture (if present)

    Args:
        glb_path: Absolute path to the input GLB file.
        out_dir:  Directory where extracted images will be written.
                  Created automatically if it does not exist.

    Returns:
        Dict mapping channel name to absolute file path.  Keys are only
        present when that channel exists in the file.

    Raises:
        FileNotFoundError: If *glb_path* does not exist.
        ValueError: If the file is not a valid GLB.
    """
    if not os.path.isfile(glb_path):
        raise FileNotFoundError(f"GLB file not found: {glb_path}")

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    if _HAS_PYGLTFLIB:
        return _extract_with_pygltflib(glb_path, out_dir)
    return _extract_with_struct(glb_path, out_dir)


def _extract_with_pygltflib(glb_path: str, out_dir: str) -> dict[str, str]:
    """Extract textures using the pygltflib library (primary path).

    Iterates over ALL materials.  For single-material models the channel
    names are unchanged.  For multi-material models the material index is
    appended (``albedo_mat0``, ``albedo_mat1``).
    """
    gltf = _pygltflib.GLTF2().load(glb_path)
    blob = gltf.binary_blob() or b""

    channel_map: dict[str, str] = {}

    if not gltf.materials:
        return channel_map

    multi = len(gltf.materials) > 1

    for mat_idx, mat in enumerate(gltf.materials):
        suffix = f"_mat{mat_idx}" if multi else ""
        pbr = mat.pbrMetallicRoughness
        orm_tex_index: Optional[int] = None

        if pbr and pbr.baseColorTexture is not None:
            img_idx = _resolve_texture_source_pygltflib(gltf, pbr.baseColorTexture.index)
            if img_idx is not None:
                p = _save_image_from_pygltflib(gltf, blob, img_idx, out_dir, f"albedo{suffix}")
                if p:
                    channel_map[f"albedo{suffix}"] = p

        if pbr and pbr.metallicRoughnessTexture is not None:
            orm_tex_index = pbr.metallicRoughnessTexture.index
            img_idx = _resolve_texture_source_pygltflib(gltf, orm_tex_index)
            if img_idx is not None:
                p = _save_image_from_pygltflib(gltf, blob, img_idx, out_dir, f"orm{suffix}")
                if p:
                    channel_map[f"orm{suffix}"] = p

        if mat.normalTexture is not None:
            img_idx = _resolve_texture_source_pygltflib(gltf, mat.normalTexture.index)
            if img_idx is not None:
                p = _save_image_from_pygltflib(gltf, blob, img_idx, out_dir, f"normal{suffix}")
                if p:
                    channel_map[f"normal{suffix}"] = p

        if mat.occlusionTexture is not None:
            ao_tex_index = mat.occlusionTexture.index
            if ao_tex_index != orm_tex_index:
                img_idx = _resolve_texture_source_pygltflib(gltf, ao_tex_index)
                if img_idx is not None:
                    p = _save_image_from_pygltflib(gltf, blob, img_idx, out_dir, f"ao{suffix}")
                    if p:
                        channel_map[f"ao{suffix}"] = p

        if mat.emissiveTexture is not None:
            img_idx = _resolve_texture_source_pygltflib(gltf, mat.emissiveTexture.index)
            if img_idx is not None:
                p = _save_image_from_pygltflib(gltf, blob, img_idx, out_dir, f"emissive{suffix}")
                if p:
                    channel_map[f"emissive{suffix}"] = p

    return channel_map


def _extract_with_struct(glb_path: str, out_dir: str) -> dict[str, str]:
    """Extract textures using the struct/JSON fallback path.

    Iterates over ALL materials.  For multi-material models the material
    index is appended to channel names.
    """
    gltf, blob = _read_glb_chunks(glb_path)

    channel_map: dict[str, str] = {}
    materials = gltf.get("materials", [])
    if not materials:
        return channel_map

    multi = len(materials) > 1

    def save(tex_info: dict | None, name: str) -> Optional[str]:
        if tex_info is None:
            return None
        tex_index = tex_info.get("index")
        if tex_index is None:
            return None
        img_idx = _resolve_texture_source_struct(gltf, tex_index)
        if img_idx is None:
            return None
        return _save_image_from_struct(gltf, blob, img_idx, out_dir, name)

    for mat_idx, mat in enumerate(materials):
        suffix = f"_mat{mat_idx}" if multi else ""
        pbr = mat.get("pbrMetallicRoughness", {}) or {}
        orm_tex_index: Optional[int] = None

        base_tex = pbr.get("baseColorTexture")
        if base_tex:
            p = save(base_tex, f"albedo{suffix}")
            if p:
                channel_map[f"albedo{suffix}"] = p

        mr_tex = pbr.get("metallicRoughnessTexture")
        if mr_tex:
            orm_tex_index = mr_tex.get("index")
            p = save(mr_tex, f"orm{suffix}")
            if p:
                channel_map[f"orm{suffix}"] = p

        norm_tex = mat.get("normalTexture")
        if norm_tex:
            p = save(norm_tex, f"normal{suffix}")
            if p:
                channel_map[f"normal{suffix}"] = p

        ao_tex = mat.get("occlusionTexture")
        if ao_tex:
            ao_tex_index = ao_tex.get("index")
            if ao_tex_index != orm_tex_index:
                p = save(ao_tex, f"ao{suffix}")
                if p:
                    channel_map[f"ao{suffix}"] = p

        em_tex = mat.get("emissiveTexture")
        if em_tex:
            p = save(em_tex, f"emissive{suffix}")
            if p:
                channel_map[f"emissive{suffix}"] = p

    return channel_map


# ---------------------------------------------------------------------------
# Public API: get_glb_texture_count
# ---------------------------------------------------------------------------

def get_glb_texture_count(glb_path: str) -> int:
    """Return the number of images embedded in a GLB file.

    Uses the lightweight struct reader regardless of pygltflib availability
    to avoid loading the full binary blob when we only need the count.

    Args:
        glb_path: Absolute path to the GLB file.

    Returns:
        Integer count of images (may be 0).

    Raises:
        FileNotFoundError: If *glb_path* does not exist.
        ValueError: If the file is not a valid GLB.
    """
    if not os.path.isfile(glb_path):
        raise FileNotFoundError(f"GLB file not found: {glb_path}")

    gltf, _ = _read_glb_chunks(glb_path)
    return len(gltf.get("images", []))
