# src/rules/rule_r6.py
from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType
from src.comparison.delta import Delta


class RuleR6(BaseRule):
    RULE_ID = "R6"
    RULE_NAME = "Add NOT NULL without default"
    RULE_DESCRIPTION = "Detects adding NOT NULL constraint without default."
    DEFAULT_LEVEL = ConflictLevel.HIGH

    def apply(self, delta: Delta, graph_a, graph_b) -> List[dict]:
        conflicts = []

        for mod in delta.modified_by_type(ObjectType.COLUMN):
            before = mod.before.attributes or {}
            after = mod.after.attributes or {}

            if (
                before.get("not_null") is False
                and after.get("not_null") is True
                and "default" not in after
            ):
                conflicts.append({
                    "rule": self.RULE_ID,
                    "level": self.DEFAULT_LEVEL.value,
                    "message": (
                        f"Column {mod.after.name} "
                        f"became NOT NULL without DEFAULT"
                    ),
                    "details": {
                        "column": mod.after.name,
                    },
                })

        return conflicts
