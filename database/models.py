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

    __table_args__ = (Index("idx_bot_user", "bot_id", "telegram_id"),)


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
    general_prompt = Column(String(4096))  # Comportamento geral da IA
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
    phase_prompt = Column(String(4096), nullable=False)  # Prompt da fase
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
        Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )

    # Dados da transação PushinPay
    transaction_id = Column(String(128), nullable=False, unique=True)
    qr_code = Column(String(512), nullable=False)  # Chave PIX copia e cola
    qr_code_base64 = Column(String(2048))  # QR Code em base64 (opcional)
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


class MediaFileCache(Base):
    """Cache de file_ids de mídia por bot (stream entre bots)"""

    __tablename__ = "media_file_cache"

    id = Column(Integer, primary_key=True)
    original_file_id = Column(
        String(256), nullable=False
    )  # file_id do bot gerenciador
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
