"""
Координатор всего процесса обнаружения конфликтов.
"""

from typing import Dict, List, Any, Optional
import time
from datetime import datetime

from src.parser import SQLParser, SQLNormalizer
from src.graph import GraphBuilder, SchemaGraph
from src.comparison import GraphComparator, Delta
from src.rules import RuleRegistry, DEFAULT_RULES
from src.core.models import DatabaseObject


class MigrationConflictDetector:
    """
    Основной класс для обнаружения конфликтов миграций.
    Реализует полный конвейер обработки.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        self.parser = SQLParser()
        self.normalizer = SQLNormalizer()
        self.graph_builder = GraphBuilder()
        self.comparator = GraphComparator()

        self.registry = RuleRegistry(self.config.get("rules", {}))
        self.registry.register_rules(DEFAULT_RULES)

        self.stats: Dict[str, float] = {
            "parsing_time": 0.0,
            "graph_building_time": 0.0,
            "comparison_time": 0.0,
            "rule_application_time": 0.0,
            "total_time": 0.0,
        }

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def detect(self, sql_a: str, sql_b: str) -> Dict[str, Any]:
        """
        Основной метод обнаружения конфликтов.
        """

        total_start = time.perf_counter()

        try:
            # ---------- Этап 1: Парсинг ----------
            t0 = time.perf_counter()
            objects_a = self._parse_schema(sql_a)
            objects_b = self._parse_schema(sql_b)
            self.stats["parsing_time"] = time.perf_counter() - t0

            # ---------- Этап 2: Построение графов ----------
            t0 = time.perf_counter()
            graph_a = self.graph_builder.build_from_objects(objects_a, "schema_a")
            graph_b = self.graph_builder.build_from_objects(objects_b, "schema_b")
            self.stats["graph_building_time"] = time.perf_counter() - t0

            # ---------- Этап 3: Сравнение ----------
            t0 = time.perf_counter()
            delta = self.comparator.compare(graph_a, graph_b)
            self.stats["comparison_time"] = time.perf_counter() - t0

            # ---------- Этап 4: Применение правил ----------
            t0 = time.perf_counter()
            result = self.registry.apply_all(delta, graph_a, graph_b)
            self.stats["rule_application_time"] = time.perf_counter() - t0

            self.stats["total_time"] = time.perf_counter() - total_start

            return self._generate_report(result, delta, graph_a, graph_b)

        except Exception as e:
            return self._generate_error_report(str(e))

    # ==========================================================
    # INTERNAL METHODS
    # ==========================================================

    def _parse_schema(self, sql_text: str) -> List[DatabaseObject]:
        """
        Парсит SQL-схему в список объектов БД.
        """

        normalized = self.normalizer.normalize(sql_text)
        statements = self.normalizer.split_statements(normalized)

        objects: List[DatabaseObject] = []
        for stmt in statements:
            if self.normalizer.is_ddl_statement(stmt):
                parsed = self.parser.parse_to_objects(stmt)
                if parsed:
                    objects.extend(parsed)

        return objects

    # ==========================================================
    # REPORT GENERATION
    # ==========================================================

    def _generate_report(
        self,
        result: Dict[str, Any],
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> Dict[str, Any]:

        conflicts: List[Dict[str, Any]] = result.get("conflicts", []) or []
        statistics: List[Dict[str, Any]] = result.get("statistics", []) or []
        summary_from_registry: Dict[str, Any] = result.get("summary", {}) or {}

        max_conflicts = int(self.config.get("max_conflicts", 100))
        conflicts_limited = conflicts[:max_conflicts]

        # --- Нормализация уровней ---
        for c in conflicts:
            if "level" in c:
                c["level"] = str(c["level"]).lower()

        # --- Агрегация уровней ---
        level_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        for c in conflicts:
            lvl = c.get("level")
            if lvl in level_counts:
                level_counts[lvl] += 1

        has_critical = level_counts["critical"] > 0

        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tool": "PostgreSQL Migration Conflict Detector",
                "version": "1.0.0",
            },

            "summary": {
                "has_conflicts": len(conflicts) > 0,
                "has_critical_conflicts": has_critical,
                "total_conflicts": len(conflicts),
                "critical_conflicts": level_counts["critical"],
                "high_conflicts": level_counts["high"],
                "medium_conflicts": level_counts["medium"],
                "low_conflicts": level_counts["low"],
                "merge_blocked": has_critical,
            },

            "conflicts": conflicts_limited,

            "conflicts_structured": {
                "list": conflicts_limited,
                "total": len(conflicts),
                "truncated": len(conflicts) > max_conflicts,
                "by_rule": self._aggregate_by_rule(conflicts),
                "by_level": level_counts,
            },

            "analysis": {
                "delta": delta.summary() if hasattr(delta, "summary") else {},
                "graphs": {
                    "schema_a": {
                        "vertices": len(graph_a.vertices),
                        "edges": len(graph_a.edges),
                    },
                    "schema_b": {
                        "vertices": len(graph_b.vertices),
                        "edges": len(graph_b.edges),
                    },
                },
                "rules_applied": len(statistics),
            },

            "performance": self.stats,
        }

    def _generate_error_report(self, error_message: str) -> Dict[str, Any]:
        """
        Генерирует отчёт об ошибке выполнения.
        Ошибка всегда считается критической.
        """

        conflict = {
            "rule": "SYSTEM",
            "level": "critical",
            "message": f"Ошибка обработки: {error_message}",
            "details": {"error_type": "system_error"},
        }

        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "status": "ERROR",
            },
            "error": {
                "message": error_message,
                "type": "ProcessingError",
            },
            "summary": {
                "has_conflicts": True,
                "has_critical_conflicts": True,
                "total_conflicts": 1,
                "critical_conflicts": 1,
                "high_conflicts": 0,
                "medium_conflicts": 0,
                "low_conflicts": 0,
                "merge_blocked": True,
            },
            "conflicts": [conflict],
            "conflicts_structured": {
                "list": [conflict],
                "total": 1,
                "truncated": False,
                "by_rule": {"SYSTEM": 1},
                "by_level": {"critical": 1},
            },
            "analysis": {},
            "performance": {},
        }

    # ==========================================================
    # HELPERS
    # ==========================================================

    def _aggregate_by_rule(self, conflicts: List[Dict[str, Any]]) -> Dict[str, int]:
        by_rule: Dict[str, int] = {}
        for c in conflicts:
            rule = c.get("rule", "UNKNOWN")
            by_rule[rule] = by_rule.get(rule, 0) + 1
        return by_rule

