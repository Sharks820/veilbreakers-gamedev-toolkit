"""Shared type definitions for the VeilBreakers code reviewer.

``Severity``, ``Category``, and ``FindingType`` were previously duplicated in
``_rules_csharp.py``, ``_rules_python.py``, and ``vb_code_reviewer.py``.  This
module is the single canonical source so each file imports from here instead of
maintaining its own copy.

No imports from other ``veilbreakers_mcp`` modules — keeps the dependency graph
acyclic and lets rule modules (which are imported *by* the main reviewer) pull
these types in safely.
"""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class Category(IntEnum):
    Security = 0
    Bug = 1
    Performance = 2
    Quality = 3
    Unity = 4  # C#-specific; Python rules leave this unused


class FindingType(IntEnum):
    ERROR = 0
    BUG = 1
    OPTIMIZATION = 2
    STRENGTHENING = 3
