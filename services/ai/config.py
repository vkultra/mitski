"""
Serviço de configuração de IA
"""

from core.telemetry import logger
from database.repos import AIConfigRepository
from services.ai.phase_service import AIPhaseService


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

            # Garantir que existe fase inicial ao criar config
            initial_phase = await AIPhaseService.ensure_initial_phase(bot_id)
            logger.info(
                "Initial phase ensured for new AI config",
                extra={
                    "bot_id": bot_id,
                    "phase_id": initial_phase.id,
                    "phase_name": initial_phase.phase_name,
                },
            )

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
    async def create_phase(
        bot_id: int,
        name: str,
        prompt: str,
        trigger: str = None,
        is_initial: bool = False,
    ):
        """
        Cria nova fase (proxy para AIPhaseService)

        Args:
            bot_id: ID do bot
            name: Nome da fase
            prompt: Prompt da fase
            trigger: Termo único (None para fase inicial)
            is_initial: Se é fase inicial

        Returns:
            AIPhase criada
        """
        return await AIPhaseService.create_phase(
            bot_id, name, prompt, trigger, is_initial
        )

    @staticmethod
    async def list_phases(bot_id: int):
        """Lista todas as fases de um bot"""
        return await AIPhaseService.list_phases(bot_id)

    @staticmethod
    async def delete_phase(phase_id: int) -> bool:
        """Deleta uma fase"""
        return await AIPhaseService.delete_phase(phase_id)
