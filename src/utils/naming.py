"""
utils/naming.py

Утилиты для работы с именами объектов и стабильными ключами.
Нужны для:
- сопоставления объектов (matching),
- обнаружения конфликтов именования (R4),
- стабильной сериализации в отчёты.

Принцип:
- PostgreSQL неquoted идентификаторы приводит к lower-case.
- quoted идентификаторы ("User") сохраняют регистр и символы.

Важно для согласованности проекта:
- SchemaGraph.build_match_key() формирует ключи вида:
    type:schema:name[:table:...][:ref:...]
- Здесь object_key() должен генерировать ключи без "двойной схемы"
"""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple, Union

try:
    from src.core.models import ObjectType, DatabaseObject
except Exception:  # pragma: no cover
    ObjectType = None  # type: ignore
    DatabaseObject = None  # type: ignore


_QUOTED_RE = re.compile(r'^".*"$')
_WS_RE = re.compile(r"\s+")


def is_quoted_identifier(identifier: str) -> bool:
    """True если идентификатор заключён в двойные кавычки."""
    if not identifier:
        return False
    s = identifier.strip()
    return bool(_QUOTED_RE.match(s))


def strip_quotes(identifier: str) -> str:
    """Убирает внешние двойные кавычки, если они есть."""
    s = (identifier or "").strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def normalize_identifier(identifier: str) -> str:
    """
    Нормализует идентификатор в стиле PostgreSQL:
    - если quoted: сохраняем внутреннее содержимое как есть (без внешних кавычек)
    - если не quoted: lower-case + trim + collapse spaces
    """
    if not identifier:
        return ""
    s = identifier.strip()
    s = _WS_RE.sub(" ", s)

    if is_quoted_identifier(s):
        return strip_quotes(s)
    return s.lower()


def normalize_schema(schema: Optional[str]) -> str:
    """Нормализует имя схемы; пустое -> 'public'."""
    s = normalize_identifier(schema or "")
    return s or "public"


def split_qualified_name(name: str) -> Tuple[Optional[str], str]:
    """
    Делит имя на (schema, object_name), если оно квалифицировано через точку.
    Примеры:
      "public.users" -> ("public", "users")
      "users" -> (None, "users")
    """
    if not name:
        return None, ""
    s = name.strip()
    if "." in s:
        left, right = s.split(".", 1)
        return normalize_identifier(left), normalize_identifier(right)
    return None, normalize_identifier(s)


def split_table_column(name: str) -> Tuple[Optional[str], str]:
    """
    Делит строку вида "table.column" на ("table", "column").
    Если точки нет — (None, normalized_name).
    """
    if not name:
        return None, ""
    s = name.strip()
    if "." in s:
        t, c = s.split(".", 1)
        return normalize_identifier(t), normalize_identifier(c)
    return None, normalize_identifier(s)


def qualify_column(table: str, column: str, schema: Optional[str] = None) -> str:
    """Собирает schema.table.column (без кавычек)."""
    sc = normalize_schema(schema)
    t = normalize_identifier(table)
    c = normalize_identifier(column)
    return f"{sc}.{t}.{c}"


def qualify_table(table: str, schema: Optional[str] = None) -> str:
    """Собирает schema.table."""
    sc = normalize_schema(schema)
    t = normalize_identifier(table)
    return f"{sc}.{t}"


def _safe_get_attr(obj: Any, key: str) -> Any:
    """Безопасно достаёт атрибут или dict-поле."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _object_type_value(obj_type: Any) -> str:
    """Превращает ObjectType/строку в строковое значение."""
    if obj_type is None:
        return "unknown"
    if hasattr(obj_type, "value"):
        return str(obj_type.value)
    return str(obj_type)


def guess_parent_table(obj: Any) -> Optional[str]:
    """
    Пытается определить "родительскую" таблицу для объекта:
    - attributes['table'/'table_name'/'parent_table']
    - имя вида 'table.column'
    - поля FK: from_table/to_table
    """
    attrs = _safe_get_attr(obj, "attributes") or {}
    if isinstance(attrs, dict):
        for k in ("table", "table_name", "parent_table"):
            v = attrs.get(k)
            if v:
                return normalize_identifier(str(v))

    name = _safe_get_attr(obj, "name") or ""
    t, _ = split_table_column(str(name))
    if t:
        return t

    for k in ("from_table", "to_table"):
        v = _safe_get_attr(obj, k)
        if v:
            return normalize_identifier(str(v))

    return None


def object_qualified_name(obj: Any) -> str:
    """
    Возвращает "человеческое" квалифицированное имя объекта для отчётов.
    Для COLUMN старается вернуть schema.table.column.
    Для TABLE — schema.table.
    Для прочих — schema.name (или schema.table.name, если можно вывести parent_table).
    """
    obj_type = _safe_get_attr(obj, "type")
    schema = normalize_schema(_safe_get_attr(obj, "schema"))
    name = normalize_identifier(str(_safe_get_attr(obj, "name") or ""))

    tval = _object_type_value(obj_type)

    if tval == "column":
        parent = guess_parent_table(obj)
        if parent:
            _, col = split_table_column(name)
            return f"{schema}.{parent}.{col}"
        return f"{schema}.{name}"

    if tval == "table":
        return f"{schema}.{name}"

    parent = guess_parent_table(obj)
    if parent and tval in {
        "constraint", "index", "foreign_key", "primary_key",
        "unique_constraint", "check_constraint", "trigger"
    }:
        return f"{schema}.{parent}.{name}"

    return f"{schema}.{name}"


def _strip_schema_prefix(qualified: str, schema: str) -> str:
    """
    Убирает ведущий 'schema.' если он уже присутствует, чтобы не было дублей в ключах.
    Пример: qualified='public.users.id', schema='public' -> 'users.id'
    """
    q = (qualified or "").strip()
    sc = (schema or "").strip()
    prefix = f"{sc}."
    if q.startswith(prefix):
        return q[len(prefix):]
    return q


def object_key(
    obj_or_type: Union[Any, str],
    schema: Optional[str] = None,
    name: Optional[str] = None,
    *,
    prefer_qualified: bool = True,
) -> str:
    """
    Генерирует стабильный ключ объекта.

    Режимы:
    1) object_key(obj) -> "type:schema:name_or_context"
    2) object_key("table", "public", "users") -> "table:public:users"

    prefer_qualified=True:
      - для COLUMN/CONSTRAINT/INDEX/FK/PK пытается включать контекст таблицы
        (table.column / table.constraint / ...),
        но схема в ключе остаётся ровно ОДНА (чтобы не было "public:public.users.id").

    Ключ согласован по смыслу с SchemaGraph.build_match_key().
    """
    if name is None and schema is None and not isinstance(obj_or_type, str):
        obj = obj_or_type
        obj_type = _safe_get_attr(obj, "type")
        tval = _object_type_value(obj_type)
        sc = normalize_schema(_safe_get_attr(obj, "schema"))
        nm = normalize_identifier(str(_safe_get_attr(obj, "name") or ""))

        if prefer_qualified and tval in {
            "column", "constraint", "index",
            "foreign_key", "primary_key",
            "unique_constraint", "check_constraint",
            "trigger",
        }:
            q = object_qualified_name(obj)        # schema.table.column
            q_wo_schema = _strip_schema_prefix(q, sc)  # table.column
            return f"{tval}:{sc}:{q_wo_schema}"

        return f"{tval}:{sc}:{nm}"

    # явный режим: передали тип/схему/имя
    tval = _object_type_value(obj_or_type)
    sc = normalize_schema(schema)
    nm = normalize_identifier(name or "")
    return f"{tval}:{sc}:{nm}"


def parse_object_key(key: str) -> Tuple[str, str, str]:
    """
    Разбирает ключ вида "type:schema:name".
    Возвращает (type, schema, name).
    """
    if not key:
        return "unknown", "public", ""
    parts = key.split(":", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "public", parts[1]
    return "unknown", "public", key


__all__ = [
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
]
