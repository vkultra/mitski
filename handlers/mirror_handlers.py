"""
Handlers para menu de Grupo/Espelhamento
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.config import settings
from database.models import Bot, MirrorGroup, UserTopic
from database.repos import BotRepository, SessionLocal
from services.conversation_state import ConversationStateManager
from workers.mirror_tasks import handle_mirror_control_action, recover_orphan_buffers


async def handle_group_menu(user_id: int) -> Dict[str, Any]:
    """Menu principal de configuração de grupos"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Verifica configuração global
    from database.models import MirrorGlobalConfig

    with SessionLocal() as session:
        global_config = (
            session.query(MirrorGlobalConfig).filter_by(admin_id=user_id).first()
        )

        if global_config and global_config.use_centralized_mode:
            mode_text = "🎯 **Centralizado**"
            mode_desc = f"Todas as conversas vão para o grupo `{global_config.manager_group_id}`"
            is_active = global_config.is_active
        else:
            # Verifica se tem bots configurados no modo individual
            bots_configured = (
                session.query(MirrorGroup)
                .join(Bot)
                .filter(Bot.admin_id == user_id, MirrorGroup.is_active.is_(True))
                .count()
            )

            mode_text = "⚙️ **Individual por Bot**"
            if bots_configured > 0:
                mode_desc = f"{bots_configured} bot(s) com espelhamento ativo"
                is_active = True
            else:
                mode_desc = "Nenhum bot configurado"
                is_active = False

    status_icon = "✅" if is_active else "⚠️"

    keyboard = {
        "inline_keyboard": [
            [{"text": "⚙️ Configurar", "callback_data": "group_configure_start"}],
            [{"text": "⬅️ Voltar", "callback_data": "back_to_main"}],
        ]
    }

    return {
        "text": (
            "🪞 **CONFIGURAÇÃO DE ESPELHAMENTO**\n"
            "─────────────────\n"
            f"{status_icon} **Modo Ativo**: {mode_text}\n"
            f"{mode_desc}\n\n"
            f"**Sistema**: {os.getenv('MIRROR_MODE', 'batch').upper()}\n"
            f"**Batch**: {os.getenv('MIRROR_BATCH_SIZE', 5)} msgs / {os.getenv('MIRROR_BATCH_DELAY', 2)}s\n\n"
            "Use o botão abaixo para configurar o espelhamento."
        ),
        "keyboard": keyboard,
    }


async def handle_group_configure_start(user_id: int) -> Dict[str, Any]:
    """Inicia configuração - escolha do modo"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    from database.models import MirrorGlobalConfig

    with SessionLocal() as session:
        global_config = (
            session.query(MirrorGlobalConfig).filter_by(admin_id=user_id).first()
        )

        current_mode = (
            "centralizado"
            if (global_config and global_config.use_centralized_mode)
            else "individual"
        )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "🎯 Modo Centralizado",
                    "callback_data": "group_mode_centralized",
                }
            ],
            [
                {
                    "text": "⚙️ Modo Individual (por Bot)",
                    "callback_data": "group_mode_individual",
                }
            ],
            [{"text": "⬅️ Voltar", "callback_data": "group_menu"}],
        ]
    }

    return {
        "text": (
            "⚙️ **ESCOLHA O MODO DE ESPELHAMENTO**\n"
            "─────────────────\n\n"
            "**🎯 Modo Centralizado:**\n"
            "• Todas as conversas de todos os bots vão para UM único grupo\n"
            "• Tópicos nomeados como: `🤖 @bot - Usuário`\n"
            "• Mais fácil de gerenciar\n"
            "• Requer apenas o bot gerenciador no grupo\n\n"
            "**⚙️ Modo Individual:**\n"
            "• Cada bot tem seu próprio grupo\n"
            "• Tópicos nomeados como: `👤 Usuário`\n"
            "• Mais organização por bot\n"
            "• Requer cada bot em seu grupo\n\n"
            f"**Modo atual**: {current_mode.upper()}"
        ),
        "keyboard": keyboard,
    }


async def handle_group_mode_centralized(user_id: int) -> Dict[str, Any]:
    """Configura modo centralizado"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Define estado para aguardar ID do grupo
    ConversationStateManager.set_state(user_id, "awaiting_centralized_group_id", {})

    return {
        "text": (
            "🎯 **MODO CENTRALIZADO**\n"
            "─────────────────\n\n"
            "Envie o **ID do grupo** onde TODAS as conversas\n"
            "de TODOS os seus bots serão espelhadas.\n\n"
            "**Passos:**\n"
            "1. Crie um supergrupo no Telegram\n"
            "2. Ative os **Tópicos** (Forum Topics)\n"
            "3. Adicione APENAS o **bot gerenciador** como admin\n"
            "4. Use @userinfobot no grupo para obter o ID\n"
            "5. Envie o ID aqui\n\n"
            "**Exemplo de ID:** `-1001234567890`"
        ),
        "keyboard": None,
    }


async def handle_group_mode_individual(user_id: int) -> Dict[str, Any]:
    """Configura modo individual - lista bots"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Lista bots para configurar
    bots = BotRepository.get_user_bots_sync(user_id)
    if not bots:
        return {
            "text": "❌ Você não possui bots cadastrados.\n\nAdicione um bot primeiro.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "⬅️ Voltar", "callback_data": "group_menu"}]
                ]
            },
        }

    # Cria teclado com bots
    keyboard_buttons = []
    for bot in bots:
        has_config = _check_mirror_config(bot.id)
        icon = "✅" if has_config else "⚠️"
        keyboard_buttons.append(
            [
                {
                    "text": f"{icon} @{bot.username}",
                    "callback_data": f"group_individual_bot_{bot.id}",
                }
            ]
        )

    keyboard_buttons.append(
        [{"text": "⬅️ Voltar", "callback_data": "group_configure_start"}]
    )

    return {
        "text": (
            "⚙️ **MODO INDIVIDUAL - SELECIONE O BOT**\n"
            "─────────────────\n"
            "Escolha o bot para configurar:\n\n"
            "✅ = Já configurado\n"
            "⚠️ = Não configurado\n\n"
            "Cada bot terá seu próprio grupo de espelhamento."
        ),
        "keyboard": {"inline_keyboard": keyboard_buttons},
    }


async def handle_group_individual_bot(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Configura grupo para bot individual"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or bot.admin_id != user_id:
        return {"text": "❌ Bot não encontrado.", "keyboard": None}

    # Define estado para aguardar ID do grupo
    ConversationStateManager.set_state(
        user_id, "awaiting_individual_group_id", {"bot_id": bot_id}
    )

    # Verifica se já tem configuração
    with SessionLocal() as session:
        mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot_id).first()
        current_group = (
            f"\n\n**Grupo atual:** `{mirror_group.group_id}`" if mirror_group else ""
        )

    return {
        "text": (
            f"⚙️ **CONFIGURAR BOT @{bot.username}**\n"
            f"─────────────────{current_group}\n\n"
            f"Envie o **ID do grupo** onde as conversas\n"
            f"deste bot serão espelhadas.\n\n"
            f"**Passos:**\n"
            f"1. Crie um supergrupo no Telegram\n"
            f"2. Ative os **Tópicos** (Forum Topics)\n"
            f"3. Adicione o bot **@{bot.username}** como admin\n"
            f"4. Use @userinfobot no grupo para obter o ID\n"
            f"5. Envie o ID aqui\n\n"
            f"**Exemplo de ID:** `-1001234567890`"
        ),
        "keyboard": None,
    }


async def handle_group_centralized_mode(user_id: int) -> Dict[str, Any]:
    """Menu do modo centralizado"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    from database.models import MirrorGlobalConfig

    with SessionLocal() as session:
        global_config = (
            session.query(MirrorGlobalConfig).filter_by(admin_id=user_id).first()
        )

        if global_config and global_config.use_centralized_mode:
            # Modo já está ativo
            bots = BotRepository.get_user_bots_sync(user_id)
            bot_count = len(bots)

            # Conta tópicos criados
            from database.models import UserTopic

            topic_count = (
                session.query(UserTopic)
                .join(Bot)
                .filter(Bot.admin_id == user_id)
                .count()
            )

            text = (
                "🎯 **MODO CENTRALIZADO ATIVO**\n"
                "─────────────────\n"
                f"✅ Bot gerenciador está espelhando todas as conversas\n\n"
                f"👥 **Grupo**: `{global_config.manager_group_id}`\n"
                f"📊 **Bots ativos**: {bot_count}\n"
                f"💬 **Tópicos criados**: {topic_count}\n\n"
                "**Configurações:**\n"
                f"• Batch size: {global_config.batch_size}\n"
                f"• Delay: {global_config.batch_delay}s\n"
                f"• Timeout: {global_config.flush_timeout}s"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📝 Alterar Grupo",
                            "callback_data": "group_centralized_change",
                        }
                    ],
                    [
                        {
                            "text": "❌ Desativar Modo Centralizado",
                            "callback_data": "group_centralized_disable",
                        }
                    ],
                    [{"text": "⬅️ Voltar", "callback_data": "group_menu"}],
                ]
            }
        else:
            # Modo não está ativo
            text = (
                "🎯 **MODO CENTRALIZADO**\n"
                "─────────────────\n"
                "Use o bot gerenciador para espelhar TODAS as conversas\n"
                "de todos os seus bots em um único grupo.\n\n"
                "**Vantagens:**\n"
                "✅ Configuração única\n"
                "✅ Não precisa adicionar cada bot ao grupo\n"
                "✅ Visão unificada de todas as conversas\n"
                "✅ Tópicos organizados por bot + usuário\n\n"
                "**Como funciona:**\n"
                "• O bot gerenciador cria tópicos como:\n"
                "  `🤖 @vendas_bot - João Silva`\n"
                "  `🤖 @suporte_bot - Maria Santos`"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Ativar Modo Centralizado",
                            "callback_data": "group_centralized_enable",
                        }
                    ],
                    [
                        {
                            "text": "❓ Como configurar",
                            "callback_data": "group_centralized_help",
                        }
                    ],
                    [{"text": "⬅️ Voltar", "callback_data": "group_menu"}],
                ]
            }

    return {"text": text, "keyboard": keyboard}


async def handle_group_centralized_enable(user_id: int) -> Dict[str, Any]:
    """Habilita modo centralizado"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Salva estado para receber ID do grupo
    ConversationStateManager.set_state(user_id, "awaiting_centralized_group_id", {})

    return {
        "text": (
            "🆔 **CONFIGURAR GRUPO CENTRALIZADO**\n"
            "─────────────────\n"
            "Envie o ID do grupo onde o bot gerenciador\n"
            "irá espelhar TODAS as conversas.\n\n"
            "**Importante:**\n"
            "• Adicione APENAS o bot gerenciador ao grupo\n"
            "• Ative os forum topics no grupo\n"
            "• Conceda permissões de admin ao bot\n\n"
            "**Exemplo de ID**: `-1001234567890`"
        ),
        "keyboard": None,
    }


async def handle_group_centralized_id_input(
    user_id: int, text: str
) -> Optional[Dict[str, Any]]:
    """Processa entrada do ID do grupo centralizado"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Recupera estado
    state_data = ConversationStateManager.get_state(user_id)
    if not state_data or state_data.get("state") != "awaiting_centralized_group_id":
        return None

    # Valida ID do grupo
    try:
        group_id = int(text.strip())
        if group_id >= 0:
            return {
                "text": "❌ ID inválido. IDs de grupos começam com `-`.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ ID inválido. Envie apenas números.\n\nExemplo: `-1001234567890`",
            "keyboard": None,
        }

    # Salva configuração global
    from core.telemetry import logger
    from database.models import MirrorGlobalConfig

    with SessionLocal() as session:
        # Busca bots PRIMEIRO para validar
        bots = session.query(Bot).filter_by(admin_id=user_id).all()

        if not bots:
            return {
                "text": (
                    "❌ **ERRO: NENHUM BOT ENCONTRADO**\n"
                    "─────────────────\n"
                    "Você não possui nenhum bot cadastrado.\n\n"
                    "Adicione um bot primeiro usando o menu principal."
                ),
                "keyboard": {
                    "inline_keyboard": [
                        [{"text": "⬅️ Voltar", "callback_data": "group_menu"}]
                    ]
                },
            }

        global_config = (
            session.query(MirrorGlobalConfig).filter_by(admin_id=user_id).first()
        )

        if global_config:
            global_config.use_centralized_mode = True
            global_config.manager_group_id = group_id
            global_config.is_active = True
        else:
            global_config = MirrorGlobalConfig(
                admin_id=user_id,
                use_centralized_mode=True,
                manager_group_id=group_id,
                is_active=True,
                batch_size=int(os.getenv("MIRROR_BATCH_SIZE", 5)),
                batch_delay=int(os.getenv("MIRROR_BATCH_DELAY", 2)),
                flush_timeout=int(os.getenv("MIRROR_FLUSH_TIMEOUT", 3)),
            )
            session.add(global_config)

        # Atualiza todos os bots do admin para usar modo centralizado
        bot_ids = []  # Armazena IDs antes de fechar sessão
        bot_usernames = []  # Armazena usernames para log

        for bot in bots:
            bot_ids.append(bot.id)
            bot_usernames.append(bot.username)

            # Cria ou atualiza MirrorGroup
            mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot.id).first()
            if mirror_group:
                mirror_group.use_manager_bot = True
                mirror_group.manager_group_id = group_id
                mirror_group.is_active = True
                logger.info(f"Updated MirrorGroup for bot {bot.id} (@{bot.username})")
            else:
                mirror_group = MirrorGroup(
                    bot_id=bot.id,
                    group_id=group_id,  # Usa como fallback
                    use_manager_bot=True,
                    manager_group_id=group_id,
                    is_active=True,
                    batch_size=global_config.batch_size,
                    batch_delay=global_config.batch_delay,
                    flush_timeout=global_config.flush_timeout,
                )
                session.add(mirror_group)
                logger.info(f"Created MirrorGroup for bot {bot.id} (@{bot.username})")

        session.commit()

        logger.info(
            f"Centralized mirror mode activated for admin {user_id}",
            extra={
                "admin_id": user_id,
                "group_id": group_id,
                "bots_configured": len(bot_ids),
                "bot_ids": bot_ids,
                "bot_usernames": bot_usernames,
            },
        )

    # Limpa estado
    ConversationStateManager.clear_state(user_id)

    # Limpa caches (usando IDs armazenados)
    from core.redis_client import redis_client

    for bot_id in bot_ids:
        redis_client.delete(f"mirror_config:{bot_id}")

    # Formata lista de bots
    bots_list = "\n".join([f"• @{username}" for username in bot_usernames])

    return {
        "text": (
            f"✅ **MODO CENTRALIZADO ATIVADO!**\n"
            f"─────────────────\n"
            f"Grupo ID: `{group_id}`\n\n"
            f"**Bots configurados ({len(bot_ids)}):**\n"
            f"{bots_list}\n\n"
            f"✅ Espelhamento via bot gerenciador\n"
            f"✅ Tópicos criados automaticamente\n\n"
            f"**Formato dos tópicos:**\n"
            f"`🤖 @bot_name - Nome do Usuário`\n\n"
            f"**Status:** As conversas serão espelhadas\n"
            f"automaticamente a partir de agora!"
        ),
        "keyboard": {
            "inline_keyboard": [
                [{"text": "✅ Concluído", "callback_data": "group_menu"}]
            ]
        },
    }


async def handle_group_configure(user_id: int) -> Dict[str, Any]:
    """Inicia configuração de grupo para bot"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Lista bots ativos
    bots = BotRepository.get_user_bots_sync(user_id)
    if not bots:
        return {
            "text": "❌ Você não possui bots cadastrados.\n\nAdicione um bot primeiro.",
            "keyboard": {
                "inline_keyboard": [
                    [{"text": "⬅️ Voltar", "callback_data": "group_menu"}]
                ]
            },
        }

    # Cria teclado com bots
    keyboard_buttons = []
    for bot in bots:
        has_config = _check_mirror_config(bot.id)
        icon = "✅" if has_config else "⚠️"
        keyboard_buttons.append(
            [
                {
                    "text": f"{icon} @{bot.username}",
                    "callback_data": f"group_select_bot_{bot.id}",
                }
            ]
        )

    keyboard_buttons.append([{"text": "⬅️ Voltar", "callback_data": "group_menu"}])

    return {
        "text": (
            "🤖 **SELECIONE O BOT**\n"
            "─────────────────\n"
            "Escolha o bot para configurar espelhamento:\n\n"
            "✅ = Configurado | ⚠️ = Não configurado"
        ),
        "keyboard": {"inline_keyboard": keyboard_buttons},
    }


async def handle_group_select_bot(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de configuração para bot específico"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    bot = BotRepository.get_bot_by_id_sync(bot_id)
    if not bot or bot.admin_id != user_id:
        return {"text": "❌ Bot não encontrado.", "keyboard": None}

    # Verifica se já tem configuração
    with SessionLocal() as session:
        mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot_id).first()

        if mirror_group:
            text = (
                f"⚙️ **CONFIGURAÇÃO ATUAL**\n"
                f"─────────────────\n"
                f"🤖 Bot: @{bot.username}\n"
                f"👥 Grupo ID: `{mirror_group.group_id}`\n"
                f"📊 Status: {'✅ Ativo' if mirror_group.is_active else '❌ Inativo'}\n\n"
                f"**Configurações de Batch:**\n"
                f"• Tamanho: {mirror_group.batch_size} mensagens\n"
                f"• Delay: {mirror_group.batch_delay}s\n"
                f"• Timeout: {mirror_group.flush_timeout}s\n"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "📝 Alterar Grupo ID",
                            "callback_data": f"group_change_id_{bot_id}",
                        }
                    ],
                    [
                        {
                            "text": (
                                "⏸️ Pausar" if mirror_group.is_active else "▶️ Ativar"
                            ),
                            "callback_data": f"group_toggle_{bot_id}",
                        }
                    ],
                    [
                        {
                            "text": "🗑 Remover Configuração",
                            "callback_data": f"group_remove_{bot_id}",
                        }
                    ],
                    [{"text": "⬅️ Voltar", "callback_data": "group_configure"}],
                ]
            }
        else:
            text = (
                f"⚠️ **CONFIGURAÇÃO NECESSÁRIA**\n"
                f"─────────────────\n"
                f"🤖 Bot: @{bot.username}\n\n"
                f"Este bot ainda não tem um grupo configurado.\n\n"
                f"**Para configurar:**\n"
                f"1. Crie um supergrupo no Telegram\n"
                f"2. Ative os tópicos (forum topics)\n"
                f"3. Adicione o bot como administrador\n"
                f"4. Obtenha o ID do grupo\n"
                f"5. Clique no botão abaixo\n"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "➕ Adicionar Grupo",
                            "callback_data": f"group_add_{bot_id}",
                        }
                    ],
                    [{"text": "❓ Como obter ID", "callback_data": "group_help_id"}],
                    [{"text": "⬅️ Voltar", "callback_data": "group_configure"}],
                ]
            }

    return {"text": text, "keyboard": keyboard}


async def handle_group_add(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Inicia processo de adicionar grupo"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Salva estado para receber ID
    ConversationStateManager.set_state(user_id, "awaiting_group_id", {"bot_id": bot_id})

    return {
        "text": (
            "🆔 **INFORME O ID DO GRUPO**\n"
            "─────────────────\n"
            "Envie o ID do grupo onde deseja espelhar as conversas.\n\n"
            "**Exemplo**: `-1001234567890`\n\n"
            "💡 **Dica**: Use o bot @userinfobot no grupo para obter o ID."
        ),
        "keyboard": None,
    }


async def handle_group_individual_id_input(
    user_id: int, text: str
) -> Optional[Dict[str, Any]]:
    """Processa entrada do ID do grupo para modo individual"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Recupera estado
    state_data = ConversationStateManager.get_state(user_id)
    if not state_data or state_data.get("state") != "awaiting_individual_group_id":
        return None

    bot_id = state_data.get("data", {}).get("bot_id")
    if not bot_id:
        return None

    # Valida ID do grupo
    try:
        group_id = int(text.strip())
        if group_id >= 0:
            return {
                "text": "❌ ID inválido. IDs de grupos começam com `-`.\n\nTente novamente:",
                "keyboard": None,
            }
    except ValueError:
        return {
            "text": "❌ ID inválido. Envie apenas números.\n\nExemplo: `-1001234567890`",
            "keyboard": None,
        }

    # Salva configuração do bot individual
    # IMPORTANTE: Desativa modo centralizado ao configurar bot individual
    from database.models import MirrorGlobalConfig

    with SessionLocal() as session:
        # Busca bot dentro da sessão
        bot = session.query(Bot).filter_by(id=bot_id).first()
        if not bot:
            return {"text": "❌ Bot não encontrado.", "keyboard": None}

        bot_username = bot.username  # Armazena antes de fechar sessão

        # Desativa modo centralizado
        global_config = (
            session.query(MirrorGlobalConfig).filter_by(admin_id=user_id).first()
        )
        if global_config:
            global_config.use_centralized_mode = False
            global_config.is_active = False

        # Configura bot individual
        mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot_id).first()

        if mirror_group:
            mirror_group.group_id = group_id
            mirror_group.use_manager_bot = False
            mirror_group.manager_group_id = None
            mirror_group.is_active = True
        else:
            mirror_group = MirrorGroup(
                bot_id=bot_id,
                group_id=group_id,
                use_manager_bot=False,
                manager_group_id=None,
                is_active=True,
                batch_size=int(os.getenv("MIRROR_BATCH_SIZE", 5)),
                batch_delay=int(os.getenv("MIRROR_BATCH_DELAY", 2)),
                flush_timeout=int(os.getenv("MIRROR_FLUSH_TIMEOUT", 3)),
            )
            session.add(mirror_group)

        session.commit()

    # Limpa cache (após fechar sessão)
    from core.redis_client import redis_client

    redis_client.delete(f"mirror_config:{bot_id}")

    # Limpa estado
    ConversationStateManager.clear_state(user_id)

    return {
        "text": (
            f"✅ **BOT CONFIGURADO**\n"
            f"─────────────────\n"
            f"🤖 Bot: @{bot_username}\n"
            f"👥 Grupo: `{group_id}`\n\n"
            f"**Status:** Espelhamento ativo!\n\n"
            f"**Importante:**\n"
            f"• Adicione o bot @{bot_username} ao grupo\n"
            f"• Configure como administrador\n"
            f"• Ative os tópicos (Forum Topics)\n"
            f"• As conversas serão espelhadas automaticamente"
        ),
        "keyboard": {
            "inline_keyboard": [
                [{"text": "✅ Concluído", "callback_data": "group_menu"}]
            ]
        },
    }


async def handle_group_batch_config(user_id: int, bot_id: int) -> Dict[str, Any]:
    """Menu de configuração de batch"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    with SessionLocal() as session:
        mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot_id).first()
        if not mirror_group:
            return {"text": "❌ Configuração não encontrada.", "keyboard": None}

        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": f"📦 Batch Size: {mirror_group.batch_size}",
                        "callback_data": "noop",
                    }
                ],
                [
                    {"text": "1", "callback_data": f"group_batch_size_{bot_id}_1"},
                    {"text": "3", "callback_data": f"group_batch_size_{bot_id}_3"},
                    {"text": "5", "callback_data": f"group_batch_size_{bot_id}_5"},
                    {"text": "7", "callback_data": f"group_batch_size_{bot_id}_7"},
                    {"text": "10", "callback_data": f"group_batch_size_{bot_id}_10"},
                ],
                [
                    {
                        "text": f"⏱ Delay: {mirror_group.batch_delay}s",
                        "callback_data": "noop",
                    }
                ],
                [
                    {"text": "1s", "callback_data": f"group_batch_delay_{bot_id}_1"},
                    {"text": "2s", "callback_data": f"group_batch_delay_{bot_id}_2"},
                    {"text": "3s", "callback_data": f"group_batch_delay_{bot_id}_3"},
                    {"text": "5s", "callback_data": f"group_batch_delay_{bot_id}_5"},
                ],
                [
                    {
                        "text": f"⏳ Timeout: {mirror_group.flush_timeout}s",
                        "callback_data": "noop",
                    }
                ],
                [
                    {"text": "3s", "callback_data": f"group_batch_timeout_{bot_id}_3"},
                    {"text": "5s", "callback_data": f"group_batch_timeout_{bot_id}_5"},
                    {
                        "text": "10s",
                        "callback_data": f"group_batch_timeout_{bot_id}_10",
                    },
                ],
                [{"text": "⬅️ Voltar", "callback_data": f"group_select_bot_{bot_id}"}],
            ]
        }

        return {
            "text": (
                "⚙️ **CONFIGURAÇÃO DE BATCH**\n"
                "─────────────────\n"
                f"**Batch Size**: {mirror_group.batch_size} mensagens\n"
                f"**Delay**: {mirror_group.batch_delay} segundos\n"
                f"**Timeout**: {mirror_group.flush_timeout} segundos\n\n"
                "Ajuste os valores abaixo:"
            ),
            "keyboard": keyboard,
        }


async def handle_group_batch_update(
    user_id: int, bot_id: int, param: str, value: int
) -> Dict[str, Any]:
    """Atualiza configuração de batch"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    with SessionLocal() as session:
        mirror_group = session.query(MirrorGroup).filter_by(bot_id=bot_id).first()
        if not mirror_group:
            return {"text": "❌ Configuração não encontrada.", "keyboard": None}

        if param == "size":
            mirror_group.batch_size = value
        elif param == "delay":
            mirror_group.batch_delay = value
        elif param == "timeout":
            mirror_group.flush_timeout = value

        session.commit()

        # Limpa cache
        from core.redis_client import redis_client

        redis_client.delete(f"mirror_config:{bot_id}")

        return {
            "text": f"✅ {param.title()} atualizado para {value}",
            "keyboard": None,
            "answer_callback": True,
        }


async def handle_group_stats(user_id: int) -> Dict[str, Any]:
    """Exibe estatísticas de espelhamento"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    from core.redis_client import redis_client
    from database.models import UserTopic

    with SessionLocal() as session:
        # Estatísticas gerais
        total_topics = session.query(UserTopic).count()
        active_topics = (
            session.query(UserTopic)
            .filter(UserTopic.last_batch_sent > datetime.now() - timedelta(hours=1))
            .count()
        )

        # Buffers no Redis
        buffer_keys = redis_client.keys("buffer:*:*")
        total_buffered = 0
        for key in buffer_keys:
            count = redis_client.hget(key, "count")
            if count:
                total_buffered += int(count)

        # Estatísticas por bot
        bot_stats = []
        bots = BotRepository.get_user_bots_sync(user_id)
        for bot in bots:
            topics = session.query(UserTopic).filter_by(bot_id=bot.id).count()
            if topics > 0:
                bot_stats.append(f"• @{bot.username}: {topics} tópicos")

        text = (
            "📊 **ESTATÍSTICAS DE ESPELHAMENTO**\n"
            "─────────────────\n"
            f"**Modo**: {os.getenv('MIRROR_MODE', 'batch').upper()}\n"
            f"**Total de Tópicos**: {total_topics}\n"
            f"**Tópicos Ativos (1h)**: {active_topics}\n"
            f"**Mensagens no Buffer**: {total_buffered}\n\n"
        )

        if bot_stats:
            text += "**Por Bot:**\n" + "\n".join(bot_stats)
        else:
            text += "Nenhum bot com tópicos ativos."

    return {
        "text": text,
        "keyboard": {
            "inline_keyboard": [
                [{"text": "🔄 Atualizar", "callback_data": "group_stats"}],
                [{"text": "⬅️ Voltar", "callback_data": "group_menu"}],
            ]
        },
    }


async def handle_mirror_control_callback(
    user_id: int, callback_data: str, callback_id: str
) -> Dict[str, Any]:
    """Processa callbacks dos botões de controle no tópico"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Parse callback_data: mirror_{action}_{user_topic_id}
    parts = callback_data.split("_")
    if len(parts) != 3:
        return {"text": "❌ Callback inválido", "answer_callback": True}

    action = parts[1]
    user_topic_id = int(parts[2])

    # Busca informações do UserTopic
    with SessionLocal() as session:
        user_topic = session.query(UserTopic).filter_by(id=user_topic_id).first()
        if not user_topic:
            return {"text": "❌ Configuração não encontrada", "answer_callback": True}

        bot_id = user_topic.bot_id
        user_telegram_id = user_topic.user_telegram_id

    # Enfileira ação
    result = handle_mirror_control_action.apply_async(
        args=[action, bot_id, user_telegram_id, callback_id, user_id],
        queue="mirror_high",
    ).get(timeout=5)

    return result


async def handle_group_recover_buffers(user_id: int) -> Dict[str, Any]:
    """Força recuperação de buffers órfãos"""
    if user_id not in settings.allowed_admin_ids_list:
        return None

    # Enfileira recuperação
    recover_orphan_buffers.delay()

    return {
        "text": "🔄 Recuperação de buffers órfãos iniciada.\n\nVerifique os logs para acompanhar.",
        "answer_callback": True,
    }


def _check_mirror_config(bot_id: int) -> bool:
    """Verifica se bot tem configuração de espelhamento"""
    with SessionLocal() as session:
        return session.query(MirrorGroup).filter_by(bot_id=bot_id).first() is not None
