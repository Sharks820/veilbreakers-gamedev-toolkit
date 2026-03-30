"""Test file with KNOWN GOOD code that the reviewer should NOT flag.

Each function/section is labeled with the rule ID it should NOT trigger.
"""
import ast
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "safe_eval",
    "safe_process",
    "safe_defaults",
    "safe_broad_except",
    "safe_reexport_check",
    "safe_lambda_capture",
    "safe_dict_get",
    "safe_open",
    "safe_none_check",
    "safe_json_load",
]


# === NOT PY-SEC-01: ast.literal_eval is safe ===
def safe_eval(data: str) -> Any:
    """Uses ast.literal_eval which is safe."""
    return ast.literal_eval(data)


# === NOT PY-SEC-02: subprocess without shell=True ===
def safe_process(args: list[str]) -> int:
    import subprocess
    result = subprocess.run(args, shell=False, capture_output=True)
    return result.returncode


# === NOT PY-COR-01: Proper None default pattern ===
def safe_defaults(items: Optional[list] = None) -> list:
    """Uses None default with explicit check."""
    if items is None:
        items = []
    items.append("safe")
    return items


# === NOT PY-COR-12: Broad except WITH proper logging ===
def safe_broad_except() -> None:
    """Broad except but logs the exception properly."""
    try:
        risky_call()
    except Exception as e:
        logger.exception("Failed during risky_call: %s", e)
        raise


# === NOT PY-COR-12: Broad except WITH structured return ===
def safe_broad_except_return() -> dict:
    """Broad except but returns a meaningful error response."""
    try:
        result = risky_call()
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e), "details": repr(e)}


# === NOT PY-STY-07: Import that IS re-exported ===
# The `re` import above IS used in this module (see safe_regex below)
# The `ast` import IS used in safe_eval
# The `json` import IS used in safe_json_load


# === NOT PY-COR-15: Lambda with proper capture ===
def safe_lambda_capture() -> list:
    """Lambda in loop with proper default-arg capture."""
    callbacks = []
    for i in range(10):
        callbacks.append(lambda x, i=i: x + i)  # Safe: i=i captures
    return callbacks


# === NOT PY-COR-06: dict.get with mutable default NOT mutated ===
def safe_dict_get(config: dict) -> int:
    """dict.get with [] default but only reads it, never mutates."""
    items = config.get("items", [])
    return len(items)  # Read-only usage, should NOT flag


def safe_dict_get_iterate(config: dict) -> None:
    """dict.get with [] default, iterates but doesn't mutate."""
    items = config.get("items", [])
    for item in items:
        print(item)


# === NOT PY-COR-04: open() WITH context manager ===
def safe_open(path: str) -> str:
    """Uses with statement for file handling."""
    with open(path, encoding="utf-8") as f:
        return f.read()


# === NOT PY-COR-03: Proper None comparison ===
def safe_none_check(val: Any) -> bool:
    """Uses 'is None' instead of '== None'."""
    if val is None:
        return True
    return False


# === NOT PY-COR-09: json.loads WITH error handling ===
def safe_json_load(data: str) -> Optional[dict]:
    """json.loads wrapped in try/except."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


# === NOT PY-COR-14: Not shadowing builtins ===
def safe_naming() -> None:
    """Uses non-builtin names for local variables."""
    items = [1, 2, 3]  # Not 'list'
    mapping = {"a": 1}  # Not 'dict'
    unique = {1, 2, 3}  # Not 'set'
    obj_type = "string"  # Not 'type'
    obj_id = 42  # Not 'id'


# === NOT PY-SEC-07: assert in test code (this is test fixtures dir) ===
# The file path contains 'fixtures' which is a test dir


# === Comment with eval() should NOT flag ===
# eval(data)  -- this is a comment, not code


# === String with eval() should NOT flag ===
HELP_TEXT = "Do not use eval() in production code"


def risky_call():
    """Placeholder for test purposes."""
    pass


def safe_regex() -> bool:
    """Uses compiled regex outside loop."""
    pattern = re.compile(r"\d+")
    items = ["abc", "123", "def"]
    results = []
    for item in items:
        if pattern.match(item):
            results.append(item)
    return len(results) > 0
