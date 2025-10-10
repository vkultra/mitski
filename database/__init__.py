"""Database package."""

# Importa modelos adicionais para garantir registro no metadata global
from .credits_models import CreditLedger, CreditTopup, CreditWallet  # noqa: F401
from .notifications import models as notifications_models  # noqa: F401
