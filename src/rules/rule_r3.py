from typing import List, Dict
from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType, RelationType
from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph


class RuleR3(BaseRule):
    RULE_ID = "R3"
    RULE_NAME = "Удаление таблицы, участвующей во внешних связях"
    RULE_DESCRIPTION = (
        "Удаление таблицы, которая участвовала "
        "в внешних ключах (как источник или цель)."
    )
    DEFAULT_LEVEL = ConflictLevel.HIGH

    def apply(
        self,
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> List[Dict]:

        conflicts = []

        for obj in delta.objects_removed:
            #  R3 работает ТОЛЬКО с таблицами
            if obj.type != ObjectType.TABLE:
                continue

            # входящие REFERENCES (на таблицу кто-то ссылался)
            incoming = graph_a.get_incoming(
                obj,
                relation=RelationType.REFERENCES,
            )

            # исходящие REFERENCES (таблица сама ссылалась на другие)
            outgoing = graph_a.get_outgoing(
                obj,
                relation=RelationType.REFERENCES,
            )

            if not incoming and not outgoing:
                continue  # таблица ни с кем не была связана

            conflicts.append({
                "rule": self.RULE_ID,
                "level": self.DEFAULT_LEVEL.value,
                "message": (
                    f"Удалена таблица {obj.name}, "
                    f"участвовавшая во внешних связях"
                ),
                "details": {
                    "table": obj.name,
                    "incoming_refs": len(incoming),
                    "outgoing_refs": len(outgoing),
                },
            })

        return conflicts
