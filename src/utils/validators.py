"""
utils/validators.py

Набор маленьких валидаторов и сигнатур для сравнения структур объектов.
Нужны для:
- R4 (конфликт именования): сравнить структуры/атрибуты объекта в ветках
- R6 (противоречивые ограничения): найти очевидные логические конфликты

"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


# --- 1) Сигнатуры атрибутов (для R4, а также для модификаций) -----------------

_DEFAULT_IGNORE_KEYS = {
    "id", "created_at", "updated_at",
    # иногда в attributes могут лежать поля, не влияющие на структуру
    "comment", "description",
}


def _freeze(obj: Any) -> Any:
    """
    Преобразует объект в хэшируемую/сравнимую форму:
    dict -> отсортированный список пар (key, freeze(value))
    list/tuple/set -> tuple(freeze(...)) (с сортировкой для set)
    прочее -> как есть
    """
    if isinstance(obj, dict):
        items = []
        for k in sorted(obj.keys(), key=lambda x: str(x)):
            items.append((str(k), _freeze(obj[k])))
        return tuple(items)
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(x) for x in obj)
    if isinstance(obj, set):
        return tuple(sorted((_freeze(x) for x in obj), key=lambda x: str(x)))
    return obj


def attrs_signature(
    attrs: Optional[Dict[str, Any]],
    *,
    ignore_keys: Optional[Iterable[str]] = None
) -> Tuple[Any, ...]:
    """
    Детерминированная сигнатура словаря атрибутов.

    Использовать так:
      if attrs_signature(a.attributes) != attrs_signature(b.attributes): конфликт структуры

    ignore_keys позволяет исключать шум (например, 'id'/'comment').
    """
    if not attrs:
        return tuple()

    ignore = set(ignore_keys or _DEFAULT_IGNORE_KEYS)
    filtered = {k: v for k, v in attrs.items() if k not in ignore}

    return _freeze(filtered)


def deep_equal_struct(
    a: Any,
    b: Any,
    *,
    ignore_keys: Optional[Iterable[str]] = None
) -> bool:
    """
    Структурное сравнение объектов (обычно dict attributes).
    """
    if isinstance(a, dict) and isinstance(b, dict):
        return attrs_signature(a, ignore_keys=ignore_keys) == attrs_signature(b, ignore_keys=ignore_keys)
    return _freeze(a) == _freeze(b)


# --- 2) Эвристики для R6: очевидные противоречия ограничений -------------------

_NUM_CMP_RE = re.compile(
    r"""
    ^\s*
    (?P<col>[a-zA-Z_][a-zA-Z0-9_]*)
    \s*
    (?P<op>>=|<=|=|>|<)
    \s*
    (?P<num>-?\d+(\.\d+)?)
    \s*$
    """,
    re.VERBOSE,
)

_NOT_NULL_RE = re.compile(r"\bNOT\s+NULL\b", re.IGNORECASE)
_NULL_RE = re.compile(r"\bNULL\b", re.IGNORECASE)


def _parse_numeric_check(expr: str) -> Optional[Tuple[str, str, float]]:
    """
    Пытается распарсить простейшее CHECK-условие вида:
      age > 0
      amount <= 100.5
    Возвращает (column, op, number).
    """
    if not expr:
        return None
    s = expr.strip()
    m = _NUM_CMP_RE.match(s)
    if not m:
        return None
    col = m.group("col")
    op = m.group("op")
    num = float(m.group("num"))
    return col, op, num


def _interval_from_cmp(op: str, num: float) -> Tuple[float, float, bool, bool]:
    """
    Превращает сравнение x op num в интервал.
    Возвращает (lo, hi, lo_inclusive, hi_inclusive)
    """
    INF = float("inf")
    if op == ">":
        return num, INF, False, True
    if op == ">=":
        return num, INF, True, True
    if op == "<":
        return -INF, num, True, False
    if op == "<=":
        return -INF, num, True, True
    if op == "=":
        return num, num, True, True
    # неизвестно
    return -INF, INF, True, True


def _intersect_intervals(a, b) -> Optional[Tuple[float, float, bool, bool]]:
    """
    Пересечение двух интервалов.
    Возвращает None если пересечение пустое.
    """
    lo1, hi1, li1, hi_i1 = a
    lo2, hi2, li2, hi_i2 = b

    lo = max(lo1, lo2)
    hi = min(hi1, hi2)

    if lo > hi:
        return None
    if lo == hi:
        # точка должна быть включена в оба
        li = (li1 if lo == lo1 else li2) and (li2 if lo == lo2 else li1)
        hi_i = (hi_i1 if hi == hi1 else hi_i2) and (hi_i2 if hi == hi2 else hi_i1)
        if li and hi_i:
            return lo, hi, True, True
        return None

    # lo_inclusive: если lo пришёл от первого — берём его inclusive, иначе от второго
    lo_incl = li1 if lo == lo1 else li2
    hi_incl = hi_i1 if hi == hi1 else hi_i2
    return lo, hi, lo_incl, hi_incl


def detect_obvious_constraint_conflict(constraint_changes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Эвристически ищет очевидные противоречия в наборе изменений ограничений для одного объекта.

    Ожидаемый вход (примерно):
      [
        {"kind": "NOT_NULL", "branch": "A", "value": True},
        {"kind": "NOT_NULL", "branch": "B", "value": False},
        {"kind": "CHECK", "branch": "A", "expression": "age > 0"},
        {"kind": "CHECK", "branch": "B", "expression": "age <= 0"},
      ]

    Возвращает dict с деталями конфликта или None.
    """

    if not constraint_changes:
        return None

    # 1) NOT NULL vs NULL (конфликт направления)
    not_null_states = {}
    for ch in constraint_changes:
        if ch.get("kind") == "NOT_NULL":
            br = ch.get("branch", "?")
            not_null_states[br] = bool(ch.get("value", True))

    if len(not_null_states) >= 2:
        vals = set(not_null_states.values())
        if vals == {True, False}:
            return {
                "type": "NOT_NULL_CONFLICT",
                "not_null_by_branch": not_null_states,
                "explanation": "В одной ветке колонка NOT NULL, в другой — допускает NULL."
            }

    # 2) CHECK-условия на одну и ту же колонку: пересечение пустое (очевидный конфликт)
    checks = []
    for ch in constraint_changes:
        if ch.get("kind") == "CHECK" and ch.get("expression"):
            parsed = _parse_numeric_check(str(ch["expression"]))
            if parsed:
                col, op, num = parsed
                checks.append({
                    "branch": ch.get("branch", "?"),
                    "column": col,
                    "op": op,
                    "num": num,
                    "expr": ch["expression"],
                    "interval": _interval_from_cmp(op, num),
                })

    # группируем по колонке
    by_col: Dict[str, List[Dict[str, Any]]] = {}
    for c in checks:
        by_col.setdefault(c["column"], []).append(c)

    for col, items in by_col.items():
        # если есть минимум два ограничения (скорее всего из разных веток)
        if len(items) < 2:
            continue

        # пытаемся пересечь все интервалы — если пусто, конфликт
        inter = items[0]["interval"]
        for it in items[1:]:
            inter = _intersect_intervals(inter, it["interval"])
            if inter is None:
                return {
                    "type": "CHECK_CONFLICT",
                    "column": col,
                    "constraints": [
                        {"branch": x["branch"], "expression": x["expr"]} for x in items
                    ],
                    "explanation": "CHECK-ограничения задают несовместимые диапазоны (пересечение пусто)."
                }

    # 3) Дубликаты UNIQUE на один и тот же набор колонок (не логическое противоречие, но конфликт структур)
    # (полезно как предупреждение)
    uniques = []
    for ch in constraint_changes:
        if ch.get("kind") == "UNIQUE":
            cols = ch.get("columns") or ch.get("cols")
            if cols:
                cols_norm = tuple(str(c).strip().lower() for c in cols)
                uniques.append((ch.get("branch", "?"), cols_norm))

    if len(uniques) >= 2:
        seen = {}
        dups = []
        for br, cols in uniques:
            if cols in seen and seen[cols] != br:
                dups.append({"branch_a": seen[cols], "branch_b": br, "columns": list(cols)})
            else:
                seen[cols] = br
        if dups:
            return {
                "type": "UNIQUE_DUPLICATE",
                "duplicates": dups,
                "explanation": "В разных ветках добавлены одинаковые UNIQUE-ограничения (возможен конфликт имён"
                               "/дублирование)."
            }

    return None


def normalize_constraint_expression(expr: str) -> str:
    """
    Очень лёгкая нормализация выражения ограничения (для сравнения/сигнатуры).
    """
    if not expr:
        return ""
    s = expr.strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()


__all__ = [
    "attrs_signature",
    "deep_equal_struct",
    "detect_obvious_constraint_conflict",
    "normalize_constraint_expression",
]
