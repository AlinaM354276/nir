# src/graph/builder.py

from __future__ import annotations

from typing import List, Dict, Optional, Tuple, cast

from src.core.models import (
    DatabaseObject,
    ObjectType,
    RelationType,
    Table,
    Column,
)
from src.graph.schema_graph import SchemaGraph


def _norm_ident(x: Optional[str]) -> str:
    return (x or "").strip().strip('"').lower()


def _table_key(schema: str, table: str) -> Tuple[str, str]:
    return (_norm_ident(schema or "public"), _norm_ident(table))


class GraphBuilder:
    """
    Строит ориентированный граф схемы БД: G = (V, E).
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.graph: Optional[SchemaGraph] = None

    def build_from_objects(
        self,
        objects: List[DatabaseObject],
        name: str = "",
    ) -> SchemaGraph:
        self.graph = SchemaGraph(name=name)
        table_ids: Dict[Tuple[str, str], int] = {}

        # ---------- TABLES ----------
        for obj in objects:
            if obj.type != ObjectType.TABLE:
                continue

            schema = obj.schema or "public"
            table_id = self.graph.add_vertex(obj)
            table_ids[_table_key(schema, obj.name)] = table_id

        # ---------- COLUMNS + CONSTRAINTS ----------
        for obj in objects:
            if obj.type != ObjectType.TABLE:
                continue

            table = cast(Table, obj)
            schema = table.schema or "public"
            table_id = table_ids.get(_table_key(schema, table.name))
            if not table_id:
                continue

            for column in table.columns.values():
                column_id = self._add_column(column, table_id)
                if column_id is None:
                    continue

                self._add_column_constraints(
                    column=column,
                    column_id=column_id,
                    table_id=table_id,
                    table_name=table.name,
                    schema=schema,
                )

        # ---------- FOREIGN KEYS ----------
        self._add_foreign_key_objects(objects, table_ids)

        return self.graph

    # ==========================================================
    # ВНУТРЕННИЕ МЕТОДЫ
    # ==========================================================

    def _add_column(self, column: Column, table_id: int) -> Optional[int]:
        if not self.graph:
            return None

        column.attributes = column.attributes or {}
        column.attributes["data_type"] = column.data_type

        column_id = self.graph.add_vertex(column)
        self.graph.add_edge(column_id, table_id, RelationType.CONTAINS)

        return column_id

    def _add_column_constraints(
        self,
        column: Column,
        column_id: int,
        table_id: int,
        table_name: str,
        schema: str,
    ) -> None:
        if not self.graph:
            return

        attrs = column.attributes or {}

        # ---------- PRIMARY KEY ----------
        if attrs.get("is_primary_key"):
            pk = DatabaseObject(
                id=0,
                type=ObjectType.PRIMARY_KEY,
                name=f"pk_{table_name}",
                schema=schema,
                attributes={"table": table_name, "column": column.name},
            )
            pk_id = self.graph.add_vertex(pk)
            self.graph.add_edge(pk_id, column_id, RelationType.DEPENDS_ON)
            self.graph.add_edge(pk_id, table_id, RelationType.CONTAINS)

        # ---------- UNIQUE ----------
        if attrs.get("is_unique") and not attrs.get("is_primary_key"):
            uq = DatabaseObject(
                id=0,
                type=ObjectType.UNIQUE_CONSTRAINT,
                name=f"uq_{table_name}_{column.name}",
                schema=schema,
                attributes={"table": table_name, "column": column.name},
            )
            uq_id = self.graph.add_vertex(uq)
            self.graph.add_edge(uq_id, column_id, RelationType.DEPENDS_ON)
            self.graph.add_edge(uq_id, table_id, RelationType.CONTAINS)

    def _add_foreign_key_objects(
        self,
        objects: List[DatabaseObject],
        table_ids: Dict[Tuple[str, str], int],
    ) -> None:
        """
        FOREIGN KEY существует как DatabaseObject
        """
        if not self.graph:
            return

        for obj in objects:
            if obj.type != ObjectType.TABLE:
                continue

            table = cast(Table, obj)
            schema = table.schema or "public"
            from_table_id = table_ids.get(_table_key(schema, table.name))
            if not from_table_id:
                continue

            foreign_keys = table.attributes.get("foreign_keys") or []

            for fk in foreign_keys:
                ref_table = fk.get("referenced_table")
                ref_schema = fk.get("referenced_schema", "public")
                ref_column = fk.get("referenced_column")

                if not ref_table:
                    continue

                to_table_id = table_ids.get(_table_key(ref_schema, ref_table))
                if not to_table_id:
                    continue

                fk_obj = DatabaseObject(
                    id=0,
                    type=ObjectType.FOREIGN_KEY,
                    name=f"fk_{table.name}_{ref_table}",
                    schema=schema,
                    attributes={
                        "from_table": table.name,
                        "to_table": ref_table,
                        "from_column": fk.get("column"),
                        "to_column": ref_column,
                    },
                )

                fk_id = self.graph.add_vertex(fk_obj)

                self.graph.add_edge(fk_id, from_table_id, RelationType.DEPENDS_ON)
                self.graph.add_edge(fk_id, to_table_id, RelationType.REFERENCES)
