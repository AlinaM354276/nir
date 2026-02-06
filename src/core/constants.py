"""
Константы системы обнаружения конфликтов миграций PostgreSQL.
"""

# Версия системы
VERSION = "1.0.0"
AUTHOR = "Студентка СПбПУ"
RESEARCH_TOPIC = "Автоматическое обнаружение структурных конфликтов при слиянии параллельных изменений схемы PostgreSQL"

# Уровни критичности конфликтов
CRITICALITY_LEVELS = {
    'CRITICAL': {
        'value': 0,
        'description': 'Блокирует слияние, требует немедленного вмешательства',
        'color': 'red',
        'emoji': '🛑'
    },
    'HIGH': {
        'value': 1,
        'description': 'Высокий риск, требует внимания перед слиянием',
        'color': 'orange',
        'emoji': '⚠️'
    },
    'MEDIUM': {
        'value': 2,
        'description': 'Средний риск, рекомендуется проверить',
        'color': 'yellow',
        'emoji': '🔶'
    },
    'LOW': {
        'value': 3,
        'description': 'Низкий риск, информационное сообщение',
        'color': 'green',
        'emoji': 'ℹ️'
    }
}


# Типы объектов PostgreSQL
POSTGRES_OBJECT_TYPES = {
    'TABLE': 'table',
    'COLUMN': 'column',
    'INDEX': 'index',
    'VIEW': 'view',
    'SEQUENCE': 'sequence',
    'FUNCTION': 'function',
    'TRIGGER': 'trigger',
    'CONSTRAINT': 'constraint',
    'SCHEMA': 'schema',
    'TYPE': 'type',
    'DOMAIN': 'domain',
    'RULE': 'rule',
    'POLICY': 'policy'
}

# Типы ограничений PostgreSQL
CONSTRAINT_TYPES = {
    'PRIMARY_KEY': 'PRIMARY KEY',
    'FOREIGN_KEY': 'FOREIGN KEY',
    'UNIQUE': 'UNIQUE',
    'CHECK': 'CHECK',
    'NOT_NULL': 'NOT NULL',
    'DEFAULT': 'DEFAULT',
    'EXCLUDE': 'EXCLUDE'
}

# Типы DDL операций
DDL_OPERATION_TYPES = {
    'CREATE': 'create',
    'ALTER': 'alter',
    'DROP': 'drop',
    'TRUNCATE': 'truncate',
    'RENAME': 'rename',
    'COMMENT': 'comment'
}

# Отношения зависимостей между объектами
DEPENDENCY_RELATIONS = {
    'CONTAINS': 'contains',  # Таблица содержит колонку
    'REFERENCES': 'references',  # FK ссылается на таблицу
    'DEPENDS_ON': 'depends_on',  # Индекс зависит от колонки
    'ENFORCED_BY': 'enforced_by',  # Колонка имеет ограничение
    'COMPOSED_OF': 'composed_of',  # Составной ключ из колонок
    'USES': 'uses',  # Представление использует таблицу
    'TRIGGERS': 'triggers',  # Триггер срабатывает на таблице
    'INHERITS': 'inherits',  # Наследование таблиц
    'PARTITION_OF': 'partition_of'  # Партиционирование
}

# Идентификаторы правил обнаружения конфликтов
RULE_IDS = {
    'R1': 'Удаление объекта с существующими зависимостями',
    'R2': 'Несовместимое изменение типа данных',
    'R3': 'FK на несуществующий объект',
    'R4': 'Конфликт именования',
    'R5': 'Нарушение ссылочной целостности при изменении PK',
    'R6': 'Противоречивые ограничения',
    'R7': 'Косвенные конфликты через транзитивные зависимости'
}

# Коды ошибок
ERROR_CODES = {
    'PARSING_ERROR': 'P001',
    'GRAPH_BUILDING_ERROR': 'G001',
    'COMPARISON_ERROR': 'C001',
    'RULE_APPLICATION_ERROR': 'R001',
    'VALIDATION_ERROR': 'V001',
    'CONFIGURATION_ERROR': 'C002',
    'IO_ERROR': 'I001',
    'UNKNOWN_ERROR': 'U001'
}

# Ограничения системы
SYSTEM_LIMITS = {
    'MAX_SCHEMA_SIZE': 10000,  # Максимальное количество объектов в схеме
    'MAX_CONFLICTS': 1000,  # Максимальное количество конфликтов в отчёте
    'MAX_CACHE_SIZE': 100,  # Максимальное количество кэшированных результатов
    'MAX_RECURSION_DEPTH': 50,  # Максимальная глубина рекурсии при анализе графа
    'TIMEOUT_SECONDS': 30  # Таймаут выполнения (секунды)
}

# Форматы вывода
OUTPUT_FORMATS = {
    'JSON': 'json',
    'TEXT': 'text',
    'MARKDOWN': 'markdown',
    'HTML': 'html',
    'CSV': 'csv',
    'YAML': 'yaml'
}

# Режимы сравнения
COMPARISON_MODES = {
    'STRICT': 'strict',  # Строгое сравнение (учитывает всё)
    'RELAXED': 'relaxed',  # Ослабленное сравнение (игнорирует некоторые различия)
    'SCHEMA_ONLY': 'schema_only',  # Только сравнение схем (без данных)
    'STRUCTURE_ONLY': 'structure_only'  # Только структура (без имён)
}

# Статусы выполнения
EXECUTION_STATUS = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled',
    'TIMEOUT': 'timeout'
}

# Поддерживаемые версии PostgreSQL
SUPPORTED_POSTGRES_VERSIONS = [
    '12', '13', '14', '15', '16'
]

# Расширения PostgreSQL, которые учитываются при анализе
POSTGRES_EXTENSIONS = [
    'postgis',
    'uuid-ossp',
    'pgcrypto',
    'citext',
    'hstore',
    'ltree'
]

# Конфигурационные параметры по умолчанию
DEFAULT_CONFIG = {
    'general': {
        'verbose': False,
        'debug': False,
        'log_level': 'INFO',
        'cache_enabled': True,
        'parallel_processing': False
    },
    'parser': {
        'normalize_sql': True,
        'remove_comments': True,
        'uppercase_keywords': True,
        'validate_syntax': True
    },
    'comparison': {
        'mode': 'strict',
        'ignore_whitespace': True,
        'ignore_case': False,
        'match_by': 'key'
    },
    'rules': {
        'enabled_rules': ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7'],
        'default_level': 'MEDIUM',
        'apply_order': 'by_criticality'
    },
    'output': {
        'format': 'json',
        'include_details': True,
        'include_recommendations': True,
        'max_conflicts': 100
    }
}

# Матрица совместимости типов (упрощённая)
TYPE_COMPATIBILITY = {
    'INTEGER': ['BIGINT', 'NUMERIC', 'DECIMAL'],
    'BIGINT': ['NUMERIC', 'DECIMAL'],
    'SMALLINT': ['INTEGER', 'BIGINT', 'NUMERIC', 'DECIMAL'],
    'NUMERIC': ['DECIMAL'],
    'DECIMAL': ['NUMERIC'],
    'REAL': ['DOUBLE PRECISION'],
    'VARCHAR': ['TEXT'],
    'CHAR': ['VARCHAR', 'TEXT'],
    'TEXT': ['VARCHAR', 'CHAR'],
    'TIMESTAMP': ['TIMESTAMPTZ'],
    'DATE': ['TIMESTAMP', 'TIMESTAMPTZ'],
    'JSON': ['JSONB'],
    'UUID': ['TEXT', 'VARCHAR']
}

# Несовместимые пары типов (абсолютно несовместимы)
INCOMPATIBLE_TYPE_PAIRS = [
    ('INTEGER', 'VARCHAR'),
    ('NUMERIC', 'TEXT'),
    ('BOOLEAN', 'INTEGER'),
    ('TIMESTAMP', 'INTEGER'),
    ('JSON', 'VARCHAR'),
    ('UUID', 'INTEGER')
]

# Ключевые слова SQL для PostgreSQL
SQL_KEYWORDS = [
    # DDL
    'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME',
    'TABLE', 'VIEW', 'INDEX', 'SEQUENCE', 'FUNCTION',
    'SCHEMA', 'TYPE', 'DOMAIN',

    # Типы данных
    'INTEGER', 'BIGINT', 'SMALLINT', 'SERIAL', 'BIGSERIAL',
    'VARCHAR', 'CHAR', 'TEXT', 'BOOLEAN', 'BOOL',
    'NUMERIC', 'DECIMAL', 'REAL', 'DOUBLE', 'PRECISION',
    'DATE', 'TIMESTAMP', 'TIME', 'INTERVAL',
    'JSON', 'JSONB', 'XML', 'UUID', 'BYTEA',

    # Ограничения
    'CONSTRAINT', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES',
    'UNIQUE', 'CHECK', 'NOT', 'NULL', 'DEFAULT',

    # Модификаторы
    'IF', 'EXISTS', 'CASCADE', 'RESTRICT', 'ONLY',
    'WITH', 'WITHOUT', 'TIME', 'ZONE',

    # Дополнительные
    'ADD', 'COLUMN', 'SET', 'DATA', 'TYPE',
    'RENAME', 'TO', 'OWNER', 'GRANT', 'REVOKE'
]

# Регулярные выражения для парсинга
REGEX_PATTERNS = {
    'TABLE_NAME': r'(?:CREATE|ALTER|DROP)\s+TABLE\s+(?:IF\s+EXISTS\s+)?"?([^\s(]+)"?',
    'COLUMN_DEFINITION': r'"?([^\s,]+)"?\s+([^\s,]+(?:\s*\([^)]+\))?)',
    'FOREIGN_KEY': r'FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+"?([^\s(]+)"?\s*\([^)]+\)',
    'CONSTRAINT_NAME': r'CONSTRAINT\s+"?([^\s]+)"?',
    'DATA_TYPE': r'([A-Z]+(?:\s+[A-Z]+)?)(?:\s*\([^)]+\))?',
    'COMMENT': r'--.*$|/\*.*?\*/'
}

# Метрики качества для оценки системы
QUALITY_METRICS = {
    'PRECISION': 'precision',  # Точность (меньше ложных срабатываний)
    'RECALL': 'recall',  # Полнота (больше обнаруженных конфликтов)
    'F1_SCORE': 'f1_score',  # F1-мера (баланс точности и полноты)
    'EXECUTION_TIME': 'execution_time',
    'MEMORY_USAGE': 'memory_usage',
    'FALSE_POSITIVE_RATE': 'false_positive_rate',
    'FALSE_NEGATIVE_RATE': 'false_negative_rate'
}
