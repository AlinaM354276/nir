# src/rules/rule_r7.py
from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.comparison.delta import Delta


class RuleR7(BaseRule):
    """
    R7: Циклические зависимости.
    """

    RULE_ID = "R7"
    RULE_NAME = "Cyclic dependencies"
    RULE_DESCRIPTION = "Detects cyclic dependencies in schema graph."
    DEFAULT_LEVEL = ConflictLevel.CRITICAL

    def apply(self, delta: Delta, graph_a, graph_b) -> List[dict]:
        conflicts = []

        cycles = graph_b.find_cycles() if hasattr(graph_b, "find_cycles") else []

        for cycle in cycles:
            conflicts.append({
                "rule": self.RULE_ID,
                "level": self.DEFAULT_LEVEL.value,
                "message": "Cyclic dependency detected in schema graph",
                "details": {
                    "cycle": [o.get_full_name() for o in cycle],
                },
            })

        return conflicts
