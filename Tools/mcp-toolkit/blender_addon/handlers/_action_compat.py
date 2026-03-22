"""Blender 5.0 Action API compatibility layer.

Blender 5.0 replaced action.fcurves with a layered system:
  action.slots -> action.layers -> strips -> channelbags -> fcurves

This module provides helpers that work across both APIs.
"""

from __future__ import annotations

import bpy


def is_layered_action(action) -> bool:
    """Check if this Blender version uses the layered Action API."""
    return not hasattr(action, "fcurves")


def setup_action_for_armature(action, armature_obj):
    """Set up action with proper slot/layer/strip for Blender 5.0+.

    Returns (channelbag_or_none, is_layered).
    For legacy Blender, returns (None, False).
    """
    if not is_layered_action(action):
        return None, False

    # Create slot for this armature
    if hasattr(action, "slots"):
        if len(action.slots) == 0:
            slot = action.slots.new(for_id=armature_obj)
        else:
            slot = action.slots[0]
    else:
        return None, True

    # Assign slot to armature
    if hasattr(armature_obj, "animation_data") and armature_obj.animation_data:
        try:
            armature_obj.animation_data.action_slot = slot
        except (AttributeError, TypeError, RuntimeError):
            pass

    # Create layer
    if hasattr(action, "layers"):
        if len(action.layers) == 0:
            layer = action.layers.new(name="Layer")
        else:
            layer = action.layers[0]
    else:
        return None, True

    # Create strip
    if len(layer.strips) == 0:
        strip = layer.strips.new(type='KEYFRAME')
    else:
        strip = layer.strips[0]

    # Get or create channelbag for our slot
    channelbag = None
    for cb in strip.channelbags:
        if cb.slot == slot:
            channelbag = cb
            break
    if channelbag is None:
        channelbag = strip.channelbags.new(slot=slot)

    return channelbag, True


def get_fcurves(action, channelbag=None, is_layered=False):
    """Get the fcurves collection from an action.

    Returns an iterable of fcurves.
    """
    if is_layered and channelbag is not None:
        return channelbag.fcurves
    if hasattr(action, "fcurves"):
        return action.fcurves
    return []


def new_fcurve(action, data_path, index, channelbag=None, is_layered=False):
    """Create a new fcurve on the action."""
    if is_layered and channelbag is not None:
        return channelbag.fcurves.new(data_path=data_path, index=index)
    return action.fcurves.new(data_path=data_path, index=index)


def remove_fcurve(action, fc, channelbag=None, is_layered=False):
    """Remove an fcurve from the action."""
    if is_layered and channelbag is not None:
        channelbag.fcurves.remove(fc)
    elif hasattr(action, "fcurves"):
        action.fcurves.remove(fc)


def get_frame_range(action, channelbag=None, is_layered=False):
    """Get [start, end] frame range from an action."""
    if is_layered and channelbag is not None:
        all_frames = []
        for fc in channelbag.fcurves:
            for kp in fc.keyframe_points:
                all_frames.append(kp.co[0])
        if all_frames:
            return [int(min(all_frames)), int(max(all_frames))]
        return [0, 0]
    if hasattr(action, "frame_range"):
        return [int(action.frame_range[0]), int(action.frame_range[1])]
    return [0, 0]


def get_fcurve_count(action, channelbag=None, is_layered=False):
    """Get the number of fcurves in the action."""
    if is_layered and channelbag is not None:
        return len(list(channelbag.fcurves))
    if hasattr(action, "fcurves"):
        return len(action.fcurves)
    return 0
