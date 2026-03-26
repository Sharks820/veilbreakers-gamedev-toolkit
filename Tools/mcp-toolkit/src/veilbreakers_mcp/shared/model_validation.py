"""Validation helpers for generated 3D model files."""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path


def validate_generated_model_file(filepath: str) -> dict:
    """Validate a generated model file before it enters the Blender pipeline.

    The Tripo path should produce GLB files. This helper performs hard
    validation so empty placeholders or corrupt downloads cannot continue.
    """
    result: dict = {
        "valid": False,
        "filepath": filepath,
        "format": "unknown",
        "checks": {},
    }

    if not os.path.isfile(filepath):
        result["error"] = "File not found"
        return result

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        result["error"] = "File is empty"
        return result

    result["checks"]["file_size"] = {"value": file_size, "passed": True}

    ext = Path(filepath).suffix.lower()
    if ext == ".glb":
        result["format"] = "glb"
        result = _validate_glb(filepath, result)
    elif ext == ".fbx":
        result["format"] = "fbx"
        result = _validate_fbx(filepath, result)
    else:
        result["error"] = f"Unsupported format: {ext}"
        return result

    result["valid"] = all(
        check.get("passed", False) for check in result["checks"].values()
    )
    return result


def _validate_glb(filepath: str, result: dict) -> dict:
    """Validate a GLB file by parsing the header and first JSON chunk."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                result["checks"]["header"] = {
                    "passed": False,
                    "error": "File too small for GLB header",
                }
                return result

            magic = struct.unpack("<I", header[0:4])[0]
            if magic != 0x46546C67:
                result["checks"]["header"] = {
                    "passed": False,
                    "error": "Invalid GLB magic bytes",
                }
                return result

            version = struct.unpack("<I", header[4:8])[0]
            declared_length = struct.unpack("<I", header[8:12])[0]
            actual_length = os.path.getsize(filepath)
            result["checks"]["header"] = {
                "passed": True,
                "version": version,
            }
            result["checks"]["declared_length"] = {
                "passed": declared_length == actual_length,
                "value": declared_length,
                "actual": actual_length,
            }

            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                result["checks"]["json_chunk"] = {
                    "passed": False,
                    "error": "Missing JSON chunk",
                }
                return result

            chunk_length = struct.unpack("<I", chunk_header[0:4])[0]
            chunk_type = struct.unpack("<I", chunk_header[4:8])[0]
            if chunk_type != 0x4E4F534A:
                result["checks"]["json_chunk"] = {
                    "passed": False,
                    "error": "First chunk is not JSON",
                }
                return result

            json_data = f.read(chunk_length)
            gltf = json.loads(json_data)
            result["checks"]["json_chunk"] = {
                "passed": True,
                "scenes": len(gltf.get("scenes", [])),
                "nodes": len(gltf.get("nodes", [])),
                "meshes": len(gltf.get("meshes", [])),
                "materials": len(gltf.get("materials", [])),
            }
            result["checks"]["materials"] = {
                "passed": len(gltf.get("materials", [])) > 0,
                "count": len(gltf.get("materials", [])),
            }
    except (OSError, json.JSONDecodeError, ValueError, KeyError, struct.error) as exc:
        result["checks"]["parse_error"] = {
            "passed": False,
            "error": str(exc),
        }

    return result


def _validate_fbx(filepath: str, result: dict) -> dict:
    """Validate an FBX file by checking binary or ASCII header bytes."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(23)
            if header[:20] == b"Kaydara FBX Binary  ":
                result["checks"]["header"] = {
                    "passed": True,
                    "format": "binary",
                }
            else:
                f.seek(0)
                first_line = f.readline().decode("ascii", errors="ignore")
                if "FBX" in first_line.upper():
                    result["checks"]["header"] = {
                        "passed": True,
                        "format": "ascii",
                    }
                else:
                    result["checks"]["header"] = {
                        "passed": False,
                        "error": "Not a valid FBX file",
                    }
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        result["checks"]["parse_error"] = {
            "passed": False,
            "error": str(exc),
        }

    return result
