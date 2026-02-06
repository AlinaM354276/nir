"""
parser package — модуль парсинга DDL
"""

from .normalizer import SQLNormalizer
from .sql_parser import SQLParser
from .tokenizer import SQLTokenizer, Token, TokenType

from .ddl_operations import (
    OperationType,
    DDLOperation,
    OperationAnalyzer,
    CreateTableOperation,
    DropTableOperation,
    AlterTableOperation,
    AddColumnOperation,
    DropColumnOperation,
    AlterColumnOperation,
    AddConstraintOperation,
    DropConstraintOperation,
    RenameTableOperation,
    RenameColumnOperation,
)

__all__ = [
    "SQLNormalizer",
    "SQLParser",
    "SQLTokenizer",
    "Token",
    "TokenType",
    "OperationType",
    "DDLOperation",
    "OperationAnalyzer",
    "CreateTableOperation",
    "DropTableOperation",
    "AlterTableOperation",
    "AddColumnOperation",
    "DropColumnOperation",
    "AlterColumnOperation",
    "AddConstraintOperation",
    "DropConstraintOperation",
    "RenameTableOperation",
    "RenameColumnOperation",
]

