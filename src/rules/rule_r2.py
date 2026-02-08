from typing import List, Dict, Any

from src.rules.base import BaseRule, ConflictLevel
from src.core.models import ObjectType, RelationType
from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph
from src.utils.type_compatibility import TypeCompatibilityChecker


class RuleR2(BaseRule):
    """
    R2: Несовместимое изменение типа колонки,
    если таблица участвует во внешних ссылках.
    """

    RULE_ID = "R2"
    RULE_NAME = "Несовместимое изменение типа колонки"
    RULE_DESCRIPTION = (
        "Изменение типа колонки на несовместимый или опасный, "
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

        for mod in delta.modified_by_type(ObjectType.COLUMN):
            if "data_type" not in mod.changed_fields:
                continue

            old_type = mod.before.attributes.get("data_type")
            new_type = mod.after.attributes.get("data_type")

            if not old_type or not new_type:
                continue

            analysis = TypeCompatibilityChecker.analyze_type_change(
                old_type,
                new_type,
                column_name=mod.after.name,
                table_name=graph_b.get_table_of_object(mod.after).name
                if graph_b.get_table_of_object(mod.after)
                else "",
            )

            # таблица должна участвовать во внешних ссылках
            table_obj = graph_b.get_table_of_object(mod.after)
            if not table_obj:
                continue

            incoming_refs = graph_b.get_incoming(
                table_obj,
                relation=RelationType.REFERENCES,
            )
            if not incoming_refs:
                continue

            if analysis["conflict_level"] in {"CRITICAL", "HIGH"}:
                conflicts.append({
                    "rule": self.RULE_ID,
                    "level": analysis["conflict_level"].lower(),
                    "message": analysis["message"],
                    "details": {
                        "table": table_obj.name,
                        "column": mod.after.name,
                        "type_change": f"{old_type} → {new_type}",
                        "incoming_references": len(incoming_refs),
                        "analysis": analysis,
                    },
                })

        return conflicts

