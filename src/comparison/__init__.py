# __init__.py для пакета comparison
"""
comparison — модуль сравнения схем (раздел 2.3).

Экспортирует:
- GraphComparator: сравнение графов и построение Δ
- Delta: структура различий Δ = (O_added, O_removed, O_modified, E_added, E_removed, E_modified)
- VertexMatcher / MatchResult: сопоставление вершин (этап 2.3.1)
"""

from .comparator import GraphComparator
from .delta import Delta
from .matcher import VertexMatcher, MatchResult

__all__ = [
    "GraphComparator",
    "Delta",
    "VertexMatcher",
    "MatchResult",
]

__version__ = "0.1.0"

