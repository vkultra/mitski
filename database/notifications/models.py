"""Models específicos para o sistema de notificações de vendas."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from database.models import Base


class NotificationSettings(Base):
    """Configuração de canal de notificação por usuário e, opcionalmente, bot."""

    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(
        Integer,
        ForeignKey("bots.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    channel_id = Column(BigInteger, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "owner_user_id", "bot_id", name="uq_notification_settings_owner_bot"
        ),
        Index(
            "idx_notification_settings_owner_enabled",
            "owner_user_id",
            "enabled",
        ),
    )


class SaleNotification(Base):
    """Registro de notificações de vendas enviadas ou evitadas."""

    __tablename__ = "sale_notifications"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(128), nullable=False)
    provider = Column(String(32), nullable=False, default="", server_default="")
    owner_user_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    is_upsell = Column(Boolean, nullable=False, default=False, server_default="false")
    amount_cents = Column(Integer)
    currency = Column(String(8), nullable=False, default="BRL", server_default="BRL")
    buyer_user_id = Column(BigInteger)
    buyer_username = Column(String(64))
    bot_username = Column(String(64))
    origin = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="pending", server_default="pending")
    error = Column(Text)
    notified_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_sale_notifications_transaction",
        ),
        Index("idx_sale_notifications_owner_bot", "owner_user_id", "bot_id"),
    )


__all__ = ["NotificationSettings", "SaleNotification"]
