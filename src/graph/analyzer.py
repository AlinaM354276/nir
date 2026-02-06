from src.comparison.delta import Delta
from src.core.models import ObjectType


class DeltaAnalyzer:
    """
    Анализ дельты изменений.
    Подготавливает данные для применения правил.
    """

    def __init__(self, delta: Delta):
        self.delta = delta

    def modified_columns(self):
        return [
            m for m in self.delta.objects_modified
            if m.before.type == ObjectType.COLUMN
        ]

    def modified_tables(self):
        return [
            m for m in self.delta.objects_modified
            if m.before.type == ObjectType.TABLE
        ]

    def has_type_changes(self) -> bool:
        return any(
            "data_type" in m.changed_fields
            for m in self.modified_columns()
        )

    def has_primary_key_changes(self) -> bool:
        return any(
            "primary_key" in m.changed_fields
            for m in self.modified_tables()
        )

    def summary(self) -> dict:
        """
        Краткая сводка дельты
        """
        return {
            "objects_added": len(self.delta.objects_added),
            "objects_removed": len(self.delta.objects_removed),
            "objects_modified": len(self.delta.objects_modified),
            "type_changes": self.has_type_changes(),
            "pk_changes": self.has_primary_key_changes(),
        }
