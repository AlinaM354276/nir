from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import RelationType, ObjectType
from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph


class RuleR1(BaseRule):
    RULE_ID = "R1"
    RULE_NAME = "Удаление таблицы с зависимостями"
    RULE_DESCRIPTION = (
        "Удаление таблицы, на которую существуют внешние ссылки "
        "в исходной версии схемы."
    )
    DEFAULT_LEVEL = ConflictLevel.CRITICAL

    def apply(
        self,
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> List[dict]:

        conflicts = []

        for removed in delta.objects_removed:

            # R1 применим ТОЛЬКО к таблицам
            if removed.type != ObjectType.TABLE:
                continue

            table = graph_a.get_table_of_object(removed)
            if table is None:
                continue

            incoming_refs = [
                e for e in graph_a.edges
                if e.relation == RelationType.REFERENCES
                and e.dst == table.id
                and e.src != table.id
            ]

            if incoming_refs:
                conflicts.append({
                    "rule": self.RULE_ID,
                    "level": self.DEFAULT_LEVEL.value,
                    "message": (
                        f"Таблица '{table.name}' удалена, "
                        f"но в исходной версии схемы на неё существуют внешние ссылки."
                    ),
                    "details": {
                        "table": table.name,
                        "incoming_refs": len(incoming_refs),
                    },
                })

        return conflicts
