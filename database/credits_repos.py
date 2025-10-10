"""Repositories for credit models (wallet, ledger, topups)."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, Tuple

from sqlalchemy import func

from .credits_models import CreditLedger, CreditTopup, CreditWallet
from .repos import SessionLocal


class CreditWalletRepository:
    @staticmethod
    def get_or_create_sync(admin_id: int) -> CreditWallet:
        with SessionLocal() as session:
            wallet = (
                session.query(CreditWallet)
                .filter(CreditWallet.admin_id == admin_id)
                .first()
            )
            if not wallet:
                wallet = CreditWallet(admin_id=admin_id, balance_cents=0)
                session.add(wallet)
                session.commit()
                session.refresh(wallet)
            return wallet

    @staticmethod
    def get_balance_cents_sync(admin_id: int) -> int:
        with SessionLocal() as session:
            row = (
                session.query(CreditWallet.balance_cents)
                .filter(CreditWallet.admin_id == admin_id)
                .first()
            )
            return int(row[0]) if row else 0

    @staticmethod
    def add_balance_sync(admin_id: int, delta_cents: int) -> int:
        with SessionLocal() as session:
            wallet = (
                session.query(CreditWallet)
                .filter(CreditWallet.admin_id == admin_id)
                .with_for_update(nowait=False)
                .first()
            )
            if not wallet:
                wallet = CreditWallet(admin_id=admin_id, balance_cents=0)
                session.add(wallet)
                session.flush()
            wallet.balance_cents = int(wallet.balance_cents) + int(delta_cents)
            if wallet.balance_cents < 0:
                wallet.balance_cents = 0
            session.commit()
            return int(wallet.balance_cents)


class CreditLedgerRepository:
    @staticmethod
    def add_entry_sync(
        admin_id: int,
        entry_type: str,
        category: str,
        amount_cents: int,
        bot_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> CreditLedger:
        with SessionLocal() as session:
            entry = CreditLedger(
                admin_id=admin_id,
                entry_type=entry_type,
                category=category,
                amount_cents=int(amount_cents),
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                note=note,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    @staticmethod
    def debit_if_enough_balance_sync(
        admin_id: int,
        amount_cents: int,
        category: str,
        bot_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> bool:
        amount_cents = int(amount_cents)
        if amount_cents <= 0:
            return True
        with SessionLocal() as session:
            wallet = (
                session.query(CreditWallet)
                .filter(CreditWallet.admin_id == admin_id)
                .with_for_update(nowait=False)
                .first()
            )
            if not wallet or int(wallet.balance_cents) < amount_cents:
                return False
            wallet.balance_cents = int(wallet.balance_cents) - amount_cents
            entry = CreditLedger(
                admin_id=admin_id,
                entry_type="debit",
                category=category,
                amount_cents=amount_cents,
                bot_id=bot_id,
                user_telegram_id=user_telegram_id,
                note=note,
            )
            session.add(entry)
            session.commit()
            return True

    @staticmethod
    def credit_sync(
        admin_id: int, amount_cents: int, category: str = "topup", note: str = None
    ) -> int:
        amount_cents = int(amount_cents)
        with SessionLocal() as session:
            wallet = (
                session.query(CreditWallet)
                .filter(CreditWallet.admin_id == admin_id)
                .with_for_update(nowait=False)
                .first()
            )
            if not wallet:
                wallet = CreditWallet(admin_id=admin_id, balance_cents=0)
                session.add(wallet)
                session.flush()
            wallet.balance_cents = int(wallet.balance_cents) + amount_cents
            entry = CreditLedger(
                admin_id=admin_id,
                entry_type="credit",
                category=category,
                amount_cents=amount_cents,
                note=note,
            )
            session.add(entry)
            session.commit()
            return int(wallet.balance_cents)

    @staticmethod
    def exists_by_note_sync(admin_id: int, note: str) -> bool:
        with SessionLocal() as session:
            row = (
                session.query(CreditLedger.id)
                .filter(CreditLedger.admin_id == admin_id, CreditLedger.note == note)
                .first()
            )
            return row is not None

    @staticmethod
    def summarize_spend_by_bot_sync(
        admin_id: int, start_day: date, end_day: date, limit: int = 5
    ) -> List[Tuple[int, int]]:
        with SessionLocal() as session:
            query = (
                session.query(CreditLedger.bot_id, func.sum(CreditLedger.amount_cents))
                .filter(CreditLedger.admin_id == admin_id)
                .filter(CreditLedger.entry_type == "debit")
                .filter(
                    CreditLedger.created_at
                    >= datetime.combine(start_day, datetime.min.time())
                )
                .filter(
                    CreditLedger.created_at
                    <= datetime.combine(end_day, datetime.max.time())
                )
                .filter(CreditLedger.bot_id.isnot(None))
                .group_by(CreditLedger.bot_id)
                .order_by(func.sum(CreditLedger.amount_cents).desc())
                .limit(limit)
            )
            return [(row[0], int(row[1])) for row in query.all()]


class CreditTopupRepository:
    @staticmethod
    def create_sync(
        admin_id: int,
        value_cents: int,
        transaction_id: str,
        qr_code: str,
        qr_code_base64: str = None,
        bot_id: Optional[int] = None,
    ) -> CreditTopup:
        with SessionLocal() as session:
            topup = CreditTopup(
                admin_id=admin_id,
                bot_id=bot_id,
                value_cents=int(value_cents),
                transaction_id=transaction_id,
                qr_code=qr_code,
                qr_code_base64=qr_code_base64,
                status="created",
            )
            session.add(topup)
            session.commit()
            session.refresh(topup)
            return topup

    @staticmethod
    def get_by_id_sync(topup_id: int) -> Optional[CreditTopup]:
        with SessionLocal() as session:
            return session.query(CreditTopup).filter(CreditTopup.id == topup_id).first()

    @staticmethod
    def get_by_tx_sync(transaction_id: str) -> Optional[CreditTopup]:
        with SessionLocal() as session:
            return (
                session.query(CreditTopup)
                .filter(CreditTopup.transaction_id == transaction_id)
                .first()
            )

    @staticmethod
    def update_status_sync(topup_id: int, status: str) -> bool:
        with SessionLocal() as session:
            topup = (
                session.query(CreditTopup).filter(CreditTopup.id == topup_id).first()
            )
            if not topup:
                return False
            topup.status = status
            session.commit()
            return True

    @staticmethod
    def mark_credited_sync(topup_id: int) -> bool:
        with SessionLocal() as session:
            topup = (
                session.query(CreditTopup).filter(CreditTopup.id == topup_id).first()
            )
            if not topup:
                return False
            topup.status = "paid"
            topup.credited_at = datetime.utcnow()
            session.commit()
            return True

    @staticmethod
    def list_recent_by_admin_sync(admin_id: int, limit: int = 5) -> List[CreditTopup]:
        with SessionLocal() as session:
            query = (
                session.query(CreditTopup)
                .filter(CreditTopup.admin_id == admin_id)
                .order_by(CreditTopup.created_at.desc())
                .limit(limit)
            )
            return list(query.all())


__all__ = [
    "CreditWalletRepository",
    "CreditLedgerRepository",
    "CreditTopupRepository",
]
