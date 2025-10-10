"""Serviços utilitários para templates de /start"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

from core.redis_client import redis_client
from database.repos import StartTemplateBlockRepository, StartTemplateRepository

_CACHE_TTL_SECONDS = 30


@dataclass
class StartTemplateMetadata:
    """Metadados mínimos necessários para decisões em runtime"""

    template_id: int
    bot_id: int
    version: int
    is_active: bool
    has_blocks: bool


class StartTemplateService:
    """Fornece acesso com cache aos templates de /start"""

    @staticmethod
    def _cache_key(bot_id: int) -> str:
        return f"start_template:meta:{bot_id}"

    @classmethod
    async def get_metadata(cls, bot_id: int) -> StartTemplateMetadata:
        """Recupera metadados do template com cache em Redis"""
        cache_key = cls._cache_key(bot_id)
        cached = redis_client.get(cache_key)

        if cached:
            data = json.loads(cached)
            return StartTemplateMetadata(**data)

        template = await StartTemplateRepository.get_or_create(bot_id)
        block_count = await StartTemplateBlockRepository.count_blocks(template.id)

        metadata = StartTemplateMetadata(
            template_id=template.id,
            bot_id=bot_id,
            version=template.version,
            is_active=template.is_active,
            has_blocks=block_count > 0,
        )

        redis_client.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(asdict(metadata)))
        return metadata

    @classmethod
    def invalidate_cache(cls, bot_id: int) -> None:
        """Remove metadados em cache"""
        redis_client.delete(cls._cache_key(bot_id))

    @classmethod
    async def bump_version(cls, template_id: int) -> Optional[int]:
        """Incrementa versão do template e invalida cache"""
        new_version = await StartTemplateRepository.increment_version(template_id)
        if new_version is None:
            return None

        template = await StartTemplateRepository.get_by_id(template_id)
        if template:
            cls.invalidate_cache(template.bot_id)
        return new_version
