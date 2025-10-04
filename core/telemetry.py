"""
Logging estruturado e telemetria
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger

# Padrões de secrets para redação
SECRET_PATTERNS = [
    re.compile(r"\d{10}:[A-Za-z0-9_-]{35}"),  # Telegram token
    re.compile(r"[A-Za-z0-9_\-]{32,}"),  # Chaves genéricas longas
]


class RedactSecrets(logging.Filter):
    """Filtro para remover secrets dos logs"""

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern in SECRET_PATTERNS:
                record.msg = pattern.sub("[REDACTED]", record.msg)
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON customizado"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = record.created
        log_record["level"] = record.levelname
        log_record["service"] = "telegram-bot-manager"
        log_record["logger"] = record.name


# Configuração do logger
logger = logging.getLogger("telegram_bot_manager")
logger.setLevel(logging.INFO)

# Handler para console (stdout)
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomJsonFormatter())
console_handler.addFilter(RedactSecrets())
logger.addHandler(console_handler)

# Handler para arquivo (logs/app.log)
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, "app.log"),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
)
file_handler.setFormatter(CustomJsonFormatter())
file_handler.addFilter(RedactSecrets())
logger.addHandler(file_handler)
