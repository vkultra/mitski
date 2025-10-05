"""
Helper functions for spam detection
"""

import re
from typing import Dict, List


def extract_urls_and_mentions(text: str) -> List[str]:
    """
    Extrai URLs e menções de um texto
    """
    if not text:
        return []

    patterns = [
        r"https?://[^\s]+",  # HTTP/HTTPS URLs
        r"www\.[^\s]+",  # www. URLs
        r"t\.me/[^\s]+",  # Telegram links
        r"@\w+",  # Menções
    ]

    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, re.IGNORECASE))

    return matches


def count_emojis(text: str) -> int:
    """
    Conta emojis em um texto
    """
    if not text:
        return 0

    # Pattern expandido para emojis
    emoji_patterns = [
        r"[\U0001F600-\U0001F64F]",  # Emoticons
        r"[\U0001F300-\U0001F5FF]",  # Misc Symbols and Pictographs
        r"[\U0001F680-\U0001F6FF]",  # Transport and Map
        r"[\U0001F700-\U0001F77F]",  # Alchemical Symbols
        r"[\U0001F780-\U0001F7FF]",  # Geometric Shapes Extended
        r"[\U0001F800-\U0001F8FF]",  # Supplemental Arrows-C
        r"[\U00002700-\U000027BF]",  # Dingbats
        r"[\U0001F900-\U0001F9FF]",  # Supplemental Symbols and Pictographs
    ]

    count = 0
    for pattern in emoji_patterns:
        count += len(re.findall(pattern, text))

    return count


def has_repeated_chars(text: str, min_repetitions: int = 4) -> bool:
    """
    Detecta caracteres repetidos excessivamente
    """
    if not text:
        return False

    # Pattern para N+ caracteres repetidos
    pattern = rf"(.)\1{{{min_repetitions-1},}}"
    return bool(re.search(pattern, text))


def is_text_only_emojis(text: str) -> bool:
    """
    Verifica se o texto contém apenas emojis
    """
    if not text:
        return False

    # Remove todos os emojis
    text_without_emojis = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U00002700-\U000027BF\U0001F900-\U0001F9FF]+",
        "",
        text,
    )

    # Se sobrar apenas espaços ou nada, era só emoji
    return len(text_without_emojis.strip()) == 0 and count_emojis(text) > 0


def calculate_message_entropy(text: str) -> float:
    """
    Calcula entropia de uma mensagem (para detectar spam aleatório)
    """
    if not text:
        return 0

    # Conta frequência de cada caractere
    char_freq: dict[str, int] = {}
    for char in text:
        char_freq[char] = char_freq.get(char, 0) + 1

    # Calcula entropia
    import math

    entropy = 0
    text_len = len(text)
    for freq in char_freq.values():
        probability = freq / text_len
        if probability > 0:
            entropy += -probability * math.log2(probability)

    return entropy


def is_gibberish(text: str) -> bool:
    """
    Detecta texto sem sentido/gibberish
    """
    if not text or len(text) < 5:
        return False

    # Verifica se tem muitas consoantes seguidas
    consonant_clusters = re.findall(r"[bcdfghjklmnpqrstvwxyz]{5,}", text.lower())
    if consonant_clusters:
        return True

    # Verifica entropia muito alta (texto aleatório)
    entropy = calculate_message_entropy(text)
    if entropy > 4.5 and len(text) > 10:
        return True

    return False


def extract_message_metadata(message: Dict) -> Dict:
    """
    Extrai metadados úteis de uma mensagem para anti-spam
    """
    return {
        "has_forward": bool(
            message.get("forward_from") or message.get("forward_from_chat")
        ),
        "has_photo": bool(message.get("photo")),
        "has_video": bool(message.get("video")),
        "has_audio": bool(message.get("audio")),
        "has_document": bool(message.get("document")),
        "has_sticker": bool(message.get("sticker")),
        "has_animation": bool(message.get("animation")),
        "has_contact": bool(message.get("contact")),
        "has_location": bool(message.get("location")),
        "has_venue": bool(message.get("venue")),
        "has_poll": bool(message.get("poll")),
        "has_dice": bool(message.get("dice")),
        "has_game": bool(message.get("game")),
        "text_length": len(message.get("text", "")),
        "is_command": bool(message.get("text", "").startswith("/")),
    }
