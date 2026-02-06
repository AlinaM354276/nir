"""
Пакет utils: вспомогательные утилиты системы анализа конфликтов.

Содержит чистые функции и классы без побочных эффектов, используемые
различными слоями системы (graph, comparison, rules, detection).

Состав пакета:
- naming: нормализация и сопоставление имён объектов БД
- type_compatibility: проверка совместимости типов данных PostgreSQL
- validators: эвристические валидаторы структурных и логических конфликтов
"""

from .naming import (
    normalize_identifier,
    normalize_schema,
    split_qualified_name,
    split_table_column,
    qualify_table,
    qualify_column,
    object_qualified_name,
    object_key,
    parse_object_key,
    guess_parent_table,
)

from .type_compatibility import (
    TypeCategory,
    TypeCompatibilityChecker,
)

from .validators import (
    attrs_signature,
    deep_equal_struct,
    detect_obvious_constraint_conflict,
)

__all__ = [
    # naming
    "normalize_identifier",
    "normalize_schema",
    "split_qualified_name",
    "split_table_column",
    "qualify_table",
    "qualify_column",
    "object_qualified_name",
    "object_key",
    "parse_object_key",
    "guess_parent_table",

    # type compatibility
    "TypeCategory",
    "TypeCompatibilityChecker",

    # validators
    "attrs_signature",
    "deep_equal_struct",
    "detect_obvious_constraint_conflict",
]

