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
    """Create a fresh read-only-ish proxy of a module's public attributes.

    Returns a new SimpleNamespace each call so that sandbox mutations
    (e.g., ``math.sin = lambda x: 'HACKED'``) only affect the current
    execution and do not persist to subsequent sandbox runs.
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


def _build_exec_globals() -> dict:
    """Build a fresh globals dict for each exec call.

    Returns a new dict with a fresh copy of _SAFE_BUILTINS each time,
    preventing cross-execution builtins poisoning.  Module proxies for
    math/random/json are also created fresh so that monkey-patching
    (e.g. ``math.sin = lambda x: 1``) does not persist across runs.

    Includes a restricted __import__ so that ``import bpy`` and similar
    statements work at runtime (they resolve from the pre-injected
    sandbox modules rather than the real import machinery).
    """
    # Map of module names to sandbox-provided objects.
    # bpy/mathutils/bmesh are passed as-is (need full mutability).
    # math/random/json get fresh proxies each call to prevent poisoning.
    sandbox_modules = {
        "bpy": bpy,
        "mathutils": mathutils,
        "bmesh": bmesh,
        "math": _make_module_proxy(math),
        "random": _make_module_proxy(random),
        "json": _make_module_proxy(json_module),
    }

    def _restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        """Import hook that only resolves pre-approved sandbox modules.

        This enables ``import bpy`` / ``from mathutils import Vector``
        to work at runtime while blocking all other imports.
        """
        if level != 0:
            raise ImportError("relative imports are not allowed")
        root = name.split(".")[0]
        mod = sandbox_modules.get(root)
        if mod is None:
            raise ImportError(
                f"Import of '{name}' is not allowed in sandbox"
            )
        # For dotted imports like 'bpy.ops', return the root so
        # attribute access resolves naturally.
        return mod

    builtins = dict(_SAFE_BUILTINS)
    builtins["__import__"] = _restricted_import

    result = {"__builtins__": builtins}
    result.update(sandbox_modules)
    return result


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
