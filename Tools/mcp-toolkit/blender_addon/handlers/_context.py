"""Shared context utilities for Blender addon handlers."""
import bpy


def get_3d_context_override() -> dict | None:
    """Find a 3D Viewport area with WINDOW region for operator context override.

    Returns dict suitable for bpy.context.temp_override(**result), or None
    if no 3D Viewport is available.
    """
    if bpy.context.screen is None:
        return None
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return {"area": area, "region": region}
    return None
