"""
Матрица совместимости типов данных PostgreSQL.
Реализует отношение Compatible(T1, T2) из раздела 2.1.4 НИРа.

прикладная проверка совместимости для правила R2.
"""

from __future__ import annotations

from typing import Dict, Set, List, Tuple, Optional, Any
from enum import Enum
import re


class TypeCategory(Enum):
    """Категории типов данных."""
    INTEGER = "integer"
    DECIMAL = "decimal"
    FLOAT = "float"
    TEXT = "text"
    CHARACTER = "character"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    INTERVAL = "interval"
    JSON = "json"
    XML = "xml"
    UUID = "uuid"
    ARRAY = "array"
    COMPOSITE = "composite"
    RANGE = "range"
    GEOMETRIC = "geometric"
    NETWORK = "network"
    BIT = "bit"
    MONEY = "money"
    BYTEA = "bytea"
    OID = "oid"
    PSEUDO = "pseudo"
    UNKNOWN = "unknown"


_ARRAY_SUFFIX_RE = re.compile(r"\[\s*\]\s*$")


class TypeCompatibilityChecker:
    """
    Проверяет совместимость типов данных PostgreSQL.
    Реализует матрицу совместимости для правила R2
    """

    # Матрица совместимости типов
    COMPATIBILITY_MATRIX: Dict[str, Set[str]] = {
        # Целочисленные типы
        "SMALLINT": {"SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION"},
        "INTEGER": {"SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION"},
        "INT": {"SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION"},
        "BIGINT": {"SMALLINT", "INTEGER", "BIGINT", "NUMERIC", "DECIMAL", "REAL", "DOUBLE PRECISION"},

        # Числа с плавающей точкой
        "REAL": {"REAL", "DOUBLE PRECISION", "NUMERIC", "DECIMAL"},
        "FLOAT4": {"REAL", "DOUBLE PRECISION", "NUMERIC", "DECIMAL"},
        "DOUBLE PRECISION": {"REAL", "DOUBLE PRECISION", "NUMERIC", "DECIMAL"},
        "FLOAT8": {"REAL", "DOUBLE PRECISION", "NUMERIC", "DECIMAL"},
        "FLOAT": {"REAL", "DOUBLE PRECISION", "NUMERIC", "DECIMAL"},

        # Числа с фиксированной точкой
        "NUMERIC": {"NUMERIC", "DECIMAL", "INTEGER", "BIGINT", "SMALLINT", "REAL", "DOUBLE PRECISION"},
        "DECIMAL": {"NUMERIC", "DECIMAL", "INTEGER", "BIGINT", "SMALLINT", "REAL", "DOUBLE PRECISION"},

        # Строковые типы
        "CHAR": {"CHAR", "VARCHAR", "TEXT", "CHARACTER"},
        "CHARACTER": {"CHAR", "VARCHAR", "TEXT", "CHARACTER"},
        "VARCHAR": {"VARCHAR", "TEXT", "CHAR", "CHARACTER"},
        "TEXT": {"TEXT", "VARCHAR", "CHAR", "CHARACTER"},
        "CHARACTER VARYING": {"VARCHAR", "TEXT", "CHAR", "CHARACTER"},

        # Логические типы
        "BOOLEAN": {"BOOLEAN", "BOOL"},
        "BOOL": {"BOOLEAN", "BOOL"},

        # Дата и время
        "DATE": {"DATE", "TIMESTAMP", "TIMESTAMPTZ"},
        "TIME": {"TIME", "TIMETZ"},
        "TIMETZ": {"TIME", "TIMETZ"},
        "TIMESTAMP": {"TIMESTAMP", "TIMESTAMPTZ", "DATE"},
        "TIMESTAMPTZ": {"TIMESTAMPTZ", "TIMESTAMP", "DATE"},

        # Интервалы
        "INTERVAL": {"INTERVAL"},

        # JSON
        "JSON": {"JSON", "JSONB"},
        "JSONB": {"JSONB", "JSON"},

        # UUID
        "UUID": {"UUID", "TEXT", "VARCHAR", "CHAR"},

        # Массивы (канонический формат: BASE[])
        "INTEGER[]": {"INTEGER[]", "BIGINT[]", "NUMERIC[]"},
        "BIGINT[]": {"BIGINT[]", "NUMERIC[]"},
        "NUMERIC[]": {"NUMERIC[]"},
        "TEXT[]": {"TEXT[]", "VARCHAR[]"},
        "VARCHAR[]": {"VARCHAR[]", "TEXT[]"},
        "CHAR[]": {"CHAR[]", "VARCHAR[]", "TEXT[]"},  # условно: char[] расширяется до text[]/varchar[]

        # Специальные типы
        "SERIAL": {"SERIAL", "INTEGER", "BIGINT"},
        "BIGSERIAL": {"BIGSERIAL", "BIGINT", "INTEGER"},
        "MONEY": {"MONEY", "NUMERIC", "DECIMAL"},
        "BYTEA": {"BYTEA"},
        "OID": {"OID", "INTEGER"},

        # Геометрические типы
        "POINT": {"POINT"},
        "LINE": {"LINE"},
        "LSEG": {"LSEG"},
        "BOX": {"BOX"},
        "PATH": {"PATH"},
        "POLYGON": {"POLYGON"},
        "CIRCLE": {"CIRCLE"},

        # Сетевые адреса
        "CIDR": {"CIDR", "INET"},
        "INET": {"INET", "CIDR"},
        "MACADDR": {"MACADDR"},
        "MACADDR8": {"MACADDR8"},

        # Битовые строки
        "BIT": {"BIT", "VARBIT"},
        "VARBIT": {"VARBIT", "BIT"},

        # XML
        "XML": {"XML"},
    }

    # Алиасы типов (синонимы) — применяются к БАЗОВОМУ типу (без [])
    TYPE_ALIASES: Dict[str, str] = {
        "INT": "INTEGER",
        "BOOL": "BOOLEAN",
        "CHARACTER VARYING": "VARCHAR",
        "DOUBLE": "DOUBLE PRECISION",
        "FLOAT4": "REAL",
        "FLOAT8": "DOUBLE PRECISION",
        "FLOAT": "DOUBLE PRECISION",
        "SERIAL4": "SERIAL",
        "SERIAL8": "BIGSERIAL",
    }

    # Алиасы массивов: внутренние имена PostgreSQL -> канонические BASE[]
    ARRAY_INTERNAL_ALIASES: Dict[str, str] = {
        "_INT2": "SMALLINT[]",
        "_INT4": "INTEGER[]",
        "_INT8": "BIGINT[]",
        "_NUMERIC": "NUMERIC[]",
        "_TEXT": "TEXT[]",
        "_VARCHAR": "VARCHAR[]",
        "_BPCHAR": "CHAR[]",
    }

    TYPE_CATEGORIES: Dict[str, TypeCategory] = {
        "SMALLINT": TypeCategory.INTEGER,
        "INTEGER": TypeCategory.INTEGER,
        "INT": TypeCategory.INTEGER,
        "BIGINT": TypeCategory.INTEGER,
        "SERIAL": TypeCategory.INTEGER,
        "BIGSERIAL": TypeCategory.INTEGER,

        "NUMERIC": TypeCategory.DECIMAL,
        "DECIMAL": TypeCategory.DECIMAL,

        "REAL": TypeCategory.FLOAT,
        "DOUBLE PRECISION": TypeCategory.FLOAT,

        "CHAR": TypeCategory.CHARACTER,
        "CHARACTER": TypeCategory.CHARACTER,
        "VARCHAR": TypeCategory.TEXT,
        "TEXT": TypeCategory.TEXT,

        "BOOLEAN": TypeCategory.BOOLEAN,
        "BOOL": TypeCategory.BOOLEAN,

        "DATE": TypeCategory.DATE,
        "TIME": TypeCategory.TIME,
        "TIMETZ": TypeCategory.TIME,
        "TIMESTAMP": TypeCategory.DATETIME,
        "TIMESTAMPTZ": TypeCategory.DATETIME,

        "JSON": TypeCategory.JSON,
        "JSONB": TypeCategory.JSON,

        "UUID": TypeCategory.UUID,

        "MONEY": TypeCategory.MONEY,
        "BYTEA": TypeCategory.BYTEA,
    }

    INCOMPATIBLE_PAIRS: Set[Tuple[str, str]] = {
        ("INTEGER", "VARCHAR"), ("VARCHAR", "INTEGER"),
        ("NUMERIC", "TEXT"), ("TEXT", "NUMERIC"),
        ("BIGINT", "CHAR"), ("CHAR", "BIGINT"),
        ("DECIMAL", "VARCHAR"), ("VARCHAR", "DECIMAL"),
        ("FLOAT", "TEXT"), ("TEXT", "FLOAT"),

        ("BOOLEAN", "INTEGER"), ("INTEGER", "BOOLEAN"),
        ("BOOL", "NUMERIC"), ("NUMERIC", "BOOL"),

        ("TIMESTAMP", "INTEGER"), ("INTEGER", "TIMESTAMP"),
        ("DATE", "NUMERIC"), ("NUMERIC", "DATE"),
        ("TIME", "INTEGER"), ("INTEGER", "TIME"),

        ("JSON", "VARCHAR"), ("VARCHAR", "JSON"),
        ("JSONB", "TEXT"), ("TEXT", "JSONB"),

        ("UUID", "INTEGER"), ("INTEGER", "UUID"),
        ("UUID", "NUMERIC"), ("NUMERIC", "UUID"),

        ("BYTEA", "TEXT"), ("TEXT", "BYTEA"),
        ("BYTEA", "VARCHAR"), ("VARCHAR", "BYTEA"),

        ("POINT", "INTEGER"), ("INTEGER", "POINT"),
        ("POLYGON", "TEXT"), ("TEXT", "POLYGON"),

        ("INET", "INTEGER"), ("INTEGER", "INET"),
        ("CIDR", "NUMERIC"), ("NUMERIC", "CIDR"),
    }

    NARROWING_CONVERSIONS: Dict[str, Set[str]] = {
        "NUMERIC": {"INTEGER", "BIGINT", "SMALLINT", "REAL"},
        "DECIMAL": {"INTEGER", "BIGINT", "SMALLINT", "REAL"},
        "DOUBLE PRECISION": {"REAL", "NUMERIC", "DECIMAL"},
        "VARCHAR": {"CHAR"},
        "TEXT": {"VARCHAR", "CHAR"},
        "TIMESTAMPTZ": {"TIMESTAMP"},
        "BIGINT": {"INTEGER", "SMALLINT"},
        "INTEGER": {"SMALLINT"},
    }

    WIDENING_CONVERSIONS: Dict[str, Set[str]] = {
        "SMALLINT": {"INTEGER", "BIGINT", "NUMERIC", "DECIMAL"},
        "INTEGER": {"BIGINT", "NUMERIC", "DECIMAL"},
        "CHAR": {"VARCHAR", "TEXT"},
        "VARCHAR": {"TEXT"},
        "TIMESTAMP": {"TIMESTAMPTZ"},
        "REAL": {"DOUBLE PRECISION"},
        "NUMERIC": {"DOUBLE PRECISION"},
    }

    @classmethod
    def normalize_type(cls, type_str: str) -> str:
        """
        Нормализует строку типа данных.

        Поддерживает:
        - модификаторы (VARCHAR(255) -> VARCHAR)
        - массивы (integer[] -> INTEGER[])
        - внутренние имена массивов PostgreSQL (_INT4 -> INTEGER[])
        """
        if not type_str:
            return "UNKNOWN"

        s = type_str.strip().upper()

        # убрать модификаторы в скобках
        s = s.split("(", 1)[0].strip()

        # 1) Внутренние имена массивов PostgreSQL: _INT4, _TEXT ...
        if s in cls.ARRAY_INTERNAL_ALIASES:
            return cls.ARRAY_INTERNAL_ALIASES[s]

        # 2) Внешняя нотация массива: base[]
        is_array = bool(_ARRAY_SUFFIX_RE.search(s))
        if is_array:
            base = _ARRAY_SUFFIX_RE.sub("", s).strip()
            base = cls.TYPE_ALIASES.get(base, base)
            # чуть-чуть нормализации имен
            if base == "CHARACTER":
                base = "CHAR"
            return f"{base}[]"

        # 3) Обычный скалярный тип
        s = cls.TYPE_ALIASES.get(s, s)
        if s == "CHARACTER":
            # не алиасим в CHAR автоматически везде, чтобы не путать категории/матрицу
            # но для совместимости в матрице CHAR/CHARACTER всё равно допускаем
            return "CHARACTER"
        return s

    @classmethod
    def get_type_category(cls, type_str: str) -> TypeCategory:
        normalized = cls.normalize_type(type_str)
        if normalized.endswith("[]"):
            return TypeCategory.ARRAY
        base = normalized[:-2] if normalized.endswith("[]") else normalized
        return cls.TYPE_CATEGORIES.get(base, TypeCategory.UNKNOWN)

    @classmethod
    def are_compatible(cls, type_a: str, type_b: str) -> bool:
        norm_a = cls.normalize_type(type_a)
        norm_b = cls.normalize_type(type_b)

        if norm_a == norm_b:
            return True

        if (norm_a, norm_b) in cls.INCOMPATIBLE_PAIRS:
            return False

        if norm_a in cls.COMPATIBILITY_MATRIX:
            return norm_b in cls.COMPATIBILITY_MATRIX[norm_a]

        if norm_b in cls.COMPATIBILITY_MATRIX:
            return norm_a in cls.COMPATIBILITY_MATRIX[norm_b]

        category_a = cls.get_type_category(norm_a)
        category_b = cls.get_type_category(norm_b)

        if category_a == category_b and category_a != TypeCategory.UNKNOWN:
            if category_a in (TypeCategory.INTEGER, TypeCategory.DECIMAL, TypeCategory.FLOAT):
                return cls._are_numeric_types_compatible(norm_a, norm_b)
            if category_a == TypeCategory.ARRAY:
                # если оба массивы, но не попали в матрицу — считаем совместимыми только если одинаковая база
                return norm_a == norm_b
            return True

        return False

    @classmethod
    def _are_numeric_types_compatible(cls, type_a: str, type_b: str) -> bool:
        numeric_types = {
            "SMALLINT", "INTEGER", "BIGINT",
            "REAL", "DOUBLE PRECISION",
            "NUMERIC", "DECIMAL",
        }
        return type_a in numeric_types and type_b in numeric_types

    @classmethod
    def is_narrowing_conversion(cls, from_type: str, to_type: str) -> bool:
        norm_from = cls.normalize_type(from_type)
        norm_to = cls.normalize_type(to_type)
        return norm_to in cls.NARROWING_CONVERSIONS.get(norm_from, set())

    @classmethod
    def is_widening_conversion(cls, from_type: str, to_type: str) -> bool:
        norm_from = cls.normalize_type(from_type)
        norm_to = cls.normalize_type(to_type)
        return norm_to in cls.WIDENING_CONVERSIONS.get(norm_from, set())

    @classmethod
    def get_conversion_risk_level(cls, from_type: str, to_type: str) -> str:
        if not cls.are_compatible(from_type, to_type):
            return "INCOMPATIBLE"
        if cls.is_narrowing_conversion(from_type, to_type):
            return "DANGEROUS"
        if cls.is_widening_conversion(from_type, to_type):
            return "SAFE"
        norm_from = cls.normalize_type(from_type)
        norm_to = cls.normalize_type(to_type)
        return "WARNING" if norm_from != norm_to else "SAFE"

    @classmethod
    def analyze_type_change(
        cls,
        old_type: str,
        new_type: str,
        column_name: str = "",
        table_name: str = "",
    ) -> Dict[str, Any]:
        norm_old = cls.normalize_type(old_type)
        norm_new = cls.normalize_type(new_type)

        analysis: Dict[str, Any] = {
            "old_type": old_type,
            "new_type": new_type,
            "normalized_old": norm_old,
            "normalized_new": norm_new,
            "is_same_type": norm_old == norm_new,
            "are_compatible": cls.are_compatible(old_type, new_type),
            "conversion_risk": cls.get_conversion_risk_level(old_type, new_type),
            "is_narrowing": cls.is_narrowing_conversion(old_type, new_type),
            "is_widening": cls.is_widening_conversion(old_type, new_type),
            "category_old": cls.get_type_category(old_type).value,
            "category_new": cls.get_type_category(new_type).value,
        }

        if not analysis["are_compatible"]:
            analysis["message"] = f"Типы {old_type} и {new_type} абсолютно несовместимы"
            analysis["conflict_level"] = "CRITICAL"
        elif analysis["is_narrowing"]:
            analysis["message"] = f"Преобразование {old_type} → {new_type} приводит к сужению (потере данных)"
            analysis["conflict_level"] = "HIGH"
        elif analysis["conversion_risk"] == "WARNING":
            analysis["message"] = f"Преобразование {old_type} → {new_type} может вызвать проблемы"
            analysis["conflict_level"] = "MEDIUM"
        else:
            analysis["message"] = f"Преобразование {old_type} → {new_type} безопасно"
            analysis["conflict_level"] = "LOW"

        if column_name and table_name:
            analysis["column"] = column_name
            analysis["table"] = table_name
            analysis["full_column_name"] = f"{table_name}.{column_name}"

        return analysis

    @classmethod
    def find_potential_type_conflicts(cls, type_changes: List[Dict]) -> List[Dict]:
        conflicts: List[Dict] = []
        for change in type_changes:
            analysis = cls.analyze_type_change(
                change["old_type"],
                change["new_type"],
                change.get("column", ""),
                change.get("table", ""),
            )
            if analysis["conflict_level"] in ("CRITICAL", "HIGH"):
                conflicts.append({
                    "rule": "R2",
                    "level": analysis["conflict_level"],
                    "message": analysis["message"],
                    "details": {
                        "table": change.get("table", ""),
                        "column": change.get("column", ""),
                        "analysis": analysis,
                    },
                })
        return conflicts

    @classmethod
    def get_type_hierarchy(cls) -> Dict[str, List[str]]:
        hierarchy: Dict[str, List[str]] = {}

        hierarchy["NUMERIC"] = ["DECIMAL", "INTEGER", "BIGINT", "SMALLINT", "REAL", "DOUBLE PRECISION"]
        hierarchy["INTEGER"] = ["BIGINT", "SMALLINT"]

        hierarchy["TEXT"] = ["VARCHAR", "CHAR", "CHARACTER"]
        hierarchy["VARCHAR"] = ["CHAR", "CHARACTER"]

        hierarchy["TIMESTAMPTZ"] = ["TIMESTAMP", "DATE"]
        hierarchy["TIMESTAMP"] = ["DATE"]

        return hierarchy

    @classmethod
    def get_type_size(cls, type_str: str) -> Optional[int]:
        size_map = {
            "SMALLINT": 2,
            "INTEGER": 4,
            "BIGINT": 8,
            "REAL": 4,
            "DOUBLE PRECISION": 8,
            "BOOLEAN": 1,
            "DATE": 4,
            "TIMESTAMP": 8,
            "TIMESTAMPTZ": 8,
            "UUID": 16,
            "OID": 4,
        }

        normalized = cls.normalize_type(type_str)
        if normalized.endswith("[]"):
            return None  # зависит от элементов/overhead
        return size_map.get(normalized)
