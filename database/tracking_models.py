"""Models dedicated to tracking deeplink performance."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)

from .models import Base


class TrackerLink(Base):
    """Represents a tracking deeplink associated with a secondary bot."""

    __tablename__ = "tracker_links"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer,
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(80), nullable=False)
    code = Column(String(32), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("bot_id", "code", name="uq_tracker_code_per_bot"),
        Index("idx_tracker_admin_bot", "admin_id", "bot_id"),
        Index("idx_tracker_active", "bot_id", "is_active"),
    )


class TrackerDailyStat(Base):
    """Aggregated daily metrics for a tracker (starts, sales, revenue)."""

    __tablename__ = "tracker_daily_stats"

    id = Column(Integer, primary_key=True)
    tracker_id = Column(
        Integer,
        ForeignKey("tracker_links.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day = Column(Date, nullable=False)
    starts = Column(Integer, default=0, nullable=False)
    sales = Column(Integer, default=0, nullable=False)
    revenue_cents = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), default=func.now())

    __table_args__ = (
        UniqueConstraint("tracker_id", "day", name="uq_tracker_day"),
        Index("idx_tracker_day", "tracker_id", "day"),
    )


class TrackerAttribution(Base):
    """Stores the mapping between a user and the tracker that brought them."""

    __tablename__ = "tracker_attributions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer,
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_telegram_id = Column(BigInteger, nullable=False)
    tracker_id = Column(
        Integer,
        ForeignKey("tracker_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_seen_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("bot_id", "user_telegram_id", name="uq_tracker_user"),
        Index("idx_tracker_user_tracker", "tracker_id", "bot_id"),
    )


class BotTrackingConfig(Base):
    """Stores per-bot configuration for tracking enforcement."""

    __tablename__ = "bot_tracking_configs"

    bot_id = Column(
        Integer,
        ForeignKey("bots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ignore_untracked_starts = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, onupdate=func.now(), default=func.now())
    last_forced_at = Column(DateTime)

    __table_args__ = (Index("idx_tracking_config_flag", "ignore_untracked_starts"),)


__all__ = [
    "TrackerLink",
    "TrackerDailyStat",
    "TrackerAttribution",
    "BotTrackingConfig",
]
