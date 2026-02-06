"""
Модуль для сопоставления вершин графов при сравнении.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple, Set
from difflib import SequenceMatcher
import hashlib

from ..graph.schema_graph import SchemaGraph
from ..core.models import DatabaseObject, ObjectType
from ..core.exceptions import VertexMatchingError


@dataclass(frozen=True)
class MatchResult:
    """
    Результат сопоставления:
    - pairs: M_paired
    - unique_a: V_unique_A
    - unique_b: V_unique_B
    """
    pairs: List[Tuple[int, int]]
    unique_a: List[int]
    unique_b: List[int]


class VertexMatcher:
    """
    Сопоставляет вершины двух графов.

    Базовый прототип использует детерминированное сопоставление по ключу.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # По умолчанию: коллизии ключей считаются ошибкой данных/предпосылок
        self.strict_keys: bool = bool(self.config.get("strict_keys", True))

        # Экспериментальные стратегии
        self.enable_experimental: bool = bool(self.config.get("enable_experimental_matching", False))

        # Порог для структурного/именного сходства (если включено)
        self.similarity_threshold: float = float(self.config.get("similarity_threshold", 0.8))

        self._cache: Dict[str, Any] = {}

    # -------------------------
    # основной метод
    # -------------------------

    def match(self, graph_a: SchemaGraph, graph_b: SchemaGraph) -> MatchResult:
        """
        Главный метод сопоставления.

        В строгом режиме (по умолчанию): только match_by_key.
        В экспериментальном режиме: может дополнять соответствия эвристикой.
        """
        pairs = self.match_by_key_pairs(graph_a, graph_b)

        paired_a = {a for a, _ in pairs}
        paired_b = {b for _, b in pairs}

        unique_a = sorted(set(graph_a.vertices.keys()) - paired_a)
        unique_b = sorted(set(graph_b.vertices.keys()) - paired_b)

        if self.enable_experimental:
            # Осторожно дополняем пары, не ломая уже найденные соответствия
            extra = self._match_experimentally(graph_a, graph_b, paired_a, paired_b)
            pairs.extend(extra)

            paired_a = {a for a, _ in pairs}
            paired_b = {b for _, b in pairs}
            unique_a = sorted(set(graph_a.vertices.keys()) - paired_a)
            unique_b = sorted(set(graph_b.vertices.keys()) - paired_b)

        return MatchResult(pairs=pairs, unique_a=unique_a, unique_b=unique_b)

    def match_by_key_pairs(self, graph_a: SchemaGraph, graph_b: SchemaGraph) -> List[Tuple[int, int]]:
        """
        сопоставление по ключу эквивалентности.
        Возвращает список пар (id_a, id_b) = M_paired.
        """
        key_to_ids_a = self._build_key_mapping(graph_a)
        key_to_ids_b = self._build_key_mapping(graph_b)

        pairs: List[Tuple[int, int]] = []

        common_keys = set(key_to_ids_a.keys()) & set(key_to_ids_b.keys())
        for key in common_keys:
            ids_a = key_to_ids_a[key]
            ids_b = key_to_ids_b[key]

            if self.strict_keys and (len(ids_a) != 1 or len(ids_b) != 1):
                raise VertexMatchingError(
                    f"Коллизия ключа '{key}': A имеет {ids_a}, B имеет {ids_b}. "
                    f"В строгом режиме (НИР) ключ должен быть уникальным."
                )

            # В нестрогом режиме сопоставляем попарно минимальное количество
            for id_a, id_b in zip(sorted(ids_a), sorted(ids_b)):
                pairs.append((id_a, id_b))

        pairs.sort(key=lambda p: (p[0], p[1]))
        return pairs

    def match_by_key(self, graph_a: SchemaGraph, graph_b: SchemaGraph) -> Dict[int, int]:
        """
        Совместимость с прошлым интерфейсом: возвращает mapping id_A -> id_B.
        Если коллизии и strict_keys=True — бросит VertexMatchingError.
        """
        pairs = self.match_by_key_pairs(graph_a, graph_b)
        mapping: Dict[int, int] = {}
        for a, b in pairs:
            mapping[a] = b
        return mapping

    # -------------------------
    # Ключ эквивалентности (должен совпадать с comparator.py)
    # -------------------------

    def _build_key_mapping(self, graph: SchemaGraph) -> Dict[str, List[int]]:
        """
        Возвращает key -> [vertex_id, ...].
        Так мы явно видим коллизии и не теряем вершины.
        """
        mapping: Dict[str, List[int]] = {}
        for vertex_id, vertex in graph.vertices.items():
            key = self._vertex_key(vertex)
            mapping.setdefault(key, []).append(vertex_id)
        return mapping

    def _vertex_key(self, vertex: DatabaseObject) -> str:
        """
        Детерминированный ключ эквивалентности.

        Совместим с GraphComparator._vertex_key():
        - базовый ключ: type:schema:name
        - для COLUMN добавляется table (иначе неоднозначность)
        - для ограничений добавляется table/from_table (унификация)
        """
        base = f"{vertex.type.value}:{vertex.schema}:{vertex.name}"

        if vertex.type == ObjectType.COLUMN:
            table = vertex.attributes.get("table")
            if table:
                return f"{base}:table:{table}"

        if vertex.type in (ObjectType.PRIMARY_KEY, ObjectType.UNIQUE_CONSTRAINT, ObjectType.FOREIGN_KEY):
            table = vertex.attributes.get("table") or vertex.attributes.get("from_table")
            if table:
                return f"{base}:table:{table}"

        return base

    # -------------------------
    # Экспериментальные стратегии (выключены по умолчанию)
    # -------------------------

    def _match_experimentally(
        self,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
        already_a: Set[int],
        already_b: Set[int],
    ) -> List[Tuple[int, int]]:
        """
        Осторожное дополнение соответствий, если enable_experimental_matching=True.
        это расширение НИР.
        """
        # Список кандидатов: только не сопоставленные вершины одинакового типа
        by_type_a = self._group_unmatched_by_type(graph_a, already_a)
        by_type_b = self._group_unmatched_by_type(graph_b, already_b)

        extra_pairs: List[Tuple[int, int]] = []

        for t, vertices_a in by_type_a.items():
            vertices_b = by_type_b.get(t, [])
            if not vertices_b:
                continue

            matched_b: Set[int] = set()

            for id_a, v_a in vertices_a:
                best_id_b: Optional[int] = None
                best_sim = 0.0

                for id_b, v_b in vertices_b:
                    if id_b in matched_b:
                        continue
                    sim = self._calculate_vertex_similarity(v_a, v_b)
                    if sim >= self.similarity_threshold and sim > best_sim:
                        best_sim = sim
                        best_id_b = id_b

                if best_id_b is not None:
                    extra_pairs.append((id_a, best_id_b))
                    matched_b.add(best_id_b)

        extra_pairs.sort(key=lambda p: (p[0], p[1]))
        return extra_pairs

    def _group_unmatched_by_type(
        self, graph: SchemaGraph, already: Set[int]
    ) -> Dict[str, List[Tuple[int, DatabaseObject]]]:
        groups: Dict[str, List[Tuple[int, DatabaseObject]]] = {}
        for vertex_id, vertex in graph.vertices.items():
            if vertex_id in already:
                continue
            groups.setdefault(vertex.type.value, []).append((vertex_id, vertex))
        return groups

    def _calculate_vertex_similarity(self, a: DatabaseObject, b: DatabaseObject) -> float:
        if a.type != b.type:
            return 0.0

        name_sim = self._name_similarity(a.name, b.name)
        attr_sim = self._attributes_similarity(a.attributes or {}, b.attributes or {})

        weights = self.config.get("similarity_weights", {"name": 0.6, "attributes": 0.4})
        return float(weights.get("name", 0.6)) * name_sim + float(weights.get("attributes", 0.4)) * attr_sim

    @staticmethod
    def _name_similarity(x: str, y: str) -> float:
        return SequenceMatcher(None, x.lower(), y.lower()).ratio()

    def _attributes_similarity(self, ax: Dict[str, Any], ay: Dict[str, Any]) -> float:
        if not ax and not ay:
            return 1.0
        if not ax or not ay:
            return 0.0

        keys_all = set(ax.keys()) | set(ay.keys())
        keys_common = set(ax.keys()) & set(ay.keys())
        if not keys_all:
            return 0.0

        score = 0.0
        for k in keys_common:
            vx, vy = ax[k], ay[k]
            if vx == vy:
                score += 1.0
            elif isinstance(vx, str) and isinstance(vy, str):
                score += self._name_similarity(vx, vy)

        return score / float(len(keys_all))

    # Хэш-стратегия оставлена как экспериментальная
    def match_by_content_hash(self, graph_a: SchemaGraph, graph_b: SchemaGraph) -> Dict[int, int]:
        if not self.enable_experimental:
            raise VertexMatchingError("match_by_content_hash отключён: включи enable_experimental_matching=True")
        map_a = self._build_hash_mapping(graph_a)
        map_b = self._build_hash_mapping(graph_b)
        mapping: Dict[int, int] = {}
        for h, id_a in map_a.items():
            if h in map_b:
                mapping[id_a] = map_b[h]
        return mapping

    def _build_hash_mapping(self, graph: SchemaGraph) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for vertex_id, vertex in graph.vertices.items():
            mapping[self._vertex_hash(vertex)] = vertex_id
        return mapping

    @staticmethod
    def _vertex_hash(v: DatabaseObject) -> str:
        content = "|".join([
            v.type.value,
            v.schema,
            v.name,
            str(sorted((v.attributes or {}).items()))
        ])
        return hashlib.md5(content.encode("utf-8")).hexdigest()
