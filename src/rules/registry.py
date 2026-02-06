"""
Реестр правил обнаружения конфликтов.
Управляет регистрацией, конфигурацией и применением правил.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from .base import BaseRule, ConflictLevel
from ..graph.schema_graph import SchemaGraph
from ..comparison.delta import Delta


class RuleRegistry:
    """
    Реестр для управления правилами обнаружения конфликтов.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._rules: Dict[str, BaseRule] = {}
        self._rule_classes: Dict[str, Type[BaseRule]] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        defaults = {
            "rule_order": "by_id",  # by_id | by_criticality | custom
            "default_conflict_level": ConflictLevel.MEDIUM.value,
            "max_total_conflicts": 1000,
            "enable_statistics": True,
        }
        for k, v in defaults.items():
            self.config.setdefault(k, v)

    def register_rule(self, rule_class: Type[BaseRule], rule_config: Optional[Dict[str, Any]] = None) -> None:
        if not issubclass(rule_class, BaseRule):
            raise TypeError(f"{rule_class} должен быть подклассом BaseRule")

        rule_id = rule_class.RULE_ID
        config = rule_config or {}

        # глобальная конфигурация под правило
        if rule_id in self.config.get("rules", {}):
            config = {**self.config["rules"][rule_id], **config}

        instance = rule_class(config)
        if not instance.validate():
            raise ValueError(f"Правило {rule_id} не прошло валидацию")

        self._rules[rule_id] = instance
        self._rule_classes[rule_id] = rule_class

    def register_rules(self, rules: List[Type[BaseRule]], configs: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        configs = configs or {}
        for rc in rules:
            self.register_rule(rc, configs.get(rc.RULE_ID, {}))

    def get_rule(self, rule_id: str) -> Optional[BaseRule]:
        return self._rules.get(rule_id)

    def get_enabled_rules(self) -> List[BaseRule]:
        return [r for r in self._rules.values() if r.is_enabled()]

    def _order_rules(self, rules: List[BaseRule]) -> List[BaseRule]:
        order = self.config.get("rule_order", "by_id")

        if order == "by_id":
            return sorted(rules, key=lambda r: r.RULE_ID)

        if order == "by_criticality":
            priority = {
                ConflictLevel.CRITICAL.value: 0,
                ConflictLevel.HIGH.value: 1,
                ConflictLevel.MEDIUM.value: 2,
                ConflictLevel.LOW.value: 3,
            }
            return sorted(rules, key=lambda r: priority.get(r.config.get("level", r.DEFAULT_LEVEL.value), 99))

        # custom: порядок задаётся списком ids
        if order == "custom":
            custom = self.config.get("custom_order", [])
            index = {rid: i for i, rid in enumerate(custom)}
            return sorted(rules, key=lambda r: index.get(r.RULE_ID, 10_000))

        return rules

    def apply_all(self, delta: Delta, graph_a: SchemaGraph, graph_b: SchemaGraph) -> Dict[str, Any]:
        if not self._rules:
            return {"conflicts": [], "statistics": [], "summary": {"total_conflicts": 0}}

        enabled = self.get_enabled_rules()
        ordered = self._order_rules(enabled)

        all_conflicts: List[Dict[str, Any]] = []
        stats: List[Dict[str, Any]] = []

        for rule in ordered:
            try:
                raw = rule.apply(delta, graph_a, graph_b)

                # --- НОРМАЛИЗАЦИЯ ВЫХОДА ПРАВИЛА ---
                if raw is None:
                    raw = []
                elif isinstance(raw, list):
                    # оставляем только dict
                    raw = [c for c in raw if isinstance(c, dict)]
                else:
                    raw = []

                processed = rule.post_process_conflicts(raw)

                if not isinstance(processed, list):
                    processed = []

                for c in processed:
                    c["rule_info"] = rule.get_info()

                all_conflicts.extend(processed)

                stats.append({
                    "rule_id": rule.RULE_ID,
                    "rule_name": rule.RULE_NAME,
                    "applied": True,
                    "conflicts_found": len(processed),
                    "details": {
                        "total_raw": len(raw),
                        "total_reported": len(processed),
                    }
                })
            except Exception as e:
                stats.append({
                    "rule_id": rule.RULE_ID,
                    "rule_name": rule.RULE_NAME,
                    "applied": False,
                    "error": str(e),
                    "conflicts_found": 0
                })

        original_total = len(all_conflicts)
        max_total = int(self.config.get("max_total_conflicts", 1000))

        trimmed = all_conflicts
        if original_total > max_total:
            trimmed = all_conflicts[:max_total]
            trimmed.append({
                "rule": "SYSTEM",
                "rule_name": "System limiter",
                "level": ConflictLevel.LOW.value,
                "message": f"Обнаружено {original_total} конфликтов. Показаны первые {max_total}.",
                "details": {
                    "total_conflicts": original_total,
                    "reported_conflicts": max_total
                }
            })

        summary = {
            "total_conflicts": len(trimmed),
            "total_rules": len(self._rules),
            "enabled_rules": len(enabled),
        }

        return {"conflicts": trimmed, "statistics": stats, "summary": summary}
