"""
Serviço de configuração de IA
"""

from core.telemetry import logger
from database.repos import AIConfigRepository, AIPhaseRepository


class AIConfigService:
    """Gerencia configurações de IA dos bots"""

    @staticmethod
    async def get_or_create_config(bot_id: int):
        """
        Busca ou cria configuração padrão de IA

        Args:
            bot_id: ID do bot

        Returns:
            BotAIConfig
        """
        config = await AIConfigRepository.get_by_bot_id(bot_id)

        if not config:
            config = await AIConfigRepository.create_config(
                bot_id=bot_id,
                model_type="reasoning",
                general_prompt="Você é um assistente útil e educado.",
                temperature="0.7",
                max_tokens=2000,
                is_enabled=True,
            )
            logger.info("AI config created", extra={"bot_id": bot_id})

        return config

    @staticmethod
    async def update_general_prompt(bot_id: int, prompt: str) -> bool:
        """
        Atualiza prompt de comportamento geral

        Args:
            bot_id: ID do bot
            prompt: Novo prompt geral

        Returns:
            True se atualizou com sucesso
        """
        success = await AIConfigRepository.update_general_prompt(bot_id, prompt)

        if success:
            logger.info(
                "General prompt updated",
                extra={"bot_id": bot_id, "prompt_length": len(prompt)},
            )

        return success

    @staticmethod
    async def toggle_model(bot_id: int) -> str:
        """
        Alterna entre reasoning e non-reasoning

        Args:
            bot_id: ID do bot

        Returns:
            Novo tipo de modelo ("reasoning" ou "non-reasoning")
        """
        config = await AIConfigRepository.get_by_bot_id(bot_id)

        if not config:
            raise ValueError("AI config not found for this bot")

        new_type = "non-reasoning" if config.model_type == "reasoning" else "reasoning"

        await AIConfigRepository.update_model_type(bot_id, new_type)

        logger.info(
            "Model toggled",
            extra={
                "bot_id": bot_id,
                "old_type": config.model_type,
                "new_type": new_type,
            },
        )

        return new_type

    @staticmethod
    async def create_phase(bot_id: int, trigger: str, prompt: str):
        """
        Cria nova fase

        Args:
            bot_id: ID do bot
            trigger: Termo único (ex: "fcf4")
            prompt: Prompt da fase

        Returns:
            AIPhase criada

        Raises:
            ValueError: Se trigger já existe
        """
        # Verifica se trigger já existe
        existing = await AIPhaseRepository.get_phase_by_trigger(bot_id, trigger)
        if existing:
            raise ValueError(f"Trigger '{trigger}' já existe para este bot")

        # Busca próximo order
        phases = await AIPhaseRepository.get_phases_by_bot(bot_id)
        next_order = len(phases)

        phase = await AIPhaseRepository.create_phase(
            bot_id, trigger, prompt, next_order
        )

        logger.info(
            "Phase created",
            extra={"bot_id": bot_id, "trigger": trigger, "phase_id": phase.id},
        )

        return phase

    @staticmethod
    async def list_phases(bot_id: int):
        """
        Lista todas as fases de um bot

        Args:
            bot_id: ID do bot

        Returns:
            Lista de AIPhase
        """
        return await AIPhaseRepository.get_phases_by_bot(bot_id)

    @staticmethod
    async def delete_phase(phase_id: int) -> bool:
        """
        Deleta uma fase

        Args:
            phase_id: ID da fase

        Returns:
            True se deletou com sucesso
        """
        success = await AIPhaseRepository.delete_phase(phase_id)

        if success:
            logger.info("Phase deleted", extra={"phase_id": phase_id})

        return success
