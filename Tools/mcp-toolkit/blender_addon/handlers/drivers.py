"""Driver system handlers for Blender property animation.

Provides:
- handle_add_driver: Add a driver to any object property (DRIVER-01)
- handle_remove_driver: Remove a driver from an object property (DRIVER-02)

Pure-logic validation functions are testable without Blender.
"""

from __future__ import annotations

import bpy


# ---------------------------------------------------------------------------
# Valid constants
# ---------------------------------------------------------------------------

_DRIVER_TYPES = frozenset({"SCRIPTED", "SUM", "MIN", "MAX", "AVERAGE"})

_ID_TYPES = frozenset({
    "OBJECT", "MESH", "ARMATURE", "MATERIAL", "SCENE",
    "WORLD", "CAMERA", "LIGHT", "CURVE", "KEY",
})

_TRANSFORM_TYPES = frozenset({
    "LOC_X", "LOC_Y", "LOC_Z",
    "ROT_X", "ROT_Y", "ROT_Z", "ROT_W",
    "SCALE_X", "SCALE_Y", "SCALE_Z",
})


# ---------------------------------------------------------------------------
# Pure-logic validation helpers (testable without Blender)
# ---------------------------------------------------------------------------


def _validate_driver_variable(var: dict, index: int) -> list[str]:
    """Validate a single driver variable definition.

    Returns list of error strings (empty means valid).
    """
    errors: list[str] = []

    var_name = var.get("name")
    if not var_name or not isinstance(var_name, str):
        errors.append(f"variable[{index}].name must be a non-empty string")

    id_type = var.get("id_type", "OBJECT")
    if id_type not in _ID_TYPES:
        errors.append(
            f"variable[{index}].id_type {id_type!r} invalid. "
            f"Valid: {sorted(_ID_TYPES)}"
        )

    obj_name = var.get("object")
    if not obj_name or not isinstance(obj_name, str):
        errors.append(f"variable[{index}].object must be a non-empty string")

    transform_type = var.get("transform_type")
    if transform_type is not None and transform_type not in _TRANSFORM_TYPES:
        errors.append(
            f"variable[{index}].transform_type {transform_type!r} invalid. "
            f"Valid: {sorted(_TRANSFORM_TYPES)}"
        )

    return errors


def _validate_add_driver_params(params: dict) -> dict:
    """Validate and normalise add_driver parameters.

    Returns dict with validated fields.
    Raises ValueError for invalid values.
    """
    target_object = params.get("target_object")
    if not target_object or not isinstance(target_object, str):
        raise ValueError("target_object must be a non-empty string")

    property_path = params.get("property_path")
    if not property_path or not isinstance(property_path, str):
        raise ValueError("property_path must be a non-empty string")

    property_index = params.get("property_index", -1)
    if not isinstance(property_index, int):
        raise ValueError(
            f"property_index must be an integer, got {type(property_index).__name__}"
        )

    driver_type = params.get("driver_type", "SCRIPTED")
    if driver_type not in _DRIVER_TYPES:
        raise ValueError(
            f"Unknown driver_type: {driver_type!r}. Valid: {sorted(_DRIVER_TYPES)}"
        )

    expression = params.get("expression", "")
    if driver_type == "SCRIPTED" and not expression:
        raise ValueError("expression is required when driver_type is SCRIPTED")

    variables = params.get("variables", [])
    if not isinstance(variables, list):
        raise ValueError("variables must be a list")

    all_errors: list[str] = []
    for i, var in enumerate(variables):
        if not isinstance(var, dict):
            all_errors.append(f"variable[{i}] must be a dict")
            continue
        all_errors.extend(_validate_driver_variable(var, i))

    if all_errors:
        raise ValueError(
            f"Invalid driver variables: {'; '.join(all_errors)}"
        )

    return {
        "target_object": target_object,
        "property_path": property_path,
        "property_index": property_index,
        "driver_type": driver_type,
        "expression": expression,
        "variables": variables,
    }


def _validate_remove_driver_params(params: dict) -> dict:
    """Validate and normalise remove_driver parameters.

    Returns dict with validated fields.
    Raises ValueError for invalid values.
    """
    target_object = params.get("target_object")
    if not target_object or not isinstance(target_object, str):
        raise ValueError("target_object must be a non-empty string")

    property_path = params.get("property_path")
    if not property_path or not isinstance(property_path, str):
        raise ValueError("property_path must be a non-empty string")

    property_index = params.get("property_index", -1)
    if not isinstance(property_index, int):
        raise ValueError(
            f"property_index must be an integer, got {type(property_index).__name__}"
        )

    return {
        "target_object": target_object,
        "property_path": property_path,
        "property_index": property_index,
    }


# ---------------------------------------------------------------------------
# Blender handlers (require bpy at runtime)
# ---------------------------------------------------------------------------


def handle_add_driver(params: dict) -> dict:
    """Add a driver to an object property (DRIVER-01).

    Params:
        target_object: Name of the object to add the driver to (required).
        property_path: RNA property path, e.g. 'location', 'rotation_euler',
            'modifiers["Bevel"].width', or 'data.shape_keys.key_blocks["Smile"].value'.
        property_index: Array index for vector properties (-1 for scalar, 0/1/2 for xyz).
        driver_type: SCRIPTED, SUM, MIN, MAX, or AVERAGE (default SCRIPTED).
        expression: Python expression for SCRIPTED type (required for SCRIPTED).
        variables: List of variable defs, each with:
            - name: Variable name used in expression
            - id_type: Blender ID type (OBJECT, ARMATURE, etc.)
            - object: Source object name
            - bone: Optional bone name (for pose bone transforms)
            - transform_type: LOC_X/Y/Z, ROT_X/Y/Z/W, SCALE_X/Y/Z
            - transform_channel: Alias for transform_type

    Returns dict with driver info.
    """
    validated = _validate_add_driver_params(params)

    obj = bpy.data.objects.get(validated["target_object"])
    if not obj:
        raise ValueError(f"Object not found: {validated['target_object']}")

    property_path = validated["property_path"]
    property_index = validated["property_index"]

    # Add the driver
    if property_index >= 0:
        fcurve = obj.driver_add(property_path, property_index)
    else:
        result = obj.driver_add(property_path)
        # driver_add returns a list for vector properties, single for scalar
        if isinstance(result, list):
            fcurve = result[0]
        else:
            fcurve = result

    driver = fcurve.driver
    driver.type = validated["driver_type"]

    if validated["driver_type"] == "SCRIPTED":
        driver.expression = validated["expression"]

    # Configure variables
    variables_added = []
    for var_def in validated["variables"]:
        var = driver.variables.new()
        var.name = var_def["name"]
        var.type = "TRANSFORMS"

        target = var.targets[0]
        id_type = var_def.get("id_type", "OBJECT")
        target.id_type = id_type
        target.id = bpy.data.objects.get(var_def["object"])

        bone = var_def.get("bone")
        if bone:
            target.bone_target = bone

        transform_type = var_def.get(
            "transform_type", var_def.get("transform_channel", "LOC_X")
        )
        target.transform_type = transform_type
        target.transform_space = var_def.get("transform_space", "LOCAL_SPACE")

        variables_added.append({
            "name": var.name,
            "object": var_def["object"],
            "transform_type": transform_type,
        })

    return {
        "target_object": validated["target_object"],
        "property_path": property_path,
        "property_index": property_index,
        "driver_type": validated["driver_type"],
        "expression": validated.get("expression", ""),
        "variables": variables_added,
    }


def handle_remove_driver(params: dict) -> dict:
    """Remove a driver from an object property (DRIVER-02).

    Params:
        target_object: Name of the object (required).
        property_path: RNA property path (required).
        property_index: Array index (-1 for all).

    Returns dict confirming removal.
    """
    validated = _validate_remove_driver_params(params)

    obj = bpy.data.objects.get(validated["target_object"])
    if not obj:
        raise ValueError(f"Object not found: {validated['target_object']}")

    property_path = validated["property_path"]
    property_index = validated["property_index"]

    if property_index >= 0:
        success = obj.driver_remove(property_path, property_index)
    else:
        success = obj.driver_remove(property_path)

    if not success:
        raise ValueError(
            f"No driver found on '{validated['target_object']}' "
            f"at path '{property_path}'"
        )

    return {
        "target_object": validated["target_object"],
        "property_path": property_path,
        "property_index": property_index,
        "removed": True,
    }
