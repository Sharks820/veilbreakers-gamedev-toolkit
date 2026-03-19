import contextlib
import io
import math
import random
import json as json_module

import bpy
import bmesh
import mathutils

from ..security import validate_code


EXEC_GLOBALS = {
    "__builtins__": {},
    "bpy": bpy,
    "mathutils": mathutils,
    "bmesh": bmesh,
    "math": math,
    "random": random,
    "json": json_module,
}


def handle_execute_code(params: dict) -> dict:
    code = params.get("code")
    if not code:
        return {
            "status": "error",
            "error_type": "validation",
            "message": "No code provided",
        }

    is_safe, violations = validate_code(code)
    if not is_safe:
        return {
            "status": "error",
            "error_type": "security",
            "message": f"Code validation failed: {violations}",
        }

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, EXEC_GLOBALS.copy())
        return {
            "status": "success",
            "result": {
                "output": stdout_capture.getvalue(),
                "executed": True,
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "execution",
            "message": f"Execution failed: {type(e).__name__}: {str(e)}",
            "output": stdout_capture.getvalue(),
        }
