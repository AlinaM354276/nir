from typing import List
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import RelationType, ObjectType
from src.comparison.delta import Delta


class RuleR1(BaseRule):
    RULE_ID = "R1"
    RULE_NAME = "Удаление объекта с зависимостями"
    RULE_DESCRIPTION = "Удаление таблицы/колонки, на которую есть ссылки"

    def apply(self, delta, graph_a, graph_b):
        conflicts = []

        print(
            "[DEBUG REFERENCES]",
            [(e.src, e.dst, e.relation) for e in graph_a.edges if e.relation == RelationType.REFERENCES]
        )

        for removed in delta.objects_removed:

            # 1. находим таблицу
            table = graph_a.get_table_of_object(removed)
            if table is None:
                continue

            # 2. ищем REFERENCES к таблице
            incoming = []
            for edge in graph_a.edges:
                if (
                        edge.dst == table.id
                        and edge.relation == RelationType.REFERENCES
                ):
                    incoming.append(edge)

            # 3. если есть — конфликт
            if incoming:
                conflicts.append({
                    "rule": "R1",
                    "level": "CRITICAL",
                    "message": (
                        f"Removed object {removed.name} "
                        f"but table {table.name} is referenced"
                    ),
                    "details": {
                        "removed_object": removed.name,
                        "table": table.name,
                        "incoming_refs": len(incoming),
                    },
                })

        return conflicts


