"""
Logging estruturado e telemetria
"""
import logging
import re
from pythonjsonlogger import jsonlogger

# Padrões de secrets para redação
SECRET_PATTERNS = [
    re.compile(r'\d{10}:[A-Za-z0-9_-]{35}'),  # Telegram token
    re.compile(r'[A-Za-z0-9_\-]{32,}'),       # Chaves genéricas longas
]


class RedactSecrets(logging.Filter):
    """Filtro para remover secrets dos logs"""

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern in SECRET_PATTERNS:
                record.msg = pattern.sub('[REDACTED]', record.msg)
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON customizado"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = record.created
        log_record['level'] = record.levelname
        log_record['service'] = 'telegram-bot-manager'
        log_record['logger'] = record.name


# Configuração do logger
handler = logging.StreamHandler()
handler.setFormatter(CustomJsonFormatter())
handler.addFilter(RedactSecrets())

logger = logging.getLogger('telegram_bot_manager')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
