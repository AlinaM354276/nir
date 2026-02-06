# src/graph/schema_graph.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Set, Optional, List
from src.core.models import DatabaseObject, RelationType, ObjectType


@dataclass(frozen=True)
class Edge:
    src: int
    dst: int
    relation: RelationType


class SchemaGraph:
    """
    Ориентированный помеченный граф объектов схемы БД.
    """

    def __init__(self, name: str = "") -> None:
        self.name = name
        self._next_id: int = 1
        self.vertices: Dict[int, DatabaseObject] = {}
        self.edges: Set[Edge] = set()

    # ==========
    # ВЕРШИНЫ
    # ==========

    def add_vertex(self, obj: DatabaseObject) -> int:
        obj.id = self._next_id
        self.vertices[self._next_id] = obj
        self._next_id += 1
        return obj.id

    def get_vertex(self, obj_id: int) -> Optional[DatabaseObject]:
        return self.vertices.get(obj_id)

    def has_vertex(self, obj_id: int) -> bool:
        return obj_id in self.vertices

    # ==========
    # РЁБРА
    # ==========

    def add_edge(
        self,
        src_id: int,
        dst_id: int,
        relation: RelationType,
        _attrs: Optional[dict] = None,  # attrs не участвуют в модели, но API совместим
    ) -> None:
        if src_id not in self.vertices or dst_id not in self.vertices:
            raise ValueError("Both vertices must exist before adding an edge")

        self.edges.add(Edge(src=src_id, dst=dst_id, relation=relation))

    def get_outgoing(
        self,
        obj: DatabaseObject,
        *,
        relation: Optional[RelationType] = None,
    ) -> Set[Edge]:
        return {
            e for e in self.edges
            if e.src == obj.id and (relation is None or e.relation == relation)
        }

    def get_incoming(
            self,
            obj: DatabaseObject,
            relation: Optional[RelationType] = None,
    ):
        result = []

        for edge in self.edges:
            # входящее ребро = edge.dst == obj.id
            if edge.dst != obj.id:
                continue

            if relation is None:
                result.append(edge)
            elif isinstance(relation, set):
                if edge.relation in relation:
                    result.append(edge)
            else:
                if edge.relation == relation:
                    result.append(edge)

        return result

    # ==========
    # ЗАВИСИМОСТИ
    # ==========

    def get_dependencies(
        self,
        obj: DatabaseObject,
        *,
        relations: Optional[Set[RelationType]] = None,
    ) -> Set[DatabaseObject]:
        result = set()
        for e in self.get_outgoing(obj):
            if relations is None or e.relation in relations:
                target = self.vertices.get(e.dst)
                if target:
                    result.add(target)
        return result

    def get_dependents(
        self,
        obj: DatabaseObject,
        *,
        relations: Optional[Set[RelationType]] = None,
    ) -> Set[DatabaseObject]:
        result = set()
        for e in self.get_incoming(obj):
            if relations is None or e.relation in relations:
                source = self.vertices.get(e.src)
                if source:
                    result.add(source)
        return result

    # ==========
    # ТРАНЗИТИВНОСТЬ (R7)
    # ==========

    def transitive_dependents(
        self,
        obj: DatabaseObject,
        *,
        relations: Optional[Set[RelationType]] = None,
    ) -> Set[DatabaseObject]:
        visited: Set[int] = set()
        result: Set[DatabaseObject] = set()
        queue: List[int] = [obj.id]

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            current_obj = self.vertices.get(current_id)
            if not current_obj:
                continue

            for e in self.get_incoming(current_obj):
                if relations is None or e.relation in relations:
                    src_obj = self.vertices.get(e.src)
                    if src_obj and src_obj.id not in visited:
                        result.add(src_obj)
                        queue.append(src_obj.id)

        return result

    def get_table_of_object(self, obj):
        # если это таблица — возвращаем её
        if obj.type == ObjectType.TABLE:
            return obj

        # если это колонка или constraint — ищем родительскую таблицу
        for edge in self.edges:
            if edge.src == obj.id and edge.relation == RelationType.CONTAINS:
                return self.vertices.get(edge.dst)

        return None

