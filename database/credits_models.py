"""Models for credit wallets, ledger and PIX topups.

Keep it compact (<280 lines).
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from .models import Base


class CreditWallet(Base):
    __tablename__ = "credit_wallets"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, unique=True, index=True)
    balance_cents = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (Index("idx_credit_wallet_admin", "admin_id", unique=True),)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"))
    user_telegram_id = Column(BigInteger)

    # type: 'credit' or 'debit'
    entry_type = Column(String(8), nullable=False)
    category = Column(
        String(24), nullable=False
    )  # text_input/output/cached/whisper/topup
    amount_cents = Column(Integer, nullable=False)  # positive magnitude
    note = Column(String(128))

    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        CheckConstraint("entry_type IN ('credit','debit')", name="ck_ledger_type"),
        Index("idx_ledger_admin_ts", "admin_id", "created_at"),
        Index("idx_ledger_admin_bot", "admin_id", "bot_id"),
    )


class CreditTopup(Base):
    __tablename__ = "credit_topups"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"))

    # PushinPay
    transaction_id = Column(String(128), nullable=False, unique=True)
    qr_code = Column(Text, nullable=False)
    qr_code_base64 = Column(Text)
    value_cents = Column(Integer, nullable=False)

    status = Column(
        String(16), nullable=False, default="created"
    )  # created|paid|expired
    credited_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_topup_admin_status", "admin_id", "status"),
        Index("idx_topup_tx", "transaction_id", unique=True),
    )


__all__ = ["CreditWallet", "CreditLedger", "CreditTopup"]
