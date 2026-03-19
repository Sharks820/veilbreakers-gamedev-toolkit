import contextlib
import io
import math
import random
import json as json_module

import bpy
import bmesh
import mathutils

from ..security import validate_code


# Curated safe builtins — omits dangerous functions like open, exec, eval,
# getattr, globals, locals, vars, dir, __import__, type, breakpoint, input
_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "print": print,
    "len": len,
    "range": range,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "round": round,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "isinstance": isinstance,
    "repr": repr,
    "iter": iter,
    "next": next,
    "any": any,
    "all": all,
    "chr": chr,
    "ord": ord,
    "hex": hex,
    "oct": oct,
    "bin": bin,
    "pow": pow,
    "divmod": divmod,
    "format": format,
    "id": id,
    "hash": hash,
    "callable": callable,
    "slice": slice,
    "complex": complex,
    "bytes": bytes,
    "bytearray": bytearray,
    "memoryview": memoryview,
    "object": object,
    "property": property,
    "staticmethod": staticmethod,
    "classmethod": classmethod,
    "super": super,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
    "RuntimeError": RuntimeError,
    "StopIteration": StopIteration,
    "ZeroDivisionError": ZeroDivisionError,
}

EXEC_GLOBALS = {
    "__builtins__": _SAFE_BUILTINS,
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
