"""
comparator.py

Сравнение двух графов схем БД и построение дельты Δ.
Реализация строго соответствует формуле из НИР (раздел 2.3.3).

Δ = (O_added, O_removed, O_modified, E_added, E_removed)
"""

from __future__ import annotations

from typing import Dict, Tuple, Set

from src.core.models import DatabaseObject
from src.graph.schema_graph import SchemaGraph, Edge
from src.comparison.delta import Delta, ModifiedObject


def _object_key(obj: DatabaseObject):
    schema = (obj.schema or "public").lower()
    name = obj.name.lower()
    obj_type = obj.type.value

    table = ""
    if obj_type == "column":
        table = str(obj.attributes.get("table", "")).lower()

    return (schema, obj_type, table, name)


class GraphComparator:
    """
    Сравнивает два графа SchemaGraph и строит Δ.
    """

    def compare(self, graph_a: SchemaGraph, graph_b: SchemaGraph) -> Delta:
        # --- Индексация вершин ---
        objs_a: Dict[Tuple[str, str, str], DatabaseObject] = {
            _object_key(o): o for o in graph_a.vertices.values()
        }
        objs_b: Dict[Tuple[str, str, str], DatabaseObject] = {
            _object_key(o): o for o in graph_b.vertices.values()
        }

        keys_a = set(objs_a.keys())
        keys_b = set(objs_b.keys())

        # --- Δ объекты ---
        added_keys = keys_b - keys_a
        removed_keys = keys_a - keys_b
        common_keys = keys_a & keys_b

        objects_added: Set[DatabaseObject] = {objs_b[k] for k in added_keys}
        objects_removed: Set[DatabaseObject] = {objs_a[k] for k in removed_keys}

        objects_modified = []

        # --- MODIFIED ---
        for k in common_keys:
            obj_a = objs_a[k]
            obj_b = objs_b[k]

            changed_fields = self._diff_attributes(obj_a, obj_b)
            if changed_fields:
                objects_modified.append(
                    ModifiedObject(
                        before=obj_a,
                        after=obj_b,
                        changed_fields=changed_fields,
                    )
                )

        # --- Рёбра ---
        edges_a: Set[Edge] = set(graph_a.edges)
        edges_b: Set[Edge] = set(graph_b.edges)

        edges_added = edges_b - edges_a
        edges_removed = edges_a - edges_b

        return Delta(
            objects_added=objects_added,
            objects_removed=objects_removed,
            objects_modified=objects_modified,
            edges_added=edges_added,
            edges_removed=edges_removed,
        )

    @staticmethod
    def _diff_attributes(
        obj_a: DatabaseObject,
        obj_b: DatabaseObject,
    ) -> Set[str]:
        """
        Определяет изменённые атрибуты объекта.
        Это реализация условия attrs(o_A) ≠ attrs(o_B).
        """
        changed: Set[str] = set()

        attrs_a = obj_a.attributes or {}
        attrs_b = obj_b.attributes or {}

        all_keys = set(attrs_a.keys()) | set(attrs_b.keys())

        for key in all_keys:
            if attrs_a.get(key) != attrs_b.get(key):
                changed.add(key)

        return changed

