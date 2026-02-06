"""
Пользовательские исключения системы обнаружения конфликтов миграций.
"""

from __future__ import annotations
from typing import Optional, Dict, Any


class ConflictDetectorError(Exception):
    """Базовое исключение для системы обнаружения конфликтов."""

    def __init__(self, message: str, code: str = "UNKNOWN", details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict:
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }


class ParsingError(ConflictDetectorError):
    """Ошибка парсинга SQL."""

    def __init__(self, message: str, sql_fragment: str = None, position: int = None):
        details: Dict[str, Any] = {}
        if sql_fragment:
            details["sql_fragment"] = sql_fragment
        if position is not None:
            details["position"] = position
        super().__init__(message, "PARSING_ERROR", details)


class SyntaxError(ParsingError):
    """Синтаксическая ошибка в SQL."""

    def __init__(self, message: str, expected: str = None, found: str = None):
        details: Dict[str, Any] = {}
        if expected:
            details["expected"] = expected
        if found:
            details["found"] = found
        super().__init__(message, sql_fragment=None, position=None)
        self.code = "SYNTAX_ERROR"
        self.details.update(details)


class UnsupportedFeatureError(ParsingError):
    """Неподдерживаемая функция PostgreSQL."""

    def __init__(self, feature: str, version: str = None):
        message = f"Неподдерживаемая функция: {feature}"
        details: Dict[str, Any] = {"feature": feature}
        if version:
            details["version"] = version
            message += f" (требуется PostgreSQL {version}+)"
        super().__init__(message, sql_fragment=None, position=None)
        self.code = "UNSUPPORTED_FEATURE"
        self.details.update(details)


class GraphBuildingError(ConflictDetectorError):
    """Ошибка построения графа зависимостей."""

    def __init__(self, message: str, object_type: str = None, object_name: str = None):
        details: Dict[str, Any] = {}
        if object_type:
            details["object_type"] = object_type
        if object_name:
            details["object_name"] = object_name
        super().__init__(message, "GRAPH_BUILDING_ERROR", details)


class CircularDependencyError(GraphBuildingError):
    """Обнаружена циклическая зависимость."""

    def __init__(self, cycle: list, objects: dict = None):
        message = f"Обнаружена циклическая зависимость: {' -> '.join(cycle)}"
        details: Dict[str, Any] = {"cycle": cycle}
        if objects:
            details["objects"] = objects
        super().__init__(message, object_type=None, object_name=None)
        self.code = "CIRCULAR_DEPENDENCY"
        self.details.update(details)


class ComparisonError(ConflictDetectorError):
    """Ошибка сравнения схем."""

    def __init__(self, message: str, schema_a: str = None, schema_b: str = None):
        details: Dict[str, Any] = {}
        if schema_a:
            details["schema_a"] = schema_a
        if schema_b:
            details["schema_b"] = schema_b
        super().__init__(message, "COMPARISON_ERROR", details)


class VertexMatchingError(ComparisonError):
    """
    Ошибка сопоставления вершин графов.

    Совместимость:
    - поддерживает старый вызов VertexMatchingError(vertex_a=..., vertex_b=...)
    - поддерживает новый вызов VertexMatchingError(message="...")
    """

    def __init__(
        self,
        message: str = None,
        vertex_a: dict = None,
        vertex_b: dict = None,
        details: Optional[dict] = None,
    ):
        if message is None:
            message = "Не удалось сопоставить вершины графов"

        det: Dict[str, Any] = {}
        if details:
            det.update(details)
        if vertex_a:
            det["vertex_a"] = vertex_a
        if vertex_b:
            det["vertex_b"] = vertex_b

        super().__init__(message)
        self.code = "VERTEX_MATCHING_ERROR"
        self.details.update(det)


class RuleApplicationError(ConflictDetectorError):
    """Ошибка применения правила обнаружения конфликтов."""

    def __init__(self, message: str, rule_id: str = None, rule_name: str = None):
        details: Dict[str, Any] = {}
        if rule_id:
            details["rule_id"] = rule_id
        if rule_name:
            details["rule_name"] = rule_name
        super().__init__(message, "RULE_APPLICATION_ERROR", details)


class ConfigurationError(ConflictDetectorError):
    """Ошибка конфигурации системы."""

    def __init__(self, message: str, config_key: str = None, config_value: str = None):
        details: Dict[str, Any] = {}
        if config_key:
            details["config_key"] = config_key
        if config_value:
            details["config_value"] = config_value
        super().__init__(message, "CONFIGURATION_ERROR", details)


class ValidationError(ConflictDetectorError):
    """Ошибка валидации входных данных."""

    def __init__(self, message: str, field: str = None, value: str = None):
        details: Dict[str, Any] = {}
        if field:
            details["field"] = field
        if value:
            details["value"] = value
        super().__init__(message, "VALIDATION_ERROR", details)


class SchemaValidationError(ValidationError):
    """Ошибка валидации схемы базы данных."""

    def __init__(self, message: str, table_name: str = None, column_name: str = None):
        details: Dict[str, Any] = {}
        if table_name:
            details["table_name"] = table_name
        if column_name:
            details["column_name"] = column_name
        super().__init__(message)
        self.code = "SCHEMA_VALIDATION_ERROR"
        self.details.update(details)


class FileSystemError(ConflictDetectorError):
    """Ошибка файловой системы."""

    def __init__(self, message: str, file_path: str = None, operation: str = None):
        details: Dict[str, Any] = {}
        if file_path:
            details["file_path"] = file_path
        if operation:
            details["operation"] = operation
        super().__init__(message, "FILESYSTEM_ERROR", details)


# НЕ переопределяем встроенные FileNotFoundError/PermissionError — даём уникальные имена
class ConflictFileNotFoundError(FileSystemError):
    """Файл не найден."""

    def __init__(self, file_path: str):
        super().__init__(f"Файл не найден: {file_path}", file_path, "read")


class ConflictPermissionError(FileSystemError):
    """Ошибка прав доступа."""

    def __init__(self, file_path: str, required_permission: str):
        details = {"required_permission": required_permission}
        super().__init__(
            f"Нет прав доступа к файлу {file_path} (требуется: {required_permission})",
            file_path,
            "access",
        )
        self.details.update(details)


class CacheError(ConflictDetectorError):
    """Ошибка кэширования."""

    def __init__(self, message: str, cache_key: str = None, cache_size: int = None):
        details: Dict[str, Any] = {}
        if cache_key:
            details["cache_key"] = cache_key
        if cache_size is not None:
            details["cache_size"] = cache_size
        super().__init__(message, "CACHE_ERROR", details)


class TimeoutError(ConflictDetectorError):
    """Таймаут выполнения операции."""

    def __init__(self, message: str, operation: str = None, timeout_seconds: int = None):
        details: Dict[str, Any] = {}
        if operation:
            details["operation"] = operation
        if timeout_seconds is not None:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, "TIMEOUT_ERROR", details)


class Warning(ConflictDetectorError):
    """Предупреждение (не фатальная ошибка)."""

    def __init__(self, message: str, code: str = "WARNING", details: dict = None):
        super().__init__(message, code, details)


def handle_exception(exception: Exception) -> dict:
    if isinstance(exception, ConflictDetectorError):
        return exception.to_dict()
    return {
        "error": str(exception),
        "code": "UNKNOWN_ERROR",
        "details": {
            "exception_type": exception.__class__.__name__,
        },
    }


def is_fatal_error(exception: Exception) -> bool:
    return not isinstance(exception, Warning)
