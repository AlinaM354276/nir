"""
Основной парсер DDL-скриптов PostgreSQL.

ВАЖНО:
- поддерживает COLUMN-LEVEL FOREIGN KEY:
    email TEXT REFERENCES users(email)
- поддерживает TABLE-LEVEL FOREIGN KEY:
    FOREIGN KEY (email) REFERENCES users(email)
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional

import sqlparse

from src.core.models import Column, Table, DatabaseObject
from src.core.exceptions import ParsingError


class SQLParser:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    # ==========================================================
    # PUBLIC API
    # ==========================================================
    print(">>> SQLParser LOADED FROM src/parser/sql_parser.py <<<")

    def parse_to_objects(self, sql_text: str) -> List[DatabaseObject]:
        statements = sqlparse.parse(sql_text)
        objects: List[DatabaseObject] = []

        for stmt in statements:
            stmt_str = str(stmt).strip()
            if not stmt_str:
                continue

            if stmt_str.upper().startswith("CREATE TABLE"):
                table = self._parse_create_table(stmt_str)
                objects.append(table)

        return objects

    # ==========================================================
    # CREATE TABLE
    # ==========================================================

    def _parse_create_table(self, stmt: str) -> Table:
        m = re.search(
            r"CREATE\s+TABLE\s+([A-Za-z0-9_\.]+)\s*\((.*)\)",
            stmt,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            raise ParsingError(f"Cannot parse CREATE TABLE: {stmt}")

        full_name = m.group(1)
        body = m.group(2)

        schema, table_name = self._split_qualified_name(full_name)

        table = Table(
            id=0,
            name=table_name,
            schema=schema,
            attributes={
                "foreign_keys": [],
                "raw_sql": stmt,
            },
        )

        elements = self._split_elements(body)

        for el in elements:
            el = el.strip()

            # TABLE-LEVEL FK
            if el.upper().startswith("FOREIGN KEY"):
                fk = self._parse_table_level_fk(el)
                if fk:
                    table.attributes["foreign_keys"].append(fk)
                continue

            # COLUMN
            column = self._parse_column(el, table_name)
            if column:
                table.columns[column.name] = column

                # COLUMN-LEVEL FK
                if "foreign_key" in column.attributes:
                    table.attributes["foreign_keys"].append(
                        column.attributes["foreign_key"]
                    )

        return table

    # ==========================================================
    # COLUMN
    # ==========================================================

    def _parse_column(self, element: str, table_name: str) -> Optional[Column]:
        parts = element.split()
        if not parts:
            return None

        name = parts[0].strip('"')
        data_type = parts[1].upper() if len(parts) > 1 else "UNKNOWN"
        upper = element.upper()

        attributes: Dict[str, Any] = {
            "definition": element,
            "data_type": data_type,
            "table": table_name,
            "is_primary_key": "PRIMARY KEY" in upper,
            "is_unique": "UNIQUE" in upper and "PRIMARY KEY" not in upper,
            "not_null": "NOT NULL" in upper,
        }

        # COLUMN-LEVEL FOREIGN KEY
        fk_match = re.search(
            r"REFERENCES\s+([A-Za-z0-9_\.]+)\s*\(([^)]+)\)",
            element,
            re.IGNORECASE,
        )

        if fk_match:
            ref_full = fk_match.group(1)
            ref_col = fk_match.group(2).strip()

            ref_schema, ref_table = self._split_qualified_name(ref_full)

            attributes["foreign_key"] = {
                "referenced_schema": ref_schema,
                "referenced_table": ref_table,
                "referenced_column": ref_col,
            }

        return Column(
            id=0,
            name=name,
            schema=None,
            data_type=data_type,
            attributes=attributes,
        )

    # ==========================================================
    # TABLE-LEVEL FK
    # ==========================================================

    def _parse_table_level_fk(self, element: str) -> Optional[Dict[str, Any]]:
        m = re.search(
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+([A-Za-z0-9_\.]+)\s*\(([^)]+)\)",
            element,
            re.IGNORECASE,
        )
        if not m:
            return None

        col = m.group(1).strip()
        ref_full = m.group(2)
        ref_col = m.group(3).strip()

        ref_schema, ref_table = self._split_qualified_name(ref_full)

        return {
            "column": col,
            "referenced_schema": ref_schema,
            "referenced_table": ref_table,
            "referenced_column": ref_col,
        }

    # ==========================================================
    # HELPERS
    # ==========================================================

    def _split_elements(self, body: str) -> List[str]:
        parts = []
        depth = 0
        current = []

        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

            if ch == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
            else:
                current.append(ch)

        tail = "".join(current).strip()
        if tail:
            parts.append(tail)

        return parts

    def _split_qualified_name(self, full_name: str):
        if "." in full_name:
            schema, name = full_name.split(".", 1)
            return schema.strip('"'), name.strip('"')
        return "public", full_name.strip('"')
