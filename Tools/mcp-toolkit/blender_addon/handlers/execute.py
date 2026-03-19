import contextlib
import io
import types
import math
import random
import json as json_module

import bpy
import bmesh
import mathutils

from ..security import validate_code


def _make_module_proxy(mod):
    """Create a read-only proxy of a module's public attributes.

    Prevents sandboxed code from monkey-patching shared modules
    (e.g., math.sin = lambda x: 'HACKED') which would corrupt the
    host Blender process.
    """
    ns = types.SimpleNamespace()
    for name in dir(mod):
        if not name.startswith("_"):
            setattr(ns, name, getattr(mod, name))
    # Preserve module name for repr
    ns.__name__ = mod.__name__
    return ns


# Curated safe builtins — omits: exec, eval, compile, open, getattr,
# setattr, delattr, globals, locals, vars, dir, __import__, type,
# breakpoint, input, help, format (format string dunder bypass), id,
# callable, object, super, property, staticmethod, classmethod
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
    "hash": hash,
    "slice": slice,
    "complex": complex,
    "bytes": bytes,
    "bytearray": bytearray,
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

# Frozen module proxies — created once, prevent monkey-patching of
# real modules. bpy/mathutils/bmesh are passed as-is since they're
# the purpose of the sandbox and need full mutability.
_MATH_PROXY = _make_module_proxy(math)
_RANDOM_PROXY = _make_module_proxy(random)
_JSON_PROXY = _make_module_proxy(json_module)


def _build_exec_globals() -> dict:
    """Build a fresh globals dict for each exec call.

    Returns a new dict with a fresh copy of _SAFE_BUILTINS each time,
    preventing cross-execution builtins poisoning.
    """
    return {
        "__builtins__": dict(_SAFE_BUILTINS),
        "bpy": bpy,
        "mathutils": mathutils,
        "bmesh": bmesh,
        "math": _MATH_PROXY,
        "random": _RANDOM_PROXY,
        "json": _JSON_PROXY,
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
            exec(code, _build_exec_globals())
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
