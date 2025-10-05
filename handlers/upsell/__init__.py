"""Handlers para gerenciamento de Upsells"""

from .menu_handlers import (
    handle_add_upsell,
    handle_delete_upsell_confirm,
    handle_delete_upsell_menu,
    handle_upsell_menu,
    handle_upsell_menu_page,
    handle_upsell_select,
)

__all__ = [
    "handle_upsell_menu",
    "handle_upsell_menu_page",
    "handle_upsell_select",
    "handle_add_upsell",
    "handle_delete_upsell_menu",
    "handle_delete_upsell_confirm",
]
