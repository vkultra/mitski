"""Repository para preferências de áudio por administrador"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.telemetry import logger

from .models import AudioPreference
from .repos import SessionLocal

DEFAULT_AUDIO_REPLY: str = "Recebemos seu áudio. Em breve entraremos em contato."


class AudioPreferencesRepository:
    """Operações de persistência para AudioPreference"""

    @staticmethod
    def get_by_admin_id(admin_id: int) -> Optional[AudioPreference]:
        with SessionLocal() as session:
            return (
                session.query(AudioPreference)
                .filter(AudioPreference.admin_id == admin_id)
                .first()
            )

    @staticmethod
    def get_or_create(admin_id: int) -> AudioPreference:
        with SessionLocal() as session:
            pref = (
                session.query(AudioPreference)
                .filter(AudioPreference.admin_id == admin_id)
                .first()
            )
            if pref:
                return pref

            # Persistir Whisper como padrão (alinhado ao menu/UX)
            pref = AudioPreference(
                admin_id=admin_id,
                mode="whisper",
                default_reply=DEFAULT_AUDIO_REPLY,
            )
            session.add(pref)
            session.commit()
            session.refresh(pref)
            logger.info(
                "Audio preferences created",
                extra={"admin_id": admin_id, "mode": pref.mode},
            )
            return pref

    @staticmethod
    def update_mode(admin_id: int, mode: str) -> AudioPreference:
        with SessionLocal() as session:
            pref = (
                session.query(AudioPreference)
                .filter(AudioPreference.admin_id == admin_id)
                .first()
            )
            if not pref:
                pref = AudioPreference(
                    admin_id=admin_id,
                    mode=mode,
                    default_reply=DEFAULT_AUDIO_REPLY,
                )
                session.add(pref)
            else:
                pref.mode = mode
                pref.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(pref)
            logger.info(
                "Audio preferences mode updated",
                extra={"admin_id": admin_id, "mode": pref.mode},
            )
            return pref

    @staticmethod
    def update_default_reply(admin_id: int, reply: str) -> AudioPreference:
        with SessionLocal() as session:
            pref = (
                session.query(AudioPreference)
                .filter(AudioPreference.admin_id == admin_id)
                .first()
            )
            if not pref:
                # Se não existir, criar já com modo Whisper como padrão
                pref = AudioPreference(
                    admin_id=admin_id,
                    default_reply=reply,
                    mode="whisper",
                )
                session.add(pref)
            else:
                pref.default_reply = reply
                pref.updated_at = datetime.utcnow()

            session.commit()
            session.refresh(pref)
            logger.info(
                "Audio default reply updated",
                extra={"admin_id": admin_id, "reply_length": len(pref.default_reply)},
            )
            return pref
