"""
Нормализатор SQL для PostgreSQL DDL.
Приводит SQL к канонической форме для упрощения парсинга.

Гибридный подход:
- грубая текстовая нормализация (regex)
- точная токенная нормализация (через SQLTokenizer)
- разбиение на операторы выполняется безопасно через sqlparse (если доступен)
"""
import re
from typing import List, Dict, Tuple

from .tokenizer import SQLTokenizer, TokenType

try:
    import sqlparse
except Exception:  # pragma: no cover
    sqlparse = None


class SQLNormalizer:
    """
    Нормализатор SQL для PostgreSQL DDL.

    Канонизация:
    1) удаление комментариев (опционально)
    2) приведение ключевых слов к верхнему регистру (опционально)
    3) нормализация пробелов
    4) токенная реконструкция (устойчивее к странному форматированию)
    """

    def __init__(
        self,
        uppercase_keywords: bool = True,
        remove_comments: bool = True,
        normalize_whitespace: bool = True,
        standardize_quotes: bool = True,
    ):
        self.uppercase_keywords = uppercase_keywords
        self.remove_comments = remove_comments
        self.normalize_whitespace = normalize_whitespace
        self.standardize_quotes = standardize_quotes

        # Важно: preserve_case зависит от цели (ключевые слова → upper)
        self.tokenizer = SQLTokenizer(preserve_case=not uppercase_keywords)

        self.patterns = self._compile_patterns()
        self.keyword_patterns = self._compile_keyword_patterns()

    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        patterns: Dict[str, re.Pattern] = {}

        # Комментарии
        patterns["single_line_comment"] = re.compile(r"--[^\n]*")
        patterns["multi_line_comment"] = re.compile(r"/\*.*?\*/", re.DOTALL)

        # Пробелы
        patterns["multiple_spaces"] = re.compile(r"\s+")
        patterns["space_before_comma"] = re.compile(r"\s+,")
        patterns["space_after_comma"] = re.compile(r",\s*")
        patterns["space_before_semicolon"] = re.compile(r"\s+;")

        return patterns

    def _compile_keyword_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """
        стабильные замены для DDL-лексики.
        """
        keywords = [
            # DDL
            (r"\bcreate\b", "CREATE"),
            (r"\btable\b", "TABLE"),
            (r"\balter\b", "ALTER"),
            (r"\bdrop\b", "DROP"),
            (r"\badd\b", "ADD"),
            (r"\bcolumn\b", "COLUMN"),

            # Constraints
            (r"\bconstraint\b", "CONSTRAINT"),
            (r"\bprimary\b", "PRIMARY"),
            (r"\bkey\b", "KEY"),
            (r"\bforeign\b", "FOREIGN"),
            (r"\breferences\b", "REFERENCES"),
            (r"\bunique\b", "UNIQUE"),
            (r"\bcheck\b", "CHECK"),
            (r"\bnot\b", "NOT"),
            (r"\bnull\b", "NULL"),
            (r"\bdefault\b", "DEFAULT"),

            # Multi-word
            (r"\bdouble\s+precision\b", "DOUBLE PRECISION"),
            (r"\bcharacter\s+varying\b", "CHARACTER VARYING"),
            (r"\bif\s+exists\b", "IF EXISTS"),
        ]

        return [(re.compile(p, re.IGNORECASE), repl) for p, repl in keywords]

    def normalize(self, sql_text: str) -> str:
        if not sql_text or not sql_text.strip():
            return sql_text

        normalized = sql_text

        if self.remove_comments:
            normalized = self._remove_comments(normalized)

        if self.uppercase_keywords:
            normalized = self._uppercase_keywords(normalized)

        if self.normalize_whitespace:
            normalized = self._normalize_whitespace(normalized)

        if self.standardize_quotes:
            normalized = self._standardize_quotes(normalized)

        # Токенная нормализация (устойчивость к форматированию)
        normalized = self._token_level_normalization(normalized)

        return normalized.strip()

    def _remove_comments(self, text: str) -> str:
        text = self.patterns["single_line_comment"].sub("", text)
        text = self.patterns["multi_line_comment"].sub("", text)
        return text

    def _uppercase_keywords(self, text: str) -> str:
        result = text
        for pattern, replacement in self.keyword_patterns:
            result = pattern.sub(replacement, result)
        return result

    def _normalize_whitespace(self, text: str) -> str:
        # Сжимаем whitespace
        text = self.patterns["multiple_spaces"].sub(" ", text)
        text = self.patterns["space_before_comma"].sub(",", text)
        text = self.patterns["space_after_comma"].sub(", ", text)
        text = self.patterns["space_before_semicolon"].sub(";", text)
        return text.strip()

    def _standardize_quotes(self, text: str) -> str:
        # Минимально: убираем лишние пробелы внутри кавычек
        text = re.sub(r'"\s+([^"]+?)\s+"', r'"\1"', text)
        text = re.sub(r"'\s+([^']+?)\s+'", r"'\1'", text)
        return text

    def _token_level_normalization(self, text: str) -> str:
        tokens = self.tokenizer.tokenize(text)

        # Обратная совместимость: если у токенизатора есть filter_tokens — используем
        if hasattr(self.tokenizer, "filter_tokens"):
            tokens = self.tokenizer.filter_tokens(tokens)

        tokens = [t for t in tokens if getattr(t, "type", None) != TokenType.EOF]

        if not tokens:
            return ""

        parts: List[str] = []

        for i, tok in enumerate(tokens):
            v = tok.value

            parts.append(v)

            # Решаем, нужен ли пробел после текущего токена
            if i == len(tokens) - 1:
                continue

            next_tok = tokens[i + 1]

            # Не ставим пробел перед некоторыми токенами
            if next_tok.type in (TokenType.COMMA, TokenType.RPAREN, TokenType.DOT, TokenType.SEMICOLON):
                continue

            # Не ставим пробел после '(' и '.'
            if tok.type in (TokenType.LPAREN, TokenType.DOT):
                continue

            # После запятой нужен пробел
            if tok.type == TokenType.COMMA:
                parts.append(" ")
                continue

            # Общий случай
            parts.append(" ")

        normalized = "".join(parts)

        # Финальное сжатие пробелов
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def split_statements(self, sql_text: str) -> List[str]:
        """
        Делит SQL на операторы.
        В гибриде корректнее использовать sqlparse.split().
        """
        normalized = self.normalize(sql_text)

        if not normalized.strip():
            return []

        if sqlparse is not None:
            stmts = [s.strip() for s in sqlparse.split(normalized) if s.strip()]
            return stmts

        return [s.strip() for s in normalized.split(";") if s.strip()]

    def is_ddl_statement(self, sql_text: str) -> bool:
        normalized = self.normalize(sql_text).upper()
        return any(normalized.startswith(k + " ") for k in ("CREATE", "ALTER", "DROP", "TRUNCATE"))

    def get_statement_type(self, sql_text: str) -> str:
        normalized = self.normalize(sql_text).upper()
        if normalized.startswith("CREATE TABLE"):
            return "CREATE_TABLE"
        if normalized.startswith("ALTER TABLE"):
            return "ALTER_TABLE"
        if normalized.startswith("DROP TABLE"):
            return "DROP_TABLE"
        if normalized.startswith("CREATE INDEX"):
            return "CREATE_INDEX"
        if normalized.startswith("CREATE VIEW"):
            return "CREATE_VIEW"
        return "UNKNOWN"
