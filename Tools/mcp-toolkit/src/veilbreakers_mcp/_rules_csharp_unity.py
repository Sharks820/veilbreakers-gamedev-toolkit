"""Unity/game-specific C# rules layered on top of the general core."""

from __future__ import annotations

from veilbreakers_mcp._rules_csharp import (
    CSharpLineClassifier,
    DEEP_CHECKS,
    LineContext,
    RULES as ALL_RULES,
)
from veilbreakers_mcp._rules_csharp_core import CORE_RULE_IDS


RULES = [rule for rule in ALL_RULES if rule.id not in CORE_RULE_IDS]


__all__ = ["RULES", "DEEP_CHECKS", "CSharpLineClassifier", "LineContext"]
