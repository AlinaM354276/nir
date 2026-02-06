# __init__.py для пакета detection
"""
Пакет detection: слой детектирования конфликтов миграции.

Реализует уровень применения формальных правил к дельте Δ,
полученной при сравнении графов схем.

- ConflictDetector — фасад уровня приложения
- MigrationConflictDetector — orchestrator конвейера
- Reporter — формирование и экспорт отчётов
"""

from .detector import ConflictDetector
from .orchestrator import MigrationConflictDetector
from .reporter import Reporter

__all__ = [
    "ConflictDetector",
    "MigrationConflictDetector",
    "Reporter",
]
