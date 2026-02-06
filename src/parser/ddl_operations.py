"""
Классы для представления DDL операций.

- DDLOperation ~ op
- OperationAnalyzer.get_domain(op) реализует domain(op)
- OperationAnalyzer.get_influence(op, graph) реализует influence(op)

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class OperationType(Enum):
    """Типы DDL операций."""
    CREATE_TABLE = "create_table"
    DROP_TABLE = "drop_table"

    ALTER_TABLE = "alter_table"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN = "alter_column"

    ADD_CONSTRAINT = "add_constraint"
    DROP_CONSTRAINT = "drop_constraint"

    RENAME_TABLE = "rename_table"
    RENAME_COLUMN = "rename_column"


@dataclass
class DDLOperation:
    """
    Базовый класс операции op.

    """
    operation_type: OperationType = field(init=False)

    schema: str = "public"
    raw_sql: str = ""

    def get_affected_objects(self) -> Set[str]:
        """Прямо затронутые объекты (можно трактовать как domain(op) в упрощённом виде)."""
        return set()

    def __str__(self) -> str:
        rs = (self.raw_sql or "").strip().replace("\n", " ")
        if len(rs) > 120:
            rs = rs[:117] + "..."
        return f"{self.operation_type.value}: {rs}"


# -------------------------
# CREATE/DROP TABLE
# -------------------------

@dataclass
class CreateTableOperation(DDLOperation):
    """CREATE TABLE schema.table (...)."""
    table_name: str = ""
    columns: List[Any] = field(default_factory=list)
    constraints: List[Any] = field(default_factory=list)
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.operation_type = OperationType.CREATE_TABLE

    def get_affected_objects(self) -> Set[str]:
        aff = {f"{self.schema}.{self.table_name}" if self.schema else self.table_name}
        # влияние: целевые таблицы внешних ключей
        for fk in self.foreign_keys:
            t = fk.get("referenced_table") or fk.get("to_table")
            if t:
                aff.add(t)
        return aff


@dataclass
class DropTableOperation(DDLOperation):
    """DROP TABLE schema.table."""
    table_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.DROP_TABLE

    def get_affected_objects(self) -> Set[str]:
        return {f"{self.schema}.{self.table_name}" if self.schema else self.table_name}


# -------------------------
# ALTER TABLE + COLUMNS
# -------------------------

@dataclass
class AlterTableOperation(DDLOperation):
    """ALTER TABLE schema.table ..."""
    table_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.ALTER_TABLE

    def get_affected_objects(self) -> Set[str]:
        return {f"{self.schema}.{self.table_name}" if self.schema else self.table_name}


@dataclass
class AddColumnOperation(DDLOperation):
    table_name: str = ""
    column: Any = None  # обычно ColumnDefinition/Column

    def __post_init__(self) -> None:
        self.operation_type = OperationType.ADD_COLUMN

    def get_affected_objects(self) -> Set[str]:
        col_name = getattr(self.column, "name", None) if self.column else None
        if col_name:
            return {f"{self.schema}.{self.table_name}.{col_name}"}
        return {f"{self.schema}.{self.table_name}"}


@dataclass
class DropColumnOperation(DDLOperation):
    table_name: str = ""
    column_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.DROP_COLUMN

    def get_affected_objects(self) -> Set[str]:
        if self.column_name:
            return {f"{self.schema}.{self.table_name}.{self.column_name}"}
        return {f"{self.schema}.{self.table_name}"}


@dataclass
class AlterColumnOperation(DDLOperation):
    table_name: str = ""
    column_name: str = ""
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    new_default: Optional[str] = None
    set_not_null: Optional[bool] = None

    def __post_init__(self) -> None:
        self.operation_type = OperationType.ALTER_COLUMN

    def get_affected_objects(self) -> Set[str]:
        if self.column_name:
            return {f"{self.schema}.{self.table_name}.{self.column_name}"}
        return {f"{self.schema}.{self.table_name}"}


# -------------------------
# CONSTRAINTS
# -------------------------

@dataclass
class AddConstraintOperation(DDLOperation):
    table_name: str = ""
    constraint: Any = None  # обычно DatabaseObject/ConstraintDefinition

    def __post_init__(self) -> None:
        self.operation_type = OperationType.ADD_CONSTRAINT

    def get_affected_objects(self) -> Set[str]:
        aff = {f"{self.schema}.{self.table_name}" if self.schema else self.table_name}
        if self.constraint is not None:
            name = getattr(self.constraint, "name", None)
            if name:
                aff.add(name)
            # FK может ссылаться на другую таблицу
            attrs = getattr(self.constraint, "attributes", None)
            if isinstance(attrs, dict):
                to_table = attrs.get("to_table") or attrs.get("referenced_table")
                if to_table:
                    aff.add(to_table)
        return aff


@dataclass
class DropConstraintOperation(DDLOperation):
    table_name: str = ""
    constraint_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.DROP_CONSTRAINT

    def get_affected_objects(self) -> Set[str]:
        aff = {f"{self.schema}.{self.table_name}" if self.schema else self.table_name}
        if self.constraint_name:
            aff.add(self.constraint_name)
        return aff


# -------------------------
# RENAME
# -------------------------

@dataclass
class RenameTableOperation(DDLOperation):
    old_table_name: str = ""
    new_table_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.RENAME_TABLE

    def get_affected_objects(self) -> Set[str]:
        s = self.schema or "public"
        return {f"{s}.{self.old_table_name}", f"{s}.{self.new_table_name}"}


@dataclass
class RenameColumnOperation(DDLOperation):
    table_name: str = ""
    old_column_name: str = ""
    new_column_name: str = ""

    def __post_init__(self) -> None:
        self.operation_type = OperationType.RENAME_COLUMN

    def get_affected_objects(self) -> Set[str]:
        s = self.schema or "public"
        return {
            f"{s}.{self.table_name}.{self.old_column_name}",
            f"{s}.{self.table_name}.{self.new_column_name}",
        }


# -------------------------
# Analyzer: domain(op) / influence(op)
# -------------------------

class OperationAnalyzer:
    """
    Реализует domain(op) и influence(op).

    domain(op): множество объектов, на которые операция действует напрямую.
    influence(op): domain(op) + косвенно затронутые (например, зависимые по графу).
    """

    @staticmethod
    def get_domain(operation: DDLOperation) -> Set[str]:
        # Здесь используем тот же формат, что и get_affected_objects(),
        # чтобы оно совпадало по интерфейсу по всему проекту.
        return set(operation.get_affected_objects())

    @staticmethod
    def get_influence(operation: DDLOperation, graph: Optional[Any] = None) -> Set[str]:
        influence = set(OperationAnalyzer.get_domain(operation))

        # Для DROP TABLE: добавим зависимых из графа (если graph умеет get_dependents/get_vertex_by_name)
        if isinstance(operation, DropTableOperation) and graph is not None:
            table_qname = f"{operation.schema}.{operation.table_name}" if operation.schema else operation.table_name

            table_id = None
            if hasattr(graph, "get_vertex_by_name"):
                table_id = graph.get_vertex_by_name(table_qname) or graph.get_vertex_by_name(operation.table_name)

            if table_id is not None and hasattr(graph, "get_dependents"):
                try:
                    deps = graph.get_dependents(table_id)
                    for dep_id in deps:
                        v = graph.vertices.get(dep_id)
                        if v is not None:
                            influence.add(getattr(v, "name", str(dep_id)))
                except Exception:
                    # граф может быть другой реализации — влияние останется базовым
                    pass

        return influence

