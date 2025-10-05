"""
Scheduler para agendamento de upsells
"""

from datetime import datetime, timedelta

from database.repos import UpsellRepository, UserUpsellHistoryRepository


class UpsellScheduler:
    """Gerencia agendamento de upsells"""

    @staticmethod
    async def calculate_send_time(last_payment_time: datetime, schedule) -> datetime:
        """
        Calcula quando enviar baseado no agendamento

        Args:
            last_payment_time: Timestamp do último pagamento
            schedule: Objeto UpsellSchedule

        Returns:
            datetime de quando enviar
        """
        if schedule.is_immediate:
            return datetime.utcnow()

        # Calcular delta
        delta = timedelta(
            days=schedule.days_after,
            hours=schedule.hours,
            minutes=schedule.minutes,
        )

        return last_payment_time + delta

    @staticmethod
    async def get_pending_upsells(current_time: datetime):
        """
        Busca upsells prontos para envio

        Returns:
            Lista de tuplas (user_telegram_id, bot_id, upsell_id)
        """
        # TODO: Implementar query complexa que:
        # 1. Busca UserUpsellHistory onde sent_at is NULL
        # 2. Junta com UpsellSchedule
        # 3. Calcula send_time baseado em último pagamento + schedule
        # 4. Filtra onde send_time <= current_time
        # Por enquanto, retorna vazio (será implementado em detalhes)
        return []

    @staticmethod
    def get_pending_upsells_sync(current_time: datetime):
        """Versão síncrona para workers"""
        # TODO: Implementar versão síncrona
        return []

    @staticmethod
    async def schedule_next_upsell(user_id: int, bot_id: int):
        """
        Agenda próximo upsell após pagamento

        Cria registro em UserUpsellHistory com sent_at=NULL
        para que seja enviado quando chegar o tempo
        """
        # Buscar próximo upsell não enviado
        next_upsell = await UpsellRepository.get_next_pending_upsell(bot_id, user_id)

        if not next_upsell:
            return None

        # Verificar se já tem registro
        has_received = await UserUpsellHistoryRepository.has_received_upsell(
            bot_id, user_id, next_upsell.id
        )

        if has_received:
            return None

        # Criar registro com sent_at=NULL (será enviado depois)
        from database.models import UserUpsellHistory
        from database.repos import SessionLocal

        with SessionLocal() as session:
            history = UserUpsellHistory(
                bot_id=bot_id,
                user_telegram_id=user_id,
                upsell_id=next_upsell.id,
                sent_at=None,  # Será preenchido quando enviar
            )
            session.add(history)
            session.commit()
            return history

    @staticmethod
    def schedule_next_upsell_sync(user_id: int, bot_id: int):
        """Versão síncrona"""
        from database.models import UserUpsellHistory
        from database.repos import SessionLocal

        # Buscar próximo
        next_upsell = UpsellRepository.get_next_pending_upsell_sync(bot_id, user_id)

        if not next_upsell:
            return None

        # Criar registro
        with SessionLocal() as session:
            # Verificar se já existe
            existing = (
                session.query(UserUpsellHistory)
                .filter(
                    UserUpsellHistory.bot_id == bot_id,
                    UserUpsellHistory.user_telegram_id == user_id,
                    UserUpsellHistory.upsell_id == next_upsell.id,
                )
                .first()
            )

            if existing:
                return existing

            history = UserUpsellHistory(
                bot_id=bot_id,
                user_telegram_id=user_id,
                upsell_id=next_upsell.id,
                sent_at=None,
            )
            session.add(history)
            session.commit()
            return history

    @staticmethod
    async def get_user_last_payment_time(user_id: int, bot_id: int) -> datetime:
        """Busca timestamp do último pagamento"""
        return await UserUpsellHistoryRepository.get_last_payment_time(bot_id, user_id)
