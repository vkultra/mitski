"""
Sistema de Ofertas - Handlers
"""

# Block handlers
from .block_handlers import (
    handle_block_autodel_click,
    handle_block_autodel_input,
    handle_block_delay_click,
    handle_block_delay_input,
    handle_block_effects_click,
    handle_block_media_click,
    handle_block_media_input,
    handle_block_text_click,
    handle_block_text_input,
)

# Creation handlers
from .creation_handlers import (
    handle_create_offer,
    handle_offer_name_input,
    handle_offer_value_input,
    handle_save_offer,
)

# Deliverable block handlers
from .deliverable_block_handlers import (
    handle_deliverable_block_autodel_click,
    handle_deliverable_block_autodel_input,
    handle_deliverable_block_delay_click,
    handle_deliverable_block_delay_input,
    handle_deliverable_block_effects_click,
    handle_deliverable_block_media_click,
    handle_deliverable_block_media_input,
    handle_deliverable_block_text_click,
    handle_deliverable_block_text_input,
)

# Deliverable block menu handlers
from .deliverable_block_menu_handlers import (
    handle_create_deliverable_block,
    handle_delete_deliverable_block,
    handle_deliverable_blocks_menu,
    handle_preview_deliverable,
)

# Deliverable handlers (antigo)
from .deliverable_handlers import (
    handle_create_deliverable,
    handle_delete_deliverable,
    handle_deliverable_content_input,
    handle_offer_deliverable_menu,
)

# Edit handlers
from .edit_handlers import (
    handle_offer_edit_menu,
    handle_offer_manual_verification_toggle,
    handle_offer_save_final,
    handle_offer_value_click,
    handle_offer_value_edit_input,
)

# Manual verification block handlers
from .manual_verification_block_handlers import (
    handle_manual_verification_block_autodel_click,
    handle_manual_verification_block_autodel_input,
    handle_manual_verification_block_delay_click,
    handle_manual_verification_block_delay_input,
    handle_manual_verification_block_effects_click,
    handle_manual_verification_block_media_click,
    handle_manual_verification_block_media_input,
    handle_manual_verification_block_text_click,
    handle_manual_verification_block_text_input,
)

# Manual verification menu handlers
from .manual_verification_menu_handlers import (
    handle_create_manual_verification_block,
    handle_delete_manual_verification_block,
    handle_manual_verification_menu,
    handle_preview_manual_verification,
    handle_set_verification_trigger,
    handle_verification_trigger_input,
)

# Menu handlers
from .menu_handlers import (
    handle_associate_offer,
    handle_delete_offer,
    handle_delete_offer_confirm,
    handle_dissociate_offer,
    handle_list_offers,
    handle_list_offers_delete,
    handle_offer_menu,
)

# Pitch menu handlers
from .pitch_menu_handlers import (
    handle_create_pitch_block,
    handle_delete_block,
    handle_offer_pitch_menu,
    handle_preview_pitch,
)

__all__ = [
    # Menu handlers
    "handle_offer_menu",
    "handle_list_offers",
    "handle_list_offers_delete",
    "handle_delete_offer_confirm",
    "handle_delete_offer",
    "handle_associate_offer",
    "handle_dissociate_offer",
    # Creation handlers
    "handle_create_offer",
    "handle_offer_name_input",
    "handle_offer_value_input",
    "handle_save_offer",
    # Pitch menu handlers
    "handle_offer_pitch_menu",
    "handle_create_pitch_block",
    "handle_delete_block",
    "handle_preview_pitch",
    # Block handlers
    "handle_block_text_click",
    "handle_block_text_input",
    "handle_block_media_click",
    "handle_block_media_input",
    "handle_block_effects_click",
    "handle_block_delay_click",
    "handle_block_delay_input",
    "handle_block_autodel_click",
    "handle_block_autodel_input",
    # Edit handlers
    "handle_offer_edit_menu",
    "handle_offer_value_click",
    "handle_offer_value_edit_input",
    "handle_offer_manual_verification_toggle",
    "handle_offer_save_final",
    # Deliverable handlers (antigo)
    "handle_offer_deliverable_menu",
    "handle_create_deliverable",
    "handle_deliverable_content_input",
    "handle_delete_deliverable",
    # Deliverable block menu handlers
    "handle_deliverable_blocks_menu",
    "handle_create_deliverable_block",
    "handle_delete_deliverable_block",
    "handle_preview_deliverable",
    # Deliverable block handlers
    "handle_deliverable_block_text_click",
    "handle_deliverable_block_text_input",
    "handle_deliverable_block_media_click",
    "handle_deliverable_block_media_input",
    "handle_deliverable_block_effects_click",
    "handle_deliverable_block_delay_click",
    "handle_deliverable_block_delay_input",
    "handle_deliverable_block_autodel_click",
    "handle_deliverable_block_autodel_input",
    # Manual verification menu handlers
    "handle_manual_verification_menu",
    "handle_set_verification_trigger",
    "handle_verification_trigger_input",
    "handle_create_manual_verification_block",
    "handle_delete_manual_verification_block",
    "handle_preview_manual_verification",
    # Manual verification block handlers
    "handle_manual_verification_block_text_click",
    "handle_manual_verification_block_text_input",
    "handle_manual_verification_block_media_click",
    "handle_manual_verification_block_media_input",
    "handle_manual_verification_block_effects_click",
    "handle_manual_verification_block_delay_click",
    "handle_manual_verification_block_delay_input",
    "handle_manual_verification_block_autodel_click",
    "handle_manual_verification_block_autodel_input",
]
