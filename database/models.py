"""
SQLAlchemy Models
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Bot(Base):
    """Modelo de Bot Secundário"""

    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    token = Column(LargeBinary, nullable=False)  # criptografado
    username = Column(String(64), unique=True)
    display_name = Column(String(128))  # nome customizado pelo admin
    webhook_secret = Column(String(128))
    associated_offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="SET NULL"), nullable=True, index=True
    )  # Oferta associada ao bot (1 bot = 1 oferta)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_admin_active", "admin_id", "is_active"),)


class User(Base):
    """Modelo de Usuário"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    username = Column(String(64))
    first_name = Column(String(128))
    last_name = Column(String(128))
    first_interaction = Column(DateTime, server_default=func.now())
    last_interaction = Column(DateTime, onupdate=func.now())
    is_blocked = Column(Boolean, default=False)
    block_reason = Column(String(128))  # Razão do bloqueio
    blocked_at = Column(DateTime)  # Quando foi bloqueado

    __table_args__ = (
        Index("idx_bot_user", "bot_id", "telegram_id"),
        Index(
            "idx_bot_user_blocked", "bot_id", "is_blocked"
        ),  # Índice para queries de bloqueio
    )


class Event(Base):
    """Modelo de Evento/Log"""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String(64), nullable=False)
    payload = Column(String(2048))
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (Index("idx_bot_event_ts", "bot_id", "event_type", "created_at"),)


class BotAIConfig(Base):
    """Configuração de IA por bot"""

    __tablename__ = "bot_ai_configs"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_type = Column(
        String(32), default="reasoning"
    )  # 'reasoning' ou 'non-reasoning'
    general_prompt = Column(Text)  # Comportamento geral da IA
    temperature = Column(String(8), default="0.7")
    max_tokens = Column(Integer, default=2000)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AIPhase(Base):
    """Fases da IA com triggers"""

    __tablename__ = "ai_phases"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    phase_name = Column(String(128), nullable=False)  # Nome legível da fase
    phase_trigger = Column(
        String(32), nullable=True
    )  # Termo único (ex: "fcf4", "eko3") - NULL para fase inicial
    phase_prompt = Column(Text, nullable=False)  # Prompt da fase
    is_initial = Column(Boolean, default=False)  # Se é a fase inicial (sem trigger)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_bot_trigger", "bot_id", "phase_trigger", unique=True),)


class ConversationHistory(Base):
    """Histórico de conversa com IA"""

    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    role = Column(String(16), nullable=False)  # 'system', 'user', 'assistant'
    content = Column(String(8192), nullable=False)
    has_image = Column(Boolean, default=False)
    image_url = Column(String(512))

    # Métricas de tokens (economia com cache!)
    prompt_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    reasoning_tokens = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_bot_user_created", "bot_id", "user_telegram_id", "created_at"),
    )


class UserAISession(Base):
    """Sessão de IA do usuário"""

    __tablename__ = "user_ai_sessions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    current_phase_id = Column(Integer, ForeignKey("ai_phases.id", ondelete="SET NULL"))
    message_count = Column(Integer, default=0)
    last_interaction = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_bot_user_session", "bot_id", "user_telegram_id", unique=True),
    )


class Offer(Base):
    """Modelo de Oferta"""

    __tablename__ = "offers"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)  # Nome da oferta
    value = Column(String(32))  # Valor formatado (ex: "R$ 7,90")
    requires_manual_verification = Column(Boolean, default=False)  # Verificação manual
    manual_verification_trigger = Column(String(128))  # Termo que aciona verificação
    discount_trigger = Column(String(128))  # Termo que aciona desconto dinâmico
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_bot_offer_name", "bot_id", "name", unique=True),
        Index("idx_bot_active_offers", "bot_id", "is_active"),
    )


class OfferPitchBlock(Base):
    """Blocos de mensagem do pitch de vendas"""

    __tablename__ = "offer_pitch_blocks"

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_offer_blocks_order", "offer_id", "order"),)


class OfferDeliverable(Base):
    """Conteúdo entregável da oferta"""

    __tablename__ = "offer_deliverables"

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    content = Column(String(8192), nullable=False)  # Conteúdo do entregável
    type = Column(String(64))  # Tipo do entregável (link, código, arquivo, etc)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_offer_deliverable", "offer_id"),)


class RecoveryCampaign(Base):
    """Campanha de mensagens de recuperação por bot"""

    __tablename__ = "recovery_campaigns"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(128))
    timezone = Column(String(64), default="UTC")
    inactivity_threshold_seconds = Column(Integer, default=600)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    skip_paid_users = Column(Boolean, default=True)
    created_by = Column(BigInteger)
    updated_by = Column(BigInteger)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_recovery_campaign_bot", "bot_id", "is_active"),)


class RecoveryStep(Base):
    """Passo sequencial de uma campanha de recuperação"""

    __tablename__ = "recovery_steps"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(
        Integer, ForeignKey("recovery_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    order_index = Column(Integer, nullable=False)
    schedule_type = Column(String(32), nullable=False)  # relative, next_day, plus_days
    schedule_value = Column(String(64), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_recovery_step_order",
            "campaign_id",
            "order_index",
            unique=True,
        ),
    )


class RecoveryBlock(Base):
    """Bloco de mensagem configurável para recuperação"""

    __tablename__ = "recovery_blocks"

    id = Column(Integer, primary_key=True)
    step_id = Column(
        Integer, ForeignKey("recovery_steps.id", ondelete="CASCADE"), nullable=False
    )
    order_index = Column(Integer, nullable=False)
    text = Column(String(4096))
    parse_mode = Column(String(32), default="Markdown")
    media_file_id = Column(String(256))
    media_type = Column(String(32))
    delay_seconds = Column(Integer, default=0)
    auto_delete_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_recovery_block_order",
            "step_id",
            "order_index",
            unique=True,
        ),
    )


class RecoveryDelivery(Base):
    """Registro de envio/agendamento das mensagens de recuperação"""

    __tablename__ = "recovery_deliveries"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(
        Integer, ForeignKey("recovery_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    step_id = Column(
        Integer, ForeignKey("recovery_steps.id", ondelete="CASCADE"), nullable=False
    )
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    episode_id = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, index=True)
    scheduled_for = Column(DateTime, index=True)
    sent_at = Column(DateTime)
    message_ids_json = Column(Text)
    version_snapshot = Column(Integer)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_recovery_delivery_unique",
            "bot_id",
            "user_id",
            "step_id",
            "episode_id",
            unique=True,
        ),
        Index("idx_recovery_delivery_status", "bot_id", "user_id", "status"),
    )


class GatewayConfig(Base):
    """Configuração de gateway de pagamento por usuário"""

    __tablename__ = "gateway_configs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False, index=True)
    gateway_type = Column(String(32), nullable=False)  # 'pushinpay'
    encrypted_token = Column(LargeBinary, nullable=False)  # Token criptografado
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_admin_gateway_type", "admin_id", "gateway_type", unique=True),
    )


class BotGatewayConfig(Base):
    """Configuração de gateway específica por bot"""

    __tablename__ = "bot_gateway_configs"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    gateway_type = Column(String(32), nullable=False)  # 'pushinpay'
    encrypted_token = Column(LargeBinary, nullable=False)  # Token criptografado
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_bot_gateway_type", "bot_id", "gateway_type", unique=True),
    )


class PixTransaction(Base):
    """Registro de transações PIX"""

    __tablename__ = "pix_transactions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=True
    )
    upsell_id = Column(
        Integer, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=True
    )
    tracker_id = Column(
        Integer,
        ForeignKey("tracker_links.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Dados da transação PushinPay
    transaction_id = Column(String(128), nullable=False, unique=True)
    qr_code = Column(String(512), nullable=False)  # Chave PIX copia e cola
    qr_code_base64 = Column(Text)  # QR Code em base64 (sem limite de tamanho)
    value_cents = Column(Integer, nullable=False)  # Valor em centavos

    # Status e controle
    status = Column(String(32), default="created")  # created, paid, expired
    delivered_at = Column(DateTime)  # Quando o conteúdo foi entregue
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_bot_user_status", "bot_id", "user_telegram_id", "status"),
        Index("idx_chat_status", "chat_id", "status"),
        Index("idx_transaction_id", "transaction_id", unique=True),
    )


class OfferDeliverableBlock(Base):
    """Blocos de mensagem do entregável (sistema de blocos)"""

    __tablename__ = "offer_deliverable_blocks"

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_deliverable_blocks_order", "offer_id", "order"),)


class OfferManualVerificationBlock(Base):
    """Blocos de mensagem para verificação manual"""

    __tablename__ = "offer_manual_verification_blocks"

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_manual_verification_blocks_order", "offer_id", "order"),
    )


# Importa modelos de rastreio para registro na metadata sem criar ciclos
from .tracking_models import (  # noqa: E402  # isort: skip
    BotTrackingConfig,
    TrackerAttribution,
    TrackerDailyStat,
    TrackerLink,
)


class OfferDiscountBlock(Base):
    """Blocos de mensagem para respostas de desconto"""

    __tablename__ = "offer_discount_blocks"

    id = Column(Integer, primary_key=True)
    offer_id = Column(
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)

    text = Column(String(4096))
    media_file_id = Column(String(256))
    media_type = Column(String(32))

    delay_seconds = Column(Integer, default=0)
    auto_delete_seconds = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_discount_blocks_order", "offer_id", "order"),)


class MediaFileCache(Base):
    """Cache de file_ids de mídia por bot (stream entre bots)"""

    __tablename__ = "media_file_cache"

    id = Column(Integer, primary_key=True)
    original_file_id = Column(String(256), nullable=False)  # file_id do bot gerenciador
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )  # bot que vai usar
    cached_file_id = Column(String(256), nullable=False)  # file_id válido para o bot
    media_type = Column(String(32), nullable=False)  # photo, video, etc
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_media_cache_lookup", "original_file_id", "bot_id"),
        Index("idx_media_cache_bot", "bot_id"),
    )


class AIAction(Base):
    """Ações da IA com gatilhos personalizados"""

    __tablename__ = "ai_actions"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    action_name = Column(String(128), nullable=False)  # Nome da ação (é o gatilho)
    track_usage = Column(Boolean, default=False)  # Se rastrear uso INACTIVE/ACTIVATED
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_bot_action_name", "bot_id", "action_name", unique=True),
        Index("idx_bot_active_actions", "bot_id", "is_active"),
    )


class AIActionBlock(Base):
    """Blocos de mensagem das ações (sistema de blocos)"""

    __tablename__ = "ai_action_blocks"

    id = Column(Integer, primary_key=True)
    action_id = Column(
        Integer, ForeignKey("ai_actions.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_action_blocks_order", "action_id", "order"),)


class StartTemplate(Base):
    """Template da mensagem inicial /start por bot"""

    __tablename__ = "start_templates"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_start_template_bot", "bot_id", unique=True),
        Index("idx_start_template_active", "bot_id", "is_active"),
    )


class StartTemplateBlock(Base):
    """Blocos que compõem o template de /start"""

    __tablename__ = "start_template_blocks"

    id = Column(Integer, primary_key=True)
    template_id = Column(
        Integer, ForeignKey("start_templates.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)
    text = Column(String(4096))
    media_file_id = Column(String(256))
    media_type = Column(String(32))
    delay_seconds = Column(Integer, default=0)
    auto_delete_seconds = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_start_blocks_order", "template_id", "order"),)


class StartMessageStatus(Base):
    """Estado de envio da mensagem inicial por usuário"""

    __tablename__ = "start_message_status"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    template_version = Column(Integer, nullable=False, default=1)
    sent_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index(
            "idx_start_message_status_unique",
            "bot_id",
            "user_telegram_id",
            unique=True,
        ),
        Index("idx_start_message_status_bot", "bot_id"),
    )


class UserActionStatus(Base):
    """Rastreamento de status de ações por usuário"""

    __tablename__ = "user_action_status"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    action_id = Column(
        Integer, ForeignKey("ai_actions.id", ondelete="CASCADE"), nullable=False
    )
    status = Column(String(16), default="INACTIVE")  # INACTIVE ou ACTIVATED
    last_triggered_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index(
            "idx_bot_user_action",
            "bot_id",
            "user_telegram_id",
            "action_id",
            unique=True,
        ),
        Index("idx_action_status", "action_id", "status"),
    )


class Upsell(Base):
    """Modelo de Upsell"""

    __tablename__ = "upsells"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    upsell_trigger = Column(String(128))  # Trigger para #1 (nome que IA menciona)
    value = Column(String(32))  # Valor formatado (R$ 19,90)
    order = Column(Integer, nullable=False)  # 1, 2, 3...
    is_pre_saved = Column(Boolean, default=False)  # True para linha 1
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_bot_upsell_order", "bot_id", "order", unique=True),
        Index("idx_bot_active_upsells", "bot_id", "is_active"),
    )


class UpsellAnnouncementBlock(Base):
    """Blocos de mensagem do anúncio de upsell"""

    __tablename__ = "upsell_announcement_blocks"

    id = Column(Integer, primary_key=True)
    upsell_id = Column(
        Integer, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_upsell_announcement_order", "upsell_id", "order"),)


class UpsellDeliverableBlock(Base):
    """Blocos de mensagem do entregável de upsell"""

    __tablename__ = "upsell_deliverable_blocks"

    id = Column(Integer, primary_key=True)
    upsell_id = Column(
        Integer, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)  # Ordem de envio (1, 2, 3...)

    # Conteúdo da mensagem
    text = Column(String(4096))  # Texto ou legenda
    media_file_id = Column(String(256))  # file_id do Telegram
    media_type = Column(String(32))  # 'photo', 'video', 'audio', 'gif', 'document'

    # Efeitos
    delay_seconds = Column(Integer, default=0)  # Delay antes de enviar
    auto_delete_seconds = Column(Integer, default=0)  # Auto-deletar após X segundos

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_upsell_deliverable_order", "upsell_id", "order"),)


class UpsellPhaseConfig(Base):
    """Configuração de fase do upsell"""

    __tablename__ = "upsell_phase_configs"

    id = Column(Integer, primary_key=True)
    upsell_id = Column(
        Integer,
        ForeignKey("upsells.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    phase_prompt = Column(Text, nullable=False)  # Prompt da fase
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class UpsellSchedule(Base):
    """Agendamento de upsell"""

    __tablename__ = "upsell_schedules"

    id = Column(Integer, primary_key=True)
    upsell_id = Column(
        Integer,
        ForeignKey("upsells.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    is_immediate = Column(Boolean, default=False)  # True apenas para #1
    days_after = Column(Integer, default=0)  # Para #2+
    hours = Column(Integer, default=0)
    minutes = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class UserUpsellHistory(Base):
    """Histórico de upsells por usuário"""

    __tablename__ = "user_upsell_history"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    upsell_id = Column(
        Integer, ForeignKey("upsells.id", ondelete="CASCADE"), nullable=False
    )
    sent_at = Column(DateTime)  # Quando anúncio foi enviado
    paid_at = Column(DateTime)  # Quando usuário pagou
    transaction_id = Column(String(128))  # ID da transação PIX
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_bot_user_upsell", "bot_id", "user_telegram_id", "upsell_id"),
        Index("idx_sent_status", "bot_id", "sent_at"),
    )


class BotAntiSpamConfig(Base):
    """Configuração de anti-spam por bot"""

    __tablename__ = "bot_antispam_configs"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Proteções básicas
    dot_after_start = Column(Boolean, default=True)  # '.' após /start
    repetition = Column(Boolean, default=True)  # Mensagens repetidas
    flood = Column(Boolean, default=True)  # Flood de mensagens
    links_mentions = Column(Boolean, default=True)  # Links e menções
    short_messages = Column(Boolean, default=True)  # Mensagens curtas
    loop_start = Column(Boolean, default=True)  # Loop de /start
    total_limit = Column(Boolean, default=False)  # Limite total de mensagens
    total_limit_value = Column(Integer, default=100)  # Valor do limite total

    # Proteções adicionais (sugestões)
    forward_spam = Column(Boolean, default=False)  # Spam de forwards
    emoji_flood = Column(Boolean, default=False)  # Flood de emojis
    char_repetition = Column(Boolean, default=False)  # Repetição de caracteres
    bot_speed = Column(Boolean, default=False)  # Velocidade bot-like
    media_spam = Column(Boolean, default=False)  # Spam de mídia
    sticker_spam = Column(Boolean, default=False)  # Spam de stickers
    contact_spam = Column(Boolean, default=False)  # Spam de contatos
    location_spam = Column(Boolean, default=False)  # Spam de localização

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_bot_antispam", "bot_id", unique=True),)


class MirrorGroup(Base):
    """Configuração do grupo de espelhamento por bot"""

    __tablename__ = "mirror_groups"

    id = Column(Integer, primary_key=True)
    bot_id = Column(
        Integer, ForeignKey("bots.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    group_id = Column(BigInteger, nullable=False)  # ID do grupo/supergrupo
    is_active = Column(Boolean, default=True)

    # Modo centralizado (usar bot gerenciador)
    use_manager_bot = Column(Boolean, default=False)  # Usar bot gerenciador
    manager_group_id = Column(
        BigInteger
    )  # ID do grupo centralizado (se use_manager_bot=True)

    # Configurações de batching
    batch_size = Column(Integer, default=5)  # Mensagens por batch (1-10)
    batch_delay = Column(Integer, default=2)  # Segundos entre batches
    flush_timeout = Column(Integer, default=3)  # Timeout para flush automático

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_mirror_bot", "bot_id", unique=True),)


class UserTopic(Base):
    """Mapeamento de usuário para tópico no grupo de espelhamento"""

    __tablename__ = "user_topics"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    topic_id = Column(Integer, nullable=False)  # message_thread_id do tópico
    pinned_message_id = Column(BigInteger)  # ID da mensagem fixada com controles

    # Estados de controle
    is_banned = Column(Boolean, default=False)
    is_ai_paused = Column(Boolean, default=False)

    # Métricas
    last_batch_sent = Column(DateTime)
    messages_mirrored = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        Index("idx_user_topic", "bot_id", "user_telegram_id", unique=True),
        Index("idx_topic_lookup", "bot_id", "topic_id"),
    )


class MirrorBuffer(Base):
    """Buffer persistente de mensagens para espelhamento"""

    __tablename__ = "mirror_buffers"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_telegram_id = Column(BigInteger, nullable=False)
    topic_id = Column(Integer)

    # Mensagens em JSON
    messages = Column(Text, nullable=False)  # JSON array de mensagens
    message_count = Column(Integer, default=0)

    # Status
    status = Column(String(16), default="pending")  # pending, sending, sent, failed
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    scheduled_flush = Column(DateTime)
    sent_at = Column(DateTime)

    __table_args__ = (
        Index("idx_buffer_status", "status", "created_at"),
        Index("idx_buffer_user", "bot_id", "user_telegram_id"),
    )


class MirrorGlobalConfig(Base):
    """Configuração global de espelhamento por administrador"""

    __tablename__ = "mirror_global_configs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(
        BigInteger, unique=True, nullable=False
    )  # ID do admin no Telegram
    use_centralized_mode = Column(Boolean, default=False)  # Ativar modo centralizado
    manager_group_id = Column(BigInteger)  # ID do grupo único para todos os bots
    is_active = Column(Boolean, default=True)

    # Configurações de batch globais
    batch_size = Column(Integer, default=5)
    batch_delay = Column(Integer, default=2)
    flush_timeout = Column(Integer, default=3)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_global_admin", "admin_id", unique=True),)


class AudioPreference(Base):
    """Preferências de processamento de áudio por administrador do bot gerenciador"""

    __tablename__ = "audio_preferences"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, unique=True, nullable=False, index=True)
    mode = Column(String(16), nullable=False, default="default")  # default | whisper
    default_reply = Column(
        String(1024),
        nullable=False,
        default="Recebemos seu áudio. Em breve entraremos em contato.",
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (Index("idx_audio_pref_admin", "admin_id", unique=True),)


def _register_extra_models() -> None:
    from . import stats_models  # noqa: F401
    from .tracking_models import (  # noqa: F401
        BotTrackingConfig,
        TrackerAttribution,
        TrackerDailyStat,
        TrackerLink,
    )


_register_extra_models()
