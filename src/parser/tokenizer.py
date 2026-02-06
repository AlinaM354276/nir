from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class TokenType(str, Enum):
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    QUOTED_IDENTIFIER = "QUOTED_IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"

    TYPE = "TYPE"
    CONSTRAINT = "CONSTRAINT"

    OPERATOR = "OPERATOR"
    COMMA = "COMMA"
    DOT = "DOT"
    SEMICOLON = "SEMICOLON"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"

    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"
    COMMENT = "COMMENT"

    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    position: int

    def normalize(self) -> str:
        return self.value.lower()

    def is_identifier(self) -> bool:
        return self.type in (TokenType.IDENTIFIER, TokenType.QUOTED_IDENTIFIER)

    def is_keyword(self) -> bool:
        return self.type == TokenType.KEYWORD


class SQLTokenizer:
    """
    Лексический анализатор DDL
    Делает токены + позиционную разметку (line/column/position).
    """

    KEYWORDS = {
        "CREATE", "ALTER", "DROP", "TABLE", "SCHEMA", "COLUMN",
        "CONSTRAINT", "PRIMARY", "KEY", "FOREIGN", "REFERENCES",
        "UNIQUE", "CHECK", "DEFAULT", "NOT", "NULL",
        "ADD", "RENAME", "TO", "IF", "EXISTS",
        "ON", "DELETE", "UPDATE", "CASCADE", "RESTRICT", "SET",
    }

    TYPE_KEYWORDS = {
        # базовые + расширенные
        "SMALLINT", "INTEGER", "INT", "BIGINT",
        "REAL", "DOUBLE", "DOUBLE PRECISION", "FLOAT", "FLOAT4", "FLOAT8",
        "NUMERIC", "DECIMAL",
        "CHAR", "CHARACTER", "VARCHAR", "TEXT", "CHARACTER VARYING",
        "BOOLEAN", "BOOL",
        "DATE", "TIME", "TIMESTAMP", "TIMESTAMPTZ", "TIMETZ", "INTERVAL",
        "JSON", "JSONB", "UUID", "XML",
        "BYTEA", "OID", "MONEY",
    }

    CONSTRAINT_KEYWORDS = {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "REFERENCES", "DEFAULT", "NOT", "NULL"}

    # NEWLINE ДО WHITESPACE, иначе \s+ “съест” \n и NEWLINE никогда не появится
    _TOKEN_SPECS: List[Tuple[str, TokenType]] = [
        (r"--[^\n]*", TokenType.COMMENT),
        (r"/\*[\s\S]*?\*/", TokenType.COMMENT),  # безопаснее, чем DOTALL на .*?
        (r"\r\n|\r|\n", TokenType.NEWLINE),
        (r"[ \t\f\v]+", TokenType.WHITESPACE),

        (r"'(?:[^']|'')*'", TokenType.STRING),
        (r'"(?:[^"]|"")*"', TokenType.QUOTED_IDENTIFIER),

        (r"\d+\.\d+", TokenType.NUMBER),
        (r"\d+", TokenType.NUMBER),

        (r"<=|>=|<>|!=|~=|!~\*|!~|~\*|~|\|\||\|/|\|\|/|@>|<@|&&|<<|>>", TokenType.OPERATOR),
        (r"[=<>!@#%^&|*/+\-]", TokenType.OPERATOR),

        (r",", TokenType.COMMA),
        (r"\.", TokenType.DOT),
        (r";", TokenType.SEMICOLON),
        (r"\(", TokenType.LPAREN),
        (r"\)", TokenType.RPAREN),

        (r"[A-Za-z_][A-Za-z0-9_]*", TokenType.IDENTIFIER),
    ]

    def __init__(self, preserve_case: bool = False):
        self.preserve_case = preserve_case

        parts = []
        for i, (pat, _) in enumerate(self._TOKEN_SPECS):
            parts.append(f"(?P<T{i}>{pat})")
        self._master = re.compile("|".join(parts), re.IGNORECASE)

        # отображение group name -> TokenType
        self._group_to_type = {f"T{i}": t for i, (_, t) in enumerate(self._TOKEN_SPECS)}

    def tokenize(self, sql_text: str) -> List[Token]:
        """
        Быстрая токенизация (один проход).
        Возвращает токены без WHITESPACE/COMMENT/NEWLINE
        """
        tokens: List[Token] = []
        line = 1
        col = 1

        pos = 0
        n = len(sql_text)

        while pos < n:
            m = self._master.match(sql_text, pos)
            if not m:
                # гарантируем прогресс: 1 символ как OPERATOR, чтобы не зависнуть
                value = sql_text[pos]
                tok = Token(TokenType.OPERATOR, value, line, col, pos)
                tokens.append(tok)
                pos += 1
                col += 1
                continue

            if m.end() == pos:
                # защита от “пустого” совпадения (иначе бесконечный цикл)
                raise ValueError(f"Tokenizer matched empty token at position {pos}")

            group = m.lastgroup
            assert group is not None
            base_type = self._group_to_type[group]
            value = m.group(group)

            # координаты обновляем ДО фильтрации
            if base_type == TokenType.NEWLINE:
                line += 1
                col = 1
            else:
                col += len(value)

            pos = m.end()

            # фильтрация шума
            if base_type in (TokenType.WHITESPACE, TokenType.COMMENT, TokenType.NEWLINE):
                continue

            precise = self._determine_token_type(base_type, value)

            # нормализация идентификаторов
            if precise == TokenType.IDENTIFIER and not self.preserve_case:
                value = value.lower()

            # нормализация keyword (по желанию можно вверх)
            if precise == TokenType.KEYWORD and not self.preserve_case:
                value = value.upper()

            tokens.append(Token(precise, value, line, col - len(value), pos - len(value)))

        tokens.append(Token(TokenType.EOF, "", line, col, pos))
        return tokens

    def _determine_token_type(self, base_type: TokenType, value: str) -> TokenType:
        if base_type != TokenType.IDENTIFIER:
            return base_type

        u = value.upper()

        if u in self.KEYWORDS:
            return TokenType.KEYWORD

        # типы данных
        if u in self.TYPE_KEYWORDS:
            return TokenType.TYPE

        if u in self.CONSTRAINT_KEYWORDS:
            return TokenType.CONSTRAINT

        return TokenType.IDENTIFIER

