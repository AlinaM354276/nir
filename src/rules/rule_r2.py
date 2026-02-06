# src/rules/rule_r2.py

from typing import List, Dict, Any, Set

from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType, RelationType
from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph


# Жёстко заданные несовместимые пары типов (прототип)
INCOMPATIBLE_TYPES: Set[tuple] = {
    ("TEXT", "INTEGER"),
    ("VARCHAR", "INTEGER"),
    ("NUMERIC", "INTEGER"),
}


class RuleR2(BaseRule):
    """
    R2: Несовместимое изменение типа колонки,
    если таблица участвует во внешних ссылках (REFERENCES).
    """

    RULE_ID = "R2"
    RULE_NAME = "Несовместимое изменение типа колонки"
    RULE_DESCRIPTION = (
        "Изменение типа колонки на несовместимый, "
        "если таблица участвует во внешних ссылках."
    )
    DEFAULT_LEVEL = ConflictLevel.HIGH

    def apply(
        self,
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> List[Dict[str, Any]]:

        conflicts: List[Dict[str, Any]] = []

        # работаем ТОЛЬКО с изменёнными колонками
        for mod in delta.modified_by_type(ObjectType.COLUMN):

            # интересует только изменение типа
            if "data_type" not in mod.changed_fields:
                continue

            attrs_before = mod.before.attributes or {}
            attrs_after = mod.after.attributes or {}

            old_type = str(attrs_before.get("data_type", "")).upper()
            new_type = str(attrs_after.get("data_type", "")).upper()

            if not old_type or not new_type:
                continue

            #  проверка несовместимости
            if (old_type, new_type) not in INCOMPATIBLE_TYPES:
                continue

            #  получаем ТАБЛИЦУ через API графа (КЛЮЧЕВО!)
            table_obj = graph_b.get_table_of_object(mod.after)
            if not table_obj:
                continue

            # ищем входящие REFERENCES к таблице
            incoming_refs = graph_b.get_incoming(
                table_obj,
                relation=RelationType.REFERENCES,
            )

            if not incoming_refs:
                continue

            # конфликт
            conflicts.append({
                "rule": self.RULE_ID,
                "level": self.DEFAULT_LEVEL.value,
                "message": (
                    f"Несовместимое изменение типа колонки "
                    f"{table_obj.name}.{mod.after.name}: "
                    f"{old_type} → {new_type} при наличии внешних ссылок"
                ),
                "details": {
                    "table": table_obj.name,
                    "column": mod.after.name,
                    "old_type": old_type,
                    "new_type": new_type,
                    "incoming_references": len(incoming_refs),
                },
            })

        return conflicts
