"""
Базовый класс для правил обнаружения конфликтов.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from ..graph.schema_graph import SchemaGraph
from ..comparison.delta import Delta


class ConflictLevel(Enum):
    """Уровни критичности конфликтов."""
    CRITICAL = "critical"  # Блокирует слияние
    HIGH = "high"          # Высокий риск, требует внимания
    MEDIUM = "medium"      # Средний риск, рекомендуется проверить
    LOW = "low"            # Низкий риск, информационное сообщение


class BaseRule(ABC):
    """
    Абстрактный базовый класс для всех правил обнаружения конфликтов.

    Каждое правило R_i представляет собой функцию:
    R_i(Δ, G_A, G_B) → {C_i} или ∅
    где {C_i} - множество обнаруженных конфликтов типа i.
    """

    RULE_ID: str = ""
    RULE_NAME: str = ""
    RULE_DESCRIPTION: str = ""
    DEFAULT_LEVEL: ConflictLevel = ConflictLevel.MEDIUM

    REQUIRES_GRAPH_ANALYSIS: bool = True
    REQUIRES_TYPE_COMPATIBILITY: bool = False
    REQUIRES_SEMANTIC_ANALYSIS: bool = False

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._init_config()

    def _init_config(self) -> None:
        defaults = {
            "enabled": True,
            "level": self.DEFAULT_LEVEL.value,
            "max_reports_per_rule": 100,
            "include_details": True,
            "generate_recommendations": True,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    @abstractmethod
    def apply(self, delta: Delta, graph_a: SchemaGraph, graph_b: SchemaGraph) -> List[Dict[str, Any]]:
        """
        Применяет правило к Δ и графам.
        Возвращает список конфликтов (list[dict]).
        """
        raise NotImplementedError

    def post_process_conflicts(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Унификация и постобработка: лимиты, level/rule/rule_name.
        """
        if not conflicts or not isinstance(conflicts, list):
            return []

        # оставляем только корректные dict
        normalized = [c for c in conflicts if isinstance(c, dict)]
        if not normalized:
            return []

        include_details = bool(self.config.get("include_details", True))
        default_level = self.config.get("level", self.DEFAULT_LEVEL.value)

        original_total = len(normalized)
        max_reports = int(self.config.get("max_reports_per_rule", 100))

        trimmed = normalized
        trimmed_flag = False
        if original_total > max_reports:
            trimmed = normalized[:max_reports]
            trimmed_flag = True

        # унификация полей
        for c in trimmed:
            c.setdefault("rule", self.RULE_ID)
            c.setdefault("rule_name", self.RULE_NAME)
            c.setdefault("level", default_level)

            if not include_details and "details" in c:
                c.pop("details", None)

        if trimmed_flag:
            trimmed.append({
                "rule": self.RULE_ID,
                "rule_name": self.RULE_NAME,
                "level": ConflictLevel.LOW.value,
                "message": f"Обнаружено {original_total} конфликтов. Показаны первые {max_reports}.",
                "details": {
                    "total_conflicts": original_total,
                    "reported_conflicts": max_reports,
                    "rule": self.RULE_ID
                }
            })

        return trimmed

    def get_info(self) -> Dict[str, Any]:
        return {
            "id": self.RULE_ID,
            "name": self.RULE_NAME,
            "description": self.RULE_DESCRIPTION,
            "default_level": self.DEFAULT_LEVEL.value,
            "requires_graph_analysis": self.REQUIRES_GRAPH_ANALYSIS,
            "requires_type_compatibility": self.REQUIRES_TYPE_COMPATIBILITY,
            "requires_semantic_analysis": self.REQUIRES_SEMANTIC_ANALYSIS,
            "config": self.config,
            "class_name": self.__class__.__name__,
        }

    def is_enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def enable(self) -> None:
        self.config["enabled"] = True

    def disable(self) -> None:
        self.config["enabled"] = False

    def set_level(self, level: ConflictLevel) -> None:
        self.config["level"] = level.value

    def validate(self) -> bool:
        return bool(self.RULE_ID and self.RULE_NAME and self.RULE_DESCRIPTION)

    def __str__(self) -> str:
        enabled = "✓" if self.is_enabled() else "✗"
        return f"[{enabled}] {self.RULE_ID}: {self.RULE_NAME}"

    def __repr__(self) -> str:
        return f"<Rule {self.RULE_ID}: {self.__class__.__name__}>"

