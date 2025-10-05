"""
Anti-spam service with atomic Redis operations
"""

import json
import re
import time
from typing import Dict, Optional

from core.redis_client import redis_client
from core.telemetry import logger

# Lua script para verificação atômica de todas as regras
ANTISPAM_CHECK_LUA = """
local bot_id = KEYS[1]
local user_id = KEYS[2]
local message_text = ARGV[1]
local timestamp = tonumber(ARGV[2])
local config = cjson.decode(ARGV[3])

-- Prefixo para todas as chaves
local prefix = 'as:' .. bot_id .. ':' .. user_id .. ':'

-- Função helper para incrementar com TTL
local function incr_with_ttl(key, ttl)
    local count = redis.call('INCR', key)
    if count == 1 then
        redis.call('EXPIRE', key, ttl)
    end
    return count
end

-- 1. FLOOD CHECK (>8 msgs em 10s)
if config['flood'] then
    local flood_count = incr_with_ttl(prefix .. 'flood', 10)
    if flood_count > 8 then
        return 'FLOOD'
    end
end

-- 2. /START LOOP CHECK (3 /starts em 5 min)
if config['loop_start'] and message_text == '/start' then
    local start_count = incr_with_ttl(prefix .. 'starts', 300)
    if start_count >= 3 then
        return 'LOOP_START'
    end

    -- Salva timestamp do último /start para verificação do '.'
    redis.call('SETEX', prefix .. 'last_start', 60, timestamp)
end

-- 3. DOT AFTER START CHECK ('.' em 60s após /start)
if config['dot_after_start'] and message_text == '.' then
    local last_start = redis.call('GET', prefix .. 'last_start')
    if last_start then
        return 'DOT_AFTER_START'
    end
end

-- 4. REPETITION CHECK (≥3 msgs iguais em 30s)
if config['repetition'] and message_text ~= '' then
    local msg_hash = prefix .. 'msg:' .. string.gsub(message_text, ' ', '_')
    local repeat_count = incr_with_ttl(msg_hash, 30)
    if repeat_count >= 3 then
        return 'REPETITION'
    end
end

-- 5. SHORT MESSAGES CHECK (5 msgs <3 chars em sequência)
if config['short_messages'] and string.len(message_text) < 3 then
    local short_count = incr_with_ttl(prefix .. 'short', 60)
    if short_count >= 5 then
        return 'SHORT_MESSAGES'
    end
else
    -- Reset contador se mensagem for longa
    redis.call('DEL', prefix .. 'short')
end

-- 6. TOTAL LIMIT CHECK
if config['total_limit'] then
    local total_count = redis.call('INCR', prefix .. 'total')
    if total_count == 1 then
        redis.call('EXPIRE', prefix .. 'total', 86400) -- 24h
    end

    local limit = tonumber(config['total_limit_value']) or 100
    if total_count > limit then
        return 'TOTAL_LIMIT'
    end
end

return 'OK'
"""

# Lua script para verificações adicionais (links, emojis, etc)
ANTISPAM_EXTRA_LUA = """
local bot_id = KEYS[1]
local user_id = KEYS[2]
local has_forward = ARGV[1] == '1'
local has_media = ARGV[2] == '1'
local has_sticker = ARGV[3] == '1'
local has_contact = ARGV[4] == '1'
local has_location = ARGV[5] == '1'
local response_time = tonumber(ARGV[6])
local config = cjson.decode(ARGV[7])

local prefix = 'as:' .. bot_id .. ':' .. user_id .. ':'

local function incr_with_ttl(key, ttl)
    local count = redis.call('INCR', key)
    if count == 1 then
        redis.call('EXPIRE', key, ttl)
    end
    return count
end

-- FORWARD SPAM (>3 em 30s)
if config['forward_spam'] and has_forward then
    local forward_count = incr_with_ttl(prefix .. 'forwards', 30)
    if forward_count > 3 then
        return 'FORWARD_SPAM'
    end
end

-- MEDIA SPAM (>5 em 30s)
if config['media_spam'] and has_media then
    local media_count = incr_with_ttl(prefix .. 'media', 30)
    if media_count > 5 then
        return 'MEDIA_SPAM'
    end
end

-- STICKER SPAM (>5 em 30s)
if config['sticker_spam'] and has_sticker then
    local sticker_count = incr_with_ttl(prefix .. 'stickers', 30)
    if sticker_count > 5 then
        return 'STICKER_SPAM'
    end
end

-- CONTACT SPAM (>2 em 60s)
if config['contact_spam'] and has_contact then
    local contact_count = incr_with_ttl(prefix .. 'contacts', 60)
    if contact_count > 2 then
        return 'CONTACT_SPAM'
    end
end

-- LOCATION SPAM (>2 em 60s)
if config['location_spam'] and has_location then
    local location_count = incr_with_ttl(prefix .. 'locations', 60)
    if location_count > 2 then
        return 'LOCATION_SPAM'
    end
end

-- BOT SPEED (<1s between messages, 5+ times)
if config['bot_speed'] and response_time < 1000 then
    local speed_count = incr_with_ttl(prefix .. 'fast', 10)
    if speed_count >= 5 then
        return 'BOT_SPEED'
    end
end

return 'OK'
"""


class AntiSpamService:
    """Serviço de anti-spam com operações atômicas"""

    # Registra scripts Lua no Redis (feito uma vez)
    try:
        MAIN_SCRIPT = redis_client.register_script(ANTISPAM_CHECK_LUA)
        EXTRA_SCRIPT = redis_client.register_script(ANTISPAM_EXTRA_LUA)
    except Exception as e:
        logger.error(f"Failed to register Lua scripts: {e}")
        MAIN_SCRIPT = None
        EXTRA_SCRIPT = None

    @staticmethod
    def check_violations_atomic(
        bot_id: int, user_id: int, message: Dict, config: Dict
    ) -> Optional[str]:
        """
        Verifica todas as violações em uma operação atômica
        Returns: tipo de violação ou None
        """
        if not AntiSpamService.MAIN_SCRIPT:
            logger.warning("Lua scripts not loaded, skipping anti-spam")
            return None

        try:
            # Extrai dados da mensagem
            text = message.get("text", "")
            timestamp = message.get("date", int(time.time()))

            # Verifica violações principais
            result = AntiSpamService.MAIN_SCRIPT(
                keys=[str(bot_id), str(user_id)],
                args=[text, str(timestamp), json.dumps(config)],
            )

            if result and result != b"OK" and result != "OK":
                return result.decode() if isinstance(result, bytes) else result

            # Verifica violações extras se configurado
            if any(
                [
                    config.get("forward_spam"),
                    config.get("media_spam"),
                    config.get("sticker_spam"),
                    config.get("contact_spam"),
                    config.get("location_spam"),
                    config.get("bot_speed"),
                ]
            ):
                has_forward = "1" if message.get("forward_from") else "0"
                has_media = "1" if message.get("photo") or message.get("video") else "0"
                has_sticker = "1" if message.get("sticker") else "0"
                has_contact = "1" if message.get("contact") else "0"
                has_location = "1" if message.get("location") else "0"

                # Calcula tempo de resposta (ms desde última mensagem)
                last_msg_key = f"as:{bot_id}:{user_id}:last_msg_time"
                last_time = redis_client.get(last_msg_key)
                response_time = 9999  # Default alto
                if last_time:
                    response_time = (timestamp - float(last_time)) * 1000

                redis_client.setex(last_msg_key, 60, str(timestamp))

                extra_result = AntiSpamService.EXTRA_SCRIPT(
                    keys=[str(bot_id), str(user_id)],
                    args=[
                        has_forward,
                        has_media,
                        has_sticker,
                        has_contact,
                        has_location,
                        str(response_time),
                        json.dumps(config),
                    ],
                )

                if extra_result and extra_result != b"OK" and extra_result != "OK":
                    return (
                        extra_result.decode()
                        if isinstance(extra_result, bytes)
                        else extra_result
                    )

            return None

        except Exception as e:
            logger.error(
                "Anti-spam check failed",
                extra={
                    "bot_id": bot_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )
            return None

    @staticmethod
    def check_text_violations(text: str, config: Dict) -> Optional[str]:
        """
        Verifica violações baseadas em texto (Python puro para casos especiais)
        """
        if not text:
            return None

        # LINKS/MENTIONS CHECK (2+ em 60s)
        if config.get("links_mentions"):
            # Conta URLs e menções
            url_pattern = r"https?://|www\.|t\.me/|@\w+"
            matches = re.findall(url_pattern, text, re.IGNORECASE)
            if len(matches) >= 2:
                return "LINKS_MENTIONS"

        # EMOJI FLOOD (>10 emojis ou só emojis)
        if config.get("emoji_flood"):
            # Pattern para emojis comuns
            emoji_pattern = r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F]"
            emojis = re.findall(emoji_pattern, text)
            if len(emojis) > 10 or (
                len(emojis) > 3 and len(text.strip()) == len("".join(emojis))
            ):
                return "EMOJI_FLOOD"

        # CHAR REPETITION (aaaa, !!!!, etc)
        if config.get("char_repetition"):
            # Detecta 4+ caracteres repetidos
            if re.search(r"(.)\1{3,}", text):
                return "CHAR_REPETITION"

        return None

    @staticmethod
    def is_banned_cached(bot_id: int, user_id: int) -> bool:
        """
        Verifica cache de banimento (rápido)
        """
        return bool(redis_client.exists(f"banned:{bot_id}:{user_id}"))

    @staticmethod
    def ban_user_cache(bot_id: int, user_id: int, reason: str, ttl: int = 86400):
        """
        Adiciona usuário ao cache de banidos
        """
        redis_client.setex(f"banned:{bot_id}:{user_id}", ttl, reason)

    @staticmethod
    def clear_user_counters(bot_id: int, user_id: int):
        """
        Limpa contadores de um usuário (útil para testes ou reset manual)
        """
        pattern = f"as:{bot_id}:{user_id}:*"
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)
