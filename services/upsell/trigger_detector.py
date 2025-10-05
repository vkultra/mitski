"""
Detector de gatilhos de upsell na resposta da IA
"""

from database.repos import UpsellRepository


class TriggerDetector:
    """Detecta triggers de upsell #1 na resposta da IA"""

    @staticmethod
    async def detect_upsell_trigger(bot_id: int, ai_response_text: str):
        """
        Verifica se resposta da IA contém trigger do upsell #1

        Args:
            bot_id: ID do bot
            ai_response_text: Texto da resposta da IA

        Returns:
            upsell_id se encontrado, None caso contrário
        """
        # Buscar upsell #1
        upsell_1 = await UpsellRepository.get_first_upsell(bot_id)

        if not upsell_1 or not upsell_1.upsell_trigger:
            return None

        # Verificar se trigger está presente na resposta (case-sensitive)
        if upsell_1.upsell_trigger in ai_response_text:
            return upsell_1.id

        return None

    @staticmethod
    async def extract_triggers(bot_id: int) -> list:
        """
        Lista todos os triggers ativos de upsells

        Returns:
            Lista de dicts com {upsell_id, trigger}
        """
        upsells = await UpsellRepository.get_upsells_by_bot(bot_id)

        triggers = []
        for upsell in upsells:
            if upsell.upsell_trigger:
                triggers.append(
                    {"upsell_id": upsell.id, "trigger": upsell.upsell_trigger}
                )

        return triggers

    @staticmethod
    def is_trigger_valid(trigger: str) -> bool:
        """
        Valida formato do trigger

        Regras:
        - Mínimo 3 caracteres
        - Sem espaços
        - Apenas letras, números, hífen, underscore
        """
        if not trigger or len(trigger) < 3:
            return False

        if " " in trigger:
            return False

        # Verificar se contém apenas caracteres válidos
        return trigger.replace("-", "").replace("_", "").isalnum()
