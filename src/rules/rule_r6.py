# src/rules/rule_r6.py
from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType
from src.comparison.delta import Delta


class RuleR6(BaseRule):
    """
    R6: Добавление NOT NULL без DEFAULT.
    """

    RULE_ID = "R6"
    RULE_NAME = "Add NOT NULL without default"
    RULE_DESCRIPTION = "Detects adding NOT NULL constraint without default."
    DEFAULT_LEVEL = ConflictLevel.HIGH

    def apply(self, delta: Delta, graph_a, graph_b) -> List[dict]:
        conflicts = []

        for mod in delta.modified_by_type(ObjectType.COLUMN):
            if "is_nullable" not in mod.changed_fields:
                continue

            if (
                mod.before.attributes.get("is_nullable") is True
                and mod.after.attributes.get("is_nullable") is False
                and "default" not in (mod.after.attributes or {})
            ):
                conflicts.append({
                    "rule": self.RULE_ID,
                    "level": self.DEFAULT_LEVEL.value,
                    "message": (
                        f"Column {mod.after.get_full_name()} "
                        f"became NOT NULL without DEFAULT"
                    ),
                    "details": {
                        "column": mod.after.get_full_name(),
                    },
                })

        return conflicts
