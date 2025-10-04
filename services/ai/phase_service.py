"""
Serviço de gerenciamento de fases de IA

Responsável por:
- Criar/editar/deletar fases
- Gerenciar fase inicial
- Listar fases
"""

from typing import List, Optional

from core.telemetry import logger
from database.repos import AIPhaseRepository


class AIPhaseService:
    """Gerencia fases de IA dos bots"""

    @staticmethod
    async def create_phase(
        bot_id: int,
        name: str,
        prompt: str,
        trigger: Optional[str] = None,
        is_initial: bool = False,
    ):
        """
        Cria nova fase

        Args:
            bot_id: ID do bot
            name: Nome legível da fase
            prompt: Prompt da fase
            trigger: Termo único (None para fase inicial)
            is_initial: Se é fase inicial (sem trigger)

        Returns:
            AIPhase criada

        Raises:
            ValueError: Se trigger já existe ou se fase inicial sem nome
        """
        # Validações
        if is_initial and trigger:
            raise ValueError("Fase inicial não pode ter trigger")

        if not is_initial and not trigger:
            raise ValueError("Fases normais precisam de trigger")

        if trigger:
            # Verifica se trigger já existe
            existing = await AIPhaseRepository.get_phase_by_trigger(bot_id, trigger)
            if existing:
                raise ValueError(f"Trigger '{trigger}' já existe para este bot")

        # Busca próximo order
        phases = await AIPhaseRepository.get_phases_by_bot(bot_id)
        next_order = len(phases)

        phase = await AIPhaseRepository.create_phase(
            bot_id=bot_id,
            name=name,
            prompt=prompt,
            trigger=trigger,
            is_initial=is_initial,
            order=next_order,
        )

        logger.info(
            "Phase created",
            extra={
                "bot_id": bot_id,
                "phase_id": phase.id,
                "phase_name": name,
                "is_initial": is_initial,
                "trigger": trigger,
            },
        )

        return phase

    @staticmethod
    async def list_phases(bot_id: int) -> List:
        """
        Lista todas as fases de um bot

        Args:
            bot_id: ID do bot

        Returns:
            Lista de AIPhase ordenada por order
        """
        return await AIPhaseRepository.get_phases_by_bot(bot_id)

    @staticmethod
    async def get_phase_by_id(phase_id: int):
        """
        Busca fase por ID

        Args:
            phase_id: ID da fase

        Returns:
            AIPhase ou None
        """
        return await AIPhaseRepository.get_by_id(phase_id)

    @staticmethod
    async def get_initial_phase(bot_id: int):
        """
        Busca fase inicial do bot

        Args:
            bot_id: ID do bot

        Returns:
            AIPhase inicial ou None
        """
        return await AIPhaseRepository.get_initial_phase(bot_id)

    @staticmethod
    async def ensure_initial_phase(bot_id: int):
        """
        Garante que existe uma fase inicial para o bot
        Se não existir, cria uma padrão

        Args:
            bot_id: ID do bot

        Returns:
            AIPhase inicial (existente ou recém-criada)
        """
        # Buscar fase inicial existente
        initial_phase = await AIPhaseRepository.get_initial_phase(bot_id)

        if not initial_phase:
            # Criar fase inicial padrão
            initial_phase = await AIPhaseRepository.create_phase(
                bot_id=bot_id,
                name="Inicial",
                prompt=(
                    "Você está na fase inicial. "
                    "Seja acolhedor e pergunte como pode ajudar."
                ),
                trigger=None,
                is_initial=True,
                order=0,
            )

            logger.info(
                "Default initial phase created automatically",
                extra={
                    "bot_id": bot_id,
                    "phase_id": initial_phase.id,
                    "phase_name": "Inicial",
                },
            )

        return initial_phase

    @staticmethod
    async def set_initial_phase(bot_id: int, phase_id: int) -> bool:
        """
        Define fase como inicial (desmarca outras)

        Args:
            bot_id: ID do bot
            phase_id: ID da fase

        Returns:
            True se atualizou com sucesso
        """
        success = await AIPhaseRepository.set_initial_phase(bot_id, phase_id)

        if success:
            logger.info(
                "Initial phase set",
                extra={"bot_id": bot_id, "phase_id": phase_id},
            )

        return success

    @staticmethod
    async def update_phase(
        phase_id: int,
        name: Optional[str] = None,
        trigger: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> bool:
        """
        Atualiza dados de uma fase

        Args:
            phase_id: ID da fase
            name: Novo nome (opcional)
            trigger: Novo trigger (opcional)
            prompt: Novo prompt (opcional)

        Returns:
            True se atualizou com sucesso
        """
        success = await AIPhaseRepository.update_phase(phase_id, name, trigger, prompt)

        if success:
            logger.info(
                "Phase updated",
                extra={
                    "phase_id": phase_id,
                    "updated_name": name is not None,
                    "updated_trigger": trigger is not None,
                    "updated_prompt": prompt is not None,
                },
            )

        return success

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
