from typing import List, Dict

from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType
from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph


class RuleR4(BaseRule):
    RULE_ID = "R4"
    RULE_NAME = "Удаление ограничения целостности"
    RULE_DESCRIPTION = (
        "Удаление PRIMARY KEY / UNIQUE / FOREIGN KEY, "
        "участвовавших в ограничениях целостности."
    )
    DEFAULT_LEVEL = ConflictLevel.HIGH

    def apply(
        self,
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> List[Dict]:

        conflicts: List[Dict] = []

        for obj in delta.objects_removed:
            if obj.type not in {
                ObjectType.PRIMARY_KEY,
                ObjectType.UNIQUE_CONSTRAINT,
                ObjectType.FOREIGN_KEY,
            }:
                continue

            conflicts.append({
                "rule": self.RULE_ID,
                "level": self.DEFAULT_LEVEL.value,
                "message": f"Удалено ограничение {obj.name}",
                "details": {
                    "constraint": obj.name,
                    "type": obj.type.value,
                    "table": obj.attributes.get("table")
                        or obj.attributes.get("from_table"),
                },
            })

        return conflicts
