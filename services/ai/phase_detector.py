"""
Detector de triggers de mudança de fase
"""

from typing import List, Optional

from core.telemetry import logger


class PhaseDetectorService:
    """Detecta triggers de mudança de fase na resposta da IA"""

    @staticmethod
    def detect_trigger(text: str, phases: List) -> Optional[str]:
        """
        Detecta se algum trigger está presente no texto (case-insensitive, qualquer posição)

        Exemplos de detecção:
        - "FCF4" em "Vamos para FCF4 agora" → detecta "FCF4"
        - "fcf4" em "preparado fcf4 continuar" → detecta "fcf4"
        - "EKO3" em "eko3processo" → detecta "EKO3"

        Args:
            text: Texto da resposta da IA
            phases: Lista de objetos AIPhase

        Returns:
            Trigger detectado (original) ou None
        """
        if not text or not phases:
            return None

        text_lower = text.lower()

        for phase in phases:
            trigger = phase.phase_trigger
            trigger_lower = trigger.lower()

            # Busca simples case-insensitive
            if trigger_lower in text_lower:
                logger.info(
                    "Phase trigger detected",
                    extra={
                        "trigger": trigger,
                        "phase_id": phase.id,
                        "text_snippet": text[:100],
                    },
                )
                return trigger  # Retorna trigger original

        return None
