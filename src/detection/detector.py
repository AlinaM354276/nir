# src/detection/detector.py

from typing import Dict, Any, Optional

from src.comparison.delta import Delta
from src.graph.schema_graph import SchemaGraph
from src.rules import RuleRegistry, DEFAULT_RULES


class ConflictDetector:
    """
    Фасад детектирования конфликтов.
    Делегирует применение правил в RuleRegistry.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.registry = RuleRegistry(self.config.get("rules", {}))
        self.registry.register_rules(DEFAULT_RULES)

    def detect(
        self,
        delta: Delta,
        graph_a: SchemaGraph,
        graph_b: SchemaGraph,
    ) -> Dict[str, Any]:
        return self.registry.apply_all(delta, graph_a, graph_b)
