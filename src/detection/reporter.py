"""
reporter.py

Генерация и экспорт отчётов для системы обнаружения конфликтов миграций.

Цели:
- единый контракт отчёта (metadata/summary/conflicts/analysis/performance)
- устойчивость к разным форматам result/conflicts (list vs dict{list,...})
- экспорт: json / text / markdown / html

Важно:
- reporter НЕ должен зависеть от конкретных правил R1..R7.
- reporter должен работать с тем, что возвращает RuleRegistry.apply_all(...)
  и/или с тем, что формирует orchestrator.
"""

from __future__ import annotations

from dataclasses import is_dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import html


class Reporter:
    """
    Построитель и экспортёр отчётов.

    Конвенции:
    - Уровни критичности: CRITICAL/HIGH/MEDIUM/LOW (строки).
    - report['conflicts'] в итоговом отчёте хранится как dict:
        {
          "list": [...],
          "by_rule": {...},
          "by_level": {...},
          "total": N
        }
      При экспорте в text/markdown/html мы используем conflicts.list как основной источник.
    """

    DEFAULT_LEVEL_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.max_conflicts_in_report = int(self.config.get("max_conflicts_in_report", 100))
        self.tool_name = self.config.get("tool_name", "PostgreSQL Migration Conflict Detector")
        self.version = self.config.get("version", "1.0.0")
        self.author = self.config.get("author", "Студентка СПбПУ")

    # ---------------------------------------------------------------------
    # 1) BUILD REPORT
    # ---------------------------------------------------------------------

    def build_report(
        self,
        *,
        result: Optional[Dict[str, Any]] = None,
        delta: Any = None,
        graph_a: Any = None,
        graph_b: Any = None,
        performance: Optional[Dict[str, Any]] = None,
        metadata_overrides: Optional[Dict[str, Any]] = None,
        hypothesis_validation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Формирует единый отчёт.

        Args:
            result: результат от RuleRegistry.apply_all(...)
                   ожидаемые ключи: conflicts, statistics, summary
            delta: объект Delta (опционально)
            graph_a / graph_b: SchemaGraph (опционально)
            performance: словарь с метриками времени (опционально)
            metadata_overrides: доп. поля metadata
            hypothesis_validation: блок проверки гипотезы (опционально)

        Returns:
            Единый отчёт-словарь.
        """
        result = result or {}

        raw_conflicts = result.get("conflicts", [])
        conflicts_list, conflicts_by_rule, conflicts_by_level = self._normalize_conflicts(raw_conflicts)

        stats = result.get("statistics", {}) or {}
        summary = result.get("summary", {}) or {}

        # если статистика не пришла — построим минимум сами
        if not conflicts_by_rule and isinstance(stats, dict):
            conflicts_by_rule = stats.get("by_rule", {}) or {}
        if not conflicts_by_level and isinstance(stats, dict):
            conflicts_by_level = stats.get("by_level", {}) or {}

        # если summary не пришёл — построим сами
        if not summary:
            summary = self._build_summary_from_conflicts(conflicts_list)

        # analyses
        delta_summary = {}
        if delta is not None and hasattr(delta, "summary"):
            try:
                delta_summary = delta.summary()
            except Exception:
                delta_summary = {}

        graphs_info = {}
        if graph_a is not None:
            graphs_info["schema_a"] = {
                "vertices": getattr(graph_a, "vertices", None) and len(graph_a.vertices) or 0,
                "edges": getattr(graph_a, "edges", None) and len(graph_a.edges) or 0,
            }
        if graph_b is not None:
            graphs_info["schema_b"] = {
                "vertices": getattr(graph_b, "vertices", None) and len(graph_b.vertices) or 0,
                "edges": getattr(graph_b, "edges", None) and len(graph_b.edges) or 0,
            }

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "version": self.version,
            "tool": self.tool_name,
            "author": self.author,
        }
        if metadata_overrides:
            metadata.update(metadata_overrides)

        report = {
            "metadata": metadata,
            "summary": {
                "has_conflicts": bool(summary.get("has_conflicts", len(conflicts_list) > 0)),
                "has_critical_conflicts": bool(
                    summary.get("has_critical_conflicts", self._count_level(conflicts_list, "CRITICAL") > 0)
                ),
                "total_conflicts": int(summary.get("total_conflicts", len(conflicts_list))),
                "critical_conflicts": int(
                    summary.get("critical_conflicts", self._count_level(conflicts_list, "CRITICAL"))),
                "recommendation": summary.get("recommendation", self._default_recommendation(conflicts_list)),
                "merge_blocked": bool(summary.get("merge_blocked", self._count_level(conflicts_list, "CRITICAL") > 0)),
            },

            # тесты ожидают список
            "conflicts": conflicts_list[: self.max_conflicts_in_report],

            # структурированная форма
            "conflicts_structured": {
                "list": conflicts_list[: self.max_conflicts_in_report],
                "by_rule": conflicts_by_rule,
                "by_level": conflicts_by_level,
                "total": len(conflicts_list),
                "truncated": len(conflicts_list) > self.max_conflicts_in_report,
            },

            "analysis": {
                "delta": delta_summary,
                "graphs": graphs_info,
                "rules_applied": stats.get("rules_applied", stats.get("total_rules", 0)),
            },
            "performance": performance or result.get("performance", {}),
        }

        if hypothesis_validation is not None:
            report["hypothesis_validation"] = hypothesis_validation
        elif "hypothesis_validation" in result:
            report["hypothesis_validation"] = result["hypothesis_validation"]

        return report

    def build_error_report(self, error_message: str, *, error_type: str = "ProcessingError") -> Dict[str, Any]:
        """Формирует отчёт об ошибке, блокирующий merge."""
        conflict = {
            "rule": "SYSTEM",
            "level": "CRITICAL",
            "message": f"Ошибка обработки: {error_message}",
            "details": {"error_type": error_type},
            "recommendation": "Исправить ошибку и повторить анализ.",
        }
        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "status": "ERROR",
                "version": self.version,
                "tool": self.tool_name,
                "author": self.author,
            },
            "error": {"message": error_message, "type": error_type},
            "summary": {
                "has_conflicts": True,
                "has_critical_conflicts": True,
                "total_conflicts": 1,
                "critical_conflicts": 1,
                "merge_blocked": True,
                "recommendation": "Ошибка анализа блокирует слияние до устранения причины.",
            },
            "conflicts": {
                "list": [conflict],
                "by_rule": {"SYSTEM": 1},
                "by_level": {"CRITICAL": 1},
                "total": 1,
                "truncated": False,
            },
            "analysis": {},
            "performance": {},
        }

    # ---------------------------------------------------------------------
    # 2) EXPORT
    # ---------------------------------------------------------------------

    def export(
        self,
        report: Dict[str, Any],
        *,
        format: str = "json",
        output_file: Optional[Union[str, Path]] = None
    ) -> str:
        """
        Экспорт отчёта в заданном формате.

        Args:
            report: отчёт
            format: json | text | markdown | html
            output_file: если задан — сохраняет в файл и возвращает пустую строку

        Returns:
            строка отчёта (если output_file=None)
        """
        fmt = (format or "json").lower().strip()

        if fmt == "json":
            output = self._export_json(report)
        elif fmt == "text":
            output = self._export_text(report)
        elif fmt == "markdown":
            output = self._export_markdown(report)
        elif fmt == "html":
            output = self._export_html(report)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}. Доступные: json, text, markdown, html")

        if output_file:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
            return ""
        return output

    def _export_json(self, report: Dict[str, Any]) -> str:
        return json.dumps(report, indent=2, ensure_ascii=False)

    def _export_text(self, report: Dict[str, Any]) -> str:
        summary = report.get("summary", {}) or {}
        metadata = report.get("metadata", {}) or {}
        conflicts = self._conflicts_list(report)

        out: List[str] = []
        out.append("=" * 70)
        out.append("ОТЧЁТ ОБ ОБНАРУЖЕНИИ КОНФЛИКТОВ МИГРАЦИЙ")
        out.append("=" * 70)
        out.append("")
        out.append("МЕТАДАННЫЕ:")
        out.append(f"  Время анализа: {metadata.get('timestamp', 'N/A')}")
        out.append(f"  Версия инструмента: {metadata.get('version', 'N/A')}")
        out.append(f"  Инструмент: {metadata.get('tool', 'N/A')}")
        out.append("")
        out.append("СВОДКА:")
        out.append(f"  Обнаружено конфликтов: {summary.get('total_conflicts', 0)}")
        out.append(f"  Критических конфликтов: {summary.get('critical_conflicts', 0)}")
        out.append(f"  Слияние заблокировано: {'ДА' if summary.get('merge_blocked') else 'НЕТ'}")
        out.append(f"  Рекомендация: {summary.get('recommendation', 'N/A')}")
        out.append("")

        if not conflicts:
            out.append("КОНФЛИКТОВ НЕ ОБНАРУЖЕНО")
        else:
            out.append("КОНФЛИКТЫ:")
            grouped = self._group_by_level(conflicts)
            for lvl in self.DEFAULT_LEVEL_ORDER:
                items = grouped.get(lvl, [])
                if not items:
                    continue
                out.append(f"\n[{lvl}] ({len(items)}):")
                for i, c in enumerate(items[:10], 1):
                    out.append(f"  {i}. {c.get('message', 'N/A')}")
                    details = c.get("details", {})
                    obj = self._format_object_from_details(details)
                    if obj:
                        out.append(f"     Объект: {obj}")
                if len(items) > 10:
                    out.append(f"     ... и ещё {len(items) - 10} конфликтов")

        perf = report.get("performance", {})
        if perf:
            out.append("\nПРОИЗВОДИТЕЛЬНОСТЬ:")
            out.append(f"  Общее время: {perf.get('total_time', 0):.2f}с")
            out.append(f"  Парсинг: {perf.get('parsing_time', 0):.2f}с")
            out.append(f"  Построение графов: {perf.get('graph_building_time', 0):.2f}с")
            out.append(f"  Сравнение: {perf.get('comparison_time', 0):.2f}с")
            out.append(f"  Проверка правил: {perf.get('rule_application_time', 0):.2f}с")

        hyp = report.get("hypothesis_validation")
        if hyp:
            out.append("\nПРОВЕРКА ГИПОТЕЗЫ:")
            out.append(f"  Статус: {'ПОДТВЕРЖДЕНА' if hyp.get('is_confirmed') else 'НЕ ПОДТВЕРЖДЕНА'}")
            out.append(f"  Интерпретация: {hyp.get('interpretation', 'N/A')}")

        out.append("\n" + "=" * 70)
        return "\n".join(out)

    from typing import Any, Dict, List

    def _export_markdown(self, report: Dict[str, Any]) -> str:
        summary = report.get("summary", {}) or {}
        conflicts = report.get("conflicts", []) or []

        out: List[str] = []

        out.append("# Отчёт об обнаружении конфликтов миграций\n")

        # --- Сводка ---
        out.append("## Сводка\n")
        out.append(f"- **Всего конфликтов:** {summary.get('total_conflicts', 0)}")
        out.append(
            f"- **Есть критические конфликты:** "
            f"{'ДА' if summary.get('has_critical_conflicts') else 'НЕТ'}"
        )
        out.append(
            f"- **Слияние заблокировано:** "
            f"{'ДА' if summary.get('merge_blocked') else 'НЕТ'}\n"
        )

        # --- Нет конфликтов ---
        if not conflicts:
            out.append("## Конфликтов не обнаружено\n")
            out.append(
                "Изменения схемы не нарушают формализованные зависимости между объектами "
                "в рамках реализованной модели."
            )
            return "\n".join(out)

        # --- Таблица конфликтов ---
        out.append("## Обнаруженные конфликты\n")
        out.append("| Уровень | Правило | Описание |")
        out.append("|---|---|---|")

        for c in conflicts[:50]:
            level = c.get("level", "unknown")
            rule = c.get("rule", "N/A")
            message = (c.get("message") or "—").replace("\n", " ")

            if len(message) > 120:
                message = message[:120] + "…"

            out.append(f"| {level} | {rule} | {message} |")

        if len(conflicts) > 50:
            out.append(f"\n> Показаны первые 50 конфликтов из {len(conflicts)}.\n")

        return "\n".join(out)

    def _export_html(self, report: Dict[str, Any]) -> str:
        summary = report.get("summary", {}) or {}
        conflicts = report.get("conflicts", []) or []

        def esc(x: Any) -> str:
            return html.escape(str(x))

        # --- Таблица конфликтов ---
        rows = []
        for c in conflicts[:100]:
            rows.append(
                "<tr>"
                f"<td>{esc(c.get('level', 'unknown'))}</td>"
                f"<td>{esc(c.get('rule', 'N/A'))}</td>"
                f"<td>{esc(c.get('message', '—'))}</td>"
                "</tr>"
            )

        table = (
            "<table>"
            "<thead><tr>"
            "<th>Уровень</th>"
            "<th>Правило</th>"
            "<th>Описание</th>"
            "</tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
            if rows
            else "<p><strong>Конфликтов не обнаружено.</strong></p>"
        )

        html_doc = f"""<!doctype html>
    <html lang="ru">
    <head>
      <meta charset="utf-8">
      <title>Отчёт о конфликтах миграций</title>
      <style>
        body {{ font-family: Arial, sans-serif; margin: 24px; }}
        h1, h2 {{ margin-bottom: 8px; }}
        .summary {{ margin-bottom: 18px; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; background: #eee; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; }}
        th {{ background: #f3f3f3; }}
      </style>
    </head>
    <body>

    <h1>Отчёт об обнаружении конфликтов миграций</h1>

    <div class="summary">
      <h2>Сводка</h2>
      <div>Всего конфликтов: <span class="badge">{esc(summary.get('total_conflicts', 0))}</span></div>
      <div>Критические конфликты: <span class="badge">
        {esc('ДА' if summary.get('has_critical_conflicts') else 'НЕТ')}
      </span></div>
      <div>Слияние заблокировано: <span class="badge">
        {esc('ДА' if summary.get('merge_blocked') else 'НЕТ')}
      </span></div>
    </div>

    <h2>Конфликты</h2>
    {table}

    </body>
    </html>"""

        return html_doc

    # ---------------------------------------------------------------------
    # 3) INTERNAL HELPERS
    # ---------------------------------------------------------------------

    def _conflicts_list(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Возвращает список конфликтов из report независимо от того,
        хранится ли report['conflicts'] как list или как dict{list:...}.
        """
        c = report.get("conflicts", [])
        if isinstance(c, list):
            return c
        if isinstance(c, dict):
            lst = c.get("list", [])
            return lst if isinstance(lst, list) else []
        return []

    def _normalize_conflicts(
        self, conflicts: Any
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int], Dict[str, int]]:
        """
        Нормализует conflicts в:
        - conflicts_list: list[dict]
        - by_rule: dict[rule_id -> count]
        - by_level: dict[level -> count]
        """
        conflicts_list: List[Dict[str, Any]] = []
        by_rule: Dict[str, int] = {}
        by_level: Dict[str, int] = {}

        # 1) если уже dict со статистикой (как в orchestrator)
        if isinstance(conflicts, dict):
            lst = conflicts.get("list", [])
            if isinstance(lst, list):
                conflicts_list = [self._to_plain_dict(x) for x in lst]
            by_rule = conflicts.get("by_rule", {}) or {}
            by_level = conflicts.get("by_level", {}) or {}
            # гарантируем int
            by_rule = {str(k): int(v) for k, v in by_rule.items()}
            by_level = {str(k): int(v) for k, v in by_level.items()}
            return conflicts_list, by_rule, by_level

        # 2) если список конфликтов
        if isinstance(conflicts, list):
            conflicts_list = [self._to_plain_dict(x) for x in conflicts]

            for c in conflicts_list:
                r = str(c.get("rule", "N/A"))
                lvl = str(c.get("level", "MEDIUM")).upper()

                by_rule[r] = by_rule.get(r, 0) + 1
                by_level[lvl] = by_level.get(lvl, 0) + 1

            return conflicts_list, by_rule, by_level

        # 3) неизвестный формат
        return [], {}, {}

    def _to_plain_dict(self, x: Any) -> Dict[str, Any]:
        """Преобразует dataclass/объект в dict, если возможно."""
        if x is None:
            return {}
        if isinstance(x, dict):
            return x
        if is_dataclass(x):
            return asdict(x)
        # fallback: пытаемся взять __dict__
        if hasattr(x, "__dict__"):
            return dict(x.__dict__)
        return {"value": str(x)}

    def _build_summary_from_conflicts(self, conflicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(conflicts)
        critical = self._count_level(conflicts, "CRITICAL")
        return {
            "has_conflicts": total > 0,
            "has_critical_conflicts": critical > 0,
            "total_conflicts": total,
            "critical_conflicts": critical,
            "merge_blocked": critical > 0,
            "recommendation": self._default_recommendation(conflicts),
        }

    def _default_recommendation(self, conflicts: List[Dict[str, Any]]) -> str:
        if not conflicts:
            return "Конфликтов не обнаружено. Слияние можно выполнять."
        if self._count_level(conflicts, "CRITICAL") > 0:
            return "Обнаружены критические конфликты. Слияние следует заблокировать до устранения."
        if self._count_level(conflicts, "HIGH") > 0:
            return "Есть высокорисковые конфликты. Рекомендуется проверить и согласовать изменения перед merge."
        return "Есть некритичные конфликты. Рекомендуется выборочная проверка."

    def _count_level(self, conflicts: List[Dict[str, Any]], level: str) -> int:
        lvl = level.upper()
        return sum(1 for c in conflicts if str(c.get("level", "")).upper() == lvl)

    def _group_by_level(self, conflicts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for c in conflicts:
            lvl = str(c.get("level", "MEDIUM")).upper()
            grouped.setdefault(lvl, []).append(c)
        return grouped

    def _format_object_from_details(self, details: Any) -> str:
        """
        Пытается извлечь “объект” из details: table/column/constraint/etc.
        Это эвристика для удобства чтения отчёта.
        """
        if not isinstance(details, dict):
            return ""

        # самый частый случай: table + column
        if "table" in details and "column" in details:
            return f"{details.get('table')}.{details.get('column')}"

        # иногда table alone
        if "table" in details:
            return str(details.get("table"))

        # варианты, встречающиеся в правилах (removed_object, source/target, object/key)
        for k in ("full_column_name", "object", "key", "removed_object", "target", "source"):
            if k in details:
                return str(details.get(k))

        # если передан edge
        edge = details.get("edge")
        if isinstance(edge, dict) and ("from" in edge or "to" in edge):
            return f"{edge.get('from', '?')} -> {edge.get('to', '?')}"

        return ""


__all__ = ["Reporter"]
