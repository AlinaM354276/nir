"""
main.py

Точка входа в систему обнаружения конфликтов миграций PostgreSQL.

Запуск:
    python main.py --a schema_a.sql --b schema_b.sql
    python main.py --a schema_a.sql --b schema_b.sql --format markdown
    python main.py --a schema_a.sql --b schema_b.sql --format html --out report.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.detection.orchestrator import MigrationConflictDetector
from src.detection import Reporter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PostgreSQL Migration Conflict Detector (НИР)"
    )

    parser.add_argument(
        "--a",
        required=True,
        help="SQL-файл исходной схемы (schema A)",
    )

    parser.add_argument(
        "--b",
        required=True,
        help="SQL-файл целевой схемы (schema B)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text", "markdown", "html"],
        default="json",
        help="Формат отчёта (по умолчанию: json)",
    )

    parser.add_argument(
        "--out",
        help="Файл для сохранения отчёта (если не указан — вывод в stdout)",
    )

    return parser.parse_args()


def read_sql_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise RuntimeError(f"Не удалось прочитать файл {path}: {e}")


def main() -> int:
    args = parse_args()

    # --- Чтение SQL ---
    sql_a = read_sql_file(args.a)
    sql_b = read_sql_file(args.b)

    # --- Детектор ---
    detector = MigrationConflictDetector()

    try:
        raw_report = detector.detect(sql_a, sql_b)
    except Exception as e:
        print(f"Критическая ошибка анализа: {e}", file=sys.stderr)
        return 1

    # --- Репортёр ---
    reporter = Reporter({
        "tool_name": "PostgreSQL Migration Conflict Detector",
        "version": "1.0.0",
        "author": "Студентка СПбПУ",
    })

    # --- Экспорт ---
    output = reporter.export(
        raw_report,
        format=args.format,
        output_file=args.out,
    )

    if output:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
