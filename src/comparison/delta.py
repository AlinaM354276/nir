from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, List, Dict

from src.core.models import DatabaseObject
from src.graph.schema_graph import Edge


@dataclass
class ModifiedObject:
    """
    Объект с зафиксированными изменёнными атрибутами.
    """
    before: DatabaseObject
    after: DatabaseObject
    changed_fields: Set[str]


@dataclass
class Delta:

    # объекты
    objects_added: Set[DatabaseObject] = field(default_factory=set)
    objects_removed: Set[DatabaseObject] = field(default_factory=set)
    objects_modified: List[ModifiedObject] = field(default_factory=list)

    # рёбра
    edges_added: Set[Edge] = field(default_factory=set)
    edges_removed: Set[Edge] = field(default_factory=set)

    # ==========
    # ВСПОМОГАТЕЛЬНОЕ
    # ==========

    def modified_by_type(self, obj_type) -> List[ModifiedObject]:
        return [
            m for m in self.objects_modified
            if m.before.type == obj_type
        ]

    def has_removed(self, obj: DatabaseObject) -> bool:
        return obj in self.objects_removed

    def has_added(self, obj: DatabaseObject) -> bool:
        return obj in self.objects_added

    def summary(self) -> Dict[str, int]:
        return {
            "objects_added": len(self.objects_added),
            "objects_removed": len(self.objects_removed),
            "objects_modified": len(self.objects_modified),
            "edges_added": len(self.edges_added),
            "edges_removed": len(self.edges_removed),
        }
