# src/rules/rule_r5.py
from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType
from src.comparison.delta import Delta


class RuleR5(BaseRule):
    """
    R5: Изменение первичного ключа таблицы.
    """

    RULE_ID = "R5"
    RULE_NAME = "Primary key modification"
    RULE_DESCRIPTION = "Detects changes to primary keys."
    DEFAULT_LEVEL = ConflictLevel.CRITICAL

    def apply(self, delta: Delta, graph_a, graph_b) -> List[dict]:
        conflicts = []

        for mod in delta.modified_by_type(ObjectType.PRIMARY_KEY):
            conflicts.append({
                "rule": self.RULE_ID,
                "level": self.DEFAULT_LEVEL.value,
                "message": (
                    f"Primary key of table {mod.after.attributes.get('table')} was modified"
                ),
                "details": {
                    "table": mod.after.attributes.get("table"),
                },
            })

        return conflicts
