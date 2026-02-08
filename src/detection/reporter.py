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
import time


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
      При экспорте в text используем conflicts.list как основной источник.
    """

    # Константы для уровней критичности (должны совпадать с ConflictLevel из base.py)
    LEVEL_CRITICAL = "CRITICAL"
    LEVEL_HIGH = "HIGH"
    LEVEL_MEDIUM = "MEDIUM"
    LEVEL_LOW = "LOW"

    DEFAULT_LEVEL_ORDER = [LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_MEDIUM, LEVEL_LOW]

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

        # Убедимся, что уровни нормализованы к верхнему регистру
        conflicts_by_level = {k.upper(): v for k, v in conflicts_by_level.items()}

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

        # Определяем, есть ли критические конфликты (с учётом нормализации регистра)
        has_critical_conflicts = self._count_level(conflicts_list, self.LEVEL_CRITICAL) > 0
        critical_conflicts_count = self._count_level(conflicts_list, self.LEVEL_CRITICAL)

        report = {
            "metadata": metadata,
            "summary": {
                "has_conflicts": bool(summary.get("has_conflicts", len(conflicts_list) > 0)),
                "has_critical_conflicts": bool(
                    summary.get("has_critical_conflicts", has_critical_conflicts)
                ),
                "total_conflicts": int(summary.get("total_conflicts", len(conflicts_list))),
                "critical_conflicts": int(
                    summary.get("critical_conflicts", critical_conflicts_count)
                ),
                "merge_blocked": bool(summary.get("merge_blocked", has_critical_conflicts)),
            },

            # основной список
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
            "level": self.LEVEL_CRITICAL,
            "message": f"Ошибка обработки: {error_message}",
            "details": {"error_type": error_type},
        }

        conflicts_by_rule = {"SYSTEM": 1}
        conflicts_by_level = {self.LEVEL_CRITICAL: 1}

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
            },
            "conflicts": [conflict],
            "conflicts_structured": {
                "list": [conflict],
                "by_rule": conflicts_by_rule,
                "by_level": conflicts_by_level,
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

        # Получаем конфликты из правильного места
        conflicts_struct = report.get("conflicts_structured", {})
        if conflicts_struct and "list" in conflicts_struct:
            conflicts = conflicts_struct["list"]
        else:
            # fallback для обратной совместимости
            conflicts = report.get("conflicts", [])
            if isinstance(conflicts, dict) and "list" in conflicts:
                conflicts = conflicts["list"]

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
        out.append("")

        if not conflicts:
            out.append("КОНФЛИКТОВ НЕ ОБНАРУЖЕНО")
        else:
            out.append("КОНФЛИКТЫ:")

            # Группируем конфликты по правилам
            conflicts_by_rule = report.get("conflicts_structured", {}).get("by_rule", {})
            if conflicts_by_rule:
                out.append("\nПО ПРАВИЛАМ:")
                for rule_id, count in sorted(conflicts_by_rule.items()):
                    rule_name = ""
                    for conflict in conflicts[:5]:  # Ищем имя правила в первых конфликтах
                        if conflict.get("rule") == rule_id and "rule_name" in conflict:
                            rule_name = conflict["rule_name"]
                            break
                    out.append(f"  {rule_id}: {count} конфликтов ({rule_name})")

            # Группируем конфликты по уровням
            grouped = self._group_by_level(conflicts)
            for lvl in self.DEFAULT_LEVEL_ORDER:
                items = grouped.get(lvl, [])
                if not items:
                    continue

                # Эмодзи для уровней
                emoji = {
                    self.LEVEL_CRITICAL: "🛑",
                    self.LEVEL_HIGH: "⚠️",
                    self.LEVEL_MEDIUM: "🔶",
                    self.LEVEL_LOW: "ℹ️"
                }.get(lvl, "")

                out.append(f"\n{emoji} [{lvl}] ({len(items)}):")
                for i, c in enumerate(items[:10], 1):
                    message = c.get('message', 'N/A')
                    # Обрезаем длинные сообщения
                    if len(message) > 100:
                        message = message[:97] + "..."
                    out.append(f"  {i}. {message}")

                    # Добавляем детали, если есть
                    details = c.get("details", {})
                    obj = self._format_object_from_details(details)
                    if obj:
                        out.append(f"     Объект: {obj}")

                    # Добавляем правило
                    rule = c.get("rule", "")
                    if rule:
                        out.append(f"     Правило: {rule}")

                if len(items) > 10:
                    out.append(f"     ... и ещё {len(items) - 10} конфликтов")

        perf = report.get("performance", {})
        if perf:
            out.append("\n" + "=" * 70)
            out.append("ПРОИЗВОДИТЕЛЬНОСТЬ:")
            out.append(f"  Общее время: {perf.get('total_time', 0):.4f}с")
            out.append(f"  Парсинг: {perf.get('parsing_time', 0):.4f}с")
            out.append(f"  Построение графов: {perf.get('graph_building_time', 0):.4f}с")
            out.append(f"  Сравнение: {perf.get('comparison_time', 0):.4f}с")
            out.append(f"  Проверка правил: {perf.get('rule_application_time', 0):.4f}с")

        hyp = report.get("hypothesis_validation")
        if hyp:
            out.append("\n" + "=" * 70)
            out.append("ПРОВЕРКА ГИПОТЕЗЫ:")
            out.append(f"  Статус: {'ПОДТВЕРЖДЕНА' if hyp.get('is_confirmed') else 'НЕ ПОДТВЕРЖДЕНА'}")
            out.append(f"  Интерпретация: {hyp.get('interpretation', 'N/A')}")

        out.append("\n" + "=" * 70)
        return "\n".join(out)

    def _export_markdown(self, report: Dict[str, Any]) -> str:
        """Экспорт в Markdown формат."""
        summary = report.get("summary", {}) or {}
        metadata = report.get("metadata", {}) or {}

        conflicts_struct = report.get("conflicts_structured", {})
        if conflicts_struct and "list" in conflicts_struct:
            conflicts = conflicts_struct["list"]
        else:
            conflicts = report.get("conflicts", [])
            if isinstance(conflicts, dict) and "list" in conflicts:
                conflicts = conflicts["list"]

        out: List[str] = []
        out.append("# Отчёт об обнаружении конфликтов миграций")
        out.append("")

        out.append("## Метаданные")
        out.append(f"- **Время анализа:** {metadata.get('timestamp', 'N/A')}")
        out.append(f"- **Версия инструмента:** {metadata.get('version', 'N/A')}")
        out.append(f"- **Инструмент:** {metadata.get('tool', 'N/A')}")
        out.append("")

        out.append("## Сводка")
        out.append(f"- **Обнаружено конфликтов:** {summary.get('total_conflicts', 0)}")
        out.append(f"- **Критических конфликтов:** {summary.get('critical_conflicts', 0)}")
        out.append(f"- **Слияние заблокировано:** {'**ДА**' if summary.get('merge_blocked') else 'нет'}")
        out.append("")

        if not conflicts:
            out.append("## Конфликты")
            out.append("Конфликтов не обнаружено.")
        else:
            out.append("## Конфликты")

            # Статистика по правилам
            conflicts_by_rule = report.get("conflicts_structured", {}).get("by_rule", {})
            if conflicts_by_rule:
                out.append("### По правилам")
                for rule_id, count in sorted(conflicts_by_rule.items()):
                    rule_name = ""
                    for conflict in conflicts[:5]:
                        if conflict.get("rule") == rule_id and "rule_name" in conflict:
                            rule_name = conflict["rule_name"]
                            break
                    out.append(f"- **{rule_id}**: {count} конфликтов ({rule_name})")
                out.append("")

            # Конфликты по уровням
            grouped = self._group_by_level(conflicts)
            for lvl in self.DEFAULT_LEVEL_ORDER:
                items = grouped.get(lvl, [])
                if not items:
                    continue

                emoji = {
                    self.LEVEL_CRITICAL: "🛑",
                    self.LEVEL_HIGH: "⚠️",
                    self.LEVEL_MEDIUM: "🔶",
                    self.LEVEL_LOW: "ℹ️"
                }.get(lvl, "")

                out.append(f"### {emoji} {lvl} ({len(items)})")

                for i, c in enumerate(items, 1):
                    message = c.get('message', 'N/A')
                    out.append(f"{i}. **{message}**")

                    details = c.get("details", {})
                    obj = self._format_object_from_details(details)
                    if obj:
                        out.append(f"   - Объект: `{obj}`")

                    rule = c.get("rule", "")
                    if rule:
                        out.append(f"   - Правило: {rule}")

                    # Добавляем дополнительные детали
                    for key, value in details.items():
                        if key not in ['object', 'table', 'column', 'constraint']:
                            out.append(f"   - {key}: {value}")

                out.append("")

        return "\n".join(out)

    def _export_html(self, report: Dict[str, Any]) -> str:
        """Экспорт в HTML формат."""
        summary = report.get("summary", {}) or {}
        metadata = report.get("metadata", {}) or {}

        conflicts_struct = report.get("conflicts_structured", {})
        if conflicts_struct and "list" in conflicts_struct:
            conflicts = conflicts_struct["list"]
        else:
            conflicts = report.get("conflicts", [])
            if isinstance(conflicts, dict) and "list" in conflicts:
                conflicts = conflicts["list"]

        html = []
        html.append("""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Отчёт о конфликтах миграций</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
                h2 { color: #555; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
                h3 { color: #777; }
                .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }
                .conflict { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .critical { border-left: 5px solid #dc3545; }
                .high { border-left: 5px solid #fd7e14; }
                .medium { border-left: 5px solid #ffc107; }
                .low { border-left: 5px solid #28a745; }
                .details { background: #f8f9fa; padding: 10px; margin-top: 10px; border-radius: 3px; }
                .metadata { color: #666; font-size: 0.9em; }
                .no-conflicts { color: #28a745; font-weight: bold; }
                .blocked { color: #dc3545; font-weight: bold; }
                table { border-collapse: collapse; width: 100%; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
        """)

        html.append(f"<h1>Отчёт об обнаружении конфликтов миграций</h1>")

        # Метаданные
        html.append("<div class='metadata'>")
        html.append(f"<p><strong>Время анализа:</strong> {metadata.get('timestamp', 'N/A')}</p>")
        html.append(f"<p><strong>Версия инструмента:</strong> {metadata.get('version', 'N/A')}</p>")
        html.append(f"<p><strong>Инструмент:</strong> {metadata.get('tool', 'N/A')}</p>")
        html.append("</div>")

        # Сводка
        html.append("<div class='summary'>")
        html.append("<h2>Сводка</h2>")
        html.append(f"<p><strong>Обнаружено конфликтов:</strong> {summary.get('total_conflicts', 0)}</p>")
        html.append(f"<p><strong>Критических конфликтов:</strong> {summary.get('critical_conflicts', 0)}</p>")

        merge_blocked = summary.get('merge_blocked', False)
        blocked_html = '<span class="blocked">ДА</span>' if merge_blocked else 'нет'
        html.append(f"<p><strong>Слияние заблокировано:</strong> {blocked_html}</p>")
        html.append("</div>")

        # Конфликты
        html.append("<h2>Конфликты</h2>")

        if not conflicts:
            html.append('<p class="no-conflicts">Конфликтов не обнаружено.</p>')
        else:
            # Статистика по правилам
            conflicts_by_rule = report.get("conflicts_structured", {}).get("by_rule", {})
            if conflicts_by_rule:
                html.append("<h3>Статистика по правилам</h3>")
                html.append("<table>")
                html.append("<tr><th>Правило</th><th>Количество</th><th>Описание</th></tr>")

                for rule_id, count in sorted(conflicts_by_rule.items()):
                    rule_name = ""
                    rule_desc = ""
                    for conflict in conflicts[:5]:
                        if conflict.get("rule") == rule_id:
                            rule_name = conflict.get("rule_name", "")
                            rule_info = conflict.get("rule_info", {})
                            rule_desc = rule_info.get("description", "")
                            break

                    html.append(f"<tr>")
                    html.append(f"<td><strong>{rule_id}</strong></td>")
                    html.append(f"<td>{count}</td>")
                    html.append(f"<td>{rule_name}<br><small>{rule_desc}</small></td>")
                    html.append(f"</tr>")

                html.append("</table>")

            # Детали конфликтов
            html.append("<h3>Детали конфликтов</h3>")

            grouped = self._group_by_level(conflicts)
            for lvl in self.DEFAULT_LEVEL_ORDER:
                items = grouped.get(lvl, [])
                if not items:
                    continue

                level_class = lvl.lower()
                emoji = {
                    self.LEVEL_CRITICAL: "🛑",
                    self.LEVEL_HIGH: "⚠️",
                    self.LEVEL_MEDIUM: "🔶",
                    self.LEVEL_LOW: "ℹ️"
                }.get(lvl, "")

                html.append(f"<h4>{emoji} {lvl} ({len(items)})</h4>")

                for i, c in enumerate(items, 1):
                    message = c.get('message', 'N/A')
                    rule = c.get("rule", "")

                    html.append(f'<div class="conflict {level_class}">')
                    html.append(f'<p><strong>{i}. {message}</strong></p>')
                    html.append(f'<p><small>Правило: {rule}</small></p>')

                    details = c.get("details", {})
                    if details:
                        html.append('<div class="details">')
                        html.append("<p><strong>Детали:</strong></p>")
                        html.append("<ul>")
                        for key, value in details.items():
                            html.append(f"<li><strong>{key}:</strong> {value}</li>")
                        html.append("</ul>")
                        html.append("</div>")

                    html.append("</div>")

        html.append("""
        </body>
        </html>
        """)

        return "\n".join(html)

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

        Уровни нормализуются к верхнему регистру.
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
            # Нормализуем уровни к верхнему регистру
            by_level = {str(k).upper(): int(v) for k, v in by_level.items()}

            # Если списки пустые, но статистика есть, заполним их
            if not conflicts_list and by_rule:
                # Не можем восстановить список конфликтов из статистики
                pass

            return conflicts_list, by_rule, by_level

        # 2) если список конфликтов
        if isinstance(conflicts, list):
            conflicts_list = [self._to_plain_dict(x) for x in conflicts]

            for c in conflicts_list:
                r = str(c.get("rule", "N/A"))
                lvl = str(c.get("level", self.LEVEL_MEDIUM)).upper()

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
        critical = self._count_level(conflicts, self.LEVEL_CRITICAL)
        return {
            "has_conflicts": total > 0,
            "has_critical_conflicts": critical > 0,
            "total_conflicts": total,
            "critical_conflicts": critical,
            "merge_blocked": critical > 0,
        }

    def _default_recommendation(self, conflicts: List[Dict[str, Any]]) -> str:
        if not conflicts:
            return "Конфликтов не обнаружено. Слияние можно выполнять."
        if self._count_level(conflicts, self.LEVEL_CRITICAL) > 0:
            return "Обнаружены критические конфликты. Слияние следует заблокировать до устранения."
        if self._count_level(conflicts, self.LEVEL_HIGH) > 0:
            return "Есть высокорисковые конфликты. Рекомендуется проверить и согласовать изменения перед merge."
        return "Есть некритичные конфликты. Рекомендуется выборочная проверка."

    def _count_level(self, conflicts: List[Dict[str, Any]], level: str) -> int:
        """
        Считает конфликты заданного уровня.
        Сравнивает нормализованные (нижний регистр) значения.
        """
        lvl_normalized = level.lower()
        count = 0
        for c in conflicts:
            conflict_level = str(c.get("level", "")).lower()
            if conflict_level == lvl_normalized:
                count += 1
        return count

    def _group_by_level(self, conflicts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Группирует конфликты по уровням.
        Уровни нормализуются к верхнему регистру.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for c in conflicts:
            lvl = str(c.get("level", self.LEVEL_MEDIUM)).upper()
            grouped.setdefault(lvl, []).append(c)

        # Убедимся, что все уровни из DEFAULT_LEVEL_ORDER присутствуют (пустые списки)
        for lvl in self.DEFAULT_LEVEL_ORDER:
            if lvl not in grouped:
                grouped[lvl] = []

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
