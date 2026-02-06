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
    Реализует полный конвейер обработки из НИРа.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        self.parser = SQLParser()
        self.normalizer = SQLNormalizer()
        self.graph_builder = GraphBuilder()
        self.comparator = GraphComparator()

        # Реестр правил
        self.registry = RuleRegistry(self.config.get("rules", {}))
        self.registry.register_rules(DEFAULT_RULES)

        # Статистика выполнения (float — время в секундах)
        self.stats: Dict[str, float] = {
            "parsing_time": 0.0,
            "graph_building_time": 0.0,
            "comparison_time": 0.0,
            "rule_application_time": 0.0,
            "total_time": 0.0,
        }

    # ==========================================================
    # API
    # ==========================================================

    def detect(self, sql_a: str, sql_b: str) -> Dict[str, Any]:
        """
        Основной метод обнаружения конфликтов.
        """
        start_time = time.time()

        try:
            # ---------- Этап 1: парсинг ----------
            t0 = time.time()
            objects_a = self._parse_schema(sql_a)
            objects_b = self._parse_schema(sql_b)
            self.stats["parsing_time"] = time.time() - t0

            # ---------- Этап 2: построение графов ----------
            t0 = time.time()
            graph_a = self.graph_builder.build_from_objects(objects_a, "schema_a")
            graph_b = self.graph_builder.build_from_objects(objects_b, "schema_b")
            self.stats["graph_building_time"] = time.time() - t0

            # ---------- Этап 3: сравнение ----------
            t0 = time.time()
            delta = self.comparator.compare(graph_a, graph_b)
            self.stats["comparison_time"] = time.time() - t0

            # ---------- Этап 4: правила ----------
            t0 = time.time()
            result = self.registry.apply_all(delta, graph_a, graph_b)
            self.stats["rule_application_time"] = time.time() - t0

            self.stats["total_time"] = time.time() - start_time

            return self._generate_report(result, delta, graph_a, graph_b)

        except Exception as e:
            # Финальный защитный слой
            return self._generate_error_report(str(e))

    # ==========================================================
    # ВНУТРЕННИЕ МЕТОДЫ
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
                objects.extend(self.parser.parse_to_objects(stmt))

        return objects

    def _generate_report(
        self,
        result: Dict[str, Any],
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> Dict[str, Any]:
        """
        Генерирует финальный отчёт.
        """

        conflicts: List[Dict[str, Any]] = result.get("conflicts", []) or []
        statistics: List[Dict[str, Any]] = result.get("statistics", []) or []
        summary: Dict[str, Any] = result.get("summary", {}) or {}

        max_conflicts = int(self.config.get("max_conflicts", 100))
        conflicts_limited = conflicts[:max_conflicts]

        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "tool": "PostgreSQL Migration Conflict Detector",
                "version": "1.0.0",
            },

            "summary": {
                "has_conflicts": bool(conflicts),
                "has_critical_conflicts": any(
                    c.get("level") == "critical" for c in conflicts
                ),
                "total_conflicts": len(conflicts),
                "merge_blocked": any(
                    c.get("level") == "critical" for c in conflicts
                ),
            },

            # основной список
            "conflicts": conflicts_limited,

            # структурированная форма
            "conflicts_structured": {
                "list": conflicts_limited,
                "total": len(conflicts),
                "truncated": len(conflicts) > max_conflicts,
                # агрегаты опущены намеренно (statistics = list)
                "by_rule": {},
                "by_level": {},
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
                "has_conflicts": False,
                "has_critical_conflicts": False,
                "total_conflicts": 0,
                "merge_blocked": True,
            },
            "conflicts": [conflict],
            "conflicts_structured": {
                "list": [conflict],
                "total": 1,
            },
        }
