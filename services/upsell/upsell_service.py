"""
Serviço principal de gerenciamento de Upsells
"""

from database.repos import (
    UpsellAnnouncementBlockRepository,
    UpsellDeliverableBlockRepository,
    UpsellPhaseConfigRepository,
    UpsellRepository,
    UserUpsellHistoryRepository,
)


class UpsellService:
    """Serviço para gerenciar lógica de upsells"""

    @staticmethod
    async def get_upsells_by_bot(bot_id: int):
        """Lista todos os upsells de um bot"""
        return await UpsellRepository.get_upsells_by_bot(bot_id)

    @staticmethod
    async def is_upsell_complete(upsell_id: int) -> bool:
        """
        Verifica se upsell está 100% configurado

        Regras:
        - Pelo menos 1 bloco de anúncio
        - Pelo menos 1 bloco de entrega
        - Fase configurada
        - Valor configurado
        - Agendamento configurado (já criado por padrão)
        """
        # Verificar blocos de anúncio
        announcement_count = await UpsellAnnouncementBlockRepository.count_blocks(
            upsell_id
        )
        if announcement_count == 0:
            return False

        # Verificar blocos de entrega
        deliverable_count = await UpsellDeliverableBlockRepository.count_blocks(
            upsell_id
        )
        if deliverable_count == 0:
            return False

        # Verificar fase
        phase_config = await UpsellPhaseConfigRepository.get_phase_config(upsell_id)
        if not phase_config:
            return False

        # Verificar valor
        upsell = await UpsellRepository.get_upsell_by_id(upsell_id)
        if not upsell or not upsell.value:
            return False

        # Para upsell #1, verificar trigger também
        if upsell.is_pre_saved and not upsell.upsell_trigger:
            return False

        # Agendamento é criado automaticamente, não precisa verificar
        return True

    @staticmethod
    def is_upsell_complete_sync(upsell_id: int) -> bool:
        """Versão síncrona para workers"""
        from database.repos import (
            UpsellAnnouncementBlockRepository,
            UpsellDeliverableBlockRepository,
            UpsellPhaseConfigRepository,
            UpsellRepository,
        )

        # Buscar upsell
        upsell = UpsellRepository.get_upsell_by_id_sync(upsell_id)
        if not upsell or not upsell.value:
            return False

        # Verificar blocos
        announcement_blocks = (
            UpsellAnnouncementBlockRepository.get_blocks_by_upsell_sync(upsell_id)
        )
        if not announcement_blocks:
            return False

        deliverable_blocks = UpsellDeliverableBlockRepository.get_blocks_by_upsell_sync(
            upsell_id
        )
        if not deliverable_blocks:
            return False

        # Verificar fase
        phase_config = UpsellPhaseConfigRepository.get_phase_config_sync(upsell_id)
        if not phase_config:
            return False

        # Para upsell #1, verificar trigger
        if upsell.is_pre_saved and not upsell.upsell_trigger:
            return False

        return True

    @staticmethod
    async def get_next_upsell_for_user(user_id: int, bot_id: int):
        """Busca próximo upsell que usuário deve receber"""
        return await UpsellRepository.get_next_pending_upsell(bot_id, user_id)

    @staticmethod
    async def mark_upsell_sent(user_id: int, bot_id: int, upsell_id: int):
        """Marca upsell como enviado"""
        return await UserUpsellHistoryRepository.mark_sent(bot_id, user_id, upsell_id)

    @staticmethod
    async def can_receive_upsell(user_id: int, bot_id: int) -> bool:
        """
        Verifica se usuário pode receber upsells

        Regra: Precisa ter feito pelo menos 1 pagamento
        """
        # Verificar se tem histórico de upsell (já pagou oferta principal)
        history = await UserUpsellHistoryRepository.get_user_history(bot_id, user_id)
        return len(history) > 0

    @staticmethod
    async def create_default_upsell(bot_id: int):
        """Cria upsell #1 pré-salvo ao criar bot"""
        return await UpsellRepository.create_default_upsell(bot_id)

    @staticmethod
    async def validate_trigger(
        bot_id: int, trigger: str, exclude_upsell_id: int = None
    ) -> dict:
        """
        Valida unicidade do trigger

        Returns:
            dict: {"valid": bool, "error": str}
        """
        if not trigger or len(trigger) < 3:
            return {"valid": False, "error": "Trigger deve ter pelo menos 3 caracteres"}

        # Verificar se contém apenas caracteres válidos
        if not trigger.replace("-", "").replace("_", "").isalnum():
            return {
                "valid": False,
                "error": "Trigger deve conter apenas letras, números, hífen e underscore",
            }

        # Buscar upsells do bot
        upsells = await UpsellRepository.get_upsells_by_bot(bot_id)

        # Verificar se trigger já existe em outro upsell
        for upsell in upsells:
            if upsell.id != exclude_upsell_id and upsell.upsell_trigger == trigger:
                return {
                    "valid": False,
                    "error": f"Trigger '{trigger}' já está em uso no upsell '{upsell.name}'",
                }

        return {"valid": True, "error": None}
