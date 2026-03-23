"""Text object creation and conversion handlers.

Provides:
- handle_create_text: Create 3D text objects with font, extrusion, bevel (TEXT-01)
- handle_text_to_mesh: Convert text object to mesh geometry (TEXT-02)

Pure-logic validation functions are testable without Blender.
"""

from __future__ import annotations

import bpy


# ---------------------------------------------------------------------------
# Valid alignment values
# ---------------------------------------------------------------------------

_ALIGNMENTS = frozenset({"LEFT", "CENTER", "RIGHT", "JUSTIFY", "FLUSH"})


# ---------------------------------------------------------------------------
# Pure-logic validation helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_create_text_params(params: dict) -> dict:
    """Validate and normalise create_text parameters.

    Returns dict with validated fields.
    Raises ValueError for invalid values.
    """
    text = params.get("text")
    if not text or not isinstance(text, str):
        raise ValueError("text must be a non-empty string")

    name = params.get("name", "Text")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"name must be a non-empty string, got {name!r}")

    font_size = params.get("font_size", 1.0)
    if not isinstance(font_size, (int, float)) or font_size <= 0:
        raise ValueError(f"font_size must be a positive number, got {font_size!r}")

    extrude_depth = params.get("extrude_depth", 0.0)
    if not isinstance(extrude_depth, (int, float)) or extrude_depth < 0:
        raise ValueError(
            f"extrude_depth must be a non-negative number, got {extrude_depth!r}"
        )

    bevel_depth = params.get("bevel_depth", 0.0)
    if not isinstance(bevel_depth, (int, float)) or bevel_depth < 0:
        raise ValueError(
            f"bevel_depth must be a non-negative number, got {bevel_depth!r}"
        )

    resolution = params.get("resolution", 12)
    if not isinstance(resolution, int) or resolution < 1:
        raise ValueError(
            f"resolution must be a positive integer, got {resolution!r}"
        )

    align = params.get("align", "LEFT")
    if align not in _ALIGNMENTS:
        raise ValueError(
            f"Unknown align: {align!r}. Valid: {sorted(_ALIGNMENTS)}"
        )

    font_path = params.get("font_path")
    if font_path is not None and not isinstance(font_path, str):
        raise ValueError(f"font_path must be a string, got {type(font_path).__name__}")

    position = params.get("position", [0, 0, 0])
    if not isinstance(position, (list, tuple)) or len(position) != 3:
        raise ValueError(f"position must have 3 elements, got {position!r}")

    return {
        "text": text,
        "name": name.strip(),
        "font_size": float(font_size),
        "extrude_depth": float(extrude_depth),
        "bevel_depth": float(bevel_depth),
        "resolution": resolution,
        "align": align,
        "font_path": font_path,
        "position": [float(c) for c in position],
    }


def _validate_text_to_mesh_params(params: dict) -> dict:
    """Validate and normalise text_to_mesh parameters.

    Returns dict with validated fields.
    Raises ValueError for invalid values.
    """
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise ValueError("name is required for text_to_mesh")

    apply_modifiers = params.get("apply_modifiers", True)
    if not isinstance(apply_modifiers, bool):
        raise ValueError(
            f"apply_modifiers must be a boolean, got {type(apply_modifiers).__name__}"
        )

    return {
        "name": name,
        "apply_modifiers": apply_modifiers,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy at runtime)
# ---------------------------------------------------------------------------


def handle_create_text(params: dict) -> dict:
    """Create a 3D text object with configurable font, extrusion, and bevel (TEXT-01).

    Params:
        text: The text content string (required).
        name: Object name (default "Text").
        font_size: Font size / scale (default 1.0).
        extrude_depth: Depth of text extrusion (default 0.0).
        bevel_depth: Bevel depth on text edges (default 0.0).
        resolution: Curve resolution / preview U (default 12).
        align: Text alignment -- LEFT, CENTER, RIGHT, JUSTIFY, FLUSH (default LEFT).
        font_path: Optional path to a .ttf/.otf font file.
        position: [x, y, z] location (default [0, 0, 0]).

    Returns dict with object name, text content, and geometry info.
    """
    validated = _validate_create_text_params(params)

    # Create the text curve data
    text_data = bpy.data.curves.new(name=validated["name"], type="FONT")
    text_data.body = validated["text"]
    text_data.size = validated["font_size"]
    text_data.extrude = validated["extrude_depth"]
    text_data.bevel_depth = validated["bevel_depth"]
    text_data.resolution_u = validated["resolution"]
    text_data.align_x = validated["align"]

    # Load custom font if specified
    if validated["font_path"]:
        try:
            font = bpy.data.fonts.load(validated["font_path"])
            text_data.font = font
        except RuntimeError as e:
            raise ValueError(f"Failed to load font: {validated['font_path']}: {e}")

    # Create the object and link to scene
    obj = bpy.data.objects.new(validated["name"], text_data)
    obj.location = tuple(validated["position"])
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    return {
        "object_name": obj.name,
        "type": "FONT",
        "text": validated["text"],
        "font_size": validated["font_size"],
        "extrude_depth": validated["extrude_depth"],
        "bevel_depth": validated["bevel_depth"],
        "align": validated["align"],
        "location": list(obj.location),
    }


def handle_text_to_mesh(params: dict) -> dict:
    """Convert a text (FONT) object to mesh geometry (TEXT-02).

    Params:
        name: Text object name (required).
        apply_modifiers: Whether to apply modifiers during conversion (default True).

    Returns dict with object name and post-conversion vertex/face counts.
    """
    validated = _validate_text_to_mesh_params(params)
    name = validated["name"]

    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    if obj.type != "FONT":
        raise ValueError(
            f"Object '{name}' is type '{obj.type}', expected 'FONT'"
        )

    # Select and make active -- isolate selection first
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Convert to mesh
    bpy.ops.object.convert(target="MESH")

    return {
        "object_name": obj.name,
        "type": "MESH",
        "vertex_count": len(obj.data.vertices),
        "face_count": len(obj.data.polygons),
    }
