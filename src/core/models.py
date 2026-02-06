from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class ObjectType(Enum):
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"
    CONSTRAINT = "constraint"
    INDEX = "index"
    FOREIGN_KEY = "foreign_key"
    PRIMARY_KEY = "primary_key"
    UNIQUE_CONSTRAINT = "unique_constraint"
    CHECK_CONSTRAINT = "check_constraint"
    VIEW = "view"
    FUNCTION = "function"
    TRIGGER = "trigger"


class RelationType(Enum):
    CONTAINS = "contains"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"
    ENFORCED_BY = "enforced_by"
    COMPOSED_OF = "composed_of"
    USES = "uses"
    TRIGGERS = "triggers"


@dataclass
class DatabaseObject:
    id: int
    type: ObjectType
    name: str
    schema: str = "public"
    attributes: Any = field(default_factory=dict)

    def __post_init__(self):
        # ГАРАНТИЯ: attributes ВСЕГДА dict
        if self.attributes is None:
            self.attributes = {}
        elif not isinstance(self.attributes, dict):
            self.attributes = {
                "value": self.attributes
            }

    def get_key(self) -> str:
        return f"{self.type.value}:{self.schema}:{self.name}"

    def __eq__(self, other):
        return (
                isinstance(other, DatabaseObject)
                and self.type == other.type
                and self.schema == other.schema
                and self.name == other.name
        )

    def __hash__(self):
        return hash((self.type, self.schema, self.name))


class Column(DatabaseObject):
    def __init__(
        self,
        *,
        id: int,
        name: str,
        table: str | None = None,
        schema: str = "public",
        data_type: str = "",
        is_nullable: bool = True,
        default_value: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        attributes: Optional[Dict[str, Any]] = None,

    ):
        super().__init__(
            id=id,
            type=ObjectType.COLUMN,
            name=name,
            schema=schema,
            attributes=attributes or {},
        )

        self.data_type = data_type
        self.is_nullable = is_nullable
        self.default_value = default_value
        self.constraints = constraints or []

        self.attributes.setdefault("table", table)
        self.attributes.setdefault("data_type", self.data_type)
        self.attributes.setdefault("is_nullable", self.is_nullable)
        self.attributes.setdefault("not_null", not self.is_nullable)

    def get_key(self) -> str:
        table = self.attributes.get("table")
        return f"column:{self.schema}:{table}.{self.name}"


class Table(DatabaseObject):
    def __init__(
        self,
        *,
        id: int,
        name: str,
        schema: str = "public",
        columns: Optional[Dict[str, Column]] = None,
        constraints: Optional[Dict[str, DatabaseObject]] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            id=id,
            type=ObjectType.TABLE,
            name=name,
            schema=schema,
            attributes=attributes or {},
        )

        self.columns = columns or {}
        self.constraints = constraints or {}
