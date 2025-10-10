"""Database models dedicated to statistics, ROI and telemetry."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)

from .models import Base


class StartEvent(Base):
    """Stores every /start command issued to a managed bot."""

    __tablename__ = "start_events"

    id = Column(Integer, primary_key=True)
    owner_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    occurred_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("idx_start_events_owner_day", "owner_id", "occurred_at"),
        Index("idx_start_events_bot_day", "bot_id", "occurred_at"),
    )


class PhaseTransitionEvent(Base):
    """Tracks IA phase transitions for abandonment metrics."""

    __tablename__ = "phase_transition_events"

    id = Column(Integer, primary_key=True)
    owner_id = Column(BigInteger, nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    from_phase_id = Column(
        Integer,
        ForeignKey("ai_phases.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_phase_id = Column(
        Integer, ForeignKey("ai_phases.id", ondelete="CASCADE"), nullable=False
    )
    occurred_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("idx_phase_events_owner_day", "owner_id", "occurred_at"),
        Index("idx_phase_events_bot_day", "bot_id", "occurred_at"),
        Index("idx_phase_events_phase", "to_phase_id", "occurred_at"),
    )


class DailyCostEntry(Base):
    """User defined cost entries used to calculate ROI."""

    __tablename__ = "daily_cost_entries"

    id = Column(Integer, primary_key=True)
    owner_id = Column(BigInteger, nullable=False, index=True)
    scope = Column(String(16), nullable=False)  # 'general' | 'bot'
    bot_id = Column(
        Integer,
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=True,
    )
    day = Column(Date, nullable=False, index=True)
    amount_cents = Column(BigInteger, nullable=False)
    note = Column(String(128))
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        CheckConstraint("scope IN ('general', 'bot')", name="ck_cost_scope"),
        Index("idx_cost_owner_day", "owner_id", "day"),
        Index("idx_cost_owner_scope", "owner_id", "scope", "bot_id"),
    )


__all__ = [
    "StartEvent",
    "PhaseTransitionEvent",
    "DailyCostEntry",
]
